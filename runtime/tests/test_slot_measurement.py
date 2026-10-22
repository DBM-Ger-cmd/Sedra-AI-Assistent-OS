"""Spec 2, S2.H0 and the start-ready measurement S2.1: --parallel in context_ladder and connection_check, slot_throughput, slot_measurement.
No GPU, no model, no real server: the runtime, the requests, nvidia-smi and the lease are fakes or a temporary database."""
import contextlib
import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

RUNTIME = Path(__file__).resolve().parents[1]
BENCH = RUNTIME / "benchmarks"
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(BENCH))

import context_ladder as ladder_tool  # noqa: E402
import slot_measurement as sm  # noqa: E402
import slot_throughput as st  # noqa: E402
from guppi_runtime.jobs.testlab import LeaseBusy, TestLab  # noqa: E402


class FakeRuntime:
    endpoint = "http://127.0.0.1:1"

    def __init__(self, applied=None, fail_load=False, alive=True):
        self.loads, self.unloads, self.applied, self.fail_load, self.alive = [], 0, applied, fail_load, alive

    def load_model(self, alias, *, context_length=None, gpu=None, identifier=None, parallel=None, server=None, **kw):
        if self.fail_load:
            raise RuntimeError("cannot start")
        self.loads.append({"context": context_length, "parallel": parallel, "server": dict(server or {})})
        self._ctx = context_length

    def loaded_models(self):
        return [{"contextLength": self.applied or self._ctx}] if self.alive else []

    def unload_model(self, **kw):
        self.unloads += 1


def good_ask(delay=0.05):
    def ask(endpoint, alias, prompt, *a, **k):
        time.sleep(delay)
        import re
        code = re.search(r"access code for vault \d+ is ([A-Z0-9]{8})", prompt)
        return {"content": code.group(1) if code else "text", "usage": {"prompt_tokens": 100, "completion_tokens": 20}, "seconds": delay}
    return ask


