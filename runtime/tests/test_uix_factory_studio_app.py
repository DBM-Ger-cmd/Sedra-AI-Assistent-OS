"""F3-01, App Factory Studio (erste lesende Stufe): Projekt Browser und Status Dashboard in einem App-Reiter der Harness-Shell.
Reine Teile (Modi, Ort, Menü, Manifest) und der Browser: zwei Modi mit jeweils einer/zwei Zellen (TM-10), Zustand je Modus (TM-20), gemerkter Modus (TM-21).
Die alte Shell bleibt nicht betroffen. Die App ist nur lesend (kein Gate Panel, kein Build-Start)."""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.gateway import check_tool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"
NODE = shutil.which("node")
WARTE_MS = 20000


def node(skript):
    out = subprocess.run([NODE, "-e", skript], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr[:400]
    return json.loads(out.stdout)


class Rein(unittest.TestCase):
    @unittest.skipUnless(NODE, "node fehlt")
    def test_modi_und_wahl(self):
        res = node("globalThis.sedraDom = {}; require(%s); const T = globalThis.sedraHarness.factory_studio;"
                   "process.stdout.write(JSON.stringify({modi: T.MODI.map(m=>[m.id, m.zellen.map(z=>z.type)]), wahl: [T.modusWahl('statusdashboard'), T.modusWahl('x'), T.modusWahl(null)]}));"
                   % json.dumps(str(UIX / "shells" / "harness" / "factory_studio.js")))
        modi = dict(res["modi"])
        self.assertEqual(list(modi), ["projektbrowser", "statusdashboard"])
        self.assertEqual(modi["projektbrowser"], ["project"])
        self.assertEqual(modi["statusdashboard"], ["decision", "meter"])
        self.assertEqual(res["wahl"], ["statusdashboard", "projektbrowser", "projektbrowser"])

    def test_jede_zelle_hat_ein_werkzeug(self):
        behandelt = set()
        for tool in (UIX / "tools").glob("*/tool.yaml"):
            behandelt.update(h.split(":")[0] for h in yaml.safe_load(tool.read_text(encoding="utf-8"))["tool"].get("handles", []))
        for typ in ("project", "decision", "meter"):
            self.assertIn(typ, behandelt, typ)

    def test_ort_menue_und_werkzeug(self):
        orte = {o["id"]: o for o in json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"]}
        self.assertEqual(orte["factory-studio"]["object"], {"type": "factory-studio", "id": "app", "title": "Factory Studio"})
        self.assertIn("factory", orte["factory-studio"]["words"])
        gruppen = json.loads((UIX / "shells" / "harness" / "start_gruppen.json").read_text(encoding="utf-8"))
        self.assertEqual(gruppen["zuordnung"]["factory-studio"], "arbeit")
        yml = yaml.safe_load((UIX / "tools" / "factory-studio" / "tool.yaml").read_text(encoding="utf-8"))
        man, fehler = check_tool(yml, UIX / "tools" / "factory-studio", "package")
        self.assertEqual(fehler, [])
        self.assertEqual(man["handles"], ["factory-studio"])
        self.assertEqual(man["api"], [], "der Platzhalter ruft keine Route")

    def test_kein_hex_keine_zweite_einhaengestelle_dateigroesse(self):
        js = (UIX / "shells" / "harness" / "factory_studio.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("setInterval", js)
        self.assertLessEqual(len(js.splitlines()), 400)


class Browser(unittest.TestCase):
    def test_app_im_browser(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise unittest.SkipTest("playwright fehlt")
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell="harness")
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                page = b.new_page(viewport={"width": 1400, "height": 860})
                fehler = []
                page.on("pageerror", lambda e: fehler.append(str(e)))
                page.goto(url)
                wait_until_started(page, shell="harness")
                S = "window.sedra.shells.get('harness')"
                H = "window.sedraHarness"
                page.evaluate(f"()=>{{ const S = {S}; return {H}.app.oeffnen(S, {{object: {{type: 'factory-studio', id: 'app', title: 'Factory Studio'}}, label: 'Factory Studio'}}); }}")
                page.wait_for_selector(".hs-fs-pane", timeout=WARTE_MS)
                self.assertEqual(page.locator(".hs-app-reiter-knopf").count(), 2)
                # Projekt Browser hängt das files-Werkzeug für project ein
                page.wait_for_selector('.hs-fs-pane[data-modus="projektbrowser"] [data-tool="files"]', timeout=WARTE_MS)
                self.assertEqual(page.locator('.hs-fs-pane[data-modus="projektbrowser"] .hs-fs-zelle').count(), 1)
                # Status Dashboard hängt decisions und meter ein
                page.click('.hs-app-reiter-knopf[data-modus="statusdashboard"]')
                page.wait_for_selector('.hs-fs-pane[data-modus="statusdashboard"] [data-tool="decisions"]', timeout=WARTE_MS)
                page.wait_for_selector('.hs-fs-pane[data-modus="statusdashboard"] [data-tool="meter"]', timeout=WARTE_MS)
                self.assertEqual(page.locator('.hs-fs-pane[data-modus="statusdashboard"] .hs-fs-zelle').count(), 2)
                # TM-21: der Modus wird gemerkt
                page.click('.hs-app-reiter-knopf[data-modus="projektbrowser"]')
                self.assertEqual(page.evaluate("()=>localStorage.getItem('sedra.harness.factory_studio.modus')"), "projektbrowser")
                self.assertEqual(fehler, [])
                b.close()
        finally:
            stop()


if __name__ == "__main__":
    unittest.main()
