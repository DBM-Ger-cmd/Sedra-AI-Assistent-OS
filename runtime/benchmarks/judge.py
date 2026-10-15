r"""Executable judge for the small-team bench: runs the tests of every candidate INSIDE GUPPI's own microVM, never on this host.

    from judge import judge
    results = judge(project_dir, {"key": (task_id, code), ...})
    # -> {"key": {"passed": 7, "total": 8, "failures": ["input ('abc\n',): expected ValueError('bad_id'), got no exception"], "error": None}}

One VM job per call (the same code the sandbox worker uses: no network, RESTRICTED, tmpfs, command timeout from config/sandbox.yaml); all candidates are
copied in and judged one after the other, each in its own python process with a time limit, so a candidate that loops or exits only loses itself.
VM starts fail about 2 times in 8 (docs/SANDBOX_BOUNDARY_STATUS.md): the job is retried, and a candidate that got no result says so (`error`).
The failure lines are what the coder gets back, in the same form GUPPI's own reworks use ("input, expected, got").

Why a judge: SWE-Review's verdict alone was wrong too often (small_team run 2026-10-05: 13 of 19 right; 2 false rejections, 2 false passes).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

# Expected behaviour per task. args are JSON values; "returns" is compared as str(result); "raises" is [exception type name, args[0]].
TESTS = {
    "regex_trailing_newline": {"fn": "check_id", "cases": [
        {"args": ["abc"], "returns": "abc"}, {"args": ["a" * 12], "returns": "a" * 12}, {"args": ["a"], "returns": "a"},
        {"args": ["abc\n"], "raises": ["ValueError", "bad_id"]}, {"args": [""], "raises": ["ValueError", "bad_id"]},
        {"args": ["a" * 13], "raises": ["ValueError", "bad_id"]}, {"args": ["ABC"], "raises": ["ValueError", "bad_id"]},
        {"args": ["ab1"], "raises": ["ValueError", "bad_id"]}, {"args": ["abc "], "raises": ["ValueError", "bad_id"]}]},
    "urlparse_port": {"fn": "check_url", "cases": [
        {"args": ["http://127.0.0.1:8080/"], "returns": "http://127.0.0.1:8080/"}, {"args": ["http://127.0.0.1:1/"], "returns": "http://127.0.0.1:1/"},
        {"args": ["http://127.0.0.1:65535/"], "returns": "http://127.0.0.1:65535/"},
        {"args": ["http://127.0.0.1:65536/"], "raises": ["ValueError", "url_not_allowed"]}, {"args": ["http://127.0.0.1:0/"], "raises": ["ValueError", "url_not_allowed"]},
        {"args": ["http://127.0.0.1:abc/"], "raises": ["ValueError", "url_not_allowed"]}, {"args": ["http://127.0.0.1/"], "raises": ["ValueError", "url_not_allowed"]},
        {"args": ["https://127.0.0.1:80/"], "raises": ["ValueError", "url_not_allowed"]}, {"args": ["http://localhost:80/"], "raises": ["ValueError", "url_not_allowed"]},
        {"args": ["http://127.0.0.1:80/x"], "raises": ["ValueError", "url_not_allowed"]}, {"args": ["http://127.0.0.1:-1/"], "raises": ["ValueError", "url_not_allowed"]}]},
    "int_conversion": {"fn": "parse_count", "cases": [
        {"args": ["5"], "returns": "5"}, {"args": ["0"], "returns": "0"}, {"args": ["1000"], "returns": "1000"},
        {"args": ["1001"], "raises": ["ValueError", "bad_count"]}, {"args": ["-1"], "raises": ["ValueError", "bad_count"]},
        {"args": ["x1"], "raises": ["ValueError", "bad_count"]}, {"args": [""], "raises": ["ValueError", "bad_count"]}, {"args": ["1.5"], "raises": ["ValueError", "bad_count"]}]},
    "dict_key": {"fn": "get_setting", "cases": [
        {"args": [{"port": 1}, "port"], "returns": "1"}, {"args": [{"a": 1, "port": 2}, "port"], "returns": "2"},
        {"args": [{}, "port"], "raises": ["LookupError", "setting_missing"]}, {"args": [{"a": 1}, "b"], "raises": ["LookupError", "setting_missing"]}]},
    "isoformat_date": {"fn": "parse_day", "cases": [
        {"args": ["2026-10-05"], "returns": "2026-10-05"}, {"args": ["2000-02-29"], "returns": "2000-02-29"},
        {"args": ["2026-13-01"], "raises": ["ValueError", "bad_day"]}, {"args": ["2026-02-30"], "raises": ["ValueError", "bad_day"]},
        {"args": ["2026-00-10"], "raises": ["ValueError", "bad_day"]}, {"args": ["2026-10-32"], "raises": ["ValueError", "bad_day"]},
        {"args": ["2026-10-00"], "raises": ["ValueError", "bad_day"]}, {"args": ["abc"], "raises": ["ValueError", "bad_day"]}, {"args": [""], "raises": ["ValueError", "bad_day"]}]},
    "pair_parse": {"fn": "parse_pair", "cases": [
        {"args": ["1,2"], "returns": "(1, 2)"}, {"args": ["255,0"], "returns": "(255, 0)"}, {"args": ["0,0"], "returns": "(0, 0)"},
        {"args": ["256,1"], "raises": ["ValueError", "bad_pair"]}, {"args": ["1"], "raises": ["ValueError", "bad_pair"]}, {"args": ["x,1"], "raises": ["ValueError", "bad_pair"]},
        {"args": ["1,2,3"], "raises": ["ValueError", "bad_pair"]}, {"args": ["-1,5"], "raises": ["ValueError", "bad_pair"]}, {"args": [","], "raises": ["ValueError", "bad_pair"]}]},
    "nested_lookup": {"fn": "get_nested", "cases": [
        {"args": [{"db": {"port": 5}}, "db", "port"], "returns": "5"},
        {"args": [{}, "db", "port"], "raises": ["LookupError", "config_missing"]}, {"args": [{"db": {}}, "db", "port"], "raises": ["LookupError", "config_missing"]},
        {"args": [{"db": None}, "db", "port"], "raises": ["LookupError", "config_missing"]}, {"args": [{"db": 5}, "db", "port"], "raises": ["LookupError", "config_missing"]},
        {"args": [{"db": [1]}, "db", "port"], "raises": ["LookupError", "config_missing"]}]},
    "flag_words": {"fn": "read_flag", "cases": [
        {"args": ["true"], "returns": "True"}, {"args": ["1"], "returns": "True"}, {"args": ["yes"], "returns": "True"}, {"args": ["TRUE"], "returns": "True"}, {"args": [" YES "], "returns": "True"},
        {"args": ["false"], "returns": "False"}, {"args": ["0"], "returns": "False"}, {"args": ["no"], "returns": "False"}, {"args": [" No "], "returns": "False"},
        {"args": ["maybe"], "raises": ["ValueError", "bad_flag"]}, {"args": [""], "raises": ["ValueError", "bad_flag"]}, {"args": ["2"], "raises": ["ValueError", "bad_flag"]},
        {"args": ["yesno"], "raises": ["ValueError", "bad_flag"]}]},
}

# Runs in the guest (and in unit tests on trusted fixtures). One process per candidate: argv[1] = key; reads cases.json, prints JUDGE_JSON=...
JUDGE_ONE = r'''
import json, signal, sys
key = sys.argv[1]
spec = json.load(open("/workspace/cases.json"))[key]
out = {"passed": 0, "total": len(spec["cases"]), "failures": [], "error": None}
def timeout(signum, frame): raise TimeoutError("case took more than 2 s")
try: signal.signal(signal.SIGALRM, timeout)
except Exception: pass
ns = {"__name__": "candidate"}
try:
    exec(compile(open("/workspace/cand_" + key + ".py", encoding="utf-8").read(), "candidate.py", "exec"), ns)
    fn = ns[spec["fn"]]
except BaseException as exc:
    out["error"] = type(exc).__name__ + ": " + str(exc)[:160]
    print("JUDGE_JSON=" + json.dumps(out)); sys.exit(0)
for case in spec["cases"]:
    shown = "input " + json.dumps(case["args"], ensure_ascii=True)[1:-1].join("()")
    try: signal.alarm(2)
    except Exception: pass
    try:
        got, raised = fn(*case["args"]), None
    except BaseException as exc:
        got, raised = None, exc
    try: signal.alarm(0)
    except Exception: pass
    if "raises" in case:
        want_type, want_msg = case["raises"]
        ok = raised is not None and any(c.__name__ == want_type for c in type(raised).__mro__) and raised.args[:1] == (want_msg,)
        expected = want_type + "(" + repr(want_msg) + ")"
    else:
        ok = raised is None and str(got) == case["returns"]
        expected = case["returns"]
    if ok: out["passed"] += 1
    elif len(out["failures"]) < 5:
        result = ("no exception, returned " + repr(got)) if raised is None else (type(raised).__name__ + "(" + repr(raised.args[0] if raised.args else "") + ")")
        out["failures"].append((shown + ": expected " + expected + ", got " + result)[:240])
print("JUDGE_JSON=" + json.dumps(out))
'''

JUDGE_ALL = r'''
import json, subprocess, sys
keys = list(json.load(open("/workspace/cases.json")))
results = {}
for key in keys:
    try:
        proc = subprocess.run([sys.executable, "-I", "/workspace/judge_one.py", key], capture_output=True, text=True, timeout=15, cwd="/workspace")
        line = [l for l in proc.stdout.splitlines() if l.startswith("JUDGE_JSON=")]
        results[key] = json.loads(line[-1][11:]) if line else {"passed": 0, "total": 0, "failures": [], "error": "no result (exit %s): %s" % (proc.returncode, proc.stderr[-120:])}
    except subprocess.TimeoutExpired:
        results[key] = {"passed": 0, "total": 0, "failures": [], "error": "candidate ran longer than 15 s"}
print("JUDGE_ALL=" + json.dumps(results))
'''


def _sandbox_run(project, source, attempts=3):
    """One VM job over the prepared folder; returns the parsed JUDGE_ALL dict, or raises RuntimeError with the last failure."""
    import yaml
    from guppi_runtime.sandbox.provider import MicrosandboxProvider
    policy = yaml.safe_load((RUNTIME / "config" / "sandbox.yaml").read_text(encoding="utf-8"))["sandbox"]
    provider = MicrosandboxProvider(Path(project) / "runtime_data" / "sandboxes" / "backend_home", RUNTIME)
    last = "no attempt"
    for attempt in range(1, attempts + 1):
        job_root = Path(tempfile.mkdtemp(prefix="guppi_judge_job_"))
        request = {"job_id": f"judge-{int(time.time())}-{attempt}", "policy": policy, "source": str(source), "job_root": str(job_root),
                   "commands": [["python3", "/workspace/judge_all.py"]], "exports": []}
        result = provider._execute_worker("run", request, job_root)
        for cmd in result.get("commands", []):
            for line in (cmd.get("output") or "").splitlines():
                if line.startswith("JUDGE_ALL="):
                    return json.loads(line[len("JUDGE_ALL="):])
        last = f"{result.get('status')}: {result.get('error')}"
        time.sleep(2)
    raise RuntimeError("judge_vm_failed: " + last)


def prepare(candidates):
    """Writes the folder that is copied into the VM: judge scripts, cases.json and one cand_<key>.py per candidate. Returns the folder."""
    folder = Path(tempfile.mkdtemp(prefix="guppi_judge_src_"))
    cases = {}
    for key, (task_id, code) in candidates.items():
        if task_id not in TESTS: raise KeyError(f"no tests for task {task_id}")
        (folder / f"cand_{key}.py").write_text(code or "", encoding="utf-8")
        cases[key] = TESTS[task_id]
    (folder / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    (folder / "judge_one.py").write_text(JUDGE_ONE, encoding="utf-8")
    (folder / "judge_all.py").write_text(JUDGE_ALL, encoding="utf-8")
    return folder


def judge(project, candidates):
    """{key: (task_id, code)} -> {key: {passed, total, failures, error}}. Model code only ever runs in the VM."""
    if not candidates: return {}
    return _sandbox_run(project, prepare(candidates))


def all_passed(entry):
    return bool(entry) and entry.get("error") is None and entry["total"] > 0 and entry["passed"] == entry["total"]


def feedback(entry):
    """The text the coder gets after a failed judgement."""
    if entry.get("error"): return "the module could not be run: " + entry["error"]
    return f"{entry['passed']} of {entry['total']} checks passed. Failing checks:\n" + "\n".join("- " + f for f in entry["failures"])
