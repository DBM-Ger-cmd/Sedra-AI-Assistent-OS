"""F3-01, zweite lesende Stufe: die Ansichten Typen, Läufe und Factory Health auf den Lese-Routen /api/uix/factory/* (Server: factory_lesen.py).
Rein (node, Attrappe der Oberfläche) und im Browser mit Daten und ohne Daten. Grenzen F301: nur lesen; das Manifest nennt genau die gerufenen Routen."""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"
HARNESS = UIX / "shells" / "harness"
NODE = shutil.which("node")
ROUTEN = ("typen", "runs", "benchmarks", "health")
KOPF = """
function el(tag, klasse, text){
  const e = {tag, kinder: [], textContent: text || '', dataset: {}, _k: klasse || '',
    append(...c){ e.kinder.push(...c); }, replaceChildren(...c){ e.kinder = c; }};
  return e;
}
globalThis.sedraDom = {el};
globalThis.sedraHarness = {};
for (const n of ['factory_typen.js', 'factory_laeufe.js', 'factory_health.js']) require(%s + '/' + n);
const H = globalThis.sedraHarness;
const alle = n=>[n].concat(...(n.kinder || []).map(alle));
const text = n=>alle(n).filter(x=>!(x.kinder && x.kinder.length)).map(x=>x.textContent).join('');
const stub = antworten=>({aufrufe: [], async api(p, o){ this.aufrufe.push({p, m: (o && o.method) || 'GET'}); const a = antworten[p]; if(a instanceof Error) throw a; return a; }});
"""


