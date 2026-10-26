"""Spec 2, S2.H6, SCH-08 (G2-S2-11): the server dies or sends garbage. Alte Leases `unterbrochen`, neue `gen`, Canary ungültig; ein Job einer lesenden
Rolle läuft erneut, einer schreibenden nicht; der vierte Absturz in 10 Minuten sperrt den Server und fragt den Captain; Müll zweimal gibt einen
kontrollierten Neustart. Fake loader and runtime; no model, no GPU."""
import tempfile
import unittest

import test_job_supervisor as tjs
from guppi_runtime.jobs.model_scheduler import SchedulerError
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
from model_scheduler_fakes import make_scheduler, resolution


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sched, self.lab, self.loader, self.runtime, self.audit, self.clock = make_scheduler(self.tmp.name)
        self.addCleanup(self.sched._release_gpu)
        self.canary = []
        self.sched.canary_invalidate = self.canary.append

    def start(self, job="SDJ-1"):
        self.assertTrue(self.sched.take_for_job(job, 5)["granted"])
        return self.sched.ensure_server(resolution(), run_id=job)

    def crash(self):
        self.runtime.running = False
        out = self.sched.poll()
        self.runtime.running = True
        return out

    def state(self, run_id):
        with self.lab._db() as db:
            return db.execute("SELECT state FROM slot_leases WHERE run_id = ?", (run_id,)).fetchone()["state"]

    def server(self):
        with self.lab._db() as db:
            return dict(db.execute("SELECT * FROM slot_server WHERE name = 'main'").fetchone())


class CrashTests(Base):
    def test_a_crash_in_the_middle_of_a_run_interrupts_its_leases_and_the_next_start_is_a_new_generation(self):
        self.assertEqual(self.start()["gen"], 1)
        self.assertTrue(self.sched.take_for_job("SDJ-2", 5)["granted"])
        self.assertEqual(self.crash(), {"state": "aus", "action": "server_exited"})
        self.assertEqual((self.state("SDJ-1"), self.state("SDJ-2")), ("unterbrochen", "unterbrochen"))
        self.assertEqual(self.canary, ["scheduler: server_exited"])                  # the next load runs the canary again
        self.assertEqual(self.audit.of("SLOT_SERVER_EXITED")[0]["interrupted"], ["SDJ-1", "SDJ-2"])
        self.assertEqual(self.loader.loaded, [("main.local", 2, 32768)])             # not started again by itself (lazy)
        self.assertTrue(self.sched.take_for_job("SDJ-3", 5)["granted"])
        self.assertEqual(self.sched.ensure_server(resolution(), run_id="SDJ-3")["gen"], 2)

    def test_the_fourth_crash_within_ten_minutes_locks_the_server_and_asks_the_captain(self):
        for n in range(3):
            self.start(f"SDJ-{n}")
            self.assertEqual(self.crash()["state"], "aus")
            self.clock.t += 60
            self.assertEqual(self.sched.decisions(), [])
        self.start("SDJ-9")
        self.assertEqual(self.crash()["state"], "gesperrt")
        self.assertEqual(len(self.audit.of("SLOT_SERVER_GESPERRT")), 1)
        (ask,) = self.sched.decisions()
        self.assertEqual((ask["kind"], ask["title"], ask["ways"]), ("slot_server", "Modellserver gesperrt, bitte prüfen", ["bestaetigen", "ablehnen"]))
        self.assertEqual(self.sched.take_for_job("SDJ-10", 5)["reason"], "gesperrt")
        with self.assertRaises(SchedulerError):
            self.sched.ensure_server(resolution(), run_id="SDJ-10")
        self.assertEqual(self.sched.answer(ask["id"], "ablehnen"), {"kind": "slot_server", "unlocked": False})   # declined: still locked, question closed
        self.assertEqual((self.sched.decisions(), self.server()["state"]), ([], "gesperrt"))

    def test_four_crashes_spread_over_more_than_ten_minutes_do_not_lock(self):
        for n in range(6):
            self.start(f"SDJ-{n}")
            self.assertEqual(self.crash()["state"], "aus")
            self.clock.t += 601                                                       # each crash leaves the window of the one before
        self.assertEqual((self.server()["state"], self.sched.decisions(), self.audit.of("SLOT_SERVER_GESPERRT")), ("aus", [], []))

    def test_confirming_unlocks_and_the_crash_count_starts_over(self):
        for n in range(4):
            self.start(f"SDJ-{n}")
            self.crash()
        (ask,) = self.sched.decisions()
        self.assertEqual(self.sched.answer(ask["id"], "bestaetigen"), {"kind": "slot_server", "unlocked": True})
        self.assertEqual((self.sched.decisions(), self.server()["state"]), ([], "aus"))
        self.assertTrue(self.sched.take_for_job("SDJ-20", 5)["granted"])
        self.assertEqual(self.sched.ensure_server(resolution(), run_id="SDJ-20")["action"], "started")
        self.crash()
        self.assertEqual(self.server()["state"], "aus")                               # one crash is not the fourth
        with self.assertRaises(ValueError):
            self.sched.answer(ask["id"], "bestaetigen")                               # answered once

    def test_unlocking_after_a_lost_lease_frees_what_the_old_server_left_behind(self):
        self.start()
        self.lab.release(self.sched._token)                                           # somebody takes the lease over ...
        self.assertTrue(self.lab.try_acquire("intruder", "x"))
        self.sched._lease_lost(self.sched._token)
        (ask,) = self.sched.decisions()
        self.assertEqual(ask["reason"], "gpu_lease_lost")
        self.sched.answer(ask["id"], "bestaetigen")
        self.assertIsNone(self.sched._resolution)
        self.assertIsNone(self.sched._reserved)

    def test_garbage_twice_in_five_minutes_restarts_the_server_in_a_controlled_way(self):
        self.start()
        self.assertEqual(self.sched.report("SDJ-1", "garbage"), {"count": 1, "restart": False})
        self.assertEqual(self.server()["state"], "bereit")
        self.clock.t += 301                                                           # outside the window: the first report is forgotten
        self.assertEqual(self.sched.report("SDJ-1", "garbage"), {"count": 1, "restart": False})
        self.clock.t += 10
        out = self.sched.report("SDJ-1", "garbage")
        self.assertEqual((out["restart"], out["state"]), (True, "aus"))
        self.assertEqual(self.loader.unloaded, ["main.local"])                        # stopped over its own loader and pid
        self.assertEqual(self.state("SDJ-1"), "unterbrochen")
        self.assertEqual(self.canary, ["scheduler: garbage"])
        self.assertEqual(len(self.audit.of("SLOT_SERVER_GARBAGE")), 1)
        self.assertEqual(self.sched.report("SDJ-1", "garbage")["restart"], False)    # nothing runs: nothing to restart
        with self.assertRaises(ValueError):
            self.sched.report("SDJ-1", "slow")


