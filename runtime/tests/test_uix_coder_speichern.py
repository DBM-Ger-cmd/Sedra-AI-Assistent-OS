"""App Coder, Entscheidung E4: Speichern nur als Antrag an die Freigaben. Ohne Zustimmung des Captains wird nichts geschrieben,
die Freigabe gilt nur für diese Änderung an dieser Datei, einmal, und gesperrte Namen sind nie ein Ziel."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime import coder_speichern as cs
from sedra_runtime.uix_server import UIXHub, make_server

ARCH = Path(__file__).resolve().parents[2] / "architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC"


class Rein(unittest.TestCase):
    def test_pruefe(self):
        self.assertEqual(cs.pruefe({"projekt": "P-1", "pfad": "a/b.py", "inhalt": "x"}), ("P-1", "a/b.py", "x"))
        for schlecht, code in (({"projekt": "", "pfad": "a", "inhalt": "x"}, "invalid_project"),
                               ({"projekt": "P", "pfad": "", "inhalt": "x"}, "invalid_path"),
                               ({"projekt": "P", "pfad": "a", "inhalt": 5}, "invalid_content"),
                               ({"projekt": "P", "pfad": "a", "inhalt": "x" * (cs.INHALT_MAX + 1)}, "content_too_large"),
                               ({"projekt": "P", "pfad": ".env", "inhalt": "x"}, "access_blocked"),
                               ({"projekt": "P", "pfad": "local_config/x.yaml", "inhalt": "x"}, "access_blocked"),
                               ("kein dict", "invalid_payload")):
            with self.assertRaises(ValueError) as r:
                cs.pruefe(schlecht)
            self.assertEqual(str(r.exception), code)

    def test_zeilenenden_und_zaehlen(self):
        self.assertEqual(cs.zeilenenden("a\r\nb\r\n", "a\nc\n"), "a\r\nc\r\n")
        self.assertEqual(cs.zeilenenden("a\nb\n", "a\nc\n"), "a\nc\n")
        self.assertEqual(cs.zaehle("a\nb\n", "a\nc\nd\n"), (2, 1))

    def test_auftrag_gueltig(self):
        self.assertEqual(cs.auftrag_gueltig("M-ABC123"), "M-ABC123")
        for schlecht in ("", "../x", "a b", None, 5):
            with self.assertRaises(ValueError):
                cs.auftrag_gueltig(schlecht)


class Hub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.pid = self.hub.new_project({"name": "Speichern"})["project_id"]
        self.ws = self.hub.runtime.filesystem_tool._resolve(self.hub.projects.get(self.pid)["workspace_path"])
        self.ws.mkdir(parents=True, exist_ok=True)

    def antrag(self, pfad, inhalt):
        return self.hub.coder_speichern_antrag({"projekt": self.pid, "pfad": pfad, "inhalt": inhalt})

    def freigeben(self, res):
        self.hub.approve_gate({"mission_id": res["mission_id"], "gate_id": res["gate_id"]})

    def test_antrag_schreibt_nichts_und_wartet(self):
        (self.ws / "a.py").write_text("x = 1\n", encoding="utf-8")
        res = self.antrag("a.py", "x = 2\n")
        self.assertEqual((res["status"], res["neu"], res["hinzu"], res["weg"]), ("wartet", False, 1, 1))
        self.assertEqual((self.ws / "a.py").read_text(encoding="utf-8"), "x = 1\n")
        self.assertEqual(self.hub.coder_speichern_stand(res["mission_id"])["status"], "wartet")

    def test_ohne_zustimmung_geschieht_nichts(self):
        (self.ws / "a.py").write_text("x = 1\n", encoding="utf-8")
        res = self.antrag("a.py", "x = 2\n")
        with self.assertRaises(ValueError) as r:
            self.hub.coder_speichern_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual(str(r.exception), "captain_approval_required")
        self.assertEqual((self.ws / "a.py").read_text(encoding="utf-8"), "x = 1\n")

    def test_freigabe_schreibt_einmal(self):
        (self.ws / "a.py").write_text("x = 1\n", encoding="utf-8")
        res = self.antrag("a.py", "x = 2\n")
        self.freigeben(res)
        self.assertEqual(self.hub.coder_speichern_stand(res["mission_id"])["status"], "freigegeben")
        out = self.hub.coder_speichern_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual((out["status"], out["pfad"]), ("angewendet", "a.py"))
        self.assertEqual((self.ws / "a.py").read_text(encoding="utf-8"), "x = 2\n")
        self.assertEqual(self.hub.coder_speichern_stand(res["mission_id"])["status"], "angewendet")
        with self.assertRaises(ValueError) as r:
            self.hub.coder_speichern_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual(str(r.exception), "already_applied")

    def test_neue_datei_und_unterordner(self):
        res = self.antrag("neu/ordner/n.txt", "hallo\n")
        self.assertTrue(res["neu"])
        self.assertFalse((self.ws / "neu").exists())
        self.freigeben(res)
        self.hub.coder_speichern_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual((self.ws / "neu" / "ordner" / "n.txt").read_text(encoding="utf-8"), "hallo\n")

    def test_datei_geaendert_nach_antrag(self):
        (self.ws / "a.py").write_text("x = 1\n", encoding="utf-8")
        res = self.antrag("a.py", "x = 2\n")
        self.freigeben(res)
        (self.ws / "a.py").write_text("x = 99\n", encoding="utf-8")        # jemand anderes war schneller
        with self.assertRaises(ValueError) as r:
            self.hub.coder_speichern_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual(str(r.exception), "file_changed_repeat_request")
        self.assertEqual((self.ws / "a.py").read_text(encoding="utf-8"), "x = 99\n")

    def test_abgelehnt(self):
        (self.ws / "a.py").write_text("x = 1\n", encoding="utf-8")
        res = self.antrag("a.py", "x = 2\n")
        self.hub.reject_gate({"mission_id": res["mission_id"], "gate_id": res["gate_id"]})
        self.assertEqual(self.hub.coder_speichern_stand(res["mission_id"])["status"], "abgelehnt")
        with self.assertRaises(ValueError):
            self.hub.coder_speichern_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual((self.ws / "a.py").read_text(encoding="utf-8"), "x = 1\n")

    def test_zeilenenden_bleiben(self):
        (self.ws / "w.txt").write_bytes(b"a\r\nb\r\n")
        res = self.antrag("w.txt", "a\nc\n")
        self.freigeben(res)
        self.hub.coder_speichern_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual((self.ws / "w.txt").read_bytes(), b"a\r\nc\r\n")

    def test_abgewiesen(self):
        (self.ws / "a.py").write_text("x = 1\n", encoding="utf-8")
        (self.ws / "sub").mkdir()
        (self.ws / "bin.dat").write_bytes(b"\xff\xfe\x00\x01")
        for pfad, inhalt, code in ((".env", "T=1", "access_blocked"), ("a.py", "x = 1\n", "keine_aenderung"), ("sub", "x", "ziel_ist_ordner"),
                                   ("../ausser.txt", "x", "invalid_path"), ("/abs.txt", "x", "invalid_path"), ("C:\\x.txt", "x", "invalid_path"),
                                   ("bin.dat", "x", "datei_nicht_lesbar")):
            with self.assertRaises(ValueError, msg=pfad) as r:
                self.antrag(pfad, inhalt)
            self.assertEqual(str(r.exception), code, pfad)
        self.assertFalse((self.ws.parent / "ausser.txt").exists())

    def test_audit_ohne_dateitext(self):
        res = self.antrag("a.txt", "geheimer Inhalt\n")
        self.freigeben(res)
        self.hub.coder_speichern_anwenden({"mission_id": res["mission_id"]})
        zeilen = [z for z in self.hub.runtime.audit.path.read_text(encoding="utf-8").splitlines() if "CODER_SPEICHERN" in z]
        self.assertEqual(len(zeilen), 2)
        for z in zeilen:
            self.assertNotIn("geheimer Inhalt", z)

    def test_fremder_auftrag_ist_kein_antrag(self):
        m = self.hub.runtime.brain.create_mission("anderer Auftrag", None, "S1")
        with self.assertRaises(ValueError) as r:
            self.hub.coder_speichern_anwenden({"mission_id": m["identity"]["mission_id"]})
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

    def test_antrag_stand_und_fremdes_werkzeug(self):
        s, res = self.rufe("POST", "/api/uix/coder/speichern", {"projekt": self.pid, "pfad": "h.txt", "inhalt": "hi\n"})
        self.assertEqual((s, res["status"]), (200, "wartet"))
        s, st = self.rufe("GET", "/api/uix/coder/speichern/" + res["mission_id"])
        self.assertEqual((s, st["status"]), (200, "wartet"))
        self.assertEqual(self.rufe("POST", "/api/uix/coder/speichern", {"projekt": self.pid, "pfad": "h.txt", "inhalt": "x"}, werkzeug="anderes")[0], 403)
        self.assertEqual(self.rufe("POST", "/api/uix/coder/speichern", {"projekt": self.pid, "pfad": ".env", "inhalt": "x"})[0], 400)
        self.assertEqual(self.rufe("GET", "/api/uix/coder/speichern/M-nichtda")[0], 400)
        s, a = self.rufe("POST", "/api/uix/coder/speichern/anwenden", {"mission_id": res["mission_id"]})
        self.assertEqual((s, a["code"]), (400, "captain_approval_required"))


if __name__ == "__main__":
    unittest.main()


class Gross(unittest.TestCase):
    """Entscheidung des Captains 17.11.: Dateien bis 2 MB öffnen und als Antrag speichern."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.pid = self.hub.new_project({"name": "Gross"})["project_id"]
        self.ws = self.hub.runtime.filesystem_tool._resolve(self.hub.projects.get(self.pid)["workspace_path"])
        self.ws.mkdir(parents=True, exist_ok=True)

    def test_lesen_bis_2_mb_und_darueber_nicht(self):
        (self.ws / "mittel.txt").write_bytes(b"zeile\n" * 100_000)            # 600 KB
        out = self.hub.coder_datei(self.pid, "mittel.txt")
        self.assertEqual((out["quelle"], len(out["inhalt"])), ("ok", 600_000))
        (self.ws / "riesig.txt").write_bytes(b"x" * (cs.INHALT_MAX + 10))
        self.assertTrue(self.hub.coder_datei(self.pid, "riesig.txt").get("too_large"))
        # andere Ansichten der Harness behalten ihre 100-KB-Vorschau
        self.assertTrue(self.hub.project_file({"project_id": self.pid, "path": "mittel.txt"}).get("too_large"))

    def test_speichern_einer_grossen_datei_als_antrag(self):
        (self.ws / "gross.txt").write_bytes(b"alt\n" * 200_000)               # 800 KB
        neu = "neu\n" * 200_000
        res = self.hub.coder_speichern_antrag({"projekt": self.pid, "pfad": "gross.txt", "inhalt": neu})
        self.assertEqual(res["status"], "wartet")
        self.assertEqual((self.ws / "gross.txt").read_bytes()[:4], b"alt\n")
        self.hub.approve_gate({"mission_id": res["mission_id"], "gate_id": res["gate_id"]})
        self.hub.coder_speichern_anwenden({"mission_id": res["mission_id"]})
        self.assertEqual((self.ws / "gross.txt").read_bytes(), neu.encode("utf-8"))

    def test_ueber_2_mb_wird_abgewiesen(self):
        with self.assertRaises(ValueError) as r:
            self.hub.coder_speichern_antrag({"projekt": self.pid, "pfad": "x.txt", "inhalt": "ä" * (cs.INHALT_MAX // 2 + 1)})     # zählt in Bytes
        self.assertEqual(str(r.exception), "content_too_large")
