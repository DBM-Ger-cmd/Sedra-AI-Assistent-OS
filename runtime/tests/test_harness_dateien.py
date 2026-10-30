"""Stufe 6 (rein, ohne Server): die Dateiauswahl für „+“ und „@“ – Ordneransicht, Suche, Sperre durch Katalog und Vorbehalt, übersprungene Ordner, Grenzen, Pfadprüfung."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.harness import dateien, katalog, schleife, vorschau


class DateienTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='dateien-')
        self.w = Path(self.tmp.name)
        for rel, text in {'docs/a.md': 'a', 'docs/sub/b.md': 'bb', 'README.md': 'r', '.env': 'GEHEIM=1', 'node_modules/x/y.js': 'js', '.git/config': 'c',
                          'runtime_data/log.txt': 'l'}.items():
            p = self.w / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding='utf-8')
        self.regeln = katalog.laden(self.w)['regeln']

    def tearDown(self):
        self.tmp.cleanup()

    def liste(self, **kw):
        return dateien.liste(self.w, self.regeln, **kw)

    def pfade(self, out):
        return [e['pfad'] for e in out['eintraege']]

    def test_wurzel_zeigt_ordner_vor_dateien_ohne_gesperrtes_und_uebersprungenes(self):
        out = self.liste()
        self.assertEqual(self.pfade(out), ['docs', 'README.md'])
        self.assertEqual([e['art'] for e in out['eintraege']], ['ordner', 'datei'])

    def test_ordneransicht(self):
        out = self.liste(ordner='docs')
        self.assertEqual(self.pfade(out), ['docs/sub', 'docs/a.md'])
        self.assertEqual(out['ordner'], 'docs')
        self.assertEqual(self.liste(ordner='gibt/es/nicht')['eintraege'], [])

    def test_suche_im_ganzen_projekt(self):
        self.assertEqual(self.pfade(self.liste(q='B.MD')), ['docs/sub/b.md'])
        self.assertEqual(sorted(self.pfade(self.liste(q='.md'))), ['README.md', 'docs/a.md', 'docs/sub/b.md'])
        self.assertEqual(self.liste(q='nichts-davon')['eintraege'], [])

    def test_gesperrtes_und_uebersprungenes_taucht_nie_auf(self):
        for q in ('env', 'config', 'y.js', 'log.txt', 'GEHEIM'):
            self.assertEqual(self.liste(q=q)['eintraege'], [], q)

    def test_grenzen(self):
        for i in range(10):
            (self.w / 'docs' / f'f{i}.md').write_text('x', encoding='utf-8')
        out = self.liste(q='f', limit=3)
        self.assertEqual((len(out['eintraege']), out['gekuerzt']), (3, True))
        out = self.liste(q='.md', besucht_max=2)
        self.assertTrue(out['gekuerzt'])

    def test_ungueltiger_ordner(self):
        for o in ('../x', '/etc', 'C:/x', 'docs/../../x'):
            with self.assertRaises(vorschau.VorschauFehler, msg=o):
                self.liste(ordner=o)

    def test_verknuepfung_wird_nicht_verfolgt(self):
        aussen = Path(self.tmp.name + '-aussen')
        aussen.mkdir()
        try:
            (aussen / 's.txt').write_text('geheim', encoding='utf-8')
            try:
                (self.w / 'docs' / 'link').symlink_to(aussen, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest('Verknüpfungen nicht erlaubt')
            self.assertNotIn('docs/link', self.pfade(self.liste(ordner='docs')))
            self.assertEqual(self.liste(q='s.txt')['eintraege'], [])
        finally:
            for p in aussen.iterdir():
                p.unlink()
            aussen.rmdir()

    def test_systemprompt_erklaert_den_anhang(self):
        self.assertIn('@pfad', schleife.system_prompt('p', ['datei_lesen']))
        self.assertIn('@pfad', schleife.SYSTEM)


if __name__ == '__main__':
    unittest.main()
