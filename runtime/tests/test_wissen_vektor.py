"""`wissen/vektor.py` (Spec 7, D7.2, D7.5; WIS-04, WIS-05): normieren, float32-Blob packen und lesen, Top-k über das Skalarprodukt
ohne numpy, Gleichstand nach nr. Feste Vektoren, kein Modell."""
import math
import struct
import unittest
from array import array

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.wissen import vektor


def v(*werte):
    return vektor.lese(vektor.packe(werte), len(werte))


class Normieren(unittest.TestCase):
    def test_norm_eins(self):
        out = vektor.normiere([3, 4])
        self.assertAlmostEqual(out[0], 0.6)
        self.assertAlmostEqual(out[1], 0.8)
        self.assertAlmostEqual(math.sqrt(sum(x * x for x in out)), 1.0)

    def test_leer_oder_null_ist_wis_vektor_leer(self):
        for werte in ([], [0.0, 0.0], [0]):
            with self.assertRaisesRegex(ValueError, "wis_vektor_leer"):
                vektor.normiere(werte)


class Blob(unittest.TestCase):
    def test_packe_ist_float32_little_endian_und_normiert(self):
        blob = vektor.packe([3, 4])
        self.assertEqual(len(blob), 8)
        self.assertEqual(struct.unpack("<2f", blob), (struct.unpack("<f", struct.pack("<f", 0.6))[0], struct.unpack("<f", struct.pack("<f", 0.8))[0]))

    def test_lese_prueft_die_laenge(self):
        blob = vektor.packe([1, 0, 0])
        self.assertEqual(list(vektor.lese(blob, 3)), [1.0, 0.0, 0.0])
        self.assertIsInstance(vektor.lese(blob, 3), array)
        for dim, b in ((2, blob), (3, blob[:-1]), (0, b""), (3, "kein blob")):
            with self.assertRaisesRegex(ValueError, "wis_vektor_dim"):
                vektor.lese(b, dim)


class TopK(unittest.TestCase):
    def setUp(self):
        self.vektoren = [(1, v(1, 0)), (2, v(0, 1)), (3, v(1, 1)), (4, v(1, 0))]

    def test_absteigend_gleichstand_nach_nr(self):
        out = vektor.top_k(v(1, 0), self.vektoren, 3)
        self.assertEqual([nr for nr, _ in out], [1, 4, 3])
        self.assertAlmostEqual(out[0][1], 1.0, places=6)
        self.assertAlmostEqual(out[2][1], math.sqrt(0.5), places=6)

    def test_erlaubt_filtert_vor_dem_ranking(self):
        out = vektor.top_k(v(1, 0), self.vektoren, 50, erlaubt=lambda nr: nr in {2, 3})
        self.assertEqual([nr for nr, _ in out], [3, 2])

    def test_k_und_dimension_werden_geprueft(self):
        with self.assertRaisesRegex(ValueError, "wis_k_ungueltig"):
            vektor.top_k(v(1, 0), self.vektoren, 0)
        with self.assertRaisesRegex(ValueError, "wis_vektor_dim"):
            vektor.top_k(v(1, 0, 0), self.vektoren, 2)
        self.assertEqual(vektor.top_k(v(1, 0), [], 5), [])

    def test_kosinus_ist_skalarprodukt_normierter_vektoren(self):
        self.assertAlmostEqual(vektor.skalarprodukt(v(2, 0), v(2, 2)), math.cos(math.pi / 4), places=6)


if __name__ == "__main__":
    unittest.main()
