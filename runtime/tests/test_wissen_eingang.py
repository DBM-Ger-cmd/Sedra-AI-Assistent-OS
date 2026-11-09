"""Der Eingang des Wissens: Teilstücke ablegen, Dialog (ersetzt), Kopieren, Grenzen."""
import base64
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sedra_runtime.wissen import eingang as e  # noqa: E402
from sedra_runtime.wissen.speicher import satz  # noqa: E402

KONFIG = types.SimpleNamespace(je_art={'md': 1000, 'txt': 1000, 'docx': 5000}, datei_max_bytes=1000)


def b64(b):
    return base64.b64encode(b).decode()


class Basis(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.projekt = Path(tmp.name) / 'projekt'
        self.projekt.mkdir()
        self.quelle = Path(tmp.name) / 'quelle'
        self.quelle.mkdir()
        self.s = e.neue_sitzung()
        e.ordner(self.projekt, self.s).mkdir(parents=True)


class Ablegen(Basis):
    def test_teilstuecke_ergeben_die_datei(self):
        e.ablegen(self.projekt, KONFIG, sitzung=self.s, name='a/b.md', offset=0, daten=b64(b'Hallo '))
        r = e.ablegen(self.projekt, KONFIG, sitzung=self.s, name='a/b.md', offset=6, daten=b64(b'Welt'), ende=True)
        self.assertEqual(r['bytes'], 10)
        self.assertEqual((e.ordner(self.projekt, self.s) / 'a' / 'b.md').read_bytes(), b'Hallo Welt')

    def test_falscher_offset_wird_abgelehnt_und_aendert_nichts(self):
        e.ablegen(self.projekt, KONFIG, sitzung=self.s, name='a.md', offset=0, daten=b64(b'abc'))
        with self.assertRaises(ValueError) as c:
            e.ablegen(self.projekt, KONFIG, sitzung=self.s, name='a.md', offset=0, daten=b64(b'abc'))
        self.assertEqual(str(c.exception), 'wis_eingang_offset_ungueltig')
        self.assertEqual((e.ordner(self.projekt, self.s) / 'a.md').read_bytes(), b'abc')

    def test_namen_die_ausbrechen_werden_abgelehnt(self):
        for name in ('../x.md', 'a/../../x.md', 'C:/x.md', '/x.md', 'con.md', 'a:b.md', 'x.md ', '', 'a//.md'):
            with self.assertRaises(ValueError, msg=name):
                e.ablegen(self.projekt, KONFIG, sitzung=self.s, name=name, offset=0, daten=b64(b'x'))
        self.assertEqual(list(e.ordner(self.projekt, self.s).rglob('*')), [])
        self.assertFalse((self.projekt.parent / 'x.md').exists())

    def test_fremde_dateiart_wird_abgelehnt(self):
        with self.assertRaises(ValueError) as c:
            e.ablegen(self.projekt, KONFIG, sitzung=self.s, name='x.exe', offset=0, daten=b64(b'x'))
        self.assertEqual(str(c.exception), 'wis_dateiart_nicht_erlaubt')

    def test_zu_grosse_datei_wird_entfernt(self):
        e.ablegen(self.projekt, KONFIG, sitzung=self.s, name='g.md', offset=0, daten=b64(b'x' * 900))
        with self.assertRaises(ValueError) as c:
            e.ablegen(self.projekt, KONFIG, sitzung=self.s, name='g.md', offset=900, daten=b64(b'x' * 200))
        self.assertEqual(str(c.exception), 'wis_eingang_datei_zu_gross')
        self.assertFalse((e.ordner(self.projekt, self.s) / 'g.md').exists())

    def test_ungueltige_sitzung_und_daten(self):
        for s in ('', 'E-1', '../x', None, 'E-20261109-101010-zzzz'):
            with self.assertRaises(ValueError, msg=str(s)):
                e.ablegen(self.projekt, KONFIG, sitzung=s, name='a.md', offset=0, daten=b64(b'x'))
        with self.assertRaises(ValueError):
            e.ablegen(self.projekt, KONFIG, sitzung=self.s, name='a.md', offset=0, daten='***')

    def test_teil_ueber_der_grenze(self):
        with self.assertRaises(ValueError) as c:
            e.ablegen(self.projekt, types.SimpleNamespace(je_art={'md': 10 ** 9}, datei_max_bytes=1), sitzung=self.s, name='a.md', offset=0,
                      daten=b64(b'x' * (e.MAX_TEIL + 1)))
        self.assertEqual(str(c.exception), 'wis_eingang_teil_zu_gross')

    def test_stand_und_verwerfen(self):
        e.ablegen(self.projekt, KONFIG, sitzung=self.s, name='a.md', offset=0, daten=b64(b'abc'))
        st = e.stand(self.projekt, self.s)
        self.assertEqual((st['dateien'], st['bytes']), (1, 3))
        self.assertEqual(st['eingang'], f'local_config/wissen/eingang/{self.s}')
        e.verwerfen(self.projekt, self.s)
        self.assertFalse(e.ordner(self.projekt, self.s).exists())


class Kopieren(Basis):
    def test_ordner_wird_mit_struktur_kopiert_fremdes_uebersprungen(self):
        ordner = self.quelle / 'Kunde'
        (ordner / 'sub').mkdir(parents=True)
        (ordner / 'a.md').write_text('a', encoding='utf-8')
        (ordner / 'sub' / 'b.txt').write_text('b', encoding='utf-8')
        (ordner / 'bild.png').write_bytes(b'x')
        (ordner / 'gross.md').write_bytes(b'x' * 2000)
        (ordner / '.git').mkdir()
        (ordner / '.git' / 'c.md').write_text('c', encoding='utf-8')
        r = e.kopieren(self.projekt, KONFIG, [str(ordner)], self.s)
        dest = e.ordner(self.projekt, self.s)
        self.assertEqual(sorted(p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file()), ['Kunde/a.md', 'Kunde/sub/b.txt'])
        self.assertEqual(r['kopiert'], 2)
        self.assertEqual((r['uebersprungen']['art'], r['uebersprungen']['gross']), (1, 1))

    def test_einzelne_dateien(self):
        f = self.quelle / 'x.docx'
        f.write_bytes(b'PK')
        r = e.kopieren(self.projekt, KONFIG, [str(f), str(self.quelle / 'gibtsnicht.md')], self.s)
        self.assertEqual(r['kopiert'], 1)
        self.assertTrue((e.ordner(self.projekt, self.s) / 'x.docx').is_file())

    def test_zahlbremse(self):
        alt = e.MAX_DATEIEN
        e.MAX_DATEIEN = 2
        self.addCleanup(setattr, e, 'MAX_DATEIEN', alt)
        for i in range(4):
            (self.quelle / f'{i}.md').write_text('x', encoding='utf-8')
        r = e.kopieren(self.projekt, KONFIG, [str(self.quelle)], self.s)
        self.assertEqual((r['kopiert'], r['uebersprungen']['limit']), (2, 2))


class Dialog(unittest.TestCase):
    def antwort(self, text, code=0):
        return lambda *a, **k: types.SimpleNamespace(returncode=code, stdout=base64.b64encode(text.encode('utf-8')).decode(), stderr='')

    def test_pfade_werden_gelesen_mit_umlauten(self):
        if sys.platform != 'win32':
            self.skipTest('nur Windows')
        r = e.dialog('dateien', laufen=self.antwort('C:\\Ordner\\Größe.md\nC:\\Ordner\\b.txt'))
        self.assertEqual(r, ['C:\\Ordner\\Größe.md', 'C:\\Ordner\\b.txt'])

    def test_abbruch_ist_leer(self):
        if sys.platform != 'win32':
            self.skipTest('nur Windows')
        self.assertEqual(e.dialog('ordner', laufen=self.antwort('')), [])

    def test_fehlercode_und_art(self):
        if sys.platform == 'win32':
            with self.assertRaises(ValueError):
                e.dialog('ordner', laufen=self.antwort('', code=1))
        with self.assertRaises(ValueError):
            e.dialog('alles')


class Saetze(unittest.TestCase):
    def test_jeder_fehlercode_hat_einen_deutschen_satz(self):
        import re
        quelle = (Path(e.__file__)).read_text(encoding='utf-8') + Path(e.__file__).with_name('desk_wissen.py').read_text(encoding='utf-8')
        for code in sorted(set(re.findall(r'"(wis_(?:eingang|dialog)_[a-z_]+)"', quelle))):
            self.assertNotEqual(satz(code), code, code + ' hat keinen Satz')


if __name__ == '__main__':
    unittest.main()
