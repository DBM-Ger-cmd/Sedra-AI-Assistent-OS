"""App Coder, Ausbau: Suche im Projekt (R6). Nur lesen; Sperrliste, Binärdateien, große Dateien und Zeitgrenze; Adresse über HTTP."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime import coder_lesen as cl
from sedra_runtime.uix_server import UIXHub, make_server

ARCH = Path(__file__).resolve().parents[2] / "architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC"


class Rein(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.w = Path(self.tmp.name)
        (self.w / "src").mkdir()
        (self.w / "src" / "a.py").write_text("alpha = 1\nBeta = 2\nalpha2 = 3\n", encoding="utf-8")
        (self.w / "b.txt").write_text("noch ein Alpha\n", encoding="utf-8")

    def test_findet_ohne_grossschreibung_mit_zeilen(self):
        out = cl.suche(self.w, "ALPHA")
        self.assertEqual([(t["pfad"], t["zeile"]) for t in out["treffer"]], [("b.txt", 1), ("src/a.py", 1), ("src/a.py", 3)])
        self.assertEqual((out["quelle"], out["anzahl"], out["gekuerzt"]), ("ok", 3, False))

    def test_gesperrtes_binaeres_grosses_und_versteckte_bleiben_draussen(self):
        (self.w / ".env").write_text("alpha=geheim\n", encoding="utf-8")
        (self.w / "local_config").mkdir()
        (self.w / "local_config" / "x.yaml").write_text("alpha: geheim\n", encoding="utf-8")
        (self.w / "server.key").write_text("alpha geheim\n", encoding="utf-8")
        (self.w / "bin.dat").write_bytes(b"alpha\x00\x01")
        (self.w / "gross.txt").write_text("alpha " * (cl.SUCHE_DATEI_BYTES // 5), encoding="utf-8")
        (self.w / ".git").mkdir()
        (self.w / ".git" / "cfg").write_text("alpha\n", encoding="utf-8")
        text = json.dumps(cl.suche(self.w, "alpha"))
        for verboten in ("geheim", ".env", "local_config", "server.key", "bin.dat", "gross.txt", ".git"):
            self.assertNotIn(verboten, text)

    def test_kein_pfad_des_rechners_und_kein_muster(self):
        self.assertNotIn(str(self.w), json.dumps(cl.suche(self.w, "alpha")))
        (self.w / "m.txt").write_text("a.c und abc\n", encoding="utf-8")
        self.assertEqual(cl.suche(self.w, "a.c")["anzahl"], 1, "reiner Text, kein Muster")

    def test_grenzen(self):
        (self.w / "viel.txt").write_text("x\n" * (cl.SUCHE_TREFFER_MAX + 50), encoding="utf-8")
        out = cl.suche(self.w, "x")
        self.assertEqual((out["anzahl"], out["gekuerzt"]), (cl.SUCHE_TREFFER_MAX, True))
        zeiten = iter(range(0, 1000, 5))          # die Uhr springt: sofort über der Zeitgrenze
        self.assertTrue(cl.suche(self.w, "alpha", uhr=lambda: next(zeiten))["gekuerzt"])

    def test_frage_pruefen(self):
        for schlecht in ("", "  ", "x" * (cl.SUCHE_FRAGE_MAX + 1), "a\x00b", "a\nb"):
            with self.assertRaises(ValueError):
                cl.suche_frage(schlecht)


class Http(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.pid = self.hub.new_project({"name": "Suche"})["project_id"]
        ws = self.hub.runtime.filesystem_tool._resolve(self.hub.projects.get(self.pid)["workspace_path"])
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "a.py").write_text("hallo welt\n", encoding="utf-8")
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port, self.token = server.server_port, url.split("#")[1]

    def get(self, pfad, werkzeug="coder"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            kopf = {"X-SEDRA-Token": self.token}
            if werkzeug:
                kopf["X-SEDRA-Tool"] = werkzeug
            c.request("GET", pfad, None, kopf)
            r = c.getresponse()
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
        finally:
            c.close()

    def test_route(self):
        s, out = self.get(f"/api/uix/coder/suche/{self.pid}/Welt")
        self.assertEqual((s, out["anzahl"], out["treffer"][0]["pfad"]), (200, 1, "a.py"))
        self.assertEqual(self.get(f"/api/uix/coder/suche/{self.pid}/Welt", werkzeug="anderes")[0], 403)
        self.assertEqual(self.get(f"/api/uix/coder/suche/{self.pid}")[0], 400)
        self.assertEqual(self.get("/api/uix/coder/suche/PRJ-nope/x")[0], 400)


if __name__ == "__main__":
    unittest.main()
