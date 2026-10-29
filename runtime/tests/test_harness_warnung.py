"""Warnung beim Überschreiben einer bestehenden Datei (Nachtrag 434b108, Captain 29.10.2026): ohne Modell, mit dem echten Guard.

Schwellen: mehr als 50 Zeilen der alten Datei entfernt, oder mehr als 30 %. W-1: erster Aufruf nur Hinweis ans Modell, nichts geschrieben,
keine Karte. W-2: derselbe Aufruf noch einmal → Karte mit Warnung. datei_aendern und neue Dateien sind nie betroffen."""
import json
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import katalog
from guppi_runtime.harness.freigabe import Karten, Kiste, oeffentlich
from guppi_runtime.harness.werkzeuge import Werkzeuge, ersetzung_warnung

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
MISSION = 'M-WARNUNG'


class Schwellen(unittest.TestCase):
    def test_wenig_entfernt_ist_keine_warnung(self):
        alt = '\n'.join(f'Zeile {i}' for i in range(100))
        neu = '\n'.join(f'Zeile {i}' for i in range(20, 100))            # 20 von 100 = 20 %, 20 Zeilen
        self.assertIsNone(ersetzung_warnung(alt, neu))

    def test_mehr_als_fuenfzig_zeilen_ist_warnung(self):
        alt = '\n'.join(f'Zeile {i}' for i in range(200))
        neu = '\n'.join(f'Zeile {i}' for i in range(51, 200))            # 51 entfernt, 149 bleiben: > 50 Zeilen
        w = ersetzung_warnung(alt, neu)
        self.assertEqual((w['entfernt'], w['alt'], w['neu']), (51, 200, 0))
        self.assertIn('Ersetzt die ganze Datei: 51 von 200 Zeilen gelöscht, 0 neu.', w['text'])

    def test_mehr_als_dreissig_prozent_ist_warnung(self):
        alt = '\n'.join(f'Zeile {i}' for i in range(10))
        neu = '\n'.join(f'Zeile {i}' for i in range(4, 10))              # 4 von 10 = 40 %
        self.assertEqual(ersetzung_warnung(alt, neu)['entfernt'], 4)

    def test_umbruch_zaehlt_nicht_als_loeschung(self):
        alt = 'ein Satz\nnoch einer'
        self.assertIsNone(ersetzung_warnung(alt, 'ein Satz\nnoch einer\n'))

    def test_leere_alte_datei_nie_warnung(self):
        self.assertIsNone(ersetzung_warnung('', 'neu\n' * 200))


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'projekt'
        (root / 'docs').mkdir(parents=True)
        self.gross = root / 'docs' / 'gross.md'
        self.gross.write_text('\n'.join(f'Eintrag {i}' for i in range(120)) + '\n', encoding='utf-8')
        self.klein = root / 'docs' / 'klein.md'
        self.klein.write_text('eins\nzwei\n', encoding='utf-8')
        self.root = root
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        projekt = {'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': ['docs/**']}
        self.regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        self.w = Werkzeuge(projekt, guard=self.guard, mission_id=MISSION, regeln=self.regeln)
        self.karten = Karten(Path(self.tmp.name) / 'karten')
        self.kiste = Kiste(self.w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id='S-00000001')


class Vorbereiten(Basis):
    def test_ersetzen_der_grossen_datei_traegt_die_warnung_im_plan(self):
        plan = self.w.vorbereiten('datei_schreiben', {'pfad': 'docs/gross.md', 'inhalt': 'nur noch eine Zeile\n'})
        self.assertIsNotNone(plan['warnung'])
        self.assertEqual(plan['warnung']['alt'], 120)

    def test_kleine_aenderung_ohne_warnung(self):
        plan = self.w.vorbereiten('datei_schreiben', {'pfad': 'docs/klein.md', 'inhalt': 'eins\nzwei\ndrei\n'})
        self.assertIsNone(plan['warnung'])

    def test_datei_aendern_ist_nie_betroffen(self):
        plan = self.w.vorbereiten('datei_aendern', {'pfad': 'docs/gross.md', 'alt': 'Eintrag 0\n', 'neu': 'x\n'})
        self.assertIsNone(plan.get('warnung'))

    def test_neue_datei_ist_nie_betroffen(self):
        plan = self.w.vorbereiten('datei_schreiben', {'pfad': 'docs/neu.md', 'inhalt': 'x\n' * 300})
        self.assertIsNone(plan['warnung'])


class HinweisUndKarte(Basis):
    """W-1 und W-2 über die Kiste (dieselbe Stelle, an der die Schleife die Aufrufe bekommt)."""

    def test_erster_aufruf_nur_hinweis_nichts_geschrieben_keine_karte(self):
        vorher = self.gross.read_text(encoding='utf-8')
        out = self.kiste.aufruf('datei_schreiben', {'pfad': 'docs/gross.md', 'inhalt': 'nur eine Zeile\n'})
        self.assertEqual(out['status'], 'hinweis')
        self.assertIn('Ersetzt die ganze Datei', out['ergebnis'])
        self.assertIn('datei_aendern', out['ergebnis'])
        self.assertFalse(out['wirkung'])
        self.assertEqual(self.gross.read_text(encoding='utf-8'), vorher, 'nichts geschrieben')
        self.assertEqual(self.karten.alle(), [], 'noch keine Karte')

    def test_zweiter_gleicher_aufruf_wird_karte_mit_warnung(self):
        args = {'pfad': 'docs/gross.md', 'inhalt': 'nur eine Zeile\n'}
        self.kiste.aufruf('datei_schreiben', args)
        out = self.kiste.aufruf('datei_schreiben', args, antwort_id='A-TEST0001')
        self.assertEqual(out['status'], 'wartet')
        karte = self.karten.laden(out['karte']['karte_id'])
        self.assertIsNotNone(karte['warnung'])
        self.assertIn('Ersetzt die ganze Datei: 120 von 120 Zeilen gelöscht', karte['warnung']['text'])
        self.assertEqual(oeffentlich(karte)['warnung'], karte['warnung'], 'die Oberfläche bekommt die Warnung')

    def test_anderer_inhalt_ist_wieder_ein_erster_hinweis(self):
        self.kiste.aufruf('datei_schreiben', {'pfad': 'docs/gross.md', 'inhalt': 'eins\n'})
        out = self.kiste.aufruf('datei_schreiben', {'pfad': 'docs/gross.md', 'inhalt': 'zwei\n'})
        self.assertEqual(out['status'], 'hinweis', 'die Zustimmung gilt nur für genau diese Ersetzung')

    def test_kleine_aenderung_geht_wie_bisher_zur_karte_ohne_warnung(self):
        out = self.kiste.aufruf('datei_schreiben', {'pfad': 'docs/klein.md', 'inhalt': 'eins\nzwei\ndrei\n'})
        self.assertEqual(out['status'], 'wartet')
        self.assertIsNone(self.karten.laden(out['karte']['karte_id'])['warnung'])

    def test_datei_aendern_geht_ohne_hinweis_zur_karte(self):
        out = self.kiste.aufruf('datei_aendern', {'pfad': 'docs/gross.md', 'alt': 'Eintrag 5\n', 'neu': 'Eintrag fünf\n'})
        self.assertEqual(out['status'], 'wartet')
        self.assertIsNone(self.karten.laden(out['karte']['karte_id'])['warnung'])


if __name__ == '__main__':
    unittest.main()
