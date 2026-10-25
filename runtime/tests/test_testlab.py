import tempfile
import threading
import unittest
from pathlib import Path

from guppi_runtime.jobs.testlab import LeaseBusy, TestLab, pid_alive
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class LabCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "lab" / "testlab.db"
        self.clock = Clock()
        self.alive_pids = {111, 222}
        self.a = TestLab(self.path, clock=self.clock, alive=lambda p: p in self.alive_pids, pid=111)
        self.b = TestLab(self.path, clock=self.clock, alive=lambda p: p in self.alive_pids, pid=222)


class LeaseTests(LabCase):
    def test_free_gpu_is_taken_and_a_second_taker_is_refused(self):
        token = self.a.try_acquire("chat-1", "quality round")
        self.assertTrue(token)
        self.assertIsNone(self.b.try_acquire("chat-2", "measure"))
        holder = self.b.holder()
        self.assertEqual((holder["owner"], holder["purpose"], holder["stale"]), ("chat-1", "quality round", False))

    def test_release_frees_it_and_only_the_holder_can_release(self):
        token = self.a.try_acquire("chat-1", "x")
        self.assertFalse(self.b.release(token + "0"))
        self.assertTrue(self.a.release(token))
        self.assertIsNone(self.a.holder())
        self.assertTrue(self.b.try_acquire("chat-2", "y"))

    def test_silent_holder_goes_stale_after_ttl(self):
        self.a.try_acquire("chat-1", "x", ttl_s=60)
        self.clock.t += 59
        self.assertIsNone(self.b.try_acquire("chat-2", "y"))
        self.clock.t += 2
        self.assertTrue(self.b.holder()["stale"])
        self.assertTrue(self.b.try_acquire("chat-2", "y"))
        self.assertIn("stale_takeover", [e["kind"] for e in self.b.events()])

    def test_dead_process_is_stale_at_once(self):
        self.a.try_acquire("chat-1", "x", ttl_s=3600)
        self.alive_pids.discard(111)
        self.assertTrue(self.b.holder()["stale"])
        self.assertTrue(self.b.try_acquire("chat-2", "y"))

    def test_heartbeat_keeps_the_lease_and_reports_a_takeover(self):
        token = self.a.try_acquire("chat-1", "x", ttl_s=60)
        self.clock.t += 50
        self.assertTrue(self.a.heartbeat(token))
        self.clock.t += 50
        self.assertIsNone(self.b.try_acquire("chat-2", "y"))          # not stale: the heartbeat moved
        self.alive_pids.discard(111)
        self.b.try_acquire("chat-2", "y")
        self.assertFalse(self.a.heartbeat(token))                     # taken over: the old holder learns it

    def test_acquire_waits_then_gives_up_with_the_holder(self):
        self.a.try_acquire("chat-1", "long job")
        naps = []
        def nap(s):
            naps.append(s)
            self.clock.t += s
        with self.assertRaises(LeaseBusy) as cm:
            self.b.acquire("chat-2", "y", wait_s=12, poll_s=5, sleep=nap)
        self.assertEqual(cm.exception.holder["owner"], "chat-1")
        self.assertEqual(naps, [5, 5, 5])

    def test_acquire_gets_the_lease_when_it_is_freed_while_waiting(self):
        token = self.a.try_acquire("chat-1", "x")
        def nap(s):
            self.clock.t += s
            self.a.release(token)
        self.assertTrue(self.b.acquire("chat-2", "y", wait_s=30, poll_s=1, sleep=nap))

    def test_context_manager_releases_also_on_error(self):
        with self.assertRaises(RuntimeError):
            with self.a.lease("chat-1", "x"):
                self.assertIsNotNone(self.a.holder())
                raise RuntimeError("boom")
        self.assertIsNone(self.a.holder())

    def test_two_threads_never_both_win(self):
        wins, barrier = [], threading.Barrier(8)
        labs = [TestLab(self.path, clock=self.clock, alive=lambda p: True, pid=1000 + i) for i in range(8)]
        def go(lab, i):
            barrier.wait()
            if lab.try_acquire(f"t{i}", "race"):
                wins.append(i)
        threads = [threading.Thread(target=go, args=(lab, i)) for i, lab in enumerate(labs)]
        [t.start() for t in threads]; [t.join() for t in threads]
        self.assertEqual(len(wins), 1)


