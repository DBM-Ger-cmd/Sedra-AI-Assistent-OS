"""Worker of one run (started detached by DevVmRuntime): runs `benchmarks/devvm_build.py` for the requested spec and writes `done.json` when it ends.
`python -m guppi_runtime.agent_manager.run_worker <run_dir> <runtime_dir> <project_dir>`. The run counts as succeeded only when the hidden acceptance test of the spec passed."""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time


MODEL_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{1,40}")


def options(project_dir, spec):
    """Run options from `runtime_data/agent_manager/seeds/<spec>.options.json`. Only these keys exist, each with a fixed type and range; anything else is ignored, so a file can never add a free command."""
    path = os.path.join(project_dir, "runtime_data", "agent_manager", "seeds", spec + ".options.json")
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key in ("check_first", "parallel_check", "tidy", "hidden_feedback"):
        if raw.get(key) is True:
            out[key] = True
    if raw.get("reasoning") in ("auto", "on", "off"):
        out["reasoning"] = raw["reasoning"]
    if type(raw.get("reasoning_budget")) is int and -1 <= raw["reasoning_budget"] <= 8192:
        out["reasoning_budget"] = raw["reasoning_budget"]
    sampling = raw.get("sampling")
    if isinstance(sampling, dict):
        limits = {"temperature": (0, 2), "top_p": (0, 1), "min_p": (0, 1), "top_k": (0, 200), "presence_penalty": (-2, 2), "frequency_penalty": (-2, 2), "repeat_penalty": (0.5, 2)}
        clean = {k: v for k, v in sampling.items() if k in limits and isinstance(v, (int, float)) and not isinstance(v, bool) and limits[k][0] <= v <= limits[k][1]}
        if clean:
            out["sampling"] = clean
    if raw.get("mode") in ("escalating", "pipeline", "delegating", "solo"):
        out["mode"] = raw["mode"]
    for flag in ("plan_steps", "step_syntax_check", "fresh_rework"):
        if raw.get(flag) is True:
            out[flag] = True
    if type(raw.get("rework")) is int and 0 <= raw["rework"] <= 4:
        out["rework"] = raw["rework"]
    if type(raw.get("parallel")) is int and 1 <= raw["parallel"] <= 2:
        out["parallel"] = raw["parallel"]
    if type(raw.get("context")) is int and 8192 <= raw["context"] <= 49152:
        out["context"] = raw["context"]
    for key in ("coder", "checker", "arbiter", "all_models"):
        if isinstance(raw.get(key), str) and MODEL_KEY.fullmatch(raw[key]):
            out[key] = raw[key]
    return out


SPEC_NAME = re.compile(r"am\d{3}_[a-z0-9_]{1,30}|bench_std")
STAGE_NAME = re.compile(r"[a-z0-9_]{1,40}")
SEED_PATH = re.compile(r"[A-Za-z0-9_\-]{1,60}(/[A-Za-z0-9_\-]{1,60}){0,3}")      # below runtime_data/devvm_snapshots, never an absolute path or a ..


def probe_script(runtime_dir, spec):
    """`probe_<name>` runs benchmarks/probes/<name>_probe.py (a measurement, not a build)."""
    return os.path.join(runtime_dir, "benchmarks", "probes", spec[len("probe_"):] + "_probe.py")


def probe_command(python, runtime_dir, project_dir, spec):
    path = os.path.join(project_dir, "runtime_data", "agent_manager", "seeds", spec + ".options.json")
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        raw = {}
    raw = raw if isinstance(raw, dict) else {}
    cmd = [python, probe_script(runtime_dir, spec), project_dir]
    models = raw.get("models")
    if isinstance(models, list) and 1 <= len(models) <= 8 and all(isinstance(m, str) and MODEL_KEY.fullmatch(m) for m in models):
        cmd += ["--models", ",".join(models)]
    modes = raw.get("modes")
    if isinstance(modes, list) and 1 <= len(modes) <= 4 and all(m in ("escalating", "solo", "solo-light", "solo-none", "qwen-none", "qwen-light", "qwen-full", "qwen-append-none", "qwen-lean-none", "qwen-lean-light") for m in modes):
        cmd += ["--modes", ",".join(modes)]
    if type(raw.get("trials")) is int and 1 <= raw["trials"] <= 5:
        cmd += ["--trials", str(raw["trials"])]
    specs = raw.get("specs")
    if isinstance(specs, list) and 1 <= len(specs) <= 4 and all(isinstance(s, str) and SPEC_NAME.fullmatch(s) for s in specs):
        cmd += ["--specs", ",".join(specs)]
    if raw.get("reasoning") in ("off", "on"):
        cmd += ["--reasoning", raw["reasoning"]]
    if type(raw.get("reasoning_budget")) is int and -1 <= raw["reasoning_budget"] <= 8192:
        cmd += ["--reasoning-budget", str(raw["reasoning_budget"])]
    if type(raw.get("per_stage")) is int and 1 <= raw["per_stage"] <= 12:
        cmd += ["--per-stage", str(raw["per_stage"])]
    if isinstance(raw.get("stage"), str) and STAGE_NAME.fullmatch(raw["stage"]):
        cmd += ["--stage", raw["stage"]]
    if isinstance(raw.get("seed"), str) and SEED_PATH.fullmatch(raw["seed"]):
        cmd += ["--seed", raw["seed"]]
    return cmd


