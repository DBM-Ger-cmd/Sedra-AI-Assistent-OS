"""Abnahme der SEDRA-gebauten Module von Spec 2 gegen `src` (Bauweg 2026-10-25, Punkt 2): die versteckten Tests der letzten Stufe von `s2_slotplan`
laufen gegen `jobs/slotplan.py`. `slot_store.py` läuft mit dem Saatgut `slot_db.py` (siehe SPECS); sein Paketverhalten mit Testlabor prüft `test_slot_store.py`.

Neue SEDRA-Module: Eintrag in SPECS (Spec -> Ordner, Module), beim Übernehmen nach G4."""
import tempfile
import unittest
from pathlib import Path

import bau_abnahme

RUNTIME = Path(__file__).resolve().parents[1]
JOBS = RUNTIME / 'src' / 'guppi_runtime' / 'jobs'
SEED = RUNTIME / 'benchmarks' / 's2_schema_seed' / 'slot_db.py'
# `slot_store.py` hängt im Paket über `slot_db` am Testlabor; die versteckten Tests öffnen `slot_db.open_db(":memory:")`. Deshalb läuft der Speicher gegen
# das Saatgut `slot_db.py` (dieselbe Tabellentext, Verbindung im Speicher): geprüft wird `slot_store.py` selbst; `slot_db` im Paket ist nur der Schalter.
SPECS = {'s2_slotplan': (JOBS, ('slotplan',), None), 's2_slot_store': (JOBS, ('slot_store', 'slotplan'), SEED)}


class Modules(unittest.TestCase):
    def test_the_hidden_acceptance_of_each_build_spec_passes_against_src(self):
        for spec, (folder, modules, seed) in SPECS.items():
            with self.subTest(spec=spec), tempfile.TemporaryDirectory(prefix='jobs-modules-') as tree:
                bau_abnahme.plain_tree(folder, modules, tree)
                extra = ()
                if seed is not None:
                    (Path(tree) / seed.name).write_text(seed.read_text(encoding='utf-8'), encoding='utf-8')
                    extra = (seed.stem,)
                failed = {n: tail for n, (code, tail) in bau_abnahme.run_hidden(spec, tree, modules + extra).items() if code != 0}
                self.assertEqual(failed, {})


if __name__ == '__main__':
    unittest.main()