class QueueAndResultTests(LabCase):
    def test_planned_rounds_are_visible_to_other_chats_and_move_with_the_run(self):
        qid = self.a.plan("chat-1", "quality", "24 tasks x 4 variants", models=["gemma", "qwen3-14b"])
        planned = self.b.queue()
        self.assertEqual((planned[0]["description"], planned[0]["models"], planned[0]["status"]), ("24 tasks x 4 variants", "gemma,qwen3-14b", "planned"))
        run = self.b.start_run("chat-2", "quality", "gemma first", {"variants": 4}, queue_id=qid)
        self.assertEqual(self.a.queue()[0]["status"], "running")
        self.b.finish_run(run)
        self.assertEqual(self.a.queue(), [])                          # done rounds drop out of the default view
        self.assertEqual(self.a.queue(("done",))[0]["id"], qid)

    def test_a_failed_run_puts_its_round_back_on_the_plan(self):
        qid = self.a.plan("chat-1", "quality", "x")
        run = self.a.start_run("chat-1", "quality", "x", queue_id=qid)
        self.a.finish_run(run, "failed")
        self.assertEqual(self.a.queue()[0]["status"], "planned")

    def test_results_summary_per_model_and_variant(self):
        run = self.a.start_run("chat-1", "quality", "r")
        for ok, out in ((True, 100), (False, 300), (True, 200)):
            self.a.record(run, "gemma", variant="off", task="t", ok=ok, tokens_out=out, seconds=2.0, thinking_chars=5)
        self.a.record(run, "qwen", variant="off", task="t", ok=True, tokens_out=50, seconds=1.0)
        rows = {(r["model"], r["variant"]): r for r in self.a.summary(run)}
        self.assertEqual(rows[("gemma", "off")]["n"], 3)
        self.assertAlmostEqual(rows[("gemma", "off")]["ok_rate"], 2 / 3)
        self.assertEqual(rows[("gemma", "off")]["tokens_out"], 200)
        self.assertEqual(rows[("qwen", "off")]["ok_rate"], 1)

    def test_invalid_status_is_refused(self):
        with self.assertRaises(ValueError):
            self.a.set_queue_status(1, "bogus")
        run = self.a.start_run("c", "k", "l")
        with self.assertRaises(ValueError):
            self.a.finish_run(run, "bogus")

    def test_long_text_is_cut_not_rejected(self):
        self.a.plan("c", "k", "x" * 5000)
        self.assertEqual(len(self.a.queue()[0]["description"]), 500)


class PidTests(unittest.TestCase):
    def test_own_process_is_alive_and_a_huge_pid_is_not(self):
        import os
        self.assertTrue(pid_alive(os.getpid()))
        self.assertFalse(pid_alive(4_000_000_000 % 2_000_000_000 + 1999999999))
        self.assertFalse(pid_alive(0))



