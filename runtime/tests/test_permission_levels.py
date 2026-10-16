"""Phase 6: permission levels as a ceiling above the Guard, scope binding, approvals as a parked job state."""
import importlib
import json
import os
import re
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from guppi_runtime.audit import AuditLog
from guppi_runtime.development_contracts import development_contract
from guppi_runtime.job_supervisor import JobError, JobSupervisor, SupervisorConfig, SupervisorJobStore, supervisor_state
from guppi_runtime.permission_levels import PermissionConfig, PermissionGate
from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
PERMS = RUNTIME / 'config' / 'permission_levels.yaml'
SUPERVISOR = RUNTIME / 'config' / 'job_supervisor.yaml'
ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
RULES = ARCH / 'core' / 'guard' / 'guard_rules.yaml'


class Clock:
    def __init__(self): self.wall = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc); self.mono = 1000.0
    def now(self): return self.wall
    def monotonic(self): return self.mono
    def advance(self, s): self.wall += timedelta(seconds=s); self.mono += s


class StubGuard:
    """Answers with fixed decisions; used to prove the gate never turns a Guard 'no' into a 'yes'."""
    def __init__(self, decision): self.decision, self.calls = decision, []
    rules, defaults = {}, {}
    def evaluate(self, action, *, mission_id=None, target=''):
        self.calls.append(action); return {'decision': self.decision, 'rule_id': 'stub', 'action': action, 'target': target}
    def check_token(self, *a, **k): return {'authorized': False, 'reason': 'stub'}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rt = GuppiRuntime(self.root / 'project', ARCH)
        self.guard, self.gate = self.rt.guard, self.rt.permission_gate
        self.dev = self.root / 'dev'; self.dev.mkdir()
        self.clock = Clock()

    def job(self, level=2, scope=True, **kw):
        job = {'job_id': 'SDJ-0123456789AB', 'permission_level': level, 'contract': {'contract_digest': 'c' * 64},
               'scope': {'roots': [str(self.dev.resolve())] if scope else []}, 'policy_hash': self.gate.policy_hash()}
        job.update(kw); return job

    def inside(self, name='a.txt'): return str(self.dev / name)


class ConsistencyTests(unittest.TestCase):
    """The mapping and the Guard's rules must not drift apart; this is what keeps a level from granting anything."""

    def setUp(self):
        self.cfg = PermissionConfig.load(PERMS)
        self.rules = {r['action']: r['decision'] for r in yaml.safe_load(RULES.read_text(encoding='utf-8'))['guard_rules']['rules']}

    def test_every_guard_action_is_classified_exactly_once(self):
        classified = set(self.cfg.actions) | set(self.cfg.never)
        self.assertEqual(set(self.rules) - classified, set(), 'a Guard action has no level')
        self.assertEqual(classified - set(self.rules), set(), 'a mapped action no longer exists in the Guard')
        self.assertEqual(len(self.rules), 28)       # 24 + self_integration(+rollback) 2026-10-02 + external_read, model_remove 2026-10-03

    def test_nothing_above_level_two_is_ever_allowed_without_the_captain(self):
        for action, spec in self.cfg.actions.items():
            if spec['level'] >= 3:
                self.assertNotEqual(self.rules[action], 'ALLOW', action)
        for action, decision in self.rules.items():
            if decision == 'ALLOW':
                self.assertLessEqual(self.cfg.actions[action]['level'], 2, action)

    def test_the_guards_blocked_actions_are_exactly_the_never_automatic_ones(self):
        self.assertEqual({a for a, d in self.rules.items() if d == 'BLOCK'}, set(self.cfg.never))

    def test_levels_five_and_six_always_need_the_captain(self):
        for action, spec in self.cfg.actions.items():
            if spec['level'] >= 5:
                self.assertEqual(self.rules[action], 'CAPTAIN_REQUIRED', action)

    def test_scoped_actions_are_exactly_those_that_touch_paths(self):
        scoped = {a for a, s in self.cfg.actions.items() if s['path_scoped']}
        self.assertEqual(scoped, {'read_project_file', 'git_read', 'create_new_artifact', 'overwrite_existing', 'filesystem_move', 'file_delete', 'git_init'})

    def test_invalid_config_is_refused(self):
        good = yaml.safe_load(PERMS.read_text(encoding='utf-8'))['permission_levels']
        mutations = [lambda c: c['names'].pop(3), lambda c: c['actions']['git_read'].update(level=0), lambda c: c['actions']['git_read'].update(level=7),
                     lambda c: c['actions']['git_read'].update(path_scoped='yes'), lambda c: c['never_automatic'].append('git_read'),
                     lambda c: c.update(actions={}), lambda c: c.update(never_automatic='nope'), lambda c: c['names'].update({3: ''})]
        for mutate in mutations:
            bad = deepcopy(good); mutate(bad)
            with self.assertRaises(ValueError): PermissionConfig(bad)
        with self.assertRaises(ValueError): PermissionConfig.load(Path(tempfile.gettempdir()) / 'nope_permissions.yaml')


