"""AM3-16 bis AM3-18, AM3-20 (SPEC_APPS_v1_AM3_BERECHTIGUNG): die Brücke filtert, was eine fremde App (COMMUNITY) sieht und sendet; eigene Module des Captains bleiben unverändert.
Die Regeln laufen mit node, ohne Browser. Dazu der reine Kern der Berechtigung (Gewährung, Ladeentscheidung)."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.berechtigung import aktivieren, eintrag_neu, entziehen, gewaehren, ladeentscheidung, werkseinstellung, wirksam

NODE = shutil.which("node")
UI = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix" / "ui"

SKRIPT = """
const fs = require('fs'), vm = require('vm');
const box = {console, setTimeout, Date}; box.globalThis = box; vm.createContext(box);
vm.runInContext(fs.readFileSync(%s, 'utf8'), box);
vm.runInContext(fs.readFileSync(%s, 'utf8'), box);
const posts = [], shellCalls = [], handlers = {};
const bus = {on: (name, fn) => { handlers[name] = fn; return () => {}; }};
const shell = {notify: async (t, ton) => { shellCalls.push(['notify', t, ton]); return null; }, open: async () => null};
const br = box.sedraBruecke.makeBruecke({kern: {forModule: () => async () => ({})}, shell, bus, onProblem: () => {}});
const fenster = {postMessage: m => posts.push(m)};
const manifest = %s;
br.register(fenster, manifest);
(async () => {
  %s
  process.stdout.write(JSON.stringify({posts, shellCalls}));
})();
"""


def lauf(manifest, korpus):
    skript = SKRIPT % (json.dumps(str(UI / "bruecke_filter.js")), json.dumps(str(UI / "bruecke.js")), json.dumps(manifest), korpus)
    out = subprocess.run([NODE, "-e", skript], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def manifest(trust):
    return {"id": "fremd", "name": "Fremde App", "trust": trust, "api": [], "events": {"listens": ["system.state", "decision.pending", "task.changed", "live.line"]}}


@unittest.skipUnless(NODE, "node fehlt")
class Bruecke(unittest.TestCase):
    EREIGNISSE = """
      handlers['system.state']({a: 1, tief: {x: 2}});
      handlers['decision.pending']({id: 'D-1', kind: 'request:install', title: 'GEHEIM', way: 'freigeben'});
      handlers['task.changed']({id: 'T-1', phase: 'EXECUTE', title: 'GEHEIM'});
      handlers['live.line']({text: 'GEHEIM'});
    """

    def test_fremde_app_sieht_nur_gefilterte_ereignisse(self):
        posts = lauf(manifest("COMMUNITY"), self.EREIGNISSE)["posts"]
        self.assertEqual(posts, [{"ereignis": "system.state", "daten": {"a": 1, "tief": {"x": 2}}},
                                 {"ereignis": "decision.pending", "daten": {"id": "D-1", "kind": "request:install", "way": "freigeben"}},
                                 {"ereignis": "task.changed", "daten": {"id": "T-1", "phase": "EXECUTE"}}])
        self.assertNotIn("GEHEIM", json.dumps(posts))

    def test_eigenes_modul_des_captains_bekommt_alles_wie_vorher(self):
        posts = lauf(manifest("CAPTAIN"), self.EREIGNISSE)["posts"]
        self.assertEqual(len(posts), 4)
        self.assertIn("GEHEIM", json.dumps(posts))

    def test_hinweis_einer_fremden_app_ist_gekennzeichnet_und_bereinigt(self):
        ergebnis = lauf(manifest("COMMUNITY"), "br.handle({source: fenster, data: {id: 'n1', op: 'shell', name: 'notify', args: ['Hallo\\u0000 Welt\\n', 'bad']}}); await new Promise(r => setTimeout(r, 30));")
        self.assertEqual(ergebnis["shellCalls"], [["notify", "Fremde App: Hallo Welt", "note"]])

    def test_hinweise_sind_gedrosselt_ein_leerer_faellt_weg(self):
        korpus = ("for (const [i, t] of ['eins', 'zwei', '   '].entries()) br.handle({source: fenster, data: {id: 'n' + i, op: 'shell', name: 'notify', args: [t, 'ok']}});"
                  " await new Promise(r => setTimeout(r, 40));")
        ergebnis = lauf(manifest("COMMUNITY"), korpus)
        self.assertEqual(ergebnis["shellCalls"], [["notify", "Fremde App: eins", "note"]])
        self.assertEqual([p["ok"] for p in ergebnis["posts"] if p.get("antwort")], [True, True, True], "jede Nachricht wird beantwortet, auch die verworfenen")

    def test_hinweis_des_captain_moduls_bleibt_unveraendert(self):
        ergebnis = lauf(manifest("CAPTAIN"), "br.handle({source: fenster, data: {id: 'n1', op: 'shell', name: 'notify', args: ['Gemerkt', 'note']}}); await new Promise(r => setTimeout(r, 30));")
        self.assertEqual(ergebnis["shellCalls"], [["notify", "Gemerkt", "note"]])


class Berechtigung(unittest.TestCase):
    def test_ladeentscheidung_ganze_kette(self):
        e = eintrag_neu("h1", "COMMUNITY", werkseinstellung(["lesen:a", "verb:x.y", "ereignis:system.state"], ["a"]))
        self.assertEqual(e["gewaehrt"], ["ereignis:system.state", "lesen:a"])
        self.assertEqual(ladeentscheidung(e, ["lesen:a", "verb:x.y"], "h1")["grund"], "app_inaktiv")
        e = aktivieren(e, True)
        self.assertEqual(ladeentscheidung(e, ["lesen:a", "verb:x.y"], "h1")["grund"], "rechte_nicht_gewaehrt:verb:x.y")
        e = gewaehren(e, ["verb:x.y"])
        self.assertEqual(ladeentscheidung(e, ["lesen:a", "verb:x.y"], "h1"), {"laden": True, "grund": None, "wirksam": ["lesen:a", "verb:x.y"]})
        self.assertEqual(ladeentscheidung(e, ["lesen:a", "verb:x.y"], "h2")["grund"], "gewaehrung_veraltet")
        e = entziehen(e, ["verb:x.y"])
        self.assertEqual(ladeentscheidung(e, ["lesen:a", "verb:x.y"], "h1")["laden"], False)

    def test_wirksam_ist_der_schnitt(self):
        self.assertEqual(wirksam(["a", "b"], ["b", "c"], ["b"]), ["b"])

    def test_werkseinstellung_nur_stufe_a(self):
        self.assertEqual(werkseinstellung(["lesen:a", "lesen:b", "verb:x.y", "zelle:text", "ablage:2048", "ablage:9999999", "ereignis:task.changed"], ["a"]), ["ablage:2048", "lesen:a"])


if __name__ == "__main__":
    unittest.main()
