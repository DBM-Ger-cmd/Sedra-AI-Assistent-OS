import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks" / "probes"))
sys.path.insert(0, str(RUNTIME / "src"))

from dense_probe import int_list, plan  # noqa: E402


class DenseProbeTests(unittest.TestCase):
    def test_options_and_plan(self):
        self.assertEqual(int_list([36, 28, 28], 0, 99, [1]), [28, 36])
        for bad in (None, [], ["x"], [True], [200], "28"):
            self.assertEqual(int_list(bad, 0, 99, [1]), [1])
        self.assertEqual(plan([28, 32, 36], True), [32, 36])
        self.assertEqual(plan([28, 32, 36], False), [])
        self.assertEqual(plan([], True), [])

    def test_the_manager_finds_the_probe(self):
        from guppi_runtime.agent_manager.run_worker import probe_script
        self.assertTrue(Path(probe_script(str(RUNTIME), "probe_dense")).is_file())


if __name__ == "__main__":
    unittest.main()
