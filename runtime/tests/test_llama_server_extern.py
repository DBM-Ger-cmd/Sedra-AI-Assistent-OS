"""Externer Router statt eigenem Prozess (llama_server.external): Sedra startet und beendet dort nichts, sondern bittet den
llama-server im Router-Modus, ein Modell zu laden und zu entladen. Kein echter Server: HTTP ist ersetzt."""
import unittest

from sedra_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime, router_id
from sedra_runtime.models.llamacpp import LlamaCppRouterAdapter, LlamaCppServerAdapter
from sedra_runtime.models.runtime_control import RuntimeControlError
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
        from sedra_runtime.local_switches import LocalSwitches
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

    def test_loading_another_model_swaps_it_on_the_shared_router(self):
        router = FakeRouter()
        rt = runtime(router)
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        rt.load_model("gemma-4-12b-qat", context_length=32768, server={"gguf": "x.gguf"})        # no refusal: the router holds one model, it swaps
        self.assertEqual([m["identifier"] for m in rt.loaded_models()], ["gemma-4-12b-qat"])
        self.assertEqual(router.posts[-1], ("/models/load", {"model": "gemma-4-12b-qat"}))

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

    def test_model_swapped_by_another_client_is_reported_as_it_is(self):
        router = FakeRouter()
        rt = runtime(router)
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        router.states["qwen3.5-9b-q6_k"] = "unloaded"; router.states["gemma-4-12b-qat"] = "loaded"     # Pi asked for another model
        self.assertEqual([m["identifier"] for m in rt.loaded_models()], ["gemma-4-12b-qat"])          # the model of the other client, not ours
        router.states["gemma-4-12b-qat"] = "unloaded"
        self.assertEqual(rt.loaded_models(), [])
        self.assertFalse(rt.status()["running"])

    def test_model_loaded_by_another_client_is_taken_over_and_reused_by_the_loader(self):
        """The series of 1.11.: a model that is already on the router (Pi, an earlier Sedra) must not be counted a second time."""
        from sedra_runtime.models.model_loader import LoaderConfig, ModelLoader
        router = FakeRouter(ids=("qwen3.5-9b-q6_k",), n_ctx=65536, slots=1)
        router.states["qwen3.5-9b-q6_k"] = "loaded"
        rt = runtime(router)
        loader = ModelLoader(LoaderConfig({"enabled": True}), rt, controllers={"llama-cpp-server": rt})
        res = {"model": "qwen3.5-9b-q6_k", "context_window": 65536, "provider_ref": "llama-cpp-server", "slots": 1,
               "estimated_resources": {"vram_gb": 7.5}, "load_profile": {"server": {"gguf": "x.gguf"}}}
        self.assertEqual(loader.resident_vram_gb(res), 7.5)                      # counted as already resident
        self.assertEqual(loader.ensure(res)["action"], "reused")
        self.assertEqual(router.posts, [])                                       # nothing loaded, nothing unloaded
        self.assertTrue(rt.status()["running"])                                  # so the scheduler does not take the server for gone

    def test_scheduler_starts_on_a_model_the_router_already_holds_without_counting_it_twice(self):
        """Series 1.11. 'warm': Pi (or an earlier run) loaded the model; free VRAM looks too small, but the instance is reused, not copied."""
        import tempfile
        from pathlib import Path
        from sedra_runtime.jobs.model_scheduler import ModelScheduler, ModelSchedulerConfig
        from sedra_runtime.jobs.testlab import TestLab
        from sedra_runtime.models.model_loader import LoaderConfig, ModelLoader
        from model_scheduler_fakes import raw_config, Clock, FakeAudit

        class Resources:
            enabled = True
            def __init__(self): self.config = type("C", (), {"vram_reserve_gb": 0.7})(); self.reserved = []
            def measured_free_vram_gb(self): return 3.7                          # the 9B on the router holds the rest of the card
            def reserve(self, job_id, attempt_id, estimate, **credit): self.reserved.append(credit); return {"status": "GRANTED", "reservation": {}}
            def audit_denied(self, *a, **k): pass
            def release_job(self, *a, **k): pass

        router = FakeRouter(ids=("qwen3.5-9b-q6_k",), n_ctx=65536, slots=1)
        router.states["qwen3.5-9b-q6_k"] = "loaded"
        rt = runtime(router)
        loader = ModelLoader(LoaderConfig({"enabled": True}), rt, controllers={"llama-cpp-server": rt})
        tmp = tempfile.mkdtemp()
        resources = Resources()
        sched = ModelScheduler(ModelSchedulerConfig(raw_config()), TestLab(Path(tmp) / "testlab.db", clock=Clock(), alive=lambda p: True, pid=111),
                               loader=loader, runtime=rt, resources=resources, audit=FakeAudit())
        res = {"capability_id": "coder.local_qwen3_5_9b_q6_k", "provider_ref": "llama-cpp-server", "model": "qwen3.5-9b-q6_k", "context_window": 65536,
               "slots": 1, "load_profile": {"server": {"gguf": "x.gguf"}},
               "estimated_resources": {"ram_gb": 8.0, "vram_gb": 7.0, "kv_cache_gb": 0.5, "kv_cache_placement": "gpu", "complete": True}}
        out = sched.ensure_server(res, owner="werkstatt")
        self.assertEqual(out["action"], "started")
        self.assertEqual(out["load"]["action"], "reused")                             # nothing was loaded again
        self.assertEqual(router.posts, [])
        self.assertTrue(resources.reserved[0].get("resident_vram_gb", 0) > 0 and resources.reserved[0].get("resident_ram_gb", 0) > 0)
        self.assertEqual(sched.view()["server"]["state"], "bereit")

    def test_a_model_key_with_vendor_prefix_loads_on_the_router(self):
        """The router knows "gemma-4-12b-qat", the recipe says "google/gemma-4-12b-qat": the load must not end in `context_not_applied:None`."""
        from sedra_runtime.models.model_loader import LoaderConfig, ModelLoader
        router = FakeRouter(ids=("gemma-4-12b-qat",), n_ctx=65536, slots=1)
        rt = runtime(router)
        loader = ModelLoader(LoaderConfig({"enabled": True}), rt, controllers={"llama-cpp-server": rt})
        out = loader.ensure({"model": "google/gemma-4-12b-qat", "context_window": 65536, "provider_ref": "llama-cpp-server", "slots": 1,
                             "estimated_resources": {"vram_gb": 8.7}, "load_profile": {"server": {"gguf": "x.gguf"}}})
        self.assertEqual((out["action"], out["context_length"]), ("loaded", 65536))
        self.assertEqual(router.states["gemma-4-12b-qat"], "loaded")

    def test_a_sleeping_model_counts_as_loaded_and_is_not_loaded_again(self):
        """After `--sleep-idle-seconds` the router reports "sleeping": the model is still there and the next request wakes it."""
        from sedra_runtime.models.model_loader import LoaderConfig, ModelLoader
        router = FakeRouter(ids=("gemma-4-12b-qat",), n_ctx=65536, slots=1)
        router.states["gemma-4-12b-qat"] = "sleeping"
        rt = runtime(router)
        loader = ModelLoader(LoaderConfig({"enabled": True}), rt, controllers={"llama-cpp-server": rt})
        out = loader.ensure({"model": "google/gemma-4-12b-qat", "context_window": 65536, "provider_ref": "llama-cpp-server", "slots": 1,
                             "estimated_resources": {"vram_gb": 8.7}, "load_profile": {"server": {"gguf": "x.gguf"}}})
        self.assertEqual(out["action"], "reused")
        self.assertEqual(router.posts, [])
        self.assertTrue(loader.loaded("google/gemma-4-12b-qat"))

    def test_other_window_on_the_router_is_refused_honestly(self):
        """The window comes from the router's preset, not from the recipe: a mismatch ends in `context_not_applied`, never in a wrong window."""
        from sedra_runtime.models.model_loader import LoaderConfig, ModelLoader
        router = FakeRouter(ids=("qwen3.5-9b-q6_k",), n_ctx=32768, slots=1)
        router.states["qwen3.5-9b-q6_k"] = "loaded"
        rt = runtime(router)
        loader = ModelLoader(LoaderConfig({"enabled": True}), rt, controllers={"llama-cpp-server": rt})
        res = {"model": "qwen3.5-9b-q6_k", "context_window": 65536, "provider_ref": "llama-cpp-server", "slots": 1,
               "estimated_resources": {"vram_gb": 7.5}, "load_profile": {"server": {"gguf": "x.gguf"}}}
        self.assertEqual(loader.resident_vram_gb(res), 0.0)                      # not reusable: the router's window differs
        from sedra_runtime.models.model_loader import LoadError
        with self.assertRaisesRegex(LoadError, "context_not_applied:32768"):
            loader.ensure(res)


