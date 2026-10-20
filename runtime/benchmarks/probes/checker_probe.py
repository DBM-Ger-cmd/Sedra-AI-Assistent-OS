r"""Which model writes the best acceptance check? (Captain 2026-10-09: the workflow with several models stays; every role gets the model that does it best, decided by data.)

    .venv\Scripts\python.exe benchmarks/probes/checker_probe.py <project_dir> [--models coder.local_primary,qwen3coder,swe] [--per-stage 8] [--trials 1]

In the DevVM the own check of the team agreed with the hidden test in only 31 of 60 cases (2026-10-09). This probe measures the CHECK WRITER on its own, with ground truth:
  1. For each of the four stages of bench_std the model gets the task text only (no code) and writes a check script (the real checker of the DevVM, `_write_check` with the check-first note).
  2. The check must PASS the reference solution of the stage (otherwise it is wrong: a false alarm) ...
  3. ... and must FAIL on the faulty versions: "mutants" of the reference (a comparison turned around, a number moved, a branch emptied) that the hidden test of the stage really catches. The share of caught
     mutants is the kill rate: a check that kills few mutants lets faulty code through.
A stage counts as "right" when the check is usable, passes the reference and kills at least 70 % of the real faults. Check scripts run in the microVM judge, never on the host. Holds the GPU lease.
Results: runtime_data/measurements/checker_probe_<stamp>.json and one line per model and trial ("<model> right k/4 ...").
"""
import argparse
import ast
import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(RUNTIME / "benchmarks"))

STAGE_FILES = {"slug": ("textkit.py",), "fix": ("ledger.py",), "extend": ("textkit.py",), "move": ("mathkit.py", "util.py", "main.py")}
SEEDED = ("fix", "move")      # the stages whose workspace already holds files (the seed folder)
GOOD_KILL_RATE = 0.7


def choose(items, count):
    """At most `count` items, evenly spread over the sorted list (the same choice every time)."""
    items = sorted(items)
    if len(items) <= count:
        return items
    step = len(items) / count
    return [items[int(i * step)] for i in range(count)]


def stage_is_right(valid, killed, total):
    return bool(valid) and total > 0 and killed / total >= GOOD_KILL_RATE


