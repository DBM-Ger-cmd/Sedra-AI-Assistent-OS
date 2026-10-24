"""Spec 2, SCH-02: the slot store on testlab.db (schema 2). Order by step, then arrival; never more than N active, also with two
processes racing for the slots (OP-S2-15, 100 rounds each)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.jobs import slot_store
from guppi_runtime.jobs.testlab import TestLab
from host_isolation import setUpModule, tearDownModule  # noqa: F401

SRC = str(Path(__file__).resolve().parents[1] / "src")
CFG = {"age_after_s": 120, "age_cap": 5, "swap": "none", "queue_max": 6, "wait_max_s": 600}
T0 = "2026-10-24T00:00:00Z"


def at(seconds):
    return f"2026-10-24T00:{seconds // 60:02d}:{seconds % 60:02d}Z"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "testlab.db"
        self.conn = TestLab(self.path).connect()
        self.addCleanup(self.conn.close)
        slot_store.set_server(self.conn, T0, "startet", recipe="main.local", slots=2, context_per_slot=32768)
        slot_store.set_server(self.conn, T0, "bereit", pid=4242)


class OrderTests(Base):
    def test_n_plus_one_runs_on_n_slots_wait_in_line_and_the_captain_goes_first(self):
        for i, run in enumerate(("A", "B", "C")):
            slot_store.request(self.conn, run, "job", "sup", 5, at(i))
        took = [slot_store.take(self.conn, r, at(5), CFG)["granted"] for r in ("A", "B", "C")]
        self.assertEqual(took, [True, True, False])
        slot_store.request(self.conn, "D", "direkt", "chat", 7, at(10))
        slot_store.release(self.conn, "A", "fertig", at(11))
        self.assertEqual(slot_store.take(self.conn, "C", at(12), CFG)["reason"], "wartet_in_reihe")     # the Captain's call overtakes
        self.assertTrue(slot_store.take(self.conn, "D", at(12), CFG)["granted"])
        slot_store.release(self.conn, "B", "fertig", at(13))
        self.assertTrue(slot_store.take(self.conn, "C", at(14), CFG)["granted"])
        self.assertEqual(sorted(r["run_id"] for r in slot_store.view(self.conn, at(14), CFG)["belegt"]), ["C", "D"])

    def test_equal_steps_go_by_arrival_and_a_routine_run_ages_up_to_agent_only(self):
        slot_store.request(self.conn, "busy-1", "job", "sup", 7, T0)
        slot_store.request(self.conn, "busy-2", "job", "sup", 7, T0)
        slot_store.take(self.conn, "busy-1", T0, CFG)
        slot_store.take(self.conn, "busy-2", T0, CFG)
        slot_store.request(self.conn, "routine", "job", "sup", 3, at(0))
        slot_store.request(self.conn, "agent", "job", "sup", 5, at(1))
        line = [r["run_id"] for r in slot_store.view(self.conn, at(60), CFG)["schlange"]]
        self.assertEqual(line, ["agent", "routine"])
        line = [r["run_id"] for r in slot_store.view(self.conn, "2026-10-24T00:04:00Z", CFG)["schlange"]]
        self.assertEqual(line, ["routine", "agent"])          # 240 s: Routine 3 + 2 steps = 5, equal to Agent, and it came first


RACE = r"""
import sys
sys.path.insert(0, sys.argv[1])
from guppi_runtime.jobs import slot_store
from guppi_runtime.jobs.testlab import TestLab
conn = TestLab(sys.argv[2], pid=int(sys.argv[3])).connect()
cfg = {"age_after_s": 120, "age_cap": 5, "swap": "none", "queue_max": 6, "wait_max_s": 600}
now = "2026-10-24T00:00:00Z"
granted = most = 0
for i in range(100):
    runs = [f"p{sys.argv[3]}-{i}-{k}" for k in "ab"]           # each process asks for both slots at once
    for run in runs:
        slot_store.request(conn, run, "job", "sup", 5, now)
    for run in runs:
        if slot_store.take(conn, run, now, cfg)["granted"]:
            granted += 1
        most = max(most, conn.execute("SELECT COUNT(*) FROM slot_leases WHERE state = 'aktiv'").fetchone()[0])
    for run in runs:
        slot_store.release(conn, run, "fertig", now)
print(granted, most)
"""


class RaceTests(Base):
    def test_two_processes_never_hold_more_than_n_slots(self):
        procs = [subprocess.Popen([sys.executable, "-c", RACE, SRC, str(self.path), str(n)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for n in (1, 2)]
        results = []
        for p in procs:
            out, err = p.communicate(timeout=300)
            self.assertEqual(p.returncode, 0, err)
            results.append(tuple(int(x) for x in out.split()))
        self.assertTrue(all(granted > 0 for granted, _ in results), results)
        self.assertTrue(all(most <= 2 for _, most in results), results)
        active = self.conn.execute("SELECT COUNT(*) FROM slot_leases WHERE state = 'aktiv'").fetchone()[0]
        self.assertEqual(active, 0)
        takes = self.conn.execute("SELECT COUNT(*) FROM slot_events WHERE kind = 'take'").fetchone()[0]
        self.assertEqual(takes, sum(g for g, _ in results))


if __name__ == "__main__":
    unittest.main()
