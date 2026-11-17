"""App Coder, R4 (Entscheidung E2): Git-Status nur lesen. Auswertung der Ausgabe, feste Form des Aufrufs, Sperrliste, Fehlerfälle,
ein echter Lauf in einem Wegwerf-Repository und die Adresse über HTTP."""
import http.client
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime import coder_lesen as cl
from sedra_runtime.uix_server import UIXHub, make_server

ARCH = Path(__file__).resolve().parents[2] / "architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC"
GIT = shutil.which("git")


class Rein(unittest.TestCase):
    def test_zeilen_zweig_und_codes(self):
        roh = "## main...origin/main [ahead 1]\x00 M src/a.py\x00?? neu.txt\x00 D weg.py\x00A  neu2.py\x00"
        zweig, e = cl.git_zeilen(roh)
        self.assertEqual(zweig, "main")
        self.assertEqual(e, [("M", "src/a.py"), ("U", "neu.txt"), ("M", "weg.py"), ("U", "neu2.py")])

    def test_zweig_ohne_commit_und_ohne_zweig(self):
        self.assertEqual(cl.git_zeilen("## No commits yet on master\x00")[0], "master")
        self.assertEqual(cl.git_zeilen("## HEAD (no branch)\x00")[0], "HEAD")

    def test_feste_form_ohne_schreibweg(self):
        self.assertIn("status", cl.GIT_ARGS)
        self.assertIn("--porcelain=v1", cl.GIT_ARGS)
        for schreibend in ("commit", "add", "checkout", "reset", "push", "stash", "clean"):
            self.assertNotIn(schreibend, cl.GIT_ARGS)
        self.assertIn("core.fsmonitor=false", cl.GIT_ARGS)

    def test_aenderungen_sperrliste_und_gekuerzt(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / ".git").mkdir()
            gesehen = {}

            def lauf(args, ordner):
                gesehen["args"] = args
                return "## main\x00 M a.py\x00?? .env\x00?? local_config/x.yaml\x00?? server.key\x00 M src\\b.py\x00"
            out = cl.aenderungen(t, lauf)
        self.assertEqual(gesehen["args"], cl.GIT_ARGS)
        self.assertEqual(out["quelle"], "ok")
        self.assertEqual([e["pfad"] for e in out["eintraege"]], ["a.py", "src/b.py"])
        self.assertEqual((out["anzahl"], out["ausgeblendet"], out["zweig"]), (2, 3, "main"))
        for verboten in (".env", "local_config", "server.key"):
            self.assertNotIn(verboten, json.dumps(out))

    def test_fehlerfaelle_nur_als_kennwort(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(cl.aenderungen(t)["grund"], "kein_git")
            (Path(t) / ".git").mkdir()

            def kaputt(args, ordner):
                raise RuntimeError(t)
            out = cl.aenderungen(t, kaputt)
            self.assertEqual((out["quelle"], out["grund"]), ("fehlt", "git_fehler"))
            self.assertNotIn(t, json.dumps(out))

            def zeit(args, ordner):
                raise subprocess.TimeoutExpired("git", 2)
            self.assertEqual(cl.aenderungen(t, zeit)["grund"], "git_zeit")

    def test_adresse(self):
        self.assertEqual(cl.zerlege("/api/uix/coder/aenderungen/PRJ-1", cl.PRAEFIX_AENDERUNGEN), ("PRJ-1", ""))


@unittest.skipUnless(GIT, "git nicht installiert")
class Echt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.pid = self.hub.new_project({"name": "Git"})["project_id"]
        self.ws = self.hub.runtime.filesystem_tool._resolve(self.hub.projects.get(self.pid)["workspace_path"])

    def git(self, *a):
        subprocess.run([GIT, "-C", str(self.ws), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True)

    def test_ohne_repository(self):
        self.assertEqual(self.hub.coder_aenderungen(self.pid)["grund"], "kein_git")

    def test_echtes_repository_aenderung_neu_und_gesperrt(self):
        self.git("init", "-q", "-b", "haupt")
        (self.ws / "a.py").write_text("x = 1\n", encoding="utf-8")
        self.git("add", "a.py")
        self.git("commit", "-q", "-m", "start")
        (self.ws / "a.py").write_text("x = 2\n", encoding="utf-8")
        (self.ws / "neu.txt").write_text("n\n", encoding="utf-8")
        (self.ws / ".env").write_text("TOKEN=geheim\n", encoding="utf-8")
        out = self.hub.coder_aenderungen(self.pid)
        self.assertEqual(out["quelle"], "ok")
        self.assertEqual(out["zweig"], "haupt")
        self.assertEqual({e["pfad"]: e["status"] for e in out["eintraege"]}, {"a.py": "M", "neu.txt": "U"})
        self.assertEqual(out["ausgeblendet"], 1)
        self.assertNotIn("geheim", json.dumps(out))
        # der Aufruf hat nichts verändert
        self.assertEqual((self.ws / "a.py").read_text(encoding="utf-8"), "x = 2\n")
        log = subprocess.run([GIT, "-C", str(self.ws), "log", "--oneline"], capture_output=True, text=True).stdout.splitlines()
        self.assertEqual(len(log), 1)

    def test_unbekanntes_projekt(self):
        with self.assertRaises(ValueError):
            self.hub.coder_aenderungen("PRJ-nope")


class Http(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.pid = self.hub.new_project({"name": "Http"})["project_id"]
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
            return r.status, r.read().decode("utf-8")
        finally:
            c.close()

    def test_route_antwortet_und_fremdes_werkzeug_nicht(self):
        status, text = self.get(f"/api/uix/coder/aenderungen/{self.pid}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["quelle"], "fehlt")
        self.assertEqual(self.get(f"/api/uix/coder/aenderungen/{self.pid}", werkzeug="anderes")[0], 403)
        self.assertEqual(self.get("/api/uix/coder/aenderungen/PRJ-nope")[0], 400)


if __name__ == "__main__":
    unittest.main()
