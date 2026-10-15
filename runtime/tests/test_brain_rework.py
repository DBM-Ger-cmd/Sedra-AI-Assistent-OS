"""The rework loop: VERIFY FAIL -> REWORK -> PLAN must really re-plan (it paused forever before 2026-10-02)."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'


class ReworkTests(unittest.TestCase):
    def runtime(self, verdicts):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        rt = GuppiRuntime(Path(tmp.name) / 'p', ARCH)
        orig = rt.bus.send; self.calls = {'verify': 0, 'plan': 0}
        def send(msg):
            if msg.type == 'verification_request':
                verdict = verdicts[min(self.calls['verify'], len(verdicts) - 1)]; self.calls['verify'] += 1
                if verdict == 'FAIL': return {'status': 'FAIL', 'findings': ['forced'], 'evidence': []}
            if msg.type == 'create_plan': self.calls['plan'] += 1
            return orig(msg)
        rt.bus.send = send
        return rt

    def drive(self, rt, mid):
        """Run to the end; every gate (the new-execution contract, and the reworked step overwriting the first result) is
        approved as the Captain would."""
        for _ in range(20):
            m = rt.brain.run(mid, max_steps=60)
            if not m['human_gates']['pending']: return m
            gate = m['human_gates']['pending'].pop()
            m['execution']['approval_token'] = rt.guard.approve(gate); m['human_gates']['resolved'].append(gate); rt.missions.save(m)
        self.fail('mission did not finish')

    def test_a_failed_verification_is_reworked_and_can_complete(self):
        rt = self.runtime(['FAIL', 'PASS'])
        m = self.drive(rt, rt.brain.create_mission('Write a short note')['identity']['mission_id'])
        self.assertEqual(m['lifecycle']['phase'], 'COMPLETE')
        self.assertEqual((m['rework_cycles'], self.calls['plan'], self.calls['verify']), (1, 2, 2))
        archived = m['execution']['previous_executions']
        self.assertEqual(len(archived), 1); self.assertEqual(archived[0]['verification']['status'], 'FAIL')

    def test_the_rework_budget_ends_in_failed(self):
        rt = self.runtime(['FAIL'])
        m = self.drive(rt, rt.brain.create_mission('Write a short note')['identity']['mission_id'])
        self.assertEqual(m['lifecycle']['phase'], 'FAILED')
        self.assertEqual(m['rework_cycles'], rt.brain.max_rework + 1)
        self.assertEqual(len(m['execution']['previous_executions']), rt.brain.max_rework)

    def test_no_new_execution_without_the_captain(self):
        rt = self.runtime(['FAIL'])
        mid = rt.brain.create_mission('Write a short note')['identity']['mission_id']
        m = rt.brain.run(mid, max_steps=60)
        self.assertEqual((m['lifecycle']['phase'], m['lifecycle']['status']), ('REWORK', 'waiting_captain'))
        self.assertEqual(self.calls['plan'], 1); self.assertNotIn('previous_executions', m['execution'])
        gate = m['human_gates']['pending'][0]
        self.assertEqual(gate['request']['exact_action'], 'execution_recovery')
        self.assertTrue(gate['request']['targets'][0].startswith('replan:' + mid))

    def test_a_step_with_an_open_outcome_is_never_archived(self):
        rt = self.runtime(['FAIL'])
        mid = rt.brain.create_mission('Write a short note')['identity']['mission_id']
        rt.brain.run(mid, max_steps=4)                                   # up to EXECUTE with a journal
        m = rt.missions.load(mid)
        m['lifecycle']['phase'] = 'REWORK'
        journal = m['execution'].get('step_journal') or {'schema': 1, 'steps': [{'id': 'STEP-1', 'status': 'RUNNING'}]}
        journal['steps'][0]['status'] = 'RUNNING'; m['execution']['step_journal'] = journal
        rt.missions.save(m)
        m = rt.brain.step(mid)
        self.assertEqual(m['lifecycle']['phase'], 'PAUSED')
        self.assertEqual(m['wait']['reason_code'], 'rework_blocked_by_unfinished_steps')
        self.assertIsNotNone(m['execution']['step_journal'])            # untouched


if __name__ == '__main__':
    unittest.main()
