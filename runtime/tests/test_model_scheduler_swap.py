"""Spec 2, SCH-06: another recipe than the loaded one only by the Captain's rule `swap` (none | idle | fallback)."""
import tempfile
import unittest

from guppi_runtime.jobs.model_scheduler import SchedulerError
from host_isolation import setUpModule, tearDownModule  # noqa: F401
from model_scheduler_fakes import make_scheduler, resolution


class SwapTests(unittest.TestCase):
    def make(self, swap):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sched, self.lab, self.loader, _, _, _ = make_scheduler(self.tmp.name, swap=swap)
        self.addCleanup(self.sched._release_gpu)
        self.sched.take_for_job("SDJ-1", 5)
        self.sched.ensure_server(resolution(recipe="main.local"), run_id="SDJ-1")

    def lease(self, run_id):
        with self.lab._db() as db:
            return dict(db.execute("SELECT * FROM slot_leases WHERE run_id=?", (run_id,)).fetchone())

    def test_without_a_rule_the_job_waits_with_its_reason(self):
        self.make("none")
        self.assertEqual(self.sched.take_for_job("SDJ-2", 5, recipe="helper.local"),
                         {"granted": False, "slot": None, "reason": "model_swap_not_allowed"})
        self.assertEqual(self.lease("SDJ-2")["reason"], "model_swap_not_allowed")
        self.assertTrue(self.sched.take_for_job("SDJ-2", 5, recipe=None)["granted"])     # recipe not known at claim: the start checks again
        with self.assertRaises(SchedulerError) as ctx:
            self.sched.ensure_server(resolution(recipe="helper.local"), run_id="SDJ-2")
        self.assertEqual(ctx.exception.reason, "model_swap_not_allowed")
        self.assertEqual(self.loader.loaded, [("main.local", 2, 32768)])

    def test_idle_reloads_only_when_no_other_lease_is_active(self):
        self.make("idle")
        self.assertEqual(self.sched.take_for_job("SDJ-2", 5, recipe="helper.local")["reason"], "model_swap_not_allowed")   # SDJ-1 still runs
        self.sched.release("SDJ-1")
        self.assertTrue(self.sched.take_for_job("SDJ-2", 5, recipe="helper.local")["granted"])
        out = self.sched.ensure_server(resolution(recipe="helper.local", model="helper-model"), run_id="SDJ-2")
        self.assertEqual((out["action"], out["gen"]), ("started", 2))
        self.assertEqual((self.loader.unloaded, [r for r, _, _ in self.loader.loaded]), (["main.local"], ["main.local", "helper.local"]))
        lease = self.lease("SDJ-2")
        self.assertEqual((lease["state"], lease["server_gen"]), ("aktiv", 2))           # the asking run keeps its slot across the reload
        self.assertEqual(self.lab.holder()["purpose"], "Modellserver helper.local")

    def test_fallback_admits_a_job_to_the_running_fallback_recipe_but_never_switches_silently(self):
        self.make({"fallback": "main.local"})
        self.assertTrue(self.sched.take_for_job("SDJ-2", 5, recipe="big.local")["granted"])
        with self.assertRaises(SchedulerError) as ctx:
            self.sched.ensure_server(resolution(recipe="big.local"), run_id="SDJ-2")
        self.assertEqual(ctx.exception.reason, "model_swap_fallback_unsupported")       # moving the attempt to the fallback model is open (S2.H5)
        self.assertEqual(len(self.loader.loaded), 1)


if __name__ == "__main__":
    unittest.main()
