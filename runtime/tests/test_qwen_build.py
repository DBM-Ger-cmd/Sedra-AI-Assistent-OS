import json
import sys
import tempfile
import unittest
from pathlib import Path
import env_skip

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))
sys.path.insert(0, str(RUNTIME / "src"))

from qwen_build import expected_names, parse_qwen_output, qwen_command, qwen_env, read_journal, stop_reason, tools_are_confined  # noqa: E402


class HelperTests(unittest.TestCase):
    def test_the_command_is_headless_json_and_a_rework_continues_the_session(self):
        first = qwen_command("node", "entry.js", "do it")
        self.assertEqual(first, ["node", "entry.js", "-p", "do it", "--output-format", "json"])
        self.assertEqual(qwen_command("node", "entry.js", "fix", True)[-1], "--continue")
        self.assertNotIn("--yolo", first)
        self.assertNotIn("-y", first)

    def test_no_secret_of_the_pc_reaches_the_agent(self):
        base = {"PATH": "p", "OPENAI_API_KEY": "real", "ANTHROPIC_API_KEY": "real", "GITHUB_TOKEN": "t", "MY_SECRET": "s", "DASHSCOPE_API_KEY": "d", "SYSTEMROOT": "C:\\Windows", "GOOGLE_APPLICATION_CREDENTIALS": "g"}
        env = qwen_env("H", "http://127.0.0.1:1/v1", "m", base)
        self.assertEqual(env["OPENAI_API_KEY"], "noop")
        for name in ("ANTHROPIC_API_KEY", "GITHUB_TOKEN", "MY_SECRET", "DASHSCOPE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"):
            self.assertNotIn(name, env)
        self.assertEqual((env["HOME"], env["USERPROFILE"], env["OPENAI_BASE_URL"], env["OPENAI_MODEL"]), ("H", "H", "http://127.0.0.1:1/v1", "m"))
        self.assertEqual(env["SYSTEMROOT"], "C:\\Windows")

    def test_the_journal_of_a_run_is_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "j.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in ({"tool": "read_file", "ok": True}, {"tool": "read_file", "ok": False}, {"tool": "edit_file", "ok": True})) + "\n", encoding="utf-8")
            self.assertEqual(read_journal(path), ({"read_file": 2, "edit_file": 1}, 3, 1))
            self.assertEqual(read_journal(Path(tmp) / "none.jsonl"), ({}, 0, 0))

    def test_the_output_of_the_agent_is_read_defensively(self):
        text = json.dumps([{"type": "system"}, {"type": "assistant", "message": {"usage": {"input_tokens": 60, "output_tokens": 10}}}, {"type": "assistant", "message": {"usage": {"input_tokens": 40, "output_tokens": 10}}},
                           {"type": "result", "result": "done", "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 70}}])
        info = parse_qwen_output(text)
        self.assertEqual((info["completion_tokens"], info["prompt_tokens"], info["cached_tokens"], info["turns"], info["result"]), (20, 100, 70, 2, "done"))      # the usage of the result event counts once
        self.assertEqual(parse_qwen_output(json.dumps([{"type": "assistant", "message": {"usage": {"input_tokens": 5, "output_tokens": 1}}}]))["prompt_tokens"], 5)
        self.assertEqual(parse_qwen_output("not json at all")["completion_tokens"], 0)
        self.assertEqual(parse_qwen_output("log line\n" + text)["result"], "done")

    def test_the_end_of_a_run_is_named_in_the_words_of_the_failure_layers(self):
        self.assertEqual(stop_reason(0, False, True), "hand_in")
        self.assertEqual(stop_reason(1, True, False), "time")
        self.assertEqual(stop_reason(1, False, False), "error")
        self.assertEqual(stop_reason(0, False, False), "no_tool_call")

    def test_only_exactly_our_tools_count_as_confined(self):
        ours = [f"mcp__devvm__{n}" for n in expected_names(False)]
        self.assertTrue(tools_are_confined(ours, False)[0])
        self.assertFalse(tools_are_confined(ours + ["run_shell_command"], False)[0])
        self.assertFalse(tools_are_confined(ours[:-1], False)[0])                       # a missing tool is a different set, too
        self.assertFalse(tools_are_confined(ours + ["mcp__devvm__run_python"], False)[0])
        self.assertTrue(tools_are_confined([f"mcp__devvm__{n}" for n in expected_names(True)], True)[0])


if __name__ == "__main__":
    unittest.main()


class QwenProbeTests(unittest.TestCase):
    def test_the_probe_builds_the_command_and_refuses_unsafe_seeds(self):
        sys.path.insert(0, str(RUNTIME / "benchmarks" / "probes"))
        from qwen_probe import command, safe_seed
        cmd = command("py", "P", "am007_crews", "coder.local_primary", "qwen-light", stage="rules", seed="am007_crews/s/after_basics")
        self.assertEqual(cmd[cmd.index("--self-check") + 1], "light")
        self.assertEqual(cmd[cmd.index("--only") + 1], "rules")
        self.assertTrue(cmd[cmd.index("--seed") + 1].replace("\\", "/").endswith("P/runtime_data/devvm_snapshots/am007_crews/s/after_basics"))
        self.assertNotIn("--yolo", cmd)
        for bad in ("../x", "/abs/path", "a/../b"):
            with self.assertRaises(ValueError): safe_seed(bad)
        self.assertIsNone(safe_seed(None))


class SystemModeTests(unittest.TestCase):
    @env_skip.needs_dulwich
    def test_the_system_prompt_modes_and_the_registered_tools(self):
        from qwen_build import our_system_text
        self.assertNotIn("--system-prompt", qwen_command("node", "e.js", "p"))
        self.assertEqual(qwen_command("node", "e.js", "p", False, "append", "OUR")[-2:], ["--append-system-prompt", "OUR"])
        lean = qwen_command("node", "e.js", "p", True, "lean", "OUR")
        self.assertEqual(lean[lean.index("--system-prompt") + 1], "OUR"); self.assertEqual(lean[-1], "--continue")
        self.assertIn("ONLY developer", our_system_text("full"))
        self.assertIn("You cannot run code", our_system_text("none")); self.assertNotIn("write ONE small script", our_system_text("none"))
        import agent_tool_probe as probe
        output = json.dumps([{"type": "system", "subtype": "init", "tools": ["manage_memory", "mcp__devvm__read_file"]}, {"type": "result"}])
        self.assertEqual(probe.init_tools(output), ["manage_memory", "mcp__devvm__read_file"])
        names = probe.all_tool_names({"init_tools": ["manage_memory"], "tools": [["mcp__devvm__read_file"], ["mcp__devvm__write_file"]]})
        self.assertEqual(names, ["manage_memory", "mcp__devvm__read_file", "mcp__devvm__write_file"])
        self.assertFalse(probe.judge(names)[0])                                             # a registered memory tool is a foreign tool even if it was not declared in the first request


class SeedTests(unittest.TestCase):
    def test_the_standard_test_always_gets_its_seed_files(self):
        text = (RUNTIME / "benchmarks" / "qwen_build.py").read_text(encoding="utf-8")
        self.assertIn('args.spec == "bench_std" and not args.seed', text)
        self.assertIn("bench_std_seed", text)
        seed = RUNTIME / "benchmarks" / "bench_std_seed"
        self.assertEqual(sorted(p.name for p in seed.glob("*.py")), ["ledger.py", "main.py", "util.py"])