def node(code):
    run = subprocess.run([NODE, "-e", KOPF % json.dumps(str(HARNESS)) + "(async()=>{" + code + "})().catch(e=>{ console.error(e); process.exit(1); });"],
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert run.returncode == 0, run.stderr[:500]
    return json.loads(run.stdout)


@unittest.skipUnless(NODE, "node fehlt")
class Rein(unittest.TestCase):
    def test_typen_zeigt_die_liste_und_ehrliche_saetze(self):
        out = node("""
const ok = stub({'/api/uix/factory/typen': {quelle: 'ok', anzahl: 1, typen: [{typ_id: 'webshop', name: 'Webshop', zustand: 'ready', funktionen: ['katalog'], gate_freigabe: true}]}});
const f1 = H.factory_typen.flaeche(ok); await f1.zeichnen();
const leer = stub({'/api/uix/factory/typen': {quelle: 'ok', anzahl: 0, typen: []}});
const f2 = H.factory_typen.flaeche(leer); await f2.zeichnen();
const fehlt = stub({'/api/uix/factory/typen': {quelle: 'fehlt', grund: 'keine Registry-Datei'}});
const f3 = H.factory_typen.flaeche(fehlt); await f3.zeichnen();
const kaputt = stub({'/api/uix/factory/typen': new Error('503')});
const f4 = H.factory_typen.flaeche(kaputt); await f4.zeichnen();
console.log(JSON.stringify([text(f1.koerper), text(f2.koerper), text(f3.koerper), text(f4.koerper)]));
""")
        self.assertIn("webshop · Webshop", out[0])
        self.assertIn("Gate: freigegeben", out[0])
        self.assertIn("Funktionen: katalog", out[0])
        self.assertEqual(out[1], "Keine Factory-Typen registriert.")
        self.assertEqual(out[2], "Quelle fehlt: keine Registry-Datei")
        self.assertEqual(out[3], "Quelle nicht erreichbar: 503")

    def test_laeufe_und_benchmarks(self):
        out = node("""
const s = stub({'/api/uix/factory/runs': {quelle: 'ok', anzahl: 2, runs: [
    {run_id: 'r1', typ_id: 'webshop', name: 'Lauf A', build_type: 'project', gestartet: '2026-11-14T08:30:26+00:00', dauer_ms: 1500, erfolg: true, artefakte: 3, fehler: null},
    {run_id: 'r2', typ_id: '3d', name: 'Lauf B', build_type: 'module', gestartet: '2026-11-14T09:00:00+00:00', dauer_ms: 20, erfolg: false, artefakte: 0, fehler: 'kaputt'}]},
  '/api/uix/factory/benchmarks': {quelle: 'ok', anzahl: 0, benchmarks: []}});
const f = H.factory_laeufe.flaeche(s); await f.zeichnen();
const zeilen = alle(f.koerper).filter(x=>x.dataset && x.dataset.run);
console.log(JSON.stringify({text: text(f.koerper), klassen: zeilen.map(x=>x._k)}));
""")
        self.assertIn("Lauf A · webshop · project", out["text"])
        self.assertIn("erfolgreich · 2026-11-14 08:30 · 1.5 s · 3 Artefakte", out["text"])
        self.assertIn("fehlgeschlagen", out["text"])
        self.assertIn("Fehler: kaputt", out["text"])
        self.assertIn("Noch keine Benchmarks gespeichert.", out["text"])
        self.assertEqual([("bad" in k, "ok" in k) for k in out["klassen"]], [(False, True), (True, False)])

    def test_laeufe_je_quelle_getrennt_ehrlich(self):
        out = node("""
const s = stub({'/api/uix/factory/runs': {quelle: 'fehlt', grund: 'kein Evidence Store'}, '/api/uix/factory/benchmarks': new Error('weg')});
const f = H.factory_laeufe.flaeche(s); await f.zeichnen();
console.log(JSON.stringify(text(f.koerper)));
""")
        self.assertIn("Quelle fehlt: kein Evidence Store", out)
        self.assertIn("Quelle nicht erreichbar: weg", out)

    def test_health(self):
        out = node("""
const s = stub({'/api/uix/factory/health': {ok: true, registry: {erreichbar: true, typen: 3, zustaende: {ready: 1, registered: 2}, gate_freigegeben: 3},
  evidence: {erreichbar: true, runs: 111, benchmarks: 0, gate_evidence: 0, meta_insights: 0, letzter_lauf: '2026-11-14T08:30:26+00:00'}}});
const f = H.factory_health.flaeche(s); await f.zeichnen();
const s2 = stub({'/api/uix/factory/health': {ok: false, registry: {erreichbar: false, grund: 'keine Registry-Datei'}, evidence: {erreichbar: false, grund: 'kein Evidence Store'}}});
const g = H.factory_health.flaeche(s2); await g.zeichnen();
console.log(JSON.stringify([text(f.koerper), text(g.koerper)]));
""")
        self.assertIn("Registry · 3 Typen (ready 1, registered 2) · Gate freigegeben: 3", out[0])
        self.assertIn("111 Läufe", out[0])
        self.assertIn("letzter Lauf 2026-11-14 08:30", out[0])
        self.assertIn("keine Registry-Datei", out[1])
        self.assertIn("kein Evidence Store", out[1])

    def test_gegenprobe_nur_lesen_nur_get(self):
        for name in ("factory_typen.js", "factory_laeufe.js", "factory_health.js", "factory_studio.js"):
            js = (HARNESS / name).read_text(encoding="utf-8")
            self.assertNotRegex(js, r"method\s*:\s*['\"](POST|PATCH|DELETE|PUT)", name)
            self.assertNotIn("innerHTML", js, name)
            self.assertNotIn("setInterval", js, name)
            self.assertLessEqual(len(js.splitlines()), 400, name)

    def test_manifest_nennt_genau_die_gerufenen_routen(self):
        man = yaml.safe_load((HARNESS / "shell.yaml").read_text(encoding="utf-8"))["shell"]
        genannt = {a.split("#")[0].strip() for a in man["api"] if "/api/uix/factory/" in a}
        self.assertEqual(genannt, {"GET /api/uix/factory/" + r for r in ROUTEN})
        gerufen = set()
        for name in ("factory_typen.js", "factory_laeufe.js", "factory_health.js"):
            gerufen |= set(re.findall(r"/api/uix/factory/([a-z]+)'", (HARNESS / name).read_text(encoding="utf-8")))
        self.assertEqual(gerufen, set(ROUTEN))
        for name in ("factory_typen.js", "factory_laeufe.js", "factory_health.js"):
            self.assertIn(name, man["entry"]["js"])


class Browser(unittest.TestCase):
    def _oeffnen(self, prepare):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise unittest.SkipTest("playwright fehlt")
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell="harness", prepare=prepare)
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                page = b.new_page(viewport={"width": 1400, "height": 860})
                fehler = []
                page.on("pageerror", lambda e: fehler.append(str(e)))
                page.goto(url)
                wait_until_started(page, shell="harness")
                page.evaluate("()=>{ const S = window.sedra.shells.get('harness'); return window.sedraHarness.app.oeffnen(S, {object: {type: 'factory-studio', id: 'app', title: 'Factory Studio'}, label: 'Factory Studio'}); }")
                page.wait_for_selector(".hs-fs-pane", timeout=20000)
                texte = {}
                for modus in ("statusdashboard", "typen", "laeufe"):
                    page.click(f'.hs-app-reiter-knopf[data-modus="{modus}"]')
                    page.wait_for_selector(f'.hs-fs-pane[data-modus="{modus}"]', state="visible", timeout=20000)
                    page.wait_for_timeout(1200)
                    texte[modus] = page.inner_text(f'.hs-fs-pane[data-modus="{modus}"]')
                b.close()
                return texte, fehler
        finally:
            stop()

    def test_mit_daten(self):
        from sedra_runtime.evidence_store import EvidenceStore
        from sedra_runtime.factory_registry import FactoryRegistry

        def prepare(hub):
            cfg = Path(hub.project_root) / "local_config"
            reg = FactoryRegistry()
            reg.registriere_typ("webshop", "Webshop", ["katalog"], gate_freigabe=True)
            reg.save(cfg / "factory_registry.json")
            st = EvidenceStore(cfg / "evidence" / "evidence.db")
            r = st.record_run_start("webshop", "Lauf A", "project")
            st.record_run_end(r.run_id, True, metrics={"n": 1})
        texte, fehler = self._oeffnen(prepare)
        self.assertEqual(fehler, [])
        self.assertIn("Registry", texte["statusdashboard"])
        self.assertIn("1 Typen", texte["statusdashboard"])
        self.assertIn("Evidence Store", texte["statusdashboard"])
        self.assertIn("webshop", texte["typen"])
        self.assertIn("Webshop", texte["typen"])
        self.assertIn("Lauf A", texte["laeufe"])

    def test_ohne_daten_ehrliche_saetze(self):
        texte, fehler = self._oeffnen(None)
        self.assertEqual(fehler, [])
        self.assertIn("Quelle fehlt", texte["typen"])
        self.assertIn("Quelle fehlt", texte["laeufe"])
        self.assertIn("keine Registry-Datei", texte["statusdashboard"])
        self.assertIn("kein Evidence Store", texte["statusdashboard"])


if __name__ == "__main__":
    unittest.main()
