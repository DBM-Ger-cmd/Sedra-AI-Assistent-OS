"""Spec 2, S2.H6, SCH-07 (G2-S2-10): a line longer than `queue_max` or a wait longer than `wait_max_s` gives ONE decision `cloud_offload` (display and
"ablehnen"), at most one per waiting run and `offer_every_s`; the scheduler never switches to the cloud. Fake loader and runtime; no GPU."""
import tempfile
import unittest

from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
from model_scheduler_fakes import make_scheduler, resolution


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sched, self.lab, self.loader, self.runtime, self.audit, self.clock = make_scheduler(self.tmp.name, queue_max=2, wait_max_s=600, offer_every_s=900)
        self.addCleanup(self.sched._release_gpu)
        self.assertTrue(self.sched.take_for_job("SDJ-1", 5)["granted"])
        self.sched.ensure_server(resolution(slots=1), run_id="SDJ-1")                    # one slot, taken

    def wait(self, run_id, task_id=None):
        self.sched.take_for_job(run_id, 5, agent_id="A-1", task_id=task_id)
        self.clock.t += 1


class OfferTests(Base):
    def test_a_short_line_and_a_short_wait_give_no_offer(self):
        self.wait("SDJ-2"); self.wait("SDJ-3")
        self.sched.poll()
        self.assertEqual(self.sched.decisions(), [])

    def test_a_line_longer_than_queue_max_gives_one_offer_for_the_oldest(self):
        for n in (2, 3, 4):
            self.wait(f"SDJ-{n}", f"T-{n}")
        self.sched.poll(); self.sched.poll()                                              # polled twice: still one decision
        (offer,) = self.sched.decisions()
        self.assertEqual((offer["kind"], offer["id"], offer["run_id"], offer["grund"]), ("cloud_offload", "cloud_offload:SDJ-2", "SDJ-2", "schlange"))
        self.assertEqual(offer["ways"], ["ablehnen", "cloud_diesen_lauf"])
        self.assertRegex(offer["title"], r"^Lauf T-2 wartet seit \d+ Minuten auf einen Slot\. Cloud-Stufe nutzen\?$")
        self.assertEqual(len(self.audit.of("SLOT_CLOUD_OFFER")), 1)

    def test_a_wait_longer_than_wait_max_s_gives_an_offer(self):
        self.wait("SDJ-2", "T-2")
        self.clock.t += 601
        self.sched.poll()
        (offer,) = self.sched.decisions()
        self.assertEqual((offer["run_id"], offer["grund"]), ("SDJ-2", "wartezeit"))
        self.assertIn("10 Minuten", offer["title"])

    def test_rejecting_closes_it_and_there_is_no_new_one_before_offer_every_s(self):
        for n in (2, 3, 4):
            self.wait(f"SDJ-{n}")
        self.sched.poll()
        (offer,) = self.sched.decisions()
        self.assertEqual(self.sched.answer(offer["id"], "ablehnen"), {"kind": "cloud_offload", "run_id": "SDJ-2", "approved": False})
        self.clock.t += 899
        self.sched.poll()
        self.assertEqual(self.sched.decisions(), [])
        self.clock.t += 2
        self.sched.poll()
        self.assertEqual([d["run_id"] for d in self.sched.decisions()], ["SDJ-2"])        # 900 s later: asked again
        self.assertEqual(len(self.audit.of("SLOT_CLOUD_OFFER")), 2)

    def test_accepting_only_returns_the_mark_and_changes_nothing_in_the_scheduler(self):
        for n in (2, 3, 4):
            self.wait(f"SDJ-{n}")
        self.sched.poll()
        before = (self.sched.view()["server"], len(self.loader.loaded), self.loader.unloaded)
        self.assertEqual(self.sched.answer("cloud_offload:SDJ-2", "cloud_diesen_lauf"), {"kind": "cloud_offload", "run_id": "SDJ-2", "approved": True})
        self.assertEqual((self.sched.view()["server"], len(self.loader.loaded), self.loader.unloaded), before)    # no switch, no stop
        self.assertEqual([r["run_id"] for r in self.sched.view()["schlange"]], ["SDJ-2", "SDJ-3", "SDJ-4"])         # the run still waits for a slot

    def test_an_offer_vanishes_when_its_run_gets_a_slot_or_ends(self):
        for n in (2, 3, 4):
            self.wait(f"SDJ-{n}")
        self.sched.poll()
        self.assertEqual(len(self.sched.decisions()), 1)
        self.sched.release("SDJ-1")
        self.sched.take_for_job("SDJ-2", 5)                                                 # SDJ-2 gets the free slot
        self.sched.poll()
        self.assertEqual([d for d in self.sched.decisions() if d["run_id"] == "SDJ-2"], [])

    def test_a_wrong_way_or_an_unknown_decision_is_refused(self):
        for n in (2, 3, 4):
            self.wait(f"SDJ-{n}")
        self.sched.poll()
        with self.assertRaises(ValueError):
            self.sched.answer("cloud_offload:SDJ-2", "einmal")
        with self.assertRaises(ValueError):
            self.sched.answer("cloud_offload:SDJ-9", "ablehnen")

    def test_off_there_are_no_decisions(self):
        off, *_ = make_scheduler(self.tmp.name + "-off", enabled=False)
        self.assertEqual(off.decisions(), [])


if __name__ == "__main__":
    unittest.main()
