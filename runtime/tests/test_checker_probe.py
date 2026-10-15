import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))
sys.path.insert(0, str(RUNTIME / "benchmarks" / "probes"))
sys.path.insert(0, str(RUNTIME / "src"))

from checker_probe import GOOD_KILL_RATE, STAGE_FILES, choose, stage_is_right  # noqa: E402


class CheckerProbeTest(unittest.TestCase):
    def test_the_choice_is_spread_evenly_and_the_same_every_time(self):
        items = [(f"f{i}.py", "k", i) for i in range(20)]
        picked = choose(items, 5)
        self.assertEqual(len(picked), 5)
        self.assertEqual(picked, choose(list(reversed(items)), 5))
        self.assertEqual(picked[0], items[0])
        self.assertEqual(choose(items[:3], 5), items[:3])

    def test_a_stage_is_right_only_for_a_valid_check_with_a_high_kill_rate(self):
        self.assertTrue(stage_is_right(True, 7, 10))
        self.assertFalse(stage_is_right(True, 6, 10))
        self.assertFalse(stage_is_right(False, 10, 10))
        self.assertFalse(stage_is_right(True, 0, 0))
        self.assertEqual(GOOD_KILL_RATE, 0.7)

    def test_every_stage_of_the_standard_benchmark_has_files_to_break(self):
        import importlib
        spec = importlib.import_module("devvm_specs.bench_std")
        self.assertEqual(sorted(STAGE_FILES), sorted(s["name"] for s in spec.STAGES))
        seed = RUNTIME / "benchmarks" / "bench_std_seed"
        self.assertTrue(all(isinstance(files, tuple) and files for files in STAGE_FILES.values()))
        self.assertEqual(sorted(p.name for p in seed.iterdir() if p.name != "__pycache__"), ["ledger.py", "main.py", "util.py"])


if __name__ == "__main__":
    unittest.main()
