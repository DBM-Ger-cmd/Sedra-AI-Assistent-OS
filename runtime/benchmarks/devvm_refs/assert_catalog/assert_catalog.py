import builtins
import re
import subprocess
import sys
import tempfile
from pathlib import Path

NAMES = {"K01": "table", "K02": "unchanged", "K03": "empty", "K04": "bounds", "K05": "tie_order", "K06": "deterministic", "K07": "raises", "K08": "stable_order",
         "K09": "near", "K10": "file_result", "K11": "text_format", "K12": "pure", "K13": "limit_marker", "K14": "form", "K15": "cumulative"}
SCHEMA = {
    "K01": (("module", "func", "cases"), {}),
    "K02": (("module", "func", "args"), {}),
    "K03": (("module", "func"), {"values": (None, "", [], {}), "prefix": ()}),
    "K04": (("module", "func", "name", "cases"), {"prefix": ()}),
    "K05": (("module", "func", "args"), {"field": "id"}),
    "K06": (("module", "func", "args"), {}),
    "K07": (("module", "func", "cases"), {}),
    "K08": (("module", "func", "args"), {"field": "id"}),
    "K09": (("module", "func", "cases"), {"tol": 0.01}),
    "K10": (("pattern", "heads"), {"head_prefix": "## ", "first_regex": "", "contains": ()}),
    "K11": (("path", "first_regex"), {"max_first": 72, "blank_second": True, "body_lines": 1}),
    "K12": (("module",), {}),
    "K13": (("module", "func", "cases"), {}),
    "K14": (("module",), {}),
    "K15": (("previous", "new"), {}),
}
BANNED = ("os", "subprocess", "socket", "urllib", "http", "requests", "shutil", "pathlib", "sys", "ctypes")


def kinds():
    return sorted(SCHEMA)


def describe(kind):
    required, optional = SCHEMA[kind]
    return {"id": kind, "name": NAMES[kind], "required": list(required), "optional": dict(optional)}


def _check_name(value, dotted=False):
    parts = value.split(".") if dotted and isinstance(value, str) else [value]
    if not isinstance(value, str) or not all(isinstance(p, str) and p.isidentifier() for p in parts):
        raise ValueError(f"bad name: {value!r}")
    return value


def _params(kind, given):
    required, optional = SCHEMA[kind]
    for key in given:
        if key not in required and key not in optional:
            raise ValueError(f"unknown parameter: {key}")
    for key in required:
        if key not in given:
            raise ValueError(f"missing parameter: {key}")
    values = {**optional, **given}
    if "module" in values:
        _check_name(values["module"], dotted=True)
    if "func" in values:
        _check_name(values["func"])
    return values


def _call(func, args):
    return f"{func}({', '.join(repr(a) for a in args)})"


def _cases(values, size):
    cases = values["cases"]
    if not isinstance(cases, (list, tuple)) or not cases or any(not isinstance(c, (list, tuple)) or len(c) != size for c in cases):
        raise ValueError("cases must be a non-empty list of tuples")
    return cases


def _head(values):
    return f"from {values['module']} import {values['func']}"


def _source_path(module):
    return module.replace(".", "/") + ".py"


def _k01(v):
    return [_head(v)] + [f"assert {_call(v['func'], args)} == {expected!r}" for args, expected in _cases(v, 2)]


def _k02(v):
    return [_head(v), "import copy", f"args = {tuple(v['args'])!r}", "before = copy.deepcopy(args)", f"{v['func']}(*args)", "assert args == before"]


def _k03(v):
    return [_head(v)] + [f"{v['func']}(*{tuple(v['prefix'])!r}, {value!r})" for value in v["values"]]


def _k04(v):
    _check_name(v["name"])
    return [_head(v)] + [f"assert {v['func']}(*{tuple(v['prefix'])!r}, {v['name']}={value!r}) == {expected!r}" for value, expected in _cases(v, 2)]


def _k05(v):
    return [_head(v), f"result = {v['func']}(*{tuple(v['args'])!r})", f"keys = [item[{v['field']!r}] for item in result]", "assert keys == sorted(keys)"]


def _k06(v):
    return [_head(v), "import copy", f"args = {tuple(v['args'])!r}", f"assert {v['func']}(*copy.deepcopy(args)) == {v['func']}(*copy.deepcopy(args))"]


def _k07(v):
    lines = [_head(v)]
    for args, name, message in _cases(v, 3):
        exception = getattr(builtins, str(name), None)
        if not (isinstance(exception, type) and issubclass(exception, BaseException)):
            raise ValueError(f"not an exception: {name!r}")
        lines += ["try:", f"    {_call(v['func'], args)}", f"except {name} as error:", f"    assert str(error) == {message!r}", "else:", f"    raise AssertionError({'no ' + name!r})"]
    return lines


def _k08(v):
    return [_head(v), f"items = {tuple(v['args'])!r}", f"before = [item[{v['field']!r}] for item in items[0]]", f"after = [item[{v['field']!r}] for item in {v['func']}(*items)]",
            "assert after == [key for key in before if key in after]"]


def _k09(v):
    return [_head(v)] + [f"assert abs({_call(v['func'], args)} - {expected!r}) < {v['tol']!r}" for args, expected in _cases(v, 2)]


