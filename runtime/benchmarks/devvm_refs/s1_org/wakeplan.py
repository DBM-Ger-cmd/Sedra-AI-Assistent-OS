from datetime import datetime, timedelta

FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SOURCES = {"assign": 2, "comment": 1, "captain": 1, "routine": 2, "unblocked": 2, "report": 1, "retry": 2}
DONE = ("erledigt", "abgebrochen")
REASONS = {"ausgecheckt": "laeuft_schon", "nur_blockiert": "blockiert", "keine_aufgabe": "keine_aufgabe"}
BUDGET = {"ok": True, "warnung": True, "gestoppt": False, "zu_wenig": False}


def _time(text):
    return datetime.strptime(text, FORMAT)


def key_for(source, ref):
    if source not in SOURCES:
        raise ValueError("wake_source_unknown")
    parts = list(ref) if isinstance(ref, (list, tuple)) else [ref]
    if len(parts) != SOURCES[source] or any(p is None or str(p) == "" for p in parts):
        raise ValueError("wake_ref_invalid")
    return ":".join([source] + [str(p) for p in parts])


def _order(row):
    return (row["due_at"], row["id"])


def coalesce(open_wakeups, now, coalesce_s):
    limit = _time(now) + timedelta(seconds=coalesce_s)
    by_agent = {}
    for row in sorted(open_wakeups, key=_order):
        if row.get("done_at") is None and row.get("coalesced_into") is None:
            by_agent.setdefault(row["agent_id"], []).append(row)
    groups = []
    for rows in by_agent.values():
        leader = rows[0]
        if leader["due_at"] > now:
            continue
        groups.append({"leader": leader, "members": [r for r in rows[1:] if _time(r["due_at"]) <= limit]})
    return sorted(groups, key=lambda g: _order(g["leader"]))


def pick_task(tasks, blockers, prefer_task_id):
    blocked = {b["task_id"] for b in blockers if b.get("state") not in DONE}
    open_ = [t for t in tasks if t["state"] in ("zugewiesen", "offen")]
    free = [t for t in open_ if not t.get("checkout_by")]
    ready = [t for t in free if t["id"] not in blocked]
    if ready:
        chosen = next((t for t in ready if t["id"] == prefer_task_id), None)
        if chosen is None:
            chosen = sorted(ready, key=lambda t: (-t.get("priority", 0), t["created_at"], t["id"]))[0]
        return chosen, "ok"
    if free:
        return None, "nur_blockiert"
    if any(t.get("checkout_by") for t in tasks):
        return None, "ausgecheckt"
    return None, "keine_aufgabe"


def decide_run(agent, budget_state, standing, task_reason):
    if task_reason != "ok" and task_reason not in REASONS:
        raise ValueError("wake_reason_unknown")
    if budget_state not in BUDGET:
        raise ValueError("budget_state_unknown")
    if agent.get("status") != "aktiv":
        return "pausiert"
    if task_reason != "ok":
        return REASONS[task_reason]
    if not BUDGET[budget_state]:
        return "kein_budget"
    return "lauf_dauerfreigabe" if standing else "antrag"
