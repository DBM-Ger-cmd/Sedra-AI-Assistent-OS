"""Die Desk-Registrierung (Spec 0, D1, KERN-04).

`Golden` hält fest, was `objects_view` und `object_view` für die neun heutigen Typen liefern – aufgezeichnet mit dem Code vor dem
Umbau (K0.7) auf einem Fake-Host, dessen Quellen aus `fixtures/desk_golden/data.json` kommen. Nach dem Umbau an das Register muss
derselbe Test unverändert grün sein. Neu aufzeichnen (nur mit dem alten Code): `python tests/test_desk_kinds.py record`."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

if __name__ == '__main__':
    sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / 'src')]

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.uix_server import UIXHub

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
GOLDEN = Path(__file__).resolve().parent / 'fixtures' / 'desk_golden'
TYPES = ('task', 'intent', 'candidate', 'model', 'skill', 'decision', 'project', 'agent', 'boundary')


def data():
    return json.loads((GOLDEN / 'data.json').read_text(encoding='utf-8'))


class _Missions:
    def __init__(self, records):
        self.records = {m['identity']['mission_id']: m for m in records}

    def list(self):
        return [json.loads(json.dumps(m)) for m in self.records.values()]

    def load(self, mid):
        if mid not in self.records:
            raise FileNotFoundError(mid)
        return json.loads(json.dumps(self.records[mid]))


class _Intents:
    def __init__(self, entries):
        self.entries = {e['id']: e for e in entries}

    def list(self, project_id=None):
        return [dict(e) for e in self.entries.values()]

    def get(self, intent_id):
        e = self.entries.get(str(intent_id))
        return dict(e) if e else None


class _Library:
    def __init__(self, own):
        self.own = own

    def view(self):
        return {'own': [dict(s) for s in self.own]}


class _Projects:
    def __init__(self, items):
        self.items = items

    def list(self):
        return [dict(p) for p in self.items]


class FakeHost(UIXHub):
    """Ein echter Hub, dessen Quellen die Testdaten sind: Missionen, Kandidatenberichte, Modelle, Grenzen, Entscheidungen,
    Skills, Projekte, Vorhaben. Die Leser in `object_view`/`objects_view` laufen unverändert darüber."""

    def __init__(self, root, fixture):
        super().__init__(Path(root) / 'project', ARCH)
        self.fixture = fixture
        self.runtime.missions = _Missions(fixture['missions'])
        self.library = _Library(fixture['skills'])
        self.projects = _Projects(fixture['projects'])
        self._fake_intents = _Intents(fixture['intents'])

    @property
    def intents(self):
        return self._fake_intents

    def _candidate_report(self, mid):
        report = self.fixture['candidate_reports'].get(mid)
        return json.loads(json.dumps(report)) if report is not None else None

    def models_view(self):
        return json.loads(json.dumps(self.fixture['models']))

    def boundaries_view(self, payload=None):
        pid = (payload or {}).get('project_id') or self.fixture['active_project']
        b = self.fixture['boundaries'].get(pid) or self.fixture['boundaries']['_kein_projekt']
        return json.loads(json.dumps(b))

    def decisions_view(self):
        items = json.loads(json.dumps(self.fixture['decisions']))
        return {'items': items, 'summary': {'count': len(items)}}


def cases():
    """Die Aufrufe, in fester Reihenfolge: je Typ die Liste, jedes Objekt der Testdaten, ein fehlendes; dazu die Fehler."""
    out = [('objects', {'type': t}) for t in TYPES]
    ids = {'task': ['M-READY', 'M-RUN', 'M-WAIT', 'M-DONE', 'M-CAND', 'M-APPL', 'M-WEG'],
           'candidate': ['M-CAND', 'M-APPL', 'M-READY', 'M-WEG'],
           'model': ['coder.local_primary', 'chat.local', 'cloud.off', 'fehlt'],
           'intent': ['V-1', 'V-2', 'V-3', 'V-4', 'V-WEG'],
           'boundary': ['projekt', 'alle', 'P-1', 'P-2', 'P-WEG'],
           'decision': ['gate:HG-1', 'crossing:C-1', 'gate:WEG'],
           'skill': ['debug', 'leer', 'weg'],
           'project': ['P-1', 'OhneId', 'Export', 'P-WEG'],
           'agent': ['unterarbeiter']}
    for t in TYPES:
        for oid in ids[t]:
            out.append(('object', (t, oid)))
            out.append(('objects', {'type': t, 'id': oid}))
    out += [('objects', {'type': 'raumschiff'}), ('objects', {'type': ''}), ('objects', {}), ('objects', {'type': ' task '}),
            ('object', ('raumschiff', 'x')), ('objects', {'type': 'agent', 'id': ''})]
    return out


def call(hub, case):
    how, arg = case
    try:
        result = hub.object_view(*arg) if how == 'object' else hub.objects_view(dict(arg))
        return {'result': json.loads(json.dumps(result))}
    except ValueError as exc:
        return {'error': str(exc)}


def key(case):
    return case[0] + ':' + json.dumps(case[1], ensure_ascii=False, sort_keys=True)


def record():
    with tempfile.TemporaryDirectory(prefix='desk-golden-') as tmp:
        hub = FakeHost(tmp, data())
        try:
            out = {key(c): call(hub, c) for c in cases()}
        finally:
            hub.close()
    (GOLDEN / 'golden.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return len(out)


class Golden(unittest.TestCase):
    """Aufgezeichnet mit dem Code vor dem Umbau (K0.7). Muss nach K0.10/K0.11 unverändert grün sein."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='desk-golden-')
        cls.hub = FakeHost(cls.tmp.name, data())
        cls.golden = json.loads((GOLDEN / 'golden.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls.hub.close()
        cls.tmp.cleanup()

    def test_every_call_answers_as_recorded(self):
        seen = set()
        for c in cases():
            k = key(c)
            seen.add(k)
            with self.subTest(k):
                self.assertIn(k, self.golden, 'Fall fehlt in der Aufzeichnung')
                self.assertEqual(call(self.hub, c), self.golden[k])
        self.assertEqual(sorted(set(self.golden) - seen), [], 'die Aufzeichnung hat Fälle, die der Test nicht mehr ruft')

    def test_the_recording_covers_the_nine_types_and_the_errors(self):
        for t in TYPES:
            self.assertIn(key(('objects', {'type': t})), self.golden)
        self.assertEqual(self.golden[key(('object', ('agent', 'unterarbeiter')))], {'error': 'unknown_object_type'})
        self.assertEqual(self.golden[key(('objects', {'type': 'agent'}))], {'result': {'type': 'agent', 'items': []}})
        self.assertEqual(self.golden[key(('objects', {'type': 'raumschiff'}))], {'error': 'unknown_object_type'})
        self.assertEqual(self.golden[key(('object', ('task', 'M-WEG')))]['result']['state'], 'nicht gefunden')
        # OP-13: die Einzelansicht einer Entscheidung behält ihre Wege, die Liste verliert sie
        one = self.golden[key(('object', ('decision', 'gate:HG-1')))]['result']
        listed = self.golden[key(('objects', {'type': 'decision'}))]['result']['items'][0]
        self.assertEqual([a['verb'] for a in one['actions']], ['einmal', 'ablehnen'])
        self.assertEqual(listed['actions'], [])


class Register(unittest.TestCase):
    """Das Register mit den eingebauten Typen (K0.10): dieselben Typen und Verben wie vorher, Beispieltyp `echo`, Fehlerfälle D5."""

    def test_the_builtin_types_and_verbs_are_the_ones_of_before(self):
        from guppi_runtime.desk import actions, objects
        self.assertEqual(objects.TYPES, TYPES)
        self.assertEqual({k: list(v) for k, v in actions.VERBS.items()},
                         {'task': ['ausfuehren'], 'candidate': ['testen', 'nachpruefen', 'uebernehmen', 'zuruecknehmen'],
                          'intent': ['aufgabe_machen'], 'boundary': ['bestaetigen', 'aendern'],
                          'model': ['laden', 'entladen', 'testen']})

    def test_echo_is_reached_through_extensions_only(self):
        import desk_echo_kind
        from guppi_runtime.desk import actions, builtin_kinds, extensions
        reg = builtin_kinds.new_registry()
        audits = []
        loaded = extensions.load(reg, None, modules=('desk_echo_kind',), audit=lambda e, p: audits.append(e))
        self.assertEqual([m.__name__ for m in loaded], ['desk_echo_kind'])
        self.assertEqual(audits, [])
        view = reg.request(None, {'type': 'echo', 'id': 'eins'})
        self.assertEqual((view['title'], [a['verb'] for a in view['actions']]), ('Erstes Echo', ['rufen']))
        self.assertEqual([i['id'] for i in reg.request(None, {'type': 'echo'})['items']], ['eins', 'zwei'])
        self.assertEqual(reg.request(None, {'type': 'echo', 'id': 'drei'})['state'], 'nicht gefunden')

        class Hub:
            kinds = reg

            def object_view(self, kind, oid):
                return reg.view(self, kind, oid)
        del desk_echo_kind.CALLS[:]
        out = actions.run(Hub(), 'echo', 'zwei', 'rufen', {'text': 'hallo'})
        self.assertEqual((out['status'], out['result']), ('done', {'echo': 'hallo'}))
        out = actions.run_type(Hub(), 'echo', 'anlegen', {'text': 'neu'})
        self.assertEqual((out['id'], out['result']), (None, {'angelegt': 'neu'}))
        self.assertEqual(desk_echo_kind.CALLS, [('zwei', {'text': 'hallo'}), (None, {'text': 'neu'})])
        with self.assertRaisesRegex(ValueError, 'id_required'):
            actions.run_type(Hub(), 'echo', 'rufen', {})
        with self.assertRaisesRegex(ValueError, 'id_required'):
            actions.run_type(Hub(), 'task', 'ausfuehren', {})
        with self.assertRaisesRegex(ValueError, 'unknown_object_type'):
            actions.run(None, 'echo', 'eins', 'rufen', {}, lookup=lambda k, i: view)
        self.assertNotIn('echo', builtin_kinds.builtin().names(), 'das eingebaute Register kennt den Beispieltyp nicht')

    def test_a_duplicate_type_is_refused_and_the_rest_keeps_running(self):
        from guppi_runtime.desk import builtin_kinds, extensions
        reg = builtin_kinds.new_registry()
        with self.assertRaisesRegex(ValueError, 'kind_already_registered'):
            reg.register(reg.Kind('task', 'Noch eine Aufgabe', lambda h, o: None, lambda h, p: []))

        class Twice:
            __name__ = 'zweimal'

            @staticmethod
            def register(registry, hub):
                registry.register(registry.Kind('neu', 'Neu', lambda h, o: None, lambda h, p: []))
                registry.register(registry.Kind('model', 'Modell 2', lambda h, o: None, lambda h, p: []))
        audits = []
        loaded = extensions.load(reg, None, modules=('zweimal',), importer=lambda n: Twice, audit=lambda e, p: audits.append((e, p)))
        self.assertEqual(loaded, [])
        self.assertNotIn('neu', reg.names(), 'eine halbe Registrierung wird zurückgenommen')
        self.assertEqual(audits, [('DESK_KIND_REFUSED', {'module': 'zweimal', 'reason': 'kind_already_registered'})])
        self.assertEqual(reg.problems, [{'source': 'zweimal', 'reason': 'kind_already_registered'}])
        self.assertEqual(reg.names(), sorted(TYPES))

    def test_freeze_ends_registration(self):
        from guppi_runtime.desk import builtin_kinds
        reg = builtin_kinds.new_registry()
        reg.freeze()
        with self.assertRaisesRegex(ValueError, 'kinds_frozen'):
            reg.register(reg.Kind('spaet', 'Zu spät', lambda h, o: None, lambda h, p: []))
        with self.assertRaisesRegex(ValueError, 'kinds_frozen'):
            builtin_kinds.builtin().register(reg.Kind('spaet', 'Zu spät', lambda h, o: None, lambda h, p: []))

    def test_only_the_agent_placeholder_may_be_replaced(self):
        from guppi_runtime.desk import builtin_kinds
        reg = builtin_kinds.new_registry()
        with self.assertRaisesRegex(ValueError, 'unknown_object_type'):
            reg.view(None, 'agent', 'x')
        self.assertEqual(reg.listing(None, 'agent'), [])
        agent = reg.Kind('agent', 'Agent', lambda h, o: {'type': 'agent', 'id': o, 'title': o, 'state': 'aktiv', 'summary': o,
                                                         'actions': [], 'links': []}, lambda h, p: [])
        reg.register(agent, replace_placeholder=True)
        self.assertEqual(reg.view(None, 'agent', 'a1')['state'], 'aktiv')
        with self.assertRaisesRegex(ValueError, 'kind_already_registered'):
            reg.register(reg.Kind('task', 'X', lambda h, o: None, lambda h, p: []), replace_placeholder=True)

    def test_a_half_object_is_refused(self):
        from guppi_runtime.desk import builtin_kinds
        reg = builtin_kinds.new_registry()
        reg.register(reg.Kind('halb', 'Halb', lambda h, o: {'type': 'halb', 'id': o}, lambda h, p: [{'type': 'halb'}]))
        for call_ in (lambda: reg.view(None, 'halb', 'x'), lambda: reg.listing(None, 'halb')):
            with self.assertRaisesRegex(ValueError, 'object_shape_invalid'):
                call_()


class Gated(unittest.TestCase):
    """`desk/gated.py` über ein Test-Verb (OP-15): Antrag erzeugt eine Entscheidung, Anwenden nur mit gültigem Einmal-Token."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-gated-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)

    def test_request_waits_for_the_captain_and_apply_runs_exactly_the_binding(self):
        from guppi_runtime.desk import gated
        done = []
        req = gated.request(self.hub, 'echo_test', 'echo_test_action', 'echo:eins', {'describe': 'Echo setzen', 'text': 'hallo'})
        mid = req['mission_id']
        self.assertIn('request:' + mid, [d['id'] for d in self.hub.decisions_view()['items']])
        with self.assertRaisesRegex(ValueError, 'captain_approval_required'):
            gated.apply(self.hub, mid, done.append)
        self.assertEqual(done, [], 'ohne Freigabe läuft nichts')
        self.hub.approve_gate({'mission_id': mid, 'gate_id': req['gate']['gate_id']})
        out = gated.apply(self.hub, mid, lambda b: done.append(b['text']) or 'ok')
        self.assertEqual((out['status'], out['result'], done), ('applied', 'ok', ['hallo']))
        self.assertIn('DESK_GATED_APPLIED', [e['event_type'] for e in self.hub.audit_view()['events']])
        with self.assertRaisesRegex(ValueError, 'captain_approval_required'):
            gated.apply(self.hub, mid, done.append)             # der Token ist verbraucht
        self.assertEqual(done, ['hallo'])

    def test_a_changed_binding_is_not_applied(self):
        from guppi_runtime.desk import gated
        req = gated.request(self.hub, 'echo_test', 'echo_test_action', 'echo:eins', {'describe': 'Echo setzen', 'text': 'hallo'})
        mid = req['mission_id']
        self.hub.approve_gate({'mission_id': mid, 'gate_id': req['gate']['gate_id']})
        m = self.hub.runtime.missions.load(mid)
        m['context'][gated.CONTEXT]['binding']['text'] = 'etwas anderes'
        self.hub.runtime.missions.save(m)
        done = []
        with self.assertRaisesRegex(ValueError, 'captain_approval_invalid'):
            gated.apply(self.hub, mid, done.append)
        self.assertEqual(done, [])
        other = self.hub.create_chat_mission({'intent': 'Nur reden'})['mission']['mission_id']
        with self.assertRaisesRegex(ValueError, 'not_a_gated_request'):
            gated.apply(self.hub, other, done.append)


def audit_payloads(hub, event):
    lines = hub.runtime.audit.path.read_text(encoding='utf-8').splitlines()
    return [e.get('payload') for e in map(json.loads, filter(str.strip, lines)) if e.get('event_type') == event]


def post(url, path, body, headers=None):
    import http.client
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    c = http.client.HTTPConnection(parts.hostname, parts.port, timeout=30)
    try:
        h = {'Content-Type': 'application/json', 'X-GUPPI-Token': parts.fragment, **(headers or {})}
        c.request('POST', path, body=json.dumps(body), headers=h)
        res = c.getresponse()
        return res.status, json.loads(res.read().decode('utf-8') or 'null')
    finally:
        c.close()


class ThroughTheServer(unittest.TestCase):
    """K0.11: `uix_server.py` kennt keine Typnamen mehr; ein Typ aus `extensions` ist über beide Routen erreichbar."""

    @classmethod
    def setUpClass(cls):
        import threading
        from unittest import mock
        from guppi_runtime.desk import extensions
        from guppi_runtime.uix_server import make_server
        cls.tmp = tempfile.TemporaryDirectory(prefix='desk-kinds-http-')
        with mock.patch.object(extensions, 'MODULES', extensions.MODULES + ('desk_echo_kind',)):
            cls.hub = UIXHub(Path(cls.tmp.name) / 'project', ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.hub.close()
        cls.tmp.cleanup()

    def test_echo_through_both_routes(self):
        import desk_echo_kind
        del desk_echo_kind.CALLS[:]
        status, obj = post(self.url, '/api/objects', {'type': 'echo', 'id': 'eins'})
        self.assertEqual((status, obj['title'], [a['verb'] for a in obj['actions']]), (200, 'Erstes Echo', ['rufen']))
        status, listing = post(self.url, '/api/objects', {'type': 'echo'})
        self.assertEqual((status, [i['id'] for i in listing['items']]), (200, ['eins', 'zwei']))
        status, out = post(self.url, '/api/actions', {'type': 'echo', 'id': 'zwei', 'verb': 'rufen', 'args': {'text': 'hallo'}})
        self.assertEqual((status, out['result']), (200, {'echo': 'hallo'}))
        status, out = post(self.url, '/api/actions', {'type': 'echo', 'verb': 'anlegen', 'args': {'text': 'neu'}})
        self.assertEqual((status, out['id'], out['result']), (200, None, {'angelegt': 'neu'}))
        self.assertEqual(desk_echo_kind.CALLS, [('zwei', {'text': 'hallo'}), (None, {'text': 'neu'})])
        actions = audit_payloads(self.hub, 'UIX_ACTION')
        self.assertEqual([(a['type'], a['id'], a['verb']) for a in actions[-2:]], [('echo', 'zwei', 'rufen'), ('echo', '', 'anlegen')])

    def test_a_verb_without_id_needs_a_type_verb(self):
        for body in ({'type': 'task', 'verb': 'ausfuehren'}, {'type': 'echo', 'verb': 'rufen'}, {'type': 'raumschiff', 'verb': 'x'}):
            with self.subTest(body):
                self.assertEqual(post(self.url, '/api/actions', body), (400, {'error': 'bad_request', 'message': 'id_required'}))

    def test_the_registry_is_frozen_after_the_start(self):
        self.assertTrue(self.hub.kinds.frozen)
        self.assertEqual(self.hub.kinds.problems, [])
        self.assertIn('echo', self.hub.kinds.names())
        with self.assertRaisesRegex(ValueError, 'kinds_frozen'):
            self.hub.kinds.register(self.hub.kinds.Kind('spaet', 'Zu spät', lambda h, o: None, lambda h, p: []))

    def test_the_chat_reads_the_verbs_from_the_same_register(self):
        """K0.12: `chat_tools` kennt die Typen mit Verben nicht mehr selbst."""
        from guppi_runtime import chat_tools
        listed = json.loads(chat_tools.ChatTools(self.hub).call('list_actions', {'type': 'echo', 'id': 'eins'}))
        self.assertEqual([a['verb'] for a in listed['actions']], ['rufen'])
        self.assertEqual(sorted(chat_tools.VERB_TYPES), ['boundary', 'candidate', 'intent', 'model', 'task'])
        self.assertNotIn('VERB_TYPES =', Path(chat_tools.__file__).read_text(encoding='utf-8'))

    def test_without_the_extension_echo_is_unknown(self):
        hub = UIXHub(Path(self.tmp.name) / 'ohne', ARCH)
        self.addCleanup(hub.close)
        with self.assertRaisesRegex(ValueError, 'unknown_object_type'):
            hub.objects_view({'type': 'echo'})
        self.assertEqual(hub.objects_view({'type': 'agent'}), {'type': 'agent', 'items': []}, 'orchestra aus: agent bleibt Platzhalter')
        with self.assertRaisesRegex(ValueError, 'unknown_object_type'):
            hub.objects_view({'type': 'issue'})

    def test_uix_server_names_no_type_in_the_object_routes(self):
        import ast
        import inspect
        from guppi_runtime import uix_server
        tree = ast.parse(inspect.getsource(uix_server.UIXHub))
        names = set(TYPES) | {'echo', 'issue', 'routine', 'budget'}
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in ('object_view', 'objects_view', 'act')]:
            with self.subTest(fn.name):
                self.assertEqual([n for n in ast.walk(fn) if isinstance(n, ast.Compare)
                                  and any(isinstance(c, ast.Constant) and c.value in names for c in ast.walk(n))], [])
                consts = {n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
                self.assertEqual(consts & names, set(), 'kein Typname in ' + fn.name)


if __name__ == '__main__':
    if sys.argv[1:] == ['record']:
        setUpModule()
        try:
            print('aufgezeichnet:', record(), 'Fälle')
        finally:
            tearDownModule()
    else:
        unittest.main()
