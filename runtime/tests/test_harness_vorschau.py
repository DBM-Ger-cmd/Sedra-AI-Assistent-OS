"""Stufe 6 N5 (rein, ohne Server): der Lese-Weg der Vorschau – Pfadprüfung, Pflicht „im Verlauf“, Sperre durch Katalog und Vorbehalt, Grenzen, Binärdateien."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.harness import katalog, vorschau


def verlauf(*pfade, name='datei_schreiben'):
    return [{'typ': 'werkzeug', 'name': name, 'args': {'pfad': p}} for p in pfade]


class VorschauTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='vorschau-')
        self.w = Path(self.tmp.name)
        (self.w / 'docs').mkdir()
        (self.w / 'docs' / 'a.md').write_text('# Titel\nzwei\n', encoding='utf-8')
        self.regeln = katalog.laden(self.w)['regeln']

    def tearDown(self):
        self.tmp.cleanup()

    def lesen(self, pfad, eintraege=None, **kw):
        return vorschau.lesen(self.w, self.regeln, verlauf('docs/a.md') if eintraege is None else eintraege, pfad, **kw)

    def test_datei_aus_dem_verlauf_wird_gelesen(self):
        out = self.lesen('docs/a.md')
        self.assertEqual((out['status'], out['zeilen'], out['gekuerzt']), ('ok', 2, False))
        self.assertIn('# Titel', out['text'])
        self.assertEqual(self.lesen('docs\\a.md')['pfad'], 'docs/a.md', 'Schrägstriche werden vereinheitlicht')

    def test_pfad_muss_im_verlauf_stehen(self):
        for eintraege in ([], verlauf('docs/b.md'), verlauf('docs/a.md', name='befehl')):
            with self.assertRaisesRegex(vorschau.VorschauFehler, 'pfad_nicht_im_verlauf'):
                self.lesen('docs/a.md', eintraege)

    def test_datei_einer_wartenden_karte_gilt_als_im_verlauf(self):
        karte = [{'typ': 'karte', 'werkzeug': 'datei_aendern', 'args': {'pfad': 'docs/a.md', 'alt': 'a', 'neu': 'b'}}]
        self.assertEqual(self.lesen('docs/a.md', karte)['status'], 'ok')
        with self.assertRaises(vorschau.VorschauFehler):
            self.lesen('docs/a.md', [{'typ': 'karte', 'werkzeug': 'befehl', 'args': {'pfad': 'docs/a.md'}}])

    def test_ungueltige_pfade(self):
        for p in ('', '  ', '../x', 'docs/../../x', '/etc/passwd', 'C:/x', 'a\0b', None):
            with self.assertRaises(vorschau.VorschauFehler, msg=repr(p)):
                self.lesen(p, verlauf(str(p)) if p else [])

    def test_gesperrt_durch_katalog_oder_vorbehalt(self):
        (self.w / '.env').write_text('GEHEIM=1\n', encoding='utf-8')
        out = vorschau.lesen(self.w, self.regeln, verlauf('.env'), '.env')
        self.assertEqual(out['status'], 'gesperrt')
        self.assertNotIn('text', out)

    def test_fehlende_binaere_und_grosse_dateien(self):
        self.assertEqual(self.lesen('docs/weg.md', verlauf('docs/weg.md'))['status'], 'fehlt')
        (self.w / 'docs' / 'b.bin').write_bytes(b'ab\0cd')
        self.assertEqual(self.lesen('docs/b.bin', verlauf('docs/b.bin')), {'status': 'binaer', 'pfad': 'docs/b.bin', 'groesse': 5})
        (self.w / 'docs' / 'g.md').write_text(''.join(f'Zeile {i}\n' for i in range(50)), encoding='utf-8')
        out = self.lesen('docs/g.md', verlauf('docs/g.md'), zeilen_max=10)
        self.assertEqual((out['zeilen'], out['gekuerzt']), (10, True))
        out = self.lesen('docs/g.md', verlauf('docs/g.md'), bytes_max=30)
        self.assertTrue(out['gekuerzt'])

    def test_verweis_aus_dem_projekt_heraus_wird_nicht_gelesen(self):
        aussen = Path(self.tmp.name + '-aussen')
        aussen.mkdir()
        try:
            (aussen / 's.txt').write_text('geheim', encoding='utf-8')
            try:
                (self.w / 'docs' / 'link').symlink_to(aussen, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest('Verknüpfungen nicht erlaubt')
            with self.assertRaisesRegex(vorschau.VorschauFehler, 'pfad_ausserhalb'):
                self.lesen('docs/link/s.txt', verlauf('docs/link/s.txt'))
        finally:
            for p in aussen.iterdir():
                p.unlink()
            aussen.rmdir()


if __name__ == '__main__':
    unittest.main()
