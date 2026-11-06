import re
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from . import assert_catalog
from . import build_request
from .catalog_proofs import PROOFS


def _run_test(code, src, timeout):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        if src is not None:
            src_path = Path(src) if not isinstance(src, Path) else src
            for item in src_path.rglob("*"):
                if "__pycache__" in item.parts:
                    continue
                if item.is_file():
                    rel = item.relative_to(src_path)
                    target = root / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(item.read_bytes())
        (root / "t_run.py").write_text(code, encoding="utf-8")
        env = {**os.environ, "PYTHONUTF8": "1"}
        done = subprocess.run(
            [sys.executable, "t_run.py"],
            cwd=root,
            capture_output=True,
            env=env,
            timeout=timeout,
        )
        return done.returncode == 0

def check_request(request, *, tree=None, seed=None, proofs=None, mutants=30, timeout=60):
    problems = []
    warnings = []
    unchecked = []
    validation_problems = build_request.validate_request(request)
    if validation_problems:
        problems = ["T1: " + p for p in validation_problems]
        unchecked = [f"T{t}: not checked (invalid request)" for t in [2, 3, 4, 6, 7, 8]]
        return {"problems": problems, "warnings": warnings, "unchecked": unchecked}
    used_kinds = set()
    for stage in request["stages"]:
        for check in stage["checks"]:
            used_kinds.add(check["kind"])
    proofs_dict = {}
    for kind in used_kinds:
        if proofs is not None:
            if kind in proofs:
                proofs_dict[kind] = proofs[kind]
        else:
            if kind in PROOFS:
                proofs_dict[kind] = PROOFS[kind]
    t2_problems = []
    proof_results = assert_catalog.check_proofs(proofs_dict if proofs_dict else None)
    for line in proof_results:
        kind = line.split(":")[0]
        if kind in used_kinds:
            t2_problems.append("T2: " + line)
    problems.extend(t2_problems)
    _t3_seen = {}
    for stage in request["stages"]:
        stage_name = stage["name"]
        for check in stage["checks"]:
            kind = check["kind"]
            params = check["params"]
            if kind not in ("K01", "K04"):
                continue
            if kind == "K01":
                group_key = (kind, params["module"], params["func"])
            else:
                group_key = (kind, params["module"], params["func"], params.get("name", ""), tuple(params.get("prefix", ())))
            if kind == "K01":
                cases = params["cases"]
                for args_tuple, expected in cases:
                    input_repr = repr(args_tuple)
                    expected_repr = repr(expected)
                    if group_key not in _t3_seen:
                        _t3_seen[group_key] = {}
                    if input_repr in _t3_seen[group_key]:
                        if _t3_seen[group_key][input_repr] != expected_repr:
                            problems.append(f"T3: stage {stage_name}: same input, different results: {input_repr}")
                    else:
                        _t3_seen[group_key][input_repr] = expected_repr
            elif kind == "K04":
                cases = params["cases"]
                for value, expected in cases:
                    input_repr = repr(value)
                    expected_repr = repr(expected)
                    if group_key not in _t3_seen:
                        _t3_seen[group_key] = {}
                    if input_repr in _t3_seen[group_key]:
                        if _t3_seen[group_key][input_repr] != expected_repr:
                            problems.append(f"T3: stage {stage_name}: same input, different results: {input_repr}")
                    else:
                        _t3_seen[group_key][input_repr] = expected_repr
    for stage in request["stages"]:
        stage_name = stage["name"]
        for n, check in enumerate(stage["checks"], 1):
            params = check["params"]
            strings = _extract_strings(params)
            for s in strings:
                if re.search(r'^[A-Za-z]:[\\/]', s) or s.startswith('/') or 'http://' in s or 'https://' in s:
                    problems.append(f"T6: stage {stage_name} check {n}: absolute path or address in the parameters")
                    break
    stage_tests = build_request.stage_tests(request)
    first_stage_name = request["stages"][0]["name"]
    if seed is None:
        unchecked.append("T4: no seed given")
    else:
        seed_path = Path(seed) if not isinstance(seed, Path) else seed
        passed = _run_test(stage_tests[0], seed_path, timeout)
        if passed:
            problems.append(f"T4: stage {first_stage_name} already passes on the seed")
    t7_failed = False
    if tree is None:
        unchecked.append("T7: no pattern given")
        unchecked.append("T8: no pattern given")
    else:
        tree_path = Path(tree) if not isinstance(tree, Path) else tree
        for i, stage in enumerate(request["stages"]):
            stage_name = stage["name"]
            passed = _run_test(stage_tests[i], tree_path, timeout)
            if not passed:
                problems.append(f"T7: stage {stage_name} fails on the pattern")
                t7_failed = True
        if t7_failed:
            unchecked.append("T8: not checked (T7 failed)")
        else:
            t8_warnings = _run_t8(tree_path, stage_tests, mutants, timeout)
            warnings.extend(t8_warnings)
    return {"problems": problems, "warnings": warnings, "unchecked": unchecked}


