"""Der Code aus der Modellantwort: auch ohne schliessenden Zaun darf keine ```-Zeile in der .scad-Datei bleiben."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))
import nachtlauf_3d as lauf  # noqa: E402


class ExtractCode(unittest.TestCase):
    def test_closed_block_with_text_around(self):
        self.assertEqual(lauf.extract_code("Hier:\n```openscad\ncube(1);\n```\nFertig."), "cube(1);")

    def test_unclosed_block_from_a_cut_off_answer(self):
        self.assertEqual(lauf.extract_code("```openscad\ncube(1);\ncube(2);"), "cube(1);\ncube(2);")

    def test_plain_fence_and_no_fence(self):
        self.assertEqual(lauf.extract_code("```\ncube(4);\n```"), "cube(4);")
        self.assertEqual(lauf.extract_code("cube(3);"), "cube(3);")


if __name__ == "__main__":
    unittest.main()
