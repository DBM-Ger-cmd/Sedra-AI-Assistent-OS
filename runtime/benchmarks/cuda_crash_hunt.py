r"""Which setting stops `CUDA error: illegal memory access`, and what does it cost in speed? A repeated measurement, not a test.

    .venv\Scripts\python.exe benchmarks/cuda_crash_hunt.py <project_dir> [--model jan|swe|qwen3coder] [--runs 2] [--requests 150] [--variants baseline,fa_off,...]

Jan-code-4b's llama-server died 7 times in one small_team run (ggml-cuda.cu:109 CUDA error: illegal memory access, in
cudaStreamSynchronize); Qwen3-Coder showed the same on this PC, Gemma and gpt-oss never did (docs/MESSUNGEN.md, section 3).
The load here is the real one: Jan's tool-using repair of the five rework tasks (small_team.repair), round after round, on a freshly started
server per run. A run ends at the first lost connection (= crash) or after `--requests` completions. Result per variant: how many requests
each run survived. A variant counts as a candidate only if EVERY run survives the full count while the baseline crashes.
Also counted: new `nvlddmkm` driver events in the Windows system log during the run (driver resets show up there even when the server survives).
Models: `jan` (tool repair load; a recipe id such as coder.llama_gptoss also works, started as its recipe says), `swe` (SWE-Review-8B, tool review load), `qwen3coder` (the recipe coder.local_primary: n_cpu_moe 44, ubatch 2048, tool repair load).
Speed: at the start of every run a fixed prompt (about 1300 tokens in, 256 out, temperature 0) is sent 3 times; the server's own timings give prompt and
generation tokens/s (median). A run that crashes before the probe is done has no speed.
Holds the GPU lease. Run log and results: runtime_data/measurements/logs/cuda_crash_hunt_<model>_*.{log,json}.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
import urllib.error
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import small_team as st                                                              # noqa: E402
from rework_bench import TASKS                                                       # noqa: E402
from guppi_runtime import gpu_preflight                                              # noqa: E402
from guppi_runtime.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.run_log import RunLog                                             # noqa: E402
from guppi_runtime.testlab import TestLab, default_path                              # noqa: E402

VARIANTS = {
    "baseline": {},
    "fa_off": {"flash_attn": "off"},
    "graphs_off": {"env": {"GGML_CUDA_DISABLE_GRAPHS": "1"}},
    "fa_off_graphs_off": {"flash_attn": "off", "env": {"GGML_CUDA_DISABLE_GRAPHS": "1"}},
    "engine_b11160": {"engine_build": "b11160"},              # Unsloth's CUDA 13 build: no crash in a short test on 2026-10-03
    "ctx8k_ubatch256": {"context": 8192, "server": {"ubatch": 256}},
    "engine_b11530": {"engine_build": "b11530", "flash_attn": "on"},          # 2026-10-09: the newest official CUDA 12.4 build (installed next to b11371), flash attention ON, new driver 617.42
    "fa_on_new_driver": {"flash_attn": "on"},                                  # 2026-10-09: the installed b11371 with flash attention ON under the new driver (617.42; the 2026-10-05 tests ran with 616.92)
    "fa_on_blocking": {"flash_attn": "on", "env": {"CUDA_LAUNCH_BLOCKING": "1"}},             # 2026-10-09: every CUDA call waits for its result, so the error names the kernel that really fails (illegal memory access is reported later by default)
    "engine_b11530_blocking": {"engine_build": "b11530", "flash_attn": "on", "env": {"CUDA_LAUNCH_BLOCKING": "1"}},
    "sanitizer_fa_on": {"flash_attn": "on", "sanitizer": True, "env": {"GGML_CUDA_DISABLE_GRAPHS": "1"}},      # 2026-10-09: the server runs under NVIDIA compute-sanitizer (memcheck): the report names the kernel and the bad address
    "sanitizer_b11530_fa_on": {"engine_build": "b11530", "flash_attn": "on", "sanitizer": True, "env": {"GGML_CUDA_DISABLE_GRAPHS": "1"}},
    "sanitizer_fa_off": {"flash_attn": "off", "sanitizer": True, "env": {"GGML_CUDA_DISABLE_GRAPHS": "1"}},       # control: the same tool with flash attention off (is anything out of bounds there too?)
    "fa_on_kvq8": {"flash_attn": "on", "server": {"kv_cache_type": "q8_0"}},      # flash attention on and a quantized KV cache (what FA makes possible)
}
SANITIZER = RUNTIME.parent / "engines" / "tools" / "compute-sanitizer-12.4.127" / "cuda_sanitizer_api-windows-x86_64-12.4.127-archive" / "compute-sanitizer" / "compute-sanitizer.exe"
CRASH = (ConnectionError, urllib.error.URLError, OSError)
ALL_VARIANTS = "baseline,fa_off,engine_b11160"


def recipe_model(project, recipe_id):
    """A model as its recipe in role_routing.yaml starts it (server profile and recommended window), tool repair load."""
    import yaml
    recipes = yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"]
    recipe = next(r for r in recipes if r["id"] == recipe_id)
    return {"alias": recipe["model"], "server": dict(recipe["profile"]["server"]), "context": recipe["profile"]["context"]["recommended"], "workload": "repair", "big_window": dict(recipe["profile"].get("big_window_server") or {}),
            "recipe_id": recipe_id}      # 2026-10-12: the window cap is looked up by THIS recipe, not by the model name several recipes share


def model_spec(name, project):
    if name == "jan": return {"alias": st.CODER["alias"], "server": {"gguf": str(st.CODER["gguf"])}, "context": st.CONTEXT, "workload": "repair"}
    if name == "swe": return {"alias": st.REVIEWER["alias"], "server": {"gguf": str(st.REVIEWER["gguf"])}, "context": st.CONTEXT, "workload": "review"}
    return recipe_model(project, "coder.llama_qwen3_coder" if name == "qwen3coder" else name)      # any other name: a recipe id (coder.llama_gptoss, verifier.llama_gemma, ...)


PROBE_TEXT = "".join(t["code"] for t in TASKS) * 3 + "\nExplain in detail what each function above does, one paragraph per function."


def speed_probe(runtime, alias, reps=3):
    """Median prompt and generation tokens/s from the server's own timings, same prompt every time."""
    import json, statistics, urllib.request
    rows = []
    for _ in range(reps):
        body = {"model": alias, "messages": [{"role": "user", "content": PROBE_TEXT}], "max_tokens": 256, "temperature": 0, "cache_prompt": False}
        req = urllib.request.Request(runtime.endpoint + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.loads(r.read())
        t = data.get("timings") or {}
        rows.append((t.get("prompt_n"), t.get("prompt_per_second"), t.get("predicted_per_second")))
    ok = [r for r in rows if r[1] and r[2]]
    if not ok: return None
    return {"prompt_tokens": ok[0][0], "prompt_tps": round(statistics.median(r[1] for r in ok), 1), "gen_tps": round(statistics.median(r[2] for r in ok), 1)}


def driver_events():
    """Number of nvlddmkm entries in the System log (driver resets / TDR)."""
    text = gpu_preflight._powershell("(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='nvlddmkm'} -ErrorAction SilentlyContinue | Measure-Object).Count")
    return int(text) if text.strip().isdigit() else None


def one_run(variant, spec, args, log, project, model):
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    if spec.get("engine_build"): config.engine_build = spec["engine_build"]
    if spec.get("sanitizer"):
        config.startup_timeout_s = 900      # under the sanitizer the model needs minutes to load
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_crashhunt_")))
    if spec.get("sanitizer"):
        runtime.launcher = (str(SANITIZER), "--tool", "memcheck", "--print-limit", "20", "--show-backtrace", "no")
    if not runtime.available(): return {"error": f"engine_not_available:{spec.get('engine_build')}"}
    server = {**model["server"], **spec.get("server", {})}
    if "flash_attn" in spec: server["flash_attn"] = spec["flash_attn"]
    saved = {k: os.environ.get(k) for k in spec.get("env", {})}
    os.environ.update(spec.get("env", {}))
    work = Path(tempfile.mkdtemp(prefix="guppi_crashhunt_files_"))
    events0, done, crash, speed, t0 = driver_events(), 0, None, None, time.monotonic()
    try:
        runtime.load_model(model["alias"], context_length=spec.get("context", model["context"]), gpu="max", identifier=model["alias"], parallel=1, server=server)
        plain = st.post_factory(runtime.endpoint)
        speed = speed_probe(runtime, model["alias"])

        def post(body):
            nonlocal done
            out = plain(body); done += 1
            return out
        n = 0
        while done < args.requests:
            task = TASKS[n % len(TASKS)]; n += 1
            folder = work / f"{task['id']}_{n}"; folder.mkdir(parents=True)
            (folder / "mod.py").write_text(task["code"], encoding="utf-8"); (folder / "failure.txt").write_text(st.failure_text(task, []), encoding="utf-8")
            if model["workload"] == "repair":
                res = st.repair(post, {"task": task, "folder": folder})
            else:       # review: the buggy original is the "candidate", the verdict does not matter, the load does
                res = st.review(post, {"task": task, "folder": folder, "candidate": {"code": task["code"]}}, "tools")
            if res.get("error") and res.get("finish") == "error":
                raise ConnectionError(res["error"])
    except CRASH as exc:
        log_file = runtime.state_dir / "server.log"
        tail = log_file.read_text(encoding="utf-8", errors="replace")[-1500:] if log_file.is_file() else ""
        crash = {"error": f"{type(exc).__name__}: {str(exc)[:120]}", "cuda_error": "CUDA error" in tail, "log_tail": tail}
    finally:
        try: runtime.unload_model(all_models=True)
        except Exception: pass
        for k, v in saved.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        time.sleep(2)
    events1 = driver_events()
    return {"requests": done, "crashed": crash is not None, "crash": crash, "speed": speed, "seconds": round(time.monotonic() - t0),
            "driver_events_new": (events1 - events0) if events0 is not None and events1 is not None else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--runs", type=int, default=2); ap.add_argument("--requests", type=int, default=150)
    ap.add_argument("--model", default="jan", help="jan | swe | qwen3coder | a recipe id such as coder.llama_gptoss or verifier.llama_gemma"); ap.add_argument("--variants", default=",".join(VARIANTS))
    args = ap.parse_args()
    project = Path(args.project)
    names = [v for v in args.variants.split(",") if v in VARIANTS]
    model = model_spec(args.model, project)
    log = RunLog(project / "runtime_data" / "measurements", f"cuda_crash_hunt_{args.model}", config={"model": model["alias"], "runs": args.runs, "requests": args.requests, "variants": names})
    result = {"model": model["alias"], "requests_per_run": args.requests, "variants": {}}
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "cuda_crash_hunt"), f"cuda crash hunt: {model['alias']}", ttl_s=1800, wait_s=3600,
                                                  preflight=clear_leftovers):
        for name in names:
            rows = []
            log.say(f"== {name} {VARIANTS[name]}")
            for i in range(args.runs):
                row = one_run(name, VARIANTS[name], args, log, project, model)
                rows.append(row)
                log.say(f"   run {i + 1}: " + (f"error {row['error']}" if "error" in row else
                        f"{'CRASH' if row['crashed'] else 'clean'} after {row['requests']} requests, {row['seconds']} s, new driver events {row['driver_events_new']}, speed {row['speed']}"
                        + (f" ({row['crash']['error']}, CUDA error in log: {row['crash']['cuda_error']})" if row["crashed"] else "")))
                result["variants"][name] = {"spec": VARIANTS[name], "runs": rows}
                log.save(result)
            survived = [r for r in rows if "error" not in r and not r["crashed"]]
            log.say(f"  -> {name}: {len(survived)}/{len(rows)} runs clean, requests until crash {[r.get('requests') for r in rows if r.get('crashed')]}")
    log.say(f"DONE -> {log.json_path.name}")


if __name__ == "__main__":
    main()
