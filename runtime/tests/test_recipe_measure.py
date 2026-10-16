import unittest

from guppi_runtime.recipe_measure import MeasureError, apply_measurements, filler_prompt, measure_recipe, suggest
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests


class FakeRuntime:
    """Stands in for LlamaServerRuntime: VRAM = weights + 0.025 GiB per 1k tokens of window; `fail_at` makes one tier fail to load."""
    def __init__(self, gpu, fail_at=None, applied=None, preloaded=False):
        self.gpu, self.fail_at, self.applied, self.info, self.preloaded = gpu, fail_at, applied or {}, None, preloaded
        self.loads = []

    def loaded_models(self):
        return [self.info] if self.info else ([{"modelKey": "other"}] if self.preloaded else [])

    def load_model(self, key, *, context_length=None, gpu=None, identifier=None, parallel=None, server=None):
        self.loads.append((key, context_length, parallel, server))
        if context_length == self.fail_at:
            raise RuntimeError("out of memory")
        self.gpu.used = 0.5 + 5.0 + 0.025 * context_length / 1000
        self.info = {"contextLength": self.applied.get(context_length, context_length), "spec_type": "none", "kv_cache_type": server.get("kv_cache_type")}

    def unload_model(self, model_key=None, *, all_models=False):
        self.info = None
        self.gpu.used = 0.5


class Gpu:
    used = 0.5


def recipe(**extra):
    return {"id": "r1", "model": "m", "profile": {"context": {"tiers": [8192, 16384, 32768]}, "server": {"gguf": "x.gguf", "kv_cache_type": "q8_0", "mtp": False}}, **extra}


def run(rt, gpu, **kw):
    return measure_recipe(recipe(), rt, lambda: gpu.used, sleep=lambda s: None, **kw)


class MeasureTests(unittest.TestCase):
    def test_measures_every_tier_and_fits_the_kv_rate(self):
        gpu = Gpu(); rt = FakeRuntime(gpu)
        result = run(rt, gpu)
        self.assertEqual([r["context"] for r in result["rows"]], [8192, 16384, 32768])
        self.assertEqual([r["status"] for r in result["rows"]], ["ok"] * 3)
        s = result["suggested"]
        self.assertEqual(s["measured_context"], 8192)
        self.assertEqual(s["measured_vram_gb"], round(5.0 + 0.025 * 8.192 + 0.3, 2))
        self.assertAlmostEqual(s["kv_cache_gb_per_1k_tokens"], 0.025, places=3)
        self.assertEqual(s["measured_maximum"], 32768)
        self.assertEqual(result["baseline_gb"], 0.5)
        self.assertIsNone(rt.info)                                   # unloaded again

    def test_uses_the_recipe_profile_one_slot(self):
        gpu = Gpu(); rt = FakeRuntime(gpu)
        run(rt, gpu, tiers=[8192])
        key, ctx, parallel, server = rt.loads[0]
        self.assertEqual((key, ctx, parallel, server["gguf"]), ("m", 8192, 1, "x.gguf"))

    def test_probe_growth_widens_the_margin(self):
        gpu = Gpu(); rt = FakeRuntime(gpu)
        def generate(alias, tokens):
            gpu.used += 0.4                                          # compute buffers grew while generating
            return {"prompt_tokens": tokens}
        result = run(rt, gpu, generate=generate, tiers=[8192])
        row = result["rows"][0]
        self.assertEqual(row["probe_growth_gb"], 0.4)
        self.assertEqual(result["suggested"]["margin_gb"], 0.6)       # 1.5 x growth beats the default 0.3
        self.assertEqual(result["suggested"]["measured_vram_gb"], round(row["vram_after_probe_gb"] + 0.6, 2))

    def test_stops_at_the_first_tier_that_does_not_load(self):
        gpu = Gpu(); rt = FakeRuntime(gpu, fail_at=32768)
        result = run(rt, gpu)
        self.assertEqual([r["status"] for r in result["rows"]], ["ok", "ok", "load_failed"])
        self.assertEqual(result["suggested"]["measured_maximum"], 16384)
        self.assertIn("32768", result["stopped"])

    def test_applied_context_mismatch_is_not_a_good_row(self):
        gpu = Gpu(); rt = FakeRuntime(gpu, applied={16384: 8192})
        result = run(rt, gpu)
        self.assertEqual(result["rows"][1]["status"], "context_mismatch")
        self.assertEqual(result["suggested"]["measured_maximum"], 8192)

    def test_refuses_when_the_gpu_is_not_idle(self):
        gpu = Gpu(); gpu.used = 3.0
        with self.assertRaises(MeasureError) as cm:
            run(FakeRuntime(gpu), gpu)
        self.assertEqual(cm.exception.code, "gpu_not_idle")

    def test_refuses_when_a_model_is_already_loaded(self):
        gpu = Gpu()
        with self.assertRaises(MeasureError) as cm:
            run(FakeRuntime(gpu, preloaded=True), gpu)
        self.assertEqual(cm.exception.code, "model_already_loaded")

    def test_refuses_a_recipe_without_server_profile(self):
        gpu = Gpu()
        with self.assertRaises(MeasureError) as cm:
            measure_recipe({"id": "r", "profile": {}}, FakeRuntime(gpu), lambda: gpu.used, sleep=lambda s: None)
        self.assertEqual(cm.exception.code, "recipe_has_no_server_profile")

    def test_single_tier_gives_no_kv_rate(self):
        self.assertNotIn("kv_cache_gb_per_1k_tokens", suggest([{"context": 8192, "status": "ok", "vram_idle_gb": 5.5}]))
        self.assertEqual(suggest([{"context": 8192, "status": "load_failed"}]), {})

    def test_filler_prompt_has_the_requested_size_and_does_not_repeat(self):
        text = filler_prompt(2600)
        self.assertEqual(len(text.split("\n")), 100)
        self.assertEqual(len(set(text.split("\n"))), 100)


