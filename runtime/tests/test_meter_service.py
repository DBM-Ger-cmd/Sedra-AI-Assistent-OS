import os
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from guppi_runtime.agent_manager.meter_service import GUPPI_BUILT, built_paths, candidate_entries, git_log, meter_view, working_tree_log

LOG = ("@2026-10-08\n10\t0\truntime/src/x.py\n99\t0\tdocs/LOG.md\n50\t0\t" + GUPPI_BUILT[0] + "\n@2026-10-02\n5\t0\truntime/src/y.py\n")


def fake_run(text, code=0, diff="", untracked=""):
    def run(command, **kwargs):
        answer = diff if "diff" in command else untracked if "ls-files" in command else text
        return SimpleNamespace(stdout=answer, returncode=code)
    return run


def write(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x = 1\n" * lines)


class MeterServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = self.tmp.name
        base = os.path.join(self.project, "runtime_data", "devvm_candidates")
        write(os.path.join(base, "am1", "attempt_01_20261008_100000", "mod.py"), 30)
        write(os.path.join(base, "am1", "attempt_01_20261008_100000", "tests", "test_mod.py"), 100)
        write(os.path.join(base, "am1", "attempt_01_20261008_100000", "acceptance_step1.py"), 100)
        write(os.path.join(base, "am1", "attempt_02_20261009_100000", "mod.py"), 40)

    def test_candidate_lines_count_code_files_only(self):
        got = {entry["attempt"]: entry["lines"] for entry in candidate_entries(self.project)}
        self.assertEqual(got, {"attempt_01_20261008_100000": 30, "attempt_02_20261009_100000": 40})
        self.assertEqual(candidate_entries(os.path.join(self.project, "nothing")), [])

    def test_the_view_splits_claude_from_git_and_guppi_from_the_newest_candidate(self):
        view = meter_view(self.tmp.name, self.project, today="2026-10-09", run=fake_run(LOG))
        total = view["ranges"]["all"]
        self.assertEqual((total["claude_lines"], total["guppi_lines"], total["total_lines"]), (15, 40, 55))
        self.assertEqual(view["ranges"]["7"]["claude_lines"], 10)
        self.assertEqual(view["ranges"]["30"]["total_lines"], 55)
        self.assertEqual((view["sources"], len(view["grid"]), len(view["grid"][0])), ({"git": True, "candidates": 2}, 7, 26))
        self.assertIn("Näherung", view["note"])

    def test_the_range_today_counts_the_work_that_is_not_committed_yet(self):
        write(os.path.join(self.tmp.name, "new_module.py"), 7)
        pending = "12" + chr(9) + "3" + chr(9) + "runtime/src/changed.py" + chr(10)
        view = meter_view(self.tmp.name, self.project, today="2026-10-09", run=fake_run(LOG, diff=pending, untracked="new_module.py" + chr(10) + "missing.py" + chr(10)))
        self.assertEqual(view["ranges"]["today"]["claude_lines"], 19)
        self.assertEqual(view["ranges"]["today"]["guppi_lines"], 40)
        self.assertEqual(view["ranges"]["all"]["claude_lines"], 15 + 19)
        self.assertEqual(view["ranges"]["7"]["claude_lines"], 10 + 19)
        text = working_tree_log(self.tmp.name, "2026-10-09", fake_run("", diff=pending))
        self.assertTrue(text.startswith("@2026-10-09" + chr(10) + "12"))

    def test_without_git_the_view_still_shows_the_candidates(self):
        for run in (fake_run("", 128), lambda *a, **k: (_ for _ in ()).throw(OSError("no git"))):
            view = meter_view(self.tmp.name, self.project, today="2026-10-09", run=run)
            self.assertEqual((view["sources"]["git"], view["ranges"]["all"]["guppi_lines"], view["ranges"]["all"]["claude_lines"]), (False, 40, 0))

    def test_git_log_reports_a_failure_as_none(self):
        self.assertIsNone(git_log(self.tmp.name, fake_run("x", 1)))
        self.assertIsNone(git_log(self.tmp.name, lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("git", 1))))
        self.assertEqual(git_log(self.tmp.name, fake_run("@2026-10-08\n")), "@2026-10-08\n")


class BuiltPaths(unittest.TestCase):
    def test_files_with_a_candidate_name_count_for_guppi(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for rel in ("proj/runtime_data/devvm_candidates/s/a1/mod_x.py", "proj/runtime_data/devvm_candidates/s/a1/__init__.py", "repo/runtime/src/pkg/mod_x.py", "repo/runtime/src/pkg/other.py", "repo/runtime/src/pkg/__init__.py"):
                path = os.path.join(tmp, *rel.split("/")); os.makedirs(os.path.dirname(path), exist_ok=True); open(path, "w").write("x = 1" + chr(10))
            self.assertEqual(built_paths(os.path.join(tmp, "repo"), os.path.join(tmp, "proj")), ("runtime/src/pkg/mod_x.py",))


if __name__ == "__main__":
    unittest.main()
