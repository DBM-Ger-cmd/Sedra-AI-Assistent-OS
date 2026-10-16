r"""STANDARD BENCHMARK for model test runs (Captain 2026-10-09): the same short task for every model, one after the other, the results in the comparison table.

    .venv\Scripts\python.exe benchmarks/probes/stdbench_probe.py <project_dir> [--models coder.local_primary,qwen3coder] [--trials 1] [--reasoning off]

For every model and trial it runs `benchmarks/devvm_build.py --spec bench_std` (four small stages, hidden tests only, see devvm_specs/bench_std.py) with FIXED settings: one model for every role (--all-models), 32768 window, tidy, one rework round,
the seed folder benchmarks/bench_std_seed. Then it prints one line per run ("<model> right k/4 ...") and rebuilds docs/MODELL_VERGLEICH_ERGEBNISSE.md. The manager starts it as the probe `probe_stdbench`
(options file seeds/probe_stdbench.options.json: models, trials). Each run holds the GPU lease on its own. Nothing is integrated.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
SEED = RUNTIME / "benchmarks" / "bench_std_seed"
STAGES = 4


def command(python, project, model, reasoning="off", context="32768", mode="escalating", reasoning_budget=None, server_set=()):
    """The fixed command of one standard run. reasoning_budget: the most thinking tokens per answer (only with reasoning on)."""
    return [python, str(RUNTIME / "benchmarks" / "devvm_build.py"), str(project), "--spec", "bench_std", "--seed", str(SEED), "--attempts", "1", "--rework", "1", "--coder", model, "--all-models", model,
            "--context", context, "--tidy", "--reasoning", reasoning, "--mode", mode.split("-")[0]] + (["--self-check", mode.split("-")[1]] if "-" in mode else []) + (["--reasoning-budget", str(reasoning_budget)] if reasoning_budget is not None else []) + [arg for item in server_set for arg in ("--server-set", item)]


def summary_line(model, record, trial=1, mode="escalating"):
    """One result line: 'model right k/4 ...' from the attempt row of the build's JSON."""
    stages = record.get("stages", [])
    passed = sum(1 for s in stages if s.get("hidden_passed"))
    names = ",".join(f"{s['stage']}={'ok' if s.get('hidden_passed') else 'FAIL'}" for s in stages)
    return f"{model:24s} {mode:10s} trial {trial} right {passed}/{STAGES}  {record.get('seconds')} s  {record.get('calls')} calls  {names}"


def newest_record(project, after):
    logs = Path(project) / "runtime_data" / "measurements" / "logs"
    files = sorted((f for f in logs.glob("devvm_build_bench_std_*.json") if f.stat().st_mtime >= after), key=lambda f: f.stat().st_mtime)
    if not files:
        return None
    attempts = json.loads(files[-1].read_text(encoding="utf-8")).get("attempts") or []
    return attempts[-1] if attempts else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--models", default="coder.local_primary,qwen3coder")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--modes", default="escalating", help="the ways of working to compare, one after the other: escalating, solo, solo-light (one small check, 2 VM runs), solo-none (cannot run code)")
    ap.add_argument("--reasoning", choices=["auto", "on", "off"], default="off")
    ap.add_argument("--reasoning-budget", type=int, help="most thinking tokens per answer (-1 unlimited, 0 none); sent to the server as --reasoning-budget")
    ap.add_argument("--server-set", action="append", default=[], metavar="KEY=VALUE", help="passed to devvm_build: a server setting for every model (e.g. flash_attn=on)")
    args = ap.parse_args()
    project = Path(args.project)
    for model in [m for m in args.models.split(",") if m]:
        for mode in [m for m in args.modes.split(",") if m]:
            for trial in range(1, args.trials + 1):
                started = time.time()
                done = subprocess.run(command(sys.executable, project, model, args.reasoning, mode=mode, reasoning_budget=args.reasoning_budget, server_set=args.server_set), cwd=str(RUNTIME), capture_output=True, text=True, errors="replace")
                record = newest_record(project, started - 1)
                print(summary_line(model, record, trial, mode) if record else f"{model:24s} {mode:10s} trial {trial} right 0/{STAGES}  (the build wrote no result: exit {done.returncode}) {done.stderr[-200:]!r}", flush=True)
    subprocess.run([sys.executable, str(RUNTIME / "benchmarks" / "model_compare.py"), str(project), "--out", str(RUNTIME.parent / "docs" / "MODELL_VERGLEICH_ERGEBNISSE.md")], capture_output=True)
    print("PROBE DONE")


if __name__ == "__main__":
    main()
