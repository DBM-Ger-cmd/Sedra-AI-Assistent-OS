"""Der Bau-Lauf mit einer anderen Spec: Angabe geprueft, Kurzbericht statt Produktpruefung, Manager reicht die Spec weiter."""
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / 'benchmarks'))
sys.path.insert(0, str(RUNTIME / 'src'))
import bau_schleife as bs  # noqa: E402


class SpecAngabe(unittest.TestCase):
    def tearDown(self):
        bs.SPEC_NAME = bs.STANDARD_SPEC
        bs.SPEC_FILE = bs.BENCH / 'devvm_specs' / (bs.STANDARD_SPEC + '.py')

    def test_unbekannte_spec_wird_abgelehnt(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(SystemExit) as ctx:
                bs.main(['--projekt', t, '--spec', 'gibt_es_nicht', 'start', 'x'])
        self.assertIn('unbekannte Spec', str(ctx.exception))

    def test_ungueltiger_name_wird_abgelehnt(self):
        for name in ('../x', 'A B', 'x;y', ''):
            with tempfile.TemporaryDirectory() as t, self.assertRaises(SystemExit):
                bs.main(['--projekt', t, '--spec', name, 'start', 'x'])

    def test_standard_spec_bleibt_ohne_angabe(self):
        self.assertEqual(bs.SPEC_NAME, 'factory_sdk_grundlage_v5')
        self.assertEqual(bs.STUFEN, ['S1', 'S2', 'S3', 'S4'])

    def test_kurzbericht_nennt_stufen_und_keine_produktpruefung(self):
        bs.SPEC_NAME = 'beispiel'
        with tempfile.TemporaryDirectory() as t:
            ziel = bs.kurzbericht(Path(t), {'S1': 'k1', 'S2': 'k2'}, 'Auftrag A')
            text = ziel.read_text(encoding='utf-8')
        self.assertIn('Stufe S1: bestanden', text)
        self.assertIn('Stufe S2: bestanden', text)
        self.assertNotIn('Stufe S3', text)
        self.assertIn('Keine Produktpruefung', text)
        self.assertIn('Auftrag A', text)

    def test_rezept_und_kontext_ersetzen_den_coder(self):
        import copy
        alt = copy.deepcopy(bs.SAETZE)
        try:
            with tempfile.TemporaryDirectory() as t:
                bs.main(['--projekt', t, '--rezept', 'coder.local_primary_1x80k', '--kontext', '81920', 'bericht'])
        except SystemExit:
            pass
        finally:
            ersetzt = copy.deepcopy(bs.SAETZE)
            bs.SAETZE[:] = alt
        self.assertEqual(ersetzt[0]['coder'], 'coder.local_primary_1x80k')
        self.assertEqual(ersetzt[0]['args'], ['--context', '81920'])
        self.assertEqual(ersetzt[2]['coder'], 'qwen3coder')
        self.assertEqual(ersetzt[2]['args'], [])

    def test_rezept_und_kontext_werden_geprueft(self):
        for argv in (['--rezept', 'X Y', 'start', 'a'], ['--rezept', 'coder.local_primary', '--kontext', '12', 'start', 'a'], ['--rezept', 'coder.local_primary', '--kontext', 'abc', 'start', 'a']):
            with tempfile.TemporaryDirectory() as t, self.assertRaises(SystemExit):
                bs.main(['--projekt', t] + argv)


class ManagerReichtSpecWeiter(unittest.TestCase):
    def test_ungueltige_spec_im_manager(self):
        from sedra_runtime.manager import werkzeuge
        with tempfile.TemporaryDirectory() as t:
            for name in ('../x', 'A B', 5):
                with self.assertRaises(ValueError):
                    werkzeuge.bau_starten(t, 'Auftrag', name)
            with self.assertRaises(ValueError):
                werkzeuge.bau_starten(t, 'Auftrag', None, 'X Y')
            with self.assertRaises(ValueError):
                werkzeuge.bau_starten(t, 'Auftrag', None, 'coder.local_primary', 12)


if __name__ == '__main__':
    unittest.main()
