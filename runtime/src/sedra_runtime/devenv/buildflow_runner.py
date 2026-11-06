"""Buildflow runner (docs/BUILDFLOW_2026-10-13.md): starts the build of a queued task with devvm_build.py, reads its log while it runs, and writes the result into the task.

    run_task(store, task_id, project=..., runtime=...)       # one task: start -> build -> finish_ok / finish_failed
    run_queue(store, project=..., runtime=..., night=False)  # the queue in the order of buildflow_core.pick_next

The build is a child process (`popen`, replaceable in tests). It takes the GPU lease itself; the runner only tells it who it is (TESTLAB_OWNER = buildflow_<id>) and with which priority
(TESTLAB_PRIORITY = the task's priority). The log of every build is kept next to the task as <id>.log. Progress lines come from build_log.events, the result from build_log.parse_log."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import build_log
from .buildflow_core import pick_next, transition

RECIPE = "coder.local_primary"
SERVER = ("flash_attn=on", "kv_cache_type=q8_0", "ubatch=512")


def iso_now():
    return datetime.now().replace(microsecond=0).isoformat()


def _path(runtime, value):
    path = Path(value)
    return str(path if path.is_absolute() else Path(runtime) / "benchmarks" / path)


def build_command(task, *, python, runtime, project):
    argv = [str(python), str(Path(runtime) / "benchmarks" / "devvm_build.py"), str(project), "--spec", task["spec"], "--attempts", "1", "--coder", RECIPE, "--all-models", RECIPE,
            "--context", "32768", "--tidy", "--reasoning", "off", "--coder-ext", "all", "--mode", "solo", "--self-check", "none", "--rework", str(task["rework"])]
    for key, flag in (("seed", "--seed"), ("review", "--review")):
        if task.get(key):
            argv += [flag, _path(runtime, task[key])]
    if task.get("from_stage"):
        argv += ["--from-stage", task["from_stage"]]
    for item in SERVER:
        argv += ["--server-set", item]
    return argv


def result_of(parsed, code):
    stages = parsed["stages"]
    attempt = parsed["attempt"]
    failed = next((stage["name"] for stage in stages if not stage["passed"]), None)
    result = {"passed": sum(1 for stage in stages if stage["passed"]), "stages": len(stages) + len(parsed["skipped"]), "failed_stage": failed, "exit": code,
              "seconds": attempt["seconds"] if attempt else None, "calls": attempt["calls"] if attempt else None, "exported_to": attempt["exported_to"] if attempt else None}
    return result, bool(attempt and attempt["passed"])


def run_task(store, task_id, *, project, runtime, python=None, popen=subprocess.Popen, now=iso_now, sleep=time.sleep, say=print, poll_s=2.0):
    task = store.update(task_id, lambda t: transition(t, "start", now(), note="runner"))
    log = store.folder / f"{task_id}.log"
    env = {**os.environ, "TESTLAB_OWNER": f"buildflow_{task_id}", "TESTLAB_PRIORITY": str(task["priority"]), "PYTHONUTF8": "1"}
    argv = build_command(task, python=python or sys.executable, runtime=runtime, project=project)
    with log.open("w", encoding="utf-8") as out:
        process = popen(argv, cwd=str(runtime), env=env, stdout=out, stderr=subprocess.STDOUT)
    since = 0
    while True:
        code = process.poll()
        text = log.read_text(encoding="utf-8", errors="replace")
        events, since = build_log.events(text, since)
        for event in events:
            say(f"{task_id}: {event['text']}")
        if code is not None:
            break
        sleep(poll_s)
    parsed = build_log.parse_log(text)
    result, passed = result_of(parsed, code)
    event = "finish_ok" if passed else "finish_failed"
    note = "" if passed else (f"stage {result['failed_stage']}" if result["failed_stage"] else f"exit {code}")
    return store.update(task_id, lambda t: transition(t, event, now(), note=note, result=result))


def run_queue(store, *, night=False, once=False, **kw):
    ran = []
    while True:
        task = pick_next(store.all(), night=night)
        if task is None:
            return ran
        run_task(store, task["id"], **kw)
        ran.append(task["id"])
        if once:
            return ran
