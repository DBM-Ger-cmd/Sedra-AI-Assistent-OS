import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import argparse, sys, tempfile, time, unittest
from pathlib import Path

from guppi_runtime.devenv.devvm import DevWorkspace
from guppi_runtime.devenv.devvm_agents import make_jobs
from guppi_runtime.devenv.devvm_tools import DevToolBox

BENCH = str(Path(__file__).resolve().parents[1] / "benchmarks")
POLICY = {'max_files': 20, 'max_file_bytes': 4000, 'max_input_bytes': 20000}


class MakeJobsTests(unittest.TestCase):
    def test_off_without_the_flag_or_without_a_vm_runner(self):
        runner = lambda commands: {"status": "completed", "output": ""}
        self.assertIsNone(make_jobs(None, runner)); self.assertIsNone(make_jobs({"enabled": ""}, runner)); self.assertIsNone(make_jobs({"bg_jobs": False}, runner))
        self.assertIsNone(make_jobs({"bg_jobs": True}, None))
        self.assertIsNotNone(make_jobs({"bg_jobs": True}, runner))

    def test_a_job_is_one_vm_run_and_wakes_the_coder_when_it_ends(self):
        seen = []
        def runner(commands):
            seen.append(commands); return {"status": "completed", "output": "3 tests ok\n"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = DevWorkspace(Path(tmp), "M-JOBS0001", policy=dict(POLICY)); ws.create()
            box = DevToolBox(ws, "solo", vm_runner=runner, jobs=make_jobs({"bg_jobs": True}, runner))
            self.assertIn("shell_start", box.names)
            started = box.call("shell_start", {"command": "python3 -m unittest -v", "wake_match": "ok"})
            self.assertTrue(started.startswith("started J1"))
            for _ in range(100):
                if seen: break
                time.sleep(0.02)
            time.sleep(0.2)
            woke = started + box.call("list_dir", {})      # a job that ends at once wakes the coder in the result of the same call or of the next
            self.assertIn("(job J1 woke you: match: 3 tests ok)", woke)
            self.assertEqual(seen, [[["python3", "-m", "unittest", "-v"]]])
            self.assertEqual(box.call("shell_log", {"job": "J1"}), "3 tests ok")

    def test_the_tools_are_absent_without_jobs_and_a_busy_vm_is_an_error_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = DevWorkspace(Path(tmp), "M-JOBS0002", policy=dict(POLICY)); ws.create()
            self.assertNotIn("shell_start", DevToolBox(ws, "solo", vm_runner=lambda c: {}).names)
            import threading
            gate = threading.Event()
            box = DevToolBox(ws, "solo", vm_runner=lambda c: {}, jobs=make_jobs({"bg_jobs": True}, lambda commands: (gate.wait(5), {"status": "completed", "output": ""})[1]))
            for _ in range(2): self.assertTrue(box.call("shell_start", {"command": "sleep 1"}).startswith("started"))
            self.assertEqual(box.call("shell_start", {"command": "sleep 1"}), "error: shell_start refused: too_many_processes")
            gate.set()


class BuildFlagTests(unittest.TestCase):
    def test_the_flag_reaches_the_agent_config_even_without_coder_ext(self):
        sys.path.insert(0, BENCH)
        try:
            import devvm_build
        finally:
            sys.path.remove(BENCH)
        def args(**kw):
            base = dict(coder_ext="", no_record=True, bg_jobs=False, skills=None, think_limit=2000, think_family=None, all_models=None, coder="coder.local_primary", context="32768")
            return argparse.Namespace(**{**base, **kw})
        self.assertIsNone(devvm_build.coder_ext_config(args()))
        self.assertTrue(devvm_build.coder_ext_config(args(bg_jobs=True))["bg_jobs"])
        self.assertFalse(devvm_build.coder_ext_config(args(no_record=False))["bg_jobs"])



class LessonProposalTests(unittest.TestCase):
    def build_module(self):
        sys.path.insert(0, BENCH)
        try:
            import devvm_build
        finally:
            sys.path.remove(BENCH)
        return devvm_build

    def test_known_mistakes_of_an_attempt_become_open_cards_once(self):
        from guppi_runtime.devenv.lesson_store import default_path, manage
        build = self.build_module()
        said = []
        with tempfile.TemporaryDirectory() as tmp:
            rows = [{"stage": "tokens", "hidden_passed": False, "hidden_output": "ModuleNotFoundError: No module named 'numpy.linalg'"}, {"stage": "later", "skipped": True, "hidden_passed": False}]
            runs = [{"label": "solo developer", "journal": [{"ok": False, "error": "error: potential_credential_file (file names with words like token)"}, {"ok": True}]}]
            build.propose_lessons(tmp, "coin_hole", "20261013_1", rows, runs, said.append)
            cards = manage(default_path(tmp), "list")["cards"]
            self.assertEqual(sorted(c["state"] for c in cards), ["proposed", "proposed"])
            self.assertEqual({c["source"] for c in cards}, {"run:coin_hole-20261013_1:tokens", "run:coin_hole-20261013_1:solo developer"})
            self.assertTrue(any("2 new" in line for line in said))
            build.propose_lessons(tmp, "coin_hole", "20261013_2", rows, runs, said.append)          # the same mistakes again: nothing new
            self.assertEqual(len(manage(default_path(tmp), "list")["cards"]), 2)

    def test_a_damaged_card_file_never_breaks_a_build(self):
        build = self.build_module()
        said = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime_data"; path.mkdir()
            (path / "lesson_cards.json").write_text("{broken", encoding="utf-8")
            build.propose_lessons(tmp, "x", "s", [{"stage": "a", "hidden_passed": False, "hidden_output": "SyntaxError"}], [], said.append)
            self.assertTrue(said and said[0].startswith("   lesson proposals skipped:"))
            self.assertEqual((path / "lesson_cards.json").read_text(encoding="utf-8"), "{broken")



class SandboxCopyTests(unittest.TestCase):
    def test_the_vm_limit_is_raised_only_for_bg_jobs_and_only_in_the_copy(self):
        sys.path.insert(0, BENCH)
        try:
            import devvm_build
        finally:
            sys.path.remove(BENCH)
        shipped = (Path(BENCH).parent / "config" / "sandbox.yaml").read_text(encoding="utf-8")
        self.assertEqual(devvm_build.sandbox_text(False), shipped)
        raised = devvm_build.sandbox_text(True)
        self.assertIn("command_timeout_seconds: 100", raised); self.assertIn("job_timeout_seconds: 150", raised)
        self.assertNotIn("command_timeout_seconds: 30", raised)
        self.assertIn("command_timeout_seconds: 30", shipped)             # the shipped file is not touched


if __name__ == "__main__":
    unittest.main()
