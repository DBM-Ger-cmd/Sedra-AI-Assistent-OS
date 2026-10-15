"""guppi buildflow ... (docs/BUILDFLOW_2026-10-13.md): the build workflow as commands. A task goes draft -> checked -> spec_approved -> queued -> building -> built -> reported -> adopt_approved -> adopted.

    guppi --root <project> buildflow add --title "..." --spec NAME [--seed DIR] [--review FILE] [--from-stage S] [--rework N] [--priority P] [--night]
    guppi --root <project> buildflow list [--all] | show ID | check ID | approve-spec ID | queue ID | run [--night] [--once]
    guppi --root <project> buildflow report ID | diagnose ID --host-ok | approve-adopt ID | adopt ID [--yes] | cancel ID | requeue ID [--review FILE] [--from-stage S]

`approve-spec` and `approve-adopt` record the Captain's decision; only the Captain runs them (they will become real mission gates when the Chat window is linked). `adopt` shows the plan of
adopt_plan and copies nothing without --yes and an approved adoption. Candidate code is only executed on this PC by `diagnose --host-ok`."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from . import adopt_plan, build_log, buildflow_core as core, review_report
from .buildflow_runner import iso_now, run_queue
from .buildflow_store import BuildflowStore, default_path

RUNTIME = Path(__file__).resolve().parents[3]
TARGET = "runtime/src/guppi_runtime/devenv"
TESTS = "runtime/tests"


def spec_tools(runtime):
    loaded = importlib.util.spec_from_file_location("spec_check_tool", Path(runtime) / "benchmarks" / "spec_check.py")
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module


def check_problems(task, runtime):
    tools = spec_tools(runtime)
    try:
        spec = tools.load_spec(task["spec"])
    except SystemExit:
        return ["no spec file"], []
    problems, warnings = tools.lint(spec)
    problems = list(problems)
    reference = Path(runtime) / "benchmarks" / "devvm_refs" / task["spec"]
    if not reference.is_dir():
        problems.append("no reference: the tests are unproven")
    else:
        problems += [f"the reference fails stage {name}" for name, ok, _ in tools.matrix(reference, spec) if not ok]
    if task["seed"]:
        seed = Path(task["seed"]) if Path(task["seed"]).is_absolute() else Path(runtime) / "benchmarks" / task["seed"]
        rows = tools.matrix(seed, spec)
        if rows and rows[0][1]:
            problems.append(f"stage {rows[0][0]} already passes on the seed")
    return problems, warnings


def candidate_dir(task, runtime):
    given = (task.get("result") or {}).get("exported_to")
    if not given:
        raise ValueError("no_candidate")
    return (Path(runtime) / given.replace("\\", "/")).resolve()


def py_files(folder):
    return sorted(path.relative_to(folder).as_posix() for path in Path(folder).rglob("*.py") if "__pycache__" not in path.parts)


def failing_stage(task, runtime):
    tools = spec_tools(runtime)
    spec = tools.load_spec(task["spec"])
    for name, ok, tail in tools.matrix(candidate_dir(task, runtime), spec):
        if not ok:
            return name, tail
    return None, []


def repo_inventory(repo):
    existing = {path.relative_to(repo).as_posix() for folder in (TARGET, TESTS) for path in (Path(repo) / folder).rglob("*.py")}
    top = Path(repo) / "runtime" / "src" / "guppi_runtime"
    shims = {path.relative_to(repo).as_posix() for path in top.glob("*.py") if path.read_text(encoding="utf-8", errors="replace").startswith('"""Moved to')}
    return existing | shims, shims


def parser():
    ap = argparse.ArgumentParser(prog="guppi buildflow")
    sub = ap.add_subparsers(dest="action", required=True)
    add = sub.add_parser("add")
    add.add_argument("--title", required=True)
    add.add_argument("--spec", required=True)
    add.add_argument("--seed", default="")
    add.add_argument("--review", default="")
    add.add_argument("--from-stage", default="")
    add.add_argument("--rework", type=int, default=3)
    add.add_argument("--priority", type=int, default=0)
    add.add_argument("--night", action="store_true")
    lst = sub.add_parser("list")
    lst.add_argument("--all", action="store_true")
    for name in ("show", "check", "approve-spec", "queue", "report", "approve-adopt", "cancel"):
        sub.add_parser(name).add_argument("task_id")
    dia = sub.add_parser("diagnose")
    dia.add_argument("task_id")
    dia.add_argument("--host-ok", action="store_true")
    adopt = sub.add_parser("adopt")
    adopt.add_argument("task_id")
    adopt.add_argument("--yes", action="store_true")
    adopt.add_argument("--target-dir", default=TARGET)
    requeue = sub.add_parser("requeue")
    requeue.add_argument("task_id")
    requeue.add_argument("--review", default=None)
    requeue.add_argument("--from-stage", default=None)
    run = sub.add_parser("run")
    run.add_argument("--night", action="store_true")
    run.add_argument("--once", action="store_true")
    return ap


