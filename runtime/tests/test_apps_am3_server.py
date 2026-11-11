"""AM3-08, AM3-09, AM3-11 (Stück 2 und 3): Einbau legt nur die Werkseinstellung an, Aktivieren und Entziehen wirken sofort, der Server prüft Lesen und Verben
einer fremden App gegen ihre gewährten Rechte – über echtes HTTP mit `X-SEDRA-Tool`."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import app_speicher
from sedra_runtime.uix_server import UIXHub, make_server

from test_desk_install import ARCH, CODE, module

MANIFEST = '''tool:
  id: fremd
  name: "Fremde App"
  version: 1.0.0
  kind: object
  handles: [task]
  entry: {js: tool.js}
  events: {emits: [], listens: [task.changed]}
  trust: COMMUNITY
  needs: {ui: ">=1.1 <2"}
  rechte:
    lesen: [task, model]
    verben: [task.close]
    ereignisse: [system.state, decision.pending]
'''


class Server(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am3-server-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.hub = UIXHub(self.root, ARCH)
        self.addCleanup(self.hub.close)
        self.hub.gateway.app_berechtigung = True
        self.quelle = module(Path(self.tmp.name) / "quelle" / "fremd", CODE, MANIFEST)
        self.hub.install_request({"kind": "tool", "source": str(self.quelle)})
        item = next(d for d in self.hub.decisions_view()["items"] if d["kind"] == "request:install")
        self.hub.decide({"id": item["id"], "way": "freigeben_und_anwenden"})
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port = server.server_port
        self.token = url.split("#")[1]

    def anfrage(self, methode, pfad, body=None, tool=None):
        kopf = {"X-SEDRA-Token": self.token}
        if tool:
            kopf["X-SEDRA-Tool"] = tool
        text = None
        if body is not None:
            kopf["Content-Type"] = "application/json"
            text = json.dumps(body)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
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

    def aktivieren(self):
        status, _ = self.anfrage("POST", "/api/uix/apps/aktivieren", {"id": "fremd"})
        self.assertEqual(status, 200)

    def gewaehre_alles(self):
        beantragt = self.hub.gateway.apps_uebersicht()[0]["beantragt"]
        app_speicher.aendern(self.root, "fremd", lambda e: {**e, "gewaehrt": sorted(b["faehigkeit"] for b in beantragt)})

    def test_einbau_legt_nur_die_werkseinstellung_an_und_inaktiv(self):
        eintrag = app_speicher.lesen(self.root)["fremd"]
        self.assertFalse(eintrag["aktiv"])
        self.assertEqual(eintrag["gewaehrt"], ["ereignis:system.state"],
                         "Werkseinstellung (AM3-28): Lesen nur eigener Typen, öffentliche Ereignisse; kein Lesen eingebauter Typen, kein Verb, kein inhaltliches Ereignis")

    def test_inaktiv_antwortet_403_app_inaktiv(self):
        status, antwort = self.anfrage("POST", "/api/objects", {"type": "task"}, tool="fremd")
        self.assertEqual((status, antwort.get("error")), (403, "app_inaktiv"))

    def test_beantragt_mehr_als_gewaehrt_laedt_nicht(self):
        self.aktivieren()
        status, antwort = self.anfrage("POST", "/api/objects", {"type": "task"}, tool="fremd")
        self.assertEqual(status, 403, "lesen:model und verb:task.close sind beantragt, aber nicht gewährt")
        self.assertEqual(self.hub.gateway.apps_uebersicht()[0]["grund"].split(":")[0], "rechte_nicht_gewaehrt")

    def test_gewaehrt_und_aktiv_liest_nur_gewaehrte_typen(self):
        self.gewaehre_alles()
        self.aktivieren()
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "task"}, tool="fremd")[0], 200)
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "model"}, tool="fremd")[0], 200)
        status, antwort = self.anfrage("POST", "/api/objects", {"type": "decision"}, tool="fremd")
        self.assertEqual((status, antwort.get("error")), (403, "typ_nicht_gewaehrt"))
        [zeile] = self.audit("UIX_APP_VERB_DENIED")
        self.assertEqual(zeile["payload"]["grund"], "typ_nicht_gewaehrt")

    def test_verben_nur_gewaehrte(self):
        self.gewaehre_alles()
        self.aktivieren()
        status, antwort = self.anfrage("POST", "/api/actions", {"type": "task", "id": "T-X", "verb": "cancel"}, tool="fremd")
        self.assertEqual((status, antwort.get("error")), (403, "verb_nicht_gewaehrt"))
        status, antwort = self.anfrage("POST", "/api/actions", {"type": "candidate", "id": "x", "verb": "uebernehmen"}, tool="fremd")
        self.assertEqual((status, antwort.get("error")), (403, "verb_nicht_gewaehrt"))
        status, antwort = self.anfrage("POST", "/api/actions", {"type": "task", "id": "T-X", "verb": "close"}, tool="fremd")
        self.assertNotEqual(antwort.get("error"), "verb_nicht_gewaehrt", "das gewährte Verb kommt durch die Prüfung (ob es das Objekt gibt, ist eine andere Frage)")

    def test_entzug_wirkt_sofort(self):
        self.gewaehre_alles()
        self.aktivieren()
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "task"}, tool="fremd")[0], 200)
        status, _ = self.anfrage("POST", "/api/uix/apps/entziehen", {"id": "fremd", "faehigkeiten": ["lesen:model"]})
        self.assertEqual(status, 200)
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "task"}, tool="fremd")[0], 403)
        self.assertTrue(self.audit("UIX_APP_RIGHTS_REVOKED"))

    def test_deaktivieren_wirkt_sofort(self):
        self.gewaehre_alles()
        self.aktivieren()
        status, _ = self.anfrage("POST", "/api/uix/apps/aktivieren", {"id": "fremd", "aktiv": False})
        self.assertEqual(status, 200)
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "task"}, tool="fremd")[1].get("error"), "app_inaktiv")
        self.assertTrue(self.audit("UIX_APP_DEACTIVATED"))

    def test_die_app_selbst_kann_weder_aktivieren_noch_entziehen_noch_lesen(self):
        self.gewaehre_alles()
        self.aktivieren()
        for pfad, body in (("/api/uix/apps/aktivieren", {"id": "fremd"}), ("/api/uix/apps/entziehen", {"id": "fremd", "faehigkeiten": ["lesen:task"]})):
            self.assertEqual(self.anfrage("POST", pfad, body, tool="fremd")[0], 403, pfad)
        self.assertEqual(self.anfrage("GET", "/api/uix/apps", tool="fremd")[0], 403)

    def test_aktivieren_ohne_gewaehrung_und_unbekannte_app(self):
        app_speicher.aendern(self.root, "fremd", lambda _e: None)
        status, antwort = self.anfrage("POST", "/api/uix/apps/aktivieren", {"id": "fremd"})
        self.assertEqual(status, 400)
        self.assertIn("keine_gewaehrung", json.dumps(antwort))
        status, antwort = self.anfrage("POST", "/api/uix/apps/aktivieren", {"id": "gibtsnicht"})
        self.assertEqual(status, 400)

    def test_ansicht_zeigt_beantragt_mit_stufe_und_gewaehrt(self):
        status, antwort = self.anfrage("GET", "/api/uix/apps")
        self.assertEqual(status, 200)
        [app] = antwort["apps"]
        stufen = {b["faehigkeit"]: (b["stufe"], b["gewaehrt"]) for b in app["beantragt"]}
        self.assertEqual(stufen["lesen:task"], ("A", False), "Stufe A, aber nicht Werkseinstellung: eingebaute Typen lesen nur auf Antrag")
        self.assertEqual(stufen["ereignis:system.state"], ("A", True))
        self.assertEqual(stufen["lesen:model"], ("A", False))
        self.assertEqual(stufen["verb:task.close"], ("B", False))
        self.assertEqual(stufen["ereignis:decision.pending"], ("B", False))
        self.assertFalse(app["aktiv"])

    def antrag(self, faehigkeiten):
        return self.hub.apps_rechte_request({"id": "fremd", "faehigkeiten": faehigkeiten})

    def offene_entscheidung(self):
        return next(d for d in self.hub.decisions_view()["items"] if d["kind"] == "request:apps_rechte")

    def gewaehrt(self):
        return app_speicher.lesen(self.root)["fremd"]["gewaehrt"]

    def test_antrag_gewaehrt_erst_nach_der_freigabe(self):
        self.antrag(["lesen:task", "verb:task.close"])
        self.assertEqual(self.gewaehrt(), ["ereignis:system.state"], "vor der Freigabe ändert sich nichts")
        d = self.offene_entscheidung()
        self.assertIn("verb:task.close (Stufe B)", d["risks"])
        self.hub.decide({"id": d["id"], "way": "freigeben_und_anwenden"})
        self.assertEqual(self.gewaehrt(), ["ereignis:system.state", "lesen:task", "verb:task.close"])
        self.assertEqual(len(self.audit("UIX_APP_RIGHTS_GRANTED")), 1)

    def test_antrag_ablehnen_aendert_nichts(self):
        self.antrag(["lesen:task"])
        self.hub.decide({"id": self.offene_entscheidung()["id"], "way": "ablehnen"})
        self.assertEqual(self.gewaehrt(), ["ereignis:system.state"])

    def test_was_nicht_beantragt_ist_wird_nicht_vorgelegt(self):
        with self.assertRaises(ValueError) as e:
            self.antrag(["lesen:decision"])
        self.assertIn("nicht_beantragt:lesen:decision", str(e.exception))

    def test_schon_gewaehrtes_wird_nicht_noch_einmal_gefragt(self):
        with self.assertRaises(ValueError) as e:
            self.antrag(["ereignis:system.state"])
        self.assertIn("schon_gewaehrt", str(e.exception))

    def test_geaendertes_manifest_zwischen_antrag_und_freigabe(self):
        self.antrag(["lesen:task"])
        ziel = self.root / "local_config" / "tools" / "fremd" / "tool.yaml"
        ziel.write_text(ziel.read_text(encoding="utf-8") + "  description: anders\n", encoding="utf-8")
        with self.assertRaises(ValueError) as e:
            self.hub.decide({"id": self.offene_entscheidung()["id"], "way": "freigeben_und_anwenden"})
        self.assertIn("manifest_changed_since_the_request", str(e.exception))
        self.assertEqual(self.gewaehrt(), ["ereignis:system.state"])

    def test_ganzer_weg_antrag_freigabe_aktivieren_lesen(self):
        self.antrag(["lesen:task", "lesen:model", "verb:task.close", "ereignis:decision.pending"])      # alles, was die App beantragt – sonst lädt sie nicht
        self.hub.decide({"id": self.offene_entscheidung()["id"], "way": "freigeben_und_anwenden"})
        self.aktivieren()
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "model"}, tool="fremd")[0], 200)
        self.assertEqual(self.anfrage("POST", "/api/objects", {"type": "decision"}, tool="fremd")[1].get("error"), "typ_nicht_gewaehrt")


if __name__ == "__main__":
    unittest.main()
