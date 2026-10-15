import ast
import tokenize
import io


def _findings_from_syntax_error(text):
    try:
        ast.parse(text)
    except SyntaxError as exc:
        line = exc.lineno if exc.lineno is not None else 1
        return [{"path": None, "line": line, "kind": "syntax", "text": f"Syntaxfehler: {exc.msg}"}]
    return []


def _findings_from_comments(text):
    findings = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    except tokenize.TokenError:
        return findings
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            findings.append({"path": None, "line": tok.start[0], "kind": "comment", "text": "Kommentar"})
    return findings


def _findings_from_docstrings(tree):
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and _is_docstring_stmt(body[0]):
                line = body[0].lineno
                findings.append({"path": None, "line": line, "kind": "docstring", "text": "Docstring"})
    return findings


def _is_import_stmt(node):
    return isinstance(node, (ast.Import, ast.ImportFrom))


def _is_docstring_stmt(node):
    if isinstance(node, ast.Expr):
        if isinstance(node.value, ast.Constant):
            return isinstance(node.value.value, str)
    return False


def _find_nested_imports(tree):
    findings = []

    def _walk(node, in_func_or_class):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                _walk(child, True)
            elif _is_import_stmt(child):
                if in_func_or_class:
                    findings.append({"path": None, "line": child.lineno, "kind": "nested_import", "text": "Import in Funktion oder Klasse"})
                _walk(child, in_func_or_class)
            else:
                _walk(child, in_func_or_class)

    _walk(tree, False)
    return findings


def _find_late_imports(tree):
    findings = []
    body = tree.body
    if not body:
        return findings

    first_is_docstring = _is_docstring_stmt(body[0])

    start_idx = 0
    if first_is_docstring:
        start_idx = 1

    found_non_import_non_docstring = False
    for i in range(start_idx, len(body)):
        node = body[i]
        if _is_import_stmt(node):
            if found_non_import_non_docstring:
                findings.append({"path": None, "line": node.lineno, "kind": "late_import", "text": "Import nicht am Dateianfang"})
        else:
            found_non_import_non_docstring = True

    return findings


def _get_bound_names(import_node):
    if isinstance(import_node, ast.Import):
        names = []
        for alias in import_node.names:
            if alias.asname:
                names.append(alias.asname)
            else:
                names.append(alias.name.split('.')[0])
        return names
    elif isinstance(import_node, ast.ImportFrom):
        if import_node.module and import_node.module == '__future__':
            return []
        if import_node.names and any(alias.name == '*' for alias in import_node.names):
            return []
        names = []
        for alias in import_node.names:
            if alias.asname:
                names.append(alias.asname)
            else:
                names.append(alias.name)
        return names
    return []


def _find_unused_imports(tree):
    findings = []

    name_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            name_ids.add(node.id)

    for node in tree.body:
        if _is_import_stmt(node):
            bound_names = _get_bound_names(node)
            for name in bound_names:
                if name not in name_ids:
                    findings.append({"path": None, "line": node.lineno, "kind": "unused_import", "text": f"Import nicht benutzt: {name}"})

    return findings


def findings_from_source(path, text):
    findings = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        findings = _findings_from_syntax_error(text)
        for f in findings:
            f["path"] = path
        return findings
    findings.extend(_findings_from_comments(text))
    findings.extend(_findings_from_docstrings(tree))
    findings.extend(_find_nested_imports(tree))
    findings.extend(_find_late_imports(tree))
    findings.extend(_find_unused_imports(tree))
    findings.sort(key=lambda f: (f["line"], f["kind"]))
    for f in findings:
        f["path"] = path
    return findings


QUESTION = "Ist der Test richtig (dann wird der Code geändert) oder ist der Code richtig (dann wird der Test geändert)? Antwort: 'Test' oder 'Code'."


def parse_answer(text):
    if text is None:
        return None
    text = "".join(c if c.isalpha() else " " for c in text)
    text = text.lower()
    words = text.split()
    if not words:
        return None
    if words[0] in ("test", "code"):
        return words[0]
    return None


def question(stage, line, error=""):
    s = f"Stufe {stage} scheitert an: {line}"
    if error:
        s += f" ({error})"
    s += "\n" + QUESTION
    return s


def report(data):
    lines = []
    spec = data.get("spec")
    lines.append(f"Abnahme-Bericht: {spec if spec is not None else '?'}")
    stages = data.get("stages")
    if stages is not None:
        passed = sum(1 for s in stages if s.get("passed"))
        lines.append(f"Ergebnis: {passed} von {len(stages)} Stufen bestanden")
    else:
        lines.append("Ergebnis: 0 von 0 Stufen bestanden")
    calls = data.get("calls")
    seconds = data.get("seconds")
    if calls is not None and seconds is not None:
        lines[-1] += f", {calls} Aufrufe, {seconds:.0f} s"
    files = data.get("files")
    if files is not None and len(files) > 0:
        file_strs = [f"{f['path']} ({f['lines']} Zeilen)" for f in files]
        lines.append("Dateien: " + ", ".join(file_strs))
    else:
        lines.append("Dateien: keine")
    findings = data.get("findings")
    if findings is not None and len(findings) > 0:
        lines.append(f"Befunde ({len(findings)}):")
        for f in findings:
            path = f.get("path")
            line = f.get("line")
            text = f.get("text", "")
            lines.append(f"  {path}:{line} {text}")
    else:
        lines.append("Befunde: keine")
    failure = data.get("failure")
    if failure is not None:
        stage = failure["stage"]
        line = failure["line"]
        error = failure.get("error", "")
        lines.append(f"Fehlschlag: Stufe {stage}: {line}")
        lines.append(question(stage, line, error))
    if failure is not None:
        lines.append("Empfehlung: erst klären, ob Test oder Code stimmt (siehe Frage)")
    elif stages is not None and len(stages) > 0:
        all_passed = all(s.get("passed") for s in stages)
        if all_passed:
            if findings is not None and len(findings) > 0:
                lines.append(f"Empfehlung: Übernahme nach Korrektur der Befunde ({len(findings)})")
            else:
                lines.append("Empfehlung: Übernahme vorschlagen")
        else:
            lines.append("Empfehlung: Bau fortsetzen oder Spec prüfen")
    else:
        lines.append("Empfehlung: Bau fortsetzen oder Spec prüfen")
    return "\n".join(lines) + "\n"
