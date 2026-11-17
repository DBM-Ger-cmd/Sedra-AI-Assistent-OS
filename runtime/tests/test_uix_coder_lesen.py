"""App Coder, Runde 5 (R1 bis R3): Lese-Routen mit Sperrliste. Reine Teile (Sperrliste, Adresse), die Hub-Wege und die Adressen über HTTP
mit dem Kopf des Werkzeugs: erlaubt sind nur die drei Routen aus der tool.yaml, nur GET, nie ein Schlüssel, nie ein Pfad des Rechners."""
import http.client
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime import coder_lesen as cl
from sedra_runtime.uix_server import UIXHub, make_server

ARCH = Path(__file__).resolve().parents[2] / "architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC"


class Rein(unittest.TestCase):
    def test_sperrliste(self):
        for name in (".env", ".env.local", "local_config", "key.pem", "SERVER.KEY", "id_rsa", "secrets.yaml", "my_password.txt", "api_key.json", ".ssh", "cert.pfx"):
            self.assertTrue(cl.gesperrt(name), name)
        for name in ("main.py", "tokens.css", "README.md", "environment.md", "config", "keyboard.js"):
            self.assertFalse(cl.gesperrt(name), name)

    def test_pfad_gesperrt_wenn_ein_teil_gesperrt_ist(self):
        self.assertTrue(cl.pfad_gesperrt("local_config/evidence/evidence.db"))
        self.assertTrue(cl.pfad_gesperrt("src\\.env"))
        self.assertFalse(cl.pfad_gesperrt("src/main.py"))

    def test_adresse_zerlegen(self):
        self.assertEqual(cl.zerlege("/api/uix/coder/dateien/PRJ-1", cl.PRAEFIX_DATEIEN), ("PRJ-1", ""))
        self.assertEqual(cl.zerlege("/api/uix/coder/dateien/PRJ-1/src%2Fmain.py", cl.PRAEFIX_DATEIEN), ("PRJ-1", "src/main.py"))
        self.assertEqual(cl.zerlege("/api/uix/coder/datei/PRJ-1/a%20b.txt", cl.PRAEFIX_DATEI), ("PRJ-1", "a b.txt"))
        for schlecht in ("/api/uix/coder/dateien/", "/api/uix/coder/dateien/%2F", "/api/uix/coder/dateien/" + "x" * 80):
            with self.assertRaises(ValueError):
                cl.zerlege(schlecht, cl.PRAEFIX_DATEIEN)
        with self.assertRaises(ValueError):
            cl.zerlege("/api/uix/coder/datei/PRJ-1/" + "a" * 400, cl.PRAEFIX_DATEI)

    def test_projekte_ohne_workspace_pfad(self):
        out = cl.projekte([{"project_id": "PRJ-1", "display_name": "Alpha", "workspace_path": "C:/geheim/alpha"}])
        self.assertEqual(out["projekte"], [{"id": "PRJ-1", "name": "Alpha"}])
        self.assertNotIn("geheim", str(out))
        self.assertEqual(cl.projekte([])["quelle"], "fehlt")


