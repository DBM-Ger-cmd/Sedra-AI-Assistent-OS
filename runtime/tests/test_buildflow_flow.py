import importlib
import importlib.util
import io
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
FIXTURES = RUNTIME / "benchmarks" / "fixtures"

from guppi_runtime.devenv import buildflow_cli, buildflow_core as core
from guppi_runtime.devenv.buildflow_runner import build_command, run_queue, run_task
from guppi_runtime.devenv.buildflow_store import BuildflowStore

NOW = "2026-10-14T08:00:00"
PASSED = (FIXTURES / "build_log_passed.txt").read_text(encoding="utf-8")
FAILED = (FIXTURES / "build_log_failed.txt").read_text(encoding="utf-8")


class FakeProcess:
    def __init__(self, text, code=0, **kw):
        kw["stdout"].write(text)
        kw["stdout"].flush()
        self.code, self.polls, self.kw = code, 0, kw

    def poll(self):
        self.polls += 1
        return None if self.polls == 1 else self.code


def fake_popen(text, code=0, record=None):
    def make(argv, **kw):
        if record is not None:
            record.append((argv, kw))
        return FakeProcess(text, code, **kw)
    return make


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name, "project")
        self.store = BuildflowStore(self.project / "runtime_data" / "buildflow")

    def add(self, task_id, **kw):
        task = core.new_task(kw.pop("title", "T " + task_id), kw.pop("spec", "gate_bar"), now=kw.pop("now", NOW), task_id=task_id, **kw)
        return self.store.add(task)

    def to(self, task_id, *events):
        for event in events:
            self.store.update(task_id, lambda t, e=event: core.transition(t, e, NOW))


class StoreTests(Case):
    def test_tasks_are_saved_loaded_updated_and_listed_oldest_first(self):
        self.add("BF-AAAA0002", now="2026-10-14T09:00:00")
        self.add("BF-AAAA0001")
        self.assertEqual([t["id"] for t in self.store.all()], ["BF-AAAA0001", "BF-AAAA0002"])
        self.assertEqual(self.store.update("BF-AAAA0001", lambda t: core.transition(t, "check_ok", NOW))["state"], "checked")
        self.assertEqual(self.store.load("BF-AAAA0001")["state"], "checked")
        self.assertEqual(sorted(p.name for p in self.store.folder.iterdir()), ["BF-AAAA0001.json", "BF-AAAA0002.json"])

    def test_bad_ids_duplicates_and_missing_tasks_are_refused(self):
        self.add("BF-AAAA0001")
        for bad in ("../x", "bf-aaaa0001", "BF-", "BF-AAAA0001.json", None):
            with self.assertRaises(ValueError):
                self.store.file(bad)
        with self.assertRaises(ValueError):
            self.add("BF-AAAA0001")
        with self.assertRaises(KeyError):
            self.store.load("BF-ZZZZ0001")

    def test_a_stale_lock_of_a_crashed_process_does_not_block_the_store(self):
        lock = self.store.folder / ".lock"
        lock.write_text("x")
        old = time.time() - 600
        os.utime(lock, (old, old))
        self.add("BF-AAAA0001")
        self.assertFalse(lock.exists())

    def test_a_fresh_lock_makes_a_second_writer_wait_and_then_give_up(self):
        (self.store.folder / ".lock").write_text("x")
        with self.assertRaises(TimeoutError):
            with self.store.locked(timeout=0.2):
                pass