class GateTests(Base):
    def test_level_is_a_ceiling_on_the_actions_a_job_may_ask_for(self):
        job = self.job(level=2)
        self.assertEqual(self.gate.check(job, 'read_project_file', self.inside())['status'], 'ALLOWED')
        self.assertEqual(self.gate.check(job, 'create_new_artifact', self.inside())['status'], 'ALLOWED')
        for action in ('sandbox_execute', 'overwrite_existing', 'model_runtime_control', 'deployment'):
            out = self.gate.check(job, action, self.inside())
            self.assertEqual((out['status'], out['reason']), ('DENIED', 'permission_level_exceeds_job'), action)

    def test_level_zero_may_do_nothing_at_all(self):
        for action in ('read_project_file', 'git_read', 'create_new_artifact'):
            self.assertEqual(self.gate.check(self.job(level=0), action, self.inside())['reason'], 'permission_level_exceeds_job')

    def test_a_sufficient_level_still_goes_through_the_guard(self):
        job = self.job(level=3)
        out = self.gate.check(job, 'sandbox_execute', 'sandbox:run-1')
        self.assertEqual((out['status'], out['reason'], out['guard']['decision']), ('APPROVAL_REQUIRED', 'guard_requires_captain', 'CAPTAIN_REQUIRED'))
        out = self.gate.check(self.job(level=6), 'deployment', 'prod')
        self.assertEqual(out['status'], 'APPROVAL_REQUIRED')                                 # even the top level never skips the Captain

    def test_never_automatic_actions_are_denied_at_every_level_and_with_any_token(self):
        for action in ('modify_core_invariants', 'bypass_guard', 'silent_stable_replacement'):
            for level in (0, 3, 6):
                out = self.gate.check(self.job(level=level), action, 'x', token={'token_id': 'APR-1', 'status': 'active'})
                self.assertEqual((out['status'], out['reason'], out['level']), ('DENIED', 'never_automatic', None), (action, level))

    def test_unknown_actions_count_as_the_highest_level(self):
        self.assertEqual(self.gate.level_of('teleport'), 6)
        self.assertEqual(self.gate.check(self.job(level=5), 'teleport', 'x')['reason'], 'permission_level_exceeds_job')
        out = self.gate.check(self.job(level=6), 'teleport', 'x')
        self.assertEqual(out['status'], 'APPROVAL_REQUIRED')                                  # the Guard's own default for unknown actions

    def test_the_guard_can_only_make_it_stricter(self):
        job = self.job(level=6, policy_hash=None)                  # the stub guard has other rules, so no fingerprint applies here
        self.assertEqual(self.gate_with(StubGuard('BLOCK')).check(job, 'create_new_artifact', self.inside())['reason'], 'guard_blocked')
        self.assertEqual(self.gate_with(StubGuard('CAPTAIN_REQUIRED')).check(job, 'read_project_file', self.inside())['status'], 'APPROVAL_REQUIRED')
        stub = StubGuard('ALLOW')
        self.assertEqual(self.gate_with(stub).check(self.job(level=1, policy_hash=None), 'create_new_artifact', self.inside())['status'], 'DENIED')
        self.assertEqual(stub.calls, [])                                                       # refused before the Guard was even asked

    def gate_with(self, guard): return PermissionGate(self.gate.config, guard, audit=self.rt.audit)

    def test_job_without_a_valid_level_gets_nothing(self):
        for level in (None, -1, 7, '2', True):
            self.assertEqual(self.gate.check(self.job(level=level), 'read_project_file', self.inside())['reason'], 'job_has_no_valid_permission_level', repr(level))

    def test_paths_must_stay_inside_the_development_environment(self):
        job = self.job(level=2)
        self.assertEqual(self.gate.check(self.job(scope=False), 'read_project_file', self.inside())['reason'], 'no_development_scope')
        outside = self.root / 'elsewhere' / 'x.txt'
        for target in (outside, self.dev / '..' / 'elsewhere' / 'x.txt', str(self.dev) + '2' + os.sep + 'x.txt', self.root, '', 'relative/path.txt'):
            out = self.gate.check(job, 'create_new_artifact', str(target))
            self.assertEqual((out['status'], out['reason']), ('DENIED', 'target_outside_scope'), str(target))
        for target in (self.dev, self.dev / 'sub' / 'deep' / 'f.txt', self.dev / 'sub' / '..' / 'g.txt'):
            self.assertEqual(self.gate.check(job, 'create_new_artifact', str(target))['status'], 'ALLOWED', str(target))

    @unittest.skipUnless(os.name == 'nt', 'case folding is a Windows rule')
    def test_windows_paths_compare_case_insensitively(self):
        self.assertEqual(self.gate.check(self.job(), 'read_project_file', str(self.dev).upper() + '\\A.TXT')['status'], 'ALLOWED')

    def test_symlink_pointing_out_of_the_scope_is_refused(self):
        outside = self.root / 'outside'; outside.mkdir()
        link = self.dev / 'link'
        try: link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc: self.skipTest(f'symlinks not permitted on this host: {exc}')
        self.assertEqual(self.gate.check(self.job(), 'create_new_artifact', str(link / 'x.txt'))['reason'], 'target_outside_scope')

    def test_logical_targets_are_not_path_checked(self):
        self.assertEqual(self.gate.check(self.job(level=3, scope=False), 'sandbox_execute', 'sandbox:anything')['status'], 'APPROVAL_REQUIRED')

    def test_policy_may_not_change_under_a_running_job(self):
        job = self.job()
        self.assertEqual(self.gate.check(job, 'read_project_file', self.inside())['status'], 'ALLOWED')
        self.guard.rules = {**self.guard.rules, 'read_project_file': {**self.guard.rules['read_project_file'], 'decision': 'ALLOW', 'id': 'GR-X'}}
        out = self.gate.check(job, 'read_project_file', self.inside())
        self.assertEqual((out['status'], out['reason']), ('DENIED', 'policy_changed_since_job_start'))
        self.assertEqual(self.gate.check({**job, 'policy_hash': None}, 'read_project_file', self.inside())['status'], 'ALLOWED')   # no fingerprint recorded: not applicable

    def test_policy_hash_follows_mapping_and_rules(self):
        first = self.gate.policy_hash()
        self.assertEqual(first, self.gate.policy_hash())
        other = deepcopy(self.gate.config); other.actions['git_read']['level'] = 3
        self.assertNotEqual(first, PermissionGate(other, self.guard).policy_hash())

    def test_denials_are_audited_and_allows_are_left_to_the_guard(self):
        self.gate.check(self.job(level=2), 'deployment', 'prod')
        events = [json.loads(x) for x in self.rt.audit.path.read_text(encoding='utf-8').splitlines()]
        denied = [e for e in events if e['event_type'] == 'PERMISSION_DENIED'][-1]['payload']
        self.assertEqual((denied['action'], denied['reason'], denied['level_required'], denied['level_job']), ('deployment', 'permission_level_exceeds_job', 6, 2))
        before = len(events)
        self.gate.check(self.job(level=2), 'read_project_file', self.inside())
        after = [json.loads(x)['event_type'] for x in self.rt.audit.path.read_text(encoding='utf-8').splitlines()][before:]
        self.assertNotIn('PERMISSION_DENIED', after)

    def test_a_captain_token_makes_the_action_allowed_but_is_not_spent_by_the_check(self):
        job = self.job(level=3)
        binding = self.gate.binding(job, 'sandbox_execute', 'sandbox:run-1')
        gate_record = self.guard.create_gate(job['job_id'], 'sandbox_execute', 'sandbox:run-1', request_binding=binding)
        token = self.guard.approve(gate_record)
        out = self.gate.check(job, 'sandbox_execute', 'sandbox:run-1', token=token)
        self.assertEqual((out['status'], out['reason']), ('ALLOWED', 'captain_approved'))
        self.assertEqual(self.gate.check(job, 'sandbox_execute', 'sandbox:run-1', token=token)['status'], 'ALLOWED')     # still unspent
        self.assertTrue(self.guard.authorize(token, mission_id=job['job_id'], action='sandbox_execute', target='sandbox:run-1', request_binding=binding)['authorized'])
        again = self.gate.check(job, 'sandbox_execute', 'sandbox:run-1', token=token)
        self.assertEqual((again['status'], again['token_problem']), ('APPROVAL_REQUIRED', 'missing_or_inactive_token'))      # spent once, gone

    def test_a_token_for_something_else_does_not_help(self):
        job = self.job(level=3)
        other = self.guard.approve(self.guard.create_gate(job['job_id'], 'sandbox_execute', 'sandbox:other',
                                                          request_binding=self.gate.binding(job, 'sandbox_execute', 'sandbox:other')))
        out = self.gate.check(job, 'sandbox_execute', 'sandbox:run-1', token=other)
        self.assertEqual((out['status'], out['token_problem']), ('APPROVAL_REQUIRED', 'target_out_of_scope'))
        foreign = self.job(level=3, job_id='SDJ-AAAAAAAAAAAA')
        self.assertEqual(self.gate.check(foreign, 'sandbox_execute', 'sandbox:other', token=other)['token_problem'], 'mission_mismatch')
        changed = deepcopy(job); changed['contract']['contract_digest'] = 'd' * 64
        self.assertEqual(self.gate.check(changed, 'sandbox_execute', 'sandbox:other', token=other)['status'], 'APPROVAL_REQUIRED')   # approval was for the old contract


