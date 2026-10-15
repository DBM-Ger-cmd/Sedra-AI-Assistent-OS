import importlib.util
import json
import random
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from guppi_runtime.code_generation import TARGET_KEYS, unusable_answer
from guppi_runtime.models.base import ModelAdapterError
from guppi_runtime.models.llamacpp import LlamaCppServerAdapter
from guppi_runtime.models.recording import Recorder, ReplayAdapter, load_recordings
from guppi_runtime.models.router import ModelRouter
from guppi_runtime.runaway_guard import RunawayGuard


def feed_all(guard, text, step=200):
    verdict = None
    for i in range(0, len(text), step):
        verdict = guard.feed(text[i:i + step])
    return verdict


def varied_text(chars, seed=7):
    rng = random.Random(seed)
    words = ["def", "return", "self", "assert", "value", "stuck", "count", "tool", "guard", "check", "history", "entry", "result", "signature"]
    out = []
    while sum(len(w) + 1 for w in out) < chars:
        out.append(rng.choice(words) + str(rng.randrange(1000)))
    return " ".join(out)


class DetectorTests(unittest.TestCase):
    def test_ordinary_varied_text_is_never_a_runaway(self):
        self.assertIsNone(feed_all(RunawayGuard(), varied_text(40000)))

    def test_long_legitimate_code_with_similar_lines_is_not_a_runaway(self):
        code = "".join(f"    self.assertEqual(g.check('A', {{'v': {i}}}), OK)  # case {i}\n" for i in range(200))
        self.assertGreater(len(code), 6000)
        self.assertIsNone(feed_all(RunawayGuard(), code))

    def test_a_table_of_identical_short_rows_below_the_span_is_not_a_runaway(self):
        self.assertIsNone(feed_all(RunawayGuard(), "x = 0000000000000000000000000\n" * 40))     # 1200 characters

    def test_a_repeated_short_block_is_a_runaway(self):
        verdict = feed_all(RunawayGuard(), varied_text(500) + "I will now check the file again.\n" * 120)
        self.assertEqual(verdict["reason"], "repetition")
        self.assertEqual(verdict["period"], len("I will now check the file again.\n"))
        self.assertGreaterEqual(verdict["span"], 3000)
        self.assertIn("check the file", verdict["sample"])

    def test_the_span_must_reach_the_minimum(self):
        self.assertIsNone(feed_all(RunawayGuard(), "ab" * 1000))              # 2000 characters
        self.assertEqual(feed_all(RunawayGuard(), "ab" * 1600)["reason"], "repetition")

    def test_the_number_of_repeats_depends_on_the_block_length(self):
        long_block = varied_text(1500)[:1200]
        self.assertEqual(len(long_block), 1200)
        self.assertIsNone(feed_all(RunawayGuard(), long_block * 2))           # 2400 characters, below the span
        self.assertEqual(feed_all(RunawayGuard(), long_block * 3)["period"], 1200)      # a block over 1000 characters: 3 repeats are enough
        mid = varied_text(800)[:800]
        self.assertIsNone(feed_all(RunawayGuard(), mid * 3))                  # a block up to 1000: 4 repeats are needed (3 x 800 = 2400)
        self.assertEqual(feed_all(RunawayGuard(), mid * 4)["period"], 800)

    def test_endless_whitespace_is_a_runaway(self):
        self.assertEqual(feed_all(RunawayGuard(), " " * 4000)["reason"], "repetition")
        self.assertEqual(feed_all(RunawayGuard(), "\n" * 4000)["reason"], "repetition")

    def test_garbage_tokens(self):
        self.assertIsNone(feed_all(RunawayGuard(), "answer " + "<unused49>" * 19))
        verdict = feed_all(RunawayGuard(), "answer " + "<unused49>" * 25)
        self.assertEqual((verdict["reason"], verdict["sample"]), ("garbage", "<unused49>"))

    def test_the_verdict_does_not_depend_on_the_chunk_size(self):
        text = varied_text(300) + "loop loop loop. " * 400
        a, b, c = RunawayGuard(), RunawayGuard(), RunawayGuard()
        self.assertEqual(feed_all(a, text, 7)["reason"], "repetition")
        self.assertEqual(feed_all(b, text, 5000)["reason"], "repetition")
        self.assertEqual(feed_all(c, text, 1)["reason"], "repetition")

    def test_the_verdict_is_kept_and_total_chars_count_everything(self):
        g = RunawayGuard()
        first = feed_all(g, "ab" * 2000)
        self.assertIsNotNone(first)
        seen = g.total_chars
        self.assertEqual(seen, first["chars"])
        self.assertIs(g.feed("something else entirely"), first)
        self.assertEqual(g.total_chars, seen)                              # nothing is counted after the verdict

    def test_custom_settings(self):
        g = RunawayGuard(min_span=400, check_every=50)
        self.assertEqual(feed_all(g, "xyz\n" * 150, 50)["reason"], "repetition")
        self.assertEqual(feed_all(RunawayGuard(max_garbage=3, check_every=1), "<unused1><unused2><unused3>", 5)["reason"], "garbage")

    def test_the_check_is_fast_on_a_full_window(self):
        g = RunawayGuard()
        started = time.monotonic()
        feed_all(g, varied_text(60000), 256)
        self.assertLess(time.monotonic() - started, 5.0)


