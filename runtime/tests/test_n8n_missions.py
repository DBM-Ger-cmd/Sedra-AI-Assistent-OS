import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sedra_runtime.uix_server import UIXHub
from sedra_runtime.workflows.desk import _save, _start, _run_read
from host_isolation import setUpModule, tearDownModule  # noqa: F401
from workflow_fixture import sample

ARCH = Path(__file__).resolve().parents[2] / 'architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'


class Missions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH); self.addCleanup(self.hub.close)      # Wissensspeicher (Kern) hält wissen.sqlite offen
        cfg = self.hub.project_root / 'local_config/n8n.json'; cfg.parent.mkdir(exist_ok=True)
        cfg.write_text(json.dumps({'enabled': True, 'base_url': 'http://127.0.0.1:5678', 'api_key_env': 'SEDRA_N8N_TEST_KEY'}))
        self.record = _save(self.hub, None, {'workflow': sample()})

    def pending(self):
        run = _start(self.hub, self.record['id'], {'revision': 1})
        m = self.hub.runtime.missions.load(run['id'])
        return run, m, m['human_gates']['pending'][0]

    def test_start_always_waits_without_touching_engine(self):
        with patch('sedra_runtime.workflows.execution.LocalN8n') as engine:
            run, m, gate = self.pending()
            self.assertEqual(run['state'], 'CAPTAIN_REVIEW')
            self.assertEqual(gate['request']['exact_action'], 'run_n8n_workflow')
            engine.assert_not_called()
            self.hub.run_mission({'mission_id': run['id']})
            engine.assert_not_called()

    def test_fresh_approval_executes_once_and_keeps_result(self):
        run, m, gate = self.pending(); token = self.hub.runtime.guard.approve(gate)
        m['execution']['approval_token'] = token; m['human_gates']['pending'] = []; self.hub.runtime.missions.save(m)
        with patch('sedra_runtime.workflows.execution.LocalN8n') as engine:
            engine.return_value.run.return_value = {'status': 'completed', 'output': [{'text': 'Hello'}], 'cleanup_errors': []}
            self.hub.run_mission({'mission_id': run['id']})
            self.hub.run_mission({'mission_id': run['id']})
            self.assertEqual(engine.return_value.run.call_count, 1)
        result = _run_read(self.hub, run['id'])
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(result['result']['output'], [{'text': 'Hello'}])
        self.assertTrue(result['artifacts'])

    def test_changed_input_cannot_reuse_gate(self):
        run, m, gate = self.pending(); token = self.hub.runtime.guard.approve(gate)
        request = dict(m['plan']['steps'][0]); request['inputs'] = {'changed': True}
        with patch('sedra_runtime.workflows.execution.LocalN8n') as engine:
            out = self.hub.runtime.control.execute(m, request, token)
            self.assertEqual(out['status'], 'captain_required'); engine.assert_not_called()

    def test_configuration_change_requires_new_approval(self):
        run, m, gate = self.pending(); token = self.hub.runtime.guard.approve(gate)
        cfg = self.hub.project_root / 'local_config/n8n.json'
        cfg.write_text(cfg.read_text().replace('5678', '5679'))
        with patch('sedra_runtime.workflows.execution.LocalN8n') as engine:
            out = self.hub.runtime.control.execute(m, m['plan']['steps'][0], token)
            self.assertEqual(out['status'], 'captain_required'); engine.assert_not_called()

    def test_timeout_closes_mission_without_replay(self):
        run, m, gate = self.pending(); token = self.hub.runtime.guard.approve(gate)
        m['execution']['approval_token'] = token; self.hub.runtime.missions.save(m)
        with patch('sedra_runtime.workflows.execution.LocalN8n') as engine:
            engine.return_value.run.return_value = {'status': 'failed', 'error': 'UNKNOWN_REMOTE_OUTCOME', 'cleanup_errors': []}
            self.hub.run_mission({'mission_id': run['id']})
            self.assertEqual(_run_read(self.hub, run['id'])['state'], 'FAILED')
            self.assertEqual(engine.return_value.run.call_count, 1)

    def test_stale_revision_is_rejected_before_mission(self):
        with self.assertRaisesRegex(ValueError, 'revision_conflict'):
            _start(self.hub, self.record['id'], {'revision': 0})

    def test_allow_rule_cannot_remove_mandatory_gate(self):
        self.hub.runtime.guard.rules['run_n8n_workflow'] = {'action': 'run_n8n_workflow', 'decision': 'ALLOW', 'id': 'test'}
        run, m, gate = self.pending()
        self.assertEqual(run['state'], 'CAPTAIN_REVIEW')

    def test_guard_block_is_authoritative(self):
        self.hub.runtime.guard.rules['run_n8n_workflow'] = {'action': 'run_n8n_workflow', 'decision': 'BLOCK', 'id': 'test'}
        with patch('sedra_runtime.workflows.execution.LocalN8n') as engine:
            run = _start(self.hub, self.record['id'], {'revision': 1})
            self.assertEqual(run['state'], 'PAUSED'); engine.assert_not_called()

    def test_desk_registers_app_and_keeps_other_extensions(self):
        self.assertTrue(self.hub.kinds.frozen)
        self.assertIsNotNone(self.hub.kinds.get('workflow'))
        out = self.hub.objects_view({'type': 'workflow', 'id': 'alle'})
        self.assertEqual(out['items'][0]['workflow'], sample())
        self.assertEqual(self.hub.kinds.problems, [])
