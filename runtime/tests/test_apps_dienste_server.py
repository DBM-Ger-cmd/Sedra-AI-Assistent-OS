"""AM4 im Hub (SPEC_APPS_v1_AM4_DIENSTE): Dienst-Apps (kind: dienst) laden und starten nur mit Schalter und Gate, ihr Token öffnet nur objects/actions gegen die Berechtigung (`client: dienst:<id>`),
Stopp entzieht ihn sofort; der Zugang `mcp` ruft mit dem Schalter nur gewährte Verben, `cli` bleibt frei. Echtes HTTP, echter Fake-Dienst."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime import uix_clients
from sedra_runtime.desk import app_speicher
from sedra_runtime.uix_server import UIXHub, make_server

from test_desk_install import ARCH

DIENST = '''import time
while True:
    time.sleep(0.2)
'''
MANIFEST = '''tool:
  id: {id}
  name: "Mein Dienst"
  version: 1.0.0
  kind: dienst
  trust: {trust}
  needs: {{ui: ">=1.1 <2"}}
  rechte:
    lesen: [task]
    verben: [task.close]
  dienst:
    start: [dienst.py]
    ort: {ort}
    neustart: nie
'''


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am4-server-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.hub = UIXHub(self.root, ARCH)
        self.addCleanup(self.hub.close)
        self.hub.gateway.herkunft_pruefen = False
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port, self.token = server.server_port, url.split("#")[1]

    def dienst_app(self, id="mein-dienst", trust="CAPTAIN", ort="host"):
        ordner = self.root / "local_config" / "tools" / id
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "dienst.py").write_text(DIENST, encoding="utf-8")
        (ordner / "tool.yaml").write_text(MANIFEST.format(id=id, trust=trust, ort=ort), encoding="utf-8")
        return ordner

    def anfrage(self, methode, pfad, body=None, token=None, tool=None):
        kopf = {"X-SEDRA-Token": token or self.token}
        if tool:
            kopf["X-SEDRA-Tool"] = tool
        text = None
        if body is not None:
            kopf["Content-Type"] = "application/json"
            text = json.dumps(body)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            c.request(methode, pfad, text, kopf)
            res = c.getresponse()
            roh = res.read()
            try:
                return res.status, json.loads(roh or b"{}")
            except ValueError:
                return res.status, {}
        finally:
            c.close()

    def audit(self, typ):
        a = self.hub.runtime.audit
        return [e for e in (json.loads(z) for z in a.path.read_text(encoding="utf-8").splitlines() if z.strip()) if e.get("event_type") == typ]

    def entscheide(self, art, way="freigeben_und_anwenden"):
        item = next(d for d in self.hub.decisions_view()["items"] if d["kind"] == art)
        return self.hub.decide({"id": item["id"], "way": way})


class Dienst(Basis):
    def test_dienst_laedt_ohne_flaeche_und_steht_nicht_in_der_oberflaeche(self):
        self.dienst_app()
        self.assertIn("mein-dienst", self.hub.gateway.tools())
        self.assertNotIn("mein-dienst", [t["id"] for t in self.hub.gateway.manifest()["tools"]])
        status, v = self.anfrage("GET", "/api/uix/dienste")
        self.assertEqual(status, 200)
        [d] = v["dienste"]
        self.assertEqual((d["id"], d["laeuft"], d["ort"], d["vertrauen"]), ("mein-dienst", False, "host", "CAPTAIN"))
        self.assertFalse(v["schalter"])

    def test_fremder_dienst_und_microvm_sind_nicht_einbaubar(self):
        self.dienst_app("fremder", trust="COMMUNITY")
        self.dienst_app("vm", ort="microvm")
        gruende = {r["id"]: r["reasons"] for r in self.hub.gateway.manifest()["rejected"]}
        self.assertIn("dienst_fremd_nur_microvm", gruende["fremder"])
        self.assertIn("dienst_microvm_nicht_verfuegbar", gruende["vm"])
        status, v = self.anfrage("GET", "/api/uix/dienste")
        self.assertEqual(sorted(a["id"] for a in v["abgewiesen"]), ["fremder", "vm"])

    def test_dienst_block_bei_einem_objekt_werkzeug_wird_abgewiesen(self):
        ordner = self.root / "local_config" / "tools" / "objekt"
        ordner.mkdir(parents=True)
        (ordner / "tool.js").write_text("// x\n", encoding="utf-8")
        (ordner / "tool.yaml").write_text('tool:\n  id: objekt\n  name: O\n  version: 1.0.0\n  kind: object\n  handles: [task]\n  entry: {js: tool.js}\n  trust: CAPTAIN\n'
                                          '  needs: {ui: ">=1.0 <2"}\n  dienst: {start: [dienst.py]}\n', encoding="utf-8")
        self.assertEqual({r["id"]: r["reasons"] for r in self.hub.gateway.manifest()["rejected"]}["objekt"], ["dienst_nur_bei_kind_dienst"])

    def test_start_nur_mit_schalter_und_gate(self):
        self.dienst_app()
        with self.assertRaises(ValueError) as e:
            self.hub.dienst_start_antrag({"id": "mein-dienst"})
        self.assertIn("dienste_aus", str(e.exception))
        self.hub.dienste_an = True
        self.hub.dienst_start_antrag({"id": "mein-dienst"})
        self.assertFalse(self.hub.dienste.laufend, "vor der Freigabe läuft nichts")
        item = next(d for d in self.hub.decisions_view()["items"] if d["kind"] == "request:dienst_start")
        self.assertIn("mit den Rechten deines Windows-Kontos", "\n".join(item["risks"]))
        self.assertIn("dienst.py", "\n".join(item["risks"]))
        self.hub.decide({"id": item["id"], "way": "freigeben_und_anwenden"})
        self.assertIn("mein-dienst", self.hub.dienste.laufend)
        self.assertEqual(self.audit("DIENST_GESTARTET")[-1]["payload"]["id"], "mein-dienst")

    def test_ablehnen_startet_nichts_und_unbekannter_dienst(self):
        self.dienst_app()
        self.hub.dienste_an = True
        self.hub.dienst_start_antrag({"id": "mein-dienst"})
        self.entscheide("request:dienst_start", "ablehnen")
        self.assertFalse(self.hub.dienste.laufend)
        with self.assertRaises(ValueError):
            self.hub.dienst_start_antrag({"id": "gibt-es-nicht"})

    def test_geaendertes_manifest_zwischen_antrag_und_freigabe_startet_nichts(self):
        ordner = self.dienst_app()
        self.hub.dienste_an = True
        self.hub.dienst_start_antrag({"id": "mein-dienst"})
        (ordner / "tool.yaml").write_text((ordner / "tool.yaml").read_text(encoding="utf-8") + "  description: anders\n", encoding="utf-8")
        try:
            self.entscheide("request:dienst_start")
        except ValueError:
            pass                                                   # je nach Weg meldet das Gate die veraltete Bindung als Fehler oder als Ergebnis – gestartet wird nichts
        self.assertFalse(self.hub.dienste.laufend)
        self.assertEqual(self.audit("DIENST_GESTARTET"), [])

    def test_token_liest_nur_gewaehrte_typen_ruft_nur_gewaehrte_verben_und_client_ist_dienst(self):
        self.dienst_app()
        self.hub.dienste_an = True
        self.hub.dienst_start_antrag({"id": "mein-dienst"})
        self.entscheide("request:dienst_start")
        token = self.hub.dienste.laufend["mein-dienst"]["token"]
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "task"}, token=token)[0], 200)
        status, antwort = self.anfrage("POST", "/api/objects", {"type": "decision"}, token=token)
        self.assertEqual((status, antwort["error"]), (403, "typ_nicht_gewaehrt"))
        status, antwort = self.anfrage("POST", "/api/actions", {"type": "task", "id": "T-X", "verb": "archivieren"}, token=token)
        self.assertEqual((status, antwort["error"]), (403, "verb_nicht_gewaehrt"))
        status, antwort = self.anfrage("POST", "/api/actions", {"type": "task", "id": "T-X", "verb": "close"}, token=token)
        self.assertNotEqual(antwort.get("error"), "verb_nicht_gewaehrt", "das gewährte Verb kommt durch die Prüfung")
        self.assertEqual(self.anfrage("GET", "/api/strip", token=token)[0], 403, "der Token öffnet nur objects und actions")
        status, antwort = self.anfrage("POST", "/api/objects", {"type": "task", "client": "shell"}, token=token)
        self.assertEqual(status, 400, "der Client wird vom Server gesetzt, nie vom Aufrufer")
        denied = self.audit("UIX_APP_VERB_DENIED")
        self.assertEqual({e["payload"]["app"] for e in denied}, {"dienst:mein-dienst"})

    def test_stopp_entzieht_den_token_sofort(self):
        self.dienst_app()
        self.hub.dienste_an = True
        self.hub.dienst_start_antrag({"id": "mein-dienst"})
        self.entscheide("request:dienst_start")
        token = self.hub.dienste.laufend["mein-dienst"]["token"]
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "task"}, token=token)[0], 200)
        status, antwort = self.anfrage("POST", "/api/uix/dienste/stopp", {"id": "mein-dienst"})
        self.assertEqual((status, antwort["status"]), (200, "gestoppt"))
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "task"}, token=token)[0], 403)
        self.assertEqual(self.anfrage("POST", "/api/uix/dienste/stopp", {"id": "mein-dienst"})[0], 400)
        self.assertIn("DIENST_TOKEN_ENTZOGEN", [e["event_type"] for e in map(json.loads, self.hub.runtime.audit.path.read_text(encoding="utf-8").splitlines())])

    def test_der_token_kann_keine_entscheidung_beantworten_und_kein_dienst_startet_einen_dienst(self):
        self.dienst_app()
        self.hub.dienste_an = True
        self.hub.dienst_start_antrag({"id": "mein-dienst"})
        self.entscheide("request:dienst_start")
        token = self.hub.dienste.laufend["mein-dienst"]["token"]
        for pfad in ("/api/decisions/answer", "/api/uix/dienste/start", "/api/uix/install"):
            self.assertEqual(self.anfrage("POST", pfad, {}, token=token)[0], 403, pfad)

    def test_server_ende_stoppt_die_dienste(self):
        self.dienst_app()
        self.hub.dienste_an = True
        self.hub.dienst_start_antrag({"id": "mein-dienst"})
        self.entscheide("request:dienst_start")
        proc = self.hub.dienste.laufend["mein-dienst"]["proc"]
        self.hub.dienste.stop_alle("ende")
        self.assertTrue(self._warte(lambda: proc.poll() is not None))

    def _warte(self, bedingung, s=10):
        ende = time.time() + s
        while time.time() < ende:
            if bedingung():
                return True
            time.sleep(0.1)
        return False


class Zugang(Basis):
    def mcp_token(self):
        return uix_clients.read(self.root, "mcp")["token"]

    def cli_token(self):
        return uix_clients.read(self.root, "cli")["token"]

    def verb(self, token, verb="schliessen"):
        return self.anfrage("POST", "/api/actions", {"type": "task", "id": "T-X", "verb": verb}, token=token)

    def test_uebergang_schalter_aus_mcp_ruft_wie_bisher_verben(self):
        status, antwort = self.verb(self.mcp_token())
        self.assertNotEqual(antwort.get("error"), "verb_nicht_gewaehrt")
        v = self.anfrage("GET", "/api/uix/zugaenge")[1]
        self.assertEqual((v["schalter"], v["zugaenge"]["mcp"]["wirkt"], v["zugaenge"]["mcp"]["verben"], v["zugaenge"]["mcp"]["lesen"]), (False, False, [], "alle"))
        self.assertIn("Windows-Konto", v["satz"])

    def test_schalter_an_mcp_nur_gewaehrte_verben_lesen_alle(self):
        self.hub.zugang_an = True
        status, antwort = self.verb(self.mcp_token())
        self.assertEqual((status, antwort["error"]), (403, "verb_nicht_gewaehrt"))
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "task"}, token=self.mcp_token())[0], 200)
        self.assertEqual({e["payload"]["app"] for e in self.audit("UIX_APP_VERB_DENIED")}, {"mcp"})

    def test_cli_bleibt_frei_auch_mit_dem_schalter(self):
        self.hub.zugang_an = True
        status, antwort = self.verb(self.cli_token())
        self.assertNotEqual(antwort.get("error"), "verb_nicht_gewaehrt")
        self.assertTrue(self.anfrage("GET", "/api/uix/zugaenge")[1]["zugaenge"]["cli"]["wirkt"])

    def test_verb_beantragen_gate_und_danach_erlaubt(self):
        self.hub.zugang_an = True
        self.hub.zugang_rechte_request({"zugang": "mcp", "faehigkeiten": ["verb:task.schliessen"]})
        self.assertEqual(app_speicher.zugaenge_lesen(self.root), {}, "vor der Freigabe ändert sich nichts")
        self.entscheide("request:zugang_rechte")
        self.assertEqual(app_speicher.zugaenge_lesen(self.root)["mcp"]["verben"], ["task.schliessen"])
        status, antwort = self.verb(self.mcp_token())
        self.assertNotEqual(antwort.get("error"), "verb_nicht_gewaehrt")
        self.assertEqual(self.verb(self.mcp_token(), "archivieren")[1]["error"], "verb_nicht_gewaehrt")
        self.assertEqual(self.audit("UIX_ZUGANG_RIGHTS_GRANTED")[-1]["payload"]["faehigkeiten"], ["verb:task.schliessen"])

    def test_die_vier_verben_mit_gate_und_ungueltige_antraege(self):
        for f in ("verb:candidate.uebernehmen", "verb:boundary.aendern"):
            with self.assertRaises(ValueError) as e:
                self.hub.zugang_rechte_request({"zugang": "mcp", "faehigkeiten": [f]})
            self.assertIn("stufe_c_abgewiesen", str(e.exception))
        for payload in ({"zugang": "cli", "faehigkeiten": ["verb:task.close"]}, {"zugang": "mcp", "faehigkeiten": []}, {"zugang": "mcp", "faehigkeiten": ["lesen:task"]}):
            with self.assertRaises(ValueError):
                self.hub.zugang_rechte_request(payload)

    def test_die_gewaehrung_bleibt_neben_den_apps_in_einer_datei(self):
        app_speicher.schreiben(self.root, {"x-app": {"aktiv": True, "gewaehrt": [], "manifest_sha256": "a", "vertrauen": "COMMUNITY"}})
        app_speicher.zugang_schreiben(self.root, "mcp", {"lesen": "alle", "verben": ["task.close"]})
        app_speicher.aendern(self.root, "x-app", lambda e: dict(e, aktiv=False))
        self.assertEqual(app_speicher.zugaenge_lesen(self.root)["mcp"]["verben"], ["task.close"], "Schreiben der Apps lässt die Zugänge stehen")
        self.assertFalse(app_speicher.lesen(self.root)["x-app"]["aktiv"])
        with self.assertRaises(ValueError):
            app_speicher.zugang_schreiben(self.root, "dienst", {})


if __name__ == "__main__":
    unittest.main()