class GuardCheckTokenTests(Base):
    def issue(self, action='candidate_accept', target='t', binding=None):
        return self.guard.approve(self.guard.create_gate('M-1', action, target, request_binding=binding))

    def test_check_does_not_consume_and_authorize_still_works_exactly_once(self):
        token = self.issue()
        for _ in range(3):
            self.assertEqual(self.guard.check_token(token, mission_id='M-1', action='candidate_accept', target='t'), {'authorized': True, 'reason': 'approved'})
        self.assertEqual(token['status'], 'active')
        self.assertTrue(self.guard.authorize(token, mission_id='M-1', action='candidate_accept', target='t')['authorized'])
        self.assertEqual(token['status'], 'used')
        self.assertFalse(self.guard.authorize(token, mission_id='M-1', action='candidate_accept', target='t')['authorized'])
        self.assertFalse(self.guard.check_token(token, mission_id='M-1', action='candidate_accept', target='t')['authorized'])

    def test_check_applies_every_rule_authorize_applies(self):
        token = self.issue(binding={'x': 1})
        cases = [(dict(mission_id='M-2', action='candidate_accept', target='t', request_binding={'x': 1}), 'mission_mismatch'),
                 (dict(mission_id='M-1', action='candidate_rollback', target='t', request_binding={'x': 1}), 'action_mismatch'),
                 (dict(mission_id='M-1', action='candidate_accept', target='elsewhere', request_binding={'x': 1}), 'target_out_of_scope'),
                 (dict(mission_id='M-1', action='candidate_accept', target='t', request_binding={'x': 2}), 'request_digest_mismatch')]
        for kwargs, reason in cases:
            self.assertEqual(self.guard.check_token(token, **kwargs)['reason'], reason)
            self.assertEqual(self.guard.authorize(deepcopy(token), **kwargs)['reason'], reason)
        forged = deepcopy(token); forged['grants']['targets'] = ['anything']
        self.assertEqual(self.guard.check_token(forged, mission_id='M-1', action='candidate_accept', target='anything', request_binding={'x': 1})['reason'], 'token_tampered')
        self.assertEqual(self.guard.check_token({'token_id': 'APR-NOPE', 'status': 'active'}, mission_id='M-1', action='a')['reason'], 'token_not_issued_by_guard')
        for junk in (None, {}, 'x'):
            self.assertEqual(self.guard.check_token(junk, mission_id='M-1', action='a')['reason'], 'missing_or_inactive_token')


