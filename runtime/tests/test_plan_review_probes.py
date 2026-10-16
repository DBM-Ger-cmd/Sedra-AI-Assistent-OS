import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
import env_skip

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))
sys.path.insert(0, str(RUNTIME / "benchmarks" / "probes"))
sys.path.insert(0, str(RUNTIME / "src"))

from plan_probe import MIN_COVERAGE, plan_metrics  # noqa: E402
from review_probe import rate  # noqa: E402
from guppi_runtime.agent_manager import run_worker  # noqa: E402


class PlanMetricsTests(unittest.TestCase):
    UNITS = ["one", "two", "three", "four", "five"]
    TASK = "x" * 3000

    @env_skip.needs_dulwich
    def test_a_plan_that_splits_claims_the_lines_and_names_interfaces_is_right(self):
        steps = [{"lines": [1, 2, 3], "interface": "a()"}, {"lines": [3, 4], "interface": "b()"}]
        m = plan_metrics(self.TASK, self.UNITS, steps, False, 1800)
        self.assertTrue(m["right"] and m["split_ok"] and m["interfaces"])
        self.assertEqual(m["coverage"], 0.8)
        self.assertLess(m["largest_extract"], 1.0)

    @env_skip.needs_dulwich
    def test_the_fallback_a_missing_split_and_missing_interfaces_make_a_plan_wrong(self):
        self.assertFalse(plan_metrics(self.TASK, self.UNITS, [{"lines": []}], True, 1800)["right"])
        self.assertFalse(plan_metrics(self.TASK, self.UNITS, [{"lines": [1, 2, 3, 4, 5]}], False, 1800)["right"])                     # long task kept as one step
        self.assertTrue(plan_metrics("short", self.UNITS, [{"lines": [1, 2, 3, 4, 5]}], False, 1800)["right"])                          # a short task may stay one step
        self.assertFalse(plan_metrics(self.TASK, self.UNITS, [{"lines": [1, 2, 3, 4]}, {"lines": [5]}], False, 1800)["right"])         # no interfaces
        low = plan_metrics(self.TASK, self.UNITS, [{"lines": [1], "interface": "a"}, {"lines": [2], "interface": "b"}], False, 1800)
        self.assertLess(low["coverage"], MIN_COVERAGE); self.assertFalse(low["right"])


class ReviewRateTests(unittest.TestCase):
    def test_a_review_is_useful_when_it_catches_most_faults_and_rarely_raises_a_false_alarm(self):
        rows = [{"kind": "reference", "verdict": "PASS"}] * 4 + [{"kind": "mutant", "verdict": "FAIL"}] * 7 + [{"kind": "mutant", "verdict": "PASS"}] * 3
        r = rate(rows)
        self.assertEqual((r["caught"], r["mutants"], r["false_alarms"]), (7, 10, 0)); self.assertTrue(r["useful"])
        self.assertFalse(rate(rows[:4] + [{"kind": "mutant", "verdict": "FAIL"}] * 5 + [{"kind": "mutant", "verdict": None}] * 5)["useful"])
        self.assertFalse(rate([{"kind": "reference", "verdict": "FAIL"}, {"kind": "reference", "verdict": "FAIL"}] + [{"kind": "mutant", "verdict": "FAIL"}] * 8)["useful"])
        self.assertFalse(rate([])["useful"])


class ProbeOptionsTests(unittest.TestCase):
    def test_the_probe_options_reach_the_script_only_when_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            seeds = os.path.join(tmp, "runtime_data", "agent_manager", "seeds")
            os.makedirs(seeds)

            def cmd(options):
                with open(os.path.join(seeds, "probe_plan.options.json"), "w") as handle:
                    json.dump(options, handle)
                return run_worker.probe_command("py", "rt", tmp, "probe_plan")[3:]
            self.assertEqual(cmd({"models": ["coder.local_primary"], "specs": ["am007_crews", "am009_collector"], "reasoning": "on", "reasoning_budget": 2048, "per_stage": 3}),
                             ["--models", "coder.local_primary", "--specs", "am007_crews,am009_collector", "--reasoning", "on", "--reasoning-budget", "2048", "--per-stage", "3"])
            six = ["coder.local_primary", "qwen3coder", "swe", "jan", "verifier.llama_gemma", "coder.llama_hermes4_14b"]
            self.assertEqual(cmd({"models": six}), ["--models", ",".join(six)])                       # the checker probe of 2026-10-09 asked for six models and silently got the default two
            self.assertEqual(cmd({"models": six + ["a1", "a2", "a3"]}), [])                            # more than eight: the option is dropped
            self.assertEqual(cmd({"specs": ["../x"], "reasoning": "maybe", "reasoning_budget": 99999, "per_stage": 0}), [])


if __name__ == "__main__":
    unittest.main()


class QwenProbeOptionTests(unittest.TestCase):
    def test_stage_seed_and_qwen_modes_reach_the_probe_only_when_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            seeds = os.path.join(tmp, "runtime_data", "agent_manager", "seeds")
            os.makedirs(seeds)

            def cmd(options):
                with open(os.path.join(seeds, "probe_qwen.options.json"), "w") as handle:
                    json.dump(options, handle)
                return run_worker.probe_command("py", "rt", tmp, "probe_qwen")[3:]
            self.assertEqual(cmd({"models": ["coder.local_primary"], "modes": ["qwen-none", "qwen-light"], "trials": 2, "specs": ["am007_crews"], "stage": "assemble_basic", "seed": "am007_crews/20261010_131036/after_rules"}),
                             ["--models", "coder.local_primary", "--modes", "qwen-none,qwen-light", "--trials", "2", "--specs", "am007_crews", "--stage", "assemble_basic", "--seed", "am007_crews/20261010_131036/after_rules"])
            self.assertEqual(cmd({"stage": "Bad Stage", "seed": "../../etc", "modes": ["qwen-yolo"]}), [])
            self.assertEqual(cmd({"seed": "/etc/passwd"}), [])
            self.assertEqual(cmd({"seed": "a/b/c/d/e"}), [])
