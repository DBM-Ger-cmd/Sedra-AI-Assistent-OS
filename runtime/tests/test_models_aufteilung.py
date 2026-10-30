"""Dynamische Rezepte R2 (rein): `models/aufteilung.py` besteht dieselben versteckten Prüfungen wie der SEDRA-Bau (benchmarks/devvm_specs/modelle_aufteilung.py),
dazu ein Bündel eigener Fälle für die Zahlen des Befunds vom 29.10.2026 (Qwen3.6, 10,65 GB VRAM und 14,3 GB RAM frei)."""
import importlib.util
import sys
import unittest
from pathlib import Path

from guppi_runtime.models import aufteilung

SPEC = Path(__file__).resolve().parents[1] / 'benchmarks' / 'devvm_specs' / 'modelle_aufteilung.py'
DYN = {"n_cpu_moe": {"min": 24, "max": 40}, "vram_fix_gb": 1.5, "ram_aufschlag_gb": 1.5, "ram_untergrenze_gb": 8,
       "tabelle": {"bei_kontext": 32768, "punkte": [{"lagen": 28, "vram_gb": 10.5, "tokens_s": 45.0}, {"lagen": 32, "vram_gb": 9.1, "tokens_s": 41.7},
                                                    {"lagen": 36, "vram_gb": 7.6, "tokens_s": 38.5}, {"lagen": 40, "vram_gb": 6.1, "tokens_s": 35.5}]}}


class AufteilungTests(unittest.TestCase):
    def test_versteckte_pruefungen_der_bau_spec(self):
        spez = importlib.util.spec_from_file_location('modelle_aufteilung_spec', SPEC)
        modul = importlib.util.module_from_spec(spez)
        spez.loader.exec_module(modul)
        vorher = sys.modules.get('aufteilung')
        sys.modules['aufteilung'] = aufteilung
        try:
            for name, text in modul.STAGES[0]['hidden'].items():
                exec(compile(text, name, 'exec'), {})
        finally:
            if vorher is None:
                sys.modules.pop('aufteilung', None)
            else:
                sys.modules['aufteilung'] = vorher

    def test_befund_vom_29_10_qwen_laedt_mit_30_lagen(self):
        a = aufteilung.waehlen(DYN, [32768], 10.65, 14.3, 0.7, 1.5, 0.04, 17.73)
        self.assertEqual((a['ok'], a['lagen'], a['kontext']), (True, 30, 32768))
        self.assertAlmostEqual(a['vram_gb'], 9.8, places=2)
        self.assertLess(a['ram_gb'], 12.8, 'passt in die freien 14,3 GB RAM nach Reserve')
        self.assertAlmostEqual(a['tokens_s'], 43.35, places=2)

    def test_ablehnung_nennt_den_fehlbetrag_in_gb(self):
        f = aufteilung.waehlen(DYN, [32768], 5.0, 8.0, 0.7, 1.5, 0.04, 17.73)
        self.assertFalse(f['ok'])
        self.assertIn('GB', f['vorschlag'])
        self.assertIn(str(f['beste']['lagen']), f['vorschlag'])

    def test_obergrenze_des_captains_wird_nie_ueberschritten(self):
        # die VRAM-Grenze (11,5 GB inkl. Reserve) kommt als frei − Reserve: nie mehr als das, auch wenn die Karte mehr frei hat
        a = aufteilung.waehlen(DYN, [32768], 11.5, 30.0, 0.7, 1.5, 0.04, 17.73)
        self.assertTrue(a['ok'])
        self.assertLessEqual(a['vram_gb'], 11.5 - 0.7)


if __name__ == '__main__':
    unittest.main()
