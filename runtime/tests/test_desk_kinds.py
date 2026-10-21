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


if __name__ == '__main__':
    if sys.argv[1:] == ['record']:
        setUpModule()
        try:
            print('aufgezeichnet:', record(), 'Fälle')
        finally:
            tearDownModule()
    else:
        unittest.main()
