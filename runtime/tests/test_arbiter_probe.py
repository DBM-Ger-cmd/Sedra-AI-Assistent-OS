import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))

from probes.arbiter_probe import build_cases, run_probe, summarize   # noqa: E402

PROJECT = RUNTIME.parent / "workspace" / "GUPPI_OS"


class FakeTeam:
    def __init__(self, answers):
        self.answers, self.prepared, self.calls = answers, [], []

    def prepare(self, case):
        self.prepared.append(case["name"])
        self.current = case["name"]

    def _arbitrate(self, task, step, output, label):
        mode = "with_evidence" if step["check"] else "old_prompt"
        self.calls.append((self.current, mode, step["check"] != "", output))
        return self.answers[(self.current, mode)].pop(0)


class ProbeLogicTest(unittest.TestCase):
    CASES = [{"name": "false_rejection", "expected": "PASS", "task": "t", "files": {}, "check": "CHECK-A", "check_name": "a.py"},
             {"name": "true_failure", "expected": "FAIL", "task": "t", "files": {}, "check": "CHECK-B", "check_name": "b.py"}]

    def test_every_trial_is_asked_once_per_mode_and_the_evidence_mode_gets_the_check(self):
        team = FakeTeam({("false_rejection", "old_prompt"): ["FAIL", "FAIL", None], ("false_rejection", "with_evidence"): ["PASS", "PASS", "FAIL"],
                         ("true_failure", "old_prompt"): ["FAIL", "FAIL", "FAIL"], ("true_failure", "with_evidence"): ["FAIL", "PASS", "FAIL"]})
        seen = []
        table = run_probe(self.CASES, ["m1"], 3, lambda model: team, lambda case: "OUT-" + case["name"], progress=lambda t: seen.append(1))
        self.assertEqual(table["m1"]["false_rejection"], {"old_prompt": {"PASS": 0, "FAIL": 2, "none": 1}, "with_evidence": {"PASS": 2, "FAIL": 1, "none": 0}})
        self.assertEqual(table["m1"]["true_failure"]["with_evidence"], {"PASS": 1, "FAIL": 2, "none": 0})
        self.assertEqual(team.prepared, ["false_rejection", "true_failure"])
        self.assertEqual(len(team.calls), 12); self.assertEqual(len(seen), 2)
        self.assertTrue(all(call[3] == "OUT-" + call[0] for call in team.calls))
        self.assertEqual({(c[0], c[1], c[2]) for c in team.calls}, {("false_rejection", "old_prompt", False), ("false_rejection", "with_evidence", True), ("true_failure", "old_prompt", False), ("true_failure", "with_evidence", True)})

    def test_the_summary_counts_the_expected_verdicts(self):
        table = {"m1": {"false_rejection": {"old_prompt": {"PASS": 0, "FAIL": 3, "none": 0}, "with_evidence": {"PASS": 3, "FAIL": 0, "none": 0}},
                        "true_failure": {"old_prompt": {"PASS": 0, "FAIL": 3, "none": 0}, "with_evidence": {"PASS": 1, "FAIL": 2, "none": 0}}}}
        lines = summarize(table, self.CASES, 3)
        self.assertIn("m1", lines[0]); self.assertIn("old_prompt", lines[0]); self.assertIn("right 3/6", lines[0])
        self.assertIn("with_evidence", lines[1]); self.assertIn("right 5/6", lines[1])


@unittest.skipUnless((PROJECT / "runtime_data" / "devvm_candidates" / "am004_import" / "salvaged_20261007_1411").is_dir(), "the AM-004 material is not on this machine")
class CasesFromDiskTest(unittest.TestCase):
    def test_the_two_cases_have_the_known_ground_truth_and_real_files(self):
        cases = build_cases(PROJECT)
        self.assertEqual([(c["name"], c["expected"]) for c in cases], [("false_rejection", "PASS"), ("true_failure", "FAIL")])
        for case in cases:
            self.assertEqual(sorted(case["files"]), ["agent_contracts.py", "agent_import.py"])
            self.assertIn("check_permissions", case["task"])
        self.assertIn("def test_check_permissions", cases[0]["check"])
        self.assertIn("privileged_not_allowed", cases[1]["check"])
        self.assertEqual([c["check_name"] for c in cases], ["acceptance_step1.py", "acceptance_step1.py"], "the check is named like in a real build, so it stays out of the diff")
        self.assertNotEqual(cases[0]["files"]["agent_import.py"], cases[1]["files"]["agent_import.py"])


if __name__ == "__main__":
    unittest.main()