class Hub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.pid = self.hub.new_project({"name": "Lesen"})["project_id"]
        ws = self.hub.runtime.filesystem_tool._resolve(self.hub.projects.get(self.pid)["workspace_path"])
        (ws / "src").mkdir()
        (ws / "src" / "main.py").write_text("print(1)\n", encoding="utf-8")
        (ws / "README.md").write_text("# Lesen\n", encoding="utf-8")
        (ws / ".env").write_text("TOKEN=geheim\n", encoding="utf-8")
        (ws / "secrets.txt").write_text("geheim\n", encoding="utf-8")
        (ws / "server.key").write_text("geheim\n", encoding="utf-8")
        (ws / "local_config").mkdir()
        (ws / "local_config" / "x.yaml").write_text("geheim: 1\n", encoding="utf-8")
        (ws / "blob.bin").write_bytes(b"\xff\xfe\x00\x01")

    def test_liste_ohne_gesperrte_eintraege(self):
        out = self.hub.coder_dateien(self.pid, "")
        namen = {e["name"] for e in out["eintraege"]}
        self.assertEqual(namen, {"src", "README.md", "blob.bin"})
        self.assertEqual(out["ausgeblendet"], 4)
        for verboten in (".env", "secrets", "server.key", "local_config"):
            self.assertNotIn(verboten, str(out))
        self.assertEqual([e["name"] for e in self.hub.coder_dateien(self.pid, "src")["eintraege"]], ["main.py"])

    def test_datei_text_binaer_und_gesperrt(self):
        self.assertEqual(self.hub.coder_datei(self.pid, "src/main.py")["inhalt"].strip(), "print(1)")
        self.assertTrue(self.hub.coder_datei(self.pid, "blob.bin")["binary"])
        for gesperrt in (".env", "secrets.txt", "server.key", "local_config/x.yaml"):
            with self.assertRaises(ValueError, msg=gesperrt):
                self.hub.coder_datei(self.pid, gesperrt)
        with self.assertRaises(ValueError):
            self.hub.coder_dateien(self.pid, "local_config")

    def test_ungueltige_pfade_und_projekte(self):
        for schlecht in ("..", "../x", "src/../..", "/etc", "C:/Windows"):
            with self.assertRaises(ValueError, msg=schlecht):
                self.hub.coder_dateien(self.pid, schlecht)
        with self.assertRaises(ValueError):
            self.hub.coder_datei(self.pid, "")
        with self.assertRaises(ValueError):
            self.hub.coder_dateien("PRJ-nope", "")


class Http(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.pid = self.hub.new_project({"name": "Http"})["project_id"]
        ws = self.hub.runtime.filesystem_tool._resolve(self.hub.projects.get(self.pid)["workspace_path"])
        (ws / "a.py").write_text("x = 1\n", encoding="utf-8")
        (ws / ".env").write_text("TOKEN=geheim\n", encoding="utf-8")
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port, self.token = server.server_port, url.split("#")[1]

    def get(self, pfad, werkzeug="coder", methode="GET"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            kopf = {"X-SEDRA-Token": self.token}
            if werkzeug:
                kopf["X-SEDRA-Tool"] = werkzeug
            c.request(methode, pfad, None, kopf)
            r = c.getresponse()
            return r.status, r.read().decode("utf-8")
        finally:
            c.close()

    def test_die_drei_routen_antworten(self):
        status, text = self.get("/api/uix/coder/projekte")
        self.assertEqual(status, 200)
        self.assertIn(self.pid, text)
        self.assertNotIn("workspace_path", text)
        status, text = self.get(f"/api/uix/coder/dateien/{self.pid}")
        self.assertEqual(status, 200)
        self.assertIn("a.py", text)
        self.assertNotIn(".env", text)
        status, text = self.get(f"/api/uix/coder/datei/{self.pid}/a.py")
        self.assertEqual(status, 200)
        self.assertIn("x = 1", text)

    def test_gesperrt_und_ungueltig_nur_als_kennwort(self):
        status, text = self.get(f"/api/uix/coder/datei/{self.pid}/.env")
        self.assertEqual((status, "geheim" in text), (400, False))
        self.assertIn("access_blocked", text)
        status, text = self.get(f"/api/uix/coder/datei/{self.pid}/a%2F..%2Fb")
        self.assertEqual(status, 403, "`..` im Pfad weist schon die Routenprüfung des Werkzeugs ab, noch vor dem Lese-Code")
        self.assertNotIn(self.tmp.name.replace("\\", "/"), text.replace("\\\\", "/"))
        self.assertEqual(self.get("/api/uix/coder/gibtsnicht")[0], 403, "nicht im Manifest: das Gate des Werkzeugs sagt nein")
        self.assertEqual(self.get("/api/uix/coder/gibtsnicht", werkzeug=None)[0], 404, "ohne Werkzeugkopf: die Route gibt es nicht")

    def test_das_werkzeug_darf_nur_seine_routen(self):
        self.assertEqual(self.get("/api/missions")[0], 403)
        self.assertEqual(self.get("/api/project/files")[0], 403)
        self.assertEqual(self.get("/api/uix/coder/projekte", werkzeug="gibtsnicht")[0], 403)

    def test_ohne_token_kein_zugang(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            c.request("GET", "/api/uix/coder/projekte")
            self.assertEqual(c.getresponse().status, 403)
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
