import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import assert_catalog
import build_request
from catalog_proofs import PROOFS

ADDRESS = re.compile(r"^[A-Za-z]:[\\/]|^/|https?://")
OPERATORS = (("==", "!="), ("!=", "=="), (" + ", " - "), (" - ", " + "), (" < ", " >= "), (" > ", " <= "), ("True", "False"), ("False", "True"))
RETURN = re.compile(r"return [^\n]+")
CASE_KINDS = {"K01": ("module", "func"), "K04": ("module", "func", "name")}
TAGS = ("T2", "T3", "T4", "T6", "T7", "T8")


def _checks(request):
    for stage in request["stages"]:
        for number, check in enumerate(stage["checks"], 1):
            yield stage["name"], number, check


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in list(value.keys()) + list(value.values()):
            yield from _strings(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _strings(item)


def _runs(code, tree, timeout):
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "ws"
        if tree is not None:
            shutil.copytree(tree, work, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            work.mkdir()
        (work / "t_run.py").write_text(code, encoding="utf-8")
        done = subprocess.run([sys.executable, "t_run.py"], cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env={**os.environ, "PYTHONUTF8": "1"}, timeout=timeout)
    return done.returncode == 0


def _contradictions(request):
    seen, found = {}, []
    for stage, _, check in _checks(request):
        keys = CASE_KINDS.get(check["kind"])
        if not keys:
            continue
        params = check["params"]
        owner = (check["kind"],) + tuple(repr(params.get(key)) for key in keys) + (repr(params.get("prefix", ())),)
        for case in params["cases"]:
            given = repr(case[0])
            known = seen.setdefault((owner, given), repr(case[1]))
            if known != repr(case[1]):
                found.append(f"T3: stage {stage}: same input, different results: {case[0]!r}")
    return found


def _mutants(tree, limit):
    found = []
    for path in sorted(Path(tree).rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        spots = [(match.start(), match.end(), match.group(), "return None") for match in RETURN.finditer(text)]
        for old, new in OPERATORS:
            spots += [(match.start(), match.end(), old, new) for match in re.finditer(re.escape(old), text)]
        for start, end, old, new in sorted(spots):
            if len(found) >= limit:
                return found
            mutated = text[:start] + new + text[end:]
            try:
                compile(mutated, str(path), "exec")
            except SyntaxError:
                continue
            found.append((path.relative_to(tree).as_posix(), text.count("\n", 0, start) + 1, old, new, mutated))
    return found


def _mutation_warnings(tree, final_test, limit, timeout):
    warnings = []
    for name, line, old, new, mutated in _mutants(tree, limit):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "tree"
            shutil.copytree(tree, work, ignore=shutil.ignore_patterns("__pycache__"))
            (work / name).write_text(mutated, encoding="utf-8")
            if _runs(final_test, work, timeout):
                warnings.append(f"T8: mutant survives: {name} line {line}: {old!r} -> {new!r}")
    return warnings


def check_request(request, *, tree=None, seed=None, proofs=None, mutants=30, timeout=60):
    report = {"problems": [], "warnings": [], "unchecked": []}
    invalid = build_request.validate_request(request)
    if invalid:
        report["problems"] = [f"T1: {problem}" for problem in invalid]
        report["unchecked"] = [f"{tag}: not checked (invalid request)" for tag in TAGS]
        return report
    used = {check["kind"] for _, _, check in _checks(request)}
    available = PROOFS if proofs is None else proofs
    report["problems"] += [f"T2: {line}" for line in assert_catalog.check_proofs({k: v for k, v in available.items() if k in used}) if line.split(":")[0] in used]
    report["problems"] += _contradictions(request)
    for stage, number, check in _checks(request):
        if any(ADDRESS.search(text) for text in _strings(check["params"])):
            report["problems"].append(f"T6: stage {stage} check {number}: absolute path or address in the parameters")
    tests = build_request.stage_tests(request)
    if seed is None:
        report["unchecked"].append("T4: no seed given")
    elif _runs(tests[0], seed, timeout):
        report["problems"].append(f"T4: stage {request['stages'][0]['name']} already passes on the seed")
    if tree is None:
        report["unchecked"] += ["T7: no pattern given", "T8: no pattern given"]
        return report
    failing = [stage["name"] for stage, code in zip(request["stages"], tests) if not _runs(code, tree, timeout)]
    report["problems"] += [f"T7: stage {name} fails on the pattern" for name in failing]
    if failing:
        report["unchecked"].append("T8: not checked (T7 failed)")
    else:
        report["warnings"] += _mutation_warnings(tree, tests[-1], mutants, timeout)
    return report


def ok(report):
    return not report["problems"]
