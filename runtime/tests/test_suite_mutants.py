import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

from guppi_runtime.selfdev.acceptance_suite import write_suite  # noqa: E402
from suite_mutants import describe, mutate, sites, survivors  # noqa: E402

REFERENCE = "def less(a, b):\n    return a < b\n\n\ndef both(a, b):\n    return a and b\n"
WEAK = "from ref import less, both\nassert less(1, 2) is True\nassert less(2, 1) is False\nassert both(1, 2) == 2\nassert both(0, 5) == 0\n"
STRICT = WEAK + "assert less(1, 1) is False\n"


class MutantTest(unittest.TestCase):
    def suite(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return write_suite(str(Path(folder.name) / "s"), "demo", "1", [{"id": "demo.c", "description": "d", "script": "check.py", "text": text.replace("ref", "ref")}], {"ref.py": REFERENCE})

    def test_sites_name_every_changeable_place(self):
        import ast
        kinds = sorted(kind for kind, _ in sites(ast.parse(REFERENCE)))
        self.assertEqual(kinds, ["boolop", "compare", "return", "return"])

    def test_a_mutant_changes_exactly_one_place(self):
        import ast
        kind, index = next(site for site in sites(ast.parse(REFERENCE)) if site[0] == "compare")
        self.assertIn("a <= b", mutate(REFERENCE, kind, index))
        self.assertIn("return a and b", mutate(REFERENCE, kind, index))
        self.assertIn("compare at line 2", describe(REFERENCE, kind, index))

    def test_a_weak_suite_lets_the_boundary_mutant_survive_and_a_strict_one_catches_it(self):
        tried, alive = survivors(self.suite(WEAK))
        self.assertGreater(tried, 3)
        self.assertTrue(any("compare at line 2" in line for line in alive), alive)
        tried, alive = survivors(self.suite(STRICT))
        self.assertFalse(any("compare at line 2" in line for line in alive), alive)


if __name__ == "__main__":
    unittest.main()