class RunnerTests(Case):
    def test_the_command_has_the_standard_settings_and_resolves_the_paths_of_a_task(self):
        task = core.new_task("T", "gate_bar", now=NOW, seed="g1_seed", review="reviews/x.md", from_stage="rest", rework=2, task_id="BF-AAAA0001")
        argv = build_command(task, python="py", runtime="rt", project="proj")
        self.assertEqual(argv[:4], ["py", str(Path("rt") / "benchmarks" / "devvm_build.py"), "proj", "--spec"])
        self.assertIn("--rework", argv)
        self.assertEqual(argv[argv.index("--rework") + 1], "2")
        self.assertEqual(argv[argv.index("--seed") + 1], str(Path("rt") / "benchmarks" / "g1_seed"))
        self.assertEqual(argv[argv.index("--from-stage") + 1], "rest")
        self.assertEqual([argv[i + 1] for i, a in enumerate(argv) if a == "--server-set"], ["flash_attn=on", "kv_cache_type=q8_0", "ubatch=512"])
        plain = build_command(core.new_task("T", "gate_bar", now=NOW), python="py", runtime="rt", project="p")
        self.assertNotIn("--seed", plain)
        self.assertNotIn("--from-stage", plain)

    def test_a_passed_build_ends_built_with_its_result_and_the_progress_goes_out(self):
        self.add("BF-AAAA0001", priority=3)
        self.to("BF-AAAA0001", "check_ok", "approve_spec", "queue")
        seen, record = [], []
        task = run_task(self.store, "BF-AAAA0001", project=self.project, runtime=RUNTIME, python="py", popen=fake_popen(PASSED, 0, record), now=lambda: NOW, sleep=lambda s: None, say=seen.append)
        self.assertEqual(task["state"], "built")
        self.assertEqual((task["result"]["passed"], task["result"]["stages"], task["result"]["seconds"], task["result"]["calls"], task["result"]["failed_stage"]), (4, 4, 420.5, 41, None))
        self.assertTrue(task["result"]["exported_to"].endswith("attempt_01_20261013_143008"))
        self.assertEqual([h["event"] for h in task["history"]][-2:], ["start", "finish_ok"])
        self.assertIn("BF-AAAA0001: Stufe names bestanden (41 s)", seen)
        self.assertEqual(seen[-1], "BF-AAAA0001: Bau beendet: done")
        env = record[0][1]["env"]
        self.assertEqual((env["TESTLAB_OWNER"], env["TESTLAB_PRIORITY"]), ("buildflow_BF-AAAA0001", "3"))
        self.assertTrue((self.store.folder / "BF-AAAA0001.log").read_text(encoding="utf-8").startswith("S0 connection check"))

    def test_a_failed_build_ends_failed_and_names_the_stage(self):
        self.add("BF-AAAA0001")
        self.to("BF-AAAA0001", "check_ok", "approve_spec", "queue")
        task = run_task(self.store, "BF-AAAA0001", project=self.project, runtime=RUNTIME, popen=fake_popen(FAILED, 0), now=lambda: NOW, sleep=lambda s: None, say=lambda t: None)
        self.assertEqual(task["state"], "failed")
        self.assertEqual((task["result"]["passed"], task["result"]["stages"], task["result"]["failed_stage"]), (2, 4, "rest"))
        self.assertEqual(task["history"][-1]["note"], "stage rest")

    def test_a_build_that_died_without_a_result_ends_failed_with_its_exit_code(self):
        self.add("BF-AAAA0001")
        self.to("BF-AAAA0001", "check_ok", "approve_spec", "queue")
        task = run_task(self.store, "BF-AAAA0001", project=self.project, runtime=RUNTIME, popen=fake_popen("Traceback", 1), now=lambda: NOW, sleep=lambda s: None, say=lambda t: None)
        self.assertEqual((task["state"], task["history"][-1]["note"], task["result"]["exit"]), ("failed", "exit 1", 1))

    def test_only_a_queued_task_may_start(self):
        self.add("BF-AAAA0001")
        with self.assertRaises(ValueError):
            run_task(self.store, "BF-AAAA0001", project=self.project, runtime=RUNTIME, popen=fake_popen(PASSED), say=lambda t: None)

    def test_the_queue_runs_by_priority_and_keeps_night_tasks_for_the_night(self):
        for task_id, priority, window in (("BF-AAAA0001", 1, "now"), ("BF-AAAA0002", 5, "now"), ("BF-AAAA0003", 9, "night")):
            self.add(task_id, priority=priority, window=window)
            self.to(task_id, "check_ok", "approve_spec", "queue")
        kw = dict(project=self.project, runtime=RUNTIME, popen=fake_popen(PASSED), now=lambda: NOW, sleep=lambda s: None, say=lambda t: None)
        self.assertEqual(run_queue(self.store, **kw), ["BF-AAAA0002", "BF-AAAA0001"])
        self.assertEqual(run_queue(self.store, night=True, once=True, **kw), ["BF-AAAA0003"])
        self.assertEqual(run_queue(self.store, **kw), [])


