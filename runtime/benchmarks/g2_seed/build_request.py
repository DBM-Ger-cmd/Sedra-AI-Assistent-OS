import re

import assert_catalog

NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
LABELS = {"K01": "Beispiele", "K02": "Argumente unverändert", "K03": "leere Eingaben", "K04": "Grenzen", "K05": "feste Reihenfolge bei Gleichstand",
          "K06": "gleiche Eingabe, gleiches Ergebnis", "K07": "Ausnahmen", "K08": "Eingabereihenfolge bleibt", "K09": "Zahlen mit Toleranz", "K10": "Datei-Ergebnis",
          "K11": "Textformat", "K12": "reiner Baustein", "K13": "Ausgabegrenze", "K14": "Bauform", "K15": "Vorstufen gelten weiter"}


def _check_problem(check):
    if not isinstance(check, dict) or not isinstance(check.get("params"), dict):
        return "bad check"
    kind = check.get("kind")
    if kind not in assert_catalog.kinds():
        return f"unknown kind {kind}"
    try:
        assert_catalog.generate(kind, **check["params"])
    except (ValueError, KeyError, TypeError) as error:
        return str(error)
    return None


def validate_request(request):
    problems = []
    if not isinstance(request.get("name"), str) or not NAME.fullmatch(request["name"]):
        problems.append("bad name")
    stages = request.get("stages")
    if not isinstance(stages, list) or not stages:
        return problems + ["no stages"]
    seen = set()
    for stage in stages:
        name = stage.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            problems.append(f"bad stage name: {name!r}")
            continue
        if name in seen:
            problems.append(f"stage name twice: {name}")
        seen.add(name)
        if not str(stage.get("task") or "").strip():
            problems.append(f"stage {name}: no task")
        checks = stage.get("checks")
        if not isinstance(checks, list) or not checks:
            problems.append(f"stage {name}: no checks")
            continue
        for number, check in enumerate(checks, 1):
            problem = _check_problem(check)
            if problem:
                problems.append(f"stage {name} check {number}: {problem}")
    return problems


def _items(stage):
    return [(check["kind"], check["params"]) for check in stage["checks"]]


def stage_tests(request):
    items, tests = [], []
    for stage in request["stages"]:
        items = items + _items(stage)
        tests.append(assert_catalog.build_test(items))
    return tests


def render_spec(request):
    problems = validate_request(request)
    if problems:
        raise ValueError(f"invalid request: {problems[0]}")
    title = " ".join(str(request.get("title") or request["name"]).split())
    stages = []
    for index, (stage, code) in enumerate(zip(request["stages"], stage_tests(request)), 1):
        stages.append({"name": stage["name"], "no_own_check": True, "task": stage["task"], "hidden": {f"hidden_{request['name']}_{index}.py": code}})
    lines = [f"TITLE = {title!r}", f"NOTES = {str(request.get('notes') or '')!r}", "", "STAGES = ["]
    lines += [f"    {stage!r}," for stage in stages]
    return "\n".join(lines + ["]"]) + "\n"


def cases_from_examples(examples):
    if not isinstance(examples, list) or not examples:
        raise ValueError("no examples")
    cases = []
    for example in examples:
        if not isinstance(example, dict) or "input" not in example or "output" not in example:
            raise ValueError("bad example")
        given = example["input"]
        cases.append((tuple(given) if isinstance(given, (list, tuple)) else (given,), example["output"]))
    return cases


def _label(check):
    if check["kind"] == "K01":
        count = len(check["params"]["cases"])
        return f"{count} Beispiel" + ("" if count == 1 else "e")
    return LABELS[check["kind"]]


def card_text(request):
    problems = validate_request(request)
    if problems:
        raise ValueError(f"invalid request: {problems[0]}")
    title = " ".join(str(request.get("title") or request["name"]).split())
    lines = [f"Spec-Karte: {title} ({request['name']})"]
    for number, stage in enumerate(request["stages"], 1):
        first = " ".join(str(stage["task"]).split())
        lines.append(f"Stufe {number}: {stage['name']} – {first[:100]}")
        lines.append("  geprüft wird: " + " · ".join(_label(check) for check in stage["checks"]))
    return "\n".join(lines) + "\n"