class SupervisorBase(Base):
    def setUp(self):
        super().setUp()
        raw = yaml.safe_load(SUPERVISOR.read_text(encoding='utf-8'))['job_supervisor']; raw['enabled'] = True
        self.reports = []
        self.sup = JobSupervisor(SupervisorJobStore(self.root / 'jobs', self.rt.audit), SupervisorConfig(raw), audit=self.rt.audit, guard=self.guard,
                                 clock=self.clock.now, monotonic=self.clock.monotonic, permissions=self.gate,
                                 provider_report=lambda *a: self.reports.append(a))

    def contract(self, level=3):
        return development_contract(objective='probe', classification='E1', permission_level=level,
                                    acceptance_criteria=[{'type': 'capability_smoke_test', 'id': 's'}], verification_plan=[{'type': 'deterministic_tests'}])

    def start(self, level=3, role='reviewer', worker='w1', scope=True):
        job = self.sup.create_job(self.contract(level), requested_role=role, scope_roots=[self.dev] if scope else None)
        self.sup.enqueue(job['job_id']); self.sup.claim(worker, [role]); self.sup.confirm_start(job['job_id'], worker)
        return job['job_id']

    def load(self, job_id): return self.sup.store.load(job_id)
    def types(self): return [json.loads(x)['event_type'] for x in self.rt.audit.path.read_text(encoding='utf-8').splitlines()]


