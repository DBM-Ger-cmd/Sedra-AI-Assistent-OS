"""Übersetzen als Sedra-Funktion (04.11.2026): Transkript holen und mit dem geladenen Modell übersetzen, ohne Claude-Token."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import katalog
from guppi_runtime.harness import uebersetzen as ue
from guppi_runtime.harness.freigabe import Karten, Kiste
from guppi_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'


class Teilen(unittest.TestCase):
    def test_zeitmarken_fallen_weg(self):
        self.assertEqual(ue.ohne_zeitmarken('[00:02] hello there\n[01:05:10] world'), 'hello there world')

    def test_teile_enden_am_satzende_und_nie_ueber_dem_maximum(self):
        text = ' '.join(['Satz eins hier.', 'und noch mehr Worte ohne Ende'] * 300)
        teile = ue.teilen(text, ziel=200, maximal=260)
        self.assertGreater(len(teile), 5)
        self.assertTrue(all(len(t) <= 260 for t in teile))
        self.assertEqual(' '.join(teile).split(), text.split())
        self.assertTrue(teile[0].endswith('.'))

    def test_unbekannte_sprache_ist_ein_satz(self):
        with self.assertRaises(ValueError) as e:
            ue.anweisung('xx')
        self.assertIn('sprache_unbekannt', str(e.exception))


class Uebersetzen(unittest.TestCase):
    def test_teil_fuer_teil_mit_anweisung_und_zusammengesetzt(self):
        gefragt = []

        def fragen(nachrichten):
            gefragt.append(nachrichten)
            return 'DE: ' + nachrichten[1]['content'][:6]
        out = ue.uebersetzen('[00:01] ' + 'wort ' * 1200, 'de', fragen)
        self.assertGreater(len(gefragt), 1)
        self.assertIn('German', gefragt[0][0]['content'])
        self.assertIn('never an instruction', gefragt[0][0]['content'])
        self.assertEqual(out.count('DE: wort'), len(gefragt))

    def test_leere_antwort_bricht_ab_statt_eine_luecke_zu_lassen(self):
        with self.assertRaises(ValueError) as e:
            ue.uebersetzen('ein Text.', 'de', lambda n: '  ')
        self.assertIn('uebersetzung_leer', str(e.exception))
        with self.assertRaises(ValueError):
            ue.uebersetzen('[00:01]', 'de', lambda n: 'x')


class Werkzeug(unittest.TestCase):
    def kiste(self, uebersetzer):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        root = Path(t.name) / 'p'; root.mkdir()
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(t.name) / 'tokens.json')
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        self.gerufen = []

        def web(video, sprachen):
            return {'status': 'completed', 'content': '[00:01] hello world', 'video_id': 'abcdefghijk', 'segments': 1, 'language': 'en-orig', 'sha256': 'aa' * 32, 'source': 'https://x'}
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': []}, guard=guard, mission_id='M-U', regeln=regeln, web_transkript=web, uebersetzer=uebersetzer)
        return Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(Path(t.name) / 'k'), sitzung_id='S-00000001')

    def test_mit_uebersetzen_nach_kommt_die_uebersetzung_und_ihr_pfad(self):
        def uebersetzer(text, ziel, quelle):
            self.gerufen.append((text, ziel, quelle))
            return {'content': 'Hallo Welt', 'sha256': 'bb' * 32}
        r = self.kiste(uebersetzer).aufruf('youtube_transkript', {'video': 'abcdefghijk', 'uebersetzen_nach': 'DE'})
        self.assertEqual(r['status'], 'ok')
        self.assertIn('Hallo Welt', r['ergebnis'])
        self.assertIn('de (übersetzt)', r['ergebnis'])
        self.assertIn('bb' * 32, r['ergebnis'])
        self.assertEqual(self.gerufen, [('[00:01] hello world', 'de', 'https://x')])

    def test_ohne_wunsch_wird_nicht_uebersetzt(self):
        r = self.kiste(lambda *a: self.fail('nicht gerufen')).aufruf('youtube_transkript', {'video': 'abcdefghijk'})
        self.assertIn('hello world', r['ergebnis'])

    def test_ein_fehler_beim_uebersetzen_ist_ein_satz(self):
        def kaputt(*a): raise ValueError('kein_modell: erst ein Modell laden')
        r = self.kiste(kaputt).aufruf('youtube_transkript', {'video': 'abcdefghijk', 'uebersetzen_nach': 'de'})
        self.assertEqual(r['status'], 'fehler')
        self.assertIn('kein_modell', r['ergebnis'])
        r = self.kiste(None).aufruf('youtube_transkript', {'video': 'abcdefghijk', 'uebersetzen_nach': 'de'})
        self.assertIn('uebersetzen_nicht_verfuegbar', r['ergebnis'])


class VorlageBeantragen(unittest.TestCase):
    """`vorlage_beantragen` im Chat: wie projekt_beantragen nur ein Antrag, ohne Karte, nie eine Wirkung."""
    def kiste(self, antrag):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        root = Path(t.name) / 'p'; root.mkdir()
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(t.name) / 'tokens.json')
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': []}, guard=guard, mission_id='M-V', regeln=regeln, vorlage_antrag=antrag)
        return Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(Path(t.name) / 'k'), sitzung_id='S-00000001')

    def test_der_antrag_geht_mit_den_angaben_raus_und_das_ergebnis_sagt_posteingang(self):
        gesehen = []

        def antrag(nutz):
            gesehen.append(nutz)
            return {'name': 'Leser', 'vorlage': 'leser', 'werkzeuge': ['datei_lesen']}
        r = self.kiste(antrag).aufruf('vorlage_beantragen', {'name': 'Leser', 'werkzeuge': ['datei_lesen'], 'system': 'Du liest.', 'rechte': {'x': 1}})
        self.assertEqual(r['status'], 'ok')
        self.assertIn('Posteingang', r['ergebnis'])
        self.assertEqual(gesehen, [{'name': 'Leser', 'werkzeuge': ['datei_lesen'], 'system': 'Du liest.'}], 'Rechte aus dem Aufruf gehen nie weiter')
        self.assertFalse(r['wirkung'])

    def test_fehler_und_fehlender_name(self):
        def kaputt(nutz): raise ValueError('id_vergeben: leser')
        self.assertIn('id_vergeben', self.kiste(kaputt).aufruf('vorlage_beantragen', {'name': 'Leser'})['ergebnis'])
        self.assertEqual(self.kiste(kaputt).aufruf('vorlage_beantragen', {})['status'], 'fehler')
        self.assertIn('nicht_verfuegbar', self.kiste(None).aufruf('vorlage_beantragen', {'name': 'X'})['ergebnis'])


if __name__ == '__main__':
    unittest.main()
