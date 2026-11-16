"""T4 der Harness-Shell: Harness-Projekte (D-E3)."""
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.harness import projekte


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
        self.assertTrue((Path(p[0]['wurzel']) / 'runtime' / 'src' / 'sedra_runtime').is_dir(), 'Wurzel = dieses Repo')
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

    def test_master_feld_mm01(self):
        """MM-01: `master` ist eine Liste relativer Muster; fehlt es, gibt es keinen Master; ein ungültiges Feld nennt den Grund."""
        kopf = f"projekte:\n  - id: eigen\n    name: Eigen\n    wurzel: '{self.tmp.name}'\n    schreibbereich: [docs/**]\n"
        self.schreibe(kopf)
        self.assertNotIn('master', projekte.laden(self.root)[0])
        self.schreibe(kopf + '    master: [runtime/**, docs/**]\n')
        self.assertEqual(projekte.laden(self.root)[0]['master'], ['runtime/**', 'docs/**'])
        for roh in ('"runtime/**"', '["../x/**"]', '["C:/x"]', '[""]'):
            self.schreibe(kopf + f'    master: {roh}\n')
            with self.assertRaises(projekte.ProjektFehler) as k:
                projekte.laden(self.root)
            self.assertIn('master_ungueltig', str(k.exception), roh)

    def test_master_feld_bleibt_beim_schreiben_der_laufzeitdatei(self):
        daten = {'projekte': [{'id': 'a', 'name': 'A', 'wurzel': str(self.root), 'schreibbereich': ['docs/**'], 'master': ['docs/**']},
                              {'id': 'b', 'name': 'B', 'wurzel': str(self.root), 'schreibbereich': ['docs/**']}], 'vorgaben': {}}
        projekte.laufzeit_schreiben(self.root, daten)
        zurueck = projekte.laufzeit_laden(self.root)['projekte']
        self.assertEqual(zurueck[0]['master'], ['docs/**'])
        self.assertNotIn('master', zurueck[1])

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
