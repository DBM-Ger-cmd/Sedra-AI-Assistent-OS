"""T4 der Harness-Shell: Harness-Projekte (D-E3)."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.harness import projekte


class ProjekteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'projekt'
        self.root.mkdir()

    def schreibe(self, text):
        (self.root / 'local_config').mkdir(exist_ok=True)
        (self.root / 'local_config' / projekte.DATEI).write_text(text, encoding='utf-8')

    def test_standard_ohne_datei(self):
        p = projekte.laden(self.root)
        self.assertEqual(len(p), 1)
        self.assertEqual((p[0]['id'], p[0]['name']), ('sedra-entwicklung', 'Sedra Entwicklung'))
        self.assertEqual(p[0]['schreibbereich'], ['runtime/**', 'docs/**', 'redesign/**'])
        self.assertTrue((Path(p[0]['wurzel']) / 'runtime' / 'src' / 'guppi_runtime').is_dir(), 'Wurzel = dieses Repo')
        self.assertFalse((self.root / 'local_config').exists(), 'es wird nichts in local_config geschrieben')

    def test_gueltige_datei(self):
        self.schreibe(f"projekte:\n  - id: eigen\n    name: Eigen\n    wurzel: '{self.tmp.name}'\n    schreibbereich: [docs/**]\n")
        p = projekte.laden(self.root)
        self.assertEqual(p[0]['id'], 'eigen')

    def test_ungueltige_datei_gibt_fehler_mit_grund(self):
        faelle = {
            'projekte: []\n': 'projekte_liste_fehlt',
            'projekte:\n  - id: Gross\n': 'id_ungueltig',
            "projekte:\n  - id: a\n    wurzel: 'C:/gibt/es/nicht/xyz'\n": 'wurzel_ungueltig',
            'projekte: [\n': 'datei_unlesbar',
        }
        for text, grund in faelle.items():
            self.schreibe(text)
            with self.assertRaises(projekte.ProjektFehler) as ctx:
                projekte.laden(self.root)
            self.assertIn(grund, str(ctx.exception), text)

    def test_schreibbereich_ausserhalb_wird_abgelehnt(self):
        for muster in ('../**', '/etc/**', 'C:/Windows/**', 'docs/../../x'):
            self.schreibe(f"projekte:\n  - id: a\n    wurzel: '{self.tmp.name}'\n    schreibbereich: ['{muster}']\n")
            with self.assertRaises(projekte.ProjektFehler, msg=muster):
                projekte.laden(self.root)

    def test_pfade_ausserhalb_der_wurzel(self):
        p = {'id': 'a', 'wurzel': str(self.root), 'schreibbereich': ['docs/**', 'runtime/**']}
        self.assertTrue(projekte.im_schreibbereich(p, 'docs/LOGBUCH.md'))
        self.assertTrue(projekte.im_schreibbereich(p, self.root / 'runtime' / 'src' / 'x.py'))
        self.assertFalse(projekte.im_schreibbereich(p, 'local_config/x.yaml'))
        self.assertFalse(projekte.im_schreibbereich(p, 'docs/../local_config/x.yaml'))
        self.assertFalse(projekte.im_schreibbereich(p, '../anderes/docs/x.md'))
        self.assertFalse(projekte.im_schreibbereich(p, Path(self.tmp.name) / 'docs' / 'x.md'))
        self.assertIsNone(projekte.relativ(p, '../x'))


if __name__ == '__main__':
    unittest.main()
