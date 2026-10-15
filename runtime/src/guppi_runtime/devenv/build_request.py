import re
import copy
from . import assert_catalog

_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

LABELS = {
    "K01": "Beispiele",
    "K02": "Argumente unverändert",
    "K03": "leere Eingaben",
    "K04": "Grenzen",
    "K05": "feste Reihenfolge bei Gleichstand",
    "K06": "gleiche Eingabe, gleiches Ergebnis",
    "K07": "Ausnahmen",
    "K08": "Eingabereihenfolge bleibt",
    "K09": "Zahlen mit Toleranz",
    "K10": "Datei-Ergebnis",
    "K11": "Textformat",
    "K12": "reiner Baustein",
    "K13": "Ausgabegrenze",
    "K14": "Bauform",
    "K15": "Vorstufen gelten weiter"
}


def validate_request(request):
    problems = []
    name = request.get("name")
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        problems.append("bad name")
    stages = request.get("stages")
    if not isinstance(stages, list) or len(stages) == 0:
        problems.append("no stages")
        return problems
    seen_stage_names = set()
    for stage in stages:
        sname = stage.get("name")
        if not isinstance(sname, str) or not _NAME_RE.fullmatch(sname):
            problems.append(f"bad stage name: {sname!r}")
            continue
        if sname in seen_stage_names:
            problems.append(f"stage name twice: {sname}")
        seen_stage_names.add(sname)
        task = stage.get("task")
        if not isinstance(task, str) or task.strip() == "":
            problems.append(f"stage {sname}: no task")
        checks = stage.get("checks")
        if not isinstance(checks, list) or len(checks) == 0:
            problems.append(f"stage {sname}: no checks")
            continue
        for n, check in enumerate(checks, 1):
            if not isinstance(check, dict) or "params" not in check or not isinstance(check.get("params"), dict):
                problems.append(f"stage {sname} check {n}: bad check")
                continue
            kind = check.get("kind")
            params = check["params"]
            if kind not in assert_catalog.kinds():
                problems.append(f"stage {sname} check {n}: unknown kind {kind}")
                continue
            try:
                assert_catalog.generate(kind, **params)
            except (ValueError, KeyError, TypeError) as e:
                problems.append(f"stage {sname} check {n}: {e}")
    return problems


def stage_tests(request):
    stages = request["stages"]
    result = []
    cumulative_checks = []
    for stage in stages:
        checks = stage.get("checks", [])
        cumulative_checks.extend([(check["kind"], check["params"]) for check in checks])
        result.append(assert_catalog.build_test(cumulative_checks))
    return result


def render_spec(request):
    problems = validate_request(request)
    if problems:
        raise ValueError("invalid request: " + problems[0])
    name = request["name"]
    title = request.get("title")
    notes = request.get("notes")
    stages = request["stages"]
    if title is not None and isinstance(title, str):
        title = " ".join(title.split())
        if title == "":
            title = name
    else:
        title = name
    if notes is None or not isinstance(notes, str):
        notes = ""
    stage_dicts = []
    cumulative_checks = []
    for n, stage in enumerate(stages, 1):
        sname = stage["name"]
        task = stage["task"]
        checks = stage.get("checks", [])
        cumulative_checks.extend([(check["kind"], check["params"]) for check in checks])
        test_text = assert_catalog.build_test(cumulative_checks)
        hidden = {"hidden_" + name + "_" + str(n) + ".py": test_text}
        stage_dicts.append({"name": sname, "no_own_check": True, "task": task, "hidden": hidden})
    lines = []
    lines.append("TITLE = " + repr(title))
    lines.append("NOTES = " + repr(notes))
    lines.append("STAGES = " + repr(stage_dicts))
    lines.append("")
    return "\n".join(lines)


def card_text(request):
    problems = validate_request(request)
    if problems:
        raise ValueError("invalid request: " + problems[0])
    name = request["name"]
    title = request.get("title")
    if title is not None and isinstance(title, str):
        title = " ".join(title.split())
        if title == "":
            title = name
    else:
        title = name
    lines = [f"Spec-Karte: {title} ({name})"]
    for n, stage in enumerate(request["stages"], 1):
        sname = stage["name"]
        task = " ".join(stage["task"].split())[:100]
        lines.append(f"Stufe {n}: {sname} \u2013 {task}")
        checks = stage.get("checks", [])
        labels = []
        for check in checks:
            kind = check["kind"]
            if kind == "K01":
                cases = check["params"].get("cases", [])
                count = len(cases)
                if count == 1:
                    labels.append("1 Beispiel")
                else:
                    labels.append(f"{count} Beispiele")
            else:
                labels.append(LABELS.get(kind, kind))
        lines.append("  geprüft wird: " + " \u00b7 ".join(labels))
    return "\n".join(lines) + "\n"


def cases_from_examples(examples):
    if not isinstance(examples, list) or len(examples) == 0:
        raise ValueError("no examples")
    result = []
    for ex in examples:
        if not isinstance(ex, dict) or "input" not in ex or "output" not in ex:
            raise ValueError("bad example")
        inp = ex["input"]
        out = ex["output"]
        if isinstance(inp, (list, tuple)):
            args = tuple(inp)
        else:
            args = (inp,)
        result.append((args, out))
    return result
