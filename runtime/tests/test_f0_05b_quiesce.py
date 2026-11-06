"""F0-05B: deterministische Quiesce-/Claim-/Start-Races ohne Modell/GPU/Netz.

Tests use an isolated temporary JobStore. They intentionally do NOT verify
Windows OS-lock behavior or the later integration commit.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
import json
import sqlite3
import tempfile
import threading
import time
import unittest

from sedra_runtime.core.audit import AuditLog
from sedra_runtime.jobs.job_supervisor import JobError, JobSupervisor, SupervisorConfig, SupervisorJobStore
from sedra_runtime.jobs.job_worker import Worker
from sedra_runtime.orchestra.service import Orchestra
from sedra_runtime.selfdev.development_contracts import development_contract
from test_job_supervisor import raw_config


class FakeSlots:
    enabled = True
    class _Config:
        @staticmethod
        def plan():
            return {"age_after_s": 3600, "age_cap": 9}
    config = _Config()

    def __init__(self, *, wait_entered=None, wait_release=None, fail_requeue=False):
        self.requests = 0
        self.wait_entered = wait_entered
        self.wait_release = wait_release
        self.fail_requeue = fail_requeue
        self.leases = {}

    def wait_for_job(self, job_id, priority, **kw):
        self.requests += 1
        if self.fail_requeue and self.requests >= 2:
            raise OSError("slot_backend_unavailable")
        self.leases[job_id] = "waiting"

    def take_for_job(self, job_id, priority, **kw):
        if self.wait_entered:
            self.wait_entered.set()
            assert self.wait_release.wait(2), "slot barrier stuck"
        self.leases[job_id] = "active"
        return {"granted": True, "slot": 1, "reason": None}

    def release(self, job_id, reason):
        self.leases.pop(job_id, None)


class QuiesceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audit = AuditLog(self.root / "audit.jsonl")
        self.config = SupervisorConfig(raw_config())
        self.sup = self.make_supervisor()

    def make_supervisor(self):
        return JobSupervisor(SupervisorJobStore(self.root / "jobs"), self.config,
                             audit=self.audit, clock=lambda: datetime(2026, 11, 6, tzinfo=timezone.utc))

    def add_job(self, sup=None):
        sup = sup or self.sup
        contract = development_contract(objective="safe-test", classification="E1",
                                        acceptance_criteria=[{"type": "capability_smoke_test", "id": "smoke"}],
                                        verification_plan=[{"type": "deterministic_tests"}])
        job = sup.create_job(contract, requested_role="reviewer")
        sup.enqueue(job["job_id"])
        return job["job_id"]

    def load(self, job_id):
        return self.sup.store.load(job_id)

    def claim(self, sup=None, worker="same"):
        return (sup or self.sup).claim(worker, ["reviewer"])

    def run_worker(self):
        worker = Worker(self.sup, "same", ["reviewer"], lambda *_: {"advance": []})
        worker._last_reap = worker._mono()
        return worker

    def test_qb01_gate_is_per_supervisor(self):
        other = self.make_supervisor()
        self.add_job(other)
        self.assertTrue(self.sup.request_quiesce())
        out = self.claim(other)
        self.assertEqual(out["status"], "claimed")
        self.assertNotEqual(other.quiesce_owner_id, self.sup.quiesce_owner_id)

    def test_qb02_same_worker_name_is_not_owner(self):
        other = self.make_supervisor()
        job_id = self.add_job(other)
        self.claim(other, "same")
        before = other.store.load(job_id)["worker"]
        self.assertTrue(self.sup.request_quiesce())
        self.assertEqual(before, other.store.load(job_id)["worker"])

    def test_qb03_fast_reject_preserves_queue_and_attempts(self):
        job_id = self.add_job()
        self.assertTrue(self.sup.request_quiesce())
        result = self.claim()
        self.assertEqual((result["status"], result["code"]), ("waiting", "quiesced"))
        self.assertEqual((self.load(job_id)["state"], self.load(job_id)["attempts"], self.load(job_id)["worker"]),
                         ("QUEUED", 0, None))

    def test_qb04_cut_during_store_scan_prevents_claim(self):
        job_id = self.add_job()
        enter, release = threading.Event(), threading.Event()
        original = self.sup.store.scan
        def delayed():
            enter.set()
            self.assertTrue(release.wait(2))
            return original()
        result = []
        with mock.patch.object(self.sup.store, "scan", side_effect=delayed):
            thread = threading.Thread(target=lambda: result.append(self.claim()))
            thread.start()
            self.assertTrue(enter.wait(2))
            # Begin the gate cut while scan holds the Store lock.
            cut = []
            cutter = threading.Thread(target=lambda: cut.append(self.sup.request_quiesce(wait_s=1.5)))
            cutter.start()
            self.assertTrue(self.sup._quiesce_requested.wait(1))
            release.set()
            thread.join(2)
            cutter.join(2)
        self.assertFalse(thread.is_alive() or cutter.is_alive())
        self.assertEqual(cut, [True])
        self.assertEqual(result[0]["code"], "quiesced")
        self.assertIsNone(self.load(job_id)["worker"])

    def test_qb05_existing_commit_finishes_before_gate_cut(self):
        job_id = self.add_job()
        entered, release = threading.Event(), threading.Event()
        original = self.sup.store.mutate
        @contextmanager
        def delayed(job):
            with original(job) as record:
                entered.set()
                self.assertTrue(release.wait(2))
                yield record
        results = []
        with mock.patch.object(self.sup.store, "mutate", delayed):
            t1 = threading.Thread(target=lambda: results.append(self.claim()))
            t1.start()
            self.assertTrue(entered.wait(2))
            t2 = threading.Thread(target=lambda: results.append(self.sup.request_quiesce(wait_s=1.5)))
            t2.start()
            self.assertTrue(self.sup._quiesce_requested.wait(1))
            release.set()
            t1.join(3); t2.join(3)
        self.assertFalse(t1.is_alive() or t2.is_alive())
        self.assertTrue(any(isinstance(x, dict) and x["status"] == "claimed" for x in results))
        self.assertEqual(self.load(job_id)["attempts"], 0)
        self.assertIsNone(self.load(job_id)["worker"])

    def test_qb06_slot_grant_during_cut_returns_to_queue(self):
        job_id = self.add_job()
        enter, release = threading.Event(), threading.Event()
        slots = FakeSlots(wait_entered=enter, wait_release=release)
        self.sup.slots = slots
        out = []
        thread = threading.Thread(target=lambda: out.append(self.claim()))
        thread.start()
        self.assertTrue(enter.wait(2))
        self.assertTrue(self.sup.request_quiesce(wait_s=.5))
        release.set();thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(out[0]["code"], "quiesced")
        self.assertEqual(slots.leases[job_id], "waiting")
        self.assertIsNone(self.load(job_id)["worker"])

    def test_qb07_slot_requeue_failure_prevents_drained(self):
        job_id = self.add_job()
        enter, release = threading.Event(), threading.Event()
        self.sup.slots = FakeSlots(wait_entered=enter, wait_release=release, fail_requeue=True)
        result = []
        t = threading.Thread(target=lambda: result.append(self.claim()))
        t.start();self.assertTrue(enter.wait(2))
        self.assertTrue(self.sup.request_quiesce(wait_s=.5))
        release.set();t.join(2)
        self.assertFalse(t.is_alive())
        self.assertEqual(self.load(job_id)["attempts"], 0)
        self.assertFalse(self.sup.complete_quiesce())
        self.assertEqual(self.sup.quiesce_state, "SHUTDOWN_PENDING")

    def test_qb08_unstarted_claim_returns_without_attempt(self):
        job_id = self.add_job()
        before = self.claim()["job"]["worker"]["claim_ticket"]
        self.assertTrue(self.sup.request_quiesce())
        job = self.load(job_id)
        self.assertEqual((job["state"], job["worker"], job["attempts"]), ("QUEUED", None, 0))
        self.assertTrue(before)

    def test_qb09_confirm_start_after_quiesce_does_not_run(self):
        job_id = self.add_job()
        self.claim()
        self.sup.request_quiesce()
        out = self.sup.confirm_start(job_id, "same")
        self.assertEqual(out["status"], "waiting")
        self.assertEqual(self.load(job_id)["attempt_log"], [])

    def test_qb10_started_before_quiesce_is_not_erased(self):
        job_id = self.add_job()
        self.claim()
        self.assertEqual(self.sup.confirm_start(job_id, "same")["status"], "running")
        self.assertTrue(self.sup.request_quiesce())
        self.assertFalse(self.sup.complete_quiesce())
        job = self.load(job_id)
        self.assertEqual((job["attempts"], job["attempt_log"][-1]["outcome"]), (1, "RUNNING"))

    def test_qb11_outer_append_lock_timeout_is_neutral(self):
        self.add_job()
        @contextmanager
        def timeout():
            raise RuntimeError("append_lock_timeout")
            yield
        with mock.patch.object(self.sup.store, "_lock", timeout):
            out = self.claim()
            self.assertEqual((out["status"], out["code"]), ("waiting", "claim_lock_timeout"))
            self.assertEqual(self.sup.run_next("same", ["reviewer"], lambda *_: None)["status"], "waiting")
            self.assertEqual(self.run_worker().run_once()["code"], "claim_lock_timeout")

    def test_qb12_unrelated_error_is_not_swallowed(self):
        self.add_job()
        @contextmanager
        def unexpected():
            raise RuntimeError("unexpected_fault")
            yield
        with mock.patch.object(self.sup.store, "_lock", unexpected):
            with self.assertRaisesRegex(RuntimeError, "unexpected_fault"):
                self.run_worker().run_once()
            with self.assertRaisesRegex(RuntimeError, "unexpected_fault"):
                self.sup.run_next("same", ["reviewer"], lambda *_: None)

    def test_qb13_shutdown_pending_then_drained_on_retry(self):
        class Pool:
            done = False
            def stop(self, _):
                return self.done
        pool = Pool()
        orch = Orchestra.__new__(Orchestra)
        orch.supervisor = self.sup
        orch._stopping = False
        orch.tick_thread = None
        orch.worker_pool = pool
        orch.conn = sqlite3.connect(":memory:")
        try:
            self.assertFalse(orch.stop_tick(wait_s=.01))
            self.assertEqual(orch._quiesce_state, "SHUTDOWN_PENDING")
            self.assertEqual(orch.conn.execute("SELECT 1").fetchone()[0], 1)
            pool.done = True
            orch.close(wait_s=.05)
            self.assertEqual(orch._quiesce_state, "DRAINED")
        finally:
            try: orch.conn.close()
            except Exception: pass

    def test_qb14_gate_wait_timeout_is_pending_and_sticky(self):
        entered, release = threading.Event(), threading.Event()
        def hold():
            self.sup._quiesce_lock.acquire()
            entered.set()
            release.wait(2)
            self.sup._quiesce_lock.release()
        t = threading.Thread(target=hold)
        t.start();self.assertTrue(entered.wait(1))
        self.assertFalse(self.sup.request_quiesce(wait_s=.01))
        self.assertTrue(self.sup.quiescing)
        self.assertEqual(self.sup.quiesce_state, "SHUTDOWN_PENDING")
        release.set();t.join(2)
        self.assertTrue(self.sup.request_quiesce(wait_s=.05))
        self.assertTrue(self.sup.complete_quiesce())

    def test_qb15_failed_audit_cannot_reopen_gate(self):
        self.add_job();self.sup.request_quiesce()
        def fail(event, *a, **kw):
            if event == "JOB_CLAIM_DEFERRED": raise OSError("audit_broken")
        with mock.patch.object(self.audit, "append", side_effect=fail):
            self.assertEqual(self.claim()["code"], "quiesced")
        self.assertTrue(self.sup.quiescing)
        self.assertFalse(self.sup.complete_quiesce())

    def test_qb16_foreign_lease_same_worker_id_untouched(self):
        other = self.make_supervisor()
        job_id = self.add_job(other)
        other.claim("same", ["reviewer"])
        before = self.load(job_id)
        self.sup.request_quiesce()
        self.assertEqual(before, self.load(job_id))

    def test_legacy_claim_without_owner_is_not_cleared_or_declared_drained(self):
        job_id = self.add_job()
        self.claim()
        with self.sup.store.mutate(job_id) as job:
            job["worker"].pop("owner_id")
            job["worker"].pop("claim_ticket")
        before = self.load(job_id)
        self.sup.request_quiesce()
        self.assertFalse(self.sup.complete_quiesce())
        self.assertEqual(before, self.load(job_id))

    def test_worker_pool_start_rejected_after_gate_closed(self):
        from sedra_runtime.desk.orchestra_runner import WorkerPool
        self.sup.request_quiesce()
        pool = WorkerPool.__new__(WorkerPool)
        pool.workers = [self.run_worker()]
        pool.threads = []
        pool._stop_requested = False
        pool.orch = None
        with self.assertRaisesRegex(RuntimeError, "worker_pool_stopping"):
            pool.start()
        self.assertEqual(pool.threads, [])

    def test_qb17_mutating_or_unknown_attempt_is_not_replayed(self):
        job_id = self.add_job()
        self.claim(); self.sup.confirm_start(job_id, "same")
        before = self.load(job_id)
        self.sup.request_quiesce()
        self.assertEqual(self.load(job_id)["attempt_log"], before["attempt_log"])
        self.assertEqual(self.load(job_id)["attempts"], before["attempts"])

    def test_qb18_worker_loop_waits_without_crash(self):
        self.add_job();self.sup.request_quiesce()
        worker = self.run_worker()
        self.assertEqual(worker.run_forever(max_iterations=1), ["waiting"])

    def test_qb19_fast_cut_avoids_blocked_store_lock(self):
        self.add_job();self.sup.request_quiesce()
        @contextmanager
        def blocked():
            raise AssertionError("must_not_wait_on_store_after_quiesce")
            yield
        with mock.patch.object(self.sup.store, "_lock", blocked):
            self.assertEqual(self.claim()["code"], "quiesced")

    def test_qb20_no_commit_after_linearization_cut(self):
        self.add_job();self.sup.request_quiesce()
        for _ in range(10):
            self.assertEqual(self.claim()["status"], "waiting")
        self.assertFalse(any((j.get("worker") or {}).get("owner_id") == self.sup.quiesce_owner_id
                             for j in self.sup.store.scan()[0]))

    def test_qb21_slot_and_non_slot_start_share_cut(self):
        for with_slots in (False, True):
            with self.subTest(with_slots=with_slots):
                other = self.make_supervisor()
                if with_slots:
                    other.slots = FakeSlots()
                job_id = self.add_job(other)
                other.claim("same", ["reviewer"])
                other.request_quiesce()
                self.assertEqual(other.confirm_start(job_id, "same")["status"], "waiting")
                self.assertEqual(other.store.load(job_id)["attempts"], 0)

    def test_qb22_old_ticket_cannot_unclaim_new_claim(self):
        job_id = self.add_job()
        old = self.claim()["job"]["worker"]["claim_ticket"]
        self.sup._unclaim(job_id, "same", "old", expected_ticket=old)
        new = self.claim()["job"]["worker"]["claim_ticket"]
        self.assertNotEqual(new, old)
        out = self.sup._unclaim(job_id, "same", "late", expected_ticket=old)
        self.assertEqual(out["reason"], "ownership_uncertain")
        self.assertEqual(self.load(job_id)["worker"]["claim_ticket"], new)

    def test_qb23_neutral_audit_and_consumer_contract(self):
        self.add_job();self.sup.request_quiesce()
        a = self.run_worker().run_once()
        b = self.sup.run_next("same", ["reviewer"], lambda *_: None)
        self.assertEqual(a["status"], b["status"])
        events = [json.loads(line) for line in (self.root / "audit.jsonl").read_text().splitlines() if line]
        self.assertIn("JOB_CLAIM_DEFERRED", [e["event_type"] for e in events])

    def test_unstarted_resource_reservation_released_on_cut(self):
        class Reserved:
            def __init__(self): self.released = []
            def release_job(self, job_id): self.released.append(job_id)
        job_id = self.add_job()
        claim = self.claim()
        scheduler = Reserved()
        self.sup.scheduler = scheduler
        self.assertTrue(self.sup.request_quiesce())
        out = self.sup._start_attempt(job_id, "same", self.sup._now(), "ATT-PENDING", None, None,
                                      {"reservation_id": "owned-by-this-attempt"},
                                      expected_ticket=claim["job"]["worker"]["claim_ticket"])
        self.assertEqual(out["status"], "waiting")
        self.assertEqual(scheduler.released, [job_id])
        self.assertEqual(self.load(job_id)["attempts"], 0)

    def test_qb24_late_lock_error_is_not_neutral(self):
        self.add_job()
        original = self.sup.store.mutate
        @contextmanager
        def late_error(job_id):
            with original(job_id) as record:
                yield record
            raise RuntimeError("append_lock_timeout")
        with mock.patch.object(self.sup.store, "mutate", late_error):
            with self.assertRaises(JobError) as err:
                self.claim()
        self.assertEqual(err.exception.code, "claim_outcome_unknown")
        self.assertEqual(self.sup.quiesce_state, "SHUTDOWN_PENDING")
        self.assertIsNotNone(self.load(self.sup.store.scan()[0][0]["job_id"])["worker"])


if __name__ == "__main__":
    unittest.main()
