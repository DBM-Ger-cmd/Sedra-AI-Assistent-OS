"""Die schwereren Objekt-Aufgaben: gleiche Aufgaben je Runde fuer jedes Modell, andere Masse in anderen Runden, und die Pruefung der fertigen STL."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))
import objekt_aufgaben_schwer as schwer  # noqa: E402


def wuerfel_stl(kante, ordner, verschoben=0.0):
    """ASCII-STL eines Wuerfels (12 Dreiecke), optional ein zweiter getrennter Wuerfel daneben."""
    def flaechen(o):
        k = kante
        p = [(o, 0, 0), (o + k, 0, 0), (o + k, k, 0), (o, k, 0), (o, 0, k), (o + k, 0, k), (o + k, k, k), (o, k, k)]
        idx = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
        return [tuple(p[i] for i in t) for t in idx]
    dreiecke = flaechen(0.0) + (flaechen(verschoben) if verschoben else [])
    zeilen = ["solid t"]
    for d in dreiecke:
        zeilen += ["facet normal 0 0 0", "outer loop"] + [f"vertex {x} {y} {z}" for x, y, z in d] + ["endloop", "endfacet"]
    pfad = Path(ordner) / "w.stl"
    pfad.write_text("\n".join(zeilen + ["endsolid t"]), encoding="utf-8")
    return pfad


class Aufgaben(unittest.TestCase):
    def test_same_round_same_tasks_other_round_other_sizes(self):
        a1 = [(n, t) for n, t, _ in schwer.aufgaben(1)]
        self.assertEqual(a1, [(n, t) for n, t, _ in schwer.aufgaben(1)])
        self.assertNotEqual([t for _, t in a1], [t for _, t, _ in schwer.aufgaben(2)])
        self.assertTrue(all(n.endswith("_r1") for n, _ in a1))
        self.assertEqual(len(schwer.aufgaben(1, 3)), 3)


class Pruefung(unittest.TestCase):
    def test_measure_cube(self):
        with tempfile.TemporaryDirectory() as d:
            dims, vol, teile = schwer.messen(schwer.lese_stl(wuerfel_stl(10, d)))
        self.assertEqual(dims, (10.0, 10.0, 10.0))
        self.assertAlmostEqual(vol, 1000.0)
        self.assertEqual(teile, 1)

    def test_matching_shape_passes_and_wrong_ones_fail(self):
        with tempfile.TemporaryDirectory() as d:
            stl = wuerfel_stl(10, d)
            self.assertIsNone(schwer.pruefer_fuer((10, 10, 10), 1000.0)(stl))
            self.assertIn("Abmessungen", schwer.pruefer_fuer((10, 10, 20), 1000.0)(stl))
            self.assertIn("Volumen", schwer.pruefer_fuer((10, 10, 10), 1500.0)(stl))
            zwei = wuerfel_stl(10, d, verschoben=30.0)
            self.assertIn("2 getrennten Teilen", schwer.pruefer_fuer((10, 10, 40), 2000.0)(zwei))


if __name__ == "__main__":
    unittest.main()
