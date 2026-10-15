import posixpath

CHANGING_ACTIONS = ("create", "replace")


def plan_adoption(candidate_files, target_dir, existing, shims=(), mode="e2", tests_dir="runtime/tests"):
    existing_set = set(existing)
    shims_set = set(shims)
    entries = []
    for src in sorted(candidate_files):
        parts = src.split("/")
        if "__pycache__" in parts:
            entries.append({"source": src, "target": None, "action": "skip", "reason": "cache"})
            continue
        name = parts[-1]
        if name == "NOTES.md" or name.startswith("hidden_") or name.startswith("check_"):
            entries.append({"source": src, "target": None, "action": "skip", "reason": "helper file of the build"})
            continue
        if not name.endswith(".py"):
            entries.append({"source": src, "target": None, "action": "skip", "reason": "not a module"})
            continue
        tgt = posixpath.join(target_dir, src)
        if tgt in shims_set:
            entries.append({"source": src, "target": tgt, "action": "refuse", "reason": "shim: edit the file in the subpackage"})
        elif mode == "e1" and tgt in existing_set:
            entries.append({"source": src, "target": tgt, "action": "refuse", "reason": "e1 allows only new files"})
        elif tgt in existing_set:
            entries.append({"source": src, "target": tgt, "action": "replace", "reason": "exists: review the diff"})
        else:
            entries.append({"source": src, "target": tgt, "action": "create", "reason": ""})
    tests = []
    seen_tests = set()
    for entry in entries:
        if entry["action"] in CHANGING_ACTIONS:
            test_path = posixpath.join(tests_dir, "test_" + posixpath.basename(entry["source"]))
            if test_path not in seen_tests:
                seen_tests.add(test_path)
                tests.append({"module": entry["target"], "test": test_path, "exists": test_path in existing_set})
    needs_gate = any(e["action"] in CHANGING_ACTIONS for e in entries)
    ok = not any(e["action"] == "refuse" for e in entries)
    return {"entries": entries, "tests": tests, "needs_gate": needs_gate, "ok": ok}


def describe(plan):
    lines = []
    lines.append("Übernahmeplan (%d Dateien)" % len(plan["entries"]))
    action_word = {"create": "neu", "replace": "ersetzen", "refuse": "abgelehnt", "skip": "übersprungen"}
    for entry in plan["entries"]:
        word = action_word[entry["action"]]
        name = entry["target"] if entry["target"] is not None else entry["source"]
        if entry["reason"]:
            lines.append("  %s: %s (%s)" % (word, name, entry["reason"]))
        else:
            lines.append("  %s: %s" % (word, name))
    for test in plan["tests"]:
        if test["exists"]:
            lines.append("Tests: %s" % test["test"])
        else:
            lines.append("Test fehlt: %s (neuer Test nötig)" % test["test"])
    lines.append("Freigabe nötig: %s" % ("ja" if plan["needs_gate"] else "nein"))
    lines.append("Plan ausführbar: %s" % ("ja" if plan["ok"] else "nein"))
    return "\n".join(lines) + "\n"


def copy_pairs(plan, candidate_dir):
    if not plan["ok"]:
        raise ValueError("plan_not_ok")
    result = []
    for entry in plan["entries"]:
        if entry["action"] in CHANGING_ACTIONS:
            src_path = posixpath.join(candidate_dir, entry["source"])
            result.append((src_path, entry["target"]))
    return result