class ActivityTests(LabCase):
    def test_a_round_is_alive_while_its_run_process_lives_and_orphaned_when_it_died(self):
        qid = self.a.plan("chat-1", "quality", "x")
        run = self.a.start_run("chat-1", "quality", "x", queue_id=qid)                 # pid 111
        seen = self.b.activity()
        self.assertEqual((seen["queue"][0]["active"], seen["runs"][0]["active"]), (True, True))
        self.alive_pids.discard(111)                                                    # the script died without finishing
        seen = self.b.activity()
        self.assertEqual((seen["queue"][0]["active"], seen["runs"][0]["active"], seen["runs"][0]["why"]), (False, False, "no live process and no lease"))

    def test_the_lease_vouches_for_a_round_without_a_live_run(self):
        qid = self.a.plan("chat-1", "quality", "x"); self.a.set_queue_status(qid, "running")        # set by hand: no run behind it
        self.assertFalse(self.b.activity()["queue"][0]["active"])
        token = self.a.acquire("chat-1", "bench", ttl_s=600)
        self.assertEqual(self.b.activity()["queue"][0]["why"], "its owner holds the GPU lease")
        self.a.release(token)
        self.assertFalse(self.b.activity()["queue"][0]["active"])

    def test_reap_only_touches_old_orphans_and_puts_the_round_back_on_the_plan(self):
        qid = self.a.plan("chat-1", "quality", "x"); run = self.a.start_run("chat-1", "quality", "x", queue_id=qid)
        self.alive_pids.discard(111)
        self.assertEqual(self.b.reap_stale(min_age_s=1800), {"queue": [], "runs": []})          # touched a moment ago: left alone
        self.clock.t += 3600
        self.assertEqual(self.b.reap_stale(min_age_s=1800), {"queue": [qid], "runs": [run]})
        row = self.b.queue()[0]
        self.assertEqual((row["status"], row["note"].startswith("orphaned")), ("planned", True))
        self.assertEqual(self.b.runs(1)[0]["status"], "aborted")
        self.assertEqual(self.b.activity(), {"queue": [], "runs": []})
        self.assertIn("reaped_round", [e["kind"] for e in self.b.events()])

    def test_a_live_round_is_never_reaped(self):
        qid = self.a.plan("chat-1", "quality", "x"); self.a.start_run("chat-1", "quality", "x", queue_id=qid)
        self.clock.t += 99999
        self.assertEqual(self.b.reap_stale(), {"queue": [], "runs": []}); self.assertEqual(self.b.queue()[0]["status"], "running")

    def test_old_databases_get_the_pid_column(self):
        import sqlite3
        old = Path(self.tmp.name) / "old" / "testlab.db"; old.parent.mkdir()
        db = sqlite3.connect(old); db.executescript("CREATE TABLE runs (id INTEGER PRIMARY KEY AUTOINCREMENT, started REAL NOT NULL, finished REAL, owner TEXT NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, config TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'running', queue_id INTEGER);"); db.close()
        lab = TestLab(old, clock=self.clock, alive=lambda p: True, pid=5)
        self.assertGreater(lab.start_run("o", "k", "l"), 0)


class ReservationTests(LabCase):
    def test_a_live_reservation_defers_lower_priority_takers_even_when_the_gpu_is_free(self):
        with self.a.reserve("night-g", "G builds", priority=1):
            self.assertIsNone(self.b.try_acquire("other-chain", "cchat"))
            self.assertEqual([e["kind"] for e in self.b.events(3)][0], "deferred")
            token = self.a.try_acquire("night-g", "G1 build", priority=1)
            self.assertTrue(token)
            self.a.release(token)
            self.assertIsNone(self.b.try_acquire("other-chain", "cchat"))
            self.assertEqual([r["owner"] for r in self.b.reservations()], ["night-g"])
        token = self.b.try_acquire("other-chain", "cchat")
        self.assertTrue(token)

    def test_without_a_reservation_nothing_changes_and_the_priority_alone_gives_no_right(self):
        token = self.a.try_acquire("chain-1", "x", priority=5)
        self.assertTrue(token)
        self.assertIsNone(self.b.try_acquire("chain-2", "y"))
        self.a.release(token)
        self.assertTrue(self.b.try_acquire("chain-2", "y"))
        self.assertEqual(self.b.reservations(), [])

    def test_a_reservation_of_a_dead_process_or_with_a_silent_heartbeat_is_ignored(self):
        with self.a.reserve("night-g", "G builds", priority=1, ttl_s=60):
            self.alive_pids.discard(111)
            self.assertEqual(self.b.reservations(), [])
            token = self.b.try_acquire("other-chain", "cchat")
            self.assertTrue(token)
            self.b.release(token)
            self.alive_pids.add(111)
            self.assertEqual(len(self.b.reservations()), 1)
            self.clock.t += 61
            self.assertEqual(self.b.reservations(), [])
            self.assertTrue(self.b.try_acquire("other-chain", "cchat"))

    def test_the_lease_context_passes_the_priority_and_a_higher_reservation_wins_over_a_lower_one(self):
        with self.a.reserve("chain-low", "low", priority=1):
            with self.b.reserve("chain-high", "high", priority=2):
                self.assertIsNone(self.a.try_acquire("chain-low", "x", priority=1))
                self.assertTrue(self.b.try_acquire("chain-high", "y", priority=2))


