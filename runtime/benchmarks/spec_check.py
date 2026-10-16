r"""Check a devvm spec before a build costs GPU time (Claude 2026-10-13: seven wrong expectations in six specs, one stage test that needed a later stage's rule cost 30 minutes of GPU).

    .venv\Scripts\python.exe benchmarks/spec_check.py <spec> [--seed DIR] [--tree DIR ...] [--snapshots DIR] [--host-ok]

The hidden tests run the way the build runs them: a copy of the tree is the workspace, each test is `python <file>` there, exit code 0 = passed.
  lint        stages and tests exist, names are unique, no assert with `or` (a weak test), a NOTES text exists
  ref         benchmarks/devvm_refs/<spec> must pass EVERY stage test (the reference is the proof that the tests are right)
  seed        --seed DIR: the first stage must FAIL on the seed, or the build would prove nothing
  tree        --tree DIR (repeatable): a candidate, a snapshot or any folder; prints which stage tests pass, with the first failing assertion
  snapshots   --snapshots DIR: a build's snapshot folder (after_<stage> subfolders): each stage test runs on its own snapshot and on the one before it
                (a test that fails on its OWN snapshot but passes on a later state needs a later stage's rule: the test is wrong, not the model)
Code in --tree/--snapshots was written by a model and runs on THIS host; it needs --host-ok. The reference does not.
Exit code 0 when lint, ref (and seed, if given) are fine."""
import argparse
import ast
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent


def load_spec(name):
    path = BENCH / "devvm_specs" / f"{name}.py"
    if not path.is_file():
        raise SystemExit(f"no spec {path}")
    loaded = importlib.util.spec_from_file_location(f"spec_{name}", path)
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module


def stages_of(spec):
    return getattr(spec, "STAGES", None) or [{"name": "all", "hidden": getattr(spec, "HIDDEN", {})}]


