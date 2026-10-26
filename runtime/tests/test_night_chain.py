"""Die Nachtkette von A1 (U2-11b): Fenster, Enddatum, Freigabe, Aufträge mit Stempel, ein Durchgang mit unechtem Bauwerkzeug, Stopp bei Canary, Trockenlauf schreibt und startet nichts."""
import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
import night_chain as nc  # noqa: E402

D = datetime.datetime


def args(**more):
    base = dict(bis=datetime.date(2026, 11, 30), start_hour=22, stop_hour=7, min_free_ram_gb=14.0, timeout_h=4.0)
    base.update(more)
    return SimpleNamespace(**base)


class Decide(unittest.TestCase):
    def test_window_over_midnight(self):
        for hour, expect in ((21, False), (22, True), (23, True), (0, True), (6, True), (7, False), (12, False)):
            self.assertEqual(nc.in_window(D(2026, 10, 27, hour, 30), 22, 7), expect, hour)

    def test_window_within_one_day(self):
        self.assertTrue(nc.in_window(D(2026, 10, 27, 3, 0), 1, 5))
        self.assertFalse(nc.in_window(D(2026, 10, 27, 5, 0), 1, 5))

    def test_decisions(self):
        bis = datetime.date(2026, 11, 30)
        self.assertEqual(nc.decide(D(2026, 12, 1, 23, 0), bis, True, 22, 7), ("ende", "befristung_abgelaufen"))
        self.assertEqual(nc.decide(D(2026, 11, 30, 23, 0), bis, True, 22, 7), ("arbeiten", ""), "am Enddatum selbst gilt noch")
        self.assertEqual(nc.decide(D(2026, 11, 3, 23, 0), bis, False, 22, 7), ("ende", "nicht_freigegeben"))
        self.assertEqual(nc.decide(D(2026, 11, 3, 14, 0), bis, True, 22, 7), ("warten", "ausserhalb_des_fensters"))


class Items(unittest.TestCase):
    def test_order_file_filters_bad_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "o.json"
            p.write_text(json.dumps([{"spec": "a"}, {"nospec": 1}, "x", {"spec": 5}, {"spec": "b", "rework": 2}]), encoding="utf-8")
            self.assertEqual([i["spec"] for i in nc.read_order(p)], ["a", "b"])
            self.assertEqual(nc.read_order(Path(tmp) / "fehlt.json"), [])
            p.write_text("kaputt", encoding="utf-8")
            self.assertEqual(nc.read_order(p), [])

    def test_status_missing_spec_no_stamp_ready_and_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(nc.item_status(tmp, {"spec": "gibt_es_nicht"}, set())[0], "spec_fehlt")
            self.assertEqual(nc.item_status(tmp, {"spec": "s1_graphs"}, set())[0], "ohne_stempel")
            self.assertEqual(nc.item_status(tmp, {"spec": "s1_graphs"}, {"s1_graphs"})[0], "erledigt")
            with mock.patch("spec_stamp.check", return_value=(None, {})):
                self.assertEqual(nc.item_status(tmp, {"spec": "s1_graphs"}, set()), ("bereit", ""))

    def test_build_argv_uses_the_one_way_with_profile_standard(self):
        argv = nc.build_argv(Path("P"), {"spec": "x", "rework": 2, "from_stage": "s2", "seed": "benchmarks/seed"}, "py")
        self.assertEqual(argv[:6], ["py", str(nc.BENCH / "devvm_build.py"), "P", "--spec", "x", "--profile"])
        self.assertEqual(argv[6], "standard")
        self.assertIn("--rework", argv)
        self.assertEqual(argv[argv.index("--from-stage") + 1], "s2")
        self.assertTrue(argv[argv.index("--seed") + 1].endswith("seed"))