class SchemaTwoTests(LabCase):
    """S2.H1 (D2.3, D2.7): the slot tables in testlab.db, the backup before the migration and the waiting taker in `handover_requests`."""

    def _tables(self, lab):
        with lab._db() as db:
            return {r["name"] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}, db.execute("PRAGMA user_version").fetchone()[0]

    def test_a_new_file_has_schema_2_with_the_four_slot_tables_and_no_backup(self):
        tables, version = self._tables(self.a)
        self.assertEqual(version, 2)
        self.assertTrue({"slot_server", "slot_leases", "handover_requests", "slot_events", "lease", "reservations"} <= tables)
        self.assertEqual((self.a.schema, self.a.schema_error, self.a.backup), (2, None, None))
        self.assertEqual(list(self.path.parent.glob("*.bak-*")), [])

    def test_the_slot_tables_are_the_seed_word_for_word(self):
        import ast
        seed = Path(__file__).resolve().parents[1] / "benchmarks" / "s2_schema_seed" / "slot_db.py"
        tree = ast.parse(seed.read_text(encoding="utf-8"))
        text = next(n.value.value for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "SCHEMA")
        from guppi_runtime.jobs import slot_db, testlab
        self.assertEqual(testlab.SLOT_SCHEMA, text)
        self.assertIs(slot_db.SCHEMA, testlab.SLOT_SCHEMA)

    def _schema_one_file(self):
        import sqlite3
        from guppi_runtime.jobs.testlab import SCHEMA
        path = Path(self.tmp.name) / "old" / "testlab.db"
        path.parent.mkdir()
        db = sqlite3.connect(path)
        db.executescript(SCHEMA)
        db.execute("INSERT INTO events (ts, kind, owner, detail) VALUES (1, 'acquired', 'old', 'x')")
        db.commit()
        db.close()
        return path

    def test_a_file_with_data_is_backed_up_before_the_migration_and_keeps_its_rows(self):
        import sqlite3
        path = self._schema_one_file()
        self.clock.t = 1792800000.0                      # 2026-10-24 UTC
        lab = TestLab(path, clock=self.clock, alive=lambda p: True, pid=111)
        self.assertEqual((lab.schema, lab.schema_error), (2, None))
        self.assertEqual(lab.backup.name, "testlab.db.bak-20261024-schema2")
        old = sqlite3.connect(lab.backup)
        self.assertEqual(old.execute("PRAGMA user_version").fetchone()[0], 0)
        self.assertEqual(old.execute("SELECT owner FROM events").fetchall(), [("old",)])
        old.close()
        self.assertEqual(lab.events()[-1]["owner"], "old")
        again = TestLab(path, clock=self.clock, alive=lambda p: True, pid=111)
        self.assertIsNone(again.backup)                  # migrated once, backed up once
        self.assertEqual(len(list(path.parent.glob("*.bak-*"))), 1)

    def test_a_failed_backup_leaves_schema_1_and_the_lease_works_as_before(self):
        from unittest import mock
        path = self._schema_one_file()
        with mock.patch("guppi_runtime.jobs.testlab_slots.backup_path", return_value=path.parent):     # a directory: sqlite cannot open it
            lab = TestLab(path, clock=self.clock, alive=lambda p: True, pid=111)
        self.assertEqual(lab.schema, 1)
        self.assertTrue(lab.schema_error.startswith("testlab_schema2_failed:"))
        self.assertNotIn("slot_leases", self._tables(lab)[0])
        self.assertTrue(lab.try_acquire("chat-1", "x"))
        self.assertFalse(lab.register_waiter("bench", "y"))
        from guppi_runtime.jobs import slot_db
        with mock.patch("guppi_runtime.jobs.testlab_slots.backup_path", return_value=path.parent):
            with self.assertRaises(ValueError):
                slot_db.open_db(path)

    def _waiters(self):
        with self.a._db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM handover_requests")]

    def test_a_waiting_taker_stands_in_handover_requests_until_it_gets_the_lease(self):
        token = self.a.try_acquire("sedra-scheduler", "model server")
        seen = []

        def nap(seconds):
            seen.append([(w["owner"], w["purpose"], w["priority"], w["pid"]) for w in self._waiters()])
            self.clock.t += seconds
            if len(seen) == 2:
                self.a.release(token)
        self.assertTrue(self.b.acquire("bench-ladder", "context ladder", wait_s=60, poll_s=5, sleep=nap, priority=1))
        self.assertEqual(seen, [[("bench-ladder", "context ladder", 1, 222)]] * 2)
        self.assertEqual(self._waiters(), [])
        with self.a._db() as db:
            kinds = [r["kind"] for r in db.execute("SELECT kind FROM slot_events")]
        self.assertEqual(kinds, ["handover"])            # one event for the request, not one per poll

    def test_a_given_up_wait_removes_the_entry_and_an_immediate_refusal_never_writes_one(self):
        self.assertTrue(self.a.try_acquire("sedra-scheduler", "model server"))
        with self.assertRaises(LeaseBusy):
            self.b.acquire("bench", "x", wait_s=0)
        with self.a._db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM slot_events").fetchone()[0], 0)

        def nap(seconds):
            self.assertEqual(len(self._waiters()), 1)
            self.clock.t += seconds
        with self.assertRaises(LeaseBusy):
            self.b.acquire("bench", "x", wait_s=10, poll_s=5, sleep=nap)
        self.assertEqual(self._waiters(), [])

    def test_the_heartbeat_of_the_entry_is_utc_text_and_refreshed_per_poll(self):
        self.clock.t = 1792800000.0
        self.assertTrue(self.a.register_waiter("bench", "x", ttl_s=60))
        self.clock.t += 7
        self.assertFalse(self.a.register_waiter("bench", "x", ttl_s=60))
        row = self._waiters()[0]
        self.assertEqual((row["since"], row["heartbeat"], row["ttl_s"]), ("2026-10-24T00:00:00Z", "2026-10-24T00:00:07Z", 60))
        self.assertTrue(self.a.clear_waiter("bench"))
        self.assertFalse(self.a.clear_waiter("bench"))

    def test_the_slot_store_works_on_the_test_lab_file(self):
        from guppi_runtime.jobs import slot_db, slot_store
        conn = slot_db.open_db(self.path)
        self.addCleanup(conn.close)
        cfg = {"age_after_s": 120, "age_cap": 5, "swap": "none", "queue_max": 6, "wait_max_s": 600}
        now = "2026-10-24T00:00:00Z"
        slot_store.request(conn, "SDJ-1", "job", "worker-1", 5, now)
        self.assertTrue(slot_store.take(conn, "SDJ-1", now, cfg)["granted"])      # server `aus`: the first one is the starter
        self.assertEqual(slot_store.view(conn, now, cfg)["belegt"][0]["run_id"], "SDJ-1")


