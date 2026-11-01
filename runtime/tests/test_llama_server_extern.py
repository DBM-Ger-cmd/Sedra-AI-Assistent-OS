"""Externer Router statt eigenem Prozess (llama_server.external): Sedra startet und beendet dort nichts, sondern bittet den
llama-server im Router-Modus, ein Modell zu laden und zu entladen. Kein echter Server: HTTP ist ersetzt."""
import unittest

from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime, router_id
from guppi_runtime.models.llamacpp import LlamaCppRouterAdapter, LlamaCppServerAdapter
from guppi_runtime.models.runtime_control import RuntimeControlError
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ENDPOINT = "http://127.0.0.1:8090"


class FakeRouter:
    """Der Router: neun Modelle, immer nur eins geladen (--models-max 1)."""
    def __init__(self, ids=("qwen3.5-9b-q6_k", "gemma-4-12b-qat", "nemotron-3.5-bolt-e4b"), up=True, n_ctx=45056, slots=1, load_polls=1):
        self.states = {i: "unloaded" for i in ids}
        self.up, self.n_ctx, self.slots, self.load_polls = up, n_ctx, slots, load_polls
        self.posts, self.pending = [], {}

    def get_json(self, url, timeout=3):
        if not self.up: raise OSError("connection refused")
        if url.endswith("/health"): return 200, {}
        if url.endswith("/v1/models"):
            for rid in list(self.pending):                      # ein Modell wird erst nach `load_polls` Abfragen "loaded"
                self.pending[rid] -= 1
                if self.pending[rid] <= 0:
                    for k in self.states: self.states[k] = "unloaded"
                    self.states[rid] = "loaded"; del self.pending[rid]
            return 200, {"data": [{"id": k, "status": {"value": v}} for k, v in self.states.items()]}
        if "/props" in url: return 200, {"default_generation_settings": {"n_ctx": self.n_ctx}, "total_slots": self.slots}
        raise OSError("unknown")

    def post_json(self, url, payload, timeout=30):
        self.posts.append((url.replace(ENDPOINT, ""), payload))
        rid = payload["model"]
        if url.endswith("/models/load"):
            if self.states.get(rid) == "loaded": return 400, {"error": {"message": "model is already running"}}
            self.pending[rid] = self.load_polls; return 200, {"success": True}
        if url.endswith("/models/unload"):
            self.states[rid] = "unloaded"; return 200, {"success": True}
        return 404, {}


def runtime(router, **cfg):
    config = LlamaServerConfig({"enabled": True, "external": {"endpoint": ENDPOINT}, **cfg})
    clock = [0.0]
    def mono(): clock[0] += 1.0; return clock[0]
    return LlamaServerRuntime(config, ".", get_json=router.get_json, post_json=router.post_json, sleep=lambda s: None, monotonic=mono)


class ConfigTests(unittest.TestCase):
    def test_off_without_the_key(self):
        self.assertIsNone(LlamaServerConfig({"enabled": True}).external_endpoint)

    def test_loopback_only(self):
        for bad in ("http://192.168.0.5:8090", "http://example.com/v1", "ftp://127.0.0.1:8090"):
            with self.subTest(bad), self.assertRaises(ValueError):
                LlamaServerConfig({"external": {"endpoint": bad}})
        with self.assertRaises(ValueError): LlamaServerConfig({"external": "http://127.0.0.1:8090"})
        with self.assertRaises(ValueError): LlamaServerConfig({"external": {}})

    def test_trailing_slash_dropped(self):
        self.assertEqual(LlamaServerConfig({"external": {"endpoint": ENDPOINT + "/"}}).external_endpoint, ENDPOINT)

    def test_shipped_file_has_it_off_and_machine_switch_is_allowed(self):
        from pathlib import Path
        import tempfile
        from guppi_runtime.local_switches import LocalSwitches
        shipped = LlamaServerConfig.load(Path(__file__).resolve().parents[1] / "config" / "llama_server.yaml")
        self.assertEqual((shipped.external_url, shipped.external_enabled, shipped.external_endpoint), (ENDPOINT, False, None))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "switches.yaml"
            path.write_text("switches:\n  llama_server: {enabled: true, external: true}\n", encoding="utf-8")
            sw = LocalSwitches.load(path)
            self.assertEqual(sw.problems, []); self.assertIs(sw.apply("llama_server", "external", False), True)
            path.write_text("switches:\n  llama_server: {external: 'ja'}\n", encoding="utf-8")
            self.assertEqual(LocalSwitches.load(path).problems, ["not_boolean:llama_server.external"])

    def test_explicit_enabled_false_keeps_it_off(self):
        config = LlamaServerConfig({"external": {"endpoint": ENDPOINT, "enabled": False}})
        self.assertIsNone(config.external_endpoint); self.assertEqual(config.external_url, ENDPOINT)
        with self.assertRaises(ValueError): LlamaServerConfig({"external": {"endpoint": ENDPOINT, "enabled": "ja"}})

    def test_router_id_strips_vendor_prefix(self):
        self.assertEqual(router_id("google/gemma-4-12b-qat"), "gemma-4-12b-qat")
        self.assertEqual(router_id("qwen3.5-9b-q6_k"), "qwen3.5-9b-q6_k")


