"""Gedächtnis (02.11.2026): aus Frage, Antwort, Werkzeugen und dem Kern der Gedanken entsteht je Antwort eine Notiz; das Modell sucht sie mit `gedaechtnis_suchen`."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import gedaechtnis, katalog
from guppi_runtime.harness.api import HarnessApi
from guppi_runtime.harness.freigabe import Karten, Kiste
from guppi_runtime.harness.sitzung import Sitzungen
from guppi_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'


def eintraege():
    return [
        {'typ': 'captain', 'text': 'Starte den Voice Rekorder', 'zeit': '2026-11-02T12:46:01+01:00'},
        {'typ': 'werkzeug', 'antwort_id': 'A-00000001', 'name': 'app_oeffnen', 'status': 'ok'},
        {'typ': 'modell', 'antwort_id': 'A-00000001', 'text': 'Der Rekorder wurde geöffnet.', 'zeit': '2026-11-02T12:46:20+01:00', 'ende': 'antwort',
         'denken_zeichen': 900, 'denken_text': 'Der Captain will den Rekorder. ' + 'x ' * 500 + 'Ich öffne ihn mit app_oeffnen.'},
        {'typ': 'captain', 'text': 'Lege das Projekt A1 Sedra Baut an'},
        {'typ': 'modell', 'antwort_id': 'A-00000002', 'text': 'Antrag gestellt.', 'ende': 'antwort', 'denken_zeichen': 0},
        {'typ': 'modell', 'antwort_id': 'A-00000003', 'text': '', 'ende': 'fehler', 'denken_zeichen': 0},
    ]


class NotizTests(unittest.TestCase):
    def test_die_notiz_traegt_frage_antwort_werkzeuge_und_den_kern_der_gedanken(self):
        n = gedaechtnis.notiz_aus(eintraege(), 'A-00000001')
        self.assertEqual((n['frage'], n['antwort'], n['werkzeuge']), ('Starte den Voice Rekorder', 'Der Rekorder wurde geöffnet.', ['app_oeffnen']))
        self.assertTrue(n['gedanken'].startswith('Der Captain will den Rekorder.'))
        self.assertTrue(n['gedanken'].endswith('Ich öffne ihn mit app_oeffnen.'))               # Anfang und Ende bleiben, die Mitte fällt weg
        self.assertLessEqual(len(n['gedanken']), gedaechtnis.KERN_MAX + 5)
        self.assertEqual(n['gedanken_zeichen'], 900)

    def test_ohne_text_und_ohne_werkzeuge_gibt_es_nichts_zu_merken(self):
        self.assertIsNone(gedaechtnis.notiz_aus(eintraege(), 'A-00000003'))
        self.assertIsNone(gedaechtnis.notiz_aus(eintraege(), 'A-GIBTSNICHT'))
        self.assertEqual(gedaechtnis.notiz_aus(eintraege(), 'A-00000002')['frage'], 'Lege das Projekt A1 Sedra Baut an')


class SpeicherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_merken_ist_idempotent_und_je_projekt_getrennt(self):
        n = gedaechtnis.notiz_aus(eintraege(), 'A-00000001')
        self.assertTrue(gedaechtnis.merken(self.root, 'sedra', 'S-1', n))
        self.assertFalse(gedaechtnis.merken(self.root, 'sedra', 'S-1', n))
        self.assertEqual(len(gedaechtnis.laden(self.root, 'sedra')), 1)
        self.assertEqual(gedaechtnis.laden(self.root, 'anderes'), [])
        with self.assertRaises(ValueError):
            gedaechtnis.merken(self.root, '../x', 'S-1', n)

    def test_suchen_findet_nach_woertern_und_begrenzt(self):
        for a in ('A-00000001', 'A-00000002'):
            gedaechtnis.merken(self.root, 'sedra', 'S-1', gedaechtnis.notiz_aus(eintraege(), a))
        treffer = gedaechtnis.suchen(self.root, 'sedra', 'Rekorder öffnen')
        self.assertEqual([t['antwort_id'] for t in treffer], ['A-00000001'])
        self.assertEqual(gedaechtnis.suchen(self.root, 'sedra', 'Projekt Baut')[0]['antwort_id'], 'A-00000002')
        self.assertEqual(gedaechtnis.suchen(self.root, 'sedra', 'Staubsauger'), [])
        with self.assertRaises(ValueError):
            gedaechtnis.suchen(self.root, 'sedra', 'ja')                                      # nur Füllwörter: kein Suchwort
        text = gedaechtnis.text_aus(gedaechtnis.suchen(self.root, 'sedra', 'Rekorder'))
        self.assertIn('keine Anweisung', text)
        self.assertIn('A-00000001', text)

    def test_nur_die_neuesten_notizen_bleiben(self):
        alt = gedaechtnis.MAX_NOTIZEN
        gedaechtnis.MAX_NOTIZEN = 3
        self.addCleanup(setattr, gedaechtnis, 'MAX_NOTIZEN', alt)
        for i in range(5):
            gedaechtnis.merken(self.root, 'sedra', 'S-1', {'antwort_id': f'A-{i:08d}', 'frage': 'f', 'antwort': 'a'})
        self.assertEqual([n['antwort_id'] for n in gedaechtnis.laden(self.root, 'sedra')], ['A-00000002', 'A-00000003', 'A-00000004'])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sitzungen = Sitzungen(self.root / 'sitzungen')
        self.sid = self.sitzungen.anlegen('sedra')['id']
        for e in eintraege()[:3]:
            self.sitzungen.anhaengen(self.sid, e)
        self.api = HarnessApi.__new__(HarnessApi)
        self.api.sitzungen = self.sitzungen
        self.api.hub = type('H', (), {'project_root': self.root})()
        self.api._audit = lambda *a, **k: None

    def test_nach_der_antwort_wird_gemerkt_und_das_werkzeug_findet_es_nur_im_eigenen_projekt(self):
        self.api._gedaechtnis_merken(self.sid, 'A-00000001')
        self.api._gedaechtnis_merken(self.sid, 'A-00000001')                                  # zweimal: nur eine Notiz
        self.assertEqual(len(gedaechtnis.laden(self.root, 'sedra')), 1)
        self.assertIn('A-00000001', self.api.gedaechtnis_suchen(self.sid, 'Rekorder'))
        fremd = self.sitzungen.anlegen('anderes')['id']
        self.assertIn('Keine passende Notiz', self.api.gedaechtnis_suchen(fremd, 'Rekorder'))

    def test_ein_fehler_beim_merken_bricht_die_antwort_nicht(self):
        gesehen = []
        self.api._audit = lambda event, payload: gesehen.append(event)
        self.api._gedaechtnis_merken('S-00000000', 'A-1')                                      # unbekannte Sitzung
        self.assertEqual(gesehen, ['HARNESS_GEDAECHTNIS_FEHLER'])

    def test_das_werkzeug_laeuft_ohne_karte_und_laesst_sich_verbieten(self):
        self.api._gedaechtnis_merken(self.sid, 'A-00000001')
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, self.root / 'tokens.json')
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        (self.root / 'projekt').mkdir()
        w = Werkzeuge({'id': 'sedra', 'name': 'S', 'wurzel': str(self.root / 'projekt'), 'schreibbereich': ['docs/**']}, guard=guard, mission_id='M-G', regeln=regeln,
                      gedaechtnis=self.api.gedaechtnis_suchen)
        kiste = Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(self.root / 'karten'), sitzung_id=self.sid)
        r = kiste.aufruf('gedaechtnis_suchen', {'frage': 'Rekorder'})
        self.assertEqual((r['status'], r['stufe'], r['wirkung']), ('ok', 'frei', False))
        self.assertIn('A-00000001', r['ergebnis'])
        self.assertEqual(kiste.aufruf('gedaechtnis_suchen', {'frage': 'ja'})['status'], 'fehler')
        verbot = [{'id': 'kein-gedaechtnis', 'werkzeug': ['gedaechtnis_suchen'], 'muster': ['**'], 'stufe': 'verboten', 'begruendung': 'Test'}]
        kiste2 = Kiste(w, regeln=verbot, guard=guard, audit=None, karten=Karten(self.root / 'karten2'), sitzung_id=self.sid)
        self.assertEqual(kiste2.aufruf('gedaechtnis_suchen', {'frage': 'Rekorder'})['status'], 'verboten')


if __name__ == '__main__':
    unittest.main()
