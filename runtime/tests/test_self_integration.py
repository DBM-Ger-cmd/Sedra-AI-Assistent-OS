import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from guppi_runtime.selfdev import self_integration
from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
QUALIFIED = {'job_id': 'SBX-x', 'report_sha256': 'f' * 64, 'test_counts': [13], 'preparation_sha256': 'e' * 64}


class SelfIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.rt = GuppiRuntime(Path(tmp.name) / 'project', ARCH)
        self.capdir = Path(tmp.name) / 'capabilities'; self.capdir.mkdir()
        for p in (patch.object(self_integration, 'CAPABILITY_DIR', self.capdir.resolve()),
                  patch.object(self_integration, 'test_qualification', lambda rt, m: dict(QUALIFIED))):
            p.start(); self.addCleanup(p.stop)
        self.sd = self.rt.self_development; self.sd.independence_check = None

    def mission(self, changes, verdict='PASS', capability='path_health_check'):
        m = self.rt.brain.create_mission('integration test')
        mid = m['identity']['mission_id']
        m['plan']['steps'] = [{'binding': {'inputs': {'changes': changes}}}]
        m['lifecycle']['phase'] = 'CANDIDATE_REVIEW'
        self.rt.missions.save(m)
        jid = self.sd.start(capability, evidence=[{'source': 'test'}])['job']['job_id']
        self.sd.prepare_development_environment(jid, {'execution_ready': True})
        self.sd.bind_candidate(jid, attempt_id='a1', stage=f'guppi-candidates/{mid}', parent_version='1', candidate_hash='a' * 64,
                               builder='coder', builder_key='gpt-oss:k1')
        cid = self.sd.jobs.load(jid)['candidate']['candidate_id']
        ev = self.rt.development_evidence.add('vm_unittest', job_id=jid, candidate_id=cid, trust_level='deterministic',
                                              payload={'status': 'PASS' if verdict == 'PASS' else 'FAIL'})['evidence_id']
        self.sd.attach_verification(jid, verifier='verifier', result=verdict, evidence_refs=[ev], verifier_key='gemma4:k2')
        return mid, jid

    def run_op(self, mid, op, plan=None):
        return self_integration.command(self.rt, mid, op, plan)

    def approve_and_apply(self, mid, op):
        plan = self.run_op(mid, op + '-preview' if op == 'rollback' else 'integrate-preview')['plan']
        out = self.run_op(mid, op, plan)
        self.assertEqual(out['status'], 'captain_required')          # never without the Captain
        m = self.rt.missions.load(mid); gate = m['human_gates']['pending'][-1]
        m['execution']['approval_token'] = self.rt.guard.approve(gate); m['human_gates']['pending'].pop(); self.rt.missions.save(m)
        return self.run_op(mid, op, plan)

    def test_new_module_is_integrated_only_with_a_gate_and_the_job_is_activated(self):
        mid, jid = self.mission([{'path': 'path_health.py', 'content': 'X = 1\n'}])
        out = self.approve_and_apply(mid, 'integrate')
        self.assertEqual(out['status'], 'completed')
        self.assertEqual((self.capdir / 'path_health.py').read_bytes(), b'X = 1\n')
        self.assertEqual(self.sd.jobs.load(jid)['state'], 'ACTIVATED')
        m = self.rt.missions.load(mid)
        self.assertEqual((m['lifecycle']['phase'], m['result']['accepted'], m['result']['accepted_via']), ('COMPLETE', True, 'self_integration'))

    def test_rollback_is_recorded_in_the_closed_mission(self):
        mid, _ = self.mission([{'path': 'path_health.py', 'content': 'X = 1\n'}])
        self.approve_and_apply(mid, 'integrate'); self.approve_and_apply(mid, 'rollback')
        m = self.rt.missions.load(mid)
        self.assertEqual((m['lifecycle']['phase'], m['result']['accepted'], m['result']['rolled_back']), ('COMPLETE', False, True))

    def test_mission_list_is_cached_but_never_stale(self):
        mid, _ = self.mission([{'path': 'path_health.py', 'content': 'X = 1\n'}])
        first = {m['identity']['mission_id']: m for m in self.rt.missions.list()}
        first[mid]['objective']['current'] = 'changed by a caller'            # callers get copies
        self.assertNotEqual(self.rt.missions.load(mid)['objective']['current'], 'changed by a caller')
        m = self.rt.missions.load(mid); m['objective']['current'] = 'saved change'; self.rt.missions.save(m)
        listed = {m['identity']['mission_id']: m for m in self.rt.missions.list()}
        self.assertEqual(listed[mid]['objective']['current'], 'saved change')

    def test_rollback_removes_only_an_unchanged_module(self):
        mid, jid = self.mission([{'path': 'path_health.py', 'content': 'X = 1\n'}])
        self.approve_and_apply(mid, 'integrate')
        (self.capdir / 'path_health.py').write_bytes(b'X = 2\n')
        with self.assertRaises(ValueError): self.run_op(mid, 'rollback-preview')
        (self.capdir / 'path_health.py').write_bytes(b'X = 1\n')     # bytes: write_text would turn \n into \r\n on Windows
        out = self.approve_and_apply(mid, 'rollback')
        self.assertEqual(out['status'], 'completed'); self.assertFalse((self.capdir / 'path_health.py').exists())
        self.assertEqual(self.sd.jobs.load(jid)['state'], 'ROLLED_BACK')

    def test_existing_module_is_never_overwritten(self):
        (self.capdir / 'path_health.py').write_text('original\n')
        mid, _ = self.mission([{'path': 'path_health.py', 'content': 'X = 1\n'}])
        with self.assertRaises(ValueError) as ctx: self.run_op(mid, 'integrate-preview')
        self.assertIn('capability_module_exists', str(ctx.exception))

    def test_tests_nested_paths_and_bad_names_are_refused(self):
        for path in ('tests/test_x.py', 'sub/x.py', '__init__.py', 'Bad-Name.py', 'x.txt'):
            mid, _ = self.mission([{'path': path, 'content': 'X = 1\n'}])
            with self.assertRaises(ValueError, msg=path): self.run_op(mid, 'integrate-preview')

    def test_a_job_that_is_not_ready_is_refused(self):
        mid, _ = self.mission([{'path': 'path_health.py', 'content': 'X = 1\n'}], verdict='FAIL')
        with self.assertRaises(ValueError) as ctx: self.run_op(mid, 'integrate-preview')
        self.assertIn('development_job_not_ready', str(ctx.exception))

    def test_only_e1_capabilities(self):
        mid, jid = self.mission([{'path': 'path_health.py', 'content': 'X = 1\n'}])
        with self.sd.jobs.mutate(jid) as job: job['contract']['classification'] = 'E2'
        with self.assertRaises(ValueError) as ctx: self.run_op(mid, 'integrate-preview')
        self.assertIn('only_e1', str(ctx.exception))

    def test_a_mission_without_a_job_is_refused(self):
        m = self.rt.brain.create_mission('plain')
        with self.assertRaises(ValueError) as ctx: self.run_op(m['identity']['mission_id'], 'integrate-preview')
        self.assertIn('self_development_job_required', str(ctx.exception))

    def test_a_changed_plan_is_refused(self):
        mid, _ = self.mission([{'path': 'path_health.py', 'content': 'X = 1\n'}])
        plan = self.run_op(mid, 'integrate-preview')['plan']; plan['files'][0]['content'] = 'import os\n'
        with self.assertRaises(ValueError): self.run_op(mid, 'integrate', plan)

    def test_guard_rules_name_both_actions(self):
        for action in ('self_integration', 'self_integration_rollback'):
            self.assertEqual(self.rt.guard.evaluate(action, target='t')['decision'], 'CAPTAIN_REQUIRED')


if __name__ == '__main__':
    unittest.main()
