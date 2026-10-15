import builtins
import copy
import subprocess
import sys
import tempfile
from pathlib import Path

NAMES = {
    "K01": "table",
    "K02": "unchanged",
    "K03": "empty",
    "K04": "bounds",
    "K05": "tie_order",
    "K06": "deterministic",
    "K07": "raises",
    "K08": "stable_order",
    "K09": "near",
    "K10": "file_result",
    "K11": "text_format",
    "K12": "pure",
    "K13": "limit_marker",
    "K14": "form",
    "K15": "cumulative",
}

SCHEMA = {
    "K01": (
        ("module", "func", "cases"),
        {},
    ),
    "K02": (
        ("module", "func", "args"),
        {},
    ),
    "K03": (
        ("module", "func"),
        {"values": (None, "", [], {}), "prefix": ()},
    ),
    "K04": (
        ("module", "func", "name", "cases"),
        {"prefix": ()},
    ),
    "K05": (
        ("module", "func", "args"),
        {"field": "id"},
    ),
    "K06": (
        ("module", "func", "args"),
        {},
    ),
    "K07": (
        ("module", "func", "cases"),
        {},
    ),
    "K08": (
        ("module", "func", "args"),
        {"field": "id"},
    ),
    "K09": (
        ("module", "func", "cases"),
        {"tol": 0.01},
    ),
    "K10": (
        ("pattern", "heads"),
        {"head_prefix": "## ", "first_regex": "", "contains": ()},
    ),
    "K11": (
        ("path", "first_regex"),
        {"max_first": 72, "blank_second": True, "body_lines": 1},
    ),
    "K12": (
        ("module",),
        {},
    ),
    "K13": (
        ("module", "func", "cases"),
        {},
    ),
    "K14": (
        ("module",),
        {},
    ),
    "K15": (
        ("previous", "new"),
        {},
    ),
}

_KNOWN_KINDS = sorted(SCHEMA.keys())


def kinds():
    return list(_KNOWN_KINDS)


def describe(kind):
    if kind not in SCHEMA:
        raise KeyError(kind)
    required, optional = SCHEMA[kind]
    return {
        "id": kind,
        "name": NAMES[kind],
        "required": list(required),
        "optional": dict(optional),
    }


def _check_name(value):
    if not isinstance(value, str):
        return False
    parts = value.split(".")
    for p in parts:
        if not p.isidentifier():
            return False
    return True


def _validate_params(kind, params):
    required, optional = SCHEMA[kind]
    all_known = set(required) | set(optional)
    for name in params:
        if name not in all_known:
            raise ValueError(f"unknown parameter: {name}")
    for name in required:
        if name not in params:
            raise ValueError(f"missing parameter: {name}")


def _validate_cases(cases):
    if not isinstance(cases, (list, tuple)):
        raise ValueError("cases must be a non-empty list (or tuple) of tuples")
    if len(cases) == 0:
        raise ValueError("cases must be a non-empty list (or tuple) of tuples")
    for c in cases:
        if not isinstance(c, tuple):
            raise ValueError("cases must be a non-empty list (or tuple) of tuples")


def _validate_args(args):
    if not isinstance(args, (list, tuple)):
        raise ValueError("args must be a tuple")


def _validate_module_func(kind, params):
    if "module" in params and not _check_name(params["module"]):
        raise ValueError(f"bad name: {params['module']!r}")
    if "func" in params and not _check_name(params["func"]):
        raise ValueError(f"bad name: {params['func']!r}")
    if "name" in params and not _check_name(params["name"]):
        raise ValueError(f"bad name: {params['name']!r}")


def generate(kind, **params):
    if kind not in SCHEMA:
        raise KeyError(kind)
    _validate_params(kind, params)
    _validate_module_func(kind, params)
    if kind == "K01":
        return _gen_k01(params)
    elif kind == "K02":
        return _gen_k02(params)
    elif kind == "K03":
        return _gen_k03(params)
    elif kind == "K04":
        return _gen_k04(params)
    elif kind == "K05":
        return _gen_k05(params)
    elif kind == "K06":
        return _gen_k06(params)
    elif kind == "K07":
        return _gen_k07(params)
    elif kind == "K08":
        return _gen_k08(params)
    elif kind == "K09":
        return _gen_k09(params)
    elif kind == "K10":
        return _gen_k10(params)
    elif kind == "K11":
        return _gen_k11(params)
    elif kind == "K12":
        return _gen_k12(params)
    elif kind == "K13":
        return _gen_k13(params)
    elif kind == "K14":
        return _gen_k14(params)
    elif kind == "K15":
        return _gen_k15(params)
    else:
        raise NotImplementedError(f"kind {kind} not yet implemented")


