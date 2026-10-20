import sys
import unittest
from pathlib import Path
import env_skip

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))
sys.path.insert(0, str(RUNTIME / "benchmarks" / "probes"))
sys.path.insert(0, str(RUNTIME / "src"))

from stdbench_probe import STAGES, command, summary_line  # noqa: E402


class StdBenchTest(unittest.TestCase):
    def test_the_command_is_fixed_and_uses_one_model_for_every_role(self):
        cmd = command("py", "proj", "coder.llama_qwen3_coder")
        for part in ("--spec", "bench_std", "--all-models", "--tidy", "--rework", "--seed"):
            self.assertIn(part, cmd)
        self.assertEqual((cmd[cmd.index("--all-models") + 1], cmd[cmd.index("--rework") + 1], cmd[cmd.index("--context") + 1], cmd[cmd.index("--reasoning") + 1]), ("coder.llama_qwen3_coder", "1", "32768", "off"))
        self.assertNotIn("--check-first", cmd)
        solo = command("py", "proj", "m", mode="solo")
        self.assertEqual(solo[solo.index("--mode") + 1], "solo")
        self.assertNotIn("--self-check", solo)
        light = command("py", "proj", "m", mode="solo-light"); none = command("py", "proj", "m", mode="solo-none")
        self.assertEqual((light[light.index("--mode") + 1], light[light.index("--self-check") + 1]), ("solo", "light"))
        self.assertEqual((none[none.index("--mode") + 1], none[none.index("--self-check") + 1]), ("solo", "none"))
        self.assertEqual(cmd[cmd.index("--mode") + 1], "escalating")

    def test_the_summary_line_counts_the_passed_stages_in_the_format_the_manager_reads(self):
        line = summary_line("m", {"seconds": 600.5, "calls": 40, "stages": [{"stage": "slug", "hidden_passed": True}, {"stage": "fix", "hidden_passed": False}]}, 2)
        self.assertIn(" right 1/4", line)
        self.assertIn("slug=ok,fix=FAIL", line)
        self.assertIn("trial 2", line)
        self.assertEqual(STAGES, 4)

    def test_the_spec_has_four_stages_without_an_own_check_and_the_seed_has_the_defects(self):
        import importlib
        spec = importlib.import_module("devvm_specs.bench_std")
        self.assertEqual([s["name"] for s in spec.STAGES], ["slug", "fix", "extend", "move"])
        self.assertTrue(all(s["no_own_check"] and s["hidden"] for s in spec.STAGES))
        seed = RUNTIME / "benchmarks" / "bench_std_seed"
        self.assertEqual(sorted(p.name for p in seed.iterdir() if p.name != "__pycache__"), ["ledger.py", "main.py", "util.py"])
        self.assertIn('total += entry["amount"]', (seed / "ledger.py").read_text(encoding="utf-8").split("debit")[1])


class ReasoningBudgetTests(unittest.TestCase):
    @env_skip.needs_dulwich
    def test_server_settings_are_passed_to_every_build_and_parsed(self):
        cmd = command("py", "proj", "m", server_set=["flash_attn=on", "kv_cache_type=q8_0", "ubatch=512"])
        self.assertEqual([cmd[i + 1] for i, part in enumerate(cmd) if part == "--server-set"], ["flash_attn=on", "kv_cache_type=q8_0", "ubatch=512"])
        self.assertNotIn("--server-set", command("py", "proj", "m"))
        from devvm_build import server_settings
        self.assertEqual(server_settings(["flash_attn=on", "kv_cache_type=q8_0", "ubatch=512", "mmap=false"]), {"flash_attn": "on", "kv_cache_type": "q8_0", "ubatch": 512, "mmap": False})
        with self.assertRaises(SystemExit):
            server_settings(["flash_attn"])

    @env_skip.needs_dulwich
    def test_layer_runs_give_each_run_the_result_of_its_stage(self):
        from devvm_build import layer_runs
        from guppi_runtime.devenv.layer_summary import cell
        outs = [{"agent_runs": [{"stopped_by": "hand_in", "seconds": 10, "completion_tokens": 100}]},
                {"agent_runs": [{"stopped_by": "hand_in", "seconds": 20, "completion_tokens": 200}, {"stopped_by": "turns", "seconds": 30, "completion_tokens": 300},
                                {"stopped_by": "hand_in", "seconds": 40, "completion_tokens": 400}]}]
        runs = layer_runs(outs, [{"hidden_passed": True}, {"hidden_passed": False}])
        self.assertEqual([r["stage_passed"] for r in runs], [True, False, False, False])
        self.assertEqual(cell(runs), "1:0 2:0 3:0 4:30 5:60 ok:10")

    def test_the_budget_is_passed_only_when_given(self):
        plain = command("py", "P", "coder.local_primary", "on")
        self.assertNotIn("--reasoning-budget", plain)
        budget = command("py", "P", "coder.local_primary", "on", reasoning_budget=2048)
        self.assertEqual(budget[budget.index("--reasoning-budget") + 1], "2048")
        self.assertEqual(budget[budget.index("--reasoning") + 1], "on")


if __name__ == "__main__":
    unittest.main()