class LadderParallel(unittest.TestCase):
    def run_rung(self, parallel, ask_fn, runtime=None, events=None):
        runtime = runtime or FakeRuntime()
        row, cpt = ladder_tool.rung_parallel(runtime, "m", {"gguf": "x"}, 8192, parallel, 2, 2.4, lambda s: None, ask_fn=ask_fn,
                                             gpu_fn=lambda: (4000, 12000), events_fn=lambda t0: events, settle_s=0)
        return row, runtime

    def test_server_gets_n_slots_and_n_times_the_window(self):
        row, runtime = self.run_rung(3, good_ask())
        self.assertEqual(runtime.loads[0]["parallel"], 3)
        self.assertEqual(runtime.loads[0]["context"], 3 * 8192)
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["parallel"], 3)
        self.assertTrue(all(p["result"] == "ok" and p["overlap"] and len(p["results"]) == 3 for p in row["probes"]))
        self.assertEqual(runtime.unloads, 1)

    def test_every_slot_gets_its_own_prompt(self):
        prompts = []

        def ask(endpoint, alias, prompt, *a, **k):
            prompts.append(prompt)
            return good_ask(0.02)(endpoint, alias, prompt)
        self.run_rung(2, ask)
        self.assertEqual(len(prompts), 4)
        self.assertEqual(len(set(prompts)), 4)

    def test_wrong_answer_in_one_slot_fails_the_rung(self):
        calls = {"n": 0}

        def ask(endpoint, alias, prompt, *a, **k):
            calls["n"] += 1
            out = good_ask(0.02)(endpoint, alias, prompt)
            if calls["n"] == 2:
                out["content"] = "nope"
            return out
        row, _ = self.run_rung(2, ask)
        self.assertEqual(row["status"], "probe_failed")
        self.assertEqual(row["probes"][0]["result"], "wrong")

    def test_requests_that_did_not_overlap_do_not_count(self):
        lock = __import__("threading").Lock()

        def ask(endpoint, alias, prompt, *a, **k):
            with lock:                                   # serialises the slots: the server did not run them at the same time
                return good_ask(0.05)(endpoint, alias, prompt)
        row, _ = self.run_rung(2, ask)
        self.assertEqual(row["probes"][0]["result"], "no_overlap")
        self.assertEqual(row["status"], "probe_failed")

    def test_context_mismatch_load_failure_driver_events_dead_server(self):
        row, _ = self.run_rung(2, good_ask(), runtime=FakeRuntime(applied=8192))
        self.assertEqual(row["status"], "context_mismatch")
        row, _ = self.run_rung(2, good_ask(), runtime=FakeRuntime(fail_load=True))
        self.assertEqual(row["status"], "load_failed")
        row, _ = self.run_rung(2, good_ask(), events=2)
        self.assertEqual(row["status"], "driver_errors")
        runtime = FakeRuntime()
        runtime.loaded_models = lambda: [{"contextLength": 16384}] if not runtime.loads or len(runtime.loads) < 2 else []
        row, _ = self.run_rung(2, good_ask(), runtime=runtime)
        self.assertEqual(row["status"], "ok")

    def test_ladder_dispatches_by_parallel_and_keeps_the_single_slot_path(self):
        recipe = {"id": "r", "model": "m", "profile": {"server": {"gguf": "x"}}}
        with mock.patch.object(ladder_tool, "rung_parallel", return_value=({"status": "ok", "context": 8192}, 2.4)) as par, \
                mock.patch.object(ladder_tool, "rung", return_value=({"status": "ok", "context": 8192}, 2.4)) as single, \
                mock.patch.object(ladder_tool, "trained_context", return_value=8192):
            out = ladder_tool.ladder(FakeRuntime(), recipe, max_ctx=8192, probes=1, say=lambda s: None, parallel=2)
            self.assertTrue(par.called and not single.called)
            self.assertEqual((out["parallel"], out["safe_max_context"]), (2, 8192))
            par.reset_mock()
            ladder_tool.ladder(FakeRuntime(), recipe, max_ctx=8192, probes=1, say=lambda s: None)
            self.assertTrue(single.called and not par.called)

    def test_overlap_and_judge_helpers(self):
        self.assertTrue(ladder_tool.overlap([(0, 5), (1, 6)]))
        self.assertFalse(ladder_tool.overlap([(0, 1), (2, 3)]))
        self.assertTrue(ladder_tool.overlap([(0, 1)]))
        self.assertEqual(ladder_tool.judge({"error": "x"}, "C"), "error")
        self.assertEqual(ladder_tool.judge({"content": "  "}, "C"), "empty")
        self.assertEqual(ladder_tool.judge({"content": "xCx"}, "C"), "ok")
        self.assertEqual(ladder_tool.judge({"content": "xx"}, "C"), "wrong")


class ConnectionCheckParallel(unittest.TestCase):
    def test_check_starts_n_slots_with_n_times_the_window(self):
        spec = importlib.util.spec_from_file_location("connection_check_t", BENCH / "connection_check.py")
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        runtime = FakeRuntime()
        with mock.patch.object(cc, "run_all", return_value={"ok": True, "checks": []}), mock.patch.object(cc, "poster"), mock.patch.object(cc, "prompt_maker"):
            out = cc.check(runtime, {"id": "r", "model": "m", "profile": {"server": {"gguf": "x"}}}, 4096, None, 3)
        self.assertEqual((runtime.loads[0]["parallel"], runtime.loads[0]["context"], out["parallel"], out["context"]), (3, 3 * 4096, 3, 4096))
        runtime = FakeRuntime()
        with mock.patch.object(cc, "run_all", return_value={"ok": True, "checks": []}), mock.patch.object(cc, "poster"), mock.patch.object(cc, "prompt_maker"):
            cc.check(runtime, {"id": "r", "model": "m", "profile": {"server": {"gguf": "x"}}}, 4096)
        self.assertEqual((runtime.loads[0]["parallel"], runtime.loads[0]["context"]), (1, 4096))


