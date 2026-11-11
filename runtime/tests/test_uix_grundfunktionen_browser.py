"""AM2-16: die Browserprüfung der Grundfunktionen je Shell. Was eine Shell in `shell.yaml` unter `grundfunktionen:` erklärt, muss im Browser erreichbar sein:
  ort      → das Objekt des Ortes über die Shell-API öffnen ergibt eine gezeichnete Fläche des Werkzeugs der Grundfunktion;
  slot:x   → das Element mit `data-slot="x"` ist da (das Gespräch zählt auch mit `data-tool="talk"`);
  eigen    → die Shell meldet ein Element mit `data-grundfunktion="<name>"`.
Geprüft werden die Shells, die alle sieben erklären: harness, cockpit, paperclip, minimal, fisch."""
import json
import sys
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"
ORTE = {o["id"]: o for o in json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"]}
ORT = {"entscheidungen": "decisions", "aufgaben": "tasks", "logbuch": "logbook", "modus_grenzen": "boundary", "module_berechtigungen": "modules", "einstellungen_zustand": "machine"}
WERKZEUG = {"entscheidungen": "decisions", "aufgaben": "task", "logbuch": "logbook", "modus_grenzen": "boundaries", "module_berechtigungen": "modules", "einstellungen_zustand": "system"}
SHELLS = ("harness", "cockpit", "paperclip", "minimal", "fisch")
WARTE_MS = 20000


class Grundfunktionen(unittest.TestCase):
    def pruefe(self, shell):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise unittest.SkipTest("playwright fehlt")
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell=shell)
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                page = b.new_page(viewport={"width": 1400, "height": 860})
                page.goto(url)
                wait_until_started(page, shell=shell)
                erklaert = page.evaluate("()=>window.sedraBoot.ctx.manifest.shell.grundfunktionen") or {}
                self.assertEqual(sorted(erklaert), sorted(list(ORT) + ["gespraech"]), shell + ": alle sieben erklärt")
                fehlt = []
                for name, art in sorted(erklaert.items()):
                    if art == "eigen":
                        warte = "(n)=>!!document.querySelector('[data-grundfunktion=\"' + n + '\"]')"
                        try:
                            page.wait_for_function(warte, arg=name, timeout=WARTE_MS)
                        except Exception:
                            fehlt.append(f"{name}: eigen, aber kein data-grundfunktion")
                    elif art == "ort":
                        objekt = ORTE[ORT[name]]["object"]
                        page.evaluate("(o)=>window.sedra.shells.get(%s).shellApi.open(o)" % json.dumps(shell), objekt)
                        try:
                            page.wait_for_function("(t)=>{ const e = document.querySelector('[data-tool=\"' + t + '\"]'); return !!e && e.textContent.trim().length > 20; }",
                                                   arg=WERKZEUG[name], timeout=WARTE_MS)
                        except Exception:
                            fehlt.append(f"{name}: ort, aber keine gezeichnete Fläche von {WERKZEUG[name]}")
                    elif art.startswith("slot:"):
                        slot = art[5:]
                        ok = page.evaluate("(s)=>!!document.querySelector('[data-slot=\"' + s + '\"]') || (s === 'talk' && !!document.querySelector('[data-tool=\"talk\"]'))", slot)
                        if not ok:
                            fehlt.append(f"{name}: {art}, aber kein Element")
                self.assertEqual(fehlt, [], shell)
                b.close()
        finally:
            stop()

    def test_harness(self):
        self.pruefe("harness")

    def test_cockpit(self):
        self.pruefe("cockpit")

    def test_paperclip(self):
        self.pruefe("paperclip")

    def test_minimal(self):
        self.pruefe("minimal")

    def test_fisch(self):
        self.pruefe("fisch")


if __name__ == "__main__":
    unittest.main()
