"""Probe: does the arbiter decide right when it gets the evidence table (devvm_evidence)? (Captain 2026-10-08, step 2 of the plan)

Two cases with a known ground truth, taken from the AM-004 build of 2026-10-07, each asked N times per model, once with the old prompt and once with the evidence:
  false_rejection  correct code, a check that contradicts itself and the task (acceptance_step1.py of the finished candidate)  -> the right answer is PASS (overrule the check)
  true_failure     code with the real defect (a missing key is not reported), and a check that is right (the suite criterion)  -> the right answer is FAIL

    .venv\\Scripts\\python.exe benchmarks/probes/arbiter_probe.py <project_dir> [--models qwen3coder,swe] [--trials 3]

It uses the real arbiter (`DevOrchestrator._arbitrate`) with the real model server and the microVM judge, under the GPU lease. Nothing is integrated or changed; the results go to the run log.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(RUNTIME / "benchmarks"))

TASK_SPEC = "am004_import"
TASK_STAGE = "permissions"
GOOD_CANDIDATE = "am004_import/attempt_01_20261007_144124"
DEFECT_CANDIDATE = "am004_import/salvaged_20261007_1411"
SUITE_CRITERION = "am004_import.permissions"


def build_cases(project):
    """The two cases from files on disk: {name, expected, task, files, check, check_name, module}. Raises FileNotFoundError when the material is not there."""
    import importlib
    sys.path.insert(0, str(RUNTIME / "benchmarks"))
    from guppi_runtime.acceptance_suite import load_suite
    project = Path(project)
    candidates = project / "runtime_data" / "devvm_candidates"
    spec = importlib.import_module(f"devvm_specs.{TASK_SPEC}")
    task = next(stage["task"] for stage in spec.STAGES if stage["name"] == TASK_STAGE)
    good, defect = candidates / GOOD_CANDIDATE, candidates / DEFECT_CANDIDATE
    files = lambda folder: {name: (folder / name).read_text(encoding="utf-8") for name in ("agent_import.py", "agent_contracts.py")}
    suite = load_suite(str(project / "acceptance" / "suites" / TASK_SPEC))
    _, text = suite.scripts[SUITE_CRITERION]
    return [
        {"name": "false_rejection", "expected": "PASS", "task": task, "files": files(good), "check": (good / "acceptance_step1.py").read_text(encoding="utf-8"), "check_name": "acceptance_step1.py"},
        {"name": "true_failure", "expected": "FAIL", "task": task, "files": files(defect), "check": text, "check_name": "acceptance_step1.py"},
    ]


def run_probe(cases, models, trials, make_team, failing_output, progress=None):
    """make_team(model) -> an object with `_arbitrate(task, step, output, label)` and a `ws` workspace prepared for one case through `prepare(team, case)`;
    failing_output(case) -> the failure text of the check. Returns {model: {case: {mode: {"PASS": n, "FAIL": n, "none": n}}}}."""
    table = {}
    for model in models:
        team = make_team(model)
        table[model] = {}
        for case in cases:
            team.prepare(case)
            output = failing_output(case)
            table[model][case["name"]] = {}
            for mode, with_evidence in (("old_prompt", False), ("with_evidence", True)):
                counts = {"PASS": 0, "FAIL": 0, "none": 0}
                for trial in range(trials):
                    step = {"title": "task", "instruction": case["task"], "acceptance": "", "check": case["check"] if with_evidence else ""}
                    verdict = team._arbitrate(case["task"], step, output, f"arbiter {case['name']} {mode} {trial + 1}")
                    counts[verdict if verdict in ("PASS", "FAIL") else "none"] += 1
                table[model][case["name"]][mode] = counts
            if progress:
                progress(table)
    return table


def summarize(table, cases, trials):
    expected = {c["name"]: c["expected"] for c in cases}
    lines = []
    for model, by_case in table.items():
        for mode in ("old_prompt", "with_evidence"):
            right = sum(by_case[name][mode][expected[name]] for name in expected)
            lines.append(f"{model:12s} {mode:14s} right {right}/{trials * len(expected)}  " + "  ".join(f"{name}: PASS {by_case[name][mode]['PASS']} FAIL {by_case[name][mode]['FAIL']} none {by_case[name][mode]['none']}" for name in expected))
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("--models", default="qwen3coder,swe")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--context", default="32768")
    args = parser.parse_args()
    project = Path(args.project)
    models = [m for m in args.models.split(",") if m]

    import devvm_agents_bench as bench
    from guppi_runtime.acceptance_vm import vm_runner
    from guppi_runtime.devvm import DevWorkspace
    from guppi_runtime.devvm_agents import DevOrchestrator, ModelHost
    from guppi_runtime.gpu_preflight import clear_leftovers
    from guppi_runtime.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
    from guppi_runtime.run_log import RunLog
    from guppi_runtime.testlab import TestLab, default_path

    cases = build_cases(project)
    log = RunLog(project / "runtime_data" / "measurements", "arbiter_probe", config={"models": models, "trials": args.trials})
    run_in_vm = vm_runner(project, RUNTIME, mission="M-PROBE")
    tool_root = Path(tempfile.mkdtemp(prefix="guppi_arbiter_probe_"))
    policy = {"max_files": 40, "max_file_bytes": 60000, "max_input_bytes": 200000}
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_arbiter_probe_rt_")))
    state = {"ws": None, "case": 0}

    def failing_output(case):
        result = run_in_vm({**case["files"], case["check_name"]: case["check"]}, [["python3", case["check_name"]]])
        return "the check script of this step fails:\n" + result["output"]

    class Team:
        def __init__(self, model):
            keys = {"planner": "qwen3coder", "coder": "qwen3coder", "reviewer": model, "coder_strong": "qwen3coder", "arbiter": model}
            self.host = ModelHost(bench.BenchLoader(runtime, project, keys, log, context=int(args.context)))
            self.team = None
            self.keys = keys

        def prepare(self, case):
            state["case"] += 1
            ws = DevWorkspace(tool_root, f"M-PROBE{state['case']:03d}", policy=dict(policy))
            ws.create()
            for name, text in case["files"].items():
                ws.write(name, text)
            ws.write(case["check_name"], case["check"])
            self.team = DevOrchestrator(ws, self.host, self.keys, vm_runner=lambda commands, ws=ws: run_in_vm({p: ws.read(p) for p in ws.tree()}, commands), say=log.say)

        def _arbitrate(self, task, step, output, label):
            return self.team._arbitrate(task, step, output, label)

        def close(self):
            self.host.close()

    teams = []

    def make_team(model):
        team = Team(model)
        teams.append(team)
        return team

    started = time.monotonic()
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "arbiter_probe"), "arbiter probe", ttl_s=1800, wait_s=3600, preflight=clear_leftovers):
        try:
            table = run_probe(cases, models, args.trials, make_team, failing_output, progress=lambda partial: log.save({"models": models, "trials": args.trials, "table": partial}))
        finally:
            for team in teams:
                team.close()
        for line in summarize(table, cases, args.trials):
            log.say(line)
            print(line)
        log.save({"models": models, "trials": args.trials, "table": table, "summary": summarize(table, cases, args.trials), "seconds": round(time.monotonic() - started, 1)})
    print(json.dumps(table))
    print("PROBE DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
