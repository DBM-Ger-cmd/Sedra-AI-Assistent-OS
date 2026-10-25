"""Abnahme der SEDRA-gebauten Module von Spec 2 gegen `src` (Bauweg 2026-10-25, Punkt 2): die versteckten Tests der letzten Stufe von `s2_slotplan`
laufen gegen `jobs/slotplan.py`. `slot_store.py` hängt über `slot_db` am Testlabor und hat seine Tests in `test_slot_store.py`.

Neue SEDRA-Module: Eintrag in SPECS (Spec -> Ordner, Module), beim Übernehmen nach G4."""
import tempfile
import unittest
from pathlib import Path

import bau_abnahme

RUNTIME = Path(__file__).resolve().parents[1]
JOBS = RUNTIME / 'src' / 'guppi_runtime' / 'jobs'
SPECS = {'s2_slotplan': (JOBS, ('slotplan',))}


class Modules(unittest.TestCase):
    def test_the_hidden_acceptance_of_each_build_spec_passes_against_src(self):
        for spec, (folder, modules) in SPECS.items():
            with self.subTest(spec=spec), tempfile.TemporaryDirectory(prefix='jobs-modules-') as tree:
                bau_abnahme.plain_tree(folder, modules, tree)
                failed = {n: tail for n, (code, tail) in bau_abnahme.run_hidden(spec, tree, modules).items() if code != 0}
                self.assertEqual(failed, {})


if __name__ == '__main__':
    unittest.main()
