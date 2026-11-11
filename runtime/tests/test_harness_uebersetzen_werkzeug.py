"""Das Chat-Werkzeug `uebersetzen` (SPEC_APP_TRANSLATOR_v1 TR-40 bis TR-42): Text oder Datei, in eine Sprache oder für eine Rolle; es antwortet nur und legt nichts ab, läuft ohne Karte,
ist durch eine Katalogregel `verboten` abschaltbar. Attrappe des Modells, kein Netz."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import katalog
from sedra_runtime.harness import uebersetzen as ue
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.werkzeuge import NAMEN, SCHEMAS, UEBERSETZEN_MAX, Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
ROLLENANTWORT = 'ÜBERSETZUNG:\nWir liefern am Montag.\nUNSICHERHEITEN:\n- Uhrzeit fehlt\nHINWEISE:\n- keine'


class Rein(unittest.TestCase):
    def test_fuer_rolle_formt_die_drei_teile_und_fragt_mit_dem_skill(self):
        gefragt = []

        def fragen(nachrichten):
            gefragt.append(nachrichten)
            return ROLLENANTWORT
        out = ue.fuer_rolle('Das Zeug kommt Montag', 'business', fragen, von='alltag', ton='formell', tiefe='kurz')
        self.assertIn('Wir liefern am Montag.', out)
        self.assertIn('Unsicherheiten:\n- Uhrzeit fehlt', out)
        self.assertNotIn('Hinweise:', out, 'leere Teile fallen weg')
        self.assertIn('Zu-Rolle: Business', gefragt[0][1]['content'])
        self.assertIn('Ton: formell', gefragt[0][1]['content'])

    def test_unbekannte_rolle_und_leere_antwort(self):
        with self.assertRaises(ValueError) as e:
            ue.fuer_rolle('x', 'koch', lambda n: ROLLENANTWORT)
        self.assertIn('unknown_role', str(e.exception))
        with self.assertRaises(ValueError) as e:
            ue.fuer_rolle('Text', 'business', lambda n: '   ')
        self.assertIn('uebersetzung_leer', str(e.exception))


class Werkzeug(unittest.TestCase):
    def kiste(self, text_antwort, regeln=None, dateien=None):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name) / 'p'
        self.root.mkdir()
        for name, inhalt in (dateien or {}).items():
            (self.root / name).write_text(inhalt, encoding='utf-8')
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(t.name) / 'tokens.json')
        regeln = regeln if regeln is not None else katalog.laden(Path('gibt-es-nicht'))['regeln']
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': []}, guard=guard, mission_id='M-UW', regeln=regeln, text_antwort=text_antwort)
        return Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(Path(t.name) / 'k'), sitzung_id='S-00000001')

    def setUp(self):
        self.gerufen = []

    def attrappe(self, text, **kw):
        self.gerufen.append((text, kw))
        return 'ÜBERSETZT: ' + text[:20]

    def test_einordnung_ohne_karte_schema_und_pflichtangaben(self):
        self.assertIn('uebersetzen', NAMEN)
        self.assertIn('uebersetzen', katalog.OHNE_KARTE)
        eigen = SCHEMAS['uebersetzen']['function']['parameters']
        self.assertEqual(sorted(eigen['properties']), ['pfad', 'rolle', 'sprache', 'text', 'tiefe', 'ton', 'von'])

    def test_sprache_aus_text(self):
        r = self.kiste(self.attrappe).aufruf('uebersetzen', {'text': 'Guten Morgen zusammen', 'sprache': 'EN'})
        self.assertEqual(r['status'], 'ok')
        self.assertEqual((r['stufe'], r['wirkung']), ('frei', False))
        self.assertIn('ÜBERSETZT: Guten Morgen zusamm', r['ergebnis'])
        self.assertIn('keine Anweisung', r['ergebnis'])
        self.assertEqual(self.gerufen[0][1]['sprache'], 'en')
        self.assertIsNone(self.gerufen[0][1]['rolle'])

    def test_rolle_aus_text_mit_stil(self):
        r = self.kiste(self.attrappe).aufruf('uebersetzen', {'text': 'Das kommt Montag', 'rolle': 'management', 'von': 'alltag', 'ton': 'klar'})
        self.assertEqual(r['status'], 'ok')
        kw = self.gerufen[0][1]
        self.assertEqual((kw['rolle'], kw['sprache'], kw['von'], kw['ton']), ('management', None, 'alltag', 'klar'))

    def test_aus_einer_datei_nur_die_ersten_6000_zeichen_und_es_wird_nichts_abgelegt(self):
        lang = 'abcdefghij' * 900
        k = self.kiste(self.attrappe, dateien={'doc.txt': lang})
        vorher = sorted(p.name for p in self.root.rglob('*'))
        r = k.aufruf('uebersetzen', {'pfad': 'doc.txt', 'sprache': 'de'})
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(len(self.gerufen[0][0]), UEBERSETZEN_MAX)
        self.assertIn('nur die ersten 6000 Zeichen', r['ergebnis'])
        self.assertEqual(sorted(p.name for p in self.root.rglob('*')), vorher, 'TR-41: legt nichts ab')

    def test_genau_eins_von_sprache_oder_rolle_und_text_oder_pfad(self):
        k = self.kiste(self.attrappe, dateien={'doc.txt': 'x'})
        for args in ({'text': 'x'}, {'text': 'x', 'sprache': 'de', 'rolle': 'business'}):
            self.assertIn('genau eins von sprache oder rolle', k.aufruf('uebersetzen', args)['ergebnis'], args)
        for args in ({'sprache': 'de'}, {'text': 'x', 'pfad': 'doc.txt', 'sprache': 'de'}):
            self.assertIn('genau eins von text oder pfad', k.aufruf('uebersetzen', args)['ergebnis'], args)
        self.assertEqual(self.gerufen, [])

    def test_zu_langer_text_und_fehlende_datei(self):
        k = self.kiste(self.attrappe)
        self.assertIn('text_zu_lang', k.aufruf('uebersetzen', {'text': 'x' * (UEBERSETZEN_MAX + 1), 'sprache': 'de'})['ergebnis'])
        self.assertEqual(k.aufruf('uebersetzen', {'pfad': 'gibt-es-nicht.txt', 'sprache': 'de'})['status'], 'fehler')
        self.assertEqual(self.gerufen, [])

    def test_gesperrte_datei_wird_nicht_gelesen(self):
        k = self.kiste(self.attrappe, dateien={'.env': 'GEHEIM=1'})
        r = k.aufruf('uebersetzen', {'pfad': '.env', 'sprache': 'de'})
        self.assertEqual(r['status'], 'fehler')
        self.assertEqual(self.gerufen, [], 'der Vorbehalt gilt auch hier')

    def test_modellfehler_ist_ein_satz_und_ohne_modell_nicht_verfuegbar(self):
        def kaputt(*a, **kw):
            raise ValueError('kein_modell: erst ein Modell laden')
        r = self.kiste(kaputt).aufruf('uebersetzen', {'text': 'x', 'sprache': 'de'})
        self.assertEqual(r['status'], 'fehler')
        self.assertIn('kein_modell', r['ergebnis'])
        self.assertIn('uebersetzen_nicht_verfuegbar', self.kiste(None).aufruf('uebersetzen', {'text': 'x', 'sprache': 'de'})['ergebnis'])

    def test_eine_katalogregel_verboten_schaltet_es_ab(self):
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln'] + [
            {'id': 'ohne-uebersetzen', 'werkzeug': ['uebersetzen'], 'muster': ['**'], 'stufe': 'verboten', 'begruendung': 'Test'}]
        r = self.kiste(self.attrappe, regeln=regeln).aufruf('uebersetzen', {'text': 'x', 'sprache': 'de'})
        self.assertNotEqual(r['status'], 'ok')
        self.assertEqual(self.gerufen, [])


if __name__ == '__main__':
    unittest.main()