MIGRATE = r"""
import sys
sys.path.insert(0, sys.argv[1])
from guppi_runtime.jobs.testlab import TestLab
lab = TestLab(sys.argv[2])
print(lab.schema, lab.schema_error)
"""


class MigrationRaceTests(SchemaTwoTests):
    def test_two_processes_migrating_the_same_file_both_end_at_schema_2(self):
        import sqlite3
        import subprocess
        import sys
        path = self._schema_one_file()
        db = sqlite3.connect(path)
        db.execute("PRAGMA journal_mode=WAL")      # every testlab.db TestLab ever wrote is in WAL mode (the mode is stored in the file)
        db.close()
        src = str(Path(__file__).resolve().parents[1] / "src")
        procs = [subprocess.Popen([sys.executable, "-c", MIGRATE, src, str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        for p in procs:
            out, err = p.communicate(timeout=120)
            self.assertEqual((p.returncode, out.strip()), (0, "2 None"), err)
        db = sqlite3.connect(path)
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
        self.assertEqual(db.execute("SELECT owner FROM events").fetchall(), [("old",)])
        db.close()
        self.assertIn(len(list(path.parent.glob("*.bak-*"))), (1, 2))         # OP-S2-20: a second backup is possible, never a lost row


if __name__ == "__main__":
    unittest.main()
