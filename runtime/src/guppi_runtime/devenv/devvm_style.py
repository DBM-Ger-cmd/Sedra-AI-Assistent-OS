"""Style rules for the code the DevVM models write, checked and partly enforced by plain code (Captain 2026-10-08, after run-dcb1e529d460).

The measurements: 90 percent of a build's time is the models generating tokens, and the candidate of that run had 323 lines with 45 comment lines, docstrings and 8 helper files although
the task said "no comments". Asking the model to remove them costs another full answer, so comments and docstrings are removed by this module (`strip_comments`, an exact transformation of
the syntax tree and the tokens) and new helper files are deleted (`tidy`); only what needs thought (an over-long function, copied code) is reported.

`style_report` is the reference implementation of the suite `am006-style` (same behaviour, same tests); it parses text with `ast` and never imports or runs it.
"""
import ast
import io
import re
import tokenize

from ..comment_archive import extract_comments


class StyleError(ValueError):
    def __init__(self, code, message=""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


JUNK_NAME = re.compile(r"(debug|repro|reproduce|scratch|tmp|temp|run_tests?|test_runner|test_check|test_debug|check_)[A-Za-z0-9_]*\.py")


def _source(value):
    if not isinstance(value, str):
        raise StyleError("bad_source", type(value).__name__)
    return value


def _kind(line):
    text = line.strip()
    return "blank" if not text else "comment" if text.startswith("#") else "code"


def count_lines(source):
    lines = _source(source).splitlines()
    out = {"total": len(lines), "blank": 0, "comment": 0, "code": 0}
    for line in lines:
        out[_kind(line)] += 1
    return out


def function_lengths(source):
    try:
        tree = ast.parse(_source(source))
    except (SyntaxError, ValueError):
        raise StyleError("bad_source", "does not parse") from None
    found = [(n.name, n.lineno, n.end_lineno - n.lineno + 1) for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return [{"name": name, "lines": size} for name, _, size in sorted(found, key=lambda item: (item[0], item[1]))]


def duplicate_blocks(source, window=4):
    _source(source)
    if not isinstance(window, int) or isinstance(window, bool) or window < 2:
        raise StyleError("bad_window", repr(window))
    counted = [(number + 1, line.strip()) for number, line in enumerate(source.splitlines()) if _kind(line) == "code"]
    groups = {}
    for start in range(len(counted) - window + 1):
        groups.setdefault(tuple(text for _, text in counted[start:start + window]), []).append(start)
    out = []
    for text, starts in groups.items():
        taken = []
        for start in starts:
            if not taken or start >= taken[-1] + window:
                taken.append(start)
        if len(taken) >= 2:
            out.append({"lines": [counted[start][0] for start in taken], "text": "\n".join(text)})
    return sorted(out, key=lambda item: item["lines"][0])


def style_report(source, max_function_lines=40, window=4):
    if not isinstance(max_function_lines, int) or isinstance(max_function_lines, bool) or max_function_lines < 1:
        raise StyleError("bad_limit", repr(max_function_lines))
    lines, functions, duplicates = count_lines(source), function_lengths(source), duplicate_blocks(source, window)
    violations = []
    if lines["comment"]:
        violations.append("comments")
    if duplicates:
        violations.append("duplicate_code")
    if any(f["lines"] > max_function_lines for f in functions):
        violations.append("long_function")
    return {"ok": not violations, "lines": lines, "functions": functions, "duplicates": duplicates, "violations": sorted(violations)}


def _docstring_spans(tree):
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                spans.append((first.lineno, first.end_lineno, len(node.body) == 1 and not isinstance(node, ast.Module), first.col_offset))
    return spans


def strip_comments(source):
    """The source without comments and docstrings; a body that would be empty keeps a `pass`. Returns the source unchanged when it does not parse or the result would not parse."""
    _source(source)
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    lines = source.split("\n")
    for start, end, only_statement, column in sorted(_docstring_spans(tree), reverse=True):
        replacement = [" " * column + "pass"] if only_statement else []
        lines[start - 1:end] = replacement
    text = "\n".join(lines)
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return source
    rows = text.split("\n")
    for token in reversed(tokens):
        if token.type != tokenize.COMMENT:
            continue
        row, column = token.start
        if row <= 2 and (token.string.startswith("#!") or "coding" in token.string):
            continue
        before = rows[row - 1][:column]
        rows[row - 1] = before.rstrip() if before.strip() else None
    result = "\n".join(line for line in rows if line is not None)
    try:
        ast.parse(result)
    except SyntaxError:
        return source
    return re.sub(r"\n{4,}", "\n\n\n", result)


def _is_test(path):
    name = path.split("/")[-1]
    return path.startswith("tests/") or name.startswith("test_")


def snapshot(workspace):
    """{path: SHA-256} of the workspace files, taken before a model's turn."""
    import hashlib
    return {path: hashlib.sha256(workspace.read(path).encode("utf-8")).hexdigest() for path in workspace.tree()}


def _is_helper(path, expected):
    name = path.split("/")[-1]
    stem = name.removesuffix(".py")
    if "/" in path or not name.endswith(".py") or stem in expected or name.startswith("acceptance_"):
        return False
    if name.startswith("test_"):
        return stem.removeprefix("test_") not in expected
    return bool(JUNK_NAME.fullmatch(name))


def tidy(workspace, before, expected=()):
    """After a model's turn: deletes NEW helper files (debug, repro, scratch, root-level test files that are not `test_<requested module>.py`), strips comments and docstrings from the
    non-test Python files the turn created or changed (never from untouched seed files), and reports what needs thought. `before` is `snapshot(workspace)` from before the turn; `expected`
    the module names the task asks for. Returns {"stripped", "deleted", "report"}."""
    import hashlib
    stripped, deleted, report, comments = [], [], {}, {}
    for path in sorted(set(workspace.tree()) - set(before)):
        if _is_helper(path, expected):
            workspace.delete(path)
            deleted.append(path)
    for path in sorted(workspace.tree()):
        if not path.endswith(".py") or _is_test(path) or path.split("/")[-1].startswith("acceptance_"):
            continue
        text = workspace.read(path)
        if before.get(path) == hashlib.sha256(text.encode("utf-8")).hexdigest():
            continue
        cleaned = strip_comments(text)
        if cleaned != text:
            comments[path] = extract_comments(text)
            workspace.write(path, cleaned)
            stripped.append(path)
            text = cleaned
        try:
            found = style_report(text)
        except StyleError:
            continue
        if found["violations"]:
            report[path] = {"violations": found["violations"], "long_functions": [f for f in found["functions"] if f["lines"] > 40], "duplicates": len(found["duplicates"])}
    return {"stripped": stripped, "deleted": deleted, "report": report, "comments": comments}
