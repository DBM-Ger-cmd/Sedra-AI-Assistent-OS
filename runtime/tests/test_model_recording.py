import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from guppi_runtime.models.base import BaseModelAdapter, ModelAdapterError
from guppi_runtime.models.recording import (CONTENT_CAP, MESSAGE_CAP, Recorder, ReplayAdapter, load_recordings, request_digest)
from guppi_runtime.models.router import ModelRouter
from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]
MESSAGES = [{"role": "system", "content": "Reply with JSON."}, {"role": "user", "content": "write loop_guard.py"}]


class FakeAdapter(BaseModelAdapter):
    id = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def health(self): return True

    def chat(self, messages, model=None, **kwargs):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return {"provider": self.id, "model": model, "content": reply, "raw": {"big": "x" * 1000}, "usage": {"input_tokens": 7, "output_tokens": 3},
                "finish_reason": "length" if reply == "cut" else "stop", "truncated": reply == "cut", "reasoning_chars": 0, "empty_answer": not reply}


def router_with(adapter, directory):
    router = ModelRouter()
    router.register(adapter)
    router.recorder = Recorder(directory)
    return router


class Digest(unittest.TestCase):
    def test_same_request_same_digest(self):
        self.assertEqual(request_digest(MESSAGES, "m", {"temperature": 0.1}), request_digest(list(MESSAGES), "m", {"temperature": 0.1}))
        self.assertEqual(len(request_digest(MESSAGES, "m", {})), 24)

    def test_each_part_of_the_request_matters(self):
        base = request_digest(MESSAGES, "m", {"temperature": 0.1, "max_tokens": 100})
        self.assertNotEqual(base, request_digest(MESSAGES[:1], "m", {"temperature": 0.1, "max_tokens": 100}))
        self.assertNotEqual(base, request_digest(MESSAGES, "other", {"temperature": 0.1, "max_tokens": 100}))
        self.assertNotEqual(base, request_digest(MESSAGES, "m", {"temperature": 0.2, "max_tokens": 100}))
        self.assertNotEqual(base, request_digest(MESSAGES, "m", {"temperature": 0.1, "max_tokens": 101}))
        self.assertNotEqual(base, request_digest(MESSAGES, "m", {"temperature": 0.1, "max_tokens": 100, "reasoning_effort": "high"}))

    def test_the_stream_guard_is_part_of_the_request(self):
        self.assertNotEqual(request_digest(MESSAGES, "m", {"max_tokens": 5, "stream_guard": True}), request_digest(MESSAGES, "m", {"max_tokens": 5}))
        self.assertEqual(request_digest(MESSAGES, "m", {"stream_guard": None}), request_digest(MESSAGES, "m", {}))

    def test_unset_and_unknown_settings_do_not_matter(self):
        self.assertEqual(request_digest(MESSAGES, "m", {"temperature": None}), request_digest(MESSAGES, "m", {}))
        self.assertEqual(request_digest(MESSAGES, "m", {"foo": 1}), request_digest(MESSAGES, "m", {}))


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "model_recordings"

    def lines(self, name):
        return [json.loads(x) for x in (self.dir / name).read_text(encoding="utf-8").splitlines()]

    def test_a_call_through_the_router_is_recorded_with_the_full_reply(self):
        adapter = FakeAdapter(["the whole reply", "cut"])
        router = router_with(adapter, self.dir)
        router.chat("M-1", MESSAGES, provider="fake", model="m", temperature=0.1, max_tokens=50)
        router.chat("M-1", MESSAGES, provider="fake", model="m", temperature=0.1, max_tokens=50)
        first, second = self.lines("M-1.jsonl")
        self.assertEqual((first["provider"], first["model"], first["mission_id"], first["sampling"]), ("fake", "m", "M-1", {"temperature": 0.1, "max_tokens": 50}))
        self.assertEqual(first["digest"], request_digest(MESSAGES, "m", {"temperature": 0.1, "max_tokens": 50}))
        self.assertEqual(first["reply"]["content"], "the whole reply")
        self.assertEqual((first["reply"]["finish_reason"], first["reply"]["truncated"], first["reply"]["usage"]["output_tokens"]), ("stop", False, 3))
        self.assertEqual((second["reply"]["finish_reason"], second["reply"]["truncated"]), ("length", True))
        self.assertEqual(first["request"][1], {"role": "user", "chars": 19, "content": "write loop_guard.py"})
        self.assertNotIn("raw", first["reply"])                                  # the provider's raw JSON is not kept
        self.assertGreaterEqual(first["seconds"], 0)

    def test_an_error_is_recorded_and_still_raised(self):
        router = router_with(FakeAdapter([ModelAdapterError("local_model_api_error:timed out")]), self.dir)
        with self.assertRaises(ModelAdapterError): router.chat("M-2", MESSAGES, provider="fake", model="m")
        entry = self.lines("M-2.jsonl")[0]
        self.assertIn("timed out", entry["error"])
        self.assertNotIn("reply", entry)

    def test_long_replies_and_messages_are_capped_but_counted(self):
        router = router_with(FakeAdapter(["y" * (CONTENT_CAP + 5)]), self.dir)
        long_messages = [{"role": "user", "content": "q" * (MESSAGE_CAP + 10)}]
        router.chat("M-3", long_messages, provider="fake", model="m")
        entry = self.lines("M-3.jsonl")[0]
        self.assertEqual((len(entry["reply"]["content"]), entry["reply"]["content_chars"], entry["reply"]["content_cut"]), (CONTENT_CAP, CONTENT_CAP + 5, True))
        self.assertEqual((len(entry["request"][0]["content"]), entry["request"][0]["chars"]), (MESSAGE_CAP, MESSAGE_CAP + 10))

    def test_ids_with_odd_characters_stay_inside_the_folder(self):
        router = router_with(FakeAdapter(["ok"]), self.dir)
        router.chat("../../evil name", MESSAGES, provider="fake", model="m")
        names = [p.name for p in self.dir.iterdir()]
        self.assertEqual(len(names), 1)
        self.assertNotIn("/", names[0]); self.assertNotIn("\\", names[0])
        self.assertTrue(self.dir.resolve() in (self.dir / names[0]).resolve().parents)

    def test_recording_can_never_break_the_inference(self):
        blocker = Path(self.tmp.name) / "a_file"
        blocker.write_text("not a folder")
        router = router_with(FakeAdapter(["fine"]), blocker / "sub")           # the folder cannot be created
        self.assertEqual(router.chat("M-4", MESSAGES, provider="fake", model="m")["content"], "fine")

    def test_without_a_recorder_nothing_is_written(self):
        router = ModelRouter(); router.register(FakeAdapter(["x"]))
        router.chat("M-5", MESSAGES, provider="fake", model="m")
        self.assertFalse(self.dir.exists())


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "model_recordings"

    def record(self, replies, mission="M-1", **kw):
        router = router_with(FakeAdapter(replies), self.dir)
        for _ in replies:
            try: router.chat(mission, MESSAGES, provider="fake", model="m", **kw)
            except ModelAdapterError: pass
        return load_recordings(self.dir)

    def test_a_recording_replays_to_the_same_answer(self):
        replay = ReplayAdapter(self.record(["the whole reply"], temperature=0.1))
        out = replay.chat(MESSAGES, model="m", temperature=0.1)
        self.assertEqual((out["content"], out["finish_reason"], out["truncated"], out["usage"]["output_tokens"]), ("the whole reply", "stop", False, 3))
        self.assertTrue(out["replayed"])
        self.assertTrue(replay.health())
        self.assertEqual(replay.list_models(), ["m"])

    def test_through_a_router_the_replay_stands_in_for_the_model(self):
        replay = ReplayAdapter(self.record(["answer"]), adapter_id="replay")
        router = ModelRouter(); router.register(replay)
        self.assertEqual(router.chat("M-9", MESSAGES, provider="replay", model="m")["content"], "answer")

    def test_a_request_that_was_never_recorded_is_an_error_not_a_guess(self):
        replay = ReplayAdapter(self.record(["answer"]))
        with self.assertRaises(ModelAdapterError) as ctx: replay.chat(MESSAGES, model="other-model")
        self.assertTrue(str(ctx.exception).startswith("replay_miss:"))
        with self.assertRaises(ModelAdapterError): replay.chat(MESSAGES, model="m", temperature=0.9)

    def test_several_recordings_of_one_request_come_back_in_order_then_the_last_repeats(self):
        replay = ReplayAdapter(self.record(["first", "cut", "third"]))
        got = [replay.chat(MESSAGES, model="m") for _ in range(5)]
        self.assertEqual([g["content"] for g in got], ["first", "cut", "third", "third", "third"])
        self.assertEqual(got[1]["truncated"], True)

    def test_a_recorded_error_is_raised_again(self):
        router = router_with(FakeAdapter([ModelAdapterError("local_model_api_error:boom")]), self.dir)
        with self.assertRaises(ModelAdapterError): router.chat("M-1", MESSAGES, provider="fake", model="m")
        with self.assertRaises(ModelAdapterError) as ctx: ReplayAdapter(load_recordings(self.dir)).chat(MESSAGES, model="m")
        self.assertIn("boom", str(ctx.exception))

    def test_load_recordings_reads_a_folder_or_one_file_and_skips_bad_lines(self):
        self.record(["a"], mission="M-1"); self.record(["b"], mission="M-2")
        (self.dir / "M-2.jsonl").write_text((self.dir / "M-2.jsonl").read_text(encoding="utf-8") + 'not json\n{"no_digest": 1}\n', encoding="utf-8")
        self.assertEqual(len(load_recordings(self.dir)), 2)
        self.assertEqual(len(load_recordings(self.dir / "M-1.jsonl")), 1)


class RuntimeWiring(unittest.TestCase):
    def runtime(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        return GuppiRuntime(Path(tmp.name) / "project", ARCH)

    def test_off_by_default(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GUPPI_RECORD_REPLIES", None)
            self.assertIsNone(getattr(self.runtime().model_router, "recorder", None))

    def test_switched_on_by_the_environment(self):
        for value in ("1", "true", "YES"):
            with self.subTest(value=value), unittest.mock.patch.dict(os.environ, {"GUPPI_RECORD_REPLIES": value}):
                rt = self.runtime()
                self.assertIsInstance(rt.model_router.recorder, Recorder)
                self.assertEqual(rt.model_router.recorder.directory, rt.project_root / "runtime_data" / "model_recordings")

    def test_other_values_do_not_switch_it_on(self):
        with unittest.mock.patch.dict(os.environ, {"GUPPI_RECORD_REPLIES": "0"}):
            self.assertIsNone(getattr(self.runtime().model_router, "recorder", None))


if __name__ == "__main__":
    unittest.main()
