"""A3, App Team (SPEC_APP_TEAM_v1): Überblick und Modi in einem App-Reiter der Harness-Shell. Reine Teile (Modi, Ort, Menü, Manifest) und der Browser:
Überblick aus vier Werkzeugen (TM-10), Zustand je Modus (TM-20), gemerkter Modus (TM-21), Aufräumen beim Schließen. Die alte Shell `paperclip` wird nicht berührt (TM-50)."""
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
        res = node("globalThis.sedraDom = {}; require(%s); const T = globalThis.sedraHarness.team;"
                   "process.stdout.write(JSON.stringify({modi: T.MODI.map(m=>[m.id, m.zellen.map(z=>z.type)]), wahl: [T.modusWahl('kosten'), T.modusWahl('x'), T.modusWahl(null)]}));"
                   % json.dumps(str(UIX / "shells" / "harness" / "team.js")))
        modi = dict(res["modi"])
        self.assertEqual(list(modi), ["ueberblick", "issues", "vorhaben", "organigramm", "routinen", "kosten"])
        self.assertEqual(modi["ueberblick"], ["decision", "issue", "agent", "meter"], "TM-10: vier Werkzeuge zugleich")
        self.assertTrue(all(len(z) == 1 for m, z in modi.items() if m != "ueberblick"))
        self.assertEqual(res["wahl"], ["kosten", "ueberblick", "ueberblick"])

    def test_jede_zelle_hat_ein_werkzeug(self):
        behandelt = set()
        for tool in (UIX / "tools").glob("*/tool.yaml"):
            behandelt.update(h.split(":")[0] for h in yaml.safe_load(tool.read_text(encoding="utf-8"))["tool"].get("handles", []))
        for typ in ("decision", "issue", "intent", "agent", "routine", "meter"):
            self.assertIn(typ, behandelt, typ)

    def test_ort_menue_und_werkzeug(self):
        orte = {o["id"]: o for o in json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"]}
        self.assertEqual(orte["team"]["object"], {"type": "team", "id": "app", "title": "Team"})
        self.assertIn("team", orte["team"]["words"])
        self.assertNotIn("team", orte["org"]["words"], "das Wort gehört der App")
        gruppen = json.loads((UIX / "shells" / "harness" / "start_gruppen.json").read_text(encoding="utf-8"))
        self.assertEqual(gruppen["zuordnung"]["team"], "arbeit")
        for versteckt in ("org", "routines", "intents", "werkzeug-board"):
            self.assertIn(versteckt, gruppen["ausblenden"], "TM-30: nur das Team steht im Menü")
        yml = yaml.safe_load((UIX / "tools" / "team" / "tool.yaml").read_text(encoding="utf-8"))
        man, fehler = check_tool(yml, UIX / "tools" / "team", "package")
        self.assertEqual(fehler, [])
        self.assertEqual(man["handles"], ["team"])
        self.assertEqual(man["api"], [], "der Platzhalter ruft keine Route")

    def test_kein_hex_keine_zweite_einhaengestelle_dateigroesse(self):
        js = (UIX / "shells" / "harness" / "team.js").read_text(encoding="utf-8")
        css = (UIX / "shells" / "harness" / "team.css").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r":\s*#[0-9a-fA-F]{3,8}", css), [])
        self.assertNotIn("mountTool", js, "TM-01: der Einhängeweg ist der von app.flaeche, kein zweiter")
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("setInterval", js)
        self.assertLessEqual(len(js.splitlines()), 400)
        self.assertLessEqual(len((UIX / "shells" / "harness" / "app.js").read_text(encoding="utf-8").splitlines()), 400)

    def test_alte_shell_paperclip_ist_unberuehrt_im_manifest(self):
        text = (UIX / "shells" / "paperclip" / "shell.yaml").read_text(encoding="utf-8")
        self.assertIn("id: paperclip", text)
        self.assertNotIn("team.js", text)


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
                page.evaluate(f"()=>{{ const S = {S}; return {H}.app.oeffnen(S, {{object: {{type: 'team', id: 'app', title: 'Team'}}, label: 'Team'}}); }}")
                page.wait_for_selector(".hs-tm-pane.raster", timeout=WARTE_MS)
                self.assertEqual(page.locator(".hs-app-reiter-knopf[data-modus]").count(), 6)
                # TM-10: der Überblick hängt vier Werkzeuge zugleich ein
                for tid in ("decisions", "board", "org", "meter"):
                    page.wait_for_selector(f'.hs-tm-pane[data-modus="ueberblick"] [data-tool="{tid}"]', timeout=WARTE_MS)
                self.assertEqual(page.locator('.hs-tm-pane[data-modus="ueberblick"] .hs-tm-zelle').count(), 4)
                self.assertEqual(page.locator('.hs-tm-pane[data-modus="issues"]').count(), 0, "erst beim ersten Öffnen eingehängt")

                # TM-20: ein Modus wird beim ersten Öffnen eingehängt und beim Wechsel nur versteckt
                page.click('.hs-app-reiter-knopf[data-modus="routinen"]')
                page.wait_for_selector('.hs-tm-pane[data-modus="routinen"] [data-tool="routines"]', timeout=WARTE_MS)
                self.assertTrue(page.locator('.hs-tm-pane[data-modus="ueberblick"]').evaluate("e=>e.hidden"))
                page.evaluate("()=>{ window.__marke = document.querySelector('.hs-tm-pane[data-modus=\"ueberblick\"] [data-tool=\"board\"]'); }")
                page.click('.hs-app-reiter-knopf[data-modus="ueberblick"]')
                self.assertFalse(page.locator('.hs-tm-pane[data-modus="ueberblick"]').evaluate("e=>e.hidden"))
                self.assertTrue(page.evaluate("()=>window.__marke === document.querySelector('.hs-tm-pane[data-modus=\"ueberblick\"] [data-tool=\"board\"]')"),
                                "der Überblick wurde nicht neu eingehängt")

                # TM-21: der Modus wird gemerkt – nur der Name
                page.click('.hs-app-reiter-knopf[data-modus="kosten"]')
                self.assertEqual(page.evaluate("()=>localStorage.getItem('sedra.harness.team.modus')"), "kosten")

                # Schließen hängt alle eingehängten Zellen aus
                page.evaluate(f"()=>{H}.reiter.schliessen({S}, 'app:team:app')")
                self.assertEqual(page.locator(".hs-tm-pane").count(), 0)
                self.assertEqual(page.locator(".hs-tm-zelle").count(), 0)
                self.assertEqual(fehler, [])
                b.close()
        finally:
            stop()


if __name__ == "__main__":
    unittest.main()