class SedraRouterTests(unittest.TestCase):
    """Sedra-Modell-Router: ist keiner da, startet Sedra ihn beim Laden selbst und schreibt das gewaehlte Fenster in seine Modellliste."""
    def test_laden_startet_den_router_und_schreibt_fenster_und_slots(self):
        import tempfile
        from pathlib import Path
        from sedra_runtime.models.router_verwaltung import RouterVerwaltung
        router = FakeRouter(up=False)
        rt = runtime(router)
        with tempfile.TemporaryDirectory() as tmp:
            gguf = Path(tmp) / "m.gguf"; gguf.write_bytes(b"x")
            rt.executable_dir = Path(tmp)
            gestartet = []
            class P:
                pid = 77
                def poll(self): return None
            def popen(argv, **kw):
                gestartet.append(argv); router.up = True; return P()
            rt.router = RouterVerwaltung(endpoint=ENDPOINT, executable_dir=tmp, vendor_dir=None, ordner=Path(tmp) / "r", popen=popen, get_json=router.get_json,
                                         sleep=lambda s: None, kill=lambda p: setattr(router, "up", False), pid_lebt=lambda p: False)
            rt.load_model("qwen3.5-9b-q6_k", context_length=131072, parallel=2, server={"gguf": str(gguf)}, identifier="qwen3.5-9b-q6_k")
            ini = rt.router.preset.read_text(encoding="utf-8")
            self.assertEqual(len(gestartet), 1)
            for zeile in ("[qwen3.5-9b-q6_k]", "c = 131072", "np = 2", "model = " + str(gguf)):
                self.assertIn(zeile, ini)
            self.assertEqual(router.posts, [("/models/load", {"model": "qwen3.5-9b-q6_k"})])
            self.assertEqual(rt.router_abschnitte([{"provider": "llama-cpp-server", "enabled": True, "model": "v/x-1", "profile": {
                "server": {"gguf": str(gguf), "slots": 2}, "context": {"tiers": [8192, 32768], "maximum": 32768, "per_slots": {2: 16384}}}}])["x-1"]["c"],
                "32768", "das groesste Fenster je Slot (16384) mal zwei Slots")


