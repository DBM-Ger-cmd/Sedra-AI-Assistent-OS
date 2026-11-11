"""A3, App Translator (SPEC_APP_TRANSLATOR_v1): vier Modi in einem App-Reiter der Harness-Shell. Reine Teile (Modi gleich der Shell fisch, Ort, Menü) und der Browser:
Zustand je Modus (TR-20), Wolke (TR-11), gemerkter Modus (TR-21), Strg+K (TR-12), Übergabe an den offenen Translator (TR-30), neue `frage` auf einen offenen Einzelreiter (TR-31),
Aufräumen beim Schließen. Die alte Shell `fisch` wird nicht berührt (TR-50)."""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

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
    def test_modi_gleich_der_alten_shell_ueber_sedraFischPure(self):
        res = node("globalThis.sedra = {registerShell(){}}; require(%s); const P = globalThis.sedraFischPure;"
                   "globalThis.sedraDom = {}; require(%s); const T = globalThis.sedraHarness.translator;"
                   "process.stdout.write(JSON.stringify({fisch: P.MODI.map(m=>[m.id, m.label, m.object, m.platzhalter]), app: T.MODI.map(m=>[m.id, m.label, m.object, m.platzhalter]),"
                   "wahl: [T.modusWahl('news'), T.modusWahl('x'), T.modusWahl(null)], fuer: [T.modusFuer('transkript').id, T.modusFuer('task')]}));"
                   % (json.dumps(str(UIX / "shells" / "fisch" / "shell.js")), json.dumps(str(UIX / "shells" / "harness" / "translator.js"))))
        self.assertEqual(res["app"], res["fisch"], "TR-10: Shell und App lesen dieselben Objekte")
        self.assertEqual(res["wahl"], ["news", "uebersetzen", "uebersetzen"])
        self.assertEqual(res["fuer"], ["transkript", None])

    def test_ort_menue_und_werkzeug(self):
        orte = json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"]
        ort = next(o for o in orte if o["id"] == "translator")
        self.assertEqual(ort["object"], {"type": "translator", "id": "app", "title": "Translator"})
        gruppen = json.loads((UIX / "shells" / "harness" / "start_gruppen.json").read_text(encoding="utf-8"))
        self.assertEqual((gruppen["zuordnung"]["translator"], gruppen["zuordnung"]["nachrichten"]), ("arbeit", "arbeit"))
        for hidden in ("uebersetzung", "transkript", "aufnahme", "werkzeug-nachrichten"):
            self.assertIn(hidden, gruppen["ausblenden"], "TR-E2: nur der Translator steht im Menü")
        self.assertTrue((UIX / "tools" / "translator" / "tool.yaml").is_file())

    def test_kein_hex_keine_zweite_einhaengestelle_dateigroesse(self):
        js = (UIX / "shells" / "harness" / "translator.js").read_text(encoding="utf-8")
        css = (UIX / "shells" / "harness" / "translator.css").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r":\s*#[0-9a-fA-F]{3,8}", css), [])
        self.assertNotIn("mountTool", js, "TR-01: der Einhängeweg ist der von app.flaeche, kein zweiter")
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("setInterval", js)
        self.assertLessEqual(len(js.splitlines()), 400)
        self.assertLessEqual(len((UIX / "shells" / "harness" / "app.js").read_text(encoding="utf-8").splitlines()), 400)

    def test_alte_shell_fisch_ist_unberuehrt_im_manifest(self):
        text = (UIX / "shells" / "fisch" / "shell.yaml").read_text(encoding="utf-8")
        self.assertIn("id: fisch", text)
        self.assertNotIn("translator", text.replace("Translator", ""))