class SupervisorPermissionTests(SupervisorBase):
    def test_job_records_its_scope_and_the_policy_it_started_under(self):
        job = self.sup.create_job(self.contract(), requested_role='reviewer', scope_roots=[self.dev, str(self.dev / 'sub' / '..')])
        self.assertEqual(job['scope']['roots'], [str(self.dev.resolve()), str(self.dev.resolve())])
        self.assertEqual(job['policy_hash'], self.gate.policy_hash())
        self.assertEqual(self.sup.create_job(self.contract(), requested_role='reviewer')['scope'], {'roots': []})
        for bad in ('nope', 5, [1], [''], {'a': 1}):
            with self.assertRaises(JobError) as ctx: self.sup.create_job(self.contract(), requested_role='reviewer', scope_roots=bad)
            self.assertEqual(ctx.exception.code, 'invalid_scope_roots', repr(bad))

    def test_an_allowed_action_leaves_the_job_alone(self):
        job_id = self.start(level=2)
        before = self.load(job_id)['rev']
        out = self.sup.check_action(job_id, 'w1', 'create_new_artifact', self.dev / 'out.txt')
        self.assertEqual((out['status'], out['job_failed']), ('ALLOWED', False))
        self.assertEqual(self.load(job_id)['rev'], before)

    def test_a_denied_action_fails_the_job_as_policy_denied_and_escalates_to_the_captain(self):
        job_id = self.start(level=2)
        out = self.sup.check_action(job_id, 'w1', 'overwrite_existing', self.dev / 'a.txt')
        stored = self.load(job_id)
        self.assertEqual((out['status'], out['reason'], out['job_failed']), ('DENIED', 'permission_level_exceeds_job', True))
        self.assertEqual((stored['state'], stored['supervisor_flags']['escalated_to'], stored['last_error']['class']), ('BLOCKED', 'captain', 'policy_denied'))
        self.assertEqual(stored['attempt_log'][0]['outcome'], 'FAILED')
        self.assertEqual(stored['retry']['exclude'], [])                                      # no fallback around a refusal
        with self.assertRaises(JobError) as ctx: self.sup.enqueue(job_id)
        self.assertEqual(ctx.exception.code, 'captain_resolution_required')

    def test_scope_escape_and_never_automatic_fail_the_job_too(self):
        for action, target, reason in (('create_new_artifact', self.root / 'elsewhere.txt', 'target_outside_scope'),
                                       ('modify_core_invariants', 'core', 'never_automatic')):
            with self.subTest(reason=reason):
                self.setUp()
                job_id = self.start(level=6)
                self.assertEqual(self.sup.check_action(job_id, 'w1', action, target)['reason'], reason)
                self.assertEqual(self.load(job_id)['state'], 'BLOCKED')

    def test_a_job_without_scope_cannot_touch_paths(self):
        job_id = self.start(level=2, scope=False)
        self.assertEqual(self.sup.check_action(job_id, 'w1', 'read_project_file', self.dev / 'a')['reason'], 'no_development_scope')

    def test_only_the_worker_holding_the_job_can_ask(self):
        job_id = self.start(level=2)
        with self.assertRaises(JobError) as ctx: self.sup.check_action(job_id, 'intruder', 'read_project_file', self.dev)
        self.assertEqual(ctx.exception.code, 'lease_lost')

    def test_without_a_gate_nothing_is_allowed(self):
        job_id = self.start(level=2)
        self.sup.permissions = None
        for call in (lambda: self.sup.check_action(job_id, 'w1', 'read_project_file', self.dev), lambda: self.sup.request_approval(job_id, 'w1', 'sandbox_execute', 'x'),
                     lambda: self.sup.resolve_approval(job_id, {})):
            with self.assertRaises(JobError) as ctx: call()
            self.assertEqual(ctx.exception.code, 'permission_gate_unavailable')

    def test_a_changed_policy_stops_a_running_job(self):
        job_id = self.start(level=2)
        self.guard.rules = {**self.guard.rules, 'git_read': {**self.guard.rules['git_read'], 'id': 'GR-CHANGED'}}
        self.assertEqual(self.sup.check_action(job_id, 'w1', 'git_read', self.dev)['reason'], 'policy_changed_since_job_start')

    def test_level_can_be_lowered_never_raised(self):
        job_id = self.start(level=3)
        self.assertEqual(self.sup.lower_permission_level(job_id, 2)['permission_level'], 2)
        self.assertIn('JOB_PERMISSION_LOWERED', self.types())
        for level in (3, 6):
            with self.assertRaises(JobError) as ctx: self.sup.lower_permission_level(job_id, level)
            self.assertEqual(ctx.exception.code, 'permission_cannot_be_raised')
        for bad in (-1, 7, '1', None):
            with self.assertRaises(JobError): self.sup.lower_permission_level(job_id, bad)
        rev = self.load(job_id)['rev']; self.sup.lower_permission_level(job_id, 2)
        self.assertEqual(self.load(job_id)['rev'], rev)                                       # same level: nothing written
        self.assertEqual(self.sup.check_action(job_id, 'w1', 'sandbox_execute', 'sandbox:x')['reason'], 'permission_level_exceeds_job')   # the lower level applies at once

    def test_final_jobs_keep_their_level(self):
        job = self.sup.create_job(self.contract(), requested_role='reviewer'); self.sup.cancel(job['job_id'], requested_by='t', reason='r')
        with self.assertRaises(JobError) as ctx: self.sup.lower_permission_level(job['job_id'], 1)
        self.assertEqual(ctx.exception.code, 'already_final')