def _gen_k01(params):
    module = params["module"]
    func = params["func"]
    cases = params["cases"]
    _validate_cases(cases)
    for c in cases:
        if len(c) != 2:
            raise ValueError("cases must be a non-empty list (or tuple) of tuples")
        args_tuple, expected = c
        if not isinstance(args_tuple, tuple):
            raise ValueError("cases must be a non-empty list (or tuple) of tuples")
    lines = [f"from {module} import {func}"]
    for args_tuple, expected in cases:
        args_str = ", ".join(repr(a) for a in args_tuple)
        lines.append(f"assert {func}({args_str}) == {repr(expected)}")
    lines.append("")
    return "\n".join(lines)


def _gen_k02(params):
    module = params["module"]
    func = params["func"]
    args = params["args"]
    _validate_args(args)
    lines = [
        f"from {module} import {func}",
        "import copy",
        "args = " + repr(args),
        "args_copy = copy.deepcopy(args)",
        f"{func}(*args)",
        "assert args == args_copy",
        "",
    ]
    return "\n".join(lines)


def _gen_k03(params):
    module = params["module"]
    func = params["func"]
    values = params.get("values", (None, "", [], {}))
    prefix = params.get("prefix", ())
    prefix_args = ", ".join(repr(v) for v in prefix)
    lines = [f"from {module} import {func}"]
    for v in values:
        if prefix_args:
            lines.append(f"{func}({prefix_args}, {repr(v)})")
        else:
            lines.append(f"{func}({repr(v)})")
    lines.append("")
    return "\n".join(lines)


def _gen_k04(params):
    module = params["module"]
    func = params["func"]
    name = params["name"]
    cases = params["cases"]
    prefix = params.get("prefix", ())
    _validate_cases(cases)
    for c in cases:
        if len(c) != 2:
            raise ValueError("cases must be a non-empty list (or tuple) of tuples")
    prefix_args = ", ".join(repr(v) for v in prefix)
    lines = [f"from {module} import {func}"]
    for value, expected in cases:
        if prefix_args:
            lines.append(f"assert {func}({prefix_args}, {name}={repr(value)}) == {repr(expected)}")
        else:
            lines.append(f"assert {func}({name}={repr(value)}) == {repr(expected)}")
    lines.append("")
    return "\n".join(lines)


def _gen_k05(params):
    module = params["module"]
    func = params["func"]
    args = params["args"]
    field = params.get("field", "id")
    _validate_args(args)
    lines = [
        f"from {module} import {func}",
        "import copy",
        "args = " + repr(args),
        "result = " + f"{func}(*args)",
        f"assert [item['{field}'] for item in result] == sorted([item['{field}'] for item in result])",
        "",
    ]
    return "\n".join(lines)

def _gen_k06(params):
    module = params["module"]
    func = params["func"]
    args = params["args"]
    _validate_args(args)
    lines = [
        "import copy",
        f"from {module} import {func}",
        "args = " + repr(args),
        "args_copy1 = copy.deepcopy(args)",
        "args_copy2 = copy.deepcopy(args)",
        f"result1 = {func}(*args_copy1)",
        f"result2 = {func}(*args_copy2)",
        "assert result1 == result2",
        "",
    ]
    return "\n".join(lines)


def _gen_k07(params):
    module = params["module"]
    func = params["func"]
    cases = params["cases"]
    _validate_cases(cases)
    for c in cases:
        if len(c) != 3:
            raise ValueError("cases must be tuples of (args_tuple, exception_name, message)")
        args_tuple, exception_name, message = c
        if not isinstance(args_tuple, tuple):
            raise ValueError("args_tuple must be a tuple")
        if not isinstance(exception_name, str):
            raise ValueError("exception_name must be a string")
        exc_class = getattr(builtins, exception_name, None)
        if exc_class is None or not isinstance(exc_class, type) or not issubclass(exc_class, BaseException):
            raise ValueError(f"not an exception: {exception_name!r}")
    lines = [
        f"from {module} import {func}",
        "import copy",
    ]
    for args_tuple, exception_name, message in cases:
        args_str = ", ".join(repr(a) for a in args_tuple)
        lines.append(f"try:")
        lines.append(f"    {func}({args_str})")
        lines.append(f"    assert False, 'expected {exception_name}'")
        lines.append(f"except {exception_name} as e:")
        lines.append(f"    assert str(e) == {repr(message)}")
    lines.append("")
    return "\n".join(lines)


