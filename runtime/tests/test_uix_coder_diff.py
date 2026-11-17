"""App Coder, Ausbau: Diff-Ansicht. Server: Stand der Datei im letzten Commit (feste Form, nur lesen, Sperrliste); Oberfläche: Route im Manifest."""
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
    def test_abgewiesen(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / ".git").mkdir()
            for pfad, code in (("", "invalid_path"), ("../x", "invalid_path"), ("a/../b", "invalid_path"), ("C:x", "invalid_path"), (".env", "access_blocked"), ("local_config/a.yaml", "access_blocked")):
                with self.assertRaises(ValueError, msg=pfad) as r:
                    cl.original(t, pfad)
                self.assertEqual(str(r.exception), code, pfad)

    def test_feste_form_und_antworten(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(cl.original(t, "a.py")["grund"], "kein_git")
            (Path(t) / ".git").mkdir()
            gesehen = {}

            def lauf(args, ordner):
                gesehen["args"] = args
                return b"x = 1\r\ny = 2\r\n"
            out = cl.original(t, "src\\a.py", lauf)
            self.assertEqual(gesehen["args"][-2:], ["show", "HEAD:src/a.py"])
            for schreibend in ("commit", "add", "checkout", "reset", "push"):
                self.assertNotIn(schreibend, gesehen["args"])
            self.assertEqual((out["quelle"], out["inhalt"], out["pfad"]), ("ok", "x = 1\ny = 2\n", "src/a.py"))
            self.assertEqual(cl.original(t, "a", lambda a, o: b"x" * (cl.ORIGINAL_MAX + 1))["grund"], "zu_gross")
            self.assertEqual(cl.original(t, "a", lambda a, o: b"\xff\xfe\x00")["grund"], "binaer")

            def neu(a, o):
                raise LookupError(t)
            out = cl.original(t, "a", neu)
            self.assertEqual(out["grund"], "neu")
            self.assertNotIn(t, json.dumps(out))

            def kaputt(a, o):
                raise RuntimeError(t)
            self.assertNotIn(t, json.dumps(cl.original(t, "a", kaputt)))

            def zeit(a, o):
                raise subprocess.TimeoutExpired("git", 2)
            self.assertEqual(cl.original(t, "a", zeit)["grund"], "git_zeit")


@unittest.skipUnless(GIT, "git nicht installiert")
class Echt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.pid = self.hub.new_project({"name": "Diff"})["project_id"]
        self.ws = self.hub.runtime.filesystem_tool._resolve(self.hub.projects.get(self.pid)["workspace_path"])
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port, self.token = server.server_port, url.split("#")[1]

    def git(self, *a):
        subprocess.run([GIT, "-C", str(self.ws), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True)

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

    def test_echtes_repository(self):
        self.git("init", "-q", "-b", "haupt")
        (self.ws / "src").mkdir()
        (self.ws / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "s")
        (self.ws / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
        (self.ws / "neu.txt").write_text("n\n", encoding="utf-8")
        s, out = self.get(f"/api/uix/coder/original/{self.pid}/src%2Fa.py")
        self.assertEqual((s, out["quelle"], out["inhalt"]), (200, "ok", "x = 1\n"))
        s, out = self.get(f"/api/uix/coder/original/{self.pid}/neu.txt")
        self.assertEqual((s, out["quelle"], out["grund"]), (200, "fehlt", "neu"))
        self.assertEqual(self.get(f"/api/uix/coder/original/{self.pid}/.env")[0], 400)
        self.assertEqual(self.get(f"/api/uix/coder/original/{self.pid}/a.py", werkzeug="anderes")[0], 403)
        self.assertEqual((self.ws / "src" / "a.py").read_text(encoding="utf-8"), "x = 2\n")


if __name__ == "__main__":
    unittest.main()