class Throughput(unittest.TestCase):
    def ask(self, endpoint, alias, prompt, max_tokens, *a):
        time.sleep(0.03)
        return {"completion_tokens": max_tokens, "predicted_per_second": 40.0, "seconds": 0.03}

    def test_runs_summary_and_peak(self):
        runtime = FakeRuntime()
        out = st.throughput(runtime, {"id": "r", "model": "m", "profile": {"server": {"gguf": "x", "mtp": True}}}, 2, 4096, 3, 32, say=lambda s: None,
                            ask_fn=self.ask, gpu_fn=lambda: (9000, 12000), events_fn=lambda t0: 0, get=lambda url: [{}, {}], settle_s=0)
        self.assertEqual((runtime.loads[0]["parallel"], runtime.loads[0]["context"], runtime.unloads), (2, 8192, 1))
        self.assertEqual(out["status"], "ok")
        self.assertEqual(len(out["runs"]), 3)
        s = out["summary"]
        self.assertEqual((s["runs_ok"], s["per_slot_tps"], s["vram_peak_gib"], s["overlap_share"]), (3, 40.0, round(9000 / 1024, 2), 1.0))
        self.assertGreater(s["total_tps"], 0)
        self.assertEqual(out["slots_endpoint"], {"available": True, "count": 2})
        self.assertNotIn("gguf", out["server"])

    def test_error_run_and_failed_load(self):
        def bad(endpoint, alias, prompt, max_tokens, *a):
            return {"error": "HTTP 500", "seconds": 0.0}
        rec = {"id": "r", "profile": {"server": {"gguf": "x"}}}
        kw = dict(say=lambda s: None, gpu_fn=lambda: (1, 2), settle_s=0)
        out = st.throughput(FakeRuntime(), rec, 1, 4096, 2, 8, ask_fn=bad, events_fn=lambda t0: 0, **kw)
        self.assertEqual(out["status"], "errors")
        self.assertEqual(st.throughput(FakeRuntime(fail_load=True), rec, 1, 4096, 1, 8, ask_fn=bad, events_fn=lambda t0: 0, **kw)["status"], "load_failed")
        self.assertEqual(st.throughput(FakeRuntime(), rec, 1, 4096, 1, 8, ask_fn=self.ask, events_fn=lambda t0: 3, **kw)["status"], "driver_errors")

    def test_summarize_prompt_and_slots_endpoint(self):
        self.assertEqual(st.summarize([{"errors": ["x"], "total_tps": 1, "per_slot_tps": [1], "wall_s": 1, "vram_peak_gib": 1, "overlap": True}]), {"runs_ok": 0, "runs": 1})
        self.assertNotEqual(st.prompt_for(0, 1), st.prompt_for(1, 1))
        self.assertNotEqual(st.prompt_for(0, 1), st.prompt_for(0, 2))
        self.assertFalse(st.slots_endpoint("http://x", get=lambda u: (_ for _ in ()).throw(OSError()))["available"])


def make_recipes():
    server = {"gguf": "x", "mtp": True}
    return {rid: {"id": rid, "model": rid, "provider": "llama-cpp-server", "profile": {"server": dict(server) if rid == "main" else {"gguf": "x"}}} for rid in ("main", "small")}


class FakeTools:
    def __init__(self, temp=60, used=4000, events=0, fail_tool=None, safe=32768):
        self.calls, self.temp, self.used, self.events, self.fail_tool, self.safe = [], temp, used, events, fail_tool, safe

    def tools(self):
        return {"check": self.check, "ladder": self.ladder, "throughput": self.throughput, "temperature": lambda: self.temp, "gpu": lambda: (self.used, 12000),
                "events": lambda t0: 0}

    def check(self, runtime, recipe, context, server, parallel):
        self.calls.append(("s0", recipe["id"], parallel))
        return {"ok": False, "checks": [], "context": context, "parallel": parallel}

    def ladder(self, runtime, recipe, **kw):
        self.calls.append(("ladder", recipe["id"], kw["parallel"]))
        if self.fail_tool in ("ladder", "both"):
            return {"safe_max_context": None, "rows": [{"status": "load_failed"}]}
        return {"safe_max_context": self.safe, "rows": [{"status": "ok", "driver_events": self.events, "vram_used_gib": 8.0}]}

    def throughput(self, runtime, recipe, parallel, context, runs, tokens, server, say=None, variant=""):
        self.calls.append(("throughput", recipe["id"], parallel, context, variant))
        if self.fail_tool in ("throughput", "both"):
            return {"status": "load_failed", "recipe": recipe["id"]}
        return {"status": "ok", "recipe": recipe["id"], "variant": variant, "context_per_slot": context,
                "summary": {"total_tps": 40.0 * parallel, "per_slot_tps": 40.0, "vram_peak_gib": 9.5, "runs_ok": runs}}


