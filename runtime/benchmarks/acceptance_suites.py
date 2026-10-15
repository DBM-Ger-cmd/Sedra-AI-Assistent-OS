"""Turns the hidden tests of the DevVM specs into acceptance suites and checks them.

    .venv\\Scripts\\python.exe benchmarks/acceptance_suites.py convert <spec> <reference_dir> [--out DIR]    # write the suite folder (criteria, reference, digest) and validate it
    .venv\\Scripts\\python.exe benchmarks/acceptance_suites.py validate [SUITE_DIR ...]                       # run each suite's reference through the suite (a suite its reference fails is invalid)
    .venv\\Scripts\\python.exe benchmarks/acceptance_suites.py run <SUITE_DIR> <candidate_dir>                        # run a CANDIDATE through the suite in the microVM judge (the files named like the reference files)
    .venv\\Scripts\\python.exe benchmarks/acceptance_suites.py leaks <SUITE_DIR> <text file ...>              # lines of the hidden scripts that appear in prompts, logs or workspace files

Suites live in <project>/acceptance/suites/<spec>, outside every model workspace. Reference code is trusted and runs on the host; candidates run only in the microVM judge.
"""
import argparse
import importlib
import os
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from guppi_runtime.acceptance_suite import SuiteError, host_runner, leak_check, load_suite, run_suite, suite_from_stages, validate_suite, write_suite   # noqa: E402
from guppi_runtime.acceptance_vm import vm_runner   # noqa: E402

PROJECT = RUNTIME.parent / "workspace" / "GUPPI_OS"
SUITES = PROJECT / "acceptance" / "suites"


def convert(spec_name, reference_dir, out, version="1"):
    spec = importlib.import_module(f"devvm_specs.{spec_name}")
    reference = {name: (Path(reference_dir) / name).read_text(encoding="utf-8") for name in sorted(os.listdir(reference_dir)) if name.endswith(".py") and not name.startswith("hidden")}
    criteria = suite_from_stages(spec.STAGES, spec_name)
    target = Path(out) if out else SUITES / spec_name
    suite = write_suite(str(target), spec_name.replace("_", "-"), str(version), criteria, reference)
    return target, suite


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    conv = sub.add_parser("convert")
    conv.add_argument("spec")
    conv.add_argument("reference_dir")
    conv.add_argument("--out")
    conv.add_argument("--version", default="1")
    val = sub.add_parser("validate")
    val.add_argument("suites", nargs="*")
    runp = sub.add_parser("run")
    runp.add_argument("suite")
    runp.add_argument("candidate")
    lk = sub.add_parser("leaks")
    lk.add_argument("suite")
    lk.add_argument("texts", nargs="+")
    args = parser.parse_args()
    if args.cmd == "convert":
        target, suite = convert(args.spec, args.reference_dir, args.out, args.version)
        report = validate_suite(suite, host_runner())
        print(f"{suite.label()}  {len(suite.criteria)} criteria  reference {'PASSES' if report['ok'] else 'FAILS ' + str(report['problems'])}  -> {target}")
        return 0 if report["ok"] else 2
    if args.cmd == "validate":
        folders = [Path(p) for p in args.suites] or sorted(p for p in SUITES.iterdir() if p.is_dir())
        bad = 0
        for folder in folders:
            try:
                suite = load_suite(str(folder))
            except SuiteError as exc:
                print(f"{folder.name}: REFUSED ({exc})")
                bad += 1
                continue
            report = validate_suite(suite, host_runner())
            print(f"{suite.label()}  {len(suite.criteria)} criteria  " + ("valid (reference passes all)" if report["ok"] else "INVALID " + ", ".join(report["problems"])))
            bad += not report["ok"]
        return 2 if bad else 0
    if args.cmd == "run":
        suite = load_suite(args.suite)
        files = {name: (Path(args.candidate) / name).read_text(encoding="utf-8") for name in suite.reference if (Path(args.candidate) / name).is_file()}
        missing = sorted(set(suite.reference) - set(files))
        if missing:
            print(f"candidate misses {missing}")
            return 2
        run = run_suite(suite, files, vm_runner(PROJECT, RUNTIME))
        print(f"{run['suite']}  candidate {run['candidate_hash'][:12]}  " + ("PASSED all" if run["passed"] else "FAILED"))
        for result in run["results"]:
            print(f"  {result['criterion_id']:34s} {result['status']}")
        return 0 if run["passed"] else 2
    suite = load_suite(args.suite)
    texts = {t: Path(t).read_text(encoding="utf-8", errors="replace") for t in args.texts}
    found = leak_check(suite, texts)
    for item in found:
        print(f"LEAK in {item['source']} (criterion {item['criterion_id']}): {item['line']}")
    print(f"{len(found)} leak(s) in {len(texts)} text(s)")
    return 2 if found else 0


if __name__ == "__main__":
    sys.exit(main())
