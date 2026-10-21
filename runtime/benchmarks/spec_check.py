r"""Check a devvm spec before a build costs GPU time (Claude 2026-10-13: seven wrong expectations in six specs, one stage test that needed a later stage's rule cost 30 minutes of GPU).

    .venv\Scripts\python.exe benchmarks/spec_check.py <spec> [--seed DIR] [--tree DIR ...] [--snapshots DIR] [--host-ok]
    .venv\Scripts\python.exe benchmarks/spec_check.py <spec> --vm --project <project>          (before every build: writes the stamp devvm_build needs)
    .venv\Scripts\python.exe benchmarks/spec_check.py <spec> --host-only --project <project>   (only when the microVM cannot start: a weaker stamp)

The hidden tests run the way the build runs them: a copy of the tree is the workspace, each test is `python <file>` there, exit code 0 = passed.
  lint        stages and tests exist, names are unique, no assert with `or` (a weak test), a NOTES text exists
  ref         benchmarks/devvm_refs/<spec> must pass EVERY stage test (the reference is the proof that the tests are right)
  seed        --seed DIR: the first stage must FAIL on the seed, or the build would prove nothing
  tree        --tree DIR (repeatable): a candidate, a snapshot or any folder; prints which stage tests pass, with the first failing assertion
  size        new hidden checks (assert, raises) per stage: more than 20 is a warning, more than 30 an error (Captain 2026-10-20, line L3: SEDRA passes a stage with up to ~20 new checks in the first run)
  vm          --vm: lint, ref and the hidden tests ALSO in the python of the microVM (the one the build judges with, devvm_vm.py); with result ok the stamp
                <project>/runtime_data/spec_stamps/<spec>.json is written (spec_stamp.py, level vm); --host-only writes a stamp of level host without the VM
  snapshots   --snapshots DIR: a build's snapshot folder (after_<stage> subfolders): each stage test runs on its own snapshot and on the one before it
                (a test that fails on its OWN snapshot but passes on a later state needs a later stage's rule: the test is wrong, not the model)
Code in --tree/--snapshots was written by a model and runs on THIS host; it needs --host-ok. The reference does not.
Exit code 0 when lint, ref (and seed, if given) are fine."""
import argparse
import ast
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent
if str(BENCH) not in sys.path:
    sys.path.insert(0, str(BENCH))
import spec_stamp  # noqa: E402
from devvm_vm import hidden_plan  # noqa: E402

SIZE_WARN, SIZE_ERROR = 20, 30


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


def count_checks(code, kind="python"):
    """Hidden checks in one test file: every assert plus every raises( (assertRaises, pytest.raises, own raises helpers), as the analysis of 2026-10-20 counts them."""
    raises = len(re.findall(r"raises\(", code, re.IGNORECASE))
    if kind == "python":
        try:
            return sum(isinstance(node, ast.Assert) for node in ast.walk(ast.parse(code))) + raises
        except SyntaxError:
            pass
    return len(re.findall(r"\bassert\b", code)) + raises


def stage_sizes(spec):
    """[(stage, checks of the stage, NEW checks)]: the stage tests are cumulative (a later stage runs the earlier test files again), so new = checks of the stage minus checks of the stage before."""
    rows, before = [], 0
    for stage in stages_of(spec):
        total = sum(count_checks(c) for c in (stage.get("hidden") or {}).values()) + sum(count_checks(c, "node") for c in (stage.get("host_hidden") or {}).values())
        rows.append((stage.get("name", "?"), total, max(total - before, 0)))
        before = total
    return rows


def size_problems(rows):
    """(errors, warnings) for stages with more new checks than SEDRA passes in a first run."""
    errors = [f"stage {name}: {new} new checks (more than {SIZE_ERROR}: split the stage)" for name, _, new in rows if new > SIZE_ERROR]
    warnings = [f"stage {name}: {new} new checks (more than {SIZE_WARN})" for name, _, new in rows if SIZE_WARN < new <= SIZE_ERROR]
    return errors, warnings


VM_LINT = r'''import ast, pathlib, sys
print("python " + sys.version.split()[0])
bad = []
for path in sorted(pathlib.Path(".").rglob("*.py")):
    try:
        ast.parse(path.read_text(encoding="utf-8"), str(path))
    except SyntaxError as exc:
        bad.append(f"{path.as_posix()}: line {exc.lineno}: {exc.msg}")
print("\n".join(bad) or "parse ok")
sys.exit(1 if bad else 0)
'''


def vm_check(ref, spec, vm_copy, tree_cls):
    """Lint and the hidden tests of every stage against the reference IN the microVM. Returns (python version or None, lint problems, rows like matrix).
    host_hidden (node) stages are left out here: the build judges them on the host as well."""
    tree = tree_cls(ref)
    files = {"_spec_vm_lint.py": VM_LINT}
    for stage in stages_of(spec):
        for file, code in (stage.get("hidden") or {}).items():
            files[f"_hidden/{stage.get('name', 'all')}/{file}"] = code
    out = vm_copy(tree, [["python3", "_spec_vm_lint.py"]], files)
    lines = [l.strip() for l in out["output"].splitlines() if l.strip()]
    python = next((l.split(" ", 1)[1] for l in lines if l.startswith("python ")), None)
    problems = [] if out["status"] == "completed" else ([l for l in lines if not l.startswith("python ")][-5:] or [f"VM run {out['status']}"])
    rows = []
    for stage in stages_of(spec):
        hidden = stage.get("hidden") or {}
        if not hidden:
            continue
        commands, extra = hidden_plan(hidden)
        done = vm_copy(tree, commands, extra)
        rows.append((stage["name"], done["status"] == "completed", [l for l in done["output"].splitlines() if l.strip()][-2:]))
    return python, problems, rows