def move(store, task_id, event, note="", **changes):
    return store.update(task_id, lambda task: core.transition(task, event, iso_now(), note=note, **changes))


def build_report(task, runtime, project, store):
    folder = candidate_dir(task, runtime)
    parsed = build_log.parse_log((store.folder / f"{task['id']}.log").read_text(encoding="utf-8", errors="replace"))
    files = py_files(folder)
    findings = []
    for name in files:
        findings += review_report.findings_from_source(name, (folder / name).read_text(encoding="utf-8", errors="replace"))
    data = {"spec": task["spec"], "stages": [{"name": s["name"], "passed": s["passed"]} for s in parsed["stages"]],
            "files": [{"path": name, "lines": len((folder / name).read_text(encoding="utf-8", errors="replace").splitlines())} for name in files],
            "findings": findings, "calls": task["result"].get("calls"), "seconds": task["result"].get("seconds")}
    return review_report.report(data)


def main(argv, project, *, runtime=RUNTIME, repo=None, out=print, runner=run_queue):
    args = parser().parse_args(argv)
    repo = Path(repo) if repo else Path(runtime).parent
    store = BuildflowStore(default_path(project))
    try:
        return act(args, store, project, Path(runtime), repo, out, runner)
    except (ValueError, KeyError) as exc:
        out(f"refused: {exc}")
        return 2


def act(args, store, project, runtime, repo, out, runner):
    name = args.action
    if name == "add":
        task = core.new_task(args.title, args.spec, now=iso_now(), seed=args.seed, review=args.review, from_stage=args.from_stage, rework=args.rework, priority=args.priority,
                             window="night" if args.night else "now")
        out(core.line(store.add(task)))
        return 0
    if name == "list":
        tasks = [t for t in store.all() if args.all or t["state"] not in ("adopted", "cancelled")]
        for task in tasks:
            out(core.line(task))
        return 0
    if name == "run":
        ran = runner(store, night=args.night, once=args.once, project=project, runtime=runtime, say=out)
        out(f"built: {', '.join(ran) if ran else 'nothing queued'}")
        return 0
    task = store.load(args.task_id)
    if name == "show":
        out(json.dumps(task, indent=1, ensure_ascii=False))
    elif name == "check":
        problems, warnings = check_problems(task, runtime)
        task = move(store, task["id"], "check_failed" if problems else "check_ok", note="; ".join(problems))
        out(core.line(task))
        for text in problems + [f"warning: {w}" for w in warnings]:
            out("  " + text)
        return 1 if problems else 0
    elif name in ("approve-spec", "queue", "approve-adopt", "cancel"):
        event = {"approve-spec": "approve_spec", "queue": "queue", "approve-adopt": "approve_adopt", "cancel": "cancel"}[name]
        out(core.line(move(store, task["id"], event, note="Captain" if event.startswith("approve") else "")))
    elif name == "requeue":
        changes = {key: value for key, value in (("review", args.review), ("from_stage", args.from_stage)) if value is not None}
        out(core.line(move(store, task["id"], "requeue", **changes)))
    elif name == "diagnose":
        if not args.host_ok:
            raise ValueError("diagnose runs candidate code on this PC: add --host-ok")
        stage, tail = failing_stage(task, runtime)
        out(review_report.question(stage, tail[0] if tail else "", tail[1] if len(tail) > 1 else "") if stage else "every stage test passes on the candidate")
    elif name == "report":
        text = build_report(task, runtime, project, store)
        move(store, task["id"], "report", result={"report": text})
        out(text)
    elif name == "adopt":
        return adopt(args, store, task, runtime, repo, out)
    return 0


def adopt(args, store, task, runtime, repo, out):
    folder = candidate_dir(task, runtime)
    existing, shims = repo_inventory(repo)
    plan = adopt_plan.plan_adoption(py_files(folder), args.target_dir, existing, shims)
    out(adopt_plan.describe(plan))
    if not args.yes:
        return 0 if plan["ok"] else 1
    if task["state"] != "adopt_approved":
        raise ValueError("the adoption is not approved: run approve-adopt first")
    for source, target in adopt_plan.copy_pairs(plan, folder.as_posix()):
        destination = Path(repo) / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(Path(source).read_bytes())
    out(core.line(move(store, task["id"], "adopt", note=f"{len(plan['entries'])} entries")))
    return 0
