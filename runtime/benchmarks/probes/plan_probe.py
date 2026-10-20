r"""Which model makes the best step plan? (Captain 2026-10-10: before more tasks are run, check the step plan against the models we have.)

    .venv\Scripts\python.exe benchmarks/probes/plan_probe.py <project_dir> [--models coder.local_primary,qwen3coder] [--specs am007_crews,am009_collector] [--reasoning off] [--reasoning-budget N] [--trials 1]

For every model, spec and stage it runs ONLY the planner of the solo step plan (`DevOrchestrator.plan_solo`: the task in numbered lines in, steps with lines, interface and acceptance out). No developer, no hidden test: it is cheap
(a few minutes per model). The plan is rated with rules that can be checked without a judge:
  - usable: the planner handed in a plan (not the fallback "whole task is one step");
  - a task over the split limit (5.5 % of the window in characters) is cut into at least two steps;
  - coverage: the share of the numbered task lines that at least one step claimed (lines nobody claims go to every step, so nothing is lost, but a high share means the planner did the assignment);
  - every step of a plan with several steps names its interface;
  - the largest extract a step gets, as a share of the whole task (how much shorter the history can become).
"right" = usable, split when required, coverage >= 60 %, interfaces for every step of a multi-step plan. The real test of a plan is the hidden test of the stage (a build run); this probe only says which model plans in the form
the workflow needs. Holds the GPU lease. Results: runtime_data/measurements/plan_probe_<stamp>.json, one line per model and trial ("<model> plan right k/n ...").
"""
import argparse
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

MIN_COVERAGE = 0.6


def plan_metrics(task, units, steps, fallback, split_at, seconds=0.0):
    """The rating of one plan (see the module text). `steps` are the cleaned steps of the planner."""
    from guppi_runtime.devenv.solo_steps import extract_for
    count = len(units)
    claimed = set()
    for s in steps:
        claimed |= {k for k in (s.get("lines") or []) if isinstance(k, int) and 1 <= k <= count}
    coverage = len(claimed) / count if count else 0.0
    must_split = len(task) > split_at
    split_ok = (not must_split) or len(steps) >= 2
    interfaces = len(steps) == 1 or all(s.get("interface") for s in steps)
    largest = max((len(extract_for(s, steps, units)) for s in steps), default=0) / max(1, len("\n".join(units)))
    right = (not fallback) and split_ok and interfaces and (coverage >= MIN_COVERAGE or len(steps) == 1)
    return {"usable": not fallback, "steps": len(steps), "must_split": must_split, "split_ok": split_ok, "coverage": round(coverage, 2), "interfaces": interfaces,
            "largest_extract": round(largest, 2), "seconds": round(seconds, 1), "right": right}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--models", default="coder.local_primary")
    ap.add_argument("--specs", default="am007_crews")
    ap.add_argument("--reasoning", default="off")
    ap.add_argument("--reasoning-budget", type=int, default=None)
    ap.add_argument("--context", default="32768")
    ap.add_argument("--trials", type=int, default=1)
    args = ap.parse_args()
    project = Path(args.project)

    import devvm_agents_bench as bench
    from devvm_build import without_test_duty
    from guppi_runtime.devenv.devvm import DevWorkspace
    from guppi_runtime.devenv.devvm_agents import DevOrchestrator, ModelHost
    from guppi_runtime.models.gpu_preflight import clear_leftovers
    from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
    from guppi_runtime.jobs.run_log import RunLog
    from guppi_runtime.devenv.solo_steps import number_task
    from guppi_runtime.jobs.testlab import TestLab, default_path

    log = RunLog(project / "runtime_data" / "measurements", "plan_probe", config=vars(args))
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_planprobe_rt_")))
    tool_root = Path(tempfile.mkdtemp(prefix="guppi_planprobe_"))
    policy = {"max_files": 40, "max_file_bytes": 60000, "max_input_bytes": 200000}
    extra = {"reasoning": args.reasoning}
    if args.reasoning_budget is not None:
        extra["reasoning_budget"] = args.reasoning_budget
    context = 32768 if args.context == "max" else int(args.context)
    rows, counter = [], 0
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "plan_probe"), "plan probe", ttl_s=1800, wait_s=36000, preflight=clear_leftovers):
        for model in [m for m in args.models.split(",") if m]:
            host = ModelHost(bench.BenchLoader(runtime, project, {"planner": model}, log, context=context, server_extra=extra))
            try:
                for trial in range(1, args.trials + 1):
                    mine = []
                    for spec_name in [s for s in args.specs.split(",") if s]:
                        spec = importlib.import_module("devvm_specs." + spec_name)
                        seed = project / "runtime_data" / "agent_manager" / "seeds" / spec_name
                        for stage in spec.STAGES:
                            counter += 1
                            ws = DevWorkspace(tool_root, f"M-PLN{counter:04d}", policy=dict(policy))
                            ws.create()
                            if seed.is_dir():
                                for f in sorted(seed.glob("*.py")):
                                    ws.write(f.name, f.read_text(encoding="utf-8"))
                            team = DevOrchestrator(ws, host, {"planner": model, "coder": model, "coder_strong": model}, mode="solo", plan_steps=True, context=context, say=log.say)
                            task = without_test_duty(stage["task"])
                            units = number_task(task)
                            started = time.monotonic()
                            steps, fallback = team.plan_solo(task, units)
                            row = {"model": model, "trial": trial, "spec": spec_name, "stage": stage["name"], "task_chars": len(task), "titles": [s["title"] for s in steps],
                                   **plan_metrics(task, units, steps, fallback, team.split_at, time.monotonic() - started)}
                            mine.append(row)
                            rows.append(row)
                            log.say(f"plan {model} {spec_name}.{stage['name']}: steps {row['steps']} coverage {row['coverage']} right {row['right']}")
                    right = sum(1 for r in mine if r["right"])
                    detail = " ".join(f"{r['stage']}={r['steps']}{'ok' if r['right'] else 'x'}" for r in mine)
                    print(f"{model:28s} plan trial {trial} right {right}/{len(mine)}  {detail}", flush=True)
            finally:
                host.close()
    out = project / "runtime_data" / "measurements" / f"plan_probe_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({"args": vars(args), "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written: {out}")
    print("PROBE DONE")


if __name__ == "__main__":
    main()
