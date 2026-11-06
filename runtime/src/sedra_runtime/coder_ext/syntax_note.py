import ast
import json
import tomllib


def _make_caret(offset):
    return " " * (offset - 1) + "^"


def _check_py(path, text):
    try:
        ast.parse(text)
        return None
    except SyntaxError as exc:
        lines = text.split("\n")
        lineno = exc.lineno
        msg = exc.msg
        offset = exc.offset
        parts = ["syntax error in " + path + " line " + str(lineno) + ": " + msg]
        if isinstance(lineno, int) and 1 <= lineno <= len(lines):
            parts.append(lines[lineno - 1].rstrip())
            if isinstance(offset, int) and offset >= 1:
                parts.append(_make_caret(offset))
        return "\n".join(parts)


def _check_json(path, text):
    try:
        json.loads(text)
        return None
    except json.JSONDecodeError as exc:
        return "invalid JSON in " + path + " line " + str(exc.lineno) + " column " + str(exc.colno) + ": " + exc.msg


def _check_toml(path, text):
    try:
        tomllib.loads(text)
        return None
    except tomllib.TOMLDecodeError as exc:
        return "invalid TOML in " + path + ": " + str(exc)


def note(path, text):
    if not isinstance(path, str) or not isinstance(text, str):
        return None
    dot = path.rfind(".")
    if dot == -1:
        return None
    suffix = path[dot:].lower()
    checks = {".py": _check_py, ".json": _check_json, ".toml": _check_toml}
    fn = checks.get(suffix)
    if fn is None:
        return None
    return fn(path, text)
