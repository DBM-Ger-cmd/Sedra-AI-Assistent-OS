"""S0 integration (2026-10-12): the stored connection check per recipe, its fingerprint, the report devvm_build writes and --require-s0; and the BenchLoader no
longer forces flash attention off (with KV q8_0 recipes the server would not start)."""
import json
import sys
import env_skip
import tempfile
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.s0_status import fingerprint, save, status  # noqa: E402

SERVER = {"gguf": r"E:\m\Model-Q4.gguf", "kv_cache_type": "q8_0", "flash_attn": "on", "ubatch": 512, "n_cpu_moe": 28, "reasoning": "off"}


class S0Status(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)

    def test_missing_ok_failed_and_changed_settings(self):
        self.assertEqual(status(self.project, "coder.x", SERVER, "b11160")["state"], "missing")
        save(self.project, "coder.x", {"ok": True, "measured_at": "2026-10-12T08:15:00+00:00", "checks": []}, SERVER, "b11160")
        self.assertEqual(status(self.project, "coder.x", SERVER, "b11160"), {"recipe": "coder.x", "state": "ok", "measured_at": "2026-10-12T08:15:00+00:00"})
        self.assertEqual(status(self.project, "coder.x", {**SERVER, "flash_attn": "off"}, "b11160")["state"], "settings_changed")
        self.assertEqual(status(self.project, "coder.x", SERVER, "b11371")["state"], "settings_changed")
        save(self.project, "coder.y", {"ok": False, "checks": []}, SERVER, "b11160")
        self.assertEqual(status(self.project, "coder.y", SERVER, "b11160")["state"], "failed")

    def test_fingerprint_ignores_folder_and_non_connection_settings(self):
        self.assertEqual(fingerprint(SERVER, "b11160"), fingerprint({**SERVER, "gguf": r"D:\other\Model-Q4.gguf", "reasoning": "auto"}, "b11160"))
        self.assertNotEqual(fingerprint(SERVER, "b11160"), fingerprint({**SERVER, "kv_cache_type": "f16"}, "b11160"))

    @env_skip.needs_dulwich
    def test_devvm_build_reports_every_model_and_skips_jan_and_swe(self):
        import devvm_build
        from unittest import mock
        save(self.project, "coder.x", {"ok": True, "checks": []}, SERVER, "b11160")
        with mock.patch.object(devvm_build.bench.hunt, "model_spec", lambda key, project: {"server": dict(SERVER)}):
            rows = devvm_build.s0_report(self.project, {"coder": "coder.x", "reviewer": "swe", "planner": "coder.z"}, {}, "b11160")
            changed = devvm_build.s0_report(self.project, {"coder": "coder.x"}, {"flash_attn": "off"}, "b11160")
        self.assertEqual([(r["recipe"], r["state"]) for r in rows], [("coder.x", "ok"), ("coder.z", "missing"), ("swe", "not_a_recipe")])
        self.assertEqual(changed[0]["state"], "settings_changed")


class BenchLoaderFlashAttention(unittest.TestCase):
    @env_skip.needs_dulwich
    def test_the_recipe_decides_flash_attention(self):
        import devvm_agents_bench as bench

        class RT:
            endpoint = "http://x"
            def __init__(self): self.server = None
            def load_model(self, alias, **kw): self.server = kw["server"]
        loader = bench.BenchLoader.__new__(bench.BenchLoader)
        loader.runtime, loader.project, loader.parallel, loader.context = RT(), Path("."), 1, 32768
        loader.log = type("L", (), {"say": staticmethod(lambda s: None)})()
        loader.server_extra = {}
        loader.specs = {"m": {"alias": "m", "server": {"gguf": "m.gguf", "kv_cache_type": "q8_0", "flash_attn": "on"}, "context": 32768}}
        loader.sampling = {"m": {}}
        from unittest import mock
        with mock.patch.object(bench, "recipe_context_maximum", lambda project, alias, recipe_id=None: 32768):
            loader.load("m")
        self.assertEqual(loader.runtime.server["flash_attn"], "on")


if __name__ == "__main__":
    unittest.main()
