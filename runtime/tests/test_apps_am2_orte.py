"""AM2-01 bis AM2-06 (SPEC_APPS_v1_AM2_ORTE_UND_GRUNDFUNKTIONEN): die Kernorte aus einer Quelle, das Feld `ort` im Manifest, Kollisionen, Orte je Shell, `open_place`, Browser-Seite."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import orte
from sedra_runtime.desk.gateway import Gateway

NODE = shutil.which("node")
UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"

MANIFEST = '''tool:
  id: {id}
  name: "App {id}"
  version: 1.0.0
  kind: object
  handles: [{typ}]
  entry: {{js: tool.js}}
  trust: CAPTAIN
  needs: {{ui: ">=1.0 <2"}}
{shells}  ort:
    id: {ortid}
    label: "Mein Ort"
    hint: "ein Satz"
    words: {words}
    object: {{type: {typ}, id: alle, title: "Mein Ort"}}
{symbol}'''


def ort_ok(**felder):
    ort = {"id": "mein-ort", "label": "Mein Ort", "hint": "ein Satz", "words": ["zauberwort"], "object": {"type": "rechnung", "id": "alle"}}
    ort.update(felder)
    return ort


class Pruefung(unittest.TestCase):
    def test_ohne_ort_nichts_zu_pruefen(self):
        self.assertEqual(orte.pruefe_ort(None, [], "x"), [])

    def test_gueltiger_ort(self):
        self.assertEqual(orte.pruefe_ort(ort_ok(symbol="★"), ["rechnung"], "x"), [])

    def test_id_belegt_durch_einen_kernort(self):
        self.assertIn("ort_id_belegt", orte.pruefe_ort(ort_ok(id="logbook"), ["rechnung"], "x"))

    def test_reservierte_woerter_kernort_und_satzmuster(self):
        fehler = orte.pruefe_ort(ort_ok(words=["logbuch", "erstelle", "was", "öffne", "frei"]), ["rechnung"], "x")
        self.assertEqual(sorted(f for f in fehler if f.startswith("ort_wort_reserviert")),
                         ["ort_wort_reserviert:erstelle", "ort_wort_reserviert:logbuch", "ort_wort_reserviert:was", "ort_wort_reserviert:öffne"])

    def test_grenzen(self):
        self.assertIn("ort_label_ungueltig", orte.pruefe_ort(ort_ok(label="x" * 41), ["rechnung"], "x"))
        self.assertIn("ort_hint_ungueltig", orte.pruefe_ort(ort_ok(hint="x" * 81), ["rechnung"], "x"))
        self.assertIn("ort_words_ungueltig", orte.pruefe_ort(ort_ok(words=[]), ["rechnung"], "x"))
        self.assertIn("ort_words_ungueltig", orte.pruefe_ort(ort_ok(words=["w%d" % i + "x" for i in range(13)]), ["rechnung"], "x"))
        self.assertIn("ort_words_ungueltig", orte.pruefe_ort(ort_ok(words=["a"]), ["rechnung"], "x"))
        self.assertIn("ort_words_ungueltig", orte.pruefe_ort(ort_ok(words=["Gross"]), ["rechnung"], "x"))
        self.assertIn("ort_id_ungueltig", orte.pruefe_ort(ort_ok(id="../x"), ["rechnung"], "x"))
        self.assertIn("ort_symbol_ungueltig", orte.pruefe_ort(ort_ok(symbol="<script>"), ["rechnung"], "x"))
        self.assertIn("ort_unbekanntes_feld:url", orte.pruefe_ort(ort_ok(url="http://x"), ["rechnung"], "x"))
        self.assertEqual(orte.pruefe_ort("kein dict", [], "x"), ["ort_ungueltig"])

    def test_objekttyp_muss_in_handles_stehen(self):
        self.assertIn("ort_object_nicht_in_handles", orte.pruefe_ort(ort_ok(), ["anderes"], "x"))
        self.assertIn("ort_object_ungueltig", orte.pruefe_ort(ort_ok(object={"type": "rechnung"}), ["rechnung"], "x"))
        self.assertIn("ort_object_ungueltig", orte.pruefe_ort(ort_ok(object={"type": "rechnung", "id": "a", "script": "x"}), ["rechnung"], "x"))

    def test_zusammensetzen_doppeltes_wort_gilt_fuer_keine(self):
        a = ort_ok(id="ort-a", words=["gemeinsam", "eigenes-a"])
        b = ort_ok(id="ort-b", words=["gemeinsam", "eigenes-b"])
        liste, warnungen = orte.zusammensetzen([("a", a), ("b", b)])
        extra = {o["id"]: o for o in liste if o.get("app")}
        self.assertEqual(extra["ort-a"]["words"], ["eigenes-a"])
        self.assertEqual(extra["ort-b"]["words"], ["eigenes-b"])
        self.assertEqual(warnungen, ["ort_wort_doppelt:gemeinsam"])

    def test_kernorte_zuerst_und_vollstaendig(self):
        liste, _ = orte.zusammensetzen([("a", ort_ok())])
        self.assertEqual([o["id"] for o in liste[:-1]], [o["id"] for o in orte.kern()])
        self.assertEqual(liste[-1]["id"], "mein-ort")


class Quelle(unittest.TestCase):
    @unittest.skipUnless(NODE, "node fehlt")
    def test_kopie_in_places_js_gleich_json(self):
        skript = "const P = require(%s); process.stdout.write(JSON.stringify({orte: P.PLACES, woerter: {order: P.ORDER_WORDS, question: P.QUESTION_WORDS, open: P.OPEN_WORDS}}));"
        out = subprocess.run([NODE, "-e", skript % json.dumps(str(UIX / "ui" / "places.js"))], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8")),
                         "ui/places.js (Kopie) und ui/orte_kern.json (Quelle) müssen gleich sein – nach einer Änderung orte_kern.json neu erzeugen")

    def test_chat_tools_liest_die_quelle(self):
        from sedra_runtime.chat_tools import PLACES
        self.assertEqual(PLACES, {o["id"]: (o["label"], o["hint"]) for o in orte.kern()})


class Gateway_(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am2-orte-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gw = Gateway(self.root)

    def app(self, id, ortid="mein-ort", words="[zauberwort]", typ="rechnung", shells="", symbol=""):
        ordner = self.root / "local_config" / "tools" / id
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "tool.js").write_text("// x\n", encoding="utf-8")
        (ordner / "tool.yaml").write_text(MANIFEST.format(id=id, ortid=ortid, words=words, typ=typ, shells=shells, symbol=symbol), encoding="utf-8")

    def ids(self, shell=None):
        return [o["id"] for o in self.gw.orte(shell)[0]]

    def test_ort_einer_app_steht_in_manifest_orte(self):
        self.app("rechnungen")
        liste = self.gw.manifest()["orte"]
        self.assertEqual(liste[-1]["id"], "mein-ort")
        self.assertEqual(liste[-1]["app"], "rechnungen")
        self.assertEqual(len(liste), len(orte.kern()) + 1)

    def test_shells_bestimmt_wo_der_ort_steht(self):
        self.app("rechnungen", shells="  shells: [cockpit]\n")
        self.assertIn("mein-ort", self.ids("cockpit"))
        self.assertNotIn("mein-ort", self.ids("harness"))

    def test_ort_id_eines_kernorts_weist_die_app_ab(self):
        self.app("rechnungen", ortid="logbook")
        self.assertNotIn("rechnungen", self.gw.tools())
        self.assertEqual({r["id"]: r["reasons"] for r in self.gw.manifest()["rejected"]}["rechnungen"], ["ort_id_belegt"])

    def test_dieselbe_ort_id_bei_zwei_apps_weist_beide_ab(self):
        self.app("app-eins")
        self.app("app-zwei", words="[anderes]")
        gruende = {r["id"]: r["reasons"] for r in self.gw.manifest()["rejected"]}
        self.assertEqual((gruende["app-eins"], gruende["app-zwei"]), (["ort_id_belegt"], ["ort_id_belegt"]))
        self.assertNotIn("mein-ort", self.ids("harness"))

    def test_gleiches_wort_bei_zwei_apps_beide_geladen_wort_gilt_fuer_keine(self):
        self.app("app-eins", ortid="ort-eins", words="[gemeinsam, nurmeins]")
        self.app("app-zwei", ortid="ort-zwei", words="[gemeinsam, nurmzwei]", typ="angebot")
        m = self.gw.manifest()
        extra = {o["id"]: o["words"] for o in m["orte"] if o.get("app")}
        self.assertEqual(extra, {"ort-eins": ["nurmeins"], "ort-zwei": ["nurmzwei"]})
        self.assertIn({"id": "orte", "grund": "ort_wort_doppelt:gemeinsam"}, m["warnungen"])

    def test_reserviertes_wort_weist_die_app_ab(self):
        self.app("rechnungen", words="[logbuch]")
        self.assertEqual({r["id"]: r["reasons"] for r in self.gw.manifest()["rejected"]}["rechnungen"], ["ort_wort_reserviert:logbuch"])

    def test_chat_open_place_kennt_app_orte(self):
        from sedra_runtime.chat_tools import ChatTools

        class Hub:
            gateway = self.gw
        self.app("rechnungen")
        box = ChatTools(Hub())
        self.assertEqual(json.loads(box.call("open_place", {"place": "mein-ort"}))["status"], "offered")
        self.assertIn("mein-ort", [o["id"] for o in json.loads(box.call("list_places", {}))])
        fehler = box.call("open_place", {"place": "keller"})
        self.assertTrue(fehler.startswith("error: unknown_place"))


class Browser(unittest.TestCase):
    @unittest.skipUnless(NODE, "node fehlt")
    def test_setzen_ersetzt_an_ort_und_stelle_und_oeffne_findet_den_app_ort(self):
        skript = ("const P = require(%s), S = require(%s); const ref = P.PLACES; const vorher = ref.length;"
                  "const ok = P.setzen([{id:'mein-ort', label:'Mein Ort', hint:'x', words:['zauberwort'], object:{type:'rechnung', id:'alle'}, symbol:'★', app:'rechnungen'}, "
                  "{id:'tasks', label:'Aufgaben', hint:'', words:['aufgabe'], object:{type:'task', id:'alle'}}]);"
                  "const bad = P.setzen([{id: 5}]); const leer = P.setzen([]);"
                  "const r1 = P.routeText('öffne zauberwort', ref), r2 = P.routeText('zauberwort', ref), r3 = P.routeText('logbuch', ref);"
                  "const liste = S.bauen(ref, [], o=>o.type === 'rechnung' ? [{id:'rechnungen', kind:'object', handles:['rechnung'], gruppe:'arbeit'}] : (o.type === 'task' ? [{id:'task', kind:'object'}] : []), {}, []);"
                  "const app = liste.apps.find(a=>a.id === 'mein-ort');"
                  "process.stdout.write(JSON.stringify({vorher, ok, bad, leer, gleich: ref === P.PLACES, laenge: ref.length, r1: r1.kind + ':' + r1.id, r2: r2.kind + ':' + r2.id, r3: r3.kind, "
                  "app: app && [app.symbol, app.gruppe, app.werkzeuge], doppelt: liste.apps.filter(a=>a.id.startsWith('werkzeug-')).length}));")
        out = subprocess.run([NODE, "-e", skript % (json.dumps(str(UIX / "ui" / "places.js")), json.dumps(str(UIX / "shells" / "harness" / "startliste.js")))],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        r = json.loads(out.stdout)
        self.assertEqual((r["ok"], r["bad"], r["leer"], r["gleich"], r["laenge"]), (True, False, False, True, 2))
        self.assertEqual((r["r1"], r["r2"]), ("place:mein-ort", "place:mein-ort"))
        self.assertEqual(r["r3"], "talk", "das Kernort-Wort logbuch ist nach dem Ersetzen nicht mehr in der Liste – hier nur: die Liste gilt")
        self.assertEqual(r["app"], ["★", "arbeit", ["rechnungen"]])
        self.assertEqual(r["doppelt"], 0, "der Ort ersetzt die abgeleitete App werkzeug-<id>")


if __name__ == "__main__":
    unittest.main()