def run_in_vm(project, ref, spec, vm_env=None):
    """The microVM of devvm_build (devvm_vm.vm_env) in a throw-away folder under <project>/runtime_data/devvm_work; vm_env can be replaced in tests (a fake VM)."""
    import devvm_vm
    work_root = Path(project) / "runtime_data" / "devvm_work"
    work_root.mkdir(parents=True, exist_ok=True)
    tool_root = Path(tempfile.mkdtemp(prefix="spec_check_", dir=work_root))
    try:
        _, vm_copy = (vm_env or devvm_vm.vm_env)(project, tool_root, False, "M-SPECCHK", "M-SPC")
        return vm_check(ref, spec, vm_copy, devvm_vm.FolderTree)
    except Exception as exc:
        return None, [f"the microVM could not run: {type(exc).__name__}: {str(exc)[:200]}"], []
    finally:
        shutil.rmtree(tool_root, ignore_errors=True)


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


def main(argv=None, vm_env=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec")
    ap.add_argument("--ref")
    ap.add_argument("--seed")
    ap.add_argument("--tree", action="append", default=[])
    ap.add_argument("--snapshots")
    ap.add_argument("--host-ok", action="store_true", help="allow model-written code (--tree, --snapshots) to run on this host")
    ap.add_argument("--vm", action="store_true", help="also run lint, reference and hidden tests in the python of the microVM; with result ok write the stamp (needs --project)")
    ap.add_argument("--host-only", action="store_true", help="write a stamp of level host (weaker) without the microVM, only when the VM cannot start (needs --project)")
    ap.add_argument("--project", help="the project folder of the build (the one devvm_build gets): its runtime_data holds the VM home and the stamps")
    args = ap.parse_args(argv)
    if args.vm and args.host_only:
        raise SystemExit("--vm and --host-only exclude each other")
    if (args.vm or args.host_only) and not args.project:
        raise SystemExit("--vm/--host-only need --project <project> (the folder devvm_build gets)")
    if args.ref and (args.vm or args.host_only):
        raise SystemExit("--ref and a stamp exclude each other: the stamp is bound to devvm_refs/<spec>")
    spec = load_spec(args.spec)
    stages = stages_of(spec)
    good = True
    print(f"spec {args.spec}: {len(stages)} stages")
    problems, warnings = lint(spec)
    print("  lint     " + ("ok" if not problems else "PROBLEMS") + (f" ({len(warnings)} warning)" if warnings else ""))
    for problem in problems + ["warning: " + w for w in warnings]:
        print("      " + problem)
    good &= not problems
    sizes = stage_sizes(spec)
    print("  size     " + " | ".join(f"{name} {new}" for name, _, new in sizes) + f" (new checks per stage; >{SIZE_WARN} warning, >{SIZE_ERROR} error)")
    size_errors, size_warnings = size_problems(sizes)
    for line in size_errors + ["warning: " + w for w in size_warnings]:
        print("      " + line)
    good &= not size_errors
    ref = Path(args.ref) if args.ref else BENCH / "devvm_refs" / args.spec
    if ref.is_dir():
        rows = matrix(ref, spec)
        show("ref", rows)
        good &= all(ok for _, ok, _ in rows)
    else:
        print(f"  ref      none ({ref}): the tests are unproven")
        good = False
    seed_name, seed_dir = spec_stamp.seed_folder(args.spec, BENCH)
    if seed_name:      # PIPE-10: the reference is complete, the seed is not loaded again; the line shows what the build will load
        if seed_dir.is_dir():
            print(f"  seed     {seed_name} ({spec_stamp.tree_sha256(seed_dir)[1]} Dateien)")
        else:
            print(f"  seed     {seed_name}: folder missing (seed_missing)")
            good = False
    level, python = None, None
    if args.vm and ref.is_dir():
        python, vm_problems, vm_rows = run_in_vm(args.project, ref, spec, vm_env)
        print("  vm lint  " + ("ok" if not vm_problems else "PROBLEMS") + f" (python {python or '?'})")
        for line in vm_problems:
            print("      " + line)
        show("vm ref", vm_rows)
        good &= not vm_problems and python is not None and all(ok for _, ok, _ in vm_rows)
        level = "vm"
    elif args.host_only:
        python, level = f"host {sys.version.split()[0]}", "host"
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
    if args.project and (args.vm or args.host_only):
        if good and level:
            path = spec_stamp.write(args.project, args.spec, level, python, bench=BENCH)
            print(f"  stamp    {level} -> {path}" + ("  (WEAKER: host python only, not the microVM)" if level == "host" else ""))
        elif spec_stamp.remove(args.project, args.spec):
            print("  stamp    removed (result not ok)")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
