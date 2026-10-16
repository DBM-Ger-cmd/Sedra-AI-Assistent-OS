import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.agent_manager.token_records import token_records
from guppi_runtime.agent_manager.usage_meter import token_view

UIX = Path(__file__).resolve().parents[1] / "src" / "guppi_runtime" / "uix"
SERVER = Path(__file__).resolve().parents[1] / "src" / "guppi_runtime" / "uix_server.py"


class MeterWindowWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UIX / "retro_desktop.html").read_text(encoding="utf-8")
        cls.js = (UIX / "js" / "meter.js").read_text(encoding="utf-8")

    def test_start_menu_taskbar_and_the_window_exist_once(self):
        self.assertEqual(self.html.count('id="meterWindow"'), 1)
        self.assertEqual(len(re.findall(r'onclick="openMeter\(\)', self.html)), 1)      # start menu; since Build 5 the taskbar holds Deck, GUPPI, Werkstatt, Besatzung, Projekte and the Deck row 'Token heute' opens the meter

    def test_script_is_loaded_before_main(self):
        self.assertLess(self.html.index("/uix/js/meter.js"), self.html.index("/uix/js/main.js"))

    def test_window_is_read_only_and_reads_only_the_meter_route(self):
        self.assertNotIn("POST", self.js)
        self.assertEqual(re.findall(r"api\('([^']+)'", self.js), ["/api/meter"])

    def test_the_server_serves_the_route_read_only(self):
        self.assertRegex(SERVER.read_text(encoding="utf-8"), r"'/api/meter': hub\.meter_view,\s+# read-only")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_script_parses(self):
        run = subprocess.run(["node", "--check", str(UIX / "js" / "meter.js")], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_coin_hole_script_comes_before_the_meter_and_parses(self):
        self.assertLess(self.html.index("/uix/js/coin_hole.js"), self.html.index("/uix/js/meter.js"))
        self.assertIn("createCoinHole(", self.js)
        if shutil.which("node"):
            run = subprocess.run(["node", "--check", str(UIX / "js" / "coin_hole.js")], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(run.returncode, 0, run.stderr)


class TokenRecordsTest(unittest.TestCase):
    def test_build_logs_become_records_with_date_spec_model_and_summed_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "runtime_data" / "measurements" / "logs"; logs.mkdir(parents=True)
            (logs / "devvm_build_coin_hole_2026-10-12_134703.log").write_text(
                "14:05:44    agent solo developer         qwen3.6-35b-a3b        hand_in      6 calls   97.0 s 3079 tokens, 22739 prompt, peak 5717\n"
                "14:08:04    agent solo developer (rework 1) qwen3.6-35b-a3b        hand_in      8 calls  140.2 s 3020 tokens, 55823 prompt, peak 7991\n"
                "14:08:04    tidy: stripped -\n", encoding="utf-8")
            (logs / "devvm_build_empty_2026-10-12_100000.log").write_text("no agent here\n", encoding="utf-8")
            (logs / "smallteam_2026-10-06.log").write_text("x", encoding="utf-8")
            self.assertEqual(token_records(tmp), [{"date": "2026-10-12", "spec": "coin_hole", "model": "qwen3.6-35b-a3b", "tokens": 6099}])
            self.assertEqual(token_view(token_records(tmp), "2026-10-12")["ranges"]["today"], {"tokens": 6099, "runs": 1})
            self.assertEqual(token_records(Path(tmp) / "none"), [])


if __name__ == "__main__":
    unittest.main()
