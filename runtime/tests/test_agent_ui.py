import re
import shutil
import subprocess
import unittest
from pathlib import Path

UIX = Path(__file__).resolve().parents[1] / "src" / "guppi_runtime" / "uix"


class AgentWindowWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UIX / "retro_desktop.html").read_text(encoding="utf-8")
        cls.js = (UIX / "js" / "agents.js").read_text(encoding="utf-8")

    def test_window_icon_start_menu_and_taskbar_open_the_same_window(self):
        self.assertEqual(self.html.count('id="agentWindow"'), 1)
        self.assertEqual(len(re.findall(r'onclick="openAgents\(\)', self.html)), 3)

    def test_script_is_loaded_before_main(self):
        self.assertLess(self.html.index("/uix/js/agents.js"), self.html.index("/uix/js/main.js"))

    def test_the_icon_is_reachable_by_keyboard(self):
        self.assertIn('role="button" tabindex="0" onclick="openAgents()" onkeydown=', self.html)

    def test_bridge_links_to_the_modules(self):
        missions = (UIX / "js" / "missions.js").read_text(encoding="utf-8")
        for name in ("openAgents", "openDevEnv", "openModels", "openHardware", "openMachineRoom", "openLogbook"):
            self.assertIn(name, missions.split("async function openBridge")[1].split("function candidateSteps")[0])

    def test_window_is_read_only(self):
        self.assertNotIn("method:'POST'", self.js)
        self.assertNotIn('method: "POST"', self.js)
        self.assertEqual(re.findall(r"api\('([^']+)'", self.js), ["/api/agents"])
        self.assertEqual(len(re.findall(r"el\('button'", self.js)), 1, "the only buttons are the tabs")
        self.assertEqual(len(re.findall(r"\.onclick\s*=", self.js)), 1, "the only handler switches a tab")

    def test_uncertain_outcome_has_its_own_wording_and_demo_is_marked(self):
        self.assertIn("Ausgang ungewiss – Reconciliation erforderlich", self.js)
        self.assertIn("DEMO", self.js)
        self.assertIn("UNVERIFIED", self.js)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_scripts_parse(self):
        for name in ("agents.js", "missions.js"):
            run = subprocess.run(["node", "--check", str(UIX / "js" / name)], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
