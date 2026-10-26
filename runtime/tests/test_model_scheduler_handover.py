"""Spec 2, S2.H5, SCH-10 (G2-S2-07): benchmarks and builds can still take the GPU exclusively. The whole way with a second process (its own `TestLab` on the
same file): request in `TestLab.acquire` -> scheduler drains -> server off -> lease free -> request gone -> server stays off. No model, no GPU."""
import tempfile
import unittest

from guppi_runtime.jobs.model_scheduler import SchedulerError
from guppi_runtime.jobs.testlab import LeaseBusy, TestLab
from guppi_runtime.models import gpu_preflight
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
from model_scheduler_fakes import make_scheduler, resolution


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sched, self.lab, self.loader, self.runtime, self.audit, self.clock = make_scheduler(self.tmp.name)
        self.addCleanup(self.sched._release_gpu)
        self.bench = TestLab(self.lab.path, clock=self.clock, alive=lambda p: True, pid=222)

    def start(self, job="SDJ-1"):
        self.assertTrue(self.sched.take_for_job(job, 5)["granted"])
        return self.sched.ensure_server(resolution(), run_id=job)

    def pending(self):
        with self.lab._db() as db:
            return [r["owner"] for r in db.execute("SELECT owner FROM handover_requests")]

    def state(self, run_id="SDJ-1"):
        with self.lab._db() as db:
            return db.execute("SELECT state FROM slot_leases WHERE run_id = ?", (run_id,)).fetchone()["state"]


class HandoverTests(Base):
    def test_the_whole_way_from_request_to_a_server_that_stays_off(self):
        self.start()
        steps, seen = [], {}

        def nap(seconds):                                    # the benchmark sleeps; meanwhile the desk's poller takes its steps
            self.clock.t += seconds
            steps.append(self.sched.poll()["action"])
            if len(steps) == 1:
                seen["queued"] = (self.pending(), self.sched.view()["exklusiv"]["eigner"], self.sched.take_for_job("SDJ-9", 5)["reason"])
            if len(steps) == 2:
                self.sched.release("SDJ-1")                  # the active run ends

        def preflight(owner):
            seen["pids"] = gpu_preflight.scheduler_server_pids(self.bench)       # clear_leftovers finds no server with a live lease any more
            seen["server"] = self.sched.view()["server"]["state"]

        with self.bench.lease("bench-ladder", "context ladder", wait_s=100, poll_s=5, sleep=nap, preflight=preflight):
            self.assertEqual(self.bench.holder()["owner"], "bench-ladder")
            self.assertEqual(self.pending(), [])             # the request is gone as soon as the lease is granted
            self.assertEqual(self.loader.unloaded, ["main.local"])
            self.assertEqual(self.sched.take_for_job("SDJ-3", 5)["reason"], "exklusiv:bench-ladder")
        self.assertEqual(steps, ["draining", "draining", "handed_over"])
        self.assertEqual(seen["queued"], (["bench-ladder"], "bench-ladder", "drain"))
        self.assertEqual(seen["pids"], set())
        self.assertEqual(seen["server"], "exklusiv")
        self.assertIsNone(self.bench.holder())
        self.assertEqual(self.sched.poll()["state"], "aus")                      # the benchmark is done: the scheduler goes `aus` ...
        self.assertEqual(self.loader.loaded, [("main.local", 2, 32768)])         # ... and does not rebuild on suspicion
        self.assertEqual(self.sched.view()["server"]["state"], "aus")

    def test_while_the_server_lives_its_pid_is_protected_from_the_benchmarks_cleanup(self):
        self.start()
        self.assertEqual(gpu_preflight.scheduler_server_pids(self.bench), {4242})
        self.sched.exclusive("bench", "x")                                        # drain: the server still runs
        self.assertEqual(gpu_preflight.scheduler_server_pids(self.bench), {4242})
        self.sched.release("SDJ-1")
        self.sched.poll()                                                         # stopped, handed over
        self.assertEqual(gpu_preflight.scheduler_server_pids(self.bench), set())

    def test_past_the_drain_limit_the_request_stands_and_no_run_is_killed(self):
        self.start()

        def nap(seconds):
            self.clock.t += seconds
            self.lab.heartbeat(self.sched._token)             # the real beat thread runs every 30 s; the test clock jumps
            self.sched.poll()
        with self.assertRaises(LeaseBusy):
            self.bench.acquire("bench", "x", wait_s=2000, poll_s=5, sleep=nap)
        self.assertEqual(len(self.audit.of("SLOT_DRAIN_OVERDUE")), 1)             # the Captain is told once
        self.assertEqual(self.state(), "aktiv")                                   # nobody was killed
        self.assertEqual(self.loader.unloaded, [])
        self.assertEqual(self.sched.view()["server"]["state"], "drain")
        self.assertEqual(self.pending(), [])                                      # the benchmark gave up: its request is gone
        self.sched.poll()
        self.assertEqual(self.sched.view()["server"]["state"], "bereit")          # and the drain ends, the slots are open again

    def test_the_night_chain_comes_before_the_restart_of_the_server(self):
        with self.bench.reserve("night-g", "G builds", priority=1):
            with self.assertRaises(SchedulerError) as ctx:
                self.start()
            self.assertEqual(ctx.exception.reason, "gpu_lease_deferred:night-g")
            self.assertEqual(self.loader.loaded, [])
            self.assertIsNone(self.lab.holder())
        self.assertEqual(self.sched.ensure_server(resolution(), run_id="SDJ-1")["action"], "started")   # the chain is done


if __name__ == "__main__":
    unittest.main()
