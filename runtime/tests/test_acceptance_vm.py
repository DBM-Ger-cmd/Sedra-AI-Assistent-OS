import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import os
import unittest
from pathlib import Path

from guppi_runtime.selfdev.acceptance_suite import candidate_hash, load_suite, run_suite
from guppi_runtime.selfdev.acceptance_vm import vm_runner

RUNTIME = Path(__file__).resolve().parents[1]
PROJECT = RUNTIME.parent / "workspace" / "GUPPI_OS"


@unittest.skipUnless(os.environ.get("GUPPI_VM_TESTS") == "1", "needs the microVM; set GUPPI_VM_TESTS=1")
class VmRunnerTest(unittest.TestCase):
    def test_a_command_runs_in_the_vm_and_a_failing_one_is_reported_as_failed(self):
        run = vm_runner(PROJECT, RUNTIME)
        self.assertEqual(run({"ok.py": "print('hi')\n"}, [["python3", "ok.py"]])["status"], "completed")
        out = run({"bad.py": "assert 1 == 2\n"}, [["python3", "bad.py"]])
        self.assertEqual(out["status"], "failed")
        self.assertIn("AssertionError", out["output"])

    def test_the_stored_suite_of_the_matcher_passes_its_reference_in_the_vm(self):
        suite = load_suite(str(PROJECT / "acceptance" / "suites" / "am005_matcher"))
        result = run_suite(suite, suite.reference, vm_runner(PROJECT, RUNTIME))
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["candidate_hash"], candidate_hash(suite.reference))


if __name__ == "__main__":
    unittest.main()
