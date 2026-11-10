"""Messlauf-Werkzeug: die reinen Teile (Argumente, Auswertung, Modellordner); kein Server wird gestartet."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
import messlauf  # noqa: E402


class Rein(unittest.TestCase):
    def test_argumente_kanaele_und_kontext(self):
        a = messlauf.argv_fuer('x.exe', 'm.gguf', 8110, ['-ngl', '99'], {'kanaele': 3, 'kontext': 49152, 'args': ['--n-cpu-moe', '22']})
        self.assertEqual(a[a.index('-c') + 1], str(3 * 49152))
        self.assertEqual(a[a.index('-np') + 1], '3')
        self.assertEqual(a[a.index('--host') + 1], '127.0.0.1')
        self.assertEqual(a[-2:], ['--n-cpu-moe', '22'])
        self.assertIn('-ngl', a)

    def test_ungueltige_stufen(self):
        for stufe in ({'kanaele': 0}, {'kanaele': 9}, {'kontext': 100}):
            with self.assertRaises(ValueError):
                messlauf.argv_fuer('x', 'm', 1, [], stufe)

    def test_auswertung(self):
        runden = [[(60.0, 200, 100, 90, 4.0), (40.0, 200, 100, 80, 4.0)]] * 3
        r = messlauf.auswerten(runden)
        self.assertEqual(r['tg_je_strom'], 50.0)
        self.assertEqual(r['gesamt_tok_s'], 100.0)
        self.assertEqual(r['annahme'], 0.85)
        ohne = messlauf.auswerten([[(10.0, 100, 0, 0, 10.0)]])
        self.assertIsNone(ohne['annahme'])

    def test_modellordner_aus_angabe(self):
        self.assertEqual(messlauf.modelle_ordner('Z'), 'Z')


if __name__ == '__main__':
    unittest.main()