class RouterNichtErreichbarTests(unittest.TestCase):
    """Windows braucht gut 2 s je abgelehnter Verbindung zu 127.0.0.1; die Modellliste fragt je Rezept. Eine Ablehnung gilt darum kurz."""
    def test_abgelehnte_verbindung_wird_nur_einmal_wirklich_versucht(self):
        from sedra_runtime.models import llama_server_runtime as m
        versuche, zeit = [], [100.0]
        def roh(url, timeout=3):
            versuche.append(url); raise m.urllib.error.URLError(ConnectionRefusedError("refused"))
        alt, m._http_json = m._http_json, roh
        m._ABGELEHNT.clear()
        try:
            for _ in range(5):
                with self.assertRaises(OSError):
                    m._http_json_router("http://127.0.0.1:59999/v1/models", _jetzt=lambda: zeit[0])
            self.assertEqual(len(versuche), 1)
            zeit[0] += 6.0                                     # nach 5 s wird wieder wirklich gefragt
            with self.assertRaises(OSError):
                m._http_json_router("http://127.0.0.1:59999/v1/models", _jetzt=lambda: zeit[0])
            self.assertEqual(len(versuche), 2)
        finally:
            m._http_json = alt; m._ABGELEHNT.clear()


class SchedulerAliveTests(unittest.TestCase):
    """server_aus series (1.11. to 12.11.): a failed /health of another thread cleared `_info` right after the load, the scheduler took the
    server for gone and stopped it. `_alive` asks the router again before it decides."""
    def _alive(self, rt):
        import types
        from sedra_runtime.jobs.model_scheduler import ModelScheduler
        return ModelScheduler._alive(types.SimpleNamespace(runtime=rt))

    def test_one_failed_health_does_not_make_the_router_server_gone(self):
        router = FakeRouter()
        rt = runtime(router)
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        router.up = False; rt.loaded_models(); router.up = True              # another thread asked while the router was busy
        self.assertFalse(rt.status()["running"])
        self.assertTrue(self._alive(rt))
        self.assertTrue(rt.status()["running"])

    def test_router_really_down_or_model_gone_is_gone(self):
        router = FakeRouter()
        rt = runtime(router)
        rt.load_model("qwen3.5-9b-q6_k", context_length=65536, server={"gguf": "x.gguf"})
        router.up = False
        self.assertFalse(self._alive(rt))
        router.up = True; router.states["qwen3.5-9b-q6_k"] = "unloaded"
        self.assertFalse(self._alive(rt))


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