class CrashJobs(tjs.SlotTests):
    """The jobs of the Supervisor after the crash (D2.8, G2-S2-11): `mutates: false` runs again, `mutates: true` does not run on its own."""
    config_overrides = {"workers": 3}


for _name in dir(tjs.SlotTests):                                                       # only the setup is inherited, not the tests of SlotTests
    if _name.startswith("test"):
        setattr(CrashJobs, _name, None)


class CrashJobTests(CrashJobs):
    def crashed_job(self, role):
        job_id = self.queued(role)
        self.assertEqual(self.sup.claim("w", [role])["job"]["job_id"], job_id)
        self.assertEqual(self.sup.confirm_start(job_id, "w")["status"], "running")
        self.runtime.running = False
        self.assertEqual(self.slots.poll()["action"], "server_exited")
        self.runtime.running = True
        self.assertEqual(self.lease(job_id)["state"], "unterbrochen")
        out = self.sup.fail(job_id, "w", reason_code="provider_unavailable", outcome_known=False)
        return job_id, out

    def worker(self, role, crash):
        from guppi_runtime.jobs.job_worker import Worker, model_text_handler
        calls = []

        def infer(job_id, request):
            calls.append(job_id)
            if crash and len(calls) == 1:                          # the server dies under the request, the poller notices
                self.runtime.running = False
                self.slots.poll()
                self.runtime.running = True
                return {"status": "failed", "error": "ConnectionResetError: [WinError 10054]"}
            return {"status": "completed", "model_result": {"content": "fertig", "usage": {}}}
        inner = model_text_handler(infer, lambda job: [{"role": "user", "content": "x"}], on_degenerate=lambda attempt, reason: None)

        def handler(job, attempt, ctx):
            if self.sup.role_mutates(job):
                ctx.mark_mutated()                                 # the writing role has changed something before the request: the outcome is unknown
            return inner(job, attempt, ctx)
        return Worker(self.sup, "w-" + role, [role], handler, heartbeat_every=3600), calls

    def attempts(self, job_id):
        return [a["outcome"] for a in self.load(job_id)["attempt_log"]]

    def test_a_crash_under_the_real_worker_a_reading_job_runs_again_a_writing_job_does_not(self):
        reader = self.queued("reviewer")
        worker, calls = self.worker("reviewer", crash=True)
        out = worker.run_once()
        self.assertEqual(out["status"], "failed")
        self.assertEqual(self.lease(reader)["state"], "unterbrochen")                  # the poller marked it when the server died
        self.assertEqual(self.load(reader)["state"], "QUEUED")                          # retried within the usual limit
        self.clock.advance(60)                                                          # past the backoff
        again = worker.run_once()
        self.assertEqual(again["status"], "handled", again)                             # a new server (generation 2), the job ran again
        self.assertEqual(self.attempts(reader)[0], "FAILED")
        self.assertEqual(self.loader.loaded[-1][0], "main.local")
        self.assertEqual(len(self.loader.loaded), 2)

        writer = self.queued("coder")
        worker, calls = self.worker("coder", crash=True)
        self.assertEqual(worker.run_once()["status"], "failed")
        self.clock.advance(3600)
        self.assertEqual(worker.run_once()["status"], "idle")                           # no silent repeat: back to a person
        self.assertNotEqual(self.load(writer)["state"], "QUEUED")
        self.assertEqual(len(calls), 1)
        self.assertLessEqual(sum(1 for a in self.attempts(writer) if a == "UNKNOWN"), 1)   # at most one attempt without an outcome


del CrashJobs     # not collected on its own


if __name__ == "__main__":
    unittest.main()