class FakeServer:
    """A minimal OpenAI-style streaming endpoint on 127.0.0.1. `script` is a list of event dicts (sent as SSE) or a callable that yields them."""

    def __init__(self, script=None, status=200):
        outer = self
        self.script, self.status = script or [], status
        self.payloads, self.sent_bytes, self.client_left = [], 0, threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass

            def do_GET(self):
                body = json.dumps({"data": [{"id": "m"}]}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                outer.payloads.append(json.loads(self.rfile.read(length) or b"{}"))
                if outer.status != 200:
                    self.send_response(outer.status); self.end_headers(); self.wfile.write(b'{"error":"boom"}'); return
                if not outer.payloads[-1].get("stream"):
                    body = json.dumps({"choices": [{"message": {"content": "plain"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers()
                    self.wfile.write(body); return
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
                events = outer.script() if callable(outer.script) else outer.script
                try:
                    for event in events:
                        data = ("data: " + (event if isinstance(event, str) else json.dumps(event)) + "\n\n").encode()
                        self.wfile.write(data); self.wfile.flush(); outer.sent_bytes += len(data)
                        if outer.sent_bytes > 4_000_000: break                 # safety: never run forever if the client does not leave
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                    outer.client_left.set()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"

    def close(self):
        self.httpd.shutdown(); self.httpd.server_close()


def delta(content=None, reasoning=None, finish=None, usage=None):
    d = {}
    if content is not None: d["content"] = content
    if reasoning is not None: d["reasoning_content"] = reasoning
    event = {"choices": [{"delta": d, "finish_reason": finish}]}
    if usage: event["usage"] = usage
    return event


MESSAGES = [{"role": "user", "content": "go"}]


class StreamedAdapterTests(unittest.TestCase):
    def serve(self, script=None, status=200):
        server = FakeServer(script, status)
        self.addCleanup(server.close)
        return server, LlamaCppServerAdapter(server.url, timeout=10)

    def test_a_normal_stream_is_assembled_and_the_request_asks_for_usage(self):
        server, adapter = self.serve([delta("Hel"), delta("lo"), delta("", finish="stop"), {"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 4}}, "[DONE]"])
        out = adapter.chat(MESSAGES, model="m", stream_guard=True, max_tokens=50)
        self.assertEqual((out["content"], out["finish_reason"], out["truncated"], out["empty_answer"], out["runaway"]), ("Hello", "stop", False, False, None))
        self.assertEqual(out["raw"]["streamed"], True)
        self.assertEqual((out["usage"] or {}).get("output_tokens"), 4)
        self.assertTrue(server.payloads[0]["stream"])
        self.assertEqual(server.payloads[0]["stream_options"], {"include_usage": True})
        self.assertEqual(server.payloads[0]["max_tokens"], 50)

    def test_without_the_option_nothing_changes(self):
        server, adapter = self.serve()
        out = adapter.chat(MESSAGES, model="m")
        self.assertEqual(out["content"], "plain")
        self.assertFalse(server.payloads[0]["stream"])
        self.assertNotIn("runaway", out)

    def test_thinking_is_counted_and_not_part_of_the_answer(self):
        server, adapter = self.serve([delta(reasoning="let me think"), delta(reasoning=" more"), delta("answer"), delta(finish="stop"), "[DONE]"])
        out = adapter.chat(MESSAGES, model="m", stream_guard=True)
        self.assertEqual((out["content"], out["reasoning_chars"]), ("answer", len("let me think more")))

    def test_a_cut_off_answer_is_truncated(self):
        server, adapter = self.serve([delta("partial"), delta(finish="length"), "[DONE]"])
        out = adapter.chat(MESSAGES, model="m", stream_guard=True)
        self.assertEqual((out["finish_reason"], out["truncated"], out["runaway"]), ("length", True, None))

    def test_a_runaway_answer_stops_the_stream_early(self):
        def endless():
            yield delta("start of the answer. ")
            while True:
                yield delta("I will now check the file again. ")
        server, adapter = self.serve(endless)
        out = adapter.chat(MESSAGES, model="m", stream_guard=True)
        self.assertEqual((out["finish_reason"], out["truncated"]), ("runaway", True))
        self.assertEqual((out["runaway"]["reason"], out["runaway"]["channel"]), ("repetition", "answer"))
        self.assertTrue(out["content"].startswith("start of the answer."))
        self.assertTrue(server.client_left.wait(5), "the server did not see the connection close")
        self.assertLess(server.sent_bytes, 1_000_000)                      # nowhere near a token limit

    def test_a_runaway_in_the_thinking_is_found_too(self):
        def endless():
            while True:
                yield delta(reasoning="wait, let me reconsider the whole thing once more. ")
        server, adapter = self.serve(endless)
        out = adapter.chat(MESSAGES, model="m", stream_guard=True)
        self.assertEqual((out["finish_reason"], out["runaway"]["channel"], out["content"]), ("runaway", "thinking", ""))
        self.assertTrue(out["empty_answer"])

    def test_garbage_tokens_are_a_runaway(self):
        def garbage():
            yield delta("ok ")
            while True:
                yield delta("<unused49>")
        server, adapter = self.serve(garbage)
        self.assertEqual(adapter.chat(MESSAGES, model="m", stream_guard=True)["runaway"]["reason"], "garbage")

    def test_guard_settings_can_be_given_and_wrong_ones_are_refused(self):
        def endless():
            while True:
                yield delta("abcdefgh ")
        server, adapter = self.serve(endless)
        out = adapter.chat(MESSAGES, model="m", stream_guard={"min_span": 500, "check_every": 64})
        self.assertEqual(out["runaway"]["reason"], "repetition")
        with self.assertRaises(ModelAdapterError) as ctx: adapter.chat(MESSAGES, model="m", stream_guard={"bogus": 1})
        self.assertEqual(str(ctx.exception), "invalid_stream_guard")

    def test_harmony_output_is_split_while_streaming(self):
        server, adapter = self.serve([delta("<|channel|>analysis<|message|>thinking<|end|><|channel|>final<|message|>the answer<|end|>"), delta(finish="stop"), "[DONE]"])
        out = adapter.chat(MESSAGES, model="m", stream_guard=True)
        self.assertEqual(out["content"], "the answer")
        self.assertGreater(out["reasoning_chars"], 0)

    def test_a_server_error_is_an_adapter_error(self):
        server, adapter = self.serve(status=500)
        with self.assertRaises(ModelAdapterError): adapter.chat(MESSAGES, model="m", stream_guard=True)

    def test_a_stream_without_done_still_returns_what_arrived(self):
        server, adapter = self.serve([delta("some "), delta("text")])
        self.assertEqual(adapter.chat(MESSAGES, model="m", stream_guard=True)["content"], "some text")


class RouterAndRecordingTests(unittest.TestCase):
    def test_the_option_reaches_the_adapter_and_the_verdict_is_recorded_and_replayed(self):
        def endless():
            while True:
                yield delta("same thing again and again. ")
        server = FakeServer(endless)
        self.addCleanup(server.close)
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        router = ModelRouter(); router.register(LlamaCppServerAdapter(server.url, timeout=10)); router.recorder = Recorder(Path(tmp.name))
        out = router.chat("M-1", MESSAGES, provider="llama-cpp-server", model="m", stream_guard=True)
        self.assertEqual(out["finish_reason"], "runaway")
        entry = load_recordings(tmp.name)[0]
        self.assertEqual((entry["reply"]["finish_reason"], entry["reply"]["runaway"]["reason"]), ("runaway", "repetition"))
        replayed = ReplayAdapter(load_recordings(tmp.name)).chat(MESSAGES, model="m", stream_guard=True)
        self.assertEqual((replayed["finish_reason"], replayed["runaway"]["reason"], replayed["content"]), ("runaway", "repetition", out["content"]))


class GenerationMappingTests(unittest.TestCase):
    def test_unusable_answers_are_named(self):
        self.assertEqual(unusable_answer({"content": "partial", "runaway": {"reason": "repetition"}}), "model_answer_runaway")
        self.assertEqual(unusable_answer({"content": "", "truncated": True}), "model_answer_truncated")
        self.assertEqual(unusable_answer({"content": "  ", "truncated": False}), "model_answer_empty")
        self.assertEqual(unusable_answer({"content": None}), "model_answer_empty")
        self.assertIsNone(unusable_answer({"content": '{"changes": []}', "truncated": False}))
        self.assertIsNone(unusable_answer({"content": "text", "runaway": None}))

    def test_the_target_may_carry_the_option(self):
        self.assertIn("stream_guard", TARGET_KEYS)

    def test_the_harness_treats_a_runaway_as_a_retryable_bad_answer_and_switches_the_guard_on(self):
        source = (Path(__file__).resolve().parents[1] / "benchmarks" / "e1_golden_path.py").read_text(encoding="utf-8")
        self.assertIn('"model_answer_runaway"', source.split("RETRYABLE = (")[1].split(")")[0])
        self.assertIn('"stream_guard": budget.get("stream_guard", True) or None', source)


if __name__ == "__main__":
    unittest.main()
