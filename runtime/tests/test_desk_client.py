"""Das Feld `client` im Audit `UIX_ACTION` und die Client-Token (Spec 0, D2, KERN-02, K0.13).

Dasselbe Verb (`model/laden` auf dem Fake-Host des Golden-Tests) über vier Wege: Browser-Token, Browser-Token mit dem Kopf des
Gesprächs, CLI-Token, MCP-Token. Vier Einträge `UIX_ACTION`, gleich bis auf `client`. Der Server setzt `client`, nie der Aufrufer."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime import uix_clients
from guppi_runtime.uix_server import make_server
from test_desk_kinds import FakeHost, audit_payloads, data, post


class LoadingHost(FakeHost):
    """Der Fake-Host, dessen Modell `chat.local` bereit ist; Laden lädt nichts, es zählt nur."""

    def load_model(self, payload):
        self.__dict__.setdefault('loads', []).append(dict(payload))
        return {'status': 'geladen (Test)', 'recipe_id': payload.get('recipe_id')}


class Client(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='desk-client-')
        cls.hub = LoadingHost(cls.tmp.name, data())
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = cls.url.split('#')[0]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.hub.close()
        cls.tmp.cleanup()

    def as_client(self, client, path, body, headers=None):
        info = uix_clients.read(self.hub.project_root, client)
        return post(self.base + '#' + info['token'], path, body, headers)

    def test_the_same_verb_from_four_ways_differs_only_in_client(self):
        body = {'type': 'model', 'id': 'chat.local', 'verb': 'laden'}
        before = len(audit_payloads(self.hub, 'UIX_ACTION'))
        loads = len(self.hub.__dict__.get('loads', []))
        self.assertEqual(post(self.url, '/api/actions', body)[0], 200)
        self.assertEqual(post(self.url, '/api/actions', body, {'X-SEDRA-Tool': 'talk'})[0], 200)
        self.assertEqual(self.as_client('cli', '/api/actions', body)[0], 200)
        self.assertEqual(self.as_client('mcp', '/api/actions', body)[0], 200)
        entries = audit_payloads(self.hub, 'UIX_ACTION')[before:]
        self.assertEqual([e['client'] for e in entries], ['shell', 'chat', 'cli', 'mcp'])
        self.assertEqual({json.dumps({k: v for k, v in e.items() if k != 'client'}, sort_keys=True) for e in entries},
                         {json.dumps({'type': 'model', 'id': 'chat.local', 'verb': 'laden'}, sort_keys=True)})
        self.assertEqual(len(self.hub.loads) - loads, 4)

    def test_a_tool_that_is_not_the_chat_stays_shell(self):
        body = {'type': 'model', 'id': 'chat.local', 'verb': 'laden'}
        self.assertEqual(post(self.url, '/api/actions', body, {'X-SEDRA-Tool': 'intent'})[0], 200)
        self.assertEqual(audit_payloads(self.hub, 'UIX_ACTION')[-1]['client'], 'shell')

    def test_client_in_the_body_is_refused_and_logged(self):
        for path in uix_clients.ROUTES:
            with self.subTest(path):
                before = len(audit_payloads(self.hub, 'UIX_CLIENT_REFUSED'))
                status, out = post(self.url, path, {'type': 'model', 'id': 'chat.local', 'verb': 'laden', 'client': 'cli'})
                self.assertEqual((status, out['message']), (400, 'client_is_set_by_server'))
                self.assertEqual(audit_payloads(self.hub, 'UIX_CLIENT_REFUSED')[before:], [{'path': path, 'client': 'shell'}])

    def test_a_foreign_token_is_refused(self):
        status, _ = post(self.base + '#falsch', '/api/actions', {'type': 'model', 'id': 'chat.local', 'verb': 'laden'})
        self.assertEqual(status, 403)

    def test_a_client_token_opens_only_the_desk(self):
        status, obj = self.as_client('cli', '/api/objects', {'type': 'model', 'id': 'chat.local'})
        self.assertEqual((status, obj['state']), (200, 'bereit'))
        self.assertEqual(self.as_client('mcp', '/api/chat', {'intent': 'x'})[0], 403)
        import http.client
        info = uix_clients.read(self.hub.project_root, 'cli')
        c = http.client.HTTPConnection('127.0.0.1', info['port'], timeout=10)
        c.request('GET', '/api/strip', headers={'X-GUPPI-Token': info['token']})
        self.assertEqual(c.getresponse().status, 403)
        c.close()

    def test_the_token_files(self):
        for client in uix_clients.CLIENTS:
            with self.subTest(client):
                path = uix_clients.path_for(self.hub.project_root, client)
                doc = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual((doc['client'], doc['port']), (client, self.server.server_port))
                token = uix_clients.read(self.hub.project_root, client)['token']
                self.assertNotIn(token, self.url)
                if sys.platform == 'win32':
                    self.assertEqual(doc['protection'], 'dpapi')
                    self.assertNotIn(token, path.read_text(encoding='utf-8'), 'unter Windows steht der Token nicht im Klartext')
                else:
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(uix_clients.read(self.hub.project_root, 'cli')['token'], uix_clients.read(self.hub.project_root, 'mcp')['token'])


class Lifecycle(unittest.TestCase):
    def test_files_go_with_the_server_and_without_them_there_is_no_way_in(self):
        with tempfile.TemporaryDirectory(prefix='desk-client-life-') as tmp:
            hub = LoadingHost(tmp, data())
            try:
                server, _ = make_server(hub)
                self.assertTrue(uix_clients.path_for(hub.project_root, 'cli').is_file())
                server.server_close()
                for client in uix_clients.CLIENTS:
                    self.assertFalse(uix_clients.path_for(hub.project_root, client).exists())
                with self.assertRaisesRegex(ValueError, 'uix_not_running'):
                    uix_clients.read(hub.project_root, 'cli')
                with self.assertRaisesRegex(ValueError, 'uix_not_running'):
                    uix_clients.call(hub.project_root, 'mcp', '/api/objects', {'type': 'task'})
                with self.assertRaisesRegex(ValueError, 'route_not_for_clients'):
                    uix_clients.call(hub.project_root, 'mcp', '/api/chat', {})
            finally:
                hub.close()


if __name__ == '__main__':
    unittest.main()
