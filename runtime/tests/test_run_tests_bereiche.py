"""run_tests.py (16.11.2026): die Prüfstellen der Freigabe-Tür, die Hardening-Gegenproben und die Kodierungsprüfung laufen in den Gruppen mit, die Harness-, Desk- oder Server-Code berühren.
Vorher blieben nach der Integration von uix-3d drei rote Prüfstellen unbemerkt, weil `harness` und `desk` sie nicht enthielten."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))

import run_tests  # noqa: E402

PRUEFSTELLEN = ('test_freigabe_vollstaendig', 'test_freigabe_klasse', 'test_freigabe_tuer', 'test_repo_kodierung')


class Bereiche(unittest.TestCase):
    def test_die_gruppen_harness_desk_und_integration_enthalten_die_pruefstellen(self):
        for bereich in ('harness', 'desk', 'integration', 'pruefstellen'):
            dateien = run_tests.match(run_tests.AREAS[bereich])
            for name in PRUEFSTELLEN:
                self.assertIn(name, dateien, f'{name} fehlt im Bereich {bereich}')

    def test_hardening_gegenproben_laufen_mit(self):
        dateien = run_tests.match(run_tests.AREAS['harness'])
        hardening = [f for f in run_tests.all_files() if f.startswith('test_hardening_')]
        self.assertTrue(hardening, 'es gibt Hardening-Tests')
        self.assertEqual(sorted(set(hardening) - set(dateien)), [])

    def test_der_bereich_pruefstellen_ist_klein_und_schnell(self):
        dateien = run_tests.match(run_tests.AREAS['pruefstellen'])
        self.assertLess(len(dateien), 30, 'nur Prüfstellen, nicht die ganze Gruppe')
        self.assertFalse([f for f in dateien if f in run_tests.SLOW_FILES], 'keine Browser-Bahn in den Prüfstellen')

    def test_alle_bereiche_haben_dateien(self):
        for name, muster in run_tests.AREAS.items():
            self.assertTrue(run_tests.match(muster), f'Bereich {name} wählt nichts')


class Geaendert(unittest.TestCase):
    def gewaehlt(self, dateien):
        with mock.patch.object(run_tests, 'changed_files', return_value=dateien):
            return run_tests.tests_for_changes('HEAD')[0]

    def test_aenderung_an_harness_desk_kern_oder_server_nimmt_die_pruefstellen_mit(self):
        for pfad in ('runtime/src/sedra_runtime/harness/zzz_nichts.py', 'runtime/src/sedra_runtime/desk/zzz_nichts.py', 'runtime/src/sedra_runtime/core/zzz_nichts.py',
                     'runtime/src/sedra_runtime/uix_server.py', 'runtime/src/sedra_runtime/uix/tools/talk/tool.yaml', 'runtime/src/sedra_runtime/uix/shells/harness/shell.yaml',
                     'runtime/src/sedra_runtime/models/cloud_api.py', 'runtime\\src\\sedra_runtime\\harness\\zzz_nichts.py'):
            with self.subTest(pfad=pfad):
                gewaehlt = self.gewaehlt([pfad])
                for name in PRUEFSTELLEN:
                    self.assertIn(name, gewaehlt, f'{name} fehlt bei Änderung an {pfad}')

    def test_aenderung_ganz_woanders_zieht_sie_nicht_mit(self):
        gewaehlt = self.gewaehlt(['docs/ETWAS.md'])
        self.assertNotIn('test_freigabe_vollstaendig', gewaehlt)
        self.assertNotIn('test_repo_kodierung', gewaehlt)


if __name__ == '__main__':
    unittest.main()
