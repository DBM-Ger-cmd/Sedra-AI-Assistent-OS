r"""Throughput of N parallel slots (Spec 2, S2.H0, SCH-01; measurement plan S2.1 step 6). A measurement, not a test.

    .venv\Scripts\python.exe benchmarks/slot_throughput.py <project_dir> <recipe_id> --parallel N [--context 32768] [--runs 3] [--tokens 256] [--set KEY=VALUE ...] [--tag x]

The recipe's server is started exactly as the recipe says, except for what --set changes for THIS run (the recipe file is not touched), with N slots and the window --context
PER SLOT (-c = N x context). Then N requests with different prompts are sent at the same moment, `--runs` times (after one warm-up request). Per run it records the wall time,
the generated tokens, the tokens per second over all slots and per slot (the server's own `timings` when it sends them), whether the N requests really overlapped, and the peak GPU memory.
Also recorded: the GPU memory after loading, new NVIDIA driver events, and whether the server answers GET /slots (open point OP-S2-03).
Result: runtime_data/measurements/slot_throughput_<recipe>_p<N>[_<tag>]_<date>.json. Holds the GPU lease (with the usual leftover clean-up). Nothing is changed in any recipe.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from context_ladder import driver_events_since, gpu_mib, overlap, timed_ask                 # noqa: E402
from guppi_runtime.models.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path                             # noqa: E402

TOPICS = ("the tides of a small harbor", "how a clock escapement works", "the life cycle of a river", "a market day in an old town", "the way a lighthouse lamp turns",
          "how bread rises in an oven", "a train crossing a mountain pass", "the habits of migrating birds")


def prompt_for(slot, run, words=120):
    """A prompt of a few hundred tokens that differs per slot and run, so the slots share no prompt cache."""
    return (f"Write a continuous, plain description about {TOPICS[(slot + run) % len(TOPICS)]}. Use about {words} words, no lists, no headings. "
            f"(request {run}-{slot})")


def generate(endpoint, alias, prompt, max_tokens, timeout=900):
    """One chat request. Returns {completion_tokens, predicted_per_second, seconds} or {error, seconds}."""
    body = json.dumps({"model": alias, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0, "reasoning_effort": "low"}).encode()
    req = urllib.request.Request(endpoint + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}: {exc.read()[:200].decode('utf-8', 'replace')}", "seconds": round(time.monotonic() - started, 1)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}", "seconds": round(time.monotonic() - started, 1)}
    seconds = time.monotonic() - started
    tokens = (data.get("usage") or {}).get("completion_tokens") or 0
    predicted = (data.get("timings") or {}).get("predicted_per_second")
    return {"completion_tokens": tokens, "predicted_per_second": predicted if isinstance(predicted, (int, float)) else (tokens / seconds if seconds > 0 else 0.0),
            "seconds": round(seconds, 2)}


def slots_endpoint(endpoint, get=None):
    """Does the server answer GET /slots, and with how many entries? (OP-S2-03) -> {available, count}"""
    try:
        if get is not None:
            data = get(endpoint + "/slots")
        else:
            with urllib.request.urlopen(endpoint + "/slots", timeout=10) as resp:
                data = json.loads(resp.read())
        return {"available": True, "count": len(data) if isinstance(data, list) else None}
    except Exception as exc:
        return {"available": False, "error": type(exc).__name__}


class PeakSampler:
    """Samples the GPU memory used while a run is going (a thread, once a second)."""

    def __init__(self, gpu_fn, interval=1.0):
        self.gpu_fn, self.interval, self.peak, self._stop = gpu_fn, interval, 0, threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.peak = max(self.peak, self.gpu_fn()[0])
            except Exception:
                pass
            self._stop.wait(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=5)
        try:
            self.peak = max(self.peak, self.gpu_fn()[0])
        except Exception:
            pass


def one_run(endpoint, alias, parallel, run, tokens, ask_fn, gpu_fn):
    """N requests at the same moment. Returns the record of the run."""
    from concurrent.futures import ThreadPoolExecutor
    prompts = [prompt_for(k, run) for k in range(parallel)]
    started = time.monotonic()
    with PeakSampler(gpu_fn) as sampler, ThreadPoolExecutor(max_workers=parallel) as pool:
        done = list(pool.map(lambda p: timed_ask(endpoint, alias, p, lambda e, a, q: ask_fn(e, a, q, tokens)), prompts))
    wall = time.monotonic() - started
    outs = [o for o, _, _ in done]
    errors = [o["error"] for o in outs if "error" in o]
    total = sum(o.get("completion_tokens", 0) for o in outs)
    return {"run": run, "wall_s": round(wall, 2), "completion_tokens": total, "total_tps": round(total / wall, 2) if wall > 0 else 0.0,
            "per_slot_tps": [round(o.get("predicted_per_second") or 0.0, 2) for o in outs], "overlap": overlap([(s, e) for _, s, e in done]),
            "vram_peak_gib": round(sampler.peak / 1024, 2), "errors": errors}


def summarize(runs):
    """Median over the runs without errors: total tokens/s, tokens/s per slot (mean of the slots), wall time, peak memory; the share of runs whose requests overlapped."""
    good = [r for r in runs if not r["errors"]]
    if not good:
        return {"runs_ok": 0, "runs": len(runs)}
    return {"runs_ok": len(good), "runs": len(runs), "total_tps": round(statistics.median(r["total_tps"] for r in good), 2),
            "per_slot_tps": round(statistics.median(statistics.mean(r["per_slot_tps"]) for r in good), 2),
            "wall_s": round(statistics.median(r["wall_s"] for r in good), 2), "vram_peak_gib": max(r["vram_peak_gib"] for r in good),
            "overlap_share": round(sum(1 for r in good if r["overlap"]) / len(good), 2)}


def throughput(runtime, recipe, parallel, context, runs, tokens, server=None, say=print, ask_fn=None, gpu_fn=None, events_fn=None, get=None, variant="", settle_s=2):
    ask_fn, gpu_fn, events_fn = ask_fn or generate, gpu_fn or gpu_mib, events_fn or driver_events_since
    server = server or recipe["profile"]["server"]
    alias = str(recipe.get("model") or recipe["id"])
    out = {"recipe": recipe["id"], "model": alias, "parallel": parallel, "context_per_slot": context, "variant": variant,
           "server": {k: v for k, v in server.items() if k != "gguf"}, "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    t0 = datetime.now()
    try:
        runtime.load_model(alias, context_length=context * parallel, gpu="max", identifier=alias, parallel=parallel, server=server)
    except Exception as exc:
        return {**out, "status": "load_failed", "error": str(exc)[:300]}
    try:
        info = (runtime.loaded_models() or [{}])[0]
        used, total = gpu_fn()
        out.update(applied_context=info.get("contextLength"), vram_load_gib=round(used / 1024, 2), vram_free_load_gib=round((total - used) / 1024, 2),
                   slots_endpoint=slots_endpoint(runtime.endpoint, get))
        if info.get("contextLength") not in (context * parallel, None):
            return {**out, "status": "context_mismatch"}
        ask_fn(runtime.endpoint, alias, prompt_for(0, 0), 16)                       # warm-up: the first request pays for lazy buffers
        records = []
        for run in range(1, runs + 1):
            rec = one_run(runtime.endpoint, alias, parallel, run, tokens, ask_fn, gpu_fn)
            records.append(rec)
            say(f"      run {run}: {rec['total_tps']} tok/s over {parallel} slot(s), per slot {rec['per_slot_tps']}, overlap {rec['overlap']}, peak {rec['vram_peak_gib']} GiB"
                + (f", ERRORS {rec['errors']}" if rec["errors"] else ""))
            if not runtime.loaded_models():
                records[-1]["errors"].append("server_died")
                break
        events = events_fn(t0)
        summary = summarize(records)
        status = "server_died" if any("server_died" in r["errors"] for r in records) else "errors" if summary["runs_ok"] < len(records) else \
                 "driver_errors" if events else "ok"
        return {**out, "runs": records, "summary": summary, "driver_events": events, "status": status}
    finally:
        try:
            runtime.unload_model(all_models=True)
        except Exception:
            pass
        time.sleep(settle_s)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("recipe")
    ap.add_argument("--parallel", type=int, default=1, choices=range(1, 9), metavar="N")
    ap.add_argument("--context", type=int, default=32768, help="window per slot")
    ap.add_argument("--runs", type=int, default=3); ap.add_argument("--tokens", type=int, default=256)
    ap.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    from devvm_build import server_settings
    overrides = server_settings(args.overrides)
    project = Path(args.project)
    recipes = {r["id"]: r for r in yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"]}
    recipe = recipes.get(args.recipe)
    if not recipe or recipe.get("provider") != "llama-cpp-server":
        raise SystemExit(f"{args.recipe}: not a llama-cpp-server recipe")
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled, config.mtp = True, True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_slots_")))
    out_dir = project / "runtime_data" / "measurements"; out_dir.mkdir(parents=True, exist_ok=True)
    with TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "slot_throughput"), f"slot throughput {args.recipe} x{args.parallel}", ttl_s=1800, wait_s=1800,
                                              preflight=clear_leftovers):
        result = throughput(runtime, recipe, args.parallel, args.context, args.runs, args.tokens, {**recipe["profile"]["server"], **overrides}, say=lambda s: print(s, flush=True))
    result["overrides"] = overrides
    tag = f"_{args.tag}" if args.tag else ""
    target = out_dir / f"slot_throughput_{args.recipe}_p{args.parallel}{tag}_{date.today().isoformat()}.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{args.recipe} x{args.parallel}: {result['status']}  {result.get('summary', {})}  -> {target.name}", flush=True)


if __name__ == "__main__":
    main()
