"""Guards taken over from little-coder (2026-10-10): write_file does not replace an existing file, edit_file with several changes, one correction before a loop or a runaway ends the run."""
import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from guppi_runtime.devvm import DevWorkspace  # noqa: E402
from guppi_runtime.devvm_agents import AgentBudget, run_agent  # noqa: E402
from guppi_runtime.devvm_tools import DevToolBox, WRITE_KEEP_LINES  # noqa: E402

POLICY = {"max_files": 40, "max_file_bytes": 60000, "max_input_bytes": 200000}


def tc(name, args, i=1):
    return {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def answer(calls=(), content=""):
    return {"choices": [{"message": {"role": "assistant", "content": content, "tool_calls": list(calls)}, "finish_reason": "tool_calls" if calls else "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 10}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = DevWorkspace(Path(self.tmp.name), "M-LC0001", policy=dict(POLICY)); self.ws.create()
        self.box = DevToolBox(self.ws, "solo")

    def tearDown(self):
        self.tmp.cleanup()


class WriteGuardTests(Base):
    def test_a_new_file_and_a_short_old_file_may_be_written_a_long_old_file_may_not(self):
        self.assertIn("created", self.box.call("write_file", {"path": "a.py", "content": "x = 1\n"}))
        self.assertIn("overwrote", self.box.call("write_file", {"path": "a.py", "content": "x = 2\n"}))                    # small: cheaper to write again
        self.ws.write("big.py", "".join(f"x{i} = {i}\n" for i in range(WRITE_KEEP_LINES + 1)))
        out = self.box.call("write_file", {"path": "big.py", "content": "y = 1\n"})
        self.assertTrue(out.startswith("error: write_file refused"))
        self.assertIn("edit_file", out); self.assertIn("delete_file", out); self.assertIn("Do not retry", out)
        self.assertTrue(self.ws.read("big.py").startswith("x0 = 0"))                                                        # the file is untouched
        self.box.call("delete_file", {"path": "big.py"})
        self.assertIn("created", self.box.call("write_file", {"path": "big.py", "content": "y = 1\n"}))                    # the way to replace a whole file


class EditManyTests(Base):
    def setUp(self):
        super().setUp()
        self.ws.write("m.py", "A = 1\nB = 2\nC = 3\nD = 4\n")

    def test_several_changes_are_applied_together(self):
        out = self.box.call("edit_file", {"path": "m.py", "edits": [{"old": "A = 1", "new": "A = 10"}, {"old": "D = 4", "new": "D = 40"}, {"old": "B = 2", "new": "B = 20"}]})
        self.assertIn("3 changes", out)
        self.assertEqual(self.ws.read("m.py"), "A = 10\nB = 20\nC = 3\nD = 40\n")

    def test_nothing_is_written_when_one_change_does_not_fit_or_they_overlap(self):
        before = self.ws.read("m.py")
        out = self.box.call("edit_file", {"path": "m.py", "edits": [{"old": "A = 1", "new": "A = 10"}, {"old": "Z = 9", "new": "Z = 90"}]})
        self.assertIn("change 2 of 2", out); self.assertIn("Nothing was changed", out); self.assertEqual(self.ws.read("m.py"), before)
        out = self.box.call("edit_file", {"path": "m.py", "edits": [{"old": "A = 1\nB = 2", "new": "AB"}, {"old": "B = 2\nC = 3", "new": "BC"}]})
        self.assertIn("overlap", out); self.assertEqual(self.ws.read("m.py"), before)
        out = self.box.call("edit_file", {"path": "m.py", "edits": [{"old": "= ", "new": "x"}]})
        self.assertIn("occurs 4 times", out); self.assertEqual(self.ws.read("m.py"), before)

    def test_one_change_in_the_old_form_still_works(self):
        self.assertIn("edited m.py (", self.box.call("edit_file", {"path": "m.py", "old": "B = 2", "new": "B = 5"}))
        self.assertEqual(self.ws.read("m.py"), "A = 1\nB = 5\nC = 3\nD = 4\n")


class NudgeTests(Base):
    def run_with(self, replies, role="solo", budget=None):
        it = iter(replies)
        seen = []

        def post(body):
            seen.append(json.dumps(body["messages"]))
            return next(it)
        return run_agent(role, "task", self.ws, post, "m", budget=budget or AgentBudget(max_turns=30)), seen

    def test_a_loop_gets_one_correction_and_the_run_goes_on(self):
        self.ws.write("a.py", "x = 1\n")
        same = [answer([tc("read_file", {"path": "a.py"}, i)]) for i in range(20)]
        r, seen = self.run_with(same)
        self.assertEqual((r["stopped_by"], r["nudges"]), ("loop", 1))
        self.assertEqual(sum(1 for s in seen if "You are repeating the same calls" in s) > 0, True)
        self.assertEqual(len(set(s.count("You are repeating the same calls") for s in seen)) >= 2, True)                      # first without, then with the note

    def test_a_loop_that_ends_after_the_correction_hands_in_normally(self):
        self.ws.write("a.py", "x = 1\n")
        replies = [answer([tc("read_file", {"path": "a.py"}, i)]) for i in range(8)] + [answer([tc("submit_result", {"summary": "done"}, 99)])]
        r, _ = self.run_with(replies)
        self.assertEqual((r["stopped_by"], r["nudges"]), ("hand_in", 1))

    def test_a_runaway_answer_is_dropped_once_and_the_loop_asks_again(self):
        block = "blah blah blah " * 400
        replies = [answer([tc("list_dir", {}, 1)], content=block), answer([tc("submit_result", {"summary": "done"}, 2)])]
        r, seen = self.run_with(replies)
        self.assertEqual((r["stopped_by"], r["nudges"]), ("hand_in", 1))
        self.assertIn("too long", seen[-1])                                       # the cut note of the tool loop is in the conversation
        self.assertNotIn("blah blah", seen[-1])                                   # the runaway answer itself was not kept


if __name__ == "__main__":
    unittest.main()


class SelfCheckTests(Base):
    def first_request(self, self_check):
        seen = []

        def post(body):
            seen.append(body)
            return answer([tc("submit_result", {"summary": "done"}, 1)])
        run_agent("solo", "task", self.ws, post, "m", vm_runner=lambda c: {"status": "completed", "output": "ok"}, self_check=self_check)
        return seen[0]

    def test_the_way_of_checking_changes_the_system_text_and_the_tools(self):
        full, light, none = (self.first_request(k) for k in ("full", "light", "none"))
        names = lambda body: [t["function"]["name"] for t in body["tools"]]
        self.assertIn("run_python", names(full)); self.assertIn("run_python", names(light)); self.assertNotIn("run_python", names(none))
        self.assertIn("write ONE small script", full["messages"][0]["content"])
        self.assertIn("at most 2 runs", light["messages"][0]["content"]); self.assertNotIn("write ONE small script", light["messages"][0]["content"])
        self.assertIn("You cannot run code", none["messages"][0]["content"])

    def test_the_number_of_vm_runs_follows_the_way_of_checking(self):
        from guppi_runtime.devvm_tools import SELF_CHECK
        self.assertEqual({k: v["vm_runs"] for k, v in SELF_CHECK.items()}, {"full": 8, "light": 2, "none": 0})
        box = DevToolBox(self.ws, "solo", vm_runner=lambda c: {"status": "completed", "output": "ok"}, max_vm_runs=2, self_check="light")
        self.ws.write("check_a.py", "print(1)\n")
        self.assertIn("ok", box.call("run_python", {"path": "check_a.py"})); box.call("run_python", {"path": "check_a.py"})
        self.assertIn("at most 2 VM runs", box.call("run_python", {"path": "check_a.py"}))
        with self.assertRaises(ValueError): DevToolBox(self.ws, "solo", self_check="sometimes")

    def test_the_orchestrator_prompts_name_the_way_of_checking(self):
        from guppi_runtime.devvm_agents import SOLO_PROMPT, CONTINUE_PROMPT
        from guppi_runtime.devvm_tools import SELF_CHECK
        for key, words in (("full", "check_*.py script and run_python"), ("light", "ONE small check_*.py"), ("none", "re-read the task against your code")):
            self.assertIn(words, SOLO_PROMPT.format(task="t", lessons="", check=SELF_CHECK[key]["prompt"]))
        self.assertIn("read your code against the report again", CONTINUE_PROMPT.format(report="r", again=SELF_CHECK["none"]["again"]))
