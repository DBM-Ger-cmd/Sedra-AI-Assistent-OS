"""MCP-Server des Desk (Spec 0, D2, KERN-05, K0.15): `act` legt über die laufende Oberfläche eine Aufgabe an, und das Audit sagt
`client: "mcp"`. Ohne gültigen MCP-Token und ohne Oberfläche geht nichts."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime import uix_clients
from guppi_runtime.desk_mcp import DeskMcpServer
from guppi_runtime.uix_server import UIXHub, make_server
from test_desk_kinds import ARCH, audit_payloads


def call(server, name, arguments, ident=1):
    return server.handle({'jsonrpc': '2.0', 'id': ident, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}})['result']


def text(result):
    body = result['content'][0]['text']
    return json.loads(body.split('\n', 1)[1].rsplit('\n</untrusted>', 1)[0]) if not result['isError'] else body


class DeskMcp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-mcp-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)
        self.http, _ = make_server(self.hub)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)
        self.mcp = DeskMcpServer(self.hub.project_root)

    def test_act_creates_a_task_and_the_audit_says_mcp(self):
        made = self.hub.intent_create({'title': 'CSV-Export bauen', 'text': 'aus dem Gespräch'})
        result = call(self.mcp, 'act', {'type': 'intent', 'id': made['id'], 'verb': 'aufgabe_machen'})
        self.assertFalse(result['isError'], result)
        out = text(result)
        self.assertEqual((out['status'], out['verb']), ('done', 'aufgabe_machen'))
        self.assertEqual(len(self.hub.intents.get(made['id'])['tasks']), 1, 'eine Aufgabe ist entstanden')
        self.assertEqual(audit_payloads(self.hub, 'UIX_ACTION')[-1],
                         {'type': 'intent', 'id': made['id'], 'verb': 'aufgabe_machen', 'client': 'mcp'})
        listing = text(call(self.mcp, 'objects', {'type': 'task'}, 2))
        self.assertEqual(len(listing['items']), 1)
        log = [json.loads(l) for l in (self.hub.project_root / 'runtime_data' / 'mcp_access.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([(e['caller'], e['tool'], e['ok']) for e in log[-2:]], [('external:mcp', 'act', True), ('external:mcp', 'objects', True)])

    def test_without_a_valid_mcp_token_nothing_happens(self):
        made = self.hub.intent_create({'title': 'Nicht anlegen', 'text': ''})
        path = uix_clients.path_for(self.hub.project_root, 'mcp')
        doc = json.loads(path.read_text(encoding='utf-8'))
        cli = json.loads(uix_clients.path_for(self.hub.project_root, 'cli').read_text(encoding='utf-8'))
        path.write_text(json.dumps(dict(doc, protection='datei-0600', token='falsch')), encoding='utf-8')
        result = call(self.mcp, 'act', {'type': 'intent', 'id': made['id'], 'verb': 'aufgabe_machen'})
        self.assertEqual((result['isError'], result['content'][0]['text']), (True, 'error: desk answered 403'))
        self.assertEqual(self.hub.intents.get(made['id'])['tasks'], [])
        path.write_text(json.dumps(dict(cli, client='mcp')), encoding='utf-8')     # der CLI-Token ist ein anderer Client
        result = call(self.mcp, 'act', {'type': 'intent', 'id': made['id'], 'verb': 'aufgabe_machen'})
        self.assertFalse(result['isError'])
        self.assertEqual(audit_payloads(self.hub, 'UIX_ACTION')[-1]['client'], 'cli', 'der Server setzt client aus dem Token, nicht aus der Datei')
        path.unlink()
        result = call(self.mcp, 'objects', {'type': 'task'})
        self.assertEqual((result['isError'], result['content'][0]['text']), (True, 'error: uix_not_running'))

    def test_only_the_schema_passes(self):
        for args in ({'type': 'task', 'client': 'shell'}, {'type': 'Task'}, {'type': 'task', 'id': '../x'}, {}):
            with self.subTest(args):
                self.assertTrue(call(self.mcp, 'objects', args)['isError'])
        self.assertIn('args_must_be_an_object', call(self.mcp, 'act', {'type': 'task', 'id': 'M-1', 'verb': 'ausfuehren', 'args': '[1]'})['content'][0]['text'])
        self.assertIn('id_required', call(self.mcp, 'act', {'type': 'task', 'verb': 'ausfuehren'})['content'][0]['text'])
        names = [t['name'] for t in self.mcp.handle({'jsonrpc': '2.0', 'id': 9, 'method': 'tools/list'})['result']['tools']]
        self.assertEqual(names, ['objects', 'act'])

    def test_the_captain_switches_it_off(self):
        off = self.hub.project_root / 'runtime_data' / 'mcp_off'
        off.write_text('', encoding='utf-8')
        self.addCleanup(off.unlink)
        self.assertIn('switched off', call(self.mcp, 'objects', {'type': 'task'})['content'][0]['text'])


if __name__ == '__main__':
    unittest.main()
