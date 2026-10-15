r"""Which model is a useful second pair of eyes? (Captain 2026-10-10: a second instance only pays off if it finds faults the developer overlooks, and without false alarms.)

    .venv\Scripts\python.exe benchmarks/probes/review_probe.py <project_dir> [--models coder.local_primary,qwen3coder,swe] [--per-stage 4] [--trials 1]

Ground truth like the checker probe (benchmarks/probes/checker_probe.py): for each of the four stages of bench_std the files of the REFERENCE solution (the reviewer must say PASS) and a few faulty versions, the "mutants" of the
reference that the hidden test of the stage really catches (the reviewer must say FAIL). The reviewer (the real reviewer role of the DevVM: read-only tools, `submit_review` with PASS or FAIL) gets the task text and the files
in the workspace. Per model: catch rate (FAIL on faulty versions), false-alarm rate (FAIL on the reference). A review is useful when it catches at least 70 % and raises a false alarm in at most 25 % of the stages.
The reviewer never runs code. Holds the GPU lease. Results: runtime_data/measurements/review_probe_<stamp>.json, one line per model and trial ("<model> review catch k/n false alarms j/m ...").
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
sys.path.insert(0, str(RUNTIME / "benchmarks" / "probes"))

GOOD_CATCH = 0.7
MAX_FALSE_ALARMS = 0.25

PROMPT = ("The overall task of the developer:\n{task}\n\nThe developer says the work is done. All files of the work are in the workspace. Check EVERY requirement and every concrete example of the task against the code, one by one "
          "(read the files with read_file; you cannot run code). PASS only if all are met; otherwise FAIL and name the missing or wrong requirement.")


def rate(rows):
    """{catch, false_alarm, useful} from the rows [{"kind": "reference"|"mutant", "verdict": "PASS"|"FAIL"|None}] (no verdict counts as a miss for a mutant and as no alarm for the reference)."""
    mutants = [r for r in rows if r["kind"] == "mutant"]
    refs = [r for r in rows if r["kind"] == "reference"]
    caught = sum(1 for r in mutants if r.get("verdict") == "FAIL")
    alarms = sum(1 for r in refs if r.get("verdict") == "FAIL")
    catch = caught / len(mutants) if mutants else 0.0
    false_alarm = alarms / len(refs) if refs else 0.0
    return {"caught": caught, "mutants": len(mutants), "false_alarms": alarms, "references": len(refs), "catch": round(catch, 2), "false_alarm": round(false_alarm, 2),
            "useful": bool(mutants) and catch >= GOOD_CATCH and false_alarm <= MAX_FALSE_ALARMS}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--models", default="coder.local_primary")
    ap.add_argument("--per-stage", type=int, default=4)
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--context", default="32768")
    args = ap.parse_args()
    project = Path(args.project)

    import devvm_agents_bench as bench
    from checker_probe import real_faults
    from guppi_runtime.acceptance_suite import host_runner, load_suite
    from guppi_runtime.devvm import DevWorkspace
    from guppi_runtime.devvm_agents import DevOrchestrator, ModelHost
    from guppi_runtime.gpu_preflight import clear_leftovers
    from guppi_runtime.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
    from guppi_runtime.run_log import RunLog
    from guppi_runtime.testlab import TestLab, default_path

    spec = importlib.import_module("devvm_specs.bench_std")
    stages = {s["name"]: s for s in spec.STAGES}
    suite = load_suite(str(project / "acceptance" / "suites" / "bench_std"))
    reference = dict(suite.reference)
    host_run = host_runner(timeout=60)
    faults = {name: real_faults(suite, name, reference, host_run, args.per_stage) for name in stages}
    print({name: len(found) for name, found in faults.items()}, "real faults per stage", flush=True)

    log = RunLog(project / "runtime_data" / "measurements", "review_probe", config=vars(args))
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_reviewprobe_rt_")))
    tool_root = Path(tempfile.mkdtemp(prefix="guppi_reviewprobe_"))
    policy = {"max_files": 40, "max_file_bytes": 60000, "max_input_bytes": 200000}
    context = 32768 if args.context == "max" else int(args.context)
    rows, counter = [], 0
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "review_probe"), "review probe", ttl_s=1800, wait_s=36000, preflight=clear_leftovers):
        for model in [m for m in args.models.split(",") if m]:
            host = ModelHost(bench.BenchLoader(runtime, project, {"planner": model}, log, context=context, server_extra={"reasoning": "off"}))
            try:
                for trial in range(1, args.trials + 1):
                    mine = []
                    for name, stage in stages.items():
                        items = [("reference", None, reference)] + [("mutant", f"{f}:{k}:{i}", {**reference, f: changed}) for f, k, i, changed in faults[name]]
                        for kind, label, files in items:
                            counter += 1
                            ws = DevWorkspace(tool_root, f"M-REV{counter:04d}", policy=dict(policy))
                            ws.create()
                            for fname, text in files.items():
                                if fname.endswith(".py") and not fname.startswith(("hidden", "acceptance")):
                                    ws.write(fname, text)
                            team = DevOrchestrator(ws, host, {"planner": model, "coder": model, "coder_strong": model, "reviewer": model}, mode="escalating", context=context, say=log.say)
                            started = time.monotonic()
                            run = team._agent("reviewer", PROMPT.format(task=stage["task"]), "reviewer")
                            verdict = (run.get("final") or {}).get("verdict")
                            row = {"model": model, "trial": trial, "stage": name, "kind": kind, "fault": label, "verdict": verdict, "stopped_by": run["stopped_by"], "seconds": round(time.monotonic() - started, 1)}
                            mine.append(row)
                            rows.append(row)
                    result = rate(mine)
                    print(f"{model:28s} review trial {trial} catch {result['caught']}/{result['mutants']} false alarms {result['false_alarms']}/{result['references']}  useful {result['useful']}", flush=True)
            finally:
                host.close()
    out = project / "runtime_data" / "measurements" / f"review_probe_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({"args": vars(args), "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written: {out}")
    print("PROBE DONE")


if __name__ == "__main__":
    main()
