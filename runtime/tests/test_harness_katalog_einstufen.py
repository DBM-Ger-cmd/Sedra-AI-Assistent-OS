"""U2 der Harness-Shell Stufe 2: `katalog.einstufen` erfüllt dieselben Prüfungen wie die Bau-Spec des ersten SEDRA-Baus
(benchmarks/devvm_specs/harness_katalog.py, versteckt für die bauenden Agenten). Seit 28.10.2026 steht im Paket der Bau von SEDRA;
dieser Test hält ihn fest – ändert jemand `einstufen`, müssen dieselben Prüfungen weiter gelten."""
import importlib.util
import sys
import unittest
from pathlib import Path

from guppi_runtime.harness import katalog

SPEC = Path(__file__).resolve().parents[1] / 'benchmarks' / 'devvm_specs' / 'harness_katalog.py'


class EinstufenTests(unittest.TestCase):
    def test_die_pruefungen_der_bau_spec_gelten_fuer_das_paket(self):
        spec = importlib.util.spec_from_file_location('harness_katalog_spec', SPEC)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        alt = sys.modules.get('katalog_einstufen')
        sys.modules['katalog_einstufen'] = katalog
        try:
            for stage in mod.STAGES:
                for name, code in stage['hidden'].items():
                    exec(compile(code, name, 'exec'), {})
        finally:
            if alt is None: sys.modules.pop('katalog_einstufen', None)
            else: sys.modules['katalog_einstufen'] = alt

    def test_die_vorlage_stuft_wie_vorgesehen_ein(self):
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        e = lambda w, z: katalog.einstufen(regeln, w, z)['stufe']
        self.assertEqual(e('datei_lesen', 'runtime/src/x.py'), 'frei')
        self.assertEqual(e('datei_lesen', 'workspace/GUPPI_OS/local_config/switches.yaml'), 'verboten')
        self.assertEqual(e('datei_aendern', 'docs/LOGBUCH_AGENT_MANAGER.md'), 'captain')
        self.assertEqual(e('befehl', 'git status'), 'frei')
        self.assertEqual(e('befehl', 'python benchmarks/run_tests.py harness'), 'frei')
        self.assertEqual(e('befehl', 'python -c "print(1)"'), 'captain')
        self.assertEqual(e('befehl', 'npm install'), 'captain')


if __name__ == '__main__':
    unittest.main()
