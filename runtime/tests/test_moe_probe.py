import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks" / "probes"))
sys.path.insert(0, str(RUNTIME / "src"))

from moe_probe import command, numbers  # noqa: E402


class MoeProbeTests(unittest.TestCase):
    def test_defaults_and_bad_options(self):
        cmd = command("py", "P", "coder.local_q4km", {})
        self.assertEqual((cmd[cmd.index("--window") + 1], cmd[cmd.index("--moe") + 1], cmd[cmd.index("--ubatch") + 1]), ("32768", "44,40,36,32,28", "1024"))
        bad = command("py", "P", "coder.local_q4km", {"window": 10**9, "moe": ["x; rm"], "ubatch": [], "prompt_tokens": -1})
        self.assertEqual((bad[bad.index("--window") + 1], bad[bad.index("--moe") + 1], bad[bad.index("--prompt-tokens") + 1]), ("32768", "44,40,36,32,28", "16000"))
        self.assertEqual(numbers([30, 26], 1, 99, "d"), "30,26")
        self.assertNotIn("--full-gpu", cmd)

    def test_the_manager_finds_the_probe(self):
        from guppi_runtime.agent_manager.run_worker import probe_script
        self.assertTrue(Path(probe_script(str(RUNTIME), "probe_moe")).is_file())


if __name__ == "__main__":
    unittest.main()
