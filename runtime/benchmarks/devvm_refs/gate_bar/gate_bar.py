from datetime import datetime, timedelta

TITLES = {"start_build": "Bau starten · GPU", "approve_spec": "Spec freigeben", "adopt_candidate": "Kandidat übernehmen"}
LOOKS = {"open": ("●", "offen"), "approved": ("✓", "freigegeben"), "rejected": ("✕", "abgelehnt")}
ENDPOINTS = {"approve": "/api/mission/approve", "reject": "/api/mission/reject"}
EVENT_TEXT = {"requested": "Freigabe angefragt: {title}, siehe Leiste", "approved": "Freigegeben {time}: {title}", "rejected": "Abgelehnt {time}: {title}"}


def title(gate):
    request = gate.get("request") or {}
    action = str(request.get("exact_action") or "")
    base = TITLES.get(action) or action.replace("_", " ").capitalize() or "Freigabe"
    targets = request.get("targets") or []
    return f"{base} · {targets[0]}" if targets and action not in TITLES else base


def gate_state(gate):
    if gate.get("status") != "resolved":
        return "open"
    decision = (gate.get("resolution") or {}).get("decision")
    return "approved" if isinstance(decision, str) and decision.startswith("APPROVE") else "rejected"


def _moment(gate, tz_minutes=0):
    stamp = (gate.get("resolution") or {}).get("decided_at")
    if not stamp:
        return None
    return datetime.fromisoformat(stamp) + timedelta(minutes=tz_minutes)


def row(gate, tz_minutes=0):
    state = gate_state(gate)
    symbol, label = LOOKS[state]
    moment = _moment(gate, tz_minutes)
    clock = moment.strftime("%H:%M") if state != "open" and moment else ""
    name = title(gate)
    text = f"{symbol} {label}" + (f" {clock}" if clock else "") + f" · {name}"
    return {"gate_id": gate.get("gate_id"), "mission_id": gate.get("mission_id"), "state": state, "symbol": symbol, "label": label, "title": name, "time": clock, "text": text}


def bar(gates, now, keep_s=20, tz_minutes=0):
    current = datetime.fromisoformat(now)
    open_rows = [row(g, tz_minutes) for g in gates if gate_state(g) == "open"]
    decided = []
    for gate in gates:
        moment = _moment(gate)
        if gate_state(gate) != "open" and moment is not None:
            decided.append((moment, gate))
    decided.sort(key=lambda pair: pair[0], reverse=True)
    recent = [row(g, tz_minutes) for moment, g in decided if (current - moment).total_seconds() <= keep_s]
    history = [row(g, tz_minutes)["text"] for moment, g in decided if (current - moment).total_seconds() > keep_s]
    return {"rows": open_rows + recent, "history": history, "open_count": len(open_rows), "badge": badge(gates)}


def badge(gates):
    count = sum(1 for g in gates if gate_state(g) == "open")
    return f" ({count} offen)" if count else ""


def detail(gate):
    request = gate.get("request") or {}
    digest = request.get("request_digest")
    return [("Aktion", str(request.get("exact_action") or "")), ("Ziele", ", ".join(request.get("targets") or []) or "keine"),
            ("Risiken", ", ".join(request.get("risks") or []) or "keine"), ("Rücknahme möglich", "ja" if request.get("rollback_available") else "nein"),
            ("Prüfsumme", str(digest)[:12] if digest else "keine"), ("Gate-ID", str(gate.get("gate_id") or ""))]


def decision_payload(kind, gate):
    if kind not in ENDPOINTS:
        raise ValueError("unknown_decision")
    if gate_state(gate) != "open":
        raise ValueError("gate_not_open")
    if not gate.get("gate_id") or not gate.get("mission_id"):
        raise ValueError("exact_gate_id_required")
    return {"url": ENDPOINTS[kind], "body": {"mission_id": gate["mission_id"], "gate_id": gate["gate_id"]}}


def conversation_line(event, gate, tz_minutes=0):
    if event not in EVENT_TEXT:
        raise ValueError("unknown_event")
    return EVENT_TEXT[event].format(title=title(gate), time=row(gate, tz_minutes)["time"])