class Measurement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "local_config").mkdir()
        (self.root / "local_config" / "role_routing.yaml").write_text("a: 1\n", encoding="utf-8")
        self.lab = TestLab(self.root / "testlab.db")
        self.logbook_rows = []

    def run_plan(self, plan, tools, **kw):
        runtime = FakeRuntime()
        run = sm.Run(self.root, make_recipes(), tools.tools(), lambda s: None, kw.pop("max_temp", 85), kw.pop("limits", {"main": 3.0, "small": 1.0}),
                     [self.root / "local_config"], clock=kw.pop("clock", time.monotonic), runtime_factory=lambda: runtime)
        lease = self.lab.lease("t", "slot measurement", ttl_s=60, preflight=kw.pop("preflight", None))
        report = sm.execute(plan, run, lease, lambda s: None, logbook=self.logbook_rows.append, out_dir=self.root / "out", today="2026-10-22")
        return report, runtime, run

    def test_plan_order_and_estimate(self):
        plan = sm.build_plan("main", "small", [1, 2])
        self.assertEqual([(s["label"], s["parallel"], s["tool"]) for s in plan[:3]], [("main", 1, "s0"), ("main", 1, "ladder"), ("main", 1, "throughput")])
        self.assertEqual(sum(1 for s in plan if s.get("cpu")), 2)
        self.assertEqual(sum(1 for s in plan if s["label"] == "small"), 8)
        self.assertTrue(all(s["minutes"] > 0 for s in plan))
        self.assertEqual(len(sm.build_plan("main", None, [1, 2, 3, 4])), 12)
        self.assertEqual(len(sm.build_plan("main", "small", [1, 2], with_small=False)), 6)

    def test_full_run_writes_results_table_logbook_and_releases_the_lease(self):
        tools = FakeTools()
        plan = sm.build_plan("main", "small", [1, 2])
        report, runtime, run = self.run_plan(plan, tools)
        self.assertIsNone(report["stopped"])
        self.assertEqual(len(run.results), len(plan))
        self.assertIsNone(self.lab.holder())
        self.assertGreaterEqual(runtime.unloads, 1)
        files = sorted(p.name for p in (self.root / "out").iterdir())
        self.assertEqual(files, ["slot_messung_2026-10-22.json", "slot_messung_2026-10-22.md"])
        data = json.loads((self.root / "out" / files[0]).read_text(encoding="utf-8"))
        self.assertEqual(len(data["results"]), len(plan))
        md = (self.root / "out" / files[1]).read_text(encoding="utf-8")
        self.assertIn("| main | 2 | 32768 | 65536 | 9.5 | 80.0 | 40.0 | nicht bestanden |", md)
        self.assertIn("ohne_mtp", md)
        self.assertIn("(CPU)", md)
        self.assertEqual(len(self.logbook_rows), 1)
        self.assertIn("vollstaendig", self.logbook_rows[0])
        throughput_calls = [c for c in tools.calls if c[0] == "throughput" and c[1] == "main"]
        self.assertEqual([c[4] for c in throughput_calls], ["", "ohne_mtp", "", "ohne_mtp"])
        self.assertTrue(all(c[3] == 32768 for c in throughput_calls))

    def test_window_follows_the_safe_maximum(self):
        tools = FakeTools(safe=16384)
        self.run_plan(sm.build_plan("main", None, [2]), tools)
        self.assertTrue(all(c[3] == 16384 for c in tools.calls if c[0] == "throughput"))

    def test_stops_on_temperature_vram_driver_events_and_config_change(self):
        for tools, reason in ((FakeTools(temp=90), "temperature_90"), (FakeTools(used=12 * 1024), "vram_over_limit_12.0"), (FakeTools(events=2), "driver_events")):
            report, runtime, _ = self.run_plan(sm.build_plan("main", None, [1, 2]), tools)
            self.assertEqual(report["stopped"], reason)
            self.assertGreaterEqual(runtime.unloads, 1)
            self.assertIsNone(self.lab.holder())
            self.assertIn("gestoppt", self.logbook_rows[-1])
        tools = FakeTools()
        original = tools.ladder

        def changing(runtime, recipe, **kw):
            (self.root / "local_config" / "role_routing.yaml").write_text("a: 2\n", encoding="utf-8")
            return original(runtime, recipe, **kw)
        tools.ladder = changing
        report, _, run = self.run_plan(sm.build_plan("main", None, [1]), tools)
        self.assertEqual(report["stopped"], "config_changed")
        self.assertEqual([r["step"]["tool"] for r in run.results], ["s0", "ladder"])

    def test_three_failures_in_a_row_and_server_that_does_not_start(self):
        tools = FakeTools(fail_tool="both")
        report, _, _ = self.run_plan(sm.build_plan("main", None, [1, 2, 3]), tools)
        self.assertEqual(report["stopped"], "three_failures_in_a_row")

        class Dead(FakeTools):
            def check(self, runtime, recipe, context, server, parallel):
                return {"ok": False, "load_error": "cannot start", "checks": []}
        report, _, run = self.run_plan(sm.build_plan("main", None, [1, 2]), Dead())
        self.assertEqual(report["stopped"], "server_does_not_start")
        self.assertEqual(len(run.results), 1)

    def test_time_limit_skips_the_rest_of_that_model_only(self):
        now = {"t": 0.0}

        def clock():
            now["t"] += 4000.0
            return now["t"]
        tools = FakeTools()
        report, _, run = self.run_plan(sm.build_plan("main", "small", [1]), tools, limits={"main": 1.0, "small": 100.0}, clock=clock)
        self.assertTrue(report["skipped"])
        self.assertTrue(all("main" in s for s in report["skipped"]))
        self.assertTrue(any(r["step"]["label"] == "small" for r in run.results))

    def test_busy_lease_and_dirty_gpu_stop_before_anything_runs(self):
        token = self.lab.acquire("someone", "test", ttl_s=600)
        tools = FakeTools()
        report, runtime, run = self.run_plan(sm.build_plan("main", None, [1]), tools)
        self.assertIn("LeaseBusy", report["stopped"])
        self.assertEqual(tools.calls, [])
        self.lab.release(token)

        def dirty(owner):
            raise RuntimeError("GPU holds 8 GiB")
        report, runtime, run = self.run_plan(sm.build_plan("main", None, [1]), FakeTools(), preflight=dirty)
        self.assertIn("RuntimeError", report["stopped"])
        self.assertEqual(run.results, [])
        self.assertIsNone(self.lab.holder())

    def test_dry_run_starts_nothing(self):
        (self.root / "local_config" / "role_routing.yaml").write_text(
            "role_routing:\n  capabilities:\n    - {id: main, provider: llama-cpp-server, profile: {server: {gguf: 'nofile.gguf'}}}\n", encoding="utf-8")
        out = []
        with mock.patch("builtins.print", side_effect=lambda *a, **k: out.append(" ".join(str(x) for x in a))), \
                mock.patch.object(sm, "real_tools", side_effect=AssertionError("no tools in a dry run")):
            code = sm.main([str(self.root), "--recipe", "main", "--no-small"])
        text = "\n".join(out)
        self.assertEqual(code, 1)
        self.assertIn("Dry run: nothing was started", text)
        self.assertIn("model file of main is missing", text)
        self.assertIsNone(self.lab.holder())
        self.assertEqual(self.lab.queue(), [])

    def test_file_hashes_and_estimates(self):
        before = sm.file_hashes([self.root / "local_config"])
        (self.root / "local_config" / "x.json").write_text("{}", encoding="utf-8")
        self.assertNotEqual(before, sm.file_hashes([self.root / "local_config"]))
        self.assertEqual(sm.estimate_minutes({"tool": "s0", "parallel": 1}), 4)
        self.assertGreater(sm.estimate_minutes({"tool": "ladder", "parallel": 1}), sm.estimate_minutes({"tool": "ladder", "parallel": 4}) - 1000)


if __name__ == "__main__":
    unittest.main()
