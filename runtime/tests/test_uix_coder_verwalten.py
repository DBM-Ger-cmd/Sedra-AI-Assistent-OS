"""App Coder, Ausbau: Dateiverwaltung nur als Antrag (neuer Ordner, Umbenennen, Löschen). Ohne Zustimmung des Captains geschieht nichts,
die Freigabe gilt einmal und nur für diese Änderung; Gelöscht werden nur Dateien und leere Ordner; geschützte und gesperrte Namen sind nie ein Ziel."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime import coder_verwalten as cv
from sedra_runtime.uix_server import UIXHub, make_server

ARCH = Path(__file__).resolve().parents[2] / "architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC"


class Rein(unittest.TestCase):
    def test_pruefe(self):
        self.assertEqual(cv.pruefe({"art": "ordner", "projekt": "P-1", "pfad": "a/b"}), ("ordner", "P-1", "a/b", None))
        self.assertEqual(cv.pruefe({"art": "umbenennen", "projekt": "P", "pfad": "a.py", "ziel": "b.py"}), ("umbenennen", "P", "a.py", "b.py"))
        for schlecht, code in (({"art": "x", "projekt": "P", "pfad": "a"}, "invalid_kind"),
                               ({"art": "loeschen", "projekt": "", "pfad": "a"}, "invalid_project"),
                               ({"art": "loeschen", "projekt": "P", "pfad": "../a"}, "invalid_path"),
                               ({"art": "loeschen", "projekt": "P", "pfad": "/a"}, "invalid_path"),
                               ({"art": "loeschen", "projekt": "P", "pfad": "C:a"}, "invalid_path"),
                               ({"art": "loeschen", "projekt": "P", "pfad": ".env"}, "access_blocked"),
                               ({"art": "loeschen", "projekt": "P", "pfad": "x/.git/config"}, "access_blocked"),
                               ({"art": "loeschen", "projekt": "P", "pfad": "node_modules"}, "access_blocked"),
                               ({"art": "umbenennen", "projekt": "P", "pfad": "a", "ziel": "local_config/x"}, "access_blocked"),
                               ({"art": "umbenennen", "projekt": "P", "pfad": "a", "ziel": "a"}, "keine_aenderung"),
                               ({"art": "umbenennen", "projekt": "P", "pfad": "a"}, "invalid_path"),
                               ("kein dict", "invalid_payload")):
            with self.assertRaises(ValueError, msg=str(schlecht)) as r:
                cv.pruefe(schlecht)
            self.assertEqual(str(r.exception), code)


class Hub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.pid = self.hub.new_project({"name": "Verwalten"})["project_id"]
        self.ws = self.hub.runtime.filesystem_tool._resolve(self.hub.projects.get(self.pid)["workspace_path"])
        self.ws.mkdir(parents=True, exist_ok=True)

    def antrag(self, art, pfad, ziel=None):
        return self.hub.coder_verwalten_antrag({"projekt": self.pid, "art": art, "pfad": pfad, "ziel": ziel})

    def freigeben(self, res):
        self.hub.approve_gate({"mission_id": res["mission_id"], "gate_id": res["gate_id"]})

    def fertig(self, res):
        self.freigeben(res)
        return self.hub.coder_verwalten_anwenden({"mission_id": res["mission_id"]})

    def test_umbenennen_erst_nach_zustimmung(self):
        (self.ws / "a.py").write_text("x\n", encoding="utf-8")
        res = self.antrag("umbenennen", "a.py", "sub/b.py")
        self.assertEqual(res["status"], "wartet")
        self.assertTrue((self.ws / "a.py").exists() and not (self.ws / "sub").exists())
        with self.assertRaises(ValueError) as r:
            self.hub.coder_verwalten_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual(str(r.exception), "captain_approval_required")
        self.assertEqual(self.hub.coder_speichern_stand(res["mission_id"])["status"], "wartet")
        out = self.fertig(res)
        self.assertEqual((out["status"], out["art"]), ("angewendet", "umbenennen"))
        self.assertFalse((self.ws / "a.py").exists())
        self.assertEqual((self.ws / "sub" / "b.py").read_text(encoding="utf-8"), "x\n")
        self.assertEqual(self.hub.coder_speichern_stand(res["mission_id"])["status"], "angewendet")
        with self.assertRaises(ValueError) as r:
            self.hub.coder_verwalten_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual(str(r.exception), "already_applied")

    def test_loeschen_datei_und_leerer_ordner(self):
        (self.ws / "weg.txt").write_text("x\n", encoding="utf-8")
        (self.ws / "leer").mkdir()
        self.fertig(self.antrag("loeschen", "weg.txt"))
        self.fertig(self.antrag("loeschen", "leer"))
        self.assertFalse((self.ws / "weg.txt").exists() or (self.ws / "leer").exists())

    def test_nie_ein_ganzer_baum(self):
        (self.ws / "voll").mkdir()
        (self.ws / "voll" / "x.txt").write_text("x\n", encoding="utf-8")
        with self.assertRaises(ValueError) as r:
            self.antrag("loeschen", "voll")
        self.assertEqual(str(r.exception), "ordner_nicht_leer")
        self.assertTrue((self.ws / "voll" / "x.txt").exists())

    def test_ordner_anlegen(self):
        res = self.antrag("ordner", "neu/tief")
        self.assertFalse((self.ws / "neu").exists())
        self.fertig(res)
        self.assertTrue((self.ws / "neu" / "tief").is_dir())

    def test_zustand_geaendert_nach_antrag(self):
        (self.ws / "a.py").write_text("x\n", encoding="utf-8")
        res = self.antrag("loeschen", "a.py")
        self.freigeben(res)
        (self.ws / "a.py").write_text("ganz anders\n", encoding="utf-8")
        with self.assertRaises(ValueError) as r:
            self.hub.coder_verwalten_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual(str(r.exception), "file_changed_repeat_request")
        self.assertTrue((self.ws / "a.py").exists())

    def test_abgelehnt(self):
        (self.ws / "a.py").write_text("x\n", encoding="utf-8")
        res = self.antrag("loeschen", "a.py")
        self.hub.reject_gate({"mission_id": res["mission_id"], "gate_id": res["gate_id"]})
        self.assertEqual(self.hub.coder_speichern_stand(res["mission_id"])["status"], "abgelehnt")
        with self.assertRaises(ValueError):
            self.hub.coder_verwalten_anwenden({"mission_id": res["mission_id"]})
        self.assertTrue((self.ws / "a.py").exists())

    def test_abgewiesen(self):
        (self.ws / "a.py").write_text("x\n", encoding="utf-8")
        (self.ws / "b.py").write_text("y\n", encoding="utf-8")
        for art, pfad, ziel, code in (("loeschen", "fehlt.txt", None, "nicht_gefunden"), ("umbenennen", "fehlt.txt", "n.txt", "nicht_gefunden"),
                                      ("umbenennen", "a.py", "b.py", "ziel_existiert"), ("ordner", "a.py", None, "ziel_existiert"),
                                      ("loeschen", ".env", None, "access_blocked"), ("loeschen", ".git", None, "access_blocked")):
            with self.assertRaises(ValueError, msg=pfad) as r:
                self.antrag(art, pfad, ziel)
            self.assertEqual(str(r.exception), code, pfad)
        self.assertEqual((self.ws / "b.py").read_text(encoding="utf-8"), "y\n")

    def test_audit_nur_namen(self):
        (self.ws / "a.py").write_text("geheimer Inhalt\n", encoding="utf-8")
        self.fertig(self.antrag("umbenennen", "a.py", "c.py"))
        zeilen = [z for z in self.hub.runtime.audit.path.read_text(encoding="utf-8").splitlines() if "CODER_VERWALTEN" in z]
        self.assertEqual(len(zeilen), 2)
        for z in zeilen:
            self.assertNotIn("geheimer Inhalt", z)

    def test_fremder_auftrag(self):
        m = self.hub.runtime.brain.create_mission("anderer Auftrag", None, "S1")
        with self.assertRaises(ValueError) as r:
            self.hub.coder_verwalten_anwenden({"mission_id": m["identity"]["mission_id"]})
        self.assertEqual(str(r.exception), "not_a_matching_request")


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

    def test_route(self):
        s, res = self.rufe("POST", "/api/uix/coder/verwalten", {"projekt": self.pid, "art": "ordner", "pfad": "neu"})
        self.assertEqual((s, res["status"]), (200, "wartet"))
        s, st = self.rufe("GET", "/api/uix/coder/speichern/" + res["mission_id"])
        self.assertEqual((s, st["status"], st["art"]), (200, "wartet", "ordner"))
        self.assertEqual(self.rufe("POST", "/api/uix/coder/verwalten", {"projekt": self.pid, "art": "ordner", "pfad": "x"}, werkzeug="anderes")[0], 403)
        self.assertEqual(self.rufe("POST", "/api/uix/coder/verwalten", {"projekt": self.pid, "art": "loeschen", "pfad": ".env"})[0], 400)
        s, a = self.rufe("POST", "/api/uix/coder/verwalten/anwenden", {"mission_id": res["mission_id"]})
        self.assertEqual((s, a["code"]), (400, "captain_approval_required"))


if __name__ == "__main__":
    unittest.main()
