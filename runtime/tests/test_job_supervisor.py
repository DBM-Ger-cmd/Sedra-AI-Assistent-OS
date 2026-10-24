"""Phase 2: minimal job supervisor. Mechanics only: fake clock, fake worker, no model, no hardware."""
import importlib
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from guppi_runtime.core.audit import AuditLog
from guppi_runtime.selfdev.development_contracts import development_contract
from guppi_runtime.core.guard import Guard
from guppi_runtime.jobs.job_supervisor import (JobError, JobSupervisor, SupervisorConfig, SupervisorJobStore, supervisor_state)
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.selfdev.self_development import DevelopmentJobStore
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
CONFIG = RUNTIME / 'config' / 'job_supervisor.yaml'
ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
SRC = str(RUNTIME / 'src')


class Clock:
    def __init__(self):
        self.wall = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        self.mono = 1000.0

    def now(self): return self.wall
    def monotonic(self): return self.mono

    def advance(self, seconds, *, wall=True, mono=True):
        if wall: self.wall += timedelta(seconds=seconds)
        if mono: self.mono += seconds


def raw_config(**overrides):
    raw = yaml.safe_load(CONFIG.read_text(encoding='utf-8'))['job_supervisor']
    raw['enabled'] = True
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(raw.get(key), dict):
            raw[key].update(value)
        else:
            raw[key] = value
    return raw