class CliTests(Case):
    def run_cli(self, *argv, **kw):
        lines = []
        code = buildflow_cli.main(list(argv), self.project, out=lines.append, **kw)
        return code, lines

    def test_add_list_cancel_and_requeue(self):
        code, lines = self.run_cli("add", "--title", "Leiste bauen", "--spec", "gate_bar", "--priority", "2", "--night")
        self.assertEqual(code, 0)
        task_id = lines[0].split()[0]
        self.assertRegex(lines[0], r"^BF-[0-9A-F]{8} \[draft\] V2 nacht · Leiste bauen$")
        self.assertEqual(self.run_cli("list")[1], lines)
        self.assertEqual(self.run_cli("cancel", task_id)[1][0].split()[1], "[cancelled]")
        self.assertEqual(self.run_cli("list")[1], [])
        self.assertEqual(len(self.run_cli("list", "--all")[1]), 1)
        code, lines = self.run_cli("queue", task_id)
        self.assertEqual((code, lines), (2, ["refused: illegal_transition: cancelled queue"]))
        self.assertEqual(self.run_cli("show", "BF-NOPE0000")[0], 2)
        self.assertEqual(self.run_cli("add", "--title", " ", "--spec", "x")[1], ["refused: bad title"])

    def test_check_approve_and_queue_follow_the_states_and_a_missing_spec_fails_the_check(self):
        task_id = self.run_cli("add", "--title", "Leiste", "--spec", "gate_bar")[1][0].split()[0]
        self.assertEqual(self.run_cli("queue", task_id)[0], 2)
        code, lines = self.run_cli("check", task_id)
        self.assertEqual((code, lines[0].split()[1]), (0, "[checked]"))
        self.assertEqual(self.run_cli("approve-spec", task_id)[1][0].split()[1], "[spec_approved]")
        self.assertEqual(self.run_cli("queue", task_id)[1][0].split()[1], "[queued]")
        self.assertEqual(self.store.load(task_id)["history"][-2]["note"], "Captain")
        other = self.run_cli("add", "--title", "Nichts", "--spec", "no_such_spec")[1][0].split()[0]
        code, lines = self.run_cli("check", other)
        self.assertEqual((code, lines[0].split()[1], lines[1].strip()), (1, "[draft]", "no spec file"))

    def test_run_hands_the_queue_to_the_runner_and_says_what_was_built(self):
        calls = []
        runner = lambda store, **kw: calls.append(kw["night"]) or ["BF-AAAA0001"]
        self.assertEqual(self.run_cli("run", "--night", runner=runner), (0, ["built: BF-AAAA0001"]))
        self.assertEqual(calls, [True])
        self.assertEqual(self.run_cli("run", runner=lambda store, **kw: [])[1], ["built: nothing queued"])


