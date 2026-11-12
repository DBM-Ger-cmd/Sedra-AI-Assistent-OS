"""A3, App Übersicht (SPEC_APP_UEBERSICHT_v1): der Baum der Gesamtlage in der Harness-Shell. Reine Teile (Modell, Zustand, Klappen, Gemerktes, Ort, Menü, Manifest) und der Browser:
Gruppen, Klappen mit „⚠ n wartet“ (UE-12), eine Zeile öffnet die App (UE-10), gemerkte Gruppen (UE-20). Die alte Shell `cockpit` wird nicht berührt (UE-50)."""
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
HARNESS_JS = UIX / "shells" / "harness" / "uebersicht.js"
NODE = shutil.which("node")
WARTE_MS = 20000


def node(skript):
    out = subprocess.run([NODE, "-e", skript], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr[:400]
    return json.loads(out.stdout)


def laden():
    return "globalThis.sedraDom = {}; require(%s); const U = globalThis.sedraHarness.uebersicht;" % json.dumps(str(HARNESS_JS))


LISTE = {"gruppen": [{"id": "arbeit", "titel": "Arbeit", "symbol": "▤", "apps": [{"id": "tasks", "label": "Aufgaben", "hint": "die Arbeit"}, {"id": "team", "label": "Team", "hint": "Überblick"}]},
                     {"id": "modelle", "titel": "Modelle", "symbol": "◆", "apps": [{"id": "models", "label": "Werkstatt", "hint": "Modelle"}]}]}


class Rein(unittest.TestCase):
    @unittest.skipUnless(NODE, "node fehlt")
    def test_modell_kopf_je_gruppe_zeile_je_app_und_wartend(self):
        zustand = {"tasks": {"note": "2 offen · 1 wartet auf dich", "ton": "warn"}}
        res = node(laden() + "process.stdout.write(JSON.stringify(U.modell(%s, %s).map(r=>[r.kind, r.schluessel, r.note || '', r.wartet === undefined ? null : r.wartet, r.anzahl === undefined ? null : r.anzahl])));"
                   % (json.dumps(LISTE), json.dumps(zustand)))
        self.assertEqual([r[:2] for r in res], [["head", "g:arbeit"], ["row", "a:tasks"], ["row", "a:team"], ["head", "g:modelle"], ["row", "a:models"]])
        self.assertEqual(res[0][3:], [1, 2], "UE-12: der Kopf zählt, was wartet")
        self.assertEqual(res[1][2], "2 offen · 1 wartet auf dich")
        self.assertEqual(res[2][2], "Überblick", "ohne Zustand steht der Hinweis der App")
        self.assertEqual(res[3][3:], [0, 1])

    @unittest.skipUnless(NODE, "node fehlt")
    def test_zugeklappt_zeigt_nur_den_kopf(self):
        res = node(laden() + "const r = U.modell(%s, {}); process.stdout.write(JSON.stringify([U.sichtbar(r, ['arbeit']).map(x=>x.schluessel), U.sichtbar(r, []).map(x=>x.schluessel)]));"
                   % json.dumps(LISTE))
        self.assertEqual(res[0], ["g:arbeit", "a:tasks", "a:team", "g:modelle"])
        self.assertEqual(res[1], ["g:arbeit", "g:modelle"])

    @unittest.skipUnless(NODE, "node fehlt")
    def test_zustand_aus_den_vorhandenen_routen(self):
        daten = {"missions": [{"offen": True, "pending_gates": 1}, {"offen": True, "pending_gates": 0}, {"offen": False}],
                 "models": {"server": {"running": True, "model": "qwen"}}}
        res = node(laden() + "process.stdout.write(JSON.stringify([U.zustandAus(%s), U.zustandAus({}), U.zustandAus(null)]));" % json.dumps(daten))
        self.assertEqual(res[0]["tasks"], {"note": "2 offen · 1 wartet auf dich", "ton": "warn"})
        self.assertEqual(res[0]["models"], {"note": "qwen geladen", "ton": "ok"})
        self.assertEqual(res[1]["tasks"], {"note": "nichts offen", "ton": ""})
        self.assertNotIn("models", res[1], "ohne Antwort kein erfundener Zustand")
        self.assertIn("tasks", res[2])

    @unittest.skipUnless(NODE, "node fehlt")
    def test_gemerkter_zustand_kaputt_oder_fremd_ist_die_vorgabe(self):
        res = node(laden() + "process.stdout.write(JSON.stringify([U.lesen('{\"v\":1,\"offen\":[\"system\"]}'), U.lesen('kaputt'), U.lesen(null), U.lesen('{\"offen\":[1]}'), U.VORGABE]));")
        self.assertEqual(res[0], ["system"])
        for kaputt in res[1:4]:
            self.assertEqual(kaputt, res[4])

    def test_ort_menue_und_werkzeug(self):
        orte = {o["id"]: o for o in json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"]}
        self.assertEqual(orte["uebersicht"]["object"], {"type": "uebersicht", "id": "app", "title": "Übersicht"})
        for wort in ("übersicht", "baum"):
            self.assertIn(wort, orte["uebersicht"]["words"])
        gruppen = json.loads((UIX / "shells" / "harness" / "start_gruppen.json").read_text(encoding="utf-8"))
        self.assertEqual(gruppen["zuordnung"]["uebersicht"], "arbeit")
        yml = yaml.safe_load((UIX / "tools" / "uebersicht" / "tool.yaml").read_text(encoding="utf-8"))
        man, fehler = check_tool(yml, UIX / "tools" / "uebersicht", "package")
        self.assertEqual(fehler, [])
        self.assertEqual(man["handles"], ["uebersicht"])
        self.assertEqual(man["api"], [], "der Platzhalter ruft keine Route")
        self.assertIn("uebersicht.js", (UIX / "shells" / "harness" / "shell.yaml").read_text(encoding="utf-8"))

    def test_kein_hex_kein_innerhtml_dateigroesse(self):
        js = HARNESS_JS.read_text(encoding="utf-8")
        css = (UIX / "shells" / "harness" / "uebersicht.css").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r":\s*#[0-9a-fA-F]{3,8}", css), [])
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("setInterval", js)
        self.assertNotIn("mountTool", js, "die Übersicht zeichnet nie selbst ein Werkstück")
        self.assertLessEqual(len(js.splitlines()), 400)
        self.assertLessEqual(len((UIX / "shells" / "harness" / "app.js").read_text(encoding="utf-8").splitlines()), 400)

    def test_alte_shell_cockpit_ist_unberuehrt_im_manifest(self):
        text = (UIX / "shells" / "cockpit" / "shell.yaml").read_text(encoding="utf-8")
        self.assertIn("id: cockpit", text)
        self.assertNotIn("uebersicht.js", text)


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
                page.evaluate(f"()=>{{ const S = {S}; return {H}.startmenue.laden(S).then(()=>{H}.app.oeffnen(S, {{object: {{type: 'uebersicht', id: 'app', title: 'Übersicht'}}, label: 'Übersicht'}})); }}")
                page.wait_for_selector(".hs-ue-baum .hs-ue-zeile.kopf", timeout=WARTE_MS)
                kopf = page.locator(".hs-ue-zeile.kopf")
                self.assertGreaterEqual(kopf.count(), 2, "mindestens zwei Gruppen")
                # UE-20: die Vorgabe öffnet Arbeit; ein Klick klappt zu und merkt nur den Namen
                self.assertEqual(page.locator('.hs-ue-zeile.kopf[data-gruppe="arbeit"]').get_attribute("aria-expanded"), "true")
                page.click('.hs-ue-zeile.kopf[data-gruppe="arbeit"]')
                self.assertEqual(page.locator('.hs-ue-zeile.kopf[data-gruppe="arbeit"]').get_attribute("aria-expanded"), "false")
                self.assertEqual(page.locator('.hs-ue-zeile[data-gruppe="arbeit"]:not(.kopf)').count(), 0)
                gemerkt = json.loads(page.evaluate("()=>localStorage.getItem('sedra.harness.uebersicht.baum')"))
                self.assertNotIn("arbeit", gemerkt["offen"])
                # Tastatur: → öffnet wieder
                page.focus('.hs-ue-zeile.kopf[data-gruppe="arbeit"]')
                page.keyboard.press("ArrowRight")
                self.assertEqual(page.locator('.hs-ue-zeile.kopf[data-gruppe="arbeit"]').get_attribute("aria-expanded"), "true")
                # UE-10: eine Zeile öffnet die App in einem eigenen Reiter
                vorher = page.evaluate(f"()=>{H}.reiter.liste ? {H}.reiter.liste({S}).length : -1")
                page.click('.hs-ue-zeile[data-key="a:tasks"]')
                page.wait_for_function("()=>document.querySelectorAll('.hs-app-kopf').length >= 1", timeout=WARTE_MS)
                self.assertTrue(page.evaluate(f"()=>{S}._start.liste.apps.some(a=>a.id === 'uebersicht')"), "UE-30: die App steht im Start-Menü")
                self.assertIsNotNone(vorher)
                # Schließen hängt den Baum aus
                page.evaluate(f"()=>{H}.reiter.schliessen({S}, 'app:uebersicht:app')")
                self.assertEqual(page.locator(".hs-ue-baum").count(), 0)
                self.assertEqual(fehler, [])
                b.close()
        finally:
            stop()


if __name__ == "__main__":
    unittest.main()
