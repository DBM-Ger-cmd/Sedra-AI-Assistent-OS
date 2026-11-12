"""AM8-01 bis AM8-09 (SPEC_APPS_v1_AM8_VERZEICHNIS): das Verzeichnis aller Erweiterungen, die gemeinsamen Wirkungsklassen (Harness-Werkzeuge, Desk-Verben, Tabelle in der Datei), Export, Sperre für fremde Apps."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import actions, verzeichnis
from sedra_runtime.desk.routen_pruefung import route_sensibel
from sedra_runtime.harness import werkzeuge
from sedra_runtime.uix_server import UIXHub, make_server

from test_desk_install import ARCH, CODE, module

KLASSEN = ("read_only", "proposal_only", "preview", "reversible_write", "destructive_write", "external_side_effect", "privileged")


class Klassen(unittest.TestCase):
    def test_tabelle_ist_vollstaendig_und_gleich_der_reihenfolge(self):
        k = verzeichnis.klassen()
        self.assertEqual(sorted(k), sorted(KLASSEN))
        self.assertEqual(tuple(verzeichnis.REIHENFOLGE), KLASSEN)
        for name, e in k.items():
            self.assertTrue(e["bedeutung"].strip(), name)
            self.assertTrue(e["entspricht_ungefaehr"].strip(), name)
        self.assertEqual([k[n]["reihenfolge"] for n in KLASSEN], list(range(1, 8)))

    def test_die_sieben_klassen_sind_die_der_agenten_vorlagen(self):
        quelle = (Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "agent_manager" / "agent_import.py").read_text(encoding="utf-8")
        for k in KLASSEN:
            self.assertIn(k, quelle, k)

    def test_jedes_harness_werkzeug_hat_eine_gueltige_klasse(self):
        self.assertEqual(sorted(set(werkzeuge.NAMEN) - set(werkzeuge.WIRKUNGSKLASSE)), [], "AM8-06: neues Werkzeug braucht eine Wirkungsklasse")
        self.assertEqual(sorted(set(werkzeuge.WIRKUNGSKLASSE) - set(werkzeuge.NAMEN)), [], "veralteter Eintrag")
        self.assertTrue(set(werkzeuge.WIRKUNGSKLASSE.values()) <= set(KLASSEN))
        w = werkzeuge.WIRKUNGSKLASSE
        self.assertEqual((w["datei_lesen"], w["suchen"], w["befehl"], w["datei_schreiben"], w["projekt_beantragen"], w["auftraege_verteilen"]),
                         ("read_only", "read_only", "destructive_write", "reversible_write", "proposal_only", "external_side_effect"))

    def test_jedes_desk_verb_hat_eine_klasse(self):
        self.assertEqual(actions.ohne_wirkungsklasse(), [], "AM8-07")
        self.assertEqual(actions.wirkungsklasse("boundary", "aendern"), "privileged")
        self.assertIsNone(actions.wirkungsklasse("task", "gibtsnicht"))
        self.assertEqual(actions.ohne_wirkungsklasse({"neu": {"tun": object()}}), ["neu.tun"])
        self.assertTrue(set(actions.WIRKUNGSKLASSE.values()) <= set(KLASSEN))

    def test_klassen_der_faehigkeiten_einer_app(self):
        w = verzeichnis.wirkung_der_faehigkeit
        self.assertEqual((w("lesen:task"), w("ereignis:system.state"), w("zelle:text"), w("verb:task.close"), w("ablage:600"), w("dienst:host"), w("seltsam:x")),
                         ("read_only", "read_only", "read_only", "reversible_write", "reversible_write", "external_side_effect", "privileged"))
        self.assertEqual(w("verb:candidate.uebernehmen"), "privileged")


class Eintraege(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am8-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.hub = UIXHub(self.root, ARCH)
        self.addCleanup(self.hub.close)
        self.v = verzeichnis.verzeichnis(self.hub)

    def test_alle_acht_arten_stehen_da_und_nichts_ist_still_unbekannt(self):
        self.assertEqual(sorted(self.v["arten"]), sorted(verzeichnis.ARTEN))
        for art in ("werkzeug", "shell", "kern_erweiterung", "architektur_modul", "faehigkeit", "harness_vorlage", "daten"):
            self.assertGreater(self.v["arten"][art], 0, art)
        self.assertEqual(self.v["unlesbar"], [])
        self.assertEqual([e for e in self.v["eintraege"] if e["zustand"] == "unbekannt"], [])

    def test_eintraege_haben_die_felder_aus_am8_01(self):
        for e in self.v["eintraege"]:
            self.assertEqual(sorted(e), sorted(["art", "id", "name", "herkunft", "vertrauen", "version", "faehigkeiten", "abhaengigkeiten", "zustand", "grund", "stelle"]))
            self.assertIn(e["art"], verzeichnis.ARTEN)
            self.assertIn(e["zustand"], ("aktiv", "aus", "abgewiesen", "unbekannt"))
            for f in e["faehigkeiten"]:
                self.assertTrue({"name", "wirkungsklasse"} <= set(f))
        paket = [e for e in self.v["eintraege"] if e["art"] == "werkzeug" and e["id"] == "decisions"][0]
        self.assertEqual((paket["herkunft"], paket["vertrauen"]), ("paket", "CORE"))

    def test_harness_vorlagen_tragen_die_klassen_ihrer_werkzeuge(self):
        mm = [e for e in self.v["eintraege"] if e["art"] == "harness_vorlage" and e["id"] == "masterchat"][0]
        klassen = {f["name"]: f["wirkungsklasse"] for f in mm["faehigkeiten"]}
        self.assertEqual(klassen.get("befehl"), "destructive_write")
        self.assertTrue(set(klassen.values()) <= set(KLASSEN))

    def test_fremde_app_mit_rechten_zeigt_faehigkeiten_und_herkunft(self):
        manifest = ('tool:\n  id: fremd\n  name: "Fremde App"\n  version: 1.0.0\n  kind: object\n  handles: [task]\n  entry: {js: tool.js}\n  events: {emits: [], listens: []}\n'
                    '  trust: COMMUNITY\n  needs: {ui: ">=1.1 <2"}\n  rechte:\n    lesen: [task]\n    verben: [task.close]\n')
        quelle = module(Path(self.tmp.name) / "quelle" / "fremd", CODE, manifest)
        self.hub.gateway.app_berechtigung = False
        self.hub.install_request({"kind": "tool", "source": str(quelle)})
        item = next(d for d in self.hub.decisions_view()["items"] if d["kind"] == "request:install")
        self.hub.decide({"id": item["id"], "way": "freigeben_und_anwenden"})
        self.hub.gateway.app_berechtigung = True
        [a] = [x for x in verzeichnis.verzeichnis(self.hub)["eintraege"] if x["id"] == "fremd"]
        self.assertEqual((a["art"], a["zustand"], a["herkunft"]), ("werkzeug", "abgewiesen", "eingebaut"))
        self.assertIn("keine_gewaehrung", a["grund"], "ohne Gewährung lädt sie nicht")
        self.hub.apps_rechte_request({"id": "fremd", "faehigkeiten": ["lesen:task", "verb:task.close"]})
        item = next(d for d in self.hub.decisions_view()["items"] if d["kind"] == "request:apps_rechte")
        self.hub.decide({"id": item["id"], "way": "freigeben_und_anwenden"})
        self.hub.apps_aktivieren({"id": "fremd"})
        [a] = [x for x in verzeichnis.verzeichnis(self.hub)["eintraege"] if x["id"] == "fremd"]
        self.assertEqual((a["zustand"], a["vertrauen"], a["herkunft"]), ("aktiv", "COMMUNITY", "eingebaut"))
        self.assertEqual({f["name"]: f["wirkungsklasse"] for f in a["faehigkeiten"]}, {"lesen:task": "read_only", "verb:task.close": "reversible_write"})
        self.assertEqual(verzeichnis.stufe_hoechste(a), "reversible_write")

    def test_eine_nicht_lesbare_quelle_steht_mit_grund_in_der_liste(self):
        def kaputt(hub):
            raise OSError("Platte weg")
        quellen = tuple((n, kaputt if n == "faehigkeit" else f) for n, f in verzeichnis.QUELLEN)
        with mock.patch.object(verzeichnis, "QUELLEN", quellen):
            v = verzeichnis.verzeichnis(self.hub)
        [u] = [e for e in v["eintraege"] if e["zustand"] == "unbekannt"]
        self.assertEqual(u["art"], "faehigkeit")
        self.assertIn("Platte weg", u["grund"])
        self.assertEqual(v["unlesbar"][0]["quelle"], "faehigkeit")

    def test_filter_und_hoechste_klasse(self):
        nur = verzeichnis.filtern(self.v, art="harness_vorlage")
        self.assertTrue(nur and all(e["art"] == "harness_vorlage" for e in nur))
        self.assertTrue(all(any(f["wirkungsklasse"] == "destructive_write" for f in e["faehigkeiten"]) for e in verzeichnis.filtern(self.v, klasse="destructive_write")))
        self.assertTrue(all(e["herkunft"] == "paket" for e in verzeichnis.filtern(self.v, herkunft="paket")))
        self.assertEqual(verzeichnis.filtern(self.v, art="werkzeug", zustand="gibtsnicht"), [])
        e = {"faehigkeiten": [{"name": "a", "wirkungsklasse": "read_only"}, {"name": "b", "wirkungsklasse": "privileged"}]}
        self.assertEqual(verzeichnis.stufe_hoechste(e), "privileged")
        self.assertIsNone(verzeichnis.stufe_hoechste({"faehigkeiten": []}))

    def test_lesbarer_export(self):
        text = verzeichnis.lesbar(self.v)
        self.assertIn("Verzeichnis der Erweiterungen", text)
        self.assertIn("[werkzeug] decisions", text)
        self.assertIn("→ destructive_write", text)
        ex = verzeichnis.export(self.hub)
        self.assertEqual(sorted(ex), ["json", "text"])
        json.dumps(ex["json"])


class Route(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am8-route-")
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port, self.token = server.server_port, url.split("#")[1]

    def hole(self, pfad, tool=None, token=True):
        kopf = {"X-SEDRA-Token": self.token} if token else {}
        if tool:
            kopf["X-SEDRA-Tool"] = tool
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            c.request("GET", pfad, None, kopf)
            res = c.getresponse()
            roh = res.read()
            try:
                return res.status, json.loads(roh or b"{}")
            except ValueError:
                return res.status, {}
        finally:
            c.close()

    def test_verzeichnis_und_export_ueber_http(self):
        status, v = self.hole("/api/erweiterungen")
        self.assertEqual(status, 200)
        self.assertGreater(v["arten"]["werkzeug"], 0)
        self.assertEqual(sorted(v["klassen"]), sorted(KLASSEN))
        status, ex = self.hole("/api/erweiterungen/export")
        self.assertEqual((status, sorted(ex)), (200, ["json", "text"]))

    def test_ohne_token_nicht(self):
        self.assertEqual(self.hole("/api/erweiterungen", token=False)[0], 403)

    def test_die_route_ist_fuer_fremde_apps_gesperrt(self):
        self.assertTrue(route_sensibel("GET /api/erweiterungen"))
        self.assertTrue(route_sensibel("GET /api/erweiterungen/export"))
        self.assertEqual(self.hole("/api/erweiterungen", tool="gibt-es-nicht")[0], 403)


class Seite(unittest.TestCase):
    def test_filter_der_seite_und_routen_im_manifest(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node fehlt")
        ordner = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix" / "tools" / "modules"
        skript = ("const m = require(%s); const e = [{art:'werkzeug', herkunft:'paket', faehigkeiten:[{wirkungsklasse:'read_only'}]}, {art:'shell', herkunft:'captain', faehigkeiten:[]},"
                  "{art:'werkzeug', herkunft:'eingebaut', faehigkeiten:[{wirkungsklasse:'privileged'}]}];"
                  "process.stdout.write(JSON.stringify([m.verzeichnisFiltern(e, {}).length, m.verzeichnisFiltern(e, {art:'werkzeug'}).length, m.verzeichnisFiltern(e, {klasse:'privileged'}).length,"
                  "m.verzeichnisFiltern(e, {herkunft:'paket', klasse:'read_only'}).length, m.verzeichnisFiltern(null, {}).length, Object.keys(m.ART_NAMEN).length]));")
        out = subprocess.run([node, "-e", skript % json.dumps(str(ordner / "tool.js"))], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), [3, 2, 1, 1, 0, 8])
        yaml_text = (ordner / "tool.yaml").read_text(encoding="utf-8")
        self.assertIn("GET /api/erweiterungen", yaml_text)
        self.assertIn("GET /api/erweiterungen/export", yaml_text)
        self.assertLessEqual(len((ordner / "tool.js").read_text(encoding="utf-8").splitlines()), 400)


if __name__ == "__main__":
    unittest.main()
