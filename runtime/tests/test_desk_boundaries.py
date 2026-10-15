"""Modus und die vier Grenzen (desk/boundaries.py, COCKPIT_MODUL_v1 §3 und Regel 7).

Hier stehen die Zusagen, auf die sich der Captain verlässt: kein Standard im Code, zwei Grenzen nie frei, nichts läuft vor der
einen Bestätigung, eine Einmal-Erlaubnis gilt einmal – und jeder dieser Schritte steht im Audit."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import boundaries as b

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'


class Rules(unittest.TestCase):
    def test_netz_and_loeschen_can_never_be_free(self):
        """P0/P4: dafür gibt es `frei` nicht – weder im Modus noch von Hand."""
        for kind in ('netz', 'loeschen'):
            with self.subTest(kind):
                with self.assertRaises(b.BoundaryError):
                    b.check_values('vertraut', {'projekt': 'frei', 'netz': 'fragt', 'loeschen': 'fragt', 'kosten': 'fragt', kind: 'frei'})
        for mode, values in b.MODE_DEFAULTS.items():
            with self.subTest(mode):
                self.assertNotEqual(values['netz'], 'frei')
                self.assertNotEqual(values['loeschen'], 'frei')

    def test_the_proposal_comes_from_the_project_not_from_the_code(self):
        empty = b.propose({'empty': True})
        self.assertEqual(empty['mode'], 'sandbox')
        self.assertIn('leer', empty['reason'])
        foreign = b.propose({'empty': False, 'git': True, 'foreign': True, 'files': 400})
        self.assertEqual(foreign['mode'], 'beobachten')
        self.assertEqual(foreign['boundaries']['projekt'], 'zu', 'fremder Code wird erst gelesen')
        own = b.propose({'empty': False, 'git': True, 'own_tool': True, 'files': 12})
        self.assertEqual(own['mode'], 'vertraut')
        for case in (empty, foreign, own):
            self.assertTrue(case['reason'].strip().endswith('.'), 'die Begründung ist ein Satz')

    def test_looking_at_a_folder_does_not_open_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(b.look_at(root)['empty'])
            (root / 'app.py').write_text('x = 1\n', encoding='utf-8')
            look = b.look_at(root)
            self.assertFalse(look['empty'])
            self.assertEqual(look['files'], 1)
            self.assertFalse(look['git'])
            (root / '.git').mkdir()
            self.assertTrue(b.look_at(root)['git'])
            self.assertTrue(b.look_at(root)['foreign'])
            (root / 'tool.yaml').write_text('tool: {}\n', encoding='utf-8')
            self.assertFalse(b.look_at(root)['foreign'], 'ein eigenes Werkzeugprojekt ist nicht fremd')

    def test_a_boundary_decides_in_three_words(self):
        values = {'projekt': 'fragt', 'netz': 'zu', 'loeschen': 'zu', 'kosten': 5000}
        self.assertEqual(b.decide('projekt', values), 'fragt')
        self.assertEqual(b.decide('netz', values), 'zu')
        self.assertEqual(b.decide('kosten', values, amount=100), 'frei')
        self.assertEqual(b.decide('kosten', values, amount=5000), 'fragt')
        with self.assertRaises(b.BoundaryError):
            b.decide('fliegen', values)

    def test_a_crossing_offers_the_three_ways_and_a_closed_one_offers_two(self):
        values = {'projekt': 'fragt', 'netz': 'zu', 'loeschen': 'zu', 'kosten': 'fragt'}
        asks = b.crossing('P-1', 'projekt', 'app.py überschreiben', values)
        self.assertEqual(asks['ways'], ['einmal', 'aendern', 'ablehnen'])
        closed = b.crossing('P-1', 'netz', 'pypi.org', values)
        self.assertEqual(closed['ways'], ['aendern', 'ablehnen'], 'was zu ist, lässt sich nicht einmal öffnen – nur ändern')
        self.assertIsNone(b.crossing('P-1', 'kosten', 'M-1', {**values, 'kosten': 9000}, amount=10),
                          'unter der Grenze passiert gar nichts')

    def test_the_cost_limit_is_measured_not_guessed(self):
        self.assertIsNone(b.measured_limit(None))
        self.assertIsNone(b.measured_limit(0))
        self.assertEqual(b.measured_limit(4120), 8240, 'bis gemessen ist: das Doppelte der teuersten Aufgabe')

    def test_the_sentence_says_all_four_boundaries(self):
        text = b.sentence('sandbox', {'projekt': 'fragt', 'netz': 'zu', 'loeschen': 'zu', 'kosten': 8240})
        for word in ('Sandbox', 'Projekt', 'Netz', 'Löschen', 'Kosten', '8240'):
            self.assertIn(word, text)

    def test_the_store_keeps_only_what_it_may(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = b.Store(Path(tmp))
            self.assertIsNone(store.get('P-1'))
            store.put('P-1', 'sandbox', {'projekt': 'fragt', 'netz': 'zu', 'loeschen': 'zu', 'kosten': 'fragt'}, '2026-10-14T20:00:00Z')
            got = store.get('P-1')
            self.assertEqual(got['mode'], 'sandbox')
            self.assertEqual(got['boundaries']['netz'], 'zu')
            with self.assertRaises(b.BoundaryError):
                store.put('P-2', 'vertraut', {'projekt': 'frei', 'netz': 'frei', 'loeschen': 'fragt', 'kosten': 'fragt'}, 'jetzt')
            self.assertIsNone(store.get('P-2'), 'eine abgelehnte Grenze wird auch nicht halb geschrieben')


class ThroughTheHub(unittest.TestCase):
    """Der ganze Weg: Vorschlag, eine Bestätigung, Überschreitung, drei Wege."""

    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-bound-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)
        self.project = self.hub.new_project({'name': 'Export'})
        workspace = self.hub.runtime.filesystem_tool._resolve(self.project['workspace_path'], must_exist=True)
        (workspace / 'README.md').write_text('# Export\n', encoding='utf-8')

    def confirm(self):
        self.hub.act({'type': 'boundary', 'id': 'projekt', 'verb': 'bestaetigen'})
        item = next(d for d in self.hub.decisions_view()['items'] if d['kind'] == 'request:boundaries')
        return self.hub.decide({'id': item['id'], 'way': 'freigeben_und_anwenden'})

    def test_nothing_is_set_before_the_captain_said_yes_once(self):
        view = self.hub.boundaries_view()
        self.assertFalse(view['confirmed'])
        self.assertIn('Noch nicht bestätigt', view['note'])
        self.assertTrue(view['reason'])
        self.assertEqual(self.hub.cross_boundary('projekt', 'app.py schreiben')['verdict'], 'unbestätigt')
        self.assertEqual(self.hub.strip_view()['mode']['value'], 'nicht bestätigt')

    def test_confirming_is_a_decision_like_every_other(self):
        self.confirm()
        view = self.hub.boundaries_view()
        self.assertTrue(view['confirmed'])
        self.assertEqual(view['mode'], 'sandbox')
        self.assertEqual(self.hub.strip_view()['mode']['value'], 'Sandbox')
        self.assertIn('PROJECT_BOUNDARIES_SET', [e['event_type'] for e in self.hub.audit_view()['events']])

    def test_a_crossing_becomes_a_decision_and_stops_the_action(self):
        self.confirm()
        out = self.hub.cross_boundary('projekt', 'app.py überschreiben')
        self.assertEqual(out['verdict'], 'fragt')
        waiting = [d for d in self.hub.decisions_view()['items'] if d['kind'] == 'boundary']
        self.assertEqual(len(waiting), 1)
        self.assertEqual(waiting[0]['ways'], ['einmal', 'aendern', 'ablehnen'])
        self.assertIn('BOUNDARY_CROSSED', [e['event_type'] for e in self.hub.audit_view()['events']])

    def test_once_means_once(self):
        self.confirm()
        self.hub.cross_boundary('projekt', 'app.py überschreiben')
        item = next(d for d in self.hub.decisions_view()['items'] if d['kind'] == 'boundary')
        self.hub.decide({'id': item['id'], 'way': 'einmal'})
        self.assertEqual(self.hub.cross_boundary('projekt', 'app.py überschreiben')['verdict'], 'frei')
        self.assertEqual(self.hub.cross_boundary('projekt', 'app.py überschreiben')['verdict'], 'fragt',
                         'die Einmal-Erlaubnis ist verbraucht')
        kinds = [e['event_type'] for e in self.hub.audit_view()['events']]
        self.assertIn('BOUNDARY_OPENED_ONCE', kinds)
        self.assertIn('BOUNDARY_PASSED_ONCE', kinds)

    def test_refusing_leaves_nothing_behind(self):
        self.confirm()
        self.hub.cross_boundary('projekt', 'app.py überschreiben')
        item = next(d for d in self.hub.decisions_view()['items'] if d['kind'] == 'boundary')
        out = self.hub.decide({'id': item['id'], 'way': 'ablehnen'})
        self.assertIn('Nichts ist passiert', out['result']['note'])
        self.assertEqual(self.hub.decisions_view()['summary']['count'], 0)
        self.assertEqual(self.hub.cross_boundary('projekt', 'app.py überschreiben')['verdict'], 'fragt')

    def test_change_leads_to_the_decision_about_the_boundary_itself(self):
        self.confirm()
        self.hub.cross_boundary('netz', 'pypi.org')
        item = next(d for d in self.hub.decisions_view()['items'] if d['kind'] == 'boundary')
        self.assertEqual(item['ways'], ['aendern', 'ablehnen'], 'Netz steht auf zu')
        out = self.hub.decide({'id': item['id'], 'way': 'aendern'})
        self.assertEqual(out['result']['open']['type'], 'boundary')
        self.assertEqual(self.hub.cross_boundary('netz', 'pypi.org')['verdict'], 'zu', 'geändert ist damit nichts')

    def test_an_unused_once_permission_expires(self):
        """Härtung: ein „ja“ von heute früh gilt am Abend nicht mehr für eine Handlung, an die niemand mehr denkt."""
        import time
        self.confirm()
        self.hub.cross_boundary('projekt', 'app.py überschreiben')
        item = next(d for d in self.hub.decisions_view()['items'] if d['kind'] == 'boundary')
        self.hub.decide({'id': item['id'], 'way': 'einmal'})
        self.hub.boundary_once[next(iter(self.hub.boundary_once))] = time.time() - self.hub.ONCE_SECONDS - 1
        self.assertEqual(self.hub.cross_boundary('projekt', 'app.py überschreiben')['verdict'], 'fragt')
        self.assertIn('BOUNDARY_ONCE_EXPIRED', [e['event_type'] for e in self.hub.audit_view()['events']])

    def test_the_same_action_asks_once_not_ten_times(self):
        """Härtung: ein Werkzeug in der Schleife füllt weder die Liste des Captains noch den Speicher."""
        self.confirm()
        first = self.hub.cross_boundary('projekt', 'app.py überschreiben')['decision']
        for _ in range(5):
            again = self.hub.cross_boundary('projekt', 'app.py überschreiben')
        self.assertEqual(again['decision']['id'], first['id'])
        self.assertTrue(again['again'])
        self.assertEqual(len([d for d in self.hub.decisions_view()['items'] if d['kind'] == 'boundary']), 1)


    def test_the_take_over_asks_the_boundary_before_the_gate(self):
        """Die Deckungsprüfung vor `guard.create_gate` (§10): das einzige Verb, das heute ins Projekt schreibt."""
        from guppi_runtime.desk import actions as desk_actions
        self.confirm()
        stopped = desk_actions._boundary_first(self.hub, 'projekt', 'Dateien dieses Kandidaten überschreiben')
        self.assertIsNotNone(stopped)
        self.assertEqual(stopped['status'], 'boundary')
        self.assertEqual(stopped['decision']['ways'], ['einmal', 'aendern', 'ablehnen'])


if __name__ == '__main__':
    unittest.main()
