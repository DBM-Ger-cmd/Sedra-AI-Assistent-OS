"""Measure the VRAM numbers of routing recipes with the real llama-server (a measurement, not a test).

    python benchmarks/measure_recipe.py <project_dir_with_local_config> <recipe_id> [<recipe_id> ...] [--tiers 8192,16384] [--no-probe]
                                        [--mtp recipe|off] [--probe-tokens 2048] [--baseline-max 1.5] [--apply]

For each recipe: the model is started the way `profile.server` says, once per context tier (smallest first), the applied window and the GPU
memory are read, one short request is run (compute buffers grow during generation) and the model is unloaded again. The GPU must be idle
(nothing of LM Studio loaded, no game). Results go to <project>/runtime_data/measurements/<recipe_id>_<date>.json and are printed.

Without --apply nothing but that file is written. With --apply the three numbers (measured_context, measured_vram_gb,
kv_cache_gb_per_1k_tokens) are written into the recipe in local_config/role_routing.yaml, after a backup copy next to it. `maximum` and
`tiers` are never changed: this tool measures memory, not stability under long prompts.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path  # noqa: E402
from guppi_runtime.models.gpu_preflight import clear_leftovers
from guppi_runtime.models.recipe_measure import MeasureError, apply_measurements, http_generate, measure_recipe  # noqa: E402


def read_vram():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True).stdout
    return int(out.split()[0]) / 1024


def find_recipe(project, recipe_id):
    for path in (project / "local_config" / "role_routing.yaml", RUNTIME / "config" / "role_routing.yaml"):
        if path.exists():
            for item in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("role_routing", {}).get("capabilities", []) or []:
                if item.get("id") == recipe_id:
                    return item, path
    raise SystemExit(f"recipe not found: {recipe_id}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("recipes", nargs="+")
    ap.add_argument("--tiers", help="comma separated windows; default: the recipe's own tiers")
    ap.add_argument("--no-probe", action="store_true", help="skip the short request after each load")
    ap.add_argument("--probe-tokens", type=int, default=2048)
    ap.add_argument("--mtp", choices=("recipe", "off"), default="recipe", help="'off' forces MTP off for the measurement")
    ap.add_argument("--baseline-max", type=float, default=1.5, help="GiB the GPU may already use before the first load")
    ap.add_argument("--apply", action="store_true", help="write the measured numbers into local_config/role_routing.yaml (backup first)")
    args = ap.parse_args()

    project = Path(args.project)
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled, config.mtp = True, True              # the recipe decides MTP; --mtp off overrides it below
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_measure_")))
    if not runtime.available():
        raise SystemExit("llama-server not found")
    tiers = [int(t) for t in args.tiers.split(",")] if args.tiers else None
    out_dir = project / "runtime_data" / "measurements"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    lab = TestLab(default_path(project))
    with lab.lease(os.environ.get("TESTLAB_OWNER", "measure_recipe"), f"measure {','.join(args.recipes)}", ttl_s=600, wait_s=1800, preflight=clear_leftovers):
        measure_all(args, project, runtime, tiers, out_dir, today)


def measure_all(args, project, runtime, tiers, out_dir, today):
    for recipe_id in args.recipes:
        recipe, source = find_recipe(project, recipe_id)
        if args.mtp == "off":
            recipe = {**recipe, "profile": {**recipe["profile"], "server": {**recipe["profile"]["server"], "mtp": False}}}
        print(f"== {recipe_id} ({recipe.get('model')})", flush=True)
        generate = None if args.no_probe else (lambda alias, n: http_generate(runtime.endpoint, alias, n))
        try:
            result = measure_recipe(recipe, runtime, read_vram, tiers=tiers, generate=generate, probe_tokens=args.probe_tokens,
                                    baseline_max_gb=args.baseline_max, say=lambda line: print(line, flush=True))
        except MeasureError as exc:
            print(f"  not measured: {exc}")
            continue
        finally:
            runtime.unload_model(all_models=True)
        target = out_dir / f"{recipe_id}_{today}.json"
        target.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("  suggested:", json.dumps(result["suggested"]), "\n  written:", target)
        if args.apply and result["suggested"]:
            if source.parent.name != "local_config":
                print("  not applied: the recipe is in the shipped file, copy it to local_config/role_routing.yaml first")
                continue
            shutil.copy2(source, source.with_name(f"{source.name}.bak-{today}"))
            source.write_text(apply_measurements(source.read_text(encoding="utf-8"), recipe_id, result["suggested"], today=today), encoding="utf-8")
            print(f"  applied to {source.name} (backup {source.name}.bak-{today}); `maximum` and `tiers` unchanged")


if __name__ == "__main__":
    main()
