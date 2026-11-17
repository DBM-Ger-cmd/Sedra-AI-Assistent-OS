"""App Coder: Agenten-Anbindung. Eingabe, Dateikontext mit Sperrliste, lokale und Cloud-Wege (ohne echtes Modell, mit Attrappen),
Audit ohne Text, nur Antworten (kein Schreibweg)."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime import coder_agent as ca
from sedra_runtime.uix_server import UIXHub, make_server

ARCH = Path(__file__).resolve().parents[2] / "architecture/SEDRA_Architecture_v1.17_RUNTIME_SYNC"


class Rein(unittest.TestCase):
    def gut(self, **kw):
        p = {"projekt": "PRJ-1", "text": "Was macht main?", "dateien": ["src/main.py"]}
        p.update(kw)
        return p

    def test_pruefe_normalfall_und_standard(self):
        p = ca.pruefe(self.gut())
        self.assertEqual((p["route"], p["modus"], p["dateien"]), ("lokal", "plan", ["src/main.py"]))

    def test_pruefe_lehnt_schlechtes_ab(self):
        for kw in ({"text": ""}, {"text": "x" * 4001}, {"route": "mond"}, {"modus": "zerstoere"}, {"projekt": "a/b"}, {"projekt": ""},
                   {"dateien": ["a"] * 6}, {"dateien": [1]}, {"dateien": "a"}, {"history": [{"role": "system", "content": "x"}]},
                   {"route": "cloud"}, {"route": "cloud", "provider": "NVIDIA!", "model": "m"}, {"route": "cloud", "provider": "nvidia", "model": ""}):
            with self.assertRaises(ValueError, msg=str(kw)):
                ca.pruefe(self.gut(**kw))
        with self.assertRaises(ValueError):
            ca.pruefe("kein dict")

    def test_kontext_sperrliste_binaer_gross_kuerzung(self):
        daten = {"a.py": {"inhalt": "x" * 9000}, "b.bin": {"binary": True}, "c.txt": {"too_large": True}, "d.md": {"inhalt": "hallo"}}

        def lese(pfad):
            if pfad == "weg.py":
                raise ValueError("nope")
            return daten[pfad]
        text, belegt, aus = ca.kontext([".env", "a.py", "b.bin", "c.txt", "d.md", "weg.py", "local_config/x.yaml"], lese)
        self.assertEqual([b["pfad"] for b in belegt], ["a.py", "d.md"])
        self.assertTrue(belegt[0]["gekuerzt"])
        self.assertEqual(belegt[0]["zeichen"], ca.DATEI_ZEICHEN)
        self.assertEqual({a["pfad"]: a["grund"] for a in aus},
                         {".env": "gesperrt", "b.bin": "binaer", "c.txt": "zu_gross", "weg.py": "nicht_lesbar", "local_config/x.yaml": "gesperrt"})
        self.assertIn("hallo", text)

    def test_kontext_gesamtgrenze(self):
        _, belegt, aus = ca.kontext(["a", "b", "c", "d", "e"], lambda p: {"inhalt": "y" * ca.DATEI_ZEICHEN})
        self.assertLessEqual(sum(b["zeichen"] for b in belegt), ca.GESAMT_ZEICHEN)
        self.assertTrue(aus and all(a["grund"] == "kein_platz" for a in aus))

    def test_nachrichten_form(self):
        p = ca.pruefe(self.gut(modus="act", history=[{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]))
        m = ca.nachrichten(p, "--- Datei: x ---\ncode")
        self.assertEqual([x["role"] for x in m], ["system", "user", "assistant", "user"])
        self.assertIn("Modus Act", m[0]["content"])
        self.assertTrue(m[-1]["content"].endswith("Was macht main?"))
        self.assertIn("code", m[-1]["content"])

    def test_modelle_nur_bereite_und_keine_schluessel(self):
        view = {"enabled": True, "providers": [
            {"id": "nvidia", "enabled": True, "status": "bereit", "default_model": "m1", "key": "gespeichert"},
            {"id": "openai", "enabled": True, "status": "nicht bereit", "default_model": "m2"},
            {"id": "aus", "enabled": False, "status": "aus", "default_model": "m3"}]}
        out = ca.modelle(view, [{"identifier": "qwen"}])
        self.assertEqual(out["cloud"]["anbieter"], [{"id": "nvidia", "modell": "m1"}])
        self.assertEqual(out["lokal"], {"bereit": True, "modell": "qwen"})
        self.assertNotIn("gespeichert", json.dumps(out))
        self.assertEqual(ca.modelle({"enabled": False, "providers": view["providers"]}, [])["cloud"], {"an": False, "anbieter": []})
        self.assertFalse(ca.modelle(view, [])["lokal"]["bereit"])


class FalschesModell:
    """Attrappe für rt.control: merkt sich die Anfragen, antwortet fest."""

    def __init__(self, antwort="Antwort aus dem Test"):
        self.antwort, self.gesehen = antwort, []

    def execute(self, mission, request):
        self.gesehen.append(request)
        return {"status": "completed", "model_result": {"content": self.antwort}}


class Hub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.pid = self.hub.new_project({"name": "Agent"})["project_id"]
        ws = self.hub.runtime.filesystem_tool._resolve(self.hub.projects.get(self.pid)["workspace_path"])
        (ws / "main.py").write_text("GEHEIME_FRAGE = 1\nprint(GEHEIME_FRAGE)\n", encoding="utf-8")
        (ws / ".env").write_text("TOKEN=geheim\n", encoding="utf-8")
        self.rt = self.hub.runtime

    def modell_da(self, antwort="Antwort aus dem Test"):
        class Server:
            def loaded_models(self):
                return [{"identifier": "test-modell"}]
        self.rt.llama_server = Server()
        self.rt.control = FalschesModell(antwort)
        return self.rt.control

    def frage(self, **kw):
        p = {"projekt": self.pid, "text": "Erkläre main", "dateien": ["main.py", ".env"]}
        p.update(kw)
        return self.hub.coder_agent(p)

    def test_lokal_antwort_kontext_und_sperrliste(self):
        ctl = self.modell_da()
        out = self.frage()
        self.assertEqual((out["status"], out["antwort"], out["modell"], out["route"]), ("completed", "Antwort aus dem Test", "test-modell", "lokal"))
        self.assertEqual([k["pfad"] for k in out["kontext"]], ["main.py"])
        self.assertEqual(out["ausgelassen"], [{"pfad": ".env", "grund": "gesperrt"}])
        gesendet = json.dumps(ctl.gesehen[0]["messages"])
        self.assertIn("GEHEIME_FRAGE", gesendet)
        self.assertNotIn("TOKEN=geheim", gesendet)
        self.assertNotIn("tools", ctl.gesehen[0], "das Modell bekommt keine Werkzeuge: nur Text")

    def test_kein_modell_geladen(self):
        class Leer:
            def loaded_models(self):
                return []
        self.rt.llama_server = Leer()
        self.assertEqual(self.frage()["status"], "no_model")

    def test_leere_antwort_ist_ein_fehler(self):
        self.modell_da("   ")
        out = self.frage()
        self.assertEqual((out["status"], out["gruende"]), ("failed", ["model_answer_empty"]))

    def test_cloud_unbekannter_anbieter(self):
        with self.assertRaises(ValueError):
            self.frage(route="cloud", provider="gibtsnicht", model="m")

    def test_cloud_weg_gibt_text_zurueck_und_inhaltsschutz_stoppt(self):
        from sedra_runtime import labor
        gesehen = {}

        def falsch(cfg, pid, model, messages, environ=None, key_store=None, audit=None, max_tokens=None):
            gesehen.update(pid=pid, model=model, messages=messages, max_tokens=max_tokens)
            return {"status": "completed", "reply": "Cloud sagt hallo", "provider": pid, "model": model}
        alt = labor.cloud_chat
        labor.cloud_chat = falsch
        self.addCleanup(setattr, labor, "cloud_chat", alt)
        self.hub._labor_provider = lambda payload: ({}, payload["provider"])
        out = self.frage(route="cloud", provider="nvidia", model="m1")
        self.assertEqual((out["status"], out["antwort"], out["anbieter"]), ("completed", "Cloud sagt hallo", "nvidia"))
        self.assertNotIn("TOKEN=geheim", json.dumps(gesehen["messages"]))
        self.assertEqual(gesehen["max_tokens"], ca.ANTWORT_TOKEN)
        labor.cloud_chat = lambda *a, **k: {"status": "blocked", "reasons": ["SG_PERSONAL_CLOUD"], "provider": "nvidia", "model": "m1"}
        out = self.frage(route="cloud", provider="nvidia", model="m1")
        self.assertEqual((out["status"], out["gruende"]), ("blocked", ["SG_PERSONAL_CLOUD"]))
        self.assertNotIn("antwort", out)

    def test_audit_ohne_frage_und_dateitext(self):
        self.modell_da()
        self.frage(text="Sehr eigene Frage XYZ")
        log = Path(self.rt.audit.path).read_text(encoding="utf-8")
        zeilen = [z for z in log.splitlines() if "CODER_AGENT" in z]
        self.assertEqual(len(zeilen), 1)
        for verboten in ("XYZ", "GEHEIME_FRAGE", "Antwort aus dem Test"):
            self.assertNotIn(verboten, zeilen[0])

    def test_modelle_zeigt_lokal(self):
        self.modell_da()
        out = self.hub.coder_modelle()
        self.assertEqual(out["lokal"]["modell"], "test-modell")


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

    def senden(self, methode, pfad, body=None, werkzeug="coder"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            kopf = {"X-SEDRA-Token": self.token, "Content-Type": "application/json"}
            if werkzeug:
                kopf["X-SEDRA-Tool"] = werkzeug
            c.request(methode, pfad, json.dumps(body) if body is not None else None, kopf)
            r = c.getresponse()
            return r.status, r.read().decode("utf-8")
        finally:
            c.close()

    def test_modelle_get_und_agent_post_ueber_das_gate(self):
        status, text = self.senden("GET", "/api/uix/coder/modelle")
        self.assertEqual(status, 200)
        self.assertIn("lokal", text)
        status, text = self.senden("POST", "/api/uix/coder/agent", {"projekt": self.pid, "text": "hi", "dateien": []})
        self.assertEqual(status, 200)
        self.assertIn(json.loads(text)["status"], ("no_model", "completed", "failed"))

    def test_fremdes_werkzeug_und_schlechte_eingabe(self):
        self.assertEqual(self.senden("POST", "/api/uix/coder/agent", {"projekt": self.pid, "text": "hi"}, werkzeug="anderes")[0], 403)
        status, _ = self.senden("POST", "/api/uix/coder/agent", {"projekt": self.pid, "text": ""})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
