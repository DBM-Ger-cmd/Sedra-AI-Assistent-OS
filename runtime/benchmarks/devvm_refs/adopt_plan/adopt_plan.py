import posixpath

IGNORED_NAMES = ("NOTES.md",)
IGNORED_PREFIXES = ("hidden_", "check_")
SHIM_REASON = "shim: edit the file in the subpackage"
E1_REASON = "e1 allows only new files"
EXISTS_REASON = "exists: review the diff"


def _skip_reason(path):
    parts = path.split("/")
    name = parts[-1]
    if "__pycache__" in parts:
        return "cache"
    if name in IGNORED_NAMES or name.startswith(IGNORED_PREFIXES):
        return "helper file of the build"
    if not name.endswith(".py"):
        return "not a module"
    return None


def _entry(source, target_dir, existing, shims, mode):
    reason = _skip_reason(source)
    if reason:
        return {"source": source, "target": None, "action": "skip", "reason": reason}
    target = posixpath.join(target_dir, source)
    if target in shims:
        return {"source": source, "target": target, "action": "refuse", "reason": SHIM_REASON}
    if target in existing:
        if mode == "e1":
            return {"source": source, "target": target, "action": "refuse", "reason": E1_REASON}
        return {"source": source, "target": target, "action": "replace", "reason": EXISTS_REASON}
    return {"source": source, "target": target, "action": "create", "reason": ""}


def plan_adoption(candidate_files, target_dir, existing, shims=(), mode="e2", tests_dir="runtime/tests"):
    existing, shims = set(existing), set(shims)
    entries = [_entry(path, target_dir, existing, shims, mode) for path in sorted(candidate_files)]
    tests, seen = [], set()
    for entry in entries:
        if entry["action"] in ("create", "replace"):
            test = posixpath.join(tests_dir, "test_" + posixpath.basename(entry["source"]))
            if test not in seen:
                seen.add(test)
                tests.append({"module": entry["target"], "test": test, "exists": test in existing})
    changes = [e for e in entries if e["action"] in ("create", "replace")]
    return {"entries": entries, "tests": tests, "needs_gate": bool(changes), "ok": not any(e["action"] == "refuse" for e in entries)}


def describe(plan):
    words = {"create": "neu", "replace": "ersetzen", "refuse": "abgelehnt", "skip": "übersprungen"}
    lines = [f"Übernahmeplan ({len(plan['entries'])} Dateien)"]
    for entry in plan["entries"]:
        name = entry["target"] or entry["source"]
        lines.append(f"  {words[entry['action']]}: {name}" + (f" ({entry['reason']})" if entry["reason"] else ""))
    for test in plan["tests"]:
        lines.append(f"Tests: {test['test']}" if test["exists"] else f"Test fehlt: {test['test']} (neuer Test nötig)")
    lines.append("Freigabe nötig: " + ("ja" if plan["needs_gate"] else "nein"))
    lines.append("Plan ausführbar: " + ("ja" if plan["ok"] else "nein"))
    return "\n".join(lines) + "\n"


def copy_pairs(plan, candidate_dir):
    if not plan["ok"]:
        raise ValueError("plan_not_ok")
    return [(posixpath.join(candidate_dir, e["source"]), e["target"]) for e in plan["entries"] if e["action"] in ("create", "replace")]