def real_faults(suite, stage, reference, host_run, per_stage):
    """The faulty versions of the stage's files that the hidden test of the stage catches: [(file, kind, index, source)]."""
    from suite_mutants import mutate, sites
    from guppi_runtime.selfdev.acceptance_suite import run_suite
    found = []
    for name in STAGE_FILES[stage]:
        source = reference[name]
        for kind, index in sites(ast.parse(source)):
            changed = mutate(source, kind, index)
            if changed is None or changed == source:
                continue
            found.append((name, kind, index, changed))
    sample = choose([(f, k, i) for f, k, i, _ in found], per_stage * 3)         # a wider sample, then the ones the hidden test really catches
    lookup = {(f, k, i): c for f, k, i, c in found}
    criterion = [c for c in suite.criteria if c["id"].endswith("." + stage)][0]["id"]
    script, text = suite.scripts[criterion]
    caught = []
    for f, k, i in sample:
        result = host_run({**reference, f: lookup[(f, k, i)], script: text}, [["python3", script]])
        if result["status"] == "failed":
            caught.append((f, k, i, lookup[(f, k, i)]))
    return choose(caught, per_stage)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--models", default="coder.local_primary,qwen3coder")
    ap.add_argument("--per-stage", type=int, default=8)
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--context", default="32768")
    args = ap.parse_args()
    project = Path(args.project)

    import devvm_agents_bench as bench
    from guppi_runtime.selfdev.acceptance_suite import host_runner, load_suite
    from guppi_runtime.selfdev.acceptance_vm import vm_runner
    from guppi_runtime.devenv.devvm import DevWorkspace
    from guppi_runtime.devenv.devvm_agents import CHECKER_FIRST_NOTE, DevOrchestrator, ModelHost
    from guppi_runtime.models.gpu_preflight import clear_leftovers
    from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
    from guppi_runtime.jobs.run_log import RunLog
    from guppi_runtime.jobs.testlab import TestLab, default_path

    spec = importlib.import_module("devvm_specs.bench_std")
    stages = {s["name"]: s for s in spec.STAGES}
    suite = load_suite(str(project / "acceptance" / "suites" / "bench_std"))
    reference = dict(suite.reference)
    seed = {p.name: p.read_text(encoding="utf-8") for p in (RUNTIME / "benchmarks" / "bench_std_seed").glob("*.py")}
    host_run = host_runner(timeout=60)
    faults = {name: real_faults(suite, name, reference, host_run, args.per_stage) for name in stages}
    print({name: len(found) for name, found in faults.items()}, "real faults per stage", flush=True)

    log = RunLog(project / "runtime_data" / "measurements", "checker_probe", config=vars(args))
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_checkerprobe_rt_")))
    vm = vm_runner(project, RUNTIME, mission="M-CHECKER")
    tool_root = Path(tempfile.mkdtemp(prefix="guppi_checkerprobe_"))
    policy = {"max_files": 40, "max_file_bytes": 60000, "max_input_bytes": 200000}
    rows, counter = [], 0
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "checker_probe"), "checker probe", ttl_s=1800, wait_s=3600, preflight=clear_leftovers):
        for model in [m for m in args.models.split(",") if m]:
            host = ModelHost(bench.BenchLoader(runtime, project, {"planner": model}, log, context=int(args.context), server_extra={"reasoning": "off"}))
            try:
                for trial in range(1, args.trials + 1):
                    per_stage = {}
                    for name, stage in stages.items():
                        counter += 1
                        ws = DevWorkspace(tool_root, f"M-CHK{counter:04d}", policy=dict(policy))
                        ws.create()
                        if name in SEEDED:
                            for file, text in seed.items():
                                ws.write(file, text)
                        team = DevOrchestrator(ws, host, {"planner": model, "coder": model, "coder_strong": model}, mode="escalating", say=log.say)
                        step = {"title": "task", "instruction": stage["task"], "acceptance": "", "check": ""}
                        started = time.monotonic()
                        team._write_check(stage["task"], step, CHECKER_FIRST_NOTE)
                        seconds = round(time.monotonic() - started, 1)
                        check = step.get("check") or ""
                        row = {"model": model, "trial": trial, "stage": name, "usable": bool(check), "check_chars": len(check), "seconds": seconds, "valid": False, "killed": 0, "total": len(faults[name])}
                        if check:
                            passes = vm({**reference, "acceptance_check.py": check + "\n"}, [["python3", "acceptance_check.py"]])
                            row["valid"] = passes["status"] == "completed"
                            row["reference_output"] = passes["output"][-300:]
                            if row["valid"]:
                                for f, k, i, changed in faults[name]:
                                    verdict = vm({**reference, f: changed, "acceptance_check.py": check + "\n"}, [["python3", "acceptance_check.py"]])
                                    row["killed"] += 1 if verdict["status"] == "failed" else 0
                        row["right"] = stage_is_right(row["valid"], row["killed"], row["total"])
                        per_stage[name] = row
                        rows.append(row)
                        log.say(f"checker {model} {name}: usable {row['usable']} valid {row['valid']} killed {row['killed']}/{row['total']}")
                    right = sum(1 for r in per_stage.values() if r["right"])
                    detail = " ".join(f"{n}={'ok' if r['right'] else ('invalid' if r['usable'] and not r['valid'] else 'weak' if r['valid'] else 'none')}({r['killed']}/{r['total']})" for n, r in per_stage.items())
                    print(f"{model:28s} checker trial {trial} right {right}/{len(stages)}  {detail}", flush=True)
            finally:
                host.close()
    out = project / "runtime_data" / "measurements" / f"checker_probe_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({"models": args.models, "per_stage": args.per_stage, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written: {out}")
    print("PROBE DONE")


if __name__ == "__main__":
    main()