class Pass(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nachtkette-")
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "GUPPI_OS"
        (self.project / "local_config").mkdir(parents=True)
        (self.project / "local_config" / nc.GATE).write_text("frei", encoding="utf-8")
        self.night = lambda: D(2026, 11, 3, 23, 30)
        self.calls = []
        self.patch = mock.patch("spec_stamp.check", return_value=(None, {}))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def runner(self, argv, env, log, timeout):
        self.calls.append((argv, env, log, timeout))
        Path(log).write_text("ok\n", encoding="utf-8")
        return 0, 3, ["ok"]

    def run_pass(self, order, **more):
        kw = dict(now=self.night, runner=self.runner, canary=lambda: False, ram=lambda: 20.0, sleep=lambda s: None, say=lambda s: None)
        kw.update(more)
        return nc.work_pass(self.project, order, args(), **kw)

    def test_builds_each_spec_once_and_records_it(self):
        order = [{"spec": "s1_graphs"}, {"spec": "s1_wakeplan"}]
        rows, stopped = self.run_pass(order)
        self.assertEqual(([r["spec"] for r in rows], stopped), (["s1_graphs", "s1_wakeplan"], None))
        argv, env, log, timeout = self.calls[0]
        self.assertEqual((env["TESTLAB_OWNER"], env["TESTLAB_PRIORITY"], timeout), ("nachtkette", "1", 4 * 3600))
        self.assertIn("--profile", argv)
        summary = json.loads((self.project / "runtime_data" / "measurements" / "night_2026-11-03" / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(summary["specs"]), ["s1_graphs", "s1_wakeplan"])
        rows2, _ = self.run_pass(order)
        self.assertEqual(rows2, [], "ein zweiter Durchgang baut nichts noch einmal")
        self.assertEqual(len(self.calls), 2)

    def test_removing_the_gate_file_stops_before_the_next_item(self):
        gate = self.project / "local_config" / nc.GATE
        def runner(argv, env, log, timeout):
            gate.unlink()
            return self.runner(argv, env, log, timeout)
        rows, _ = self.run_pass([{"spec": "s1_graphs"}, {"spec": "s1_wakeplan"}], runner=runner)
        self.assertEqual([r["spec"] for r in rows], ["s1_graphs"])

    def test_outside_the_window_nothing_is_built(self):
        rows, _ = self.run_pass([{"spec": "s1_graphs"}], now=lambda: D(2026, 11, 3, 14, 0))
        self.assertEqual((rows, self.calls), ([], []))

    def test_a_failed_canary_stops_the_chain(self):
        rows, stopped = self.run_pass([{"spec": "s1_graphs"}, {"spec": "s1_wakeplan"}], canary=lambda: True)
        self.assertEqual(([r["spec"] for r in rows], stopped), (["s1_graphs"], "gpu_canary_fehlgeschlagen"))

    def test_too_little_free_ram_builds_nothing(self):
        rows, _ = self.run_pass([{"spec": "s1_graphs"}], ram=lambda: 5.0)
        self.assertEqual((rows, self.calls), ([], []))

    def test_spec_without_stamp_is_skipped(self):
        self.patch.stop()
        self.addCleanup(self.patch.start)
        rows, _ = self.run_pass([{"spec": "s1_graphs"}])
        self.assertEqual((rows, self.calls), ([], []))


class DryRun(unittest.TestCase):
    def test_writes_nothing_and_starts_nothing(self):
        with tempfile.TemporaryDirectory(prefix="nachtkette-dry-") as tmp:
            project = Path(tmp) / "GUPPI_OS"
            (project / "local_config").mkdir(parents=True)
            (project / "local_config" / nc.ORDER).write_text(json.dumps([{"spec": "s1_graphs"}]), encoding="utf-8")
            before = sorted(p.relative_to(project).as_posix() for p in project.rglob("*"))
            with mock.patch("subprocess.run", side_effect=AssertionError("startet etwas")), mock.patch("subprocess.Popen", side_effect=AssertionError("startet etwas")):
                self.assertEqual(nc.main([str(project), "--bis", "2026-11-30", "--dry-run"]), 0)
            self.assertEqual(sorted(p.relative_to(project).as_posix() for p in project.rglob("*")), before)

    def test_end_date_in_the_past_ends_the_loop_at_once(self):
        with tempfile.TemporaryDirectory(prefix="nachtkette-end-") as tmp:
            self.assertEqual(nc.main([tmp, "--bis", "2020-01-01", "--once"]), 0)


if __name__ == "__main__":
    unittest.main()