class ApprovalTests(SupervisorBase):
    def ask(self, job_id, action='sandbox_execute', target='sandbox:run-1'):
        return self.sup.request_approval(job_id, 'w1', action, target)

    def test_request_parks_the_job_without_blaming_anyone(self):
        job_id = self.start(level=3)
        out = self.ask(job_id)
        stored = self.load(job_id)
        self.assertEqual((out['status'], stored['state'], supervisor_state(stored)), ('approval_requested', 'BLOCKED', 'WAITING_APPROVAL'))
        self.assertEqual((stored['attempt_log'][0]['outcome'], stored['attempt_log'][0]['reason_code']), ('SUSPENDED', 'awaiting_approval'))
        self.assertIsNone(stored['worker'])
        self.assertEqual(stored['retry']['count'], 0)                                          # not a failure
        self.assertEqual(self.reports, [])
        self.assertEqual(stored['approval']['gate_id'], out['gate']['gate_id'])
        self.assertIn('JOB_APPROVAL_REQUESTED', self.types())
        self.assertEqual(self.sup.view()['counts'], {'WAITING_APPROVAL': 1})

    def test_a_parked_job_cannot_be_queued_resumed_or_claimed(self):
        job_id = self.start(level=3); self.ask(job_id)
        for call in (lambda: self.sup.enqueue(job_id), lambda: self.sup.resume(job_id, resolved_by='guppi')):
            with self.assertRaises(JobError) as ctx: call()
            self.assertEqual(ctx.exception.code, 'approval_pending')
        with self.assertRaises(JobError) as ctx: self.sup.claim('w1', ['reviewer'])
        self.assertEqual(ctx.exception.code, 'no_job')

    def test_the_slot_is_free_while_the_captain_thinks(self):
        job_id = self.start(level=3); self.ask(job_id)
        other = self.sup.create_job(self.contract(2), requested_role='reviewer')
        self.sup.enqueue(other['job_id'])
        self.assertEqual(self.sup.claim('w2', ['reviewer'])['job']['job_id'], other['job_id'])   # workers=1 and it is not blocked by the parked job

    def test_only_actions_that_need_the_captain_can_ask(self):
        job_id = self.start(level=3)
        with self.assertRaises(JobError) as ctx: self.sup.request_approval(job_id, 'w1', 'read_project_file', self.dev / 'a')
        self.assertEqual((ctx.exception.code, ctx.exception.detail['status']), ('approval_not_required', 'ALLOWED'))
        with self.assertRaises(JobError) as ctx: self.sup.request_approval(job_id, 'w1', 'deployment', 'prod')            # level 6 > job level 3
        self.assertEqual((ctx.exception.code, ctx.exception.detail['reason']), ('approval_not_required', 'permission_level_exceeds_job'))
        self.assertEqual(self.load(job_id)['state'], 'BUILDING')                               # nothing changed

    def test_full_cycle_approve_resume_run_with_the_token_spent_exactly_once(self):
        job_id = self.start(level=3)
        out = self.ask(job_id)
        token = self.guard.approve(out['gate'])
        resumed = self.sup.resolve_approval(job_id, token)
        self.assertEqual((resumed['state'], supervisor_state(resumed), resumed['approval']['status']), ('QUEUED', 'QUEUED', 'granted'))
        self.assertIn('JOB_APPROVAL_RESOLVED', self.types())
        self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        handed = self.sup.consume_approval(job_id, 'w1')
        self.assertEqual((handed['action'], handed['target']), ('sandbox_execute', 'sandbox:run-1'))
        self.assertEqual(self.load(job_id)['approval']['status'], 'handed_over')
        self.assertNotIn('token', self.load(job_id)['approval'])                              # the bearer token does not stay in the job file
        again = self.sup.check_action(job_id, 'w1', 'sandbox_execute', 'sandbox:run-1', token=handed['token'])
        self.assertEqual(again['status'], 'ALLOWED')
        spend = lambda: self.guard.authorize(handed['token'], mission_id=job_id, action='sandbox_execute', target='sandbox:run-1',
                                             request_binding=self.load(job_id)['approval']['binding'])
        self.assertTrue(spend()['authorized'])
        self.assertFalse(spend()['authorized'])
        with self.assertRaises(JobError) as ctx: self.sup.consume_approval(job_id, 'w1')
        self.assertEqual(ctx.exception.code, 'no_granted_approval')
        self.assertEqual(len(self.load(job_id)['attempt_log']), 2)

    def test_only_the_worker_of_the_new_attempt_may_collect_the_token(self):
        job_id = self.start(level=3); token = self.guard.approve(self.ask(job_id)['gate'])
        self.sup.resolve_approval(job_id, token)
        with self.assertRaises(JobError) as ctx: self.sup.consume_approval(job_id, 'w1')
        self.assertEqual(ctx.exception.code, 'lease_lost')                                     # not started yet: nobody holds the lease

    def test_a_bad_or_foreign_token_is_not_accepted(self):
        job_id = self.start(level=3); out = self.ask(job_id)
        for token in (None, {}, {'token_id': 'APR-FAKE', 'status': 'active', 'mission_id': job_id, 'grants': {}}):
            with self.assertRaises(JobError) as ctx: self.sup.resolve_approval(job_id, token)
            self.assertEqual(ctx.exception.code, 'approval_invalid')
        wrong = self.guard.approve(self.guard.create_gate(job_id, 'sandbox_execute', 'sandbox:other',
                                                          request_binding=self.gate.binding(self.load(job_id), 'sandbox_execute', 'sandbox:other')))
        with self.assertRaises(JobError) as ctx: self.sup.resolve_approval(job_id, wrong)
        self.assertEqual((ctx.exception.code, ctx.exception.detail), ('approval_invalid', 'target_out_of_scope'))
        other_action = self.guard.approve(self.guard.create_gate(job_id, 'shell_execute', 'sandbox:run-1', request_binding=self.load(job_id)['approval']['binding']))
        with self.assertRaises(JobError): self.sup.resolve_approval(job_id, other_action)
        self.assertEqual(supervisor_state(self.load(job_id)), 'WAITING_APPROVAL')              # still waiting; nothing was consumed
        self.assertTrue(self.sup.resolve_approval(job_id, self.guard.approve(out['gate']))['state'] == 'QUEUED')

    def test_an_approval_for_a_changed_contract_or_policy_is_stale(self):
        for change in (lambda j: j['contract'].update(contract_digest='e' * 64), lambda j: j.update(policy_hash='f' * 64)):
            self.setUp()
            job_id = self.start(level=3); token = self.guard.approve(self.ask(job_id)['gate'])
            with self.sup.store.mutate(job_id) as job: change(job)
            with self.assertRaises(JobError) as ctx: self.sup.resolve_approval(job_id, token)
            self.assertEqual(ctx.exception.code, 'approval_stale')

    def test_token_cannot_be_reused_after_it_was_spent_elsewhere(self):
        job_id = self.start(level=3); out = self.ask(job_id); token = self.guard.approve(out['gate'])
        self.assertTrue(self.guard.authorize(token, mission_id=job_id, action='sandbox_execute', target='sandbox:run-1',
                                             request_binding=self.load(job_id)['approval']['binding'])['authorized'])
        with self.assertRaises(JobError) as ctx: self.sup.resolve_approval(job_id, token)
        self.assertEqual(ctx.exception.code, 'approval_invalid')

    def test_denial_ends_the_job_and_nothing_retries_around_it(self):
        job_id = self.start(level=3); self.ask(job_id)
        done = self.sup.deny_approval(job_id, decided_by='captain', reason='not now')
        self.assertEqual((done['state'], done['approval']['status'], done['cancel']['reason']), ('CANCELLED', 'denied', 'approval_denied'))
        self.assertEqual(self.sup.view()['counts'], {'CANCELLED': 1})
        for call in (lambda: self.sup.enqueue(job_id), lambda: self.sup.resolve_approval(job_id, {}), lambda: self.sup.deny_approval(job_id, decided_by='x', reason='y')):
            with self.assertRaises(JobError): call()

    def test_cancelling_a_parked_job_closes_its_approval(self):
        job_id = self.start(level=3); self.ask(job_id)
        self.sup.cancel(job_id, requested_by='guppi', reason='obsolete')
        self.assertEqual(self.load(job_id)['approval']['status'], 'cancelled')
        self.assertNotEqual(supervisor_state(self.load(job_id)), 'WAITING_APPROVAL')

    def test_a_pending_approval_survives_a_restart(self):
        job_id = self.start(level=3); out = self.ask(job_id); token = self.guard.approve(out['gate'])
        raw = yaml.safe_load(SUPERVISOR.read_text(encoding='utf-8'))['job_supervisor']; raw['enabled'] = True
        restarted = JobSupervisor(SupervisorJobStore(self.root / 'jobs', self.rt.audit), SupervisorConfig(raw), audit=self.rt.audit, guard=self.guard,
                                  clock=self.clock.now, monotonic=self.clock.monotonic, permissions=self.gate)
        self.assertEqual(restarted.startup_recovery()['abandoned'], [])                         # a parked job has no worker to recover
        self.assertEqual(supervisor_state(restarted.store.load(job_id)), 'WAITING_APPROVAL')
        self.assertEqual(restarted.resolve_approval(job_id, token)['state'], 'QUEUED')

    def test_resolve_without_a_pending_approval_is_refused(self):
        job_id = self.start(level=3)
        for call in (lambda: self.sup.resolve_approval(job_id, {}), lambda: self.sup.deny_approval(job_id, decided_by='x', reason='y')):
            with self.assertRaises(JobError) as ctx: call()
            self.assertEqual(ctx.exception.code, 'no_approval_pending')

    def test_parked_job_is_not_touched_by_the_reaper(self):
        job_id = self.start(level=3); self.ask(job_id)
        self.sup.reap(); self.clock.advance(10 ** 5); self.assertEqual(self.sup.reap(), [])
        self.assertEqual(supervisor_state(self.load(job_id)), 'WAITING_APPROVAL')


