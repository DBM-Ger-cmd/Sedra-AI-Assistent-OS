r"""moe_sweep through the gate system (Captain 2026-10-10): how many expert layers must stay in RAM for a MoE recipe on THIS PC.

    .venv\Scripts\python.exe benchmarks/probes/moe_probe.py <project_dir> [--models coder.local_q4km]

The manager starts it as `probe_moe` (options file seeds/probe_moe.options.json: models (recipe ids), window, moe (list of n_cpu_moe), ubatch (list), prompt_tokens).
It only calls benchmarks/moe_sweep.py (a measurement; it holds the GPU lease, stops below the 1 GiB reserve, and changes no recipe). Defaults: window 32768, moe 44,40,36,32,28, ubatch 1024.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
RECIPE = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{1,60}")


def numbers(value, low, high, default):
    """A list of 1..8 integers in [low, high]; anything else gives the default."""
    ok = isinstance(value, list) and 1 <= len(value) <= 8 and all(type(v) is int and low <= v <= high for v in value)
    return ",".join(str(v) for v in value) if ok else default


def command(python, project, recipe, options):
    window = options.get("window")
    window = window if type(window) is int and 4096 <= window <= 65536 else 32768
    prompt = options.get("prompt_tokens")
    prompt = prompt if type(prompt) is int and 1000 <= prompt <= 24000 else 16000
    return [python, str(RUNTIME / "benchmarks" / "moe_sweep.py"), str(project), recipe, "--window", str(window), "--moe", numbers(options.get("moe"), 1, 99, "44,40,36,32,28"),
            "--ubatch", numbers(options.get("ubatch"), 128, 4096, "1024"), "--prompt-tokens", str(prompt)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--models", default="")
    args = ap.parse_args()
    try:
        options = json.loads((Path(args.project) / "runtime_data" / "agent_manager" / "seeds" / "probe_moe.options.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        options = {}
    options = options if isinstance(options, dict) else {}
    recipes = [m for m in args.models.split(",") if RECIPE.fullmatch(m)] or [m for m in (options.get("models") or []) if isinstance(m, str) and RECIPE.fullmatch(m)]
    if not recipes:
        print("no recipe given"); sys.exit(2)
    for recipe in recipes[:2]:
        print(f"== {recipe}", flush=True)
        done = subprocess.run(command(sys.executable, args.project, recipe, options), cwd=str(RUNTIME), text=True, errors="replace")
        print(f"{recipe}: moe_sweep exit {done.returncode}", flush=True)
    print("PROBE DONE")


if __name__ == "__main__":
    main()
