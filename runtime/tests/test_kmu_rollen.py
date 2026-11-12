"""AM7-08 und AM7-09 (SPEC_APPS_v1_AM7_UNTERNEHMEN §3.3): die Rollen-Sicht der KMU-Shell und der Zugang „Verwaltung“.
Reine Funktionen in rollen.js (mit node), die Erklärung in shell.yaml, und im Browser: die Leiste folgt der Rolle, „Verwaltung“ öffnet dieselben Apps des Pakets."""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
SHELL = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix" / "shells" / "gateway-kmu"
NODE = shutil.which("node")

SIEBEN = ["entscheidungen", "gespraech", "aufgaben", "logbuch", "modus_grenzen", "module_berechtigungen", "einstellungen_zustand"]


def betrieb(rolle, aktiv=True, frei=None):
    return {"schalter": True, "richtlinie": {"aktiv": aktiv}, "rolle": rolle, "grundfunktionen": SIEBEN if frei is None else frei}


def rein(*faelle):
    """Wertet rollen.js mit node für jeden Fall (Zustand) aus: [[sichtbar, zugaenge], ...]."""
    skript = "const R=require(%s);const f=JSON.parse(process.argv[1]);process.stdout.write(JSON.stringify(f.map(b=>[R.sichtbar(b),R.zugaenge(b)])));" % json.dumps(str(SHELL / "rollen.js"))
    ausgabe = subprocess.run([NODE, "-e", skript, json.dumps(list(faelle))], capture_output=True, text=True, check=True, encoding="utf-8").stdout
    return json.loads(ausgabe)


@unittest.skipUnless(NODE, "node fehlt")
class Rein(unittest.TestCase):
    def test_sachbearbeitung_sieht_gespraech_entscheidungen_aufgaben(self):
        (sichtbar, zu), = rein(betrieb("sachbearbeitung"))
        self.assertEqual(sichtbar, ["entscheidungen", "gespraech", "aufgaben"], "AM7-08")
        self.assertEqual(zu["verwaltung"], [], "kein Zugang Verwaltung")

    def test_betreiber_und_pruefung_haben_verwaltung_mit_vier_grundfunktionen(self):
        for rolle in ("betreiber", "pruefung"):
            (sichtbar, zu), = rein(betrieb(rolle))
            self.assertEqual(sichtbar, SIEBEN, rolle)
            self.assertEqual(zu["verwaltung"], ["logbuch", "modus_grenzen", "module_berechtigungen", "einstellungen_zustand"], "AM7-09")

    def test_die_richtlinie_darf_nur_einschraenken(self):
        (_, zu), (_, zu2) = rein(betrieb("betreiber", frei=["gespraech", "logbuch"]), betrieb("sachbearbeitung", frei=SIEBEN))
        self.assertEqual(zu["verwaltung"], ["logbuch"])
        self.assertFalse(zu["entscheidungen"] or zu["aufgaben"])
        self.assertEqual(zu2["verwaltung"], [], "die Richtlinie gibt der Sachbearbeitung nichts dazu")

    def test_ohne_aktive_richtlinie_oder_ohne_zustand_wie_bisher_alles(self):
        for fall in (betrieb("sachbearbeitung", aktiv=False), None, {}, {"schalter": False, "rolle": None}):
            (sichtbar, _), = rein(fall)
            self.assertEqual(sichtbar, SIEBEN, str(fall))

    def test_unbekannte_rolle_bekommt_die_kleinste_sicht(self):
        (sichtbar, zu), = rein(betrieb("gast"))
        self.assertEqual(sichtbar, ["entscheidungen", "gespraech", "aufgaben"])
        self.assertEqual(zu["verwaltung"], [])