class RuntimeAndBoundaryTests(unittest.TestCase):
    def test_runtime_wires_the_gate_and_reports_the_levels(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            self.assertIs(rt.job_supervisor.permissions, rt.permission_gate)
            status = rt.boot()['permissions']
            self.assertTrue(status['available'])
            self.assertEqual(status['levels'][6], 'EXTERNAL_ACTION')
            self.assertEqual(status['actions']['sandbox_execute'], 3)
            self.assertEqual(status['never_automatic'], ['bypass_guard', 'modify_core_invariants', 'silent_stable_replacement'])
            self.assertEqual(status['policy_hash'], rt.permission_gate.policy_hash())

    def test_a_broken_permission_file_leaves_no_gate_and_says_why(self):
        import guppi_runtime.runtime as runtime_module
        real = runtime_module.PermissionConfig.load
        runtime_module.PermissionConfig.load = staticmethod(lambda path: (_ for _ in ()).throw(ValueError('permission_config_invalid:test')))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
        finally:
            runtime_module.PermissionConfig.load = real
        self.assertIsNone(rt.permission_gate)
        self.assertIsNone(rt.job_supervisor.permissions)
        self.assertEqual(rt.permission_status(), {'available': False, 'error': 'permission_config_invalid:test'})

    def test_the_gate_never_grants_or_changes_anything_itself(self):
        source = Path(importlib.import_module('guppi_runtime.permission_levels').__file__).read_text(encoding='utf-8')
        for forbidden in ('.approve(', 'create_gate(', 'authorize(', '.transition(', 'atomic_write_json', '.write_text(', 'open('):
            self.assertNotIn(forbidden, source)

    def test_gate_source_names_no_provider_or_model(self):
        for name in ('permission_levels.py',):
            source = (RUNTIME / 'src' / 'guppi_runtime' / name).read_text(encoding='utf-8').lower()
            for word in ('lm-studio', 'llama', 'qwen', 'kev', 'openai', 'anthropic'):
                self.assertNotRegex(source, rf'\b{re.escape(word)}\b', word)


if __name__ == '__main__':
    unittest.main()