def _k10(v):
    lines = ["import re", "from pathlib import Path", f"files = sorted(Path('.').glob({v['pattern']!r}))", "assert len(files) == 1", "text = files[0].read_text(encoding='utf-8')",
             "lines = text.splitlines()", f"heads = [line.strip() for line in lines if line.startswith({v['head_prefix']!r})]", f"assert heads == {list(v['heads'])!r}"]
    if v["first_regex"]:
        lines.append(f"assert re.match({v['first_regex']!r}, lines[0])")
    return lines + [f"assert {text!r} in text" for text in v["contains"]]


def _k11(v):
    lines = ["import re", "from pathlib import Path", f"lines = Path({v['path']!r}).read_text(encoding='utf-8').splitlines()", f"assert re.match({v['first_regex']!r}, lines[0]) and len(lines[0]) <= {v['max_first']!r}"]
    if v["blank_second"]:
        lines.append("assert len(lines) >= 3 and lines[1] == ''")
    return lines + [f"assert sum(1 for line in lines[1:] if line.strip()) >= {v['body_lines']!r}"]


def _k12(v):
    banned = {name: None for name in BANNED}
    return ["import ast", "from pathlib import Path", f"tree = ast.parse(Path({_source_path(v['module'])!r}).read_text(encoding='utf-8'))", "names = set()",
            "for node in ast.walk(tree):", "    if isinstance(node, ast.Import):", "        names.update(alias.name.split('.')[0] for alias in node.names)",
            "    elif isinstance(node, ast.ImportFrom) and node.module:", "        names.add(node.module.split('.')[0])", f"assert not names & set({sorted(banned)!r})",
            "assert not any(isinstance(node, ast.Call) and getattr(node.func, 'id', '') in ('open', 'exec', 'eval', 'input') for node in ast.walk(tree))"]


def _k13(v):
    lines = [_head(v)]
    for args, maximum, marker in _cases(v, 3):
        lines += [f"out = {_call(v['func'], args)}.splitlines()", f"assert len(out) <= {maximum!r}", f"assert out[-1] == {marker!r}"]
    return lines


def _k14(v):
    return ["import ast", "import io", "import tokenize", "from pathlib import Path", f"source = Path({_source_path(v['module'])!r}).read_text(encoding='utf-8')", "tree = ast.parse(source)",
            "assert not any(token.type == tokenize.COMMENT for token in tokenize.generate_tokens(io.StringIO(source).readline))",
            "assert not any(ast.get_docstring(node) for node in ast.walk(tree) if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))",
            "kinds = (ast.Import, ast.ImportFrom)", "body = tree.body", "last = max((i for i, node in enumerate(body) if isinstance(node, kinds)), default=-1)",
            "assert all(isinstance(node, kinds) for node in body[:last + 1])", "assert not any(isinstance(node, kinds) for node in ast.walk(tree) if node not in body)",
            "imported = set()", "for node in body:", "    if isinstance(node, ast.Import):", "        imported.update((alias.asname or alias.name).split('.')[0] for alias in node.names)",
            "    elif isinstance(node, ast.ImportFrom):", "        imported.update(alias.asname or alias.name for alias in node.names)",
            "assert imported <= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}"]


def _k15(v):
    seen = {line for line in v["previous"].splitlines() if line.strip()}
    return v["previous"].rstrip("\n").splitlines() + [line for line in v["new"].splitlines() if line not in seen]


MAKERS = {"K01": _k01, "K02": _k02, "K03": _k03, "K04": _k04, "K05": _k05, "K06": _k06, "K07": _k07, "K08": _k08, "K09": _k09, "K10": _k10, "K11": _k11, "K12": _k12,
          "K13": _k13, "K14": _k14, "K15": _k15}


def generate(kind, **params):
    if kind not in SCHEMA:
        raise KeyError(kind)
    return "\n".join(MAKERS[kind](_params(kind, params))) + "\n"


def build_test(items):
    seen, lines = set(), []
    for kind, params in items:
        for line in generate(kind, **params).splitlines():
            if line.startswith(("import ", "from ")):
                if line in seen:
                    continue
                seen.add(line)
            lines.append(line)
    return "\n".join(lines) + "\n"


def _passes(code, files):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, source in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
        (root / "check_run.py").write_text(code, encoding="utf-8")
        done = subprocess.run([sys.executable, "check_run.py"], cwd=root, capture_output=True, text=True, timeout=60)
    return done.returncode == 0, [line for line in done.stderr.splitlines() if line.strip()][-1:]


def check_proofs(proofs=None):
    if proofs is None:
        from catalog_proofs import PROOFS as proofs
    problems = []
    for kind in kinds():
        proof = proofs.get(kind)
        if proof is None:
            problems.append(f"{kind}: no proof")
            continue
        code = generate(kind, **proof["params"])
        ok, tail = _passes(code, proof["good"])
        if not ok:
            problems.append(f"{kind}: the good example fails {' '.join(tail)}".strip())
        for number, mutant in enumerate(proof["mutants"], 1):
            if _passes(code, mutant)[0]:
                problems.append(f"{kind}: mutant {number} passes")
        if not proof["mutants"]:
            problems.append(f"{kind}: no mutant")
    return problems
