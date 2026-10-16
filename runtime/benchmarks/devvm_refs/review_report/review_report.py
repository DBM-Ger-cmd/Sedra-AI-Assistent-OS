import ast
import io
import tokenize

DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
IMPORTS = (ast.Import, ast.ImportFrom)
QUESTION = "Ist der Test richtig (dann wird der Code geändert) oder ist der Code richtig (dann wird der Test geändert)? Antwort: 'Test' oder 'Code'."


def _finding(path, line, kind, text):
    return {"path": path, "line": line, "kind": kind, "text": text}


def _bound_names(node):
    if isinstance(node, ast.Import):
        return [(alias.asname or alias.name.split(".")[0]) for alias in node.names]
    if node.module == "__future__":
        return []
    return [(alias.asname or alias.name) for alias in node.names if alias.name != "*"]


def _is_docstring(node):
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def findings_from_source(path, text):
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return [_finding(path, error.lineno or 1, "syntax", f"Syntaxfehler: {error.msg}")]
    found = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            found.append(_finding(path, token.start[0], "comment", "Kommentar"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module,) + DEFS) and ast.get_docstring(node):
            found.append(_finding(path, node.body[0].lineno, "docstring", "Docstring"))
    nested = {child.lineno for node in ast.walk(tree) if isinstance(node, DEFS) for child in ast.walk(node) if isinstance(child, IMPORTS)}
    found += [_finding(path, line, "nested_import", "Import in Funktion oder Klasse") for line in nested]
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    seen_code = False
    for statement in tree.body:
        if isinstance(statement, IMPORTS):
            if seen_code:
                found.append(_finding(path, statement.lineno, "late_import", "Import nicht am Dateianfang"))
            found += [_finding(path, statement.lineno, "unused_import", f"Import nicht benutzt: {name}") for name in _bound_names(statement) if name not in used]
        elif not (_is_docstring(statement) and statement is tree.body[0]):
            seen_code = True
    return sorted(found, key=lambda item: (item["line"], item["kind"]))


def parse_answer(text):
    words = "".join(ch if ch.isalpha() else " " for ch in str(text or "").lower()).split()
    return words[0] if words and words[0] in ("test", "code") else None


def question(stage, line, error=""):
    head = f"Stufe {stage} scheitert an: {line}" + (f" ({error})" if error else "")
    return head + "\n" + QUESTION


def report(data):
    stages = data.get("stages") or []
    passed = sum(1 for stage in stages if stage["passed"])
    result = f"Ergebnis: {passed} von {len(stages)} Stufen bestanden"
    if data.get("calls") is not None and data.get("seconds") is not None:
        result += f", {data['calls']} Aufrufe, {data['seconds']:.0f} s"
    files = data.get("files") or []
    lines = [f"Abnahme-Bericht: {data.get('spec') or '?'}", result,
             "Dateien: " + (", ".join(f"{f['path']} ({f['lines']} Zeilen)" for f in files) if files else "keine")]
    findings = data.get("findings") or []
    if findings:
        lines.append(f"Befunde ({len(findings)}):")
        lines += [f"  {f['path']}:{f['line']} {f['text']}" for f in findings]
    else:
        lines.append("Befunde: keine")
    failure = data.get("failure")
    if failure:
        lines.append(f"Fehlschlag: Stufe {failure['stage']}: {failure['line']}")
        lines.append(question(failure["stage"], failure["line"], failure.get("error", "")))
    if failure:
        advice = "erst klären, ob Test oder Code stimmt (siehe Frage)"
    elif stages and passed == len(stages):
        advice = "Übernahme vorschlagen" if not findings else f"Übernahme nach Korrektur der Befunde ({len(findings)})"
    else:
        advice = "Bau fortsetzen oder Spec prüfen"
    return "\n".join(lines + [f"Empfehlung: {advice}"]) + "\n"
