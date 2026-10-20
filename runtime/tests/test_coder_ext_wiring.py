"""Acceptance of E-21 (coder_ext wired into the core, spec E21_KERNVERDRAHTUNG.md). Written by Claude 2026-10-10; moves to runtime/tests/ after the wiring is done."""
import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from guppi_runtime.devenv.devvm import DevWorkspace  # noqa: E402
from guppi_runtime.devenv.devvm_agents import AgentBudget, run_agent  # noqa: E402
from guppi_runtime.devenv.devvm_tools import DevToolBox  # noqa: E402
from guppi_runtime.coder_ext import CoderExtensions  # noqa: E402
from guppi_runtime.coder_ext.replay_log import Player  # noqa: E402
from guppi_runtime.coder_ext.coder_cards import CARDS  # noqa: E402

POLICY = {"max_files": 40, "max_file_bytes": 60000, "max_input_bytes": 200000}
A = "a = 1\nb = 2\n"
T = "def f(x):\n    if x:\n        return 1\n    return 2\n"
BIG = "".join(f"x{i} = {i}\n" for i in range(1, 301))
LONG = "".join(f"line_{i} = {i}\n" for i in range(100))


def tc(name, args, i=1):
    return {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def answer(calls=(), content="", prompt=100, reasoning=None):
    usage = {"prompt_tokens": prompt, "completion_tokens": 10}
    if reasoning is not None: usage["completion_tokens_details"] = {"reasoning_tokens": reasoning}
    return {"choices": [{"message": {"role": "assistant", "content": content, "tool_calls": list(calls)}, "finish_reason": "tool_calls" if calls else "stop"}], "usage": usage}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ws = DevWorkspace(Path(self.tmp.name), "M-E21001", policy=dict(POLICY)); self.ws.create()

    def box(self, enabled):
        return DevToolBox(self.ws, "solo", ext=CoderExtensions(enabled, tool_names=("read_file",)))

    def run_with(self, replies, cfg=None, budget=None):
        it, bodies = iter(replies), []

        def post(body):
            bodies.append(json.loads(json.dumps(body)))
            return next(it)
        return run_agent("solo", "task", self.ws, post, "m", coder_ext=cfg, budget=budget or AgentBudget(max_turns=30)), bodies


class ToolHookTests(Base):
    def test_e01_edit_and_write_need_a_read(self):
        self.ws.write("a.py", A); b = self.box("e01")
        out = b.call("edit_file", {"path": "a.py", "old": "a = 1", "new": "a = 5"})
        self.assertTrue(out.startswith("error: edit_file refused: you have not read a.py")); self.assertEqual(self.ws.read("a.py"), A)
        out = b.call("write_file", {"path": "./a.py", "content": "z = 0\n"})
        self.assertTrue(out.startswith("error: write_file refused: a.py exists and you have not read it")); self.assertEqual(self.ws.read("a.py"), A)
        self.assertIn("created", b.call("write_file", {"path": "n.py", "content": A}))
        b.call("read_file", {"path": "a.py"})
        self.assertTrue(b.call("edit_file", {"path": "a.py", "old": "a = 1", "new": "a = 5"}).startswith("edited a.py"))
        self.assertTrue(b.call("edit_file", {"path": "n.py", "old": "a = 1", "new": "a = 6"}).startswith("edited n.py"))
        self.assertEqual(b.ext_stats["refusals"], 2)

    def test_e01_partial_read_of_a_long_file_and_a_change_from_outside(self):
        self.ws.write("big.py", BIG); b = self.box("e01")
        b.call("read_file", {"path": "big.py"})
        out = b.call("write_file", {"path": "big.py", "content": "z\n"})
        self.assertIn("you have only seen lines 1-150 of big.py (300 lines)", out)
        self.ws.write("a.py", A); b.call("read_file", {"path": "a.py"}); self.ws.write("a.py", "a = 9\nb = 2\n")
        out = b.call("edit_file", {"path": "a.py", "old": "b = 2", "new": "b = 3"})
        self.assertTrue(out.startswith("edited a.py")); self.assertIn("(note: a.py changed since you last read it", out)
        self.assertEqual(self.ws.read("a.py"), "a = 9\nb = 3\n")

    def test_e08_fuzzy_fallback_only_when_on(self):
        self.ws.write("t.py", T)
        off = DevToolBox(self.ws, "solo")
        self.assertIn("old was not found", off.call("edit_file", {"path": "t.py", "old": "if x:\n    return 1", "new": "if x:\n    return 7"}))
        b = self.box("e08")
        out = b.call("edit_file", {"path": "t.py", "old": "if x:\n    return 1", "new": "if x:\n    return 7"})
        self.assertTrue(out.startswith("edited t.py (matched with indentation")); self.assertEqual(self.ws.read("t.py"), T.replace("return 1", "return 7"))
        self.assertEqual(b.ext_stats["fuzzy_edits"], 1)
        self.ws.write("d.py", "  x = 1\ny = 0\n    x = 1\n")
        self.assertIn("old was not found", b.call("edit_file", {"path": "d.py", "old": "x = 1 ", "new": "x = 2"}))

    def test_e09_and_e07_notes_are_appended(self):
        b = self.box("e09,e07")
        out = b.call("write_file", {"path": "bad.py", "content": "def f(:\n    pass\n"})
        self.assertTrue(out.startswith("created bad.py")); self.assertIn("\nsyntax error in bad.py line 1", out)
        self.ws.write("a.py", A)
        first = b.call("edit_file", {"path": "a.py", "old": "zzz", "new": "y"})
        second = b.call("edit_file", {"path": "a.py", "old": "zzz", "new": "y"})
        self.assertIn(CARDS["edit_not_found"], first); self.assertNotIn(CARDS["edit_not_found"], second)
        self.assertEqual((b.ext_stats["syntax_notes"], b.ext_stats["cards"]), (1, 1))

    def test_e12_churn_guard_warns_after_three_broken_writes(self):
        b = self.box("e12,e09")
        outs = [b.call("write_file", {"path": "bad.py", "content": "def f(:" + chr(10) + "    pass" + chr(10) + "# " + str(i) + chr(10)}) for i in range(3)]
        self.assertNotIn("churn:", outs[1]); self.assertIn("churn: bad.py", outs[2])
        self.assertNotIn("churn:", self.box("e09").call("write_file", {"path": "bad.py", "content": "def f(:" + chr(10)}))

    def test_without_ext_nothing_changes(self):
        self.ws.write("a.py", A); b = DevToolBox(self.ws, "solo")
        self.assertTrue(b.call("edit_file", {"path": "a.py", "old": "a = 1", "new": "a = 5"}).startswith("edited a.py"))
        self.assertEqual(b.call("write_file", {"path": "bad.py", "content": "def f(:\n"}), "created bad.py (8 bytes)")


class AnswerHookTests(Base):
    def test_e03_runs_a_call_written_as_text_and_corrects_prose(self):
        self.ws.write("a.py", A)
        text_call = '```json\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```'
        r, bodies = self.run_with([answer(content=text_call), answer(content="I am done."), answer([tc("submit_result", {"summary": "ok"}, 2)])], cfg={"enabled": "e03"})
        self.assertEqual(r["stopped_by"], "hand_in"); self.assertIn("read_file", r["tool_counts"])
        self.assertIn("Do not answer in text", json.dumps(bodies[-1]["messages"]))
        r, _ = self.run_with([answer(content="I am done.")])
        self.assertEqual(r["stopped_by"], "no_tool_call")

    def test_e02_note_then_less_thinking_in_later_requests(self):
        replies = [answer([tc("list_dir", {}, 1)], reasoning=5000), answer([tc("list_dir", {"path": ""}, 2)], reasoning=5000), answer([tc("submit_result", {"summary": "ok"}, 3)])]
        r, bodies = self.run_with(replies, cfg={"enabled": "e02", "think_limit": 1000, "family": "qwen"})
        self.assertEqual(r["stopped_by"], "hand_in")
        self.assertNotIn("chat_template_kwargs", bodies[1]); self.assertIn("You thought for 5000 tokens", json.dumps(bodies[1]["messages"]))
        self.assertEqual(bodies[2]["chat_template_kwargs"], {"enable_thinking": False})
        self.assertTrue(r["coder_ext"]["think_less"])

    def test_e05_prunes_old_long_results_above_the_fill_mark(self):
        self.ws.write("long.py", LONG)
        replies = [answer([tc("read_file", {"path": "long.py"}, 1)], prompt=100)] + [answer([tc("list_dir", {"path": f"x{i}"}, i + 2)], prompt=900) for i in range(7)] + [answer([tc("submit_result", {"summary": "ok"}, 99)], prompt=900)]
        r, bodies = self.run_with(replies, cfg={"enabled": "e05", "window": 1000, "prune_at": 0.5})
        first_tool = next(m for m in bodies[-1]["messages"] if m["role"] == "tool")
        self.assertIn("lines cut", first_tool["content"])
        self.assertGreaterEqual(r["coder_ext"]["prunes"], 1)
        r, bodies = self.run_with(replies)
        self.assertNotIn("lines cut", json.dumps(bodies[-1]["messages"]))

    def test_e04_records_and_the_run_replays_without_a_server(self):
        self.ws.write("a.py", A)
        replies = [answer([tc("read_file", {"path": "a.py"}, 1)]), answer([tc("submit_result", {"summary": "ok"}, 2)])]
        r, bodies = self.run_with(replies, cfg={"enabled": "e04", "record": True})
        self.assertEqual(len(r["replay_records"]), 2)
        again = run_agent("solo", "task", self.ws, Player(r["replay_records"]), "m", budget=AgentBudget(max_turns=30))
        self.assertEqual((again["stopped_by"], again["tool_counts"]), (r["stopped_by"], r["tool_counts"]))

    def test_recording_works_without_any_extension_and_keeps_what_was_sent(self):
        self.ws.write("a.py", A)
        replies = [answer([tc("read_file", {"path": "a.py"}, 1)]), answer([tc("submit_result", {"summary": "ok"}, 2)])]
        r, _ = self.run_with(replies, cfg={"enabled": "", "record": True})
        self.assertEqual(r["coder_ext"]["enabled"], [])
        self.assertEqual(len(r["replay_records"]), 2)
        sent = r["replay_records"][1]["sent"]
        self.assertTrue(any(m.get("role") == "tool" and "a = 1" in m.get("content", "") for m in sent))      # the tool result the model saw
        r, _ = self.run_with(replies[:])
        self.assertNotIn("replay_records", r)

    def test_a_continued_conversation_keeps_what_was_read(self):
        self.ws.write("a.py", A)
        first, _ = self.run_with([answer([tc("read_file", {"path": "a.py"}, 1)]), answer([tc("submit_result", {"summary": "ok"}, 2)])], cfg={"enabled": "e01"})
        state = first["_coder_ext"]
        edit = [answer([tc("edit_file", {"path": "a.py", "old": "a = 1", "new": "a = 5"}, 3)]), answer([tc("submit_result", {"summary": "ok"}, 4)])]
        it, history = iter(edit), [{"role": "system", "content": "s"}, {"role": "user", "content": "task"}]
        r = run_agent("solo", "go on", self.ws, lambda body: next(it), "m", coder_ext={"enabled": "e01"}, coder_ext_state=state, history=history, budget=AgentBudget(max_turns=30))
        self.assertEqual(r["coder_ext"]["refusals"], 0); self.assertEqual(self.ws.read("a.py"), "a = 5\nb = 2\n")
        self.ws.write("a.py", A)
        it = iter(edit)
        r = run_agent("solo", "new conversation", self.ws, lambda body: next(it), "m", coder_ext={"enabled": "e01"}, coder_ext_state=state, budget=AgentBudget(max_turns=30))
        self.assertEqual(r["coder_ext"]["refusals"], 1)                                            # no history: a new conversation starts with a new tracker

    def test_the_result_reports_the_extensions(self):
        r, _ = self.run_with([answer([tc("submit_result", {"summary": "ok"}, 1)])], cfg={"enabled": "e01,e08"})
        self.assertEqual(r["coder_ext"]["enabled"], ["e01", "e08"])
        r, _ = self.run_with([answer([tc("submit_result", {"summary": "ok"}, 1)])])
        self.assertEqual(r["coder_ext"]["enabled"], [])


if __name__ == "__main__":
    unittest.main()