def lint(spec):
    problems, warnings, seen = [], [], set()
    stages = stages_of(spec)
    if not getattr(spec, "NOTES", ""):
        problems.append("no NOTES text")
    for stage in stages:
        name = stage.get("name", "?")
        if name in seen:
            problems.append(f"stage name twice: {name}")
        seen.add(name)
        if not stage.get("task") and not getattr(spec, "TASK", ""):
            problems.append(f"stage {name}: no task")
        if not stage.get("hidden") and not stage.get("host_hidden"):
            problems.append(f"stage {name}: no hidden test (nothing could ever pass it)")
        for file, code in (stage.get("hidden") or {}).items():
            try:
                tree = ast.parse(code)
            except SyntaxError as exc:
                problems.append(f"stage {name} {file}: syntax error line {exc.lineno}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert) and isinstance(node.test, ast.BoolOp) and isinstance(node.test.op, ast.Or):
                    warnings.append(f"stage {name} {file} line {node.lineno}: assert with `or` (check that it is meant)")
    return problems, warnings


def _failure(stderr, file, code):
    lines = [l for l in (stderr or "").splitlines() if l.strip()]
    source = code.splitlines()
    for line in reversed(lines):
        if "File " in line and Path(file).name in line and "line " in line:
            number = int(line.rsplit("line ", 1)[1].split(",")[0])
            return [f"line {number}: {source[number - 1].strip()[:140]}" if 0 < number <= len(source) else line.strip(), lines[-1].strip()[:140]]
    return lines[-2:]


def _node_failure(stderr):
    lines = [l.strip() for l in (stderr or "").splitlines() if l.strip()]
    hit = next((l for l in lines if l.startswith("AssertionError")), None)
    where = next((l for l in lines if ".cjs:" in l and l.startswith("at ")), None)
    return [x for x in (where, hit) if x] or lines[-2:]


def run_stage(tree, stage, timeout=60):
    """Every test of the stage against a copy of the tree: `hidden` with python, `host_hidden` with node (the JS stages, as devvm_build judges them).
    A node test without node is a FAIL, never a silent ok (2026-10-13: three JS specs were reported ok while their tests failed, because only `hidden` ran)."""
    results = []
    tests = [(f, c, "python") for f, c in (stage.get("hidden") or {}).items()] + [(f, c, "node") for f, c in (stage.get("host_hidden") or {}).items()]
    node = shutil.which("node")
    for file, code, kind in tests:
        if kind == "node" and not node:
            results.append((file, False, ["node is not installed: the JS test could not run"])); continue
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "ws"
            if tree is not None and Path(tree).is_dir():
                shutil.copytree(tree, work, ignore=shutil.ignore_patterns("__pycache__", ".git"))
            else:
                work.mkdir()
            (work / file).write_text(code, encoding="utf-8")
            try:
                if kind == "node":
                    done = subprocess.run([node, file], cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
                    ok, tail = done.returncode == 0, _node_failure(done.stderr)
                else:
                    done = subprocess.run([sys.executable, file], cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONUTF8": "1"}, timeout=timeout)
                    ok, tail = done.returncode == 0, _failure(done.stderr, file, code)
            except subprocess.TimeoutExpired:
                ok, tail = False, [f"timeout after {timeout} s"]
        results.append((file, ok, tail))
    return results


def matrix(tree, spec):
    rows = []
    for stage in stages_of(spec):
        results = run_stage(tree, stage)
        rows.append((stage["name"], all(ok for _, ok, _ in results), next((tail for _, ok, tail in results if not ok), [])))
    return rows


def show(label, rows, detail=True):
    print(f"  {label:<9}" + " | ".join(f"{name} {'ok' if ok else 'FAIL'}" for name, ok, _ in rows))
    if detail:
        for name, ok, tail in rows:
            if not ok:
                print(f"      {name}: " + " / ".join(t.strip() for t in tail[-2:]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec")
    ap.add_argument("--ref")
    ap.add_argument("--seed")
    ap.add_argument("--tree", action="append", default=[])
    ap.add_argument("--snapshots")
    ap.add_argument("--host-ok", action="store_true", help="allow model-written code (--tree, --snapshots) to run on this host")
    args = ap.parse_args()
    spec = load_spec(args.spec)
    stages = stages_of(spec)
    good = True
    print(f"spec {args.spec}: {len(stages)} stages")
    problems, warnings = lint(spec)
    print("  lint     " + ("ok" if not problems else "PROBLEMS") + (f" ({len(warnings)} warning)" if warnings else ""))
    for problem in problems + ["warning: " + w for w in warnings]:
        print("      " + problem)
    good &= not problems
    ref = Path(args.ref) if args.ref else BENCH / "devvm_refs" / args.spec
    if ref.is_dir():
        rows = matrix(ref, spec)
        show("ref", rows)
        good &= all(ok for _, ok, _ in rows)
    else:
        print(f"  ref      none ({ref}): the tests are unproven")
        good = False
    if args.seed:
        rows = matrix(args.seed, spec)
        show("seed", rows, detail=False)
        if rows and rows[0][1]:
            print(f"      stage {rows[0][0]} already passes on the seed: the first stage proves nothing")
            good = False
    if (args.tree or args.snapshots) and not args.host_ok:
        raise SystemExit("--tree/--snapshots run model-written code on this host: add --host-ok")
    for tree in args.tree:
        show(Path(tree).name[:9], matrix(tree, spec))
    if args.snapshots:
        names = [s["name"] for s in stages]
        folders = {n: Path(args.snapshots) / f"after_{n}" for n in names}
        before = None
        for stage in stages:
            own = folders[stage["name"]]
            if not own.is_dir():
                print(f"  snapshot {own.name}: missing")
                continue
            now = all(ok for _, ok, _ in run_stage(own, stage))
            earlier = None if before is None else all(ok for _, ok, _ in run_stage(before, stage))
            print(f"  {stage['name']:<10} own snapshot: {'ok' if now else 'FAIL'}" + ("" if earlier is None else f" | previous snapshot: {'ok (stage adds nothing)' if earlier else 'FAIL (as expected)'}"))
            if not now:
                for _, ok, tail in run_stage(own, stage):
                    if not ok:
                        print("      " + " / ".join(t.strip() for t in tail[-2:]))
            before = own
    print("  result   " + ("ok" if good else "PROBLEMS"))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
