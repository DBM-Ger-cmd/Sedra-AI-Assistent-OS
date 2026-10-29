"""N2 und N8 der Harness-Shell Stufe 3: die Pakete `aufgabe_deckung` und `lauf_fortschritt` erfüllen dieselben versteckten Prüfungen wie ihre Bau-Specs
(benchmarks/devvm_specs/harness_aufgabe_deckung.py, harness_lauf_fortschritt.py – versteckt für die bauenden Agenten). Heute stehen dort die Referenzen von Claude;
übernimmt der Captain den Bau von SEDRA, hält dieser Test ihn fest – ändert jemand die Module, müssen dieselben Prüfungen weiter gelten."""
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1] / 'benchmarks'


def spec_laden(name):
    spec = importlib.util.spec_from_file_location(name + '_spec', BENCH / 'devvm_specs' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pruefungen_laufen(spec_name, modul_name, paket_modul):
    mod = spec_laden(spec_name)
    alt = sys.modules.get(modul_name)
    sys.modules[modul_name] = importlib.import_module(paket_modul)
    try:
        for stage in mod.STAGES:
            for name, code in stage['hidden'].items():
                exec(compile(code, name, 'exec'), {})
    finally:
        if alt is None: sys.modules.pop(modul_name, None)
        else: sys.modules[modul_name] = alt


class BauPruefungenTests(unittest.TestCase):
    def test_n2_aufgabe_deckung(self):
        pruefungen_laufen('harness_aufgabe_deckung', 'aufgabe_deckung', 'guppi_runtime.harness.aufgabe_deckung')

    def test_n8_lauf_fortschritt(self):
        pruefungen_laufen('harness_lauf_fortschritt', 'lauf_fortschritt', 'guppi_runtime.harness.lauf_fortschritt')

    def test_hoechstens_20_pruefungen_je_bau(self):
        for spec, grenze in (('harness_aufgabe_deckung', 20), ('harness_lauf_fortschritt', 12)):
            mod = spec_laden(spec)
            code = '\n'.join(c for st in mod.STAGES for c in st['hidden'].values())
            self.assertLessEqual(sum(1 for z in code.splitlines() if z.startswith('assert ')), grenze, spec)


if __name__ == '__main__':
    unittest.main()