OPERATORS = (("==", "!="), ("!=", "=="), (" + ", " - "), (" - ", " + "), (" < ", " >= "), (" > ", " <= "), ("True", "False"), ("False", "True"))


def _get_spots(text):
    spots = []
    for m in re.finditer(r'return [^\n]+', text):
        old_text = m.group(0)
        new_text = "return None"
        spots.append((m.start(), m.end(), old_text, new_text))
    for old_text, new_text in OPERATORS:
        start = 0
        while True:
            idx = text.find(old_text, start)
            if idx == -1:
                break
            end = idx + len(old_text)
            spots.append((idx, end, old_text, new_text))
            start = end
    spots.sort(key=lambda s: (s[0], s[1], s[2]))
    return spots


def _apply_mutation(text, spot):
    start, end, old_text, new_text = spot
    return text[:start] + new_text + text[end:]


def _collect_py_files(tree_path):
    files = []
    for item in tree_path.rglob("*.py"):
        if "__pycache__" in item.parts:
            continue
        files.append(item)
    files.sort(key=lambda p: p.parts)
    return files


def _copy_tree(src, dst):
    for item in src.rglob("*"):
        if "__pycache__" in item.parts:
            continue
        if item.is_file():
            rel = item.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())


def _run_t8(tree_path, stage_tests, mutants_limit, timeout):
    warnings = []
    tree_path = Path(tree_path) if not isinstance(tree_path, Path) else tree_path
    py_files = _collect_py_files(tree_path)
    last_stage_test = stage_tests[-1]
    mutant_count = 0

    for py_file in py_files:
        text = py_file.read_text(encoding="utf-8")
        spots = _get_spots(text)
        for spot in spots:
            if mutant_count >= mutants_limit:
                return warnings
            new_text = _apply_mutation(text, spot)
            try:
                compile(new_text, str(py_file), "exec")
            except SyntaxError:
                continue
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                _copy_tree(tree_path, tmp_path)
                rel = py_file.relative_to(tree_path)
                mutated_file = tmp_path / rel
                mutated_file.write_text(new_text, encoding="utf-8")
                passed = _run_test(last_stage_test, tmp_path, timeout)
                if passed:
                    line_num = text[:spot[0]].count('\n') + 1
                    rel_str = str(rel).replace(os.sep, '/')
                    warnings.append(f"T8: mutant survives: {rel_str} line {line_num}: {spot[2]!r} -> {spot[3]!r}")
                    mutant_count += 1
    return warnings


def _extract_strings(obj):
    result = []
    if isinstance(obj, str):
        result.append(obj)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            result.extend(_extract_strings(item))
    elif isinstance(obj, dict):
        for key, value in obj.items():
            result.extend(_extract_strings(key))
            result.extend(_extract_strings(value))
    return result


def ok(report):
    return len(report["problems"]) == 0
