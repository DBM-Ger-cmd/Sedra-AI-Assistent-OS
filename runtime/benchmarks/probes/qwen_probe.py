r"""Qwen Code against our solo developer, through the gate system (Captain 2026-10-10).

    .venv\Scripts\python.exe benchmarks/probes/qwen_probe.py <project_dir> [--models coder.local_primary] [--modes qwen-none,qwen-light] [--trials 1] [--specs bench_std] [--stage <name>] [--seed <path below runtime_data/devvm_snapshots>] [--reasoning off]

For every model, spec, way of checking and trial it runs `benchmarks/qwen_build.py` (Qwen Code confined to GUPPI's MCP server, same model server, same workspace, same hidden test) and prints one line "<model> <mode> ... right k/n ...".
The ways: qwen-none (the agent cannot run code), qwen-light (one small check, 2 VM runs), qwen-full (up to 8 VM runs). A single hard stage can be repeated with --stage and --seed (a snapshot taken after the stage before). The manager starts it as `probe_qwen`
(options file seeds/probe_qwen.options.json: models, modes, trials, specs, stage, seed, reasoning). The tool-list check of qwen_build.py runs before every trial; a trial that is not confined stops the probe with exit 3. Holds the GPU lease per trial.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
SELF_CHECK = {"qwen-none": "none", "qwen-light": "light", "qwen-full": "full", "qwen-append-none": "none", "qwen-lean-none": "none", "qwen-lean-light": "light"}
SYSTEM_MODE = {"qwen-append-none": "append", "qwen-lean-none": "lean", "qwen-lean-light": "lean"}      # the others use Qwen Code's own system prompt


def command(python, project, spec, model, mode, reasoning="off", stage=None, seed=None, context="32768"):
    """The fixed command of one trial."""
    cmd = [python, str(RUNTIME / "benchmarks" / "qwen_build.py"), str(project), "--spec", spec, "--coder", model, "--self-check", SELF_CHECK[mode], "--reasoning", reasoning, "--context", context, "--system", SYSTEM_MODE.get(mode, "asis")]
    if stage: cmd += ["--only", stage]
    if seed: cmd += ["--seed", str(Path(project) / "runtime_data" / "devvm_snapshots" / seed)]
    return cmd


def safe_seed(seed):
    """A seed is a relative path below runtime_data/devvm_snapshots, nothing else."""
    if not seed: return None
    parts = Path(seed).parts
    if Path(seed).is_absolute() or seed.startswith(("/", "\\")) or ":" in seed or ".." in parts or not parts: raise ValueError("bad_seed")
    return seed


def newest_record(project, spec, after):
    logs = Path(project) / "runtime_data" / "measurements" / "logs"
    files = sorted((f for f in logs.glob(f"devvm_build_{spec}_*.json") if f.stat().st_mtime >= after), key=lambda f: f.stat().st_mtime)
    if not files: return None
    attempts = json.loads(files[-1].read_text(encoding="utf-8")).get("attempts") or []
    return attempts[-1] if attempts else None


def summary_line(model, mode, spec, record, trial=1):
    stages = record.get("stages", [])
    passed = sum(1 for s in stages if s.get("hidden_passed"))
    names = ",".join(f"{s['stage']}={'ok' if s.get('hidden_passed') else 'FAIL'}" for s in stages)
    return f"{model:24s} {mode:10s} {spec} trial {trial} right {passed}/{len(stages)}  {record.get('seconds')} s  {record.get('calls')} calls  reworks {sum(s.get('reworks', 0) for s in stages)}  {names}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--models", default="coder.local_primary")
    ap.add_argument("--modes", default="qwen-none")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--specs", default="bench_std")
    ap.add_argument("--stage")
    ap.add_argument("--seed")
    ap.add_argument("--reasoning", default="off")
    args = ap.parse_args()
    project = Path(args.project)
    seed = safe_seed(args.seed)
    for model in [m for m in args.models.split(",") if m]:
        for spec in [s for s in args.specs.split(",") if s]:
            for mode in [m for m in args.modes.split(",") if m in SELF_CHECK]:
                for trial in range(1, args.trials + 1):
                    started = time.time()
                    done = subprocess.run(command(sys.executable, project, spec, model, mode, args.reasoning, args.stage, seed), cwd=str(RUNTIME), capture_output=True, text=True, errors="replace")
                    if done.returncode == 3:
                        print(f"{model:24s} {mode:10s} {spec} trial {trial}  NOT CONFINED: stopped before any model call", flush=True)
                        sys.exit(3)
                    record = newest_record(project, spec, started - 1)
                    print(summary_line(model, mode, spec, record, trial) if record else f"{model:24s} {mode:10s} {spec} trial {trial} right 0/0  (no result: exit {done.returncode}) {done.stderr[-200:]!r}", flush=True)
    subprocess.run([sys.executable, str(RUNTIME / "benchmarks" / "model_compare.py"), str(project), "--out", str(RUNTIME.parent / "docs" / "MODELL_VERGLEICH_ERGEBNISSE.md")], capture_output=True)
    print("PROBE DONE")


if __name__ == "__main__":
    main()
