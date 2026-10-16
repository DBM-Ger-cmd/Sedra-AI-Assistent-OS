import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from guppi_runtime.solo_steps import extract_for, number_task, numbered  # noqa: E402


class UnitTests(unittest.TestCase):
    def test_the_task_is_cut_without_changing_a_word(self):
        task = "Line one.\n\nLine two has `code` and e.g. \"x\". " + "Second sentence of a long line. " * 20
        units = number_task(task)
        self.assertEqual(units[0], "Line one.")
        self.assertEqual(" ".join(units[1:]).split(), (task.split("\n\n")[1]).split())
        self.assertTrue(all(len(u) <= 520 for u in units))
        self.assertTrue(numbered(units).startswith("[1] Line one.\n[2] "))

    def test_a_step_gets_its_units_plus_the_ones_nobody_claimed_and_never_loses_anything(self):
        units = ["a", "b", "c", "d"]
        steps = [{"lines": [1, 2]}, {"lines": [2, 3]}]
        self.assertEqual(extract_for(steps[0], steps, units), "a\nb\nd")
        self.assertEqual(extract_for(steps[1], steps, units), "b\nc\nd")
        self.assertEqual(extract_for({"lines": []}, steps, units), "a\nb\nc\nd")
        self.assertEqual(extract_for({"lines": [9, "x"]}, steps, units), "a\nb\nc\nd")


if __name__ == "__main__":
    unittest.main()