class Base(unittest.TestCase):
    config_overrides = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.clock = Clock()
        self.audit = AuditLog(self.root / 'audit.jsonl')
        self.alive = {}
        self.sup = self.make_supervisor()

    def make_supervisor(self, **extra):
        config = SupervisorConfig(raw_config(**self.config_overrides))
        store = SupervisorJobStore(self.root / 'jobs', self.audit)
        args = dict(audit=self.audit, clock=self.clock.now, monotonic=self.clock.monotonic,
                    health_check=lambda w: self.alive.get(w, False), pass_gate=lambda job, v: [])
        args.update(extra)
        return JobSupervisor(store, config, **args)

    def contract(self, **kw):
        kw.setdefault('acceptance_criteria', [{'type': 'capability_smoke_test', 'id': 'smoke'}])
        kw.setdefault('verification_plan', [{'type': 'deterministic_tests'}])
        return development_contract(objective='probe', classification='E1', **kw)

    def job(self, role='reviewer', **kw):
        return self.sup.create_job(self.contract(), requested_role=role, **kw)

    def running(self, role='reviewer', worker='w1', **kw):
        job = self.job(role, **kw)
        self.sup.enqueue(job['job_id'])
        self.sup.claim(worker, [role])
        self.sup.confirm_start(job['job_id'], worker)
        return job['job_id']

    def load(self, job_id): return self.sup.store.load(job_id)
    def events(self): return [json.loads(x) for x in (self.root / 'audit.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    def event_types(self): return [e['event_type'] for e in self.events()]


class ConfigTests(unittest.TestCase):
    def test_shipped_config_is_valid_and_off_by_default(self):
        config = SupervisorConfig.load(CONFIG)
        self.assertFalse(config.enabled)
        self.assertEqual(config.workers, 1)
        self.assertTrue(config.roles['coder']['mutates'])
        self.assertFalse(config.roles['reviewer']['mutates'])
        self.assertEqual(len(config.roles), 12)     # Spec 1 S1.H8: dazu foreman

    def test_invalid_values_refuse_start(self):
        bad = [dict(workers=0), dict(workers=9), dict(workers='2'), dict(lease_s=1000, max_lease_s=900), dict(lease_s=30, heartbeat_interval_s=20),
               dict(retry={'limit': 11}), dict(retry={'limit': -1}), dict(roles={}), dict(roles={'x': {'mutates': 'yes', 'capability': 'c'}}),
               dict(claim_timeout_s=0), dict(enabled='yes'), dict(dependency_satisfied_states=['NOPE'])]
        for overrides in bad:
            raw = raw_config()
            for k, v in overrides.items():
                raw[k] = v if (k == 'roles' or not isinstance(v, dict)) else {**raw.get(k, {}), **v}
            with self.assertRaises(ValueError, msg=str(overrides)):
                SupervisorConfig(raw)

    def test_missing_file_is_reported(self):
        with self.assertRaises(ValueError):
            SupervisorConfig.load(Path(tempfile.gettempdir()) / 'no_such_job_supervisor.yaml')

    def test_disabled_supervisor_refuses_every_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = raw_config(); raw['enabled'] = False
            sup = JobSupervisor(SupervisorJobStore(Path(tmp) / 'jobs'), SupervisorConfig(raw))
            for call in (lambda: sup.create_job({}, requested_role='coder'), lambda: sup.claim('w', ['coder']),
                         lambda: sup.reap(), lambda: sup.startup_recovery(), lambda: sup.cancel('SDJ-AAAAAAAAAAAA', requested_by='x', reason='y')):
                with self.assertRaises(JobError) as ctx: call()
                self.assertEqual(ctx.exception.code, 'supervisor_disabled')

    def test_runtime_wires_the_supervisor_disabled_and_reports_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            self.assertIsNotNone(rt.job_supervisor)
            self.assertFalse(rt.job_supervisor.enabled)
            status = rt.boot()['job_supervisor']
            self.assertFalse(status['enabled'])
            self.assertEqual(rt.job_supervisor.view()['counts'], {})

    def test_v120_store_rules_are_untouched(self):
        self.assertNotIn('QUEUED', DevelopmentJobStore.ALLOWED['READY'])
        self.assertNotIn('DEAD', DevelopmentJobStore.ALLOWED)
        self.assertNotIn('CANCELLED', DevelopmentJobStore.ALLOWED)
        self.assertIn('QUEUED', SupervisorJobStore.ALLOWED['READY'])
        for final in ('DEAD', 'CANCELLED', 'REJECTED', 'ROLLED_BACK'):
            self.assertEqual(SupervisorJobStore.ALLOWED[final], set(), final)


class LifecycleTests(Base):
    def test_happy_path_and_derived_states(self):
        job = self.job()
        self.assertEqual(supervisor_state(job), 'READY')
        self.sup.enqueue(job['job_id'])
        self.assertEqual(supervisor_state(self.load(job['job_id'])), 'QUEUED')
        claimed = self.sup.claim('w1', ['reviewer'])['job']
        self.assertEqual(supervisor_state(claimed), 'CLAIMED')
        self.sup.confirm_start(job['job_id'], 'w1')
        self.assertEqual(supervisor_state(self.load(job['job_id'])), 'RUNNING')
        self.sup.complete_step(job['job_id'], 'w1', 'TESTING')
        self.sup.complete_step(job['job_id'], 'w1', 'VERIFYING')
        self.assertEqual(supervisor_state(self.load(job['job_id'])), 'VERIFYING')
        done = self.sup.mark_passed(job['job_id'], 'w1', {'result': 'PASS', 'verification_digest': 'd' * 64})
        self.assertEqual(supervisor_state(done['job']), 'PASSED')
        self.assertIsNone(done['job']['worker'])
        self.assertEqual(done['job']['attempt_log'][0]['outcome'], 'SUCCEEDED')

    def test_unknown_stored_state_is_left_alone(self):
        job = self.job()
        job['state'] = 'FROM_THE_FUTURE'
        self.assertEqual(supervisor_state(job), 'UNKNOWN')

    def test_passed_is_not_reachable_through_complete_step(self):
        job_id = self.running()
        for target in ('READY_FOR_ACCEPTANCE', 'ACTIVATED', 'COMPLETED', 'BUILDING'):
            with self.assertRaises(JobError) as ctx: self.sup.complete_step(job_id, 'w1', target)
            self.assertEqual(ctx.exception.code, 'invalid_transition')

    def test_mark_passed_needs_gate_pass_and_verification(self):
        job_id = self.running()
        self.sup.complete_step(job_id, 'w1', 'TESTING'); self.sup.complete_step(job_id, 'w1', 'VERIFYING')
        with self.assertRaises(JobError) as ctx: self.sup.mark_passed(job_id, 'w1', {'result': 'FAIL', 'verification_digest': 'd' * 64})
        self.assertEqual(ctx.exception.code, 'passing_verification_required')
        with self.assertRaises(JobError) as ctx: self.sup.mark_passed(job_id, 'w1', {'result': 'PASS'})
        self.assertEqual(ctx.exception.code, 'passing_verification_required')
        self.sup.pass_gate = lambda job, v: ['deterministic_test_evidence_required']
        with self.assertRaises(JobError) as ctx: self.sup.mark_passed(job_id, 'w1', {'result': 'PASS', 'verification_digest': 'd' * 64})
        self.assertEqual(ctx.exception.code, 'verification_gate_failed')
        self.assertEqual(self.load(job_id)['state'], 'VERIFYING')
        self.sup.pass_gate = None
        with self.assertRaises(JobError) as ctx: self.sup.mark_passed(job_id, 'w1', {'result': 'PASS', 'verification_digest': 'd' * 64})
        self.assertEqual(ctx.exception.code, 'verification_gate_unavailable')

    def test_create_job_validation(self):
        with self.assertRaises(JobError) as ctx: self.sup.create_job(self.contract(), requested_role='wizard')
        self.assertEqual(ctx.exception.code, 'unknown_role')
        with self.assertRaises(JobError) as ctx: self.sup.create_job(self.contract(), requested_role='coder', priority=10)
        self.assertEqual(ctx.exception.code, 'invalid_priority')
        with self.assertRaises(JobError) as ctx: self.sup.create_job(self.contract(permission_level=2), requested_role='coder', permission_level=3)
        self.assertEqual(ctx.exception.code, 'invalid_permission_level')
        with self.assertRaises(JobError) as ctx: self.sup.create_job({'contract_digest': 'x'}, requested_role='coder')
        self.assertEqual(ctx.exception.code, 'invalid_contract')
        tampered = self.contract(); tampered['objective'] = 'something else'
        with self.assertRaises(JobError) as ctx: self.sup.create_job(tampered, requested_role='coder')
        self.assertEqual(ctx.exception.code, 'invalid_contract')
        with self.assertRaises(JobError) as ctx: self.sup.create_job(self.contract(), requested_role='coder', parent_job_id='SDJ-AAAAAAAAAAAA')
        self.assertEqual(ctx.exception.code, 'unknown_parent')
        with self.assertRaises(JobError) as ctx: self.sup.create_job(self.contract(), requested_role='coder', depends_on=['nonsense'])
        self.assertEqual(ctx.exception.code, 'unknown_dependency')

    def test_permission_level_can_only_be_lowered_from_contract(self):
        job = self.sup.create_job(self.contract(permission_level=3), requested_role='coder', permission_level=1)
        self.assertEqual(job['permission_level'], 1)

    def test_enqueue_requires_ready(self):
        job = self.sup.create_job(self.contract(), requested_role='coder', ready=False)
        with self.assertRaises(JobError) as ctx: self.sup.enqueue(job['job_id'])
        self.assertEqual(ctx.exception.code, 'not_ready')

    def test_enqueue_is_idempotent_per_operation_id(self):
        job = self.job()
        first = self.sup.enqueue(job['job_id'], operation_id='op-1')
        rev = self.load(job['job_id'])['rev']
        again = self.sup.enqueue(job['job_id'], operation_id='op-1')
        self.assertEqual((first['status'], again['status']), ('queued', 'duplicate'))
        self.assertEqual(self.load(job['job_id'])['rev'], rev)
        self.assertEqual(self.event_types().count('JOB_ENQUEUED'), 1)
        with self.assertRaises(JobError): self.sup.enqueue(job['job_id'], operation_id='bad id with spaces')

    def test_final_states_have_no_exit(self):
        job_id = self.job()['job_id']
        self.sup.cancel(job_id, requested_by='t', reason='r')
        with self.assertRaises(JobError) as ctx: self.sup.cancel(job_id, requested_by='t', reason='r')
        self.assertEqual(ctx.exception.code, 'already_final')
        with self.assertRaises(JobError): self.sup.enqueue(job_id)

    def test_v120_job_record_without_supervisor_fields_is_not_enqueued(self):
        sd = DevelopmentJobStore(self.root / 'jobs')
        record = {'schema': 1, 'job_id': 'SDJ-0123456789AB', 'created_at': 'x', 'state': 'READY', 'contract': {}, 'attempts': 0}
        (self.root / 'jobs' / 'SDJ-0123456789AB.json').write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaises(JobError) as ctx: self.sup.enqueue('SDJ-0123456789AB')
        self.assertEqual(ctx.exception.code, 'not_a_supervisor_job')
        self.assertEqual(self.sup.view()['counts'].get('READY'), 1)


class QueueTests(Base):
    def test_priority_then_age_then_id(self):
        low, high, later_high = self.job(priority=1), self.job(priority=9), None
        for job in (low, high): self.sup.enqueue(job['job_id'])
        self.clock.advance(5)
        later_high = self.job(priority=9); self.sup.enqueue(later_high['job_id'])
        order = []
        for _ in range(3):
            claimed = self.sup.claim('w1', ['reviewer'])['job']['job_id']; order.append(claimed)
            self.sup.confirm_start(claimed, 'w1'); self.sup.cancel(claimed, requested_by='t', reason='next'); self.sup.acknowledge_cancel(claimed, 'w1')
        self.assertEqual(order, [high['job_id'], later_high['job_id'], low['job_id']])

    def test_role_filter_and_empty_queue(self):
        self.sup.enqueue(self.job('coder')['job_id'])
        with self.assertRaises(JobError) as ctx: self.sup.claim('w1', ['reviewer'])
        self.assertEqual(ctx.exception.code, 'no_job')
        self.assertEqual(self.sup.claim('w1', ['reviewer', 'coder'])['status'], 'claimed')
        with self.assertRaises(JobError) as ctx: self.sup.claim('w1', ['nobody'])
        self.assertEqual(ctx.exception.code, 'invalid_roles')
        with self.assertRaises(JobError) as ctx: self.sup.claim('bad worker!', ['coder'])
        self.assertEqual(ctx.exception.code, 'invalid_worker_id')

    def test_only_one_worker_at_a_time(self):
        for _ in range(2): self.sup.enqueue(self.job()['job_id'])
        self.sup.claim('w1', ['reviewer'])
        with self.assertRaises(JobError) as ctx: self.sup.claim('w2', ['reviewer'])
        self.assertEqual(ctx.exception.code, 'worker_busy')

    def test_not_before_is_respected(self):
        job = self.job()
        self.sup.enqueue(job['job_id'], not_before=self.clock.now() + timedelta(seconds=60))
        with self.assertRaises(JobError) as ctx: self.sup.claim('w1', ['reviewer'])
        self.assertEqual(ctx.exception.code, 'no_job')
        self.clock.advance(61)
        self.assertEqual(self.sup.claim('w1', ['reviewer'])['job']['job_id'], job['job_id'])

    def test_dependencies_gate_enqueue_and_claim(self):
        parent = self.job()
        child = self.job(depends_on=[parent['job_id']])
        with self.assertRaises(JobError) as ctx: self.sup.enqueue(child['job_id'])
        self.assertEqual(ctx.exception.code, 'dependency_unmet')
        self.sup.enqueue(parent['job_id']); self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(parent['job_id'], 'w1')
        self.sup.complete_step(parent['job_id'], 'w1', 'TESTING'); self.sup.complete_step(parent['job_id'], 'w1', 'VERIFYING')
        self.sup.mark_passed(parent['job_id'], 'w1', {'result': 'PASS', 'verification_digest': 'd' * 64})
        self.assertEqual(self.sup.enqueue(child['job_id'])['status'], 'queued')

    def test_cancelled_dependency_never_satisfies(self):
        parent = self.job(); self.sup.cancel(parent['job_id'], requested_by='t', reason='r')
        child = self.job(depends_on=[parent['job_id']])
        with self.assertRaises(JobError) as ctx: self.sup.enqueue(child['job_id'])
        self.assertEqual(ctx.exception.code, 'dependency_unmet')

    def test_parent_job_is_recorded(self):
        parent = self.job()
        self.assertEqual(self.job(parent_job_id=parent['job_id'])['parent_job_id'], parent['job_id'])

    def test_claim_is_atomic_across_threads(self):
        self.sup.enqueue(self.job()['job_id'])
        results = []

        def go(n):
            try: results.append(self.sup.claim(f'w{n}', ['reviewer'])['status'])
            except JobError as exc: results.append(exc.code)

        threads = [threading.Thread(target=go, args=(n,)) for n in range(6)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(results.count('claimed'), 1)
        self.assertEqual(len([r for r in results if r in {'worker_busy', 'no_job'}]), 5)

    def test_claim_is_atomic_across_processes(self):
        self.sup.enqueue(self.job()['job_id'])
        code = ("import sys, yaml\nsys.path.insert(0, sys.argv[1])\nfrom pathlib import Path\n"
                "from guppi_runtime.jobs.job_supervisor import *\n"
                "raw = yaml.safe_load(Path(sys.argv[3]).read_text(encoding='utf-8'))['job_supervisor']; raw['enabled'] = True\n"
                "sup = JobSupervisor(SupervisorJobStore(Path(sys.argv[2]) / 'jobs'), SupervisorConfig(raw))\n"
                "try: print(sup.claim('wp' + sys.argv[4], ['reviewer'])['status'])\n"
                "except JobError as e: print(e.code)\n")
        procs = [subprocess.Popen([sys.executable, '-c', code, SRC, str(self.root), str(CONFIG), str(n)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for n in range(4)]
        outs = []
        for p in procs:
            out, err = p.communicate(timeout=120); self.assertEqual(p.returncode, 0, err); outs.append(out.strip())
        self.assertEqual(outs.count('claimed'), 1, outs)


class HeartbeatTests(Base):
    def test_heartbeat_and_progress_are_separate_and_monotonic(self):
        job_id = self.running()
        before = self.load(job_id)
        for _ in range(3): self.sup.heartbeat(job_id, 'w1')
        mid = self.load(job_id)
        self.assertEqual(mid['heartbeat_seq'], before['heartbeat_seq'] + 3)
        self.assertEqual(mid['progress_seq'], before['progress_seq'])
        self.assertEqual(self.sup.report_progress(job_id, 'w1', 'step-a')['status'], 'progress')
        self.assertEqual(self.sup.report_progress(job_id, 'w1', 'step-a')['status'], 'no_change')
        self.assertEqual(self.sup.report_progress(job_id, 'w1', 'step-b')['status'], 'progress')
        self.assertEqual(self.load(job_id)['progress_seq'], before['progress_seq'] + 2)

    def test_foreign_worker_has_no_lease(self):
        job_id = self.running()
        for call in (lambda: self.sup.heartbeat(job_id, 'intruder'), lambda: self.sup.report_progress(job_id, 'intruder', 'x'),
                     lambda: self.sup.complete_step(job_id, 'intruder', 'TESTING'), lambda: self.sup.fail(job_id, 'intruder', message='x')):
            with self.assertRaises(JobError) as ctx: call()
            self.assertEqual(ctx.exception.code, 'lease_lost')

    def test_lease_extension_is_capped(self):
        job_id = self.running()
        self.sup.heartbeat(job_id, 'w1', lease_extend_s=10 ** 6)
        lease = datetime.fromisoformat(self.load(job_id)['worker']['lease_until'])
        self.assertLessEqual((lease - self.clock.now()).total_seconds(), self.sup.config.max_lease_s)
        with self.assertRaises(JobError): self.sup.heartbeat(job_id, 'w1', lease_extend_s=0)

    def test_heartbeats_are_not_audited(self):
        job_id = self.running()
        count = len(self.events())
        for _ in range(10): self.sup.heartbeat(job_id, 'w1')
        self.sup.report_progress(job_id, 'w1', 'x')
        self.assertEqual(len(self.events()), count)

    def test_claim_without_start_expires(self):
        job = self.job(); self.sup.enqueue(job['job_id']); self.sup.claim('w1', ['reviewer'])
        self.clock.advance(self.sup.config.claim_timeout_s + 1)
        events = self.sup.reap()
        self.assertIn('JOB_CLAIM_EXPIRED', [e['event'] for e in events])
        stored = self.load(job['job_id'])
        self.assertIsNone(stored['worker']); self.assertEqual(stored['state'], 'QUEUED')
        with self.assertRaises(JobError) as ctx: self.sup.confirm_start(job['job_id'], 'w1')
        self.assertEqual(ctx.exception.code, 'not_claimed')

    def test_late_confirm_start_is_refused(self):
        job = self.job(); self.sup.enqueue(job['job_id']); self.sup.claim('w1', ['reviewer'])
        self.clock.advance(self.sup.config.claim_timeout_s + 1)
        with self.assertRaises(JobError) as ctx: self.sup.confirm_start(job['job_id'], 'w1')
        self.assertEqual(ctx.exception.code, 'claim_expired')


class ReaperTests(Base):
    def expire(self, job_id, *, seconds=None):
        seconds = seconds or (self.sup.config.lease_s + self.sup.config.suspect_after_s + 1)
        self.clock.advance(seconds)

    def test_live_worker_is_never_reaped(self):
        job_id = self.running()
        for _ in range(20):
            self.clock.advance(self.sup.config.heartbeat_interval_s)
            self.sup.heartbeat(job_id, 'w1'); self.sup.report_progress(job_id, 'w1', f'm{self.clock.mono}')
            self.assertEqual(self.sup.reap(), [])
        self.assertEqual(self.load(job_id)['state'], 'BUILDING')

    def test_expired_lease_goes_suspect_then_grace_then_abandon_for_readonly_job(self):
        job_id = self.running('reviewer')
        self.sup.reap()                       # first observation
        self.expire(job_id)
        first = self.sup.reap()
        self.assertEqual([e['event'] for e in first], ['JOB_LEASE_SUSPECT'])
        self.assertEqual(self.load(job_id)['state'], 'BUILDING')   # grace period still running
        self.clock.advance(self.sup.config.grace_s + 1)
        second = self.sup.reap()
        self.assertEqual([e['event'] for e in second], ['JOB_ABANDONED'])
        stored = self.load(job_id)
        self.assertEqual((stored['state'], stored['attempt_log'][0]['outcome']), ('QUEUED', 'ABANDONED'))
        self.assertIsNone(stored['worker'])
        types = self.event_types()
        for needed in ('JOB_LEASE_SUSPECT', 'JOB_LEASE_EXPIRED', 'JOB_ABANDONED'):
            self.assertIn(needed, types)

    def test_alive_worker_gets_grace_instead_of_abandon(self):
        job_id = self.running('reviewer'); self.alive['w1'] = True
        self.sup.reap(); self.expire(job_id)
        events = self.sup.reap()
        self.assertEqual([e['event'] for e in events], ['JOB_LEASE_GRACE'])
        self.assertEqual(self.load(job_id)['state'], 'BUILDING')
        self.assertIn('JOB_LEASE_GRACE', self.event_types())

    def test_mutating_job_with_lost_worker_is_dead_and_escalated_never_replayed(self):
        job_id = self.running('coder')
        self.sup.reap(); self.expire(job_id); self.sup.reap(); self.clock.advance(self.sup.config.grace_s + 1)
        self.sup.reap()
        stored = self.load(job_id)
        self.assertEqual((stored['state'], supervisor_state(stored)), ('DEAD', 'DEAD'))
        self.assertEqual(stored['attempt_log'][0]['outcome'], 'UNKNOWN')
        self.assertEqual(stored['supervisor_flags']['escalated_to'], 'guppi')
        with self.assertRaises(JobError): self.sup.enqueue(job_id)
        with self.assertRaises(JobError) as ctx: self.sup.claim('w2', ['coder'])
        self.assertEqual(ctx.exception.code, 'no_job')

    def test_critical_readonly_job_is_escalated_not_silently_replayed(self):
        job_id = self.running('reviewer', priority=9)
        self.sup.reap(); self.expire(job_id); self.sup.reap(); self.clock.advance(self.sup.config.grace_s + 1); self.sup.reap()
        stored = self.load(job_id)
        self.assertEqual((stored['state'], stored['supervisor_flags']['escalated_to']), ('BLOCKED', 'guppi'))

    def test_wall_clock_jump_forward_does_not_kill_a_live_worker(self):
        job_id = self.running('reviewer')
        self.sup.reap()
        self.clock.advance(86400, mono=False)           # clock jumps one day, real time barely moves
        self.sup.heartbeat(job_id, 'w1')                # worker is alive
        self.assertEqual(self.sup.reap(), [])
        self.assertEqual(self.load(job_id)['state'], 'BUILDING')

    def test_wall_clock_jump_without_heartbeats_still_needs_stale_observation(self):
        job_id = self.running('reviewer')
        self.sup.reap()
        self.clock.advance(86400, mono=False)           # lease looks expired, but no real time passed
        self.assertEqual(self.sup.reap(), [])
        self.assertEqual(self.load(job_id)['state'], 'BUILDING')

    def test_wall_clock_jump_backward_does_not_extend_forever(self):
        job_id = self.running('reviewer')
        self.sup.reap()
        self.clock.advance(-3600, mono=False)
        self.clock.advance(self.sup.config.lease_s + self.sup.config.suspect_after_s + 3700, wall=True, mono=False)
        self.clock.advance(self.sup.config.suspect_after_s + 1, wall=False)   # monotonic time passes, no heartbeat
        events = self.sup.reap()
        self.assertEqual([e['event'] for e in events], ['JOB_LEASE_SUSPECT'])

    def test_stall_readonly_job_asks_for_new_context_instead_of_retrying(self):
        job_id = self.running('reviewer')
        self.sup.reap()
        for _ in range(int(self.sup.config.stall_after_s / self.sup.config.heartbeat_interval_s) + 2):
            self.clock.advance(self.sup.config.heartbeat_interval_s); self.sup.heartbeat(job_id, 'w1')
        events = self.sup.reap()
        self.assertEqual([e['event'] for e in events], ['JOB_STALLED'])
        stored = self.load(job_id)
        self.assertEqual(stored['state'], 'REWORK')
        self.assertEqual(stored['retry']['awaiting_change'], 'context_manifest')
        self.assertEqual(stored['last_error']['class'], 'context_quality_degraded')
        with self.assertRaises(JobError) as ctx: self.sup.enqueue(job_id)
        self.assertEqual(ctx.exception.code, 'change_required')

    def test_progress_resets_the_stall_timer(self):
        job_id = self.running('reviewer')
        self.sup.reap()
        for i in range(int(self.sup.config.stall_after_s / self.sup.config.heartbeat_interval_s) * 3):
            self.clock.advance(self.sup.config.heartbeat_interval_s); self.sup.heartbeat(job_id, 'w1')
            if i % 5 == 0: self.sup.report_progress(job_id, 'w1', f'step-{i}')
            self.assertEqual(self.sup.reap(), [])

    def test_stall_of_mutating_job_ends_dead(self):
        job_id = self.running('coder')
        self.sup.reap()
        for _ in range(int(self.sup.config.stall_after_s / self.sup.config.heartbeat_interval_s) + 2):
            self.clock.advance(self.sup.config.heartbeat_interval_s); self.sup.heartbeat(job_id, 'w1')
        self.sup.reap()
        self.assertEqual(self.load(job_id)['state'], 'DEAD')


class RetryTests(Base):
    def fail_once(self, role='reviewer', **kw):
        job_id = self.running(role)
        out = self.sup.fail(job_id, 'w1', **kw)
        return job_id, out

    def test_every_class_follows_its_rule(self):
        table = [
            (dict(reason_code='TOOL_UNAVAILABLE'), 'transient_provider_error', 'QUEUED', None),
            (dict(exception=TimeoutError()), 'timeout', 'QUEUED', None),
            (dict(message='http 429 too many requests'), 'rate_limit', 'QUEUED', None),
            (dict(message='worker process crashed'), 'runtime_crash', 'QUEUED', None),
            (dict(reason_code='PROVIDER_UNAVAILABLE'), 'model_unavailable', 'QUEUED', None),
            (dict(reason_code='JOB_LIMIT'), 'hardware_pressure', 'QUEUED', None),
            (dict(reason_code='CONTEXT_CAPACITY_UNQUALIFIED'), 'context_overflow', 'REWORK', 'context_manifest'),
            (dict(message='context quality degraded'), 'context_quality_degraded', 'REWORK', 'context_manifest'),
            (dict(reason_code='NO_HANDLER'), 'validation_failure', 'REWORK', 'input'),
            (dict(message='3 tests failed'), 'deterministic_test_failure', 'REWORK', 'candidate_hash'),
            (dict(reason_code='missing_permission'), 'policy_denied', 'BLOCKED', None),
            (dict(message='something odd'), 'unknown_failure', 'BLOCKED', None),
        ]
        for kwargs, klass, state, awaiting in table:
            with self.subTest(klass=klass):
                self.setUp()
                job_id, out = self.fail_once(**kwargs)
                stored = self.load(job_id)
                self.assertEqual(out['failure_class'], klass)
                self.assertEqual(stored['state'], state)
                self.assertEqual(stored['retry']['awaiting_change'], awaiting)
                self.assertEqual(stored['attempt_log'][0]['outcome'], 'FAILED')
                self.assertEqual(stored['attempt_log'][0]['failure_class'], klass)
                self.assertIsNone(stored['worker'])

    def test_retry_waits_for_backoff(self):
        job_id, _ = self.fail_once(reason_code='TOOL_UNAVAILABLE')
        stored = self.load(job_id)
        wait = (datetime.fromisoformat(stored['queue']['not_before']) - self.clock.now()).total_seconds()
        self.assertTrue(0.8 * 2 <= wait <= 1.2 * 2 + 0.01, wait)
        with self.assertRaises(JobError) as ctx: self.sup.claim('w1', ['reviewer'])
        self.assertEqual(ctx.exception.code, 'no_job')
        self.clock.advance(3)
        self.assertEqual(self.sup.claim('w1', ['reviewer'])['job']['job_id'], job_id)

    def test_backoff_grows_and_is_capped(self):
        waits = []
        job_id = self.running()
        for _ in range(3):
            self.sup.fail(job_id, 'w1', reason_code='TOOL_UNAVAILABLE')
            stored = self.load(job_id)
            waits.append((datetime.fromisoformat(stored['queue']['not_before']) - self.clock.now()).total_seconds())
            self.clock.advance(300)
            self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        self.assertLess(waits[0], waits[1]); self.assertLess(waits[1], waits[2])
        self.assertLessEqual(max(waits), self.sup.config.backoff_max_s * 1.2 + 0.01)

    def test_retry_limit_ends_in_escalation(self):
        job_id = self.running()
        for attempt in range(self.sup.config.retry_limit):
            self.sup.fail(job_id, 'w1', reason_code='TOOL_UNAVAILABLE')
            self.assertEqual(self.load(job_id)['state'], 'QUEUED', attempt)
            self.clock.advance(300); self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        out = self.sup.fail(job_id, 'w1', reason_code='TOOL_UNAVAILABLE')
        stored = self.load(job_id)
        self.assertEqual(out['decision']['reason'], 'retry_limit_reached')
        self.assertEqual((stored['state'], stored['supervisor_flags']['escalated_to']), ('BLOCKED', 'guppi'))
        self.assertEqual(len(stored['attempt_log']), self.sup.config.retry_limit + 1)

    def test_third_timeout_asks_for_fallback_and_excludes_the_provider(self):
        job_id = self.running()
        for n in range(3):
            with self.sup.store.mutate(job_id) as job: job['attempt_log'][-1]['provider_ref'] = 'opaque-provider-A'
            out = self.sup.fail(job_id, 'w1', exception=TimeoutError())
            if n < 2:
                self.assertEqual(out['decision']['action'], 'RETRY')
                self.clock.advance(300); self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        self.assertEqual(out['decision']['action'], 'FALLBACK')
        self.assertEqual(self.load(job_id)['retry']['exclude'], ['opaque-provider-A'])
        self.assertIn('JOB_FALLBACK_DECIDED', self.event_types())

    def test_policy_denied_never_falls_back_and_needs_the_captain(self):
        job_id, out = self.fail_once(reason_code='missing_permission')
        stored = self.load(job_id)
        self.assertEqual(out['decision']['action'], 'ESCALATE')
        self.assertEqual(stored['supervisor_flags']['escalated_to'], 'captain')
        self.assertEqual(supervisor_state(stored), 'ESCALATED_TO_CAPTAIN')
        self.assertEqual(stored['retry']['exclude'], [])
        for call in (lambda: self.sup.enqueue(job_id), lambda: self.sup.resume(job_id, resolved_by='guppi')):
            with self.assertRaises(JobError) as ctx: call()
            self.assertEqual(ctx.exception.code, 'captain_resolution_required')
        self.assertNotIn('JOB_FALLBACK_DECIDED', self.event_types())

    def test_text_that_mentions_policy_cannot_be_retried(self):
        job_id, out = self.fail_once(message='rate limit hit but policy forbids another provider')
        self.assertEqual(out['failure_class'], 'policy_denied')
        self.assertEqual(self.load(job_id)['state'], 'BLOCKED')

    def test_guppi_escalation_can_be_resumed(self):
        job_id, _ = self.fail_once(message='something odd')
        self.assertEqual(supervisor_state(self.load(job_id)), 'ESCALATED_TO_GUPPI')
        with self.assertRaises(JobError): self.sup.enqueue(job_id)   # escalation must be resolved first
        resumed = self.sup.resume(job_id, resolved_by='guppi')
        self.assertEqual(resumed['state'], 'QUEUED')
        self.assertIsNone(resumed['supervisor_flags']['escalated_to'])

    def test_identical_request_is_not_requeued_without_a_change(self):
        for kwargs, need, bad, good in [
            (dict(message='3 tests failed'), 'candidate_hash', dict(candidate_hash=None), dict(candidate_hash='b' * 64)),
            (dict(reason_code='CONTEXT_CAPACITY_UNQUALIFIED'), 'context_manifest', dict(context_manifest_id=None), dict(context_manifest_id='CTX-NEW')),
            (dict(reason_code='NO_HANDLER'), 'input', dict(input_digest=None), dict(input_digest='f' * 64)),
        ]:
            with self.subTest(need=need):
                self.setUp()
                job_id, _ = self.fail_once(**kwargs)
                with self.assertRaises(JobError) as ctx: self.sup.enqueue(job_id)
                self.assertEqual((ctx.exception.code, ctx.exception.detail), ('change_required', need))
                with self.assertRaises(JobError) as ctx: self.sup.supply_change(job_id, **bad)
                self.assertEqual(ctx.exception.code, 'change_not_different')
                self.sup.supply_change(job_id, **good)
                self.assertEqual(self.sup.enqueue(job_id)['status'], 'queued')
                with self.assertRaises(JobError) as ctx: self.sup.supply_change(job_id, **good)
                self.assertEqual(ctx.exception.code, 'no_change_awaited')

    def test_failed_tests_need_a_different_candidate_hash(self):
        job_id = self.running()
        with self.sup.store.mutate(job_id) as job: job['candidate'] = {'candidate_hash': 'a' * 64}
        self.sup.fail(job_id, 'w1', message='3 tests failed')
        with self.assertRaises(JobError): self.sup.supply_change(job_id, candidate_hash='a' * 64)
        self.sup.supply_change(job_id, candidate_hash='c' * 64)

    def test_unknown_outcome_of_a_mutating_attempt_is_dead(self):
        job_id = self.running('coder')
        out = self.sup.fail(job_id, 'w1', reason_code='TOOL_UNAVAILABLE', outcome_known=False)
        stored = self.load(job_id)
        self.assertEqual((out['decision']['action'], stored['state']), ('DEAD', 'DEAD'))
        self.assertEqual(stored['attempt_log'][0]['outcome'], 'UNKNOWN')

    def test_known_failure_of_a_mutating_role_is_still_retried(self):
        job_id = self.running('coder')
        self.sup.fail(job_id, 'w1', reason_code='TOOL_UNAVAILABLE')
        self.assertEqual(self.load(job_id)['state'], 'QUEUED')

    def test_retry_counter_matches_failed_attempts(self):
        job_id = self.running()
        for _ in range(2):
            self.sup.fail(job_id, 'w1', reason_code='TOOL_UNAVAILABLE')
            self.clock.advance(300); self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        stored = self.load(job_id)
        failed = [a for a in stored['attempt_log'] if a['outcome'] in {'FAILED', 'ABANDONED', 'UNKNOWN'}]
        self.assertEqual(stored['retry']['count'], len(failed))
        self.assertEqual(len([a for a in stored['attempt_log'] if a['outcome'] == 'RUNNING']), 1)


class CancelTests(Base):
    def test_cancel_before_start(self):
        for prepare in (lambda j: None, lambda j: self.sup.enqueue(j), lambda j: (self.sup.enqueue(j), self.sup.claim('w1', ['reviewer']))):
            with self.subTest():
                self.setUp(); job = self.job(); prepare(job['job_id'])
                out = self.sup.cancel(job['job_id'], requested_by='captain', reason='not needed')
                self.assertEqual(out['status'], 'cancelled')
                self.assertEqual(supervisor_state(out['job']), 'CANCELLED')
                self.assertIsNone(out['job']['worker'])

    def test_cancel_of_running_job_is_cooperative(self):
        job_id = self.running()
        out = self.sup.cancel(job_id, requested_by='captain', reason='stop')
        self.assertEqual(out['status'], 'cancel_requested')
        self.assertEqual(self.load(job_id)['state'], 'BUILDING')
        self.assertTrue(self.sup.heartbeat(job_id, 'w1')['cancel_requested'])
        done = self.sup.acknowledge_cancel(job_id, 'w1')
        self.assertEqual(done['job']['state'], 'CANCELLED')
        self.assertEqual(done['job']['attempt_log'][0]['outcome'], 'ABANDONED')
        self.assertTrue({'JOB_CANCEL_REQUESTED', 'JOB_CANCELLED'} <= set(self.event_types()))

    def test_cancelled_running_job_whose_worker_vanished_is_not_retried(self):
        job_id = self.running()
        self.sup.cancel(job_id, requested_by='captain', reason='stop')
        self.sup.reap(); self.clock.advance(self.sup.config.lease_s + self.sup.config.suspect_after_s + 1); self.sup.reap()
        self.clock.advance(self.sup.config.grace_s + 1); self.sup.reap()
        self.assertEqual(self.load(job_id)['state'], 'CANCELLED')

    def test_cancel_is_idempotent(self):
        job = self.job()
        self.sup.cancel(job['job_id'], requested_by='t', reason='r', operation_id='c-1')
        self.assertEqual(self.sup.cancel(job['job_id'], requested_by='t', reason='r', operation_id='c-1')['status'], 'duplicate')

    def test_cancelled_job_is_never_claimed(self):
        job = self.job(); self.sup.enqueue(job['job_id'])
        self.sup.cancel(job['job_id'], requested_by='t', reason='r')
        with self.assertRaises(JobError) as ctx: self.sup.claim('w1', ['reviewer'])
        self.assertEqual(ctx.exception.code, 'no_job')


class RecoveryTests(Base):
    def test_startup_recovery_cases(self):
        claimed = self.job(); self.sup.enqueue(claimed['job_id'])
        self.sup.claim('w1', ['reviewer'])                                     # claimed only
        self.sup.cancel(claimed['job_id'], requested_by='t', reason='r')      # cancelled while claimed -> already final
        sup2 = self.make_supervisor()
        # fresh jobs for the real cases (workers=1: finish them one by one)
        a = self.running('reviewer', worker='wa')
        sup2 = self.make_supervisor(); r1 = sup2.startup_recovery()
        self.assertEqual(r1['abandoned'], [a])
        self.assertEqual(self.load(a)['state'], 'QUEUED')
        b = self.running('coder', worker='wb')
        r2 = self.make_supervisor().startup_recovery()
        self.assertEqual(r2['dead'], [b])
        self.assertEqual(self.load(b)['state'], 'DEAD')
        c = self.job(); self.sup.enqueue(c['job_id']); self.sup.claim('wc', ['reviewer'])
        # job a is queued again and may have been claimed: release whatever is claimed
        r3 = self.make_supervisor().startup_recovery()
        self.assertTrue(r3['claims_released'])
        self.assertIsNone(self.load(c['job_id'])['worker'])

    def test_startup_recovery_finishes_a_pending_cancel(self):
        job_id = self.running()
        self.sup.cancel(job_id, requested_by='t', reason='r')              # worker never acknowledged
        report = self.make_supervisor().startup_recovery()
        self.assertEqual(report['cancel_finished'], [job_id])
        self.assertEqual(self.load(job_id)['state'], 'CANCELLED')

    def test_queue_retry_lease_and_counters_survive_a_restart(self):
        job_id = self.running()
        for _ in range(3): self.sup.heartbeat(job_id, 'w1')
        self.sup.fail(job_id, 'w1', reason_code='TOOL_UNAVAILABLE')
        before = self.load(job_id)
        restarted = self.make_supervisor()
        after = restarted.store.load(job_id)
        self.assertEqual((after['retry'], after['queue'], after['heartbeat_seq']), (before['retry'], before['queue'], before['heartbeat_seq']))
        self.clock.advance(300); restarted.claim('w1', ['reviewer']); restarted.confirm_start(job_id, 'w1')
        restarted.heartbeat(job_id, 'w1')
        self.assertGreater(restarted.store.load(job_id)['heartbeat_seq'], before['heartbeat_seq'])
        self.assertEqual(len(restarted.store.load(job_id)['attempt_log']), 2)

    def test_damaged_job_file_is_quarantined_and_never_overwritten(self):
        job = self.job()
        path = self.sup.store.path(job['job_id'])
        original = b'{"job_id": "SDJ-BROKEN", "state": '           # cut off mid-write
        path.write_bytes(original)
        report = self.make_supervisor().startup_recovery()
        self.assertEqual(len(report['corrupt']), 1)
        self.assertEqual(path.read_bytes(), original)               # untouched
        backups = list((self.root / 'jobs' / '_corrupt').glob('*.bak'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.make_supervisor().startup_recovery(); self.make_supervisor().reap()
        self.assertEqual(len(list((self.root / 'jobs' / '_corrupt').glob('*.bak'))), 1)   # no duplicates
        self.assertIn('JOB_CORRUPT_RECORD', self.event_types())
        self.assertEqual(self.sup.view()['corrupt_records'], 1)

    def test_only_three_backups_are_kept_per_file(self):
        job = self.job(); path = self.sup.store.path(job['job_id'])
        for n in range(5):
            path.write_bytes(b'{"broken": %d' % n)
            self.sup.store.scan()
        self.assertLessEqual(len(list((self.root / 'jobs' / '_corrupt').glob(f'{path.name}.*.bak'))), 3)

    def test_recover_needs_the_captain_and_never_replays_mutating_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            guard = rt.guard
            sup = self.make_supervisor(guard=guard)
            job_id = self.running('reviewer', worker='wr')            # via self.sup, same store
            sup.fail(job_id, 'wr', reason_code='TOOL_UNAVAILABLE', outcome_known=False, mutated=False)
            stored = sup.store.load(job_id)
            self.assertEqual(stored['state'], 'QUEUED')              # read-only + unknown outcome is retried
            # build a blocked job with an unknown outcome: critical read-only job lost its worker
            crit = self.running('reviewer', worker='wc', priority=9)
            sup.reap(); self.clock.advance(sup.config.lease_s + sup.config.suspect_after_s + 1); sup.reap()
            self.clock.advance(sup.config.grace_s + 1); sup.reap()
            self.assertEqual(sup.store.load(crit)['state'], 'BLOCKED')
            first = sup.recover(crit, 'abort')
            self.assertEqual(first['status'], 'captain_required')
            token = guard.approve(first['gate'])
            done = sup.recover(crit, 'abort', approval_token=token)
            self.assertEqual((done['status'], done['job']['state']), ('completed', 'CANCELLED'))
            with self.assertRaises(JobError): sup.recover(crit, 'abort', approval_token=token)       # no unknown outcome left to recover
            dead = self.running('coder', worker='wd')
            sup.fail(dead, 'wd', reason_code='TOOL_UNAVAILABLE', outcome_known=False)
            self.assertEqual(sup.store.load(dead)['state'], 'DEAD')
            with self.assertRaises(JobError) as ctx: sup.recover(dead, 'retry_readonly')
            self.assertEqual(ctx.exception.code, 'mutating_job_cannot_be_replayed')
            with self.assertRaises(JobError) as ctx: sup.recover(dead, 'rewrite_history')
            self.assertEqual(ctx.exception.code, 'unsupported_recovery_resolution')

    def test_recover_token_is_bound_to_the_job_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            sup = self.make_supervisor(guard=rt.guard)
            crit = self.running('reviewer', worker='wc', priority=9)
            sup.reap(); self.clock.advance(sup.config.lease_s + sup.config.suspect_after_s + 1); sup.reap()
            self.clock.advance(sup.config.grace_s + 1); sup.reap()
            gate = sup.recover(crit, 'abort')['gate']
            token = rt.guard.approve(gate)
            with sup.store.mutate(crit) as job: job['attempts'] += 1        # job changed after approval
            self.assertEqual(sup.recover(crit, 'abort', approval_token=token)['status'], 'captain_required')


class RunNextTests(Base):
    def test_idle_when_nothing_is_queued(self):
        self.assertEqual(self.sup.run_next('w1', ['reviewer'], lambda job, ctx: None)['status'], 'idle')

    def test_successful_handler_leaves_the_job_running_until_it_is_stepped_forward(self):
        job = self.job(); self.sup.enqueue(job['job_id'])
        seen = {}

        def handler(j, ctx):
            ctx.heartbeat(); ctx.progress('step-1'); seen['state'] = j['state']; return 'ok'

        out = self.sup.run_next('w1', ['reviewer'], handler)
        self.assertEqual((out['status'], out['result']), ('handled', 'ok'))
        self.assertEqual(seen['state'], 'BUILDING')
        self.assertEqual(self.load(job['job_id'])['progress_seq'], 2)

    def test_exception_is_classified_and_retried(self):
        job = self.job(); self.sup.enqueue(job['job_id'])
        out = self.sup.run_next('w1', ['reviewer'], lambda j, c: (_ for _ in ()).throw(TimeoutError('slow')))
        self.assertEqual((out['status'], out['failure_class']), ('failed', 'timeout'))
        self.assertEqual(self.load(job['job_id'])['state'], 'QUEUED')

    def test_unclassifiable_exception_escalates_instead_of_looping(self):
        job = self.job(); self.sup.enqueue(job['job_id'])
        out = self.sup.run_next('w1', ['reviewer'], lambda j, c: (_ for _ in ()).throw(RuntimeError('odd')))
        self.assertEqual(out['failure_class'], 'unknown_failure')
        self.assertEqual(self.load(job['job_id'])['state'], 'BLOCKED')

    def test_handler_that_changed_something_and_then_crashed_is_dead_when_outcome_unknown(self):
        job = self.job('coder'); self.sup.enqueue(job['job_id'])

        def handler(j, ctx):
            ctx.mark_mutated(); raise MemoryError()

        out = self.sup.run_next('w1', ['coder'], handler)
        self.assertEqual(out['failure_class'], 'hardware_pressure')
        self.assertEqual(self.load(job['job_id'])['state'], 'QUEUED')   # failure is known, so a retry is fine

    def test_cancel_during_handler_is_acknowledged(self):
        job = self.job(); self.sup.enqueue(job['job_id'])

        def handler(j, ctx):
            self.sup.cancel(j['job_id'], requested_by='captain', reason='stop'); ctx.heartbeat()

        out = self.sup.run_next('w1', ['reviewer'], handler)
        self.assertEqual(out['job']['state'], 'CANCELLED')


class AuditAndBoundaryTests(Base):
    def test_audit_chain_stays_valid_and_events_carry_the_required_fields(self):
        job_id = self.running('coder')
        self.sup.fail(job_id, 'w1', reason_code='TOOL_UNAVAILABLE')
        self.assertTrue(self.audit.verify_chain())
        failed = [e for e in self.events() if e['event_type'] == 'JOB_FAILED'][0]['payload']
        for key in ('job_id', 'rev', 'requested_role', 'permission_level', 'failure_class', 'reason_code', 'attempt_id'):
            self.assertIn(key, failed)
        self.assertEqual(failed['requested_role'], 'coder')

    def test_no_secrets_or_prompts_reach_the_audit(self):
        job_id = self.running()
        self.sup.fail(job_id, 'w1', message='api_key=SECRET123 prompt: write my diary', reason_code='TOOL_UNAVAILABLE')
        blob = (self.root / 'audit.jsonl').read_text(encoding='utf-8')
        self.assertNotIn('SECRET123', blob)
        self.assertNotIn('write my diary', blob)

    def test_supervisor_source_names_no_provider_or_model(self):
        source = Path(importlib.import_module('guppi_runtime.jobs.job_supervisor').__file__).read_text(encoding='utf-8').lower()
        for word in ('lm-studio', 'lmstudio', 'llama', 'qwen', 'kev', 'openai', 'anthropic', 'gpt'):
            self.assertNotRegex(source, rf'\b{re.escape(word)}\b', word)

    def test_view_reports_derived_states(self):
        self.job(); self.sup.enqueue(self.job()['job_id'])
        view = self.sup.view()
        self.assertEqual((view['counts']['READY'], view['counts']['QUEUED']), (1, 1))
        self.assertTrue(view['enabled'])

    def test_state_machine_has_no_exit_from_final_states_in_any_path(self):
        for final in ('DEAD', 'CANCELLED', 'REJECTED', 'ROLLED_BACK'):
            for target in SupervisorJobStore.ALLOWED:
                self.assertNotIn(target, SupervisorJobStore.ALLOWED[final])


class StalledReworkTests(Base):
    """Rework watch (plan 2026-10-04): the same failure again and again, or two failures alternating, go to the Captain."""
    config_overrides = {'retry': {'limit': 10}}          # the plain retry limit (3) must not end these jobs first
    SAME = 'FAIL: test_ports (m.C.test_ports)\nAssertionError: 1 != 2'
    OTHER = 'FAIL: test_dollar (m.C.test_dollar)\nAssertionError: ok != no'

    def again(self, job_id, n, message):
        self.sup.supply_change(job_id, candidate_hash=f'{n:064x}')
        self.sup.enqueue(job_id)
        self.sup.claim('w1', ['reviewer'])
        self.sup.confirm_start(job_id, 'w1')
        return self.sup.fail(job_id, 'w1', message=message)

    def stalled_job(self):
        job_id = self.running()
        self.sup.fail(job_id, 'w1', message=self.SAME)
        self.assertEqual(self.load(job_id)['state'], 'REWORK')
        self.again(job_id, 1, self.SAME)
        return job_id

    def test_the_same_failure_twice_goes_to_the_captain(self):
        job_id = self.stalled_job()
        stored = self.load(job_id)
        self.assertEqual((stored['state'], stored['supervisor_flags']['escalated_to']), ('BLOCKED', 'captain'))
        self.assertEqual(stored['last_error']['reason_code'], 'rework_stalled')
        self.assertEqual(supervisor_state(stored), 'ESCALATED_TO_CAPTAIN')
        types = self.event_types()
        self.assertIn('JOB_REWORK_STALLED', types)
        self.assertEqual(types.count('JOB_RETRY_SCHEDULED'), 1)          # only the first failure scheduled a retry
        stalled = [e for e in self.events() if e['event_type'] == 'JOB_REWORK_STALLED'][0]['payload']
        self.assertEqual((stalled['detector'], stalled['count']), ('generic_repeat', 3))
        with self.assertRaises(JobError) as ctx: self.sup.enqueue(job_id)
        self.assertEqual(ctx.exception.code, 'captain_resolution_required')

    def test_different_failures_do_not_stall(self):
        job_id = self.running()
        self.sup.fail(job_id, 'w1', message=self.SAME)
        self.again(job_id, 1, self.OTHER)
        self.assertEqual(self.load(job_id)['state'], 'REWORK')
        self.assertNotIn('JOB_REWORK_STALLED', self.event_types())

    def test_alternating_failures_stall_after_four(self):
        job_id = self.running()
        self.sup.fail(job_id, 'w1', message=self.SAME)
        for n, message in enumerate([self.OTHER, self.SAME], 1):
            self.again(job_id, n, message)
            self.assertEqual(self.load(job_id)['state'], 'REWORK')
        self.again(job_id, 3, self.OTHER)
        stored = self.load(job_id)
        self.assertEqual(stored['state'], 'BLOCKED')
        stalled = [e for e in self.events() if e['event_type'] == 'JOB_REWORK_STALLED'][0]['payload']
        self.assertEqual((stalled['detector'], stalled['count']), ('ping_pong', 4))

    def test_infrastructure_retries_are_not_rework(self):
        job_id = self.running()
        for _ in range(3):
            self.sup.fail(job_id, 'w1', reason_code='TOOL_UNAVAILABLE')
            self.clock.advance(300); self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        self.assertEqual(self.load(job_id)['retry']['watch'], [])
        self.assertNotIn('JOB_REWORK_STALLED', self.event_types())

    def test_a_hint_returns_the_job_to_rework_and_the_next_attempt_runs(self):
        job_id = self.stalled_job()
        hint = 'the port is parsed before the range check'
        job = self.sup.give_hint(job_id, f'  {hint}  ', resolved_by='captain')
        self.assertEqual((job['state'], job['supervisor_flags']['escalated_to'], job['retry']['captain_hint']), ('REWORK', None, hint))
        self.assertIn('JOB_HINT_GIVEN', self.event_types())
        with self.assertRaises(JobError) as ctx: self.sup.enqueue(job_id)
        self.assertEqual(ctx.exception.code, 'change_required')          # a different candidate is still needed
        self.again(job_id, 2, self.SAME)                                  # first failure under the new hint: allowed
        self.assertEqual(self.load(job_id)['state'], 'REWORK')
        self.again(job_id, 3, self.SAME)                                  # second one under the same hint: stalled again
        self.assertEqual(self.load(job_id)['state'], 'BLOCKED')
        with self.assertRaises(JobError) as ctx: self.sup.give_hint(job_id, hint, resolved_by='captain')
        self.assertEqual(ctx.exception.code, 'hint_not_new')
        self.sup.give_hint(job_id, 'look at urlparse', resolved_by='captain')
        self.assertEqual(self.load(job_id)['state'], 'REWORK')

    def test_give_hint_only_resolves_a_stalled_rework(self):
        job_id = self.running()
        self.sup.fail(job_id, 'w1', message=self.SAME)                    # in REWORK, not stalled
        with self.assertRaises(JobError) as ctx: self.sup.give_hint(job_id, 'hint', resolved_by='captain')
        self.assertEqual(ctx.exception.code, 'no_stalled_rework')
        self.again(job_id, 1, self.SAME)                                  # now stalled
        for bad in ('', '   ', None, 'x' * 2001):
            with self.assertRaises(JobError) as ctx: self.sup.give_hint(job_id, bad, resolved_by='captain')
            self.assertEqual(ctx.exception.code, 'invalid_hint')
        self.assertEqual(self.load(job_id)['state'], 'BLOCKED')

    def test_a_job_without_the_watch_fields_still_works(self):
        job_id = self.running()
        with self.sup.store.mutate(job_id) as job:
            job['retry'].pop('watch'); job['retry'].pop('captain_hint')
        self.sup.fail(job_id, 'w1', message=self.SAME)
        self.assertEqual(len(self.load(job_id)['retry']['watch']), 1)

    def test_a_context_overflow_repeated_is_not_a_rework_stall(self):
        # the context repair changes the next attempt (a new manifest) and has its own limit, so the watch must not count it
        job_id = self.running()
        for n in range(4):
            if n:
                self.sup.enqueue(job_id); self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
            self.sup.fail(job_id, 'w1', reason_code='CONTEXT_CAPACITY_UNQUALIFIED')
            stored = self.load(job_id)
            self.assertEqual((stored['state'], stored['retry']['awaiting_change']), ('REWORK', 'context_manifest'))
            self.assertFalse(stored['supervisor_flags'].get('escalated_to'))
            self.assertEqual(stored['retry']['watch'], [])
            self.sup.supply_change(job_id, context_manifest_id=f'CM-{n}')
        self.assertNotIn('JOB_REWORK_STALLED', self.event_types())

    def test_the_old_candidate_again_is_refused_and_counted(self):
        job_id = self.running()
        with self.sup.store.mutate(job_id) as job: job['candidate'] = {'candidate_hash': 'a' * 64}
        self.sup.fail(job_id, 'w1', message=self.SAME)
        with self.assertRaises(JobError) as ctx: self.sup.supply_change(job_id, candidate_hash='a' * 64)
        self.assertEqual(ctx.exception.code, 'change_not_different')       # still refused as before ...
        stored = self.load(job_id)
        self.assertEqual(len(stored['retry']['watch']), 2)                 # ... and now remembered
        self.assertEqual((stored['state'], stored['retry']['awaiting_change']), ('REWORK', 'candidate_hash'))
        with self.assertRaises(JobError): self.sup.supply_change(job_id, candidate_hash='a' * 64)
        stored = self.load(job_id)                                         # the second identical candidate in a row: stalled
        self.assertEqual((stored['state'], stored['supervisor_flags']['escalated_to']), ('BLOCKED', 'captain'))
        self.assertEqual(stored['last_error']['reason_code'], 'rework_stalled')
        self.assertIn('JOB_REWORK_STALLED', self.event_types())

    def test_a_missing_candidate_hash_is_refused_without_a_record(self):
        job_id = self.running()
        self.sup.fail(job_id, 'w1', message=self.SAME)
        with self.assertRaises(JobError) as ctx: self.sup.supply_change(job_id, candidate_hash=None)
        self.assertEqual(ctx.exception.code, 'change_not_different')
        self.assertEqual(len(self.load(job_id)['retry']['watch']), 1)

    def test_a_different_candidate_is_accepted_as_before(self):
        job_id = self.running()
        with self.sup.store.mutate(job_id) as job: job['candidate'] = {'candidate_hash': 'a' * 64}
        self.sup.fail(job_id, 'w1', message=self.SAME)
        self.sup.supply_change(job_id, candidate_hash='b' * 64)
        stored = self.load(job_id)
        self.assertEqual((stored['retry']['awaiting_change'], len(stored['retry']['watch'])), (None, 1))

    def test_rejected_reviews_repeat_into_a_stall(self):
        job_id = self.running()

        def verifying(n):
            with self.sup.store.mutate(job_id) as job:
                job['state'] = 'VERIFYING'; job['worker'] = None
                job['supervisor_flags']['awaiting_verification'] = True
                job['candidate'] = {'candidate_hash': f'{n:064x}'}
        verifying(1)
        self.assertEqual(self.sup.reject_verification(job_id, findings=['wrong'])['status'], 'REWORK')
        self.sup.supply_change(job_id, candidate_hash=f'{2:064x}')
        self.sup.enqueue(job_id); self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        verifying(2)
        out = self.sup.reject_verification(job_id, findings=['still wrong'])
        self.assertEqual(out['status'], 'BLOCKED')
        self.assertEqual(self.load(job_id)['last_error']['reason_code'], 'rework_stalled')



class SlotTests(Base):
    """Spec 2, S2.H4a (G2-S2-04, 12): with the model scheduler on, a job is claimed only with a slot, waits in line without losing an
    attempt, ages, and the server holds the one reservation. Fake loader and runtime; no model, no GPU."""
    config_overrides = {'workers': 3}

    def setUp(self):
        super().setUp()
        from guppi_runtime.jobs.testlab import TestLab
        from model_scheduler_fakes import make_scheduler, resolution
        self.make_resolution = resolution
        self.big = False
        self.recipes = {}
        self.slots, self.lab, self.loader, self.runtime, _, _ = make_scheduler(self.root / 'lab')
        self.lab.clock = lambda: self.clock.wall.timestamp()
        self.addCleanup(self.slots._release_gpu)
        self.TestLab = TestLab
        self.reserved = []
        test = self

        class Ledger:
            enabled = True
            def reserve(self, *args, **kw): test.reserved.append(args); return {'status': 'GRANTED', 'reservation': None}
            def release_job(self, job_id): return 0
            def reconcile(self, live): return []
            def refresh(self): return True
        self.sup = self.make_supervisor(resolver=self.resolve, scheduler=Ledger())
        self.sup.slots = self.slots

    def resolve(self, role, req, exclude, independent_of):
        return self.make_resolution(recipe=self.recipes.get(role, 'main.local'), vram_gb=10.5 if self.big else 8.0)

    def lease(self, job_id):
        with self.lab._db() as db:
            row = db.execute('SELECT * FROM slot_leases WHERE run_id=?', (job_id,)).fetchone()
        return dict(row) if row else None

    def queued(self, role='reviewer', priority=5):
        job = self.job(role, priority=priority)
        self.sup.enqueue(job['job_id'])
        self.clock.advance(1)                         # distinct arrival times: the line is by arrival, not by the random job id
        return job['job_id']

    def test_the_shipped_file_allows_up_to_8_workers_and_gives_the_starter_240_s(self):
        shipped = SupervisorConfig.load(CONFIG)
        self.assertEqual((shipped.workers, shipped.claim_timeout_s), (1, 240))
        self.assertEqual(SupervisorConfig(raw_config(workers=8)).workers, 8)

    def test_a_job_is_claimed_only_with_a_slot_and_the_last_one_waits_without_losing_an_attempt(self):
        a, b, c = self.queued(), self.queued(), self.queued()
        self.assertEqual(self.sup.claim('w1', ['reviewer'])['job']['job_id'], a)
        self.assertEqual(self.sup.confirm_start(a, 'w1')['status'], 'running')
        self.assertEqual(self.sup.claim('w2', ['reviewer'])['job']['job_id'], b)
        self.assertEqual(self.sup.confirm_start(b, 'w2')['status'], 'running')
        with self.assertRaises(JobError) as ctx:
            self.sup.claim('w3', ['reviewer'])
        self.assertEqual((ctx.exception.code, ctx.exception.detail), ('no_slot', 'kein_slot'))
        stored = self.load(c)
        self.assertEqual((stored['state'], stored['attempts'], stored['worker'], self.lease(c)['state']), ('QUEUED', 0, None, 'wartend'))
        self.assertEqual(self.loader.loaded, [('main.local', 2, 32768)])                 # one server, started once by the first job
        self.assertEqual(self.reserved, [])                                               # jobs with a slot reserve nothing themselves
        self.assertIsNone(self.load(a)['attempt_log'][0]['reservation_id'])
        self.sup.cancel(a, requested_by='t', reason='r')
        self.sup.acknowledge_cancel(a, 'w1')
        self.assertEqual(self.lease(a)['state'], 'fertig')
        self.assertEqual(self.sup.claim('w3', ['reviewer'])['job']['job_id'], c)

    def test_a_waiting_routine_job_ages_up_to_agent_and_then_comes_first_by_arrival(self):
        self.slots.take_for_job('BUSY-1', 7)
        routine = self.queued(priority=3)
        self.clock.advance(1)
        agent = self.queued(priority=5)
        self.clock.advance(60)
        with self.assertRaises(JobError):
            self.sup.claim('w1', ['reviewer'])                                            # BUSY-1 is the starter; nobody else while the server is off
        self.slots.release('BUSY-1')
        self.assertEqual(self.sup.claim('w1', ['reviewer'])['job']['job_id'], agent)      # after 61 s Routine is still 3
        self.sup._unclaim(agent, 'w1', 'test')
        self.clock.advance(180)
        self.assertEqual(self.sup.claim('w1', ['reviewer'])['job']['job_id'], routine)    # 241 s: 3 + 2 = 5 = Agent, and it came first

    def test_without_the_scheduler_the_raw_priority_decides_as_before(self):
        self.sup.slots = None
        routine = self.queued(priority=3)
        self.clock.advance(1)
        agent = self.queued(priority=5)
        self.clock.advance(10_000)
        self.assertEqual(self.sup.claim('w1', ['reviewer'])['job']['job_id'], agent)
        self.assertIsNone(self.lease(agent))
        self.assertIsNone(self.lease(routine))

    def test_a_busy_gpu_puts_the_job_back_in_line_instead_of_failing_it(self):
        other = self.TestLab(self.lab.path, clock=self.lab.clock, alive=lambda p: True, pid=222)
        token = other.try_acquire('bench', 'ladder')
        job = self.queued()
        self.sup.claim('w1', ['reviewer'])
        out = self.sup.confirm_start(job, 'w1')
        self.assertEqual((out['status'], out['reason']), ('waiting', 'gpu_lease_busy:bench:ladder'))
        stored = self.load(job)
        self.assertEqual((stored['state'], stored['attempts'], stored['worker'], self.lease(job)['state']), ('QUEUED', 0, None, 'wartend'))
        self.assertIn('JOB_SLOT_WAITING', self.event_types())
        other.release(token)
        self.sup.claim('w1', ['reviewer'])
        self.assertEqual(self.sup.confirm_start(job, 'w1')['status'], 'running')

    def test_another_recipe_without_a_rule_waits_and_the_next_claim_already_knows(self):
        a = self.queued()
        self.sup.claim('w1', ['reviewer'])
        self.sup.confirm_start(a, 'w1')
        self.recipes['planner'] = 'helper.local'
        p = self.queued('planner')
        self.sup.claim('w2', ['planner'])
        self.assertEqual(self.sup.confirm_start(p, 'w2')['status'], 'waiting')
        with self.assertRaises(JobError) as ctx:
            self.sup.claim('w2', ['planner'])
        self.assertEqual(ctx.exception.detail, 'model_swap_not_allowed')
        self.assertEqual(self.load(p)['attempts'], 0)

    def test_a_start_too_big_for_the_card_fails_the_attempt_with_a_known_reason(self):
        self.big = True
        job = self.queued()
        self.sup.claim('w1', ['reviewer'])
        out = self.sup.confirm_start(job, 'w1')
        self.assertEqual((out['status'], out['code']), ('resolution_failed', 'hardware_pressure'))
        self.assertEqual(self.load(job)['attempt_log'][0]['reason_code'], 'hardware_pressure')
        self.assertEqual(self.lease(job)['state'], 'fertig')                              # the starter's slot is free again

    def test_heartbeat_keeps_the_slot_lease_alive_and_reap_follows_the_jobs(self):
        a = self.queued()
        self.sup.claim('w1', ['reviewer'])
        self.sup.confirm_start(a, 'w1')
        self.clock.advance(30)
        self.sup.heartbeat(a, 'w1')
        self.assertEqual(self.lease(a)['heartbeat'], '2026-10-01T12:00:31Z')     # queued at 12:00:00, then +1 s
        b = self.queued()
        self.sup.claim('w2', ['reviewer'])
        self.clock.advance(self.sup.config.claim_timeout_s + 1)
        self.sup.heartbeat(a, 'w1')
        self.sup.reap()
        self.assertEqual((self.load(b)['worker'], self.lease(b)['state']), (None, 'wartend'))     # an expired claim gives its slot back
        self.sup.cancel(b, requested_by='t', reason='r')
        self.sup.reap()
        self.assertEqual((self.lease(a)['state'], self.lease(b)['state']), ('aktiv', 'verfallen'))

    def test_the_worker_waits_quietly_when_no_slot_is_free(self):
        from guppi_runtime.jobs.job_worker import Worker
        for _ in range(3):
            self.queued()
        for worker in ('w1', 'w2'):
            claimed = self.sup.claim(worker, ['reviewer'])
            self.sup.confirm_start(claimed['job']['job_id'], worker)
        self.assertEqual(Worker(self.sup, 'w3', ['reviewer'], lambda job, attempt, ctx: {}).run_once(), {'status': 'waiting'})
        self.assertEqual(self.sup.run_next('w3', ['reviewer'], lambda job, ctx: None), {'status': 'idle'})


if __name__ == '__main__':
    unittest.main()