class ExternalRuntimeTests(unittest.TestCase):
    def test_available_without_an_engine_and_endpoint_is_the_router(self):
        rt = runtime(FakeRouter())
        self.assertTrue(rt.available()); self.assertEqual(rt.endpoint, ENDPOINT); self.assertTrue(rt.status()["external"])

    def test_load_asks_the_router_and_reports_what_it_applies(self):
        router = FakeRouter(n_ctx=45056, slots=1)
        rt = runtime(router)
        out = rt.load_model("nvidia/nemotron-3.5-bolt-e4b", context_length=45056, parallel=2, server={"gguf": "x.gguf", "kv_cache_type": "q8_0"}, identifier="nemotron-3.5-bolt-e4b")
        self.assertIn("nemotron-3.5-bolt-e4b", out["output"])
        self.assertEqual(router.posts, [("/models/load", {"model": "nemotron-3.5-bolt-e4b"})])
        info = rt.loaded_models()[0]
        self.assertEqual((info["contextLength"], info["slots"], info["pid"]), (45056, 1, None))   # the router's numbers, not the recipe's
        self.assertEqual(rt.status()["running"], True)

    def test_recipe_model_name_with_vendor_prefix_finds_the_router_model(self):
        router = FakeRouter()
        rt = runtime(router)
        rt.load_model("google/gemma-4-12b-qat", context_length=32768, server={"gguf": "x.gguf"})
        self.assertEqual(router.posts[0][1], {"model": "gemma-4-12b-qat"})

    def test_no_process_started_no_canary_no_gguf_needed(self):
        rt = runtime(FakeRouter())
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server=None)       # no recipe `server` block is fine here
        self.assertIsNone(rt._proc)

    def test_already_loaded_is_not_an_error(self):
        router = FakeRouter(); router.states["qwen3.5-9b-q6_k"] = "loaded"
        rt = runtime(router)
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        self.assertEqual(router.posts, [])                                          # nothing to load: no request at all

    def test_load_waits_until_the_router_reports_loaded(self):
        router = FakeRouter(load_polls=3)
        rt = runtime(router)
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        self.assertEqual(router.states["qwen3.5-9b-q6_k"], "loaded")

    def test_load_timeout(self):
        router = FakeRouter(load_polls=10 ** 6)
        rt = runtime(router, startup_timeout_s=5)
        with self.assertRaisesRegex(RuntimeControlError, "external_model_load_timeout"):
            rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        self.assertEqual(rt.loaded_models(), [])

    def test_unknown_model_is_refused_before_any_request(self):
        router = FakeRouter()
        rt = runtime(router)
        with self.assertRaisesRegex(RuntimeControlError, "external_model_unknown:no-such-model"):
            rt.load_model("no-such-model", context_length=4096, server={"gguf": "x.gguf"})
        self.assertEqual(router.posts, [])

    def test_router_down_says_so(self):
        rt = runtime(FakeRouter(up=False))
        with self.assertRaisesRegex(RuntimeControlError, "external_server_unreachable"):
            rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})

    def test_second_load_without_unload_is_refused_like_the_own_server(self):
        rt = runtime(FakeRouter())
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        with self.assertRaisesRegex(RuntimeControlError, "server_already_running"):
            rt.load_model("gemma-4-12b-qat", context_length=32768, server={"gguf": "x.gguf"})

    def test_unload_asks_the_router_and_forgets(self):
        router = FakeRouter()
        rt = runtime(router)
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        self.assertEqual(rt.unload_model("qwen3.5-9b-q6_k")["output"], "stopped")
        self.assertEqual(router.posts[-1], ("/models/unload", {"model": "qwen3.5-9b-q6_k"}))
        self.assertEqual(rt.loaded_models(), [])
        self.assertEqual(rt.unload_model()["output"], "nothing to stop")

    def test_unload_of_a_model_that_is_not_loaded_here(self):
        rt = runtime(FakeRouter())
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        with self.assertRaises(ValueError): rt.unload_model("gemma-4-12b-qat")

    def test_model_swapped_by_another_client_is_not_reported_as_loaded(self):
        router = FakeRouter()
        rt = runtime(router)
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        router.states["qwen3.5-9b-q6_k"] = "unloaded"; router.states["gemma-4-12b-qat"] = "loaded"     # Pi asked for another model
        self.assertEqual(rt.loaded_models(), [])
        self.assertFalse(rt.status()["running"])


class RouterAdapterTests(unittest.TestCase):
    def test_vendor_prefix_removed_in_the_request(self):
        sent = []
        class Spy(LlamaCppRouterAdapter):
            def _request(self, method, path, payload=None):
                sent.append(payload); return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}
        Spy("http://127.0.0.1:8090").chat([{"role": "user", "content": "hi"}], model="nvidia/nemotron-3.5-bolt-e4b")
        self.assertEqual(sent[0]["model"], "nemotron-3.5-bolt-e4b")

    def test_own_server_adapter_keeps_the_name_as_before(self):
        sent = []
        class Spy(LlamaCppServerAdapter):
            def _request(self, method, path, payload=None):
                sent.append(payload); return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}
        Spy("http://127.0.0.1:8089").chat([{"role": "user", "content": "hi"}], model="nvidia/nemotron-3.5-bolt-e4b")
        self.assertEqual(sent[0]["model"], "nvidia/nemotron-3.5-bolt-e4b")


if __name__ == "__main__":
    unittest.main()