def _gen_k08(params):
    module = params["module"]
    func = params["func"]
    args = params["args"]
    field = params.get("field", "id")
    _validate_args(args)
    lines = [
        f"from {module} import {func}",
        "import copy",
        "args = " + repr(args),
        "before = [item['" + field + "'] for item in args[0]]",
        "result = " + f"{func}(*args)",
        "after = [item['" + field + "'] for item in result]",
        "assert after == [key for key in before if key in after]",
        "",
    ]
    return "\n".join(lines)


def _gen_k09(params):
    module = params["module"]
    func = params["func"]
    cases = params["cases"]
    tol = params.get("tol", 0.01)
    _validate_cases(cases)
    for c in cases:
        if len(c) != 2:
            raise ValueError("cases must be tuples of (args_tuple, expected_number)")
        args_tuple, expected = c
        if not isinstance(args_tuple, tuple):
            raise ValueError("args_tuple must be a tuple")
    lines = [
        f"from {module} import {func}",
        f"tol = {repr(tol)}",
    ]
    for args_tuple, expected in cases:
        args_str = ", ".join(repr(a) for a in args_tuple)
        lines.append(f"assert abs({func}({args_str}) - {repr(expected)}) < tol")
    lines.append("")
    return "\n".join(lines)


def _gen_k10(params):
    pattern = params["pattern"]
    heads = params["heads"]
    head_prefix = params.get("head_prefix", "## ")
    first_regex = params.get("first_regex", "")
    contains = params.get("contains", ())
    lines = [
        "from pathlib import Path",
        "import re",
        "pattern = " + repr(pattern),
        "matches = sorted(Path('.').glob(pattern))",
        "assert len(matches) == 1",
        "text = matches[0].read_text()",
        "lines = text.splitlines()",
        "expected_heads = " + repr(heads),
        "actual_heads = [line.strip() for line in lines if line.startswith(" + repr(head_prefix) + ")]",
        "assert actual_heads == expected_heads",
    ]
    if first_regex:
        lines.append(f"assert re.match({repr(first_regex)}, lines[0])")
    for item in contains:
        lines.append(f"assert {repr(item)} in text")
    lines.append("")
    return "\n".join(lines)

def _gen_k11(params):
    import re
    path = params["path"]
    first_regex = params["first_regex"]
    max_first = params.get("max_first", 72)
    blank_second = params.get("blank_second", True)
    body_lines = params.get("body_lines", 1)
    lines = []
    lines.append(f"path = {repr(path)}")
    lines.append("import re")
    lines.append(f"with open(path, 'r', encoding='utf-8') as f:")
    lines.append("    text = f.read()")
    lines.append("lines = text.splitlines()")
    lines.append(f"assert re.match({repr(first_regex)}, lines[0])")
    lines.append(f"assert len(lines[0]) <= {max_first}")
    if blank_second:
        lines.append("assert len(lines) >= 3")
        lines.append("assert lines[1] == ''")
    lines.append(f"non_blank = [l for l in lines[1:] if l.strip()]")
    lines.append(f"assert len(non_blank) >= {body_lines}")
    lines.append("")
    return "\n".join(lines)


def _gen_k12(params):
    module = params["module"]
    lines = []
    lines.append(f"module = {repr(module)}")
    lines.append("import ast")
    lines.append("import importlib")
    lines.append("import importlib.util")
    lines.append("mod = importlib.import_module(module)")
    lines.append("src = importlib.util.find_spec(module).origin")
    lines.append("with open(src, 'r', encoding='utf-8') as f:")
    lines.append("    source = f.read()")
    lines.append("tree = ast.parse(source)")
    lines.append("banned_modules = ['os', 'subprocess', 'socket', 'urllib', 'http', 'requests', 'shutil', 'pathlib', 'sys', 'ctypes']")
    lines.append("banned_calls = ['open', 'exec', 'eval', 'input']")
    lines.append("for node in ast.walk(tree):")
    lines.append("    if isinstance(node, ast.Import):")
    lines.append("        for alias in node.names:")
    lines.append("            top = alias.name.split('.')[0]")
    lines.append("            assert top not in banned_modules, f'banned import: {top}'")
    lines.append("    elif isinstance(node, ast.ImportFrom):")
    lines.append("        if node.module:")
    lines.append("            top = node.module.split('.')[0]")
    lines.append("            assert top not in banned_modules, f'banned import from: {top}'")
    lines.append("    elif isinstance(node, ast.Call):")
    lines.append("        if isinstance(node.func, ast.Name):")
    lines.append("            assert node.func.id not in banned_calls, f'banned call: {node.func.id}'")
    lines.append("        elif isinstance(node.func, ast.Attribute):")
    lines.append("            assert node.func.attr not in banned_calls, f'banned call: {node.func.attr}'")
    lines.append("")
    return "\n".join(lines)

