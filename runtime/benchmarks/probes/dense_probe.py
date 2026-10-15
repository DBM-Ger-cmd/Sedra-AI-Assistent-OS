r"""Layers on the GPU for a DENSE model (Qwen3.8-27B) on THIS PC, with and without MTP, through the gate system (Captain 2026-10-10).

    .venv\Scripts\python.exe benchmarks/probes/dense_probe.py <project_dir> [--models coder.local_q38]

The manager starts it as `probe_dense` (options file seeds/probe_dense.options.json: models (recipe ids), window, ngl (list of n_gpu_layers), mtp (true: also measure with MTP), prompt_tokens).
For every n_gpu_layers (ascending, MTP off) the recipe's server is started, one prompt of real GUPPI source is answered (benchmarks/moe_sweep.py `one`), and the speed and the free VRAM are recorded; the ascending part stops
below the 1 GiB reserve or at a failed start. Then the two highest layer counts inside the reserve are measured again with MTP on (if the options ask for it). It holds the GPU lease and changes no recipe.
Results: runtime_data/measurements/dense_probe_<recipe>_<date>.json.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RUNTIME / "src"), str(RUNTIME / "benchmarks")]
RECIPE = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{1,60}")


def int_list(value, low, high, default):
    ok = isinstance(value, list) and 1 <= len(value) <= 12 and all(type(v) is int and low <= v <= high for v in value)
    return sorted(set(value)) if ok else default


def plan(fitting, with_mtp):
    """The layer counts that get the MTP measurement: the two highest ones that stayed inside the reserve."""
    return sorted(fitting)[-2:] if with_mtp else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--models", default="")
    args = ap.parse_args()
    project = Path(args.project)
    try:
        options = json.loads((project / "runtime_data" / "agent_manager" / "seeds" / "probe_dense.options.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        options = {}
    options = options if isinstance(options, dict) else {}
    recipes = [m for m in args.models.split(",") if RECIPE.fullmatch(m)] or [m for m in (options.get("models") or []) if isinstance(m, str) and RECIPE.fullmatch(m)]
    if not recipes:
        print("no recipe given")
        sys.exit(2)
    import yaml
    from context_ladder import RESERVE_GIB
    from guppi_runtime.gpu_preflight import clear_leftovers
    from guppi_runtime.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
    from guppi_runtime.testlab import TestLab, default_path
    from moe_sweep import RAM_FLOOR_GIB, free_ram_gib, one, source_text
    window = options.get("window") if type(options.get("window")) is int and 4096 <= options["window"] <= 65536 else 32768
    ngl_list = int_list(options.get("ngl"), 0, 99, [24, 28, 32, 36, 40, 44])
    with_mtp = options.get("mtp") is True
    tokens = options.get("prompt_tokens") if type(options.get("prompt_tokens")) is int and 1000 <= options["prompt_tokens"] <= 24000 else 16000
    table = {r["id"]: r for r in yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"]}
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_dense_")))
    prompt = source_text(int(tokens * 3.2))
    recipe_id = recipes[0]
    recipe = table[recipe_id]
    alias = str(recipe.get("model") or recipe_id)
    out = project / "runtime_data" / "measurements" / f"dense_probe_{recipe_id}_{date.today().isoformat()}_{time.strftime('%H%M%S')}.json"
    rows = []

    def measure(ngl, mtp):
        if free_ram_gib() < RAM_FLOOR_GIB:
            print(f"  ngl {ngl} mtp {mtp}: not started, RAM below the floor", flush=True)
            return None
        server = {**recipe["profile"]["server"], "n_gpu_layers": ngl, "mtp": mtp}
        try:
            row = one(runtime, alias, server, window, prompt)
        except Exception as exc:
            row = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        row.update(n_gpu_layers=ngl, mtp=mtp, window=window)
        row["within_reserve"] = row.get("free_gib", 0) >= RESERVE_GIB
        rows.append(row)
        print(f"  ngl {ngl:2d} mtp {mtp}: {row}", flush=True)
        out.write_text(json.dumps({"recipe": recipe_id, "rows": rows}, indent=2), encoding="utf-8")
        return row

    with TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "dense_probe"), "dense probe " + recipe_id, ttl_s=3600, wait_s=1800, preflight=clear_leftovers):
        fitting = []
        for ngl in ngl_list:
            row = measure(ngl, False)
            if row is None or "error" in row or not row["within_reserve"]:
                break
            fitting.append(ngl)
        for ngl in plan(fitting, with_mtp):
            measure(ngl, True)
    print(f"  DONE -> {out.name}", flush=True)
    print("PROBE DONE")


if __name__ == "__main__":
    main()
