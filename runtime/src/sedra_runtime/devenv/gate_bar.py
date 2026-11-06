from datetime import datetime, timedelta

TITLES = {
    "start_build": "Bau starten · GPU",
    "approve_spec": "Spec freigeben",
    "adopt_candidate": "Kandidat übernehmen",
}


def title(gate):
    request = gate.get("request")
    if not request:
        action = None
    else:
        action = request.get("exact_action")
    if not action:
        return "Freigabe"
    if action in TITLES:
        return TITLES[action]
    targets = request.get("targets", [])
    if targets:
        return action.replace("_", " ").capitalize() + " · " + targets[0]
    return action.replace("_", " ").capitalize()


def gate_state(gate):
    status = gate.get("status")
    if status != "resolved":
        return "open"
    resolution = gate.get("resolution")
    if not resolution:
        return "rejected"
    decision = resolution.get("decision")
    if decision and str(decision).startswith("APPROVE"):
        return "approved"
    return "rejected"


def _time_str(decided_at, tz_minutes=0):
    dt = datetime.fromisoformat(decided_at)
    dt = dt + timedelta(minutes=tz_minutes)
    return dt.strftime("%H:%M")


def row(gate, tz_minutes=0):
    state = gate_state(gate)
    if state == "open":
        symbol = "●"
        label = "offen"
    elif state == "approved":
        symbol = "✓"
        label = "freigegeben"
    else:
        symbol = "✕"
        label = "abgelehnt"
    t = ""
    if state != "open":
        resolution = gate.get("resolution")
        if resolution:
            decided_at = resolution.get("decided_at")
            if decided_at:
                t = _time_str(decided_at, tz_minutes)
    title_text = title(gate)
    text = symbol + " " + label
    if t:
        text += " " + t
    text += " · " + title_text
    return {
        "gate_id": gate.get("gate_id"),
        "mission_id": gate.get("mission_id"),
        "state": state,
        "symbol": symbol,
        "label": label,
        "title": title_text,
        "time": t,
        "text": text,
    }


def badge(gates):
    open_count = sum(1 for g in gates if gate_state(g) == "open")
    if open_count == 0:
        return ""
    return f" ({open_count} offen)"


CONVERSATION_TEXTS = {
    "requested": "Freigabe angefragt: {title}, siehe Leiste",
    "approved": "Freigegeben {time}: {title}",
    "rejected": "Abgelehnt {time}: {title}",
}


def detail(gate):
    request = gate.get("request") or {}
    exact_action = request.get("exact_action") or ""
    targets = request.get("targets", [])
    targets_str = ", ".join(targets) if targets else "keine"
    risks = request.get("risks", [])
    risks_str = ", ".join(risks) if risks else "keine"
    rollback = request.get("rollback_available", False)
    rollback_str = "ja" if rollback else "nein"
    request_digest = request.get("request_digest")
    digest_str = request_digest[:12] if request_digest else "keine"
    gate_id = gate.get("gate_id") or ""
    return [
        ("Aktion", exact_action),
        ("Ziele", targets_str),
        ("Risiken", risks_str),
        ("Rücknahme möglich", rollback_str),
        ("Prüfsumme", digest_str),
        ("Gate-ID", gate_id),
    ]


def decision_payload(kind, gate):
    if kind not in ("approve", "reject"):
        raise ValueError("unknown_decision")
    if gate_state(gate) != "open":
        raise ValueError("gate_not_open")
    if not gate.get("gate_id") or not gate.get("mission_id"):
        raise ValueError("exact_gate_id_required")
    url = f"/api/mission/{kind}"
    return {
        "url": url,
        "body": {
            "mission_id": gate["mission_id"],
            "gate_id": gate["gate_id"],
        },
    }


def conversation_line(event, gate, tz_minutes=0):
    if event not in CONVERSATION_TEXTS:
        raise ValueError("unknown_event")
    title_text = title(gate)
    if event == "requested":
        return CONVERSATION_TEXTS["requested"].format(title=title_text)
    resolution = gate.get("resolution")
    if resolution:
        decided_at = resolution.get("decided_at")
        time_str = _time_str(decided_at, tz_minutes) if decided_at else ""
    else:
        time_str = ""
    return CONVERSATION_TEXTS[event].format(time=time_str, title=title_text)


def _decided_info(gate):
    resolution = gate.get("resolution")
    if resolution:
        decided_at = resolution.get("decided_at")
        if decided_at:
            return datetime.fromisoformat(decided_at)
    return None


def bar(gates, now, keep_s=20, tz_minutes=0):
    now_dt = datetime.fromisoformat(now)
    open_rows = []
    decided_rows = []
    decided_texts = []
    for g in gates:
        st = gate_state(g)
        if st == "open":
            open_rows.append(row(g, tz_minutes))
        elif st in ("approved", "rejected"):
            decided_dt = _decided_info(g)
            if decided_dt:
                diff = (now_dt - decided_dt).total_seconds()
                if diff <= keep_s:
                    decided_rows.append((decided_dt, row(g, tz_minutes)))
                else:
                    decided_texts.append((decided_dt, row(g, tz_minutes)["text"]))
    decided_rows.sort(key=lambda x: x[0], reverse=True)
    decided_texts.sort(key=lambda x: x[0], reverse=True)
    rows = open_rows + [r[1] for r in decided_rows]
    history = [t[1] for t in decided_texts]
    open_count = len(open_rows)
    return {
        "rows": rows,
        "history": history,
        "open_count": open_count,
        "badge": badge(gates),
    }
