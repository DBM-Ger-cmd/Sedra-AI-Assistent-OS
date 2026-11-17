"""App Coder, Ausbau: gemerkter Zustand. Feste Felder mit Grenzen, nie Dateitext, eine lokale Datei außerhalb des Projekts, Adresse über HTTP."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime import coder_zustand as cz
from sedra_runtime.uix_server import UIXHub, make_server

ARCH = Path(__file__).resolve().parents[2] / "architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC"


class Rein(unittest.TestCase):
    def test_gueltiger_zustand_bleibt(self):
        z = cz.bereinige({"projekt": "PRJ-1", "schrift": 16, "weg": "lokal", "chat": [{"von": "Ich", "ich": True, "text": "hallo"}],
                          "verlauf": [{"role": "user", "content": "q"}], "antraege": [{"id": "M-ABC123", "art": "speichern", "pfad": "a.py"}]})
        self.assertEqual((z["projekt"], z["schrift"], z["weg"]), ("PRJ-1", 16, "lokal"))
        self.assertEqual(z["chat"], [{"von": "Ich", "ich": True, "text": "hallo"}])
        self.assertEqual(z["antraege"], [{"id": "M-ABC123", "art": "speichern", "pfad": "a.py", "ziel": None}])

    def test_ungueltiges_faellt_weg(self):
        for roh in (None, "text", 5, [], {"projekt": "a/b", "schrift": 99}, {"schrift": True}, {"chat": "x"}):
            z = cz.bereinige(roh)
            self.assertEqual((z["projekt"], z["schrift"], z["chat"], z["antraege"]), ("", 13, [], []), str(roh))
        z = cz.bereinige({"antraege": [{"id": "../x", "art": "speichern", "pfad": "a"}, {"id": "M-ABC", "art": "boese", "pfad": "a"},
                                       {"id": "M-ABC", "art": "loeschen", "pfad": ".env"}, {"id": "M-OK1", "art": "loeschen", "pfad": "x.txt"}],
                          "verlauf": [{"role": "system", "content": "x"}, {"role": "user", "content": "ok"}]})
        self.assertEqual([a["id"] for a in z["antraege"]], ["M-OK1"])
        self.assertEqual(len(z["verlauf"]), 1)

    def test_grenzen(self):
        z = cz.bereinige({"chat": [{"von": "x", "ich": False, "text": "y" * 99999}] * 100, "unbekannt": "x"})
        self.assertEqual(len(z["chat"]), cz.CHAT_MAX)
        self.assertEqual(len(z["chat"][0]["text"]), cz.TEXT_MAX)
        self.assertNotIn("unbekannt", z)


class Http(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port, self.token = server.server_port, url.split("#")[1]

    def rufe(self, methode, pfad, body=None, werkzeug="coder"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            kopf = {"X-SEDRA-Token": self.token, "Content-Type": "application/json"}
            if werkzeug:
                kopf["X-SEDRA-Tool"] = werkzeug
            c.request(methode, pfad, json.dumps(body) if body is not None else None, kopf)
            r = c.getresponse()
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
        finally:
            c.close()

    def test_merken_und_wiederfinden(self):
        s, leer = self.rufe("GET", "/api/uix/coder/zustand")
        self.assertEqual((s, leer["zustand"]["projekt"], leer["zustand"]["chat"]), (200, "", []))
        body = {"zustand": {"projekt": "PRJ-7", "schrift": 15, "chat": [{"von": "Ich", "ich": True, "text": "hi"}], "boeses": "x"}}
        self.assertEqual(self.rufe("POST", "/api/uix/coder/zustand", body)[0], 200)
        s, z = self.rufe("GET", "/api/uix/coder/zustand")
        self.assertEqual((z["zustand"]["projekt"], z["zustand"]["schrift"], len(z["zustand"]["chat"])), ("PRJ-7", 15, 1))
        datei = Path(self.hub.runtime.project_root) / "local_config" / "coder_zustand.json"
        self.assertTrue(datei.is_file())
        self.assertNotIn("boeses", datei.read_text(encoding="utf-8"))
        self.assertEqual(self.rufe("GET", "/api/uix/coder/zustand", werkzeug="anderes")[0], 403)

    def test_kaputte_datei_gibt_leeren_zustand(self):
        datei = Path(self.hub.runtime.project_root) / "local_config" / "coder_zustand.json"
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text("{kaputt", encoding="utf-8")
        s, z = self.rufe("GET", "/api/uix/coder/zustand")
        self.assertEqual((s, z["zustand"]["projekt"]), (200, ""))


if __name__ == "__main__":
    unittest.main()