class ReportAdoptTests(Case):
    def setUp(self):
        super().setUp()
        self.runtime = Path(self.tmp.name, "runtime")
        self.repo = Path(self.tmp.name, "repo")
        (self.repo / "runtime" / "src" / "guppi_runtime" / "devenv").mkdir(parents=True)
        (self.repo / "runtime" / "tests").mkdir(parents=True)
        (self.repo / "runtime" / "src" / "guppi_runtime" / "old.py").write_text('"""Moved to guppi_runtime.devenv.old."""\n', encoding="utf-8")
        self.candidate = Path(self.tmp.name, "candidate")
        self.candidate.mkdir()
        (self.candidate / "newmod.py").write_text('import os\n\n\ndef f(x):\n    return x  # note\n', encoding="utf-8")
        (self.candidate / "NOTES.md").write_text("notes", encoding="utf-8")
        self.add("BF-AAAA0001", spec="gate_bar")
        self.to("BF-AAAA0001", "check_ok", "approve_spec", "queue", "start")
        self.store.update("BF-AAAA0001", lambda t: core.transition(t, "finish_ok", NOW, result={"exported_to": str(self.candidate), "calls": 9, "seconds": 12.0}))
        (self.store.folder / "BF-AAAA0001.log").write_text(PASSED, encoding="utf-8")

    def cli(self, *argv):
        lines = []
        code = buildflow_cli.main(list(argv), self.project, runtime=self.runtime, repo=self.repo, out=lines.append)
        return code, lines

    def test_the_report_lists_files_and_findings_and_moves_the_task_on(self):
        code, lines = self.cli("report", "BF-AAAA0001")
        text = "\n".join(lines)
        self.assertEqual(code, 0)
        self.assertIn("Abnahme-Bericht: gate_bar", text)
        self.assertIn("Dateien: newmod.py (5 Zeilen)", text)
        self.assertIn("newmod.py:1 Import nicht benutzt: os", text)
        self.assertIn("newmod.py:5 Kommentar", text)
        self.assertIn("Empfehlung: Übernahme nach Korrektur der Befunde (2)", text)
        task = self.store.load("BF-AAAA0001")
        self.assertEqual(task["state"], "reported")
        self.assertIn("Abnahme-Bericht", task["result"]["report"])

    def test_adopt_shows_the_plan_first_and_copies_only_after_the_approval(self):
        self.cli("report", "BF-AAAA0001")
        code, lines = self.cli("adopt", "BF-AAAA0001")
        self.assertEqual(code, 0)
        self.assertIn("neu: runtime/src/guppi_runtime/devenv/newmod.py", "\n".join(lines))
        self.assertIn("Test fehlt: runtime/tests/test_newmod.py", "\n".join(lines))
        target = self.repo / "runtime" / "src" / "guppi_runtime" / "devenv" / "newmod.py"
        self.assertFalse(target.exists())
        self.assertEqual(self.cli("adopt", "BF-AAAA0001", "--yes")[0], 2)
        self.assertFalse(target.exists())
        self.cli("approve-adopt", "BF-AAAA0001")
        code, lines = self.cli("adopt", "BF-AAAA0001", "--yes")
        self.assertEqual(code, 0)
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), (self.candidate / "newmod.py").read_text(encoding="utf-8"))
        self.assertEqual(self.store.load("BF-AAAA0001")["state"], "adopted")

    def test_adopt_without_the_approval_is_refused(self):
        self.cli("report", "BF-AAAA0001")
        code, lines = self.cli("adopt", "BF-AAAA0001", "--yes")
        self.assertEqual(code, 2)
        self.assertEqual(lines[-1], "refused: the adoption is not approved: run approve-adopt first")

    def test_a_shim_is_refused_in_the_plan(self):
        (self.candidate / "old.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "runtime" / "src" / "guppi_runtime" / "devenv" / "old.py").write_text("x = 0\n", encoding="utf-8")
        self.cli("report", "BF-AAAA0001")
        code, lines = self.cli("adopt", "BF-AAAA0001")
        self.assertEqual(code, 0)
        self.assertNotIn("abgelehnt", "\n".join(lines))
        top = self.repo / "runtime" / "src" / "guppi_runtime" / "devenv" / "old.py"
        top.write_text('"""Moved to guppi_runtime.somewhere."""\n', encoding="utf-8")
        code, lines = self.cli("adopt", "BF-AAAA0001", "--target-dir", "runtime/src/guppi_runtime")
        self.assertEqual(code, 1)
        self.assertIn("abgelehnt: runtime/src/guppi_runtime/old.py (shim: edit the file in the subpackage)", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
