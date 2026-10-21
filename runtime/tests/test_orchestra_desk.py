"""Abnahme KERN-01 (Spec 0, D5, K0.22): mit eingeschaltetem Schalter und einer Fixture-Datenbank aus `orchestra.store.open_db`
liefern `POST /api/objects` für `agent`, `issue`, `routine` und `budget` genau die Schlüssel der einen Form; `task` bleibt die
Mission wie aufgezeichnet (Golden). Mit Schalter aus ist `issue` ein unbekannter Typ und `agent` der Platzhalter."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk.kinds import SHAPE
from guppi_runtime.orchestra.store import open_db
from guppi_runtime.uix_server import make_server
from test_desk_kinds import FakeHost, call, cases, data, key, post, GOLDEN

ROWS = Path(__file__).resolve().parent / 'fixtures' / 'orchestra_desk' / 'rows.json'


def fixture_db(project):
    """Die Datenbank, wie die Runtime sie öffnen wird (runtime_data/orchestra/orchestra.db), mit den Zeilen aus rows.json."""
    rows = json.loads(ROWS.read_text(encoding='utf-8'))
    conn = open_db(Path(project) / 'runtime_data' / 'orchestra' / 'orchestra.db')
    try:
        for table in ('agents', 'tasks', 'routines', 'spend'):
            for row in rows[table]:
                cols = sorted(row)
                conn.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", [row[c] for c in cols])
    finally:
        conn.close()


def switch_on(project):
    (Path(project) / 'local_config').mkdir(parents=True, exist_ok=True)
    (Path(project) / 'local_config' / 'switches.yaml').write_text('switches:\n  orchestra: {enabled: true}\n', encoding='utf-8')


class SwitchOn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='orchestra-desk-')
        project = Path(cls.tmp.name) / 'project'
        switch_on(project)
        fixture_db(project)
        cls.hub = FakeHost(cls.tmp.name, data())
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.hub.close()
        cls.hub.runtime.orchestra.close()
        cls.tmp.cleanup()

    def objects(self, body):
        status, out = post(self.url, '/api/objects', body)
        self.assertEqual(status, 200, out)
        return out

    def test_the_runtime_is_on_and_the_four_types_are_registered(self):
        self.assertEqual(self.hub.runtime.boot()['orchestra'], {'enabled': True, 'error': None, 'schema_version': 1})
        self.assertEqual(self.hub.kinds.problems, [])
        for name in ('agent', 'issue', 'routine', 'budget'):
            self.assertEqual(self.hub.kinds.get(name).source, 'orchestra', name)

    def test_the_four_types_have_exactly_the_shape(self):
        singles = [{'type': 'agent', 'id': 'A-CODER'}, {'type': 'issue', 'id': 'I-100'}, {'type': 'routine', 'id': 'R-1'},
                   {'type': 'budget', 'id': 'A-CODER'}]
        for body in singles:
            with self.subTest(body):
                obj = self.objects(body)
                self.assertEqual(sorted(obj), sorted(SHAPE))
                self.assertEqual((obj['type'], obj['id']), (body['type'], body['id']))
        for t in ('agent', 'issue', 'routine', 'budget'):
            with self.subTest(t):
                listing = self.objects({'type': t})
                self.assertTrue(listing['items'])
                for item in listing['items']:
                    self.assertEqual(sorted(item), sorted(SHAPE))

    def test_what_the_objects_say(self):
        agent = self.objects({'type': 'agent', 'id': 'A-CODER'})
        self.assertEqual((agent['title'], agent['state'], agent['links']), ('Coder', 'pausiert', [{'type': 'agent', 'id': 'A-UA'}]))
        self.assertEqual([i['id'] for i in self.objects({'type': 'issue'})['items']], ['I-100', 'I-101'], 'Priorität zuerst')
        self.assertEqual([i['id'] for i in self.objects({'type': 'issue', 'state': 'offen'})['items']], ['I-101'])
        budget = self.objects({'type': 'budget', 'id': 'A-CODER'})
        self.assertEqual((budget['state'], budget['summary']), ('Warnung', 'Token 850/1000 · Cent 120/500'))
        self.assertEqual(self.objects({'type': 'budget', 'id': 'A-UA'})['state'], 'im Rahmen')
        self.assertEqual(self.objects({'type': 'agent', 'id': 'A-WEG'})['state'], 'nicht gefunden')
        self.assertEqual(self.objects({'type': 'routine', 'id': 'R-1'})['state'], 'an')

    def test_the_types_are_read_only_in_spec_0(self):
        """OP-12, G3-S0-15: in Spec 0 keine Verben an den vier Typen."""
        for body in ({'type': 'agent', 'id': 'A-CODER'}, {'type': 'issue', 'id': 'I-100'}):
            self.assertEqual(self.objects(body)['actions'], [])
        status, out = post(self.url, '/api/actions', {'type': 'agent', 'id': 'A-CODER', 'verb': 'wecken'})
        self.assertEqual((status, out['message']), (400, 'unknown_object_type'))

    def test_task_stays_the_mission_as_recorded(self):
        golden = json.loads((GOLDEN / 'golden.json').read_text(encoding='utf-8'))
        for c in cases():
            if c[1] and (c[1][0] if c[0] == 'object' else c[1].get('type')) == 'task':
                with self.subTest(key(c)):
                    self.assertEqual(call(self.hub, c), golden[key(c)])


class SwitchOff(unittest.TestCase):
    def test_issue_is_unknown_and_agent_the_placeholder(self):
        with tempfile.TemporaryDirectory(prefix='orchestra-desk-off-') as tmp:
            fixture_db(Path(tmp) / 'project')                # die Datenbank liegt da – ohne Schalter wird sie nicht gelesen
            hub = FakeHost(tmp, data())
            try:
                self.assertIsNone(hub.runtime.orchestra)
                with self.assertRaisesRegex(ValueError, 'unknown_object_type'):
                    hub.objects_view({'type': 'issue'})
                self.assertEqual(hub.objects_view({'type': 'agent'}), {'type': 'agent', 'items': []})
                with self.assertRaisesRegex(ValueError, 'unknown_object_type'):
                    hub.objects_view({'type': 'agent', 'id': 'A-CODER'})
            finally:
                hub.close()


if __name__ == '__main__':
    unittest.main()