class Browser(unittest.TestCase):
    def test_app_im_browser(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise unittest.SkipTest("playwright fehlt")
        import uix_check
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell="harness")
        try:
            hub = uix_check.LAST_HUB
            seen = []

            class FakeServer:
                def loaded_models(self):
                    return [{"identifier": "fake", "modelKey": "fake"}]

            def execute(mission, request):
                seen.append(request["messages"][-1]["content"])
                return {"status": "completed", "model_result": {"content": "ÜBERSETZUNG:\nFertig.\nUNSICHERHEITEN:\n- keine\nHINWEISE:\n- keine"}}
            hub.runtime.llama_server = FakeServer()
            hub.runtime.control.execute = execute
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                page = b.new_page(viewport={"width": 1400, "height": 860})
                fehler = []
                page.on("pageerror", lambda e: fehler.append(str(e)))
                page.goto(url)
                wait_until_started(page, shell="harness")
                S = "window.sedra.shells.get('harness')"
                H = "window.sedraHarness"
                offen = f"()=>{{ const S = {S}; return {H}.app.oeffnen(S, {{object: {{type: 'translator', id: 'app', title: 'Translator'}}, label: 'Translator'}}); }}"
                zaehle = f"()=>{{ const S = {S}; return {H}.app.liste(S); }}"

                page.evaluate(offen)
                page.wait_for_selector(".hs-tr-wolke", timeout=WARTE_MS)
                self.assertEqual(page.locator(".hs-app-reiter-knopf[data-modus]").count(), 4)
                page.wait_for_selector('.hs-tr-pane[data-modus="uebersetzen"] [data-tool="uebersetzer"]', timeout=WARTE_MS)
                self.assertEqual(page.locator('.hs-tr-pane[data-modus="news"]').count(), 0, "erst beim ersten Öffnen eingehängt")

                # TR-20: Zustand bleibt beim Moduswechsel
                page.fill('.hs-tr-pane[data-modus="uebersetzen"] textarea', "Mein Entwurf bleibt")
                page.click('.hs-app-reiter-knopf[data-modus="news"]')
                page.wait_for_selector('.hs-tr-pane[data-modus="news"] [data-tool="nachrichten"]', timeout=WARTE_MS)
                self.assertTrue(page.locator('.hs-tr-pane[data-modus="uebersetzen"]').evaluate("e=>e.hidden"))
                self.assertIn("Interessen", page.text_content('.hs-tr-pane[data-modus="news"]'), "TR-E5")
                page.click('.hs-app-reiter-knopf[data-modus="uebersetzen"]')
                self.assertEqual(page.input_value('.hs-tr-pane[data-modus="uebersetzen"] textarea'), "Mein Entwurf bleibt")
                self.assertFalse(page.locator('.hs-tr-pane[data-modus="uebersetzen"]').evaluate("e=>e.hidden"))

                # TR-11: die Wolke gibt den Satz an den aktiven Modus; Enter sendet, Umschalt+Enter bricht um
                page.fill(".hs-tr-wolke", "Das Zeug kommt Montag")
                page.keyboard.press("Enter")
                page.wait_for_selector(".t-ue-ergebnis", timeout=WARTE_MS)
                self.assertTrue(any("Das Zeug kommt Montag" in s for s in seen), seen)
                self.assertEqual(page.input_value(".hs-tr-wolke"), "")

                # TR-21: der Modus wird gemerkt (nie ein Text)
                page.click('.hs-app-reiter-knopf[data-modus="transkript"]')
                self.assertEqual(page.evaluate("()=>localStorage.getItem('sedra.harness.translator.modus')"), "transkript")
                self.assertNotIn("Montag", json.dumps(page.evaluate("()=>Object.assign({}, localStorage)")))

                # TR-12: Strg+K fokussiert die Wolke, solange der Reiter vorn ist
                page.evaluate("()=>document.activeElement && document.activeElement.blur()")
                page.keyboard.press("Control+k")
                self.assertTrue(page.evaluate("()=>document.activeElement && document.activeElement.classList.contains('hs-tr-wolke')"))

                # TR-30: ein open auf den Übersetzer kommt im offenen Translator an, auch wenn der Modus schon eingehängt ist
                vorher = len(seen)
                page.evaluate(f"()=>{S}.shellApi.open({{type: 'uebersetzung', id: 'wolke', title: 'Übersetzen', frage: 'Neuer Text aus dem Transkript'}})")
                page.wait_for_function("()=>document.querySelector('.hs-app-reiter-knopf[data-modus=\"uebersetzen\"]').classList.contains('on')", timeout=WARTE_MS)
                for _ in range(40):
                    if len(seen) > vorher:
                        break
                    page.wait_for_timeout(250)
                self.assertTrue(any("Neuer Text aus dem Transkript" in s for s in seen[vorher:]), seen[vorher:])
                tabs = page.evaluate(zaehle)
                self.assertEqual([t for t in tabs if t.startswith("app:translator")], ["app:translator:app"])
                self.assertEqual([t for t in tabs if t.startswith("app:uebersetzung")], [], "kein loser Einzelreiter daneben")
                self.assertEqual(page.evaluate("()=>localStorage.getItem('sedra.harness.translator.modus')"), "uebersetzen")

                # Schließen hängt alle eingehängten Modi aus
                page.evaluate(f"()=>{H}.reiter.schliessen({S}, 'app:translator:app')")
                self.assertEqual(page.evaluate(f"()=>!!{S}._translatorAnsicht"), False)
                self.assertEqual(page.locator(".hs-tr-wolke").count(), 0)

                # TR-31 (B10): ohne offenen Translator öffnet derselbe Aufruf den Einzelreiter; eine neue `frage` auf den offenen Reiter geht nicht verloren
                vorher = len(seen)
                page.evaluate(f"()=>{S}.shellApi.open({{type: 'uebersetzung', id: 'wolke', title: 'Übersetzen', frage: 'Erste Frage'}})")
                for _ in range(40):
                    if len(seen) > vorher:
                        break
                    page.wait_for_timeout(250)
                page.evaluate(f"()=>{S}.shellApi.open({{type: 'uebersetzung', id: 'wolke', title: 'Übersetzen', frage: 'Zweite Frage'}})")
                for _ in range(40):
                    if any("Zweite Frage" in s for s in seen):
                        break
                    page.wait_for_timeout(250)
                self.assertTrue(any("Erste Frage" in s for s in seen[vorher:]))
                self.assertTrue(any("Zweite Frage" in s for s in seen[vorher:]), "TR-31: die neue Frage kommt an")
                self.assertEqual(len([t for t in page.evaluate(zaehle) if t.startswith("app:uebersetzung")]), 1)

                self.assertEqual(fehler, [])
                b.close()
        finally:
            stop()


if __name__ == "__main__":
    unittest.main()