class Erklaerung(unittest.TestCase):
    def test_shell_yaml_erklaert_alle_sieben_und_die_dateien_stehen_da(self):
        doc = yaml.safe_load((SHELL / "shell.yaml").read_text(encoding="utf-8"))["shell"]
        self.assertEqual(sorted(doc["grundfunktionen"]), sorted(SIEBEN))
        for name in ("logbuch", "modus_grenzen", "module_berechtigungen", "einstellungen_zustand"):
            self.assertEqual(doc["grundfunktionen"][name], "verwaltung")
        self.assertEqual(doc["entry"]["js"], ["rollen.js", "shell.js"], "shell.js zuletzt")
        for datei in doc["entry"]["js"]:
            self.assertTrue((SHELL / datei).is_file(), datei)
        self.assertIn("GET /api/uix/betrieb", doc["api"])

    def test_keine_warnung_mehr_fuer_die_kmu_shell(self):
        from sedra_runtime.desk.gateway import check_shell
        man, fehler = check_shell(yaml.safe_load((SHELL / "shell.yaml").read_text(encoding="utf-8")), SHELL, "package")
        self.assertEqual(fehler, [])
        self.assertEqual(man["grundfunktionen_warnungen"], [])


class Browser(unittest.TestCase):
    def test_leiste_folgt_der_rolle_und_verwaltung_oeffnet_dieselben_apps(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise unittest.SkipTest("playwright fehlt")
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell="gateway-kmu")
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                page = b.new_page(viewport={"width": 1400, "height": 860})
                fehler = []
                page.on("pageerror", lambda e: fehler.append(str(e)))
                page.goto(url)
                wait_until_started(page, shell="gateway-kmu")
                page.wait_for_selector(".sh-gateway-kmu-leiste", timeout=15000)
                zustand = lambda b_: page.evaluate("(b)=>{ const s = window.sedra.shells.get('gateway-kmu'); s.rollenAnwenden(b); "
                                                   "return {knoepfe: [...document.querySelectorAll('.sh-gateway-kmu-leiste button, .sh-gateway-kmu-verwaltung button')].map(x=>x.dataset.grundfunktion || x.dataset.leiste), "
                                                   "talk: !document.querySelector('.sh-gateway-kmu-talk').hidden}; }", b_)
                # Sachbearbeitung: Vorgänge, Entscheidungen, Aufgaben – kein Zugang Verwaltung
                z = zustand(betrieb("sachbearbeitung"))
                self.assertEqual(z["knoepfe"], ["vorgaenge", "entscheidungen", "aufgaben"])
                self.assertTrue(z["talk"])
                # Betreiber: dazu Verwaltung mit vier Knöpfen (zunächst zugeklappt)
                z = zustand(betrieb("betreiber"))
                self.assertEqual(z["knoepfe"], ["vorgaenge", "entscheidungen", "aufgaben", "verwaltung", "logbuch", "modus_grenzen", "module_berechtigungen", "einstellungen_zustand"])
                self.assertTrue(page.locator(".sh-gateway-kmu-verwaltung").is_hidden())
                page.click("[data-leiste=verwaltung]")
                self.assertTrue(page.locator(".sh-gateway-kmu-verwaltung").is_visible())
                # derselbe Weg wie im Paket: das Werkzeug des Ortes wird gezeichnet
                for name, werkzeug in (("logbuch", "logbook"), ("modus_grenzen", "boundaries"), ("module_berechtigungen", "modules"), ("einstellungen_zustand", "system")):
                    page.click(f"[data-grundfunktion={name}]")
                    page.wait_for_function("(t)=>{ const e = document.querySelector('.sh-gateway-kmu-werkstueck [data-tool=\"' + t + '\"]'); return !!e && e.textContent.trim().length > 20; }",
                                           arg=werkzeug, timeout=20000)
                # Gespräch kann die Richtlinie abblenden
                self.assertFalse(zustand(betrieb("betreiber", frei=["logbuch"]))["talk"])
                self.assertEqual(fehler, [], "keine Seitenfehler")
                b.close()
        finally:
            stop()


if __name__ == "__main__":
    unittest.main()
