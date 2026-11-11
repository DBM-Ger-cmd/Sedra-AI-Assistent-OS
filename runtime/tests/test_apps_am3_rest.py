"""AM3 Rest: die Ablage einer App (`ablage:<n>`, höchstens 1 MB), die letzten Audit-Einträge je App und der Export `/api/uix/apps/verzeichnis`."""
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
  gedaechtnis: [ablage]
  rechte:
    ablage: ABLAGE
'''


class Rest(unittest.TestCase):
    ABLAGE = 600

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am3-rest-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.hub = UIXHub(self.root, ARCH)
        self.addCleanup(self.hub.close)
        self.hub.gateway.app_berechtigung = True
        quelle = module(Path(self.tmp.name) / "quelle" / "fremd", CODE, MANIFEST.replace("ABLAGE", str(self.ABLAGE)))
        self.hub.install_request({"kind": "tool", "source": str(quelle)})
        self.entscheide("request:install")
        self.assertEqual(app_speicher.lesen(self.root)["fremd"]["gewaehrt"], ["ablage:%d" % self.ABLAGE], "ablage bis 1 MB ist Stufe A: Werkseinstellung")
        self.hub.apps_aktivieren({"id": "fremd"})
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port = server.server_port
        self.token = url.split("#")[1]

    def entscheide(self, art):
        item = next(d for d in self.hub.decisions_view()["items"] if d["kind"] == art)
        return self.hub.decide({"id": item["id"], "way": "freigeben_und_anwenden"})

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

    def schreibe(self, objekt, text):
        return self.anfrage("POST", "/api/ablage/schreiben", {"objekt": objekt, "werte": {"t": text}}, tool="fremd")

    def test_ablage_nur_mit_gewaehrter_faehigkeit_und_innerhalb_der_grenze(self):
        self.assertEqual(self.schreibe("task:T-1", "x" * 100)[0], 200)
        status, antwort = self.anfrage("POST", "/api/ablage/lesen", {"objekt": "task:T-1"}, tool="fremd")
        self.assertEqual((status, antwort["werte"]["t"]), (200, "x" * 100))
        status, antwort = self.schreibe("task:T-2", "y" * 600)
        self.assertEqual(status, 400, "100 + 600 Byte sind mehr als die gewährten 600")
        self.assertIn("ablage_zu_gross", json.dumps(antwort))
        self.assertEqual(self.schreibe("task:T-1", "z" * 400)[0], 200, "der eigene Eintrag wird ersetzt, nicht addiert")

    def test_ohne_ablage_fahigkeit_keine_ablage_obwohl_gedaechtnis_ablage_im_manifest_steht(self):
        self.anfrage("POST", "/api/uix/apps/entziehen", {"id": "fremd", "faehigkeiten": ["ablage:%d" % self.ABLAGE]})
        # beantragt ist `ablage`, gewährt nichts → die App lädt gar nicht
        self.assertEqual(self.schreibe("task:T-1", "x")[0], 403)

    def test_ablage_grenze_hoechstens_ein_megabyte(self):
        self.assertEqual(self.hub.gateway.ablage_grenze("fremd"), self.ABLAGE)
        self.assertIsNone(self.hub.gateway.ablage_grenze("decisions"), "ein Paket-Werkzeug hat keine App-Grenze")
        self.assertIsNone(self.hub.gateway.ablage_grenze("gibt-es-nicht"))

    def test_audit_je_app_und_verzeichnis(self):
        status, antwort = self.anfrage("GET", "/api/uix/apps")
        self.assertEqual(status, 200)
        [app] = antwort["apps"]
        arten = [e["art"] for e in app["audit"]]
        self.assertIn("UIX_APP_ACTIVATED", arten)
        self.assertIn("UIX_APP_RIGHTS_SET", arten)
        self.assertIn("UIX_MODULE_INSTALLED", arten)
        self.assertLessEqual(len(app["audit"]), 20)
        self.assertEqual(app["audit"][0]["art"], "UIX_APP_ACTIVATED", "das Neueste zuerst")
        status, verz = self.anfrage("GET", "/api/uix/apps/verzeichnis")
        self.assertEqual(status, 200)
        [eintrag] = verz["apps"]
        self.assertEqual((eintrag["id"], eintrag["aktiv"], eintrag["gewaehrt"], eintrag["beantragt"]), ("fremd", True, ["ablage:600"], ["ablage:600"]))
        self.assertEqual(len(eintrag["manifest_sha256"]), 64)

    def test_die_app_selbst_kann_das_verzeichnis_nicht_lesen(self):
        self.assertEqual(self.anfrage("GET", "/api/uix/apps/verzeichnis", tool="fremd")[0], 403)


if __name__ == "__main__":
    unittest.main()
