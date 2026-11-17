"""Hardening-Runde Start-Menü und Taskleiste (17.11.2026). Jeder Test hält einen Fehler fest, der vor der Runde auftrat:
1. Ein Klick im Menü, der das Menü neu zeichnet (Gruppe auf-/zuklappen), schloss das Menü, weil die Klick-außerhalb-Prüfung den schon entfernten Knoten sah.
2. Pfeil links/rechts im Suchfeld bewegte die Auswahl statt der Schreibmarke: ein Suchbegriff ließ sich nicht bearbeiten.
3. Vor dem Laden der Liste zeigte das offene Menü nichts, auch keinen Fehler.
4. Warf das Öffnen einer App, blieb der Fehler unbemerkt (kein Hinweis).
5. Ein Token-Stand ohne Zahlen ließ die ganze Statuszeile auf „nicht lesbar“ fallen.
6. Ein Lauf mit kaputter Startzeit zeigte „NaN min“, ein Lauf ohne Namen „undefined“.
"""
import json
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
    def test_lauf_name_ohne_nan_und_ohne_undefined(self):
        res = node("globalThis.sedraDom = {}; require(%s); const T = globalThis.sedraHarness.taskleiste;"
                   "process.stdout.write(JSON.stringify([T.laufName({status:'laeuft', name:'Bau', gestartet:'kaputt'}),"
                   "T.laufName({status:'laeuft', name:'Bau', fortschritt:{prozent:40}}), T.laufName({status:'ok'}), T.laufName({status:'rätsel', name:'X'}),"
                   "T.laufName({status:'laeuft'}), T.laufName({})]));" % json.dumps(str(UIX / "shells" / "harness" / "taskleiste.js")))
        for text in res:
            self.assertNotIn("NaN", text)
            self.assertNotIn("undefined", text)
        self.assertIn("40 %", res[1])
        self.assertTrue(res[0].startswith("Bau"))


class Browser(unittest.TestCase):
    def setUp(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise unittest.SkipTest("playwright fehlt")
        from uix_check import start_server, wait_until_started
        self.url, self.stop = start_server(lambda *a: None, shell="harness")
        self.addCleanup(self.stop)
        self.pw = sync_playwright().start()
        self.addCleanup(self.pw.stop)
        self.browser = self.pw.chromium.launch()
        self.addCleanup(self.browser.close)
        self.page = self.browser.new_page(viewport={"width": 1400, "height": 900})
        self.fehler = []
        self.page.on("pageerror", lambda e: self.fehler.append(str(e)))
        self.page.goto(self.url)
        wait_until_started(self.page, shell="harness")
        self.page.wait_for_function("()=>window.sedraHarness && window.sedraHarness.startmenue && window.sedra.shells.get('harness')._start && window.sedra.shells.get('harness')._start.liste", timeout=WARTE_MS)

    S = "window.sedra.shells.get('harness')"
    H = "window.sedraHarness"

    def oeffne_menue(self):
        self.page.evaluate(f"()=>{self.H}.startmenue.oeffnen({self.S})")
        self.page.wait_for_selector(".hs-start-menue:not([hidden])", timeout=WARTE_MS)

    def test_klick_der_das_menue_neu_zeichnet_schliesst_es_nicht(self):
        self.oeffne_menue()
        kopf = self.page.locator(".hs-start-kachel-kopf").first
        kopf.scroll_into_view_if_needed()
        offen_vorher = kopf.get_attribute("aria-expanded")
        kopf.click()
        self.page.wait_for_timeout(300)
        self.assertFalse(self.page.evaluate("()=>document.querySelector('.hs-start-menue').hidden"), "das Menü blieb offen")
        self.assertNotEqual(self.page.locator(".hs-start-kachel-kopf").first.get_attribute("aria-expanded"), offen_vorher, "die Gruppe hat umgeschaltet")
        self.page.mouse.click(1380, 300)
        self.page.wait_for_timeout(200)
        self.assertTrue(self.page.evaluate("()=>document.querySelector('.hs-start-menue').hidden"), "ein Klick außerhalb schließt weiterhin")
        self.assertEqual(self.fehler, [])

    def test_pfeile_im_suchfeld_bewegen_die_schreibmarke(self):
        self.oeffne_menue()
        self.page.fill(".hs-start-suche", "abc")
        self.page.focus(".hs-start-suche")
        self.page.keyboard.press("End")
        self.page.keyboard.press("ArrowLeft")
        self.assertEqual(self.page.evaluate("()=>document.querySelector('.hs-start-suche').selectionStart"), 2)
        self.page.fill(".hs-start-suche", "")
        self.page.keyboard.press("ArrowRight")                       # leeres Feld: die Pfeile wählen weiter eine App
        self.assertEqual(self.page.evaluate(f"()=>{self.S}._start.wahl"), 1)

    def test_menue_vor_dem_laden_sagt_es(self):
        self.page.evaluate(f"()=>{{ const st = {self.S}._start; st.liste = null; {self.H}.startmenue.oeffnen({self.S}); }}")
        self.page.wait_for_selector(".hs-start-menue:not([hidden])", timeout=WARTE_MS)
        text = self.page.locator(".hs-start-inhalt").inner_text().strip()
        self.assertNotEqual(text, "", "kein leeres Menü ohne Wort")

    def test_fehler_beim_oeffnen_einer_app_wird_gemeldet(self):
        self.page.evaluate(f"""()=>{{
            const S = {self.S}; window.__hinweise = []; const alt = S.hinweis; S.hinweis = (t, ton)=>{{ window.__hinweise.push(String(t)); }};
            {self.H}.app.oeffnen = ()=>{{ throw new Error('kaputt'); }};
            {self.H}.startmenue.oeffnen(S); {self.H}.startmenue.waehlen(S, {{id: 'x', label: 'Test-App'}});
        }}""")
        self.page.wait_for_timeout(200)
        hinweise = self.page.evaluate("()=>window.__hinweise")
        self.assertTrue(any("Test-App" in h for h in hinweise), hinweise)
        self.assertEqual(self.fehler, [], "kein ungefangener Fehler")

    def test_token_stand_ohne_zahlen_laesst_die_statuszeile_stehen(self):
        self.page.evaluate(f"()=>{{ const S = {self.S}; S.tokenStand = {{sitzung: {{}}, heute: {{antworten: 2}}}}; S._leiste.zuletzt = 0; {self.H}.taskleiste.status(S); }}")
        # erst wenn die Leiste mit dem neuen Stand gezeichnet ist: der Tooltip der Token-Zelle nennt „eingehend“
        self.page.wait_for_function(f"()=>{{ const z = {self.S}._leiste.status.querySelector('[data-zelle=\"token\"]'); return !!z && z.title.includes('eingehend'); }}", timeout=WARTE_MS)
        self.assertEqual(self.page.evaluate(f"()=>{self.S}._leiste.status.textContent.includes('nicht lesbar')"), False, "keine Fehlerzeile statt der Statuszeile")
        self.assertEqual(self.page.locator('.hs-status [data-zelle="token"]').count(), 1)
        self.assertEqual(self.fehler, [])


if __name__ == "__main__":
    unittest.main()
