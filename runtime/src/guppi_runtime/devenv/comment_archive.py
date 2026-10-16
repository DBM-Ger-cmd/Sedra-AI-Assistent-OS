"""Finds every comment and docstring of a Python source with line, owner and text and writes them as JSON lines, so that `tidy` can save them before it strips them (AM-010, written by Claude on the Captain's decision of 2026-10-09)."""
import ast
import io
import json
import tokenize

SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _scopes(tree):
    found = []

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, SCOPES):
                name = prefix + child.name
                found.append((name, child))
                walk(child, name + ".")
            else:
                walk(child, prefix)

    walk(tree, "")
    return found


def _owner(scopes, line):
    best = "<module>"
    for name, node in scopes:
        if node.lineno <= line <= node.end_lineno and (best == "<module>" or len(name) > len(best)):
            best = name
    return best


def _docstrings(tree, scopes):
    owners = [("<module>", tree)] + scopes
    found = []
    for name, node in owners:
        first = node.body[0] if node.body else None
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            found.append({"line": first.lineno, "kind": "docstring", "owner": name, "inline": False, "text": first.value.value})
    return found


def _comments(source, scopes):
    found = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        row, column = token.start
        if row <= 2 and (token.string.startswith("#!") or "coding" in token.string):
            continue
        found.append({"line": row, "kind": "comment", "owner": _owner(scopes, row), "inline": bool(token.line[:column].strip()), "text": token.string[1:].strip()})
    return found


def extract_comments(source):
    if not isinstance(source, str):
        return []
    try:
        tree = ast.parse(source)
        scopes = _scopes(tree)
        return sorted(_docstrings(tree, scopes) + _comments(source, scopes), key=lambda e: (e["line"], e["kind"]))
    except (SyntaxError, ValueError, tokenize.TokenError, IndentationError):
        return []


def to_jsonl(entries, meta):
    base = meta if isinstance(meta, dict) else {}
    lines = [json.dumps({**base, **entry}, sort_keys=True, ensure_ascii=False) + "\n" for entry in entries or () if isinstance(entry, dict)]
    return "".join(lines)
