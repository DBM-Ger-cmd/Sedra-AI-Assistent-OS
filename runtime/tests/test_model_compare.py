import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

from model_compare import attempt_tokens, build_rows, code_lines, render, speed_rows, summary_rows  # noqa: E402

LOG = ("10:00 agent coder (alone)   m   hand_in  5 calls  10.0 s 1000 tokens, 4000 prompt\n10:01 other line 99 tokens\n10:02 agent arbiter r1   m   hand_in  2 calls  5.0 s 500 tokens\n"
       "10:03 attempt 1: hidden test FAILED | own check accepted=True | 100.0 s\n10:04 agent coder (alone)   m   hand_in  5 calls  10.0 s 700 tokens, 2500 prompt\n10:05 attempt 2: hidden test PASSED | own check accepted=True | 60.0 s\n")
BS = chr(92)


class ModelCompareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.logs = self.project / "runtime_data" / "measurements" / "logs"
        self.logs.mkdir(parents=True)
        self.candidates = self.project / "runtime_data" / "devvm_candidates" / "s"

    def candidate(self, name, lines, tests=40):
        folder = self.candidates / name
        (folder / "tests").mkdir(parents=True)
        (folder / "mod.py").write_text("x = 1\n\n" * lines, encoding="utf-8")
        (folder / "tests" / "test_mod.py").write_text("y = 1\n" * tests, encoding="utf-8")
        (folder / "acceptance_step1.py").write_text("z = 1\n" * tests, encoding="utf-8")
        return folder

    def run_files(self):
        (self.logs / "devvm_build_s_1.log").write_text(LOG, encoding="utf-8")
        relative = BS.join(["..", "workspace", "GUPPI_OS", "runtime_data", "devvm_candidates", "s", "a1"])
        attempts = [{"attempt": 1, "hidden_passed": False, "seconds": 100.0, "calls": 7, "agent_runs": 2, "coder": "q", "models": {"coder": "m", "planner": "m"}, "stages": [{"hidden_passed": False}], "exported_to": relative},
                    {"attempt": 2, "hidden_passed": True, "seconds": 60.0, "calls": 3, "agent_runs": 1, "coder": "q", "models": {"coder": "m"}, "stages": [{"hidden_passed": True}], "exported_to": str(self.candidates / "a2")}]
        (self.logs / "devvm_build_s_1.json").write_text(json.dumps({"spec": "s", "attempts": attempts}), encoding="utf-8")

    def test_speed_rows_come_from_the_sweep_files_and_the_manual_file_and_skip_errors(self):
        measurements = self.project / "runtime_data" / "measurements"
        (measurements / "moe_sweep_r_2026-10-09.json").write_text(json.dumps({"recipe": "r", "rows": [{"n_cpu_moe": 44, "ubatch": 512, "gen_tps": 30.0}, {"error": "x"}]}), encoding="utf-8")
        (measurements / "model_comparison_manual.json").write_text(json.dumps({"speed": [{"recipe": "r", "n_cpu_moe": 40, "gen_tps": 33.0}]}), encoding="utf-8")
        (measurements / "moe_sweep_bad.json").write_text("{broken", encoding="utf-8")
        self.assertEqual([(r["n_cpu_moe"], r["source"]) for r in speed_rows(measurements)], [(44, "moe_sweep_r_2026-10-09.json"), (40, "manual")])

    def test_every_attempt_has_its_own_tokens_and_the_failed_one_counts_too(self):
        (self.logs / "devvm_build_s_1.log").write_text(LOG, encoding="utf-8")
        self.assertEqual(attempt_tokens(self.logs / "devvm_build_s_1.log"), {1: 1500, 2: 700})
        self.assertEqual(attempt_tokens(self.logs / "devvm_build_s_1.log", prompt=True), {1: 4000, 2: 2500})
        self.assertIsNone(attempt_tokens(self.logs / "nothing.log"))

    def test_tokens_after_the_last_closing_line_belong_to_the_last_attempt(self):
        (self.logs / "x.log").write_text(LOG + "10:06 agent coder (alone)   m   error  1 calls  1.0 s 50 tokens\n", encoding="utf-8")
        self.assertEqual(attempt_tokens(self.logs / "x.log"), {1: 1500, 2: 750})

    def test_built_code_is_the_model_code_only_and_the_used_code_needs_a_passed_attempt(self):
        self.candidate("a1", 30)
        self.candidate("a2", 20)
        self.run_files()
        failed, passed = build_rows(self.logs, self.project)
        self.assertEqual((failed["tokens"], failed["built_lines"], failed["used_lines"], failed["passed"]), (1500, 30, 0, False))
        self.assertEqual((passed["tokens"], passed["built_lines"], passed["used_lines"], passed["models"], passed["tokens_per_second"]), (700, 20, 20, ["m"], 11.7))

    def test_the_summary_counts_the_failed_attempt_in_the_needed_tokens(self):
        self.candidate("a1", 30)
        self.candidate("a2", 20)
        self.run_files()
        summary = summary_rows(build_rows(self.logs, self.project))
        self.assertEqual(summary, [{"spec": "s", "models": "m", "tokens": 2200, "built": 50, "used": 20, "attempts": 2, "passed": 1, "tokens_per_used_line": 110}])

    def test_a_file_identical_to_the_seed_is_not_counted_as_built_unless_the_seed_is_newer(self):
        folder = self.candidate("a1", 10)
        seeds = self.project / "seeds"
        seeds.mkdir()
        (seeds / "mod.py").write_bytes((folder / "mod.py").read_bytes())
        (folder / "own.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
        old = (folder / "mod.py").stat().st_mtime - 100
        os.utime(seeds / "mod.py", (old, old))
        self.assertEqual(code_lines(folder, seeds), 2)
        self.assertEqual(code_lines(folder), 12)
        new = (folder / "mod.py").stat().st_mtime + 100
        os.utime(seeds / "mod.py", (new, new))
        self.assertEqual(code_lines(folder, seeds), 12, "a seed copied after the run is not the seed of that run")
        self.assertIsNone(code_lines(self.project / "missing"))

    def test_editor_sessions_come_from_the_manual_file_and_get_their_own_table(self):
        from model_compare import editor_rows
        measurements = self.project / "runtime_data" / "measurements"
        (measurements / "model_comparison_manual.json").write_text(json.dumps({"editor_sessions": [{"tool": "Cline", "model": "m", "task": "t", "minutes": 61, "requests": 128, "tool_calls": 109, "tool_errors": 34}]}), encoding="utf-8")
        rows = editor_rows(measurements)
        text = render([], [], rows)
        self.assertIn("| Cline | m | t | 61 | 128 | None | None | 109 (34) |", text)
        self.assertNotIn("Sitzungen im Editor", render([], [], []))
        self.assertEqual(editor_rows(self.project / "nothing"), [])

    def test_the_table_has_the_needed_built_and_used_columns(self):
        self.candidate("a1", 30)
        self.candidate("a2", 20)
        self.run_files()
        text = render([{"recipe": "r", "window": 1, "n_cpu_moe": 2, "ubatch": 3, "prompt_tokens": 4, "prompt_tps": 5, "gen_tps": 6, "free_gib": 7, "source": "s"}], build_rows(self.logs, self.project))
        self.assertIn("| r | 1 | 2 | 3 | 4 | 5 | 6 | 7 | s |", text)
        self.assertIn("| s | m | 2 (1) | 2200 | 50 | 20 | 110 |", text)
        self.assertIn("Benötigte Token", text)
        self.assertIn("Genutzter Code", text)


if __name__ == "__main__":
    unittest.main()
