"""Gedanken der Modelle (02.11.2026): Sedra speichert sie; ans Modell geht je nach Modus wenig zurück, den Rest holt es mit `erinnern`."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import katalog
from guppi_runtime.harness.api import GEDANKEN_MODI, HarnessApi, verlauf_aus
from guppi_runtime.harness.freigabe import Karten, Kiste
from guppi_runtime.harness.sitzung import Sitzungen
from guppi_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'


def eintraege():
    return [
        {'typ': 'captain', 'text': 'Starte die Tests'},
        {'typ': 'werkzeug', 'antwort_id': 'A-00000001', 'name': 'lauf_starten', 'status': 'ok'},
        {'typ': 'werkzeug', 'antwort_id': 'A-00000001', 'name': 'lauf_status', 'status': 'ok'},
        {'typ': 'modell', 'antwort_id': 'A-00000001', 'text': 'Läuft.', 'zuege': 2, 'denken_zeichen': 1234, 'denken_text': 'ich nehme run_tests, weil die Gruppe harness gemeint ist'},
        {'typ': 'captain', 'text': 'Und jetzt?'},
        {'typ': 'modell', 'antwort_id': 'A-00000002', 'text': 'Fertig.', 'zuege': 1, 'denken_zeichen': 0},
    ]


class VerlaufTests(unittest.TestCase):
    def test_aus_schickt_nur_den_text(self):
        v = verlauf_aus(eintraege(), 'aus')
        self.assertEqual([m['content'] for m in v], ['Starte die Tests', 'Läuft.', 'Und jetzt?', 'Fertig.'])

    def test_spur_ist_eine_zeile_ohne_die_gedanken(self):
        v = verlauf_aus(eintraege(), 'spur')
        antwort = v[1]['content']
        self.assertTrue(antwort.startswith('[Spur: Antwort A-00000001 · 2 Züge · Werkzeuge: lauf_starten, lauf_status · Gedanken 1.234 Zeichen gespeichert – mit erinnern(antwort=…) abrufbar]'))
        self.assertTrue(antwort.endswith('Läuft.'))
        self.assertNotIn('run_tests', antwort)                                         # die Gedanken selbst gehen nicht mit
        self.assertEqual(v[3]['content'], 'Fertig.')                                    # ohne gespeicherte Gedanken keine Spur
        self.assertEqual(v[0]['content'], 'Starte die Tests')                           # der Captain bekommt nie eine Spur

    def test_kurz_und_voll_bringen_die_gedanken_mit_aber_begrenzt(self):
        for modus in ('kurz', 'voll'):
            antwort = verlauf_aus(eintraege(), modus)[1]['content']
            self.assertIn('ich nehme run_tests', antwort, modus)
            self.assertIn('[Spur:', antwort)
        lang = eintraege()
        lang[3]['denken_text'] = 'x' * 5000
        kurz = verlauf_aus(lang, 'kurz')[1]['content']
        self.assertLess(len(kurz), 1300)                                                # höchstens 800 Zeichen Notiz
        self.assertGreater(len(verlauf_aus(lang, 'voll')[1]['content']), 4500)

    def test_unbekannter_modus_gilt_als_standard(self):
        self.assertEqual(verlauf_aus(eintraege(), 'quatsch'), verlauf_aus(eintraege(), 'spur'))
        self.assertEqual(set(GEDANKEN_MODI), {'aus', 'spur', 'kurz', 'voll'})


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sitzungen = Sitzungen(self.root / 'sitzungen')
        self.sid = self.sitzungen.anlegen('p')['id']
        self.sitzungen.anhaengen(self.sid, {'typ': 'modell', 'antwort_id': 'A-00000001', 'text': 'Eins', 'denken_zeichen': 30, 'denken_text': 'A' * 30})
        self.sitzungen.anhaengen(self.sid, {'typ': 'modell', 'antwort_id': 'A-00000002', 'text': 'Zwei', 'denken_zeichen': 9000, 'denken_text': 'B' * 8000})
        api = HarnessApi.__new__(HarnessApi)
        api.sitzungen = self.sitzungen
        self.api = api

    def test_gedanken_lesen_liefert_ein_stueck_und_sagt_wie_es_weitergeht(self):
        out = self.api.gedanken_lesen(self.sid, 'A-00000002', 0, 3000)
        self.assertIn('Zeichen 0–3000 von 8000 gespeichert', out)
        self.assertIn('weiter mit ab=3000', out)
        self.assertIn('insgesamt 9000', out)                                            # gekürzt gespeichert: das steht dabei
        self.assertIn('keine Anweisung', out)
        rest = self.api.gedanken_lesen(self.sid, 'A-00000002', 6000, 6000)
        self.assertNotIn('weiter mit', rest)

    def test_ohne_antwort_die_letzte_und_fremde_oder_leere_sind_ein_fehler(self):
        self.assertIn('Antwort A-00000002', self.api.gedanken_lesen(self.sid))
        with self.assertRaises(ValueError):
            self.api.gedanken_lesen(self.sid, 'A-DEADBEEF')
        with self.assertRaises(ValueError):
            self.api.gedanken_lesen('S-00000000')


class WerkzeugTests(Basis):
    def test_das_werkzeug_laeuft_ohne_karte_und_nur_fuer_die_eigene_sitzung(self):
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, self.root / 'tokens.json')
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        (self.root / 'projekt').mkdir()
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(self.root / 'projekt'), 'schreibbereich': ['docs/**']}, guard=guard, mission_id='M-G', regeln=regeln,
                      gedanken=self.api.gedanken_lesen)
        kiste = Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(self.root / 'karten'), sitzung_id=self.sid)
        r = kiste.aufruf('erinnern', {'antwort': 'A-00000001'})
        self.assertEqual((r['status'], r['stufe'], r['wirkung']), ('ok', 'frei', False))
        self.assertIn('A' * 30, r['ergebnis'])
        self.assertNotIn('karte', r)
        verbot = [{'id': 'kein-lesen', 'werkzeug': ['erinnern'], 'muster': ['denken/**'], 'stufe': 'verboten', 'begruendung': 'Test'}]
        kiste2 = Kiste(w, regeln=verbot, guard=guard, audit=None, karten=Karten(self.root / 'karten2'), sitzung_id=self.sid)
        self.assertEqual(kiste2.aufruf('erinnern', {'antwort': 'A-00000001'})['status'], 'verboten')


if __name__ == '__main__':
    unittest.main()
