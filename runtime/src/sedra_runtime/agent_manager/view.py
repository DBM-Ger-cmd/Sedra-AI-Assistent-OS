"""Read-only view of the agent manager database for the UIX (route /api/agents). It opens the SQLite file in read-only mode: it can neither create nor change anything."""
import json
import os
import sqlite3


def agents_view(db_path):
    base = {"demo": True, "templates": [], "crews": [], "instances": [], "assignments": [], "note": None}
    if not os.path.isfile(db_path):
        return {**base, "note": "no agent manager database yet"}
    uri = "file:" + str(db_path).replace("\\", "/").replace("?", "%3f").replace("#", "%23") + "?mode=ro"
    db = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "entries" in names:
            for key, data in db.execute("SELECT key, data FROM entries WHERE kind = 'template' ORDER BY key"):
                entry = json.loads(data)
                preview = entry.get("preview") or {}
                base["templates"].append({"ref": key, "role": (entry.get("template") or {}).get("role"), "trust": entry.get("trust", "UNVERIFIED"),
                                          "ok": bool(preview.get("ok")), "problems": preview.get("problems", [])})
        if "entries" in names:
            for key, data in db.execute("SELECT key, data FROM entries WHERE kind = 'crew' ORDER BY key"):
                entry = json.loads(data)
                crew = entry.get("crew") or {}
                base["crews"].append({"ref": key, "purpose": crew.get("purpose"), "slots": len(crew.get("slots") or []), "steps": len(crew.get("workflow") or []), "problems": entry.get("problems", [])})
            for key, data, revision in db.execute("SELECT key, data, revision FROM entries WHERE kind = 'agent' ORDER BY key"):
                entry = json.loads(data)
                run = entry["suite_runs"][-1] if entry.get("suite_runs") else None
                base["instances"].append({"instance_id": key, "template_ref": entry.get("template_ref"), "qualification": entry.get("qualification", "UNVERIFIED"), "lifecycle": entry.get("lifecycle", "ACTIVE"),
                                          "admission": bool((entry.get("admission") or {}).get("valid")), "revoked": bool((entry.get("admission") or {}).get("revoked")),
                                          "suite": run["suite"] if run else None, "suite_passed": sum(r["status"] == "PASS" for r in run["results"]) if run else 0, "suite_total": len(run["results"]) if run else 0,
                                          "review": (entry.get("review") or {}).get("verdict"), "runs": (entry.get("stats") or {}).get("runs", 0), "successes": (entry.get("stats") or {}).get("successes", 0)})
        if "assignments" in names:
            columns = [row[1] for row in db.execute("PRAGMA table_info(assignments)")]
            wanted = ["assignment_id", "run_id", "agent_ref", "mission_id", "state", "detail"] + (["demo"] if "demo" in columns else [])
            for row in db.execute(f"SELECT {', '.join(wanted)} FROM assignments ORDER BY assignment_id"):
                base["assignments"].append(dict(zip(wanted, row)))
    finally:
        db.close()
    for row in base["assignments"]:
        row["demo"] = bool(row.get("demo", 1))
    base["demo"] = all(row["demo"] for row in base["assignments"])
    return base
