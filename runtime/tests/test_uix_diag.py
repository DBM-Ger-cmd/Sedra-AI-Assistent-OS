import importlib.util, json, shutil, subprocess, sys, tempfile, threading, unittest
from pathlib import Path
from types import SimpleNamespace

from guppi_runtime import uix_diag

SRC = Path(__file__).resolve().parents[1] / "src" / "guppi_runtime"
SPEC = Path(__file__).resolve().parents[1] / "benchmarks" / "devvm_specs" / "chat_diag.py"


def metric(value): return {"value": value, "unit": "GiB", "state": "valid"}


class FakeHardware:
    def __init__(self): self.changed, self.rebound = False, False
    def get_state(self, fresh=False): return {"gpus": [{"vram_used": metric(1.3), "vram_total": metric(12.0)}]}
    def active_profile(self):
        if self.changed and not self.rebound: raise RuntimeError("active_profile_hardware_changed")
        return {}
    def rebind_preview(self):
        if not self.changed or self.rebound: return {"needed": False}
        return {"needed": True, "active_profile": "custom-x", "previous_fingerprint": "aaa", "hardware_fingerprint": "bbb"}
    def rebind(self, plan): self.rebound = True; return {"rebound": ["active_state", "custom-x"]}


class Hub:
    LEASE_OWNER = "guppi-uix"

    def __init__(self, tmp):
        self.audit_path = Path(tmp) / "events.jsonl"
        self.hardware = FakeHardware()
        self.runtime = SimpleNamespace(hardware_manager=self.hardware, llama_server=SimpleNamespace(status=lambda: {"running": True, "model": "qwen3.6"}), audit=SimpleNamespace(path=self.audit_path))
        self.holder, self.gpu_token, self.lock = None, None, threading.Lock()
        self.lab = SimpleNamespace(holder=lambda: self.holder)

    def models_view(self): return {"recipes": [{"id": "coder.a", "model": "qwen", "enabled": True, "loaded": True}, {"id": "coder.b", "model": "gemma", "enabled": False, "loaded": False}]}

    def event(self, kind, payload=None, at="2026-10-13T08:00:00+00:00"):
        with open(self.audit_path, "a", encoding="utf-8") as f: f.write(json.dumps({"event_type": kind, "timestamp": at, "payload": payload or {}, "source": {"component": "x"}}) + "\n")


class UixDiagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.hub = Hub(self.tmp.name)

    def lines(self, text): return uix_diag.command(self.hub, {"text": text})["lines"]

    def test_the_view_reads_the_facts_and_judges_them(self):
        v = uix_diag.view(self.hub)
        self.assertEqual([r["id"] for r in v["rows"]], ["gpu", "lease", "model", "canary", "profile"])
        self.assertEqual(v["rows"][0]["detail"], "10.7 GB frei von 12.0 GB"); self.assertEqual(v["rows"][2]["detail"], "qwen3.6")
        self.assertEqual(v["rows"][1]["detail"], "frei")
        self.hub.holder = {"owner": "claude_quant", "purpose": None, "stale": False}      # a lease without a purpose must not break the view
        self.assertEqual(uix_diag.view(self.hub)["rows"][1]["detail"], "belegt von claude_quant")
        self.hub.hardware.changed = True
        v = uix_diag.view(self.hub)
        self.assertEqual((v["rows"][4]["state"], v["worst"]), ("bad", "bad")); self.assertIn("/rebind", v["rows"][4]["detail"])

    def test_status_models_help_and_unknown_commands(self):
        self.assertIn("Grafikkarte: 10.7 GB frei von 12.0 GB", self.lines("/status"))
        self.assertEqual(self.lines("/modelle"), ["● coder.a (qwen) - geladen", "○ coder.b (gemma) - aus"])
        self.assertTrue(any(l.startswith("/fehler") for l in self.lines("/hilfe")))
        self.assertIn("Unbekannter Befehl: /foo", self.lines("/foo")[0])
        for bad in ("hallo", "/plan x", 5, None):
            with self.assertRaises(ValueError): uix_diag.command(self.hub, {"text": bad})
        with self.assertRaises(ValueError): uix_diag.command(self.hub, None)

    def test_errors_are_listed_with_their_explanation_and_log_is_limited(self):
        self.hub.event("ROLE_RESOLUTION_FAILED", {"code": "hardware_pressure", "rejected": [{"capability_id": "c", "reason": "hardware_profile_changed"}]})
        self.hub.event("MISSION_STATE_CHANGED"); self.hub.event("RESOURCE_DENIED", {"reason": "vram_insufficient"})
        out = self.lines("/fehler")
        self.assertEqual(len(out), 2)
        self.assertIn("Hardware-Profil passt nicht mehr zu diesem PC", out[0]); self.assertIn("[hardware_profile_changed]", out[0])
        self.assertIn("Unbekannter Fehler", out[1]); self.assertIn("[vram_insufficient]", out[1])
        for _ in range(60): self.hub.event("MESSAGE_SENT")
        self.assertEqual(len(self.lines("/log 500")), 50); self.assertEqual(len(self.lines("/log")), 10)
        self.assertEqual(uix_diag.command(Hub(self.tmp.name + "/none"), {"text": "/fehler"})["lines"], ["Keine Fehler in den letzten Ereignissen."])

    def test_rebind_previews_first_and_changes_only_after_ja(self):
        self.assertEqual(self.lines("/rebind"), ["Das Hardware-Profil passt schon zu diesem PC, nichts zu binden."])
        self.hub.hardware.changed = True
        out = self.lines("/rebind")
        self.assertIn("Zum Binden: /rebind ja", out); self.assertFalse(self.hub.hardware.rebound)
        out = self.lines("/rebind ja")
        self.assertTrue(self.hub.hardware.rebound); self.assertIn("Neu gebunden: active_state, custom-x", out[-1])

    def test_explain_is_read_only_text_in_text_out(self):
        self.assertEqual(uix_diag.explain({"text": "gpu_lease_busy:claude:S0"})["code"], "gpu_lease_busy")
        for bad in (None, {}, {"text": 5}, {"text": "x" * 2001}):
            with self.assertRaises(ValueError): uix_diag.explain(bad)

    def test_the_installed_files_pass_the_hidden_tests_of_the_spec(self):
        loader = importlib.util.spec_from_file_location("chat_diag_spec", SPEC); spec = importlib.util.module_from_spec(loader); loader.loader.exec_module(spec)
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(SRC / "diag_core.py", d); shutil.copy(SRC / "uix" / "js" / "diag_panel.js", d)
            for stage in spec.STAGES:
                for name, source in {**stage.get("hidden", {}), **stage.get("host_hidden", {})}.items():
                    if name.endswith(".cjs") and not shutil.which("node"): continue
                    (Path(d) / name).write_text(source, encoding="utf-8")
                    run = subprocess.run([sys.executable, name] if name.endswith(".py") else ["node", name], cwd=d, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, name + run.stderr[-400:])


if __name__ == "__main__":
    unittest.main()
