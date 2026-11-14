"""DesktopKarteTest für W3: Karte mit update_desktop Aktion."""
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import katalog
from sedra_runtime.harness.freigabe import Karten, Kiste, beantworten
from sedra_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
MISSION = 'M-HARNESS'


class DesktopKarteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'projekt'
        (root / 'docs').mkdir(parents=True)
        (root / 'runtime').mkdir()
        self.root = root
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        self.projekt = {'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': ['docs/**', 'runtime/**']}
        self.regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        self.w = Werkzeuge(self.projekt, guard=self.guard, mission_id=MISSION, regeln=self.regeln,
                          desktop_stand=lambda profil=None: __import__('sedra_runtime.harness.desktop', fromlist=['laden']).laden(str(root)))
        self.karten = Karten(Path(self.tmp.name) / 'karten')
        self.kiste = Kiste(self.w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id='S-00000001')

    def test_karte_wird_mit_update_desktop_angelegt(self):
        # desktop_aendern erzeugt Karte mit update_desktop
        r = self.kiste.aufruf('desktop_aendern', {'marke': {'name': 'Test', 'akzent': '#333333'}})
        self.assertEqual(r['status'], 'wartet')
        self.assertIn('karte', r)
        self.assertEqual(r['karte']['art'], 'werkzeug')
        self.assertEqual(r['karte']['werkzeug'], 'desktop_aendern')
        self.assertIsNotNone(r['karte'].get('gate_id'), 'Karte hat Gate-ID (update_desktop-Aktion)')

    def test_karte_profil_wechseln_mit_update_desktop(self):
        # Profil anlegen
        import sedra_runtime.harness.desktop as dt
        dt.speichern(str(self.root), {'marke': {'name': 'Test'}})
        dt.profil_speichern(str(self.root), 'test-profil', 'Test', '', '')
        r = self.kiste.aufruf('profil_wechseln', {'profil': 'test-profil'})
        self.assertEqual(r['status'], 'wartet')
        self.assertIsNotNone(r['karte'].get('gate_id'), 'Karte hat Gate-ID (update_desktop-Aktion)')
        self.assertEqual(r['karte']['args']['profil'], 'test-profil')

    def test_beantworten_erlauben_fuehrt_zu_ausfuehrung(self):
        import sedra_runtime.harness.desktop as dt
        dt.speichern(str(self.root), {'marke': {'name': 'Alt'}})
        r = self.kiste.aufruf('desktop_aendern', {'marke': {'name': 'Neu'}})
        karte_id = r['karte']['karte_id']
        # Captain erlaubt
        out = beantworten(self.karten, karte_id, 'erlauben', von='captain', guard=self.guard, werkzeuge_fuer=lambda k: self.w)
        self.assertEqual(out['status'], 'ok')
        self.assertTrue(out['wirkung'])
        self.assertIn('Desktop aktualisiert', out['ergebnis'])
        wahl = dt.laden(str(self.root))
        self.assertEqual(wahl['marke']['name'], 'Neu')

    def test_beantworten_ablehnen_aendert_nichts(self):
        import sedra_runtime.harness.desktop as dt
        dt.speichern(str(self.root), {'marke': {'name': 'Alt'}})
        r = self.kiste.aufruf('desktop_aendern', {'marke': {'name': 'Neu'}})
        karte_id = r['karte']['karte_id']
        out = beantworten(self.karten, karte_id, 'ablehnen', von='captain', guard=self.guard, werkzeuge_fuer=lambda k: self.w)
        self.assertEqual(out['status'], 'abgelehnt')
        self.assertFalse(out['wirkung'])
        wahl = dt.laden(str(self.root))
        self.assertEqual(wahl['marke']['name'], 'Alt')


if __name__ == '__main__':
    unittest.main()