FILE = """# header
role_routing:
  capabilities:
    - id: a
      measured_vram_gb: 6.2        # old comment
      measured_context: 8192
      kv_cache_gb_per_1k_tokens: 0.026   # old
      model: keep-a
    - id: b
      measured_vram_gb: 7.7
      measured_context: 8192
      kv_cache_gb_per_1k_tokens: 0.017
"""


class ApplyTests(unittest.TestCase):
    S = {"measured_context": 8192, "measured_vram_gb": 6.05, "kv_cache_gb_per_1k_tokens": 0.031}

    def test_changes_only_the_named_recipe(self):
        new = apply_measurements(FILE, "a", self.S, today="2026-10-02")
        self.assertIn("measured_vram_gb: 6.05        # measured 2026-10-02 (recipe_measure)", new)
        self.assertIn("kv_cache_gb_per_1k_tokens: 0.031", new)
        self.assertIn("      measured_vram_gb: 7.7\n", new)              # recipe b untouched
        self.assertIn("model: keep-a", new)
        self.assertTrue(new.startswith("# header"))
        self.assertNotIn("old comment", new)

    def test_result_stays_valid_yaml_with_the_new_numbers(self):
        import yaml
        new = apply_measurements(FILE, "b", self.S, today="2026-10-02")
        caps = {c["id"]: c for c in yaml.safe_load(new)["role_routing"]["capabilities"]}
        self.assertEqual(caps["b"]["measured_vram_gb"], 6.05)
        self.assertEqual(caps["a"]["measured_vram_gb"], 6.2)

    def test_unknown_recipe_or_missing_line_raises(self):
        with self.assertRaises(MeasureError) as cm:
            apply_measurements(FILE, "zzz", self.S, today="x")
        self.assertEqual(cm.exception.code, "recipe_not_in_file")
        with self.assertRaises(MeasureError) as cm:
            apply_measurements("    - id: c\n      model: m\n", "c", self.S, today="x")
        self.assertEqual(cm.exception.code, "recipe_line_missing")

    def test_maximum_and_tiers_are_never_written(self):
        new = apply_measurements(FILE, "a", {**self.S, "measured_maximum": 65536}, today="x")
        self.assertNotIn("65536", new)


if __name__ == "__main__":
    unittest.main()