EXPERIMENTAL = ("plan_steps", "step_syntax_check", "fresh_rework", "parallel_check", "checker", "arbiter")      # devvm_build wants --experimental for these (finished measurements)


def command(python, runtime_dir, project_dir, spec):
    """The ONE way to build (PIPE-06, Captain 2026-10-20): devvm_build --profile standard; single values of the options file override the profile, and
    --experimental is added only when the options file asks for an option of a finished measurement."""
    if spec.startswith("probe_"):
        return probe_command(python, runtime_dir, project_dir, spec)
    chosen = options(project_dir, spec)
    cmd = [python, os.path.join(runtime_dir, "benchmarks", "devvm_build.py"), project_dir, "--spec", spec, "--profile", "standard", "--rework", str(chosen.get("rework", 2)), "--coder", chosen.get("coder", "coder.local_primary"),
           "--context", str(chosen.get("context", 32768))]
    if "coder" in chosen and "all_models" not in chosen:      # the profile sets --all-models; a coder of the options file would otherwise have no effect
        cmd += ["--all-models", chosen["coder"]]
    if any(chosen.get(key) for key in EXPERIMENTAL):
        cmd.append("--experimental")
    for flag in ("check_first", "parallel_check", "tidy", "hidden_feedback"):
        if chosen.get(flag):
            cmd.append("--" + flag.replace("_", "-"))
    if "parallel" in chosen:
        cmd += ["--parallel", str(chosen["parallel"])]
    if "checker" in chosen:
        cmd += ["--checker", chosen["checker"]]
    if "mode" in chosen:
        cmd += ["--mode", chosen["mode"]]
    for flag in ("plan_steps", "step_syntax_check", "fresh_rework"):
        if chosen.get(flag):
            cmd.append("--" + flag.replace("_", "-"))
    if "sampling" in chosen:
        cmd += ["--sampling", json.dumps(chosen["sampling"])]
    if "reasoning" in chosen:
        cmd += ["--reasoning", chosen["reasoning"]]
    if "reasoning_budget" in chosen:
        cmd += ["--reasoning-budget", str(chosen["reasoning_budget"])]
    if "all_models" in chosen:
        cmd += ["--all-models", chosen["all_models"]]
    if "arbiter" in chosen:
        cmd += ["--arbiter", chosen["arbiter"]]
    seed = os.path.join(project_dir, "runtime_data", "agent_manager", "seeds", spec)
    if os.path.isdir(seed):
        cmd += ["--seed", seed]
    return cmd


def summarize(output, exit_code):
    if "PROBE DONE" in output:
        rows = [line.strip() for line in output.splitlines() if re.search(r" right \d+/\d+", line)]
        return {"state": "succeeded" if exit_code == 0 else "failed", "exit_code": exit_code, "hidden_passed": False, "candidate": None, "probe": rows}
    passed = re.search(r"hidden test PASSED", output) is not None
    candidate = re.search(r"^.*hidden test (?:PASSED|FAILED).* -> (.+?)\s*$", output.split("# run ended")[0], re.M)
    return {"state": "succeeded" if exit_code == 0 and passed else "failed", "exit_code": exit_code, "hidden_passed": passed, "candidate": candidate.group(1) if candidate else None}


def stamp_gate(runtime_dir, project_dir, spec):
    """The same spec stamp rule as devvm_build (benchmarks/spec_stamp.py gate), with the same messages; a probe is a measurement and needs none. Raises SystemExit(reason)."""
    if spec.startswith("probe_"):
        return
    path = os.path.join(runtime_dir, "benchmarks", "spec_stamp.py")
    loaded = importlib.util.spec_from_file_location("spec_stamp", path)
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    module.gate(project_dir, spec, False, os.path.join(runtime_dir, "benchmarks"), False)


def run(run_dir, runtime_dir, project_dir, runner=subprocess.run, clock=time.monotonic, gate=stamp_gate):
    with open(os.path.join(run_dir, "request.json"), encoding="utf-8") as handle:
        request = json.load(handle)
    started = clock()
    done = {"state": "failed", "exit_code": None, "hidden_passed": False, "candidate": None}
    try:
        gate(runtime_dir, project_dir, request["spec"])
        result = runner(command(sys.executable, runtime_dir, project_dir, request["spec"]), cwd=runtime_dir, capture_output=True, text=True, encoding="utf-8", errors="replace")
        output = (result.stdout or "") + (result.stderr or "")
        with open(os.path.join(run_dir, "build.log"), "w", encoding="utf-8") as handle:
            handle.write(output)
        done = summarize(output, result.returncode)
        done["log_tail"] = output[-1500:]
    except SystemExit as stop:      # no valid spec stamp: no model is loaded, the run ends as failed with the reason of devvm_build
        done["error"] = str(stop)
    except Exception as exc:
        done["error"] = f"{type(exc).__name__}: {exc}"
    done["seconds"] = round(clock() - started, 1)
    temporary = os.path.join(run_dir, "done.json.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(done, handle)
    os.replace(temporary, os.path.join(run_dir, "done.json"))
    return done


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], sys.argv[3])