def _gen_k13(params):
    module = params["module"]
    func = params["func"]
    cases = params["cases"]
    lines = [f"from {module} import {func}"]
    for args_tuple, maximum, marker in cases:
        args_str = ", ".join(repr(a) for a in args_tuple)
        lines.append(f"out = {func}({args_str}).splitlines()")
        lines.append(f"assert len(out) <= {maximum}")
        lines.append(f"assert out[-1] == {repr(marker)}")
    lines.append("")
    return "\n".join(lines)


def _gen_k14(params):
    module = params["module"]
    lines = []
    lines.append(f"module = {repr(module)}")
    lines.append("import ast")
    lines.append("import importlib")
    lines.append("import importlib.util")
    lines.append("import tokenize")
    lines.append("import io")
    lines.append("mod = importlib.import_module(module)")
    lines.append("src = importlib.util.find_spec(module).origin")
    lines.append("with open(src, 'r', encoding='utf-8') as f:")
    lines.append("    source = f.read()")
    lines.append("tree = ast.parse(source)")
    lines.append("tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))")
    lines.append("for tok in tokens:")
    lines.append("    if tok.type == tokenize.COMMENT:")
    lines.append("        assert False, f'comment found: {tok.string}'")
    lines.append("for node in ast.walk(tree):")
    lines.append("    if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):")
    lines.append("        docstring = ast.get_docstring(node)")
    lines.append("        if docstring:")
    lines.append("            assert False, f'docstring found in {type(node).__name__}'")
    lines.append("for node in ast.walk(tree):")
    lines.append("    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):")
    lines.append("        for child in ast.walk(node):")
    lines.append("            if isinstance(child, (ast.Import, ast.ImportFrom)):")
    lines.append("                assert False, f'import nested in {type(node).__name__}'")
    lines.append("imported_names = set()")
    lines.append("for node in ast.walk(tree):")
    lines.append("    if isinstance(node, ast.Import):")
    lines.append("        for alias in node.names:")
    lines.append("            imported_names.add(alias.asname if alias.asname else alias.name.split('.')[0])")
    lines.append("    elif isinstance(node, ast.ImportFrom):")
    lines.append("        for alias in node.names:")
    lines.append("            imported_names.add(alias.asname if alias.asname else alias.name)")
    lines.append("for name in imported_names:")
    lines.append("    found = False")
    lines.append("    for node in ast.walk(tree):")
    lines.append("        if isinstance(node, ast.Name) and node.id == name:")
    lines.append("            found = True")
    lines.append("            break")
    lines.append("    assert found, f'imported name {name!r} not used'")
    lines.append("")
    return "\n".join(lines)

def _gen_k15(params):
    previous = params["previous"]
    new = params["new"]
    prev_content = previous.rstrip('\n')
    prev_lines = prev_content.split('\n') if prev_content else []
    new_content = new.rstrip('\n')
    new_lines = new_content.split('\n') if new_content else []
    prev_non_blank = set(l for l in prev_lines if l.strip())
    result_lines = list(prev_lines)
    for line in new_lines:
        if line.strip() and line in prev_non_blank:
            continue
        result_lines.append(line)
    result = '\n'.join(result_lines) + '\n'
    lines = []
    for line in result.split('\n'):
        if line:
            lines.append(line)
    lines.append("")
    return "\n".join(lines)


def build_test(items):
    if not items:
        return "\n"
    seen_imports = set()
    all_lines = []
    for kind, params_dict in items:
        code = generate(kind, **params_dict)
        for line in code.splitlines():
            if line.startswith("import ") or line.startswith("from "):
                if line not in seen_imports:
                    seen_imports.add(line)
                    all_lines.append(line)
            else:
                all_lines.append(line)
    result = "\n".join(all_lines)
    if result and not result.endswith("\n"):
        result += "\n"
    if not result:
        result = "\n"
    return result
