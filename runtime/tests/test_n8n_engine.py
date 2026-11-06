from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sedra_runtime.workflows.engine import LocalN8n, EngineError, configuration
from workflow_fixture import sample

CONFIG = {'enabled': True, 'base_url': 'http://127.0.0.1:5678', 'api_key_env': 'SEDRA_N8N_TEST_KEY'}


class EngineDouble(LocalN8n):
    def __init__(self, fail=None):
        super().__init__(CONFIG); self.calls = []; self.doc = None; self.fail = fail

    def request(self, method, path, body=None, *, api=True):
        self.calls.append((method, path, deepcopy(body), api))
        if self.fail == path or (self.fail == 'trigger' and path.startswith('/webhook/')):
            raise TimeoutError('test timeout')
        if path == '/api/v1/workflows':
            self.doc = deepcopy(body); return dict(self.doc, id='temporary-1')
        if method == 'GET':
            observed = deepcopy(self.doc)
            if self.fail == 'tamper': observed['nodes'][0]['parameters'] = {'changed': True}
            return observed
        if path.startswith('/webhook/'):
            return [{'text': 'Hello'}]
        return {}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'SEDRA_N8N_TEST_KEY': 'test-key'}); self.env.start(); self.addCleanup(self.env.stop)

    def test_gated_adapter_protocol_and_cleanup(self):
        engine = EngineDouble(); result = engine.run(sample(), {'text': 'Input'})
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['cleanup_errors'], [])
        self.assertEqual([c[0] for c in engine.calls], ['POST', 'POST', 'GET', 'POST', 'POST', 'DELETE'])
        self.assertFalse(engine.calls[3][3], 'API key must not be sent to the webhook')
        self.assertEqual(engine.doc['nodes'][0]['parameters']['jsonOutput'], '={{ $json.body }}')
        self.assertNotIn('active', engine.doc)
        self.assertEqual(engine.doc['settings']['saveDataSuccessExecution'], 'none')

    def test_remote_tampering_prevents_trigger_and_still_cleans(self):
        engine = EngineDouble('tamper'); result = engine.run(sample(), {})
        self.assertEqual(result['error'], 'n8n_remote_workflow_changed')
        self.assertFalse(any(c[1].startswith('/webhook/') for c in engine.calls))
        self.assertEqual(engine.calls[-1][0], 'DELETE')

    def test_trigger_timeout_is_unknown_and_never_retried(self):
        engine = EngineDouble('trigger'); result = engine.run(sample(), {})
        self.assertEqual(result['error'], 'UNKNOWN_REMOTE_OUTCOME')
        self.assertEqual(sum(c[1].startswith('/webhook/') for c in engine.calls), 1)
        self.assertEqual(engine.calls[-1][0], 'DELETE')

    def test_cleanup_failure_is_visible(self):
        engine = EngineDouble('/api/v1/workflows/temporary-1/deactivate')
        self.assertEqual(engine.run(sample(), {})['cleanup_errors'], ['POST temporary workflow'])
        self.assertEqual(engine.calls[-1][0], 'DELETE')

    def test_unsafe_node_never_reaches_engine(self):
        doc = sample(); doc['nodes'][1]['type'] = 'n8n-nodes-base.httpRequest'
        engine = EngineDouble()
        with self.assertRaises(ValueError): engine.run(doc, {})
        self.assertEqual(engine.calls, [])

    def test_loopback_config_is_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root / 'local_config'; folder.mkdir()
            self.assertEqual(configuration(root), {'enabled': False})
            for url in ('http://localhost:5678', 'http://example.com:5678', 'http://127.0.0.1:5678/path',
                        'http://user:pass@127.0.0.1:5678', 'http://127.0.0.1:5678/?x=1', 'https://127.0.0.1:5678'):
                (folder / 'n8n.json').write_text(json.dumps(dict(CONFIG, base_url=url)))
                with self.assertRaises(ValueError, msg=url): configuration(root)
            (folder / 'n8n.json').write_text(json.dumps(CONFIG))
            self.assertEqual(configuration(root), CONFIG)

    def test_missing_key_has_no_network_effect(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(EngineError, 'key_missing'): LocalN8n(CONFIG)

    def test_client_never_follows_redirects(self):
        class Response:
            status = 302
            def read(self, limit): return b'{}'
        with patch('sedra_runtime.workflows.engine.http.client.HTTPConnection') as connection:
            connection.return_value.getresponse.return_value = Response()
            with self.assertRaisesRegex(EngineError, '302'): LocalN8n(CONFIG).request('GET', '/api/v1/workflows')
            connection.assert_called_once_with('127.0.0.1', 5678, timeout=5)
            self.assertTrue(connection.return_value.close.called)
