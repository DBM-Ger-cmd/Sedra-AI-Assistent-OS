"""Übergang alter Namen (Umgebungsvariablen, Projektordner, Programmpaket, Architekturordner)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sedra_runtime import legacy_names as ln  # noqa: E402

ALT = ln._ALT


class TestEnvAliase(unittest.TestCase):
    def test_alte_variable_wird_zur_neuen(self):
        env = {ALT + '_SECRET_X': 'abc', 'PATH': 'p'}
        self.assertEqual(ln.env_aliase(env), ['SEDRA_SECRET_X'])
        self.assertEqual(env['SEDRA_SECRET_X'], 'abc')
        self.assertEqual(env[ALT + '_SECRET_X'], 'abc')

    def test_neue_variable_gewinnt(self):
        env = {ALT + '_A': 'alt', 'SEDRA_A': 'neu'}
        self.assertEqual(ln.env_aliase(env), [])
        self.assertEqual(env['SEDRA_A'], 'neu')

    def test_fremde_variablen_bleiben(self):
        env = {'SEDRA_B': '1', 'ANDERE': '2'}
        self.assertEqual(ln.env_aliase(env), [])
        self.assertEqual(env, {'SEDRA_B': '1', 'ANDERE': '2'})


class TestUmziehen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_projektordner_wird_umbenannt_inhalt_bleibt(self):
        alt = self.root / 'workspace' / ln.PROJEKTORDNER_ALT
        (alt / 'runtime_data').mkdir(parents=True)
        (alt / 'runtime_data' / 'a.txt').write_text('daten', encoding='utf-8')
        schritte = ln.umziehen(self.root)
        neu = self.root / 'workspace' / ln.PROJEKTORDNER_NEU
        self.assertTrue((neu / 'runtime_data' / 'a.txt').is_file())
        self.assertFalse(alt.exists())
        self.assertEqual(len(schritte), 1)

    def test_beide_ordner_nichts_verschoben(self):
        (self.root / 'workspace' / ln.PROJEKTORDNER_ALT).mkdir(parents=True)
        (self.root / 'workspace' / ln.PROJEKTORDNER_NEU).mkdir(parents=True)
        schritte = ln.umziehen(self.root)
        self.assertTrue((self.root / 'workspace' / ln.PROJEKTORDNER_ALT).is_dir())
        self.assertIn('Hinweis', schritte[0])

    def test_altes_paket_wird_gesichert_nicht_geloescht(self):
        src = self.root / 'runtime' / 'src'
        (src / ln.PAKET_ALT).mkdir(parents=True)
        (src / ln.PAKET_ALT / 'x.py').write_text('1', encoding='utf-8')
        (src / ln.PAKET_NEU).mkdir()
        schritte = ln.umziehen(self.root)
        gesichert = self.root / 'local_config/update/sicherung/alt_namen' / ln.PAKET_ALT / 'x.py'
        self.assertTrue(gesichert.is_file())
        self.assertFalse((src / ln.PAKET_ALT).exists())
        self.assertTrue((src / ln.PAKET_NEU).is_dir())
        self.assertEqual(len(schritte), 1)

    def test_altes_paket_bleibt_ohne_neues(self):
        src = self.root / 'runtime' / 'src'
        (src / ln.PAKET_ALT).mkdir(parents=True)
        self.assertEqual(ln.umziehen(self.root), [])
        self.assertTrue((src / ln.PAKET_ALT).is_dir())

    def test_alter_architekturordner_wird_gesichert_wenn_neuer_da(self):
        arch = self.root / 'architecture'
        (arch / (ln.ARCHITEKTUR_ALT + 'v1.20_X')).mkdir(parents=True)
        (arch / (ln.ARCHITEKTUR_NEU + 'v1.20_X')).mkdir()
        schritte = ln.umziehen(self.root)
        self.assertEqual(len(schritte), 1)
        self.assertFalse((arch / (ln.ARCHITEKTUR_ALT + 'v1.20_X')).exists())
        self.assertTrue((arch / (ln.ARCHITEKTUR_NEU + 'v1.20_X')).is_dir())

    def test_zweiter_lauf_tut_nichts(self):
        (self.root / 'workspace' / ln.PROJEKTORDNER_ALT).mkdir(parents=True)
        self.assertEqual(len(ln.umziehen(self.root)), 1)
        self.assertEqual(ln.umziehen(self.root), [])



class TestBefehlszeile(unittest.TestCase):
    def test_umzug_meldet_schritte_und_code_null(self):
        import contextlib
        import io
        from sedra_runtime import umzug
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'workspace' / ln.PROJEKTORDNER_ALT).mkdir(parents=True)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = umzug.main(['--root', tmp])
            self.assertEqual(code, 0)
            self.assertIn('Projektordner umbenannt', out.getvalue())
            self.assertTrue((Path(tmp) / 'workspace' / ln.PROJEKTORDNER_NEU).is_dir())

    def test_gesperrter_ordner_gibt_code_drei_und_aendert_nichts(self):
        import contextlib
        import io
        from unittest import mock
        from sedra_runtime import umzug
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'workspace' / ln.PROJEKTORDNER_ALT).mkdir(parents=True)
            err = io.StringIO()
            with mock.patch.object(Path, 'rename', side_effect=PermissionError('gesperrt')), contextlib.redirect_stderr(err):
                code = umzug.main(['--root', tmp])
            self.assertEqual(code, 3)
            self.assertIn('Umzug nicht möglich', err.getvalue())
            self.assertTrue((Path(tmp) / 'workspace' / ln.PROJEKTORDNER_ALT).is_dir())
            self.assertFalse((Path(tmp) / 'workspace' / ln.PROJEKTORDNER_NEU).exists())


if __name__ == '__main__':
    unittest.main()
