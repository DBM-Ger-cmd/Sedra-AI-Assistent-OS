r"""Balance of expert layers in host RAM vs. VRAM for a MoE recipe on THIS PC (a measurement, not a test).

    .venv\\Scripts\\python.exe benchmarks/moe_sweep.py <project_dir> <recipe_id> --window 49152 --moe 48,40,36,32 --ubatch 512,2048
        [--prompt-tokens 16000]

For every (n_cpu_moe, ubatch) the recipe's server is started with that window, one prompt of real GUPPI source (~prompt-tokens) is
answered (max 256 tokens), and the server's own timings (prompt and generation tokens/s) plus the free GPU memory after the answer are
recorded. A combination below the 1 GiB reserve is marked and the sweep does not go further down that ubatch (fewer layers in RAM
only needs more memory). Results: runtime_data/measurements/moe_sweep_<recipe>_<date>.json. Nothing in any recipe is changed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.request
from datetime import date
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from context_ladder import RESERVE_GIB, gpu_mib                                       # noqa: E402
from guppi_runtime.models.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path                             # noqa: E402


def source_text(n_chars):
    parts, size = [], 0
    for f in sorted((RUNTIME / "src" / "guppi_runtime").rglob("*.py")):
        t = f.read_text(encoding="utf-8")
        parts.append(f"# file: {f.name}\n{t}\n"); size += len(t)
        if size >= n_chars:
            break
    return "".join(parts)[:n_chars]


FULL_GPU_FLOOR_GIB = 0.25     # --full-gpu: below this much free VRAM Windows starts to spill into shared memory (speed collapses) or the start fails, so nothing goes further down
RAM_FLOOR_GIB = 3.0           # always leave 3 GB RAM free (Captain 2026-10-04)


def free_ram_gib():
    import ctypes

    class Status(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong), ("total_page", ctypes.c_ulonglong),
                    ("avail_page", ctypes.c_ulonglong), ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong), ("avail_ext", ctypes.c_ulonglong)]
    status = Status(); status.length = ctypes.sizeof(Status)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.avail_phys / 2 ** 30


def one(runtime, alias, server, window, prompt):
    runtime.load_model(alias, context_length=window, gpu="max", identifier=alias, parallel=1, server=server)
    try:
        body = json.dumps({"model": alias, "max_tokens": 256, "temperature": 0.1,
                           "messages": [{"role": "user", "content": prompt + "\n\nIn three sentences: what do these modules do?"}]}).encode()
        req = urllib.request.Request(runtime.endpoint + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=1800) as r:
            data = json.loads(r.read())
        used, total = gpu_mib()
        t = data.get("timings") or {}
        return {"prompt_tokens": (data.get("usage") or {}).get("prompt_tokens"), "prompt_tps": round(t.get("prompt_per_second") or 0, 1),
                "gen_tps": round(t.get("predicted_per_second") or 0, 1), "seconds": round(time.monotonic() - t0, 1),
                "free_gib": round((total - used) / 1024, 2)}
    finally:
        try:
            runtime.unload_model(all_models=True)
        except Exception:
            pass
        time.sleep(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("recipe")
    ap.add_argument("--window", type=int, default=49152); ap.add_argument("--moe", default="48,40,36,32")
    ap.add_argument("--ubatch", default="512,2048"); ap.add_argument("--prompt-tokens", type=int, default=16000)
    ap.add_argument("--server-json", help="JSON of extra server settings for every combination, e.g. '{\"kv_cache_type_k\": \"q8_0\"}' (2026-10-09: a quantized K cache works without flash attention)")
    ap.add_argument("--full-gpu", action="store_true", help="do not stop below the reserve: try every combination with all of the GPU (Captain 2026-10-09); a failed start still stops that ubatch")
    args = ap.parse_args()
    project = Path(args.project)
    recipes = {r["id"]: r for r in yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"]}
    recipe = recipes[args.recipe]
    alias = str(recipe.get("model") or recipe["id"])
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_moesweep_")))
    prompt = source_text(int(args.prompt_tokens * 3.2))
    rows = []
    out = project / "runtime_data" / "measurements" / f"moe_sweep_{args.recipe}_{date.today().isoformat()}_{time.strftime('%H%M%S')}.json"
    with TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "moe_sweep"), f"moe sweep {args.recipe}", ttl_s=1800,
                                              wait_s=1800, preflight=clear_leftovers):
        for ub in (int(x) for x in args.ubatch.split(",")):
            for moe in (int(x) for x in args.moe.split(",")):
                server = {**recipe["profile"]["server"], "n_cpu_moe": moe, "ubatch": ub, **(json.loads(args.server_json) if args.server_json else {})}
                ram = free_ram_gib()
                if ram < RAM_FLOOR_GIB:
                    print(f"  moe {moe:2d} ub {ub:4d}: not started, only {ram:.1f} GiB RAM free (floor {RAM_FLOOR_GIB})", flush=True)
                    break
                try:
                    row = one(runtime, alias, server, args.window, prompt)
                except Exception as exc:
                    row = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                row.update(n_cpu_moe=moe, ubatch=ub, window=args.window)
                row["within_reserve"] = row.get("free_gib", 0) >= RESERVE_GIB
                rows.append(row)
                print(f"  moe {moe:2d} ub {ub:4d}: {row}", flush=True)
                out.write_text(json.dumps({"recipe": args.recipe, "rows": rows}, indent=2), encoding="utf-8")
                spilled = bool(args.full_gpu and rows[:-1] and rows[-2].get("gen_tps") and row.get("gen_tps") and row["gen_tps"] < 0.75 * rows[-2]["gen_tps"] and rows[-2].get("ubatch") == ub)
                if "error" in row or spilled or (args.full_gpu and row.get("free_gib", 0) < FULL_GPU_FLOOR_GIB) or (not row["within_reserve"] and not args.full_gpu):
                    break
    print(f"  DONE -> {out.name}", flush=True)


if __name__ == "__main__":
    main()
