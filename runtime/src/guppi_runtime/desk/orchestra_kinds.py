"""Die Typen der Orchestrierung am Desk (Spec 0, D3.2; Spec 1, D1.3, S1.H7).

`agent`, `issue`, `routine`, `budget` ersetzen ihre Platzhalter aus `builtin_kinds`, `gespraech` kommt dazu (nur lesend). Jede Liste
trägt `quelle = {zustand: 'bereit', grund, takt}`. Die Verben heißen so, wie Shell D sie aufruft (Vertrag S1); hier werden ihre
Argumente auf die Module abgebildet. „direkt“ heißt: `guard.evaluate` muss ALLOW sagen, dann läuft es im selben Aufruf. „Antrag“ heißt
`gated.request` mit Art `orchestra`; ausgeführt wird erst nach „Freigeben und anwenden“ über den Applier `apply`, der vorher die
gebundene Revision mit der jetzigen vergleicht (`binding_stale`). Jedes Schreiben nimmt `orch.lock` (Takt und Desk teilen die
Verbindung). Die deutschen Sätze zu den Fehlercodes stehen in `SAETZE`, nicht in `orchestra/`.

Dauerfreigabe (D1.4, G2-S1-13; G4-Entscheidung HALT 1 A mit Auflage, Captain 22.10.2026): das Verb `dauerfreigabe` beantragt
mit Art `standing` und genau der Bindung, die der Guard nachbaut; nach der Freigabe gibt der Applier den unverbrauchten Einmal-Token
an `guard.grant_standing` und gleicht den Spiegel `standing_approvals` ab. `widerrufen` braucht kein Gate.

Einstellen (Entscheidung HALT 3 B, Captain 22.10.2026; OP-S1-01): die AM-Instanz entsteht vorher über den eigenen AM-Ablauf
(`instantiation_gate`/`instantiate`, eigener Token, eigene Bindung). `einstellen` nimmt `instance_id` einer vorhandenen Instanz
(Abweichung vom Shell-D-Vertrag: `vorlage` → `instance_id`) und ist ein Antrag mit Gate `set_org`; der Applier prüft vor
`org.hire`, dass die Instanz noch da, ACTIVE und im gebundenen Stand ist und keinem Agenten gehört. Die Zulassung (promote) vor
dem ersten Lauf (Entscheidung Captain 22.10.2026) prüft der Takt über `instance_admitted`, das hier aus der AM-Registry liest:
VERIFIED, Zulassung gültig, nicht widerrufen."""
import json
import sqlite3
import uuid
from datetime import datetime, timedelta

from . import gated
from .actions import Verb
from ..orchestra import board, budget, cron, graphs, heartbeat, messages, org, routines, wakeplan

TYPES = ("agent", "issue", "routine", "budget", "gespraech")
TITLES = {"agent": "Agent", "issue": "Aufgabe", "routine": "Routine", "budget": "Budget", "gespraech": "Gespräch"}
KIND = "orchestra"                                       # die Art aller Anträge der Orchestrierung (gated, D1.3.2)
STANDING = "standing"                                    # die Art des Antrags Dauerfreigabe (gated.SPENDS_TOKEN)
TIME = "%Y-%m-%dT%H:%M:%SZ"
LIST_COMMENTS = 3                                        # OP-S1-18: in der Liste die letzten drei, vollständig in der Einzelansicht
ANTRAG = "Antrag liegt im Posteingang"

SAETZE = {
    "agent_not_found": "Diesen Agenten gibt es nicht.",
    "agent_terminated": "Der Agent ist beendet.",
    "agent_inactive": "Der Agent ist nicht aktiv.",
    "agent_not_paused": "Der Agent ist nicht pausiert.",
    "agent_required": "Welcher Agent? Das Gespräch braucht einen Agenten.",
    "task_not_found": "Diese Aufgabe gibt es nicht.",
    "task_closed": "Die Aufgabe ist schon erledigt oder abgebrochen.",
    "task_checked_out": "Die Aufgabe ist gerade in Arbeit.",
    "task_title_invalid": "Der Titel fehlt oder ist länger als 200 Zeichen.",
    "routine_not_found": "Diese Routine gibt es nicht.",
    "blocker_cycle": "Das ergäbe einen Kreis von Blockern.",
    "blocker_self": "Eine Aufgabe kann sich nicht selbst blockieren.",
    "text_too_long": "Der Text ist zu lang.",
    "comment_empty": "Der Kommentar ist leer.",
    "message_empty": "Die Anweisung ist leer.",
    "message_too_long": "Die Anweisung ist länger als 8000 Zeichen.",
    "org_cycle": "Das ergäbe einen Kreis in der Berichtslinie.",
    "org_second_root": "Es gibt schon einen Agenten direkt unter dem Captain.",
    "org_too_deep": "Die Berichtslinie würde zu tief.",
    "org_unknown_superior": "Den Vorgesetzten gibt es nicht oder er ist beendet.",
    "org_self": "Ein Agent kann nicht sein eigener Vorgesetzter sein.",
    "org_has_subordinates": "Der Agent hat noch Untergebene.",
    "cron_timezone_unknown": "Diese Zeitzone kennt SEDRA nicht.",
    "binding_stale": "Seit dem Antrag hat sich etwas geändert; die Freigabe galt für den alten Stand, ausgeführt wurde nichts.",
    "runner_off": "Es gibt noch keinen Agentenlauf; die Freigabe kann nicht angewendet werden.",
    "guard_block": "Der Guard lässt das nicht zu.",
    "budget_invalid": "Die Budget-Angabe ist ungültig.",
    "args_invalid": "Die Angaben sind unvollständig oder ungültig.",
    "standing_active": "Der Agent hat schon eine Dauerfreigabe.",
    "instance_not_found": "Diese Agenten-Instanz gibt es nicht.",
    "nicht_zugelassen": "Die Agenten-Instanz ist noch nicht zugelassen (VERIFIED und Zulassung über agent.promote); sie wird nicht geweckt.",
    "instance_not_active": "Die Agenten-Instanz ist nicht aktiv (z. B. in Quarantäne).",
    "instance_taken": "Diese Agenten-Instanz gehört schon einem Agenten.",
    "template_without_effect": "Die Vorlage der Instanz sagt nicht, was sie bewirkt; daraus folgt keine Stufe.",
    "standing_agent_not_active": "Der Agent ist nicht aktiv; eine Dauerfreigabe gibt es nur für aktive Agenten.",
    "standing_level_too_high": "Die Stufe des Agenten ist zu hoch für eine Dauerfreigabe.",
    "standing_uses_out_of_range": "So viele Läufe deckt eine Dauerfreigabe nicht.",
    "standing_expiry_out_of_range": "So lange gilt eine Dauerfreigabe nicht.",
}


def satz(code):
    code = str(code)
    if code.startswith(gated.REFUSED):
        return "Der Guard hat abgelehnt: " + satz(code[len(gated.REFUSED):])
    if code.startswith("cron_invalid:"):
        return "Der Zeitplan ist ungültig (Feld " + code.split(":", 1)[1] + ")."
    return SAETZE.get(code, code)


# ---- Zugang
def _orch(hub):
    return getattr(getattr(hub, "runtime", None), "orchestra", None)


def _need(hub):
    orch = _orch(hub)
    if orch is None:
        raise ValueError("unknown_object_type")
    return orch


def _now(orch):
    return orch.clock()


def _allow(hub, action, target):
    out = hub.runtime.guard.evaluate(action, target=target)
    if out["decision"] != "ALLOW":
        raise ValueError("guard_block")


def _text(args, key, limit=None, required=True):
    value = args.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError("args_invalid")
        return None
    value = str(value).strip()
    if limit and len(value) > limit:
        raise ValueError("text_too_long")
    return value


def _request(hub, action, target, binding, gates=None):
    req = gated.request(hub, KIND, action, target, binding, gates=gates)
    return {"status": "beantragt", "decision_id": "request:" + req["mission_id"], "text": ANTRAG}


def _agent_row(orch, agent_id):
    row = org.get(orch.conn, agent_id)
    if row is None:
        raise ValueError("agent_not_found")
    return row


def _task_row(orch, task_id):
    row = orch.issue(task_id)
    if row is None:
        raise ValueError("task_not_found")
    return row


def _wake(orch, agent_id, reason, key, now, task_id=None):
    return heartbeat.enqueue(orch.conn, agent_id, reason, key, now, orch.config.coalesce_s, task_id=task_id)


# ---- Felder für Shell D (D1.3.4, Vertrag S1)
def _standing_view(orch, agent_id):
    row = orch.conn.execute("SELECT uses, max_uses, expires_at FROM standing_approvals WHERE agent_id = ? AND status = 'aktiv'",
                            (agent_id,)).fetchone()
    return {"aktiv": True, "laeufe": row["uses"], "max_laeufe": row["max_uses"], "bis": row["expires_at"]} if row else None


def _decisions_by_agent(hub):
    counts = {}
    try:
        items = hub.decisions_view()["items"]
    except Exception:
        items = []
    for d in items:
        if d.get("agent_id"):
            counts[d["agent_id"]] = counts.get(d["agent_id"], 0) + 1
    return counts


def _agent_runs(orch, agent_id):
    rows = list(reversed(orch.agent_runs(agent_id)))       # Shell D zeigt die letzten, älteste zuerst
    return [{"termin": r["due_at"], "ts": r["due_at"], "ausgang": r["outcome"], "zustand": r["outcome"], "task_id": r["task_id"],
             "mission_id": r["mission_id"]} for r in rows]


def agent_object(row, extra=None):
    reports_to = row.get("reports_to")
    if reports_to is not None and reports_to != "":
        summary = row.get("role", "") + " · unter " + reports_to
    else:
        summary = row.get("role", "") + " · direkt unter dem Captain"
    links = _build_links(row, [("agent", "reports_to")])
    obj = _build_object("agent", row["id"], row["name"], row["status"], summary, links)
    obj.update({"rolle": row.get("role"), "reports_to": reports_to, "status": row["status"], "stufe": row.get("permission_level"),
                "can_delegate": row.get("can_delegate", 0), "pause_reason": row.get("pause_reason"), "revision": row.get("revision")})
    obj.update(extra or {})
    return obj


def _agent_fields(orch, row, now, decisions):
    return {"arbeitet": bool(orch.conn.execute("SELECT 1 FROM tasks WHERE checkout_by = ?", (row["id"],)).fetchone()),
            "budget": budget.state(orch.conn, row, now, orch.config.warn_percent, orch.config.stop_percent),
            "offene_entscheidungen": decisions.get(row["id"], 0), "dauerfreigabe": _standing_view(orch, row["id"]),
            "letzte_nachricht": messages.last(orch.conn, row["id"]), "laeufe": _agent_runs(orch, row["id"])}


def agent_read(hub, oid):
    orch = _orch(hub)
    if orch is None:
        return None
    row = orch.agent(oid)
    if row is None:
        return None
    return agent_object(row, _agent_fields(orch, row, _now(orch), _decisions_by_agent(hub)))


def agent_listing(hub, payload):
    orch = _orch(hub)
    if orch is None:
        return []
    now, decisions = _now(orch), _decisions_by_agent(hub)
    return [agent_object(row, _agent_fields(orch, row, now, decisions)) for row in orch.agents()]


def _comment(row):
    return {"id": row["id"], "autor": row["author_id"] or {"captain": "Captain", "system": "SEDRA"}.get(row["author_kind"], row["author_kind"]),
            "autor_art": row["author_kind"], "author_kind": row["author_kind"], "author_id": row["author_id"], "text": row["text"], "ts": row["ts"]}


def _chain(orch, task_id):
    built = orch.chain(task_id)
    if built is None:
        return None
    types = {"vorhaben": "intent", "projekt": "project", "eltern": "issue", "aufgabe": "issue"}
    return [{"type": types[g["art"]], "id": g["id"], "title": g["titel"] or g["id"], "fehlt": g["titel"] is None} for g in built["glieder"]]


def issue_object(row, extra=None):
    assignee = row.get("assignee")
    checkout_by = row.get("checkout_by")
    if assignee is not None and assignee != "":
        summary = "zugewiesen an " + assignee
    else:
        summary = "nicht zugewiesen"
    if checkout_by is not None and checkout_by != "":
        summary += " · ausgecheckt von " + checkout_by
    links = _build_links(row, [("agent", "assignee"), ("issue", "parent_id"), ("task", "mission_id"), ("intent", "goal_ref"), ("project", "project_id")])
    obj = _build_object("issue", row["id"], row["title"], row["state"], summary, links)
    obj.update({"zustand": row["state"], "bearbeiter": assignee, "prioritaet": row.get("priority", 0), "eltern_id": row.get("parent_id"),
                "mission_id": row.get("mission_id"), "vorhaben_id": row.get("goal_ref"), "projekt_id": row.get("project_id"),
                "geaendert": row.get("updated_at"), "max_level": row.get("max_level"), "origin": row.get("origin"),
                "pruefung": row.get("check_result"), "ausgecheckt": bool(checkout_by), "revision": row.get("revision")})
    obj.update(extra or {})
    return obj


def _issue_fields(orch, row, single=False):
    blockers = [r[0] for r in orch.conn.execute("SELECT b.blocked_by_task_id FROM blockers b JOIN tasks t ON t.id = b.blocked_by_task_id "
                                                "WHERE b.task_id = ? AND t.state NOT IN ('erledigt', 'abgebrochen') ORDER BY 1", (row["id"],))]
    fields = {"blocker": blockers,
              "kommentare": [_comment(c) for c in orch.comments(row["id"], None if single else LIST_COMMENTS)]}
    if single:
        fields["kette"] = _chain(orch, row["id"])
    return fields


def issue_read(hub, oid):
    orch = _orch(hub)
    if orch is None:
        return None
    row = orch.issue(oid)
    return issue_object(row, _issue_fields(orch, row, single=True)) if row is not None else None


def issue_listing(hub, payload):
    orch = _orch(hub)
    if orch is None:
        return []
    rows = orch.issues(state=(payload or {}).get("state"), assignee=(payload or {}).get("assignee"))
    return [issue_object(row, _issue_fields(orch, row)) for row in rows]


def _template(row):
    try:
        data = json.loads(row.get("task_template") or "{}") or {}
    except ValueError:
        data = {}
    return {"titel": data.get("titel") or data.get("title"), "beschreibung": data.get("beschreibung") or data.get("description")}


def routine_object(row, extra=None):
    cron_text = row.get("cron", "")
    timezone = row.get("timezone", "Europe/Berlin")
    summary = cron_text + " (" + timezone + ")"
    enabled = row.get("enabled")
    state = "an" if enabled else "aus"
    links = _build_links(row, [("agent", "agent_id")])
    obj = _build_object("routine", row["id"], row["title"], state, summary, links)
    try:
        beschreibung = cron.describe(cron.parse(cron_text))
    except ValueError:
        beschreibung = None
    obj.update({"agent_id": row.get("agent_id"), "cron": cron_text, "zeitzone": timezone, "nachholen": row.get("catch_up"),
                "catch_up": row.get("catch_up"), "enabled": bool(enabled), "next_run": row.get("next_run"), "last_run": row.get("last_run"),
                "beschreibung": beschreibung, "vorlage": _template(row)})
    obj.update(extra or {})
    return obj


def _routine_fields(orch, row):
    runs = [{"termin": r["due_at"], "ausgang": r["outcome"], "issue_id": r["task_id"]} for r in reversed(orch.routine_runs(row["id"]))]
    return {"laeufe": runs, "letzter_lauf": runs[-1] if runs else None}


def routine_read(hub, oid):
    orch = _orch(hub)
    if orch is None:
        return None
    row = orch.routine(oid)
    return routine_object(row, _routine_fields(orch, row)) if row is not None else None


def routine_listing(hub, payload):
    orch = _orch(hub)
    if orch is None:
        return []
    return [routine_object(row, _routine_fields(orch, row)) for row in orch.routines()]


# ---- gespraech (D1.3.6, G2-S4-12): nur lesend
def message_object(row):
    text = row["text"]
    obj = _build_object("gespraech", row["id"], text.split("\n")[0][:60], row["status"], text, [])
    obj["links"] = _build_links(row, [("agent", "agent_id"), ("issue", "issue_id"), ("task", "mission_id")])
    obj.update({k: row.get(k) for k in ("agent_id", "rolle", "text", "ts", "status", "issue_id", "mission_id", "route", "provider_id", "model")})
    return obj


def _page(orch, payload):
    agent = str((payload or {}).get("agent") or "").strip()
    if not agent:
        raise ValueError("agent_required")
    before = (payload or {}).get("vor")
    limit = (payload or {}).get("limit") or 50
    return messages.page(orch.conn, agent, before_id=int(before) if before not in (None, "") else None, limit=int(limit))


def gespraech_read(hub, oid):
    orch = _orch(hub)
    if orch is None:
        return None
    try:
        mid = int(oid)
    except (TypeError, ValueError):
        return None
    row = orch.conn.execute("SELECT * FROM agent_messages WHERE id = ?", (mid,)).fetchone()
    return message_object(dict(row)) if row is not None else None


def gespraech_listing(hub, payload):
    orch = _orch(hub)
    if orch is None:
        return []
    return [message_object(dict(r)) for r in _page(orch, payload)["items"]]


def quelle(hub):
    """D1.3.4: die Orchestrierung ist da; der Takt läuft oder nicht; ohne Supervisor gibt es keine Läufe (D1.7)."""
    orch = _orch(hub)
    takt = orch.takt()
    grund = "supervisor_off" if orch.run_blocked() == "supervisor_off" else None
    return {"zustand": "bereit", "grund": grund, "takt": {"laeuft": takt["laeuft"], "letzter": takt["letzter"]}}


def _extra(hub, payload):
    return {"quelle": quelle(hub)}


def _extra_gespraech(hub, payload):
    return {"quelle": quelle(hub), "mehr": bool(_page(_orch(hub), payload)["mehr"])}


# ---- Verben am Agenten (D1.3.1)
def _halt_agent(hub, orch, agent_id, now, comment):
    """Was pausieren und beenden gemeinsam haben: laufender Lauf abgebrochen, Mission angehalten, Aufgabe frei, Weckrufe zu."""
    for task in [dict(r) for r in orch.conn.execute("SELECT * FROM tasks WHERE checkout_by = ?", (agent_id,))]:
        run_id = task["checkout_run"]
        if orch.supervisor is not None and run_id:
            try:
                orch.supervisor.cancel(run_id, requested_by="captain", reason=comment)
            except Exception:
                pass
        if task.get("mission_id"):
            try:
                m = hub.runtime.missions.load(task["mission_id"])
                hub.runtime.missions.transition(m, "PAUSED")
            except Exception:
                pass
        board.release(orch.conn, task["id"], run_id, "offen", now, comment)
    for (wid,) in orch.conn.execute("SELECT id FROM wakeups WHERE agent_id = ? AND done_at IS NULL AND coalesced_into IS NULL",
                                    (agent_id,)).fetchall():
        heartbeat.finish(orch.conn, wid, "pausiert", now)
    orch.revoke_standing(agent_id, "captain")


def _pausieren(hub, oid, args):
    orch = _need(hub)
    _allow(hub, "pause_agent", "agent:" + oid)
    with orch.lock:
        now = _now(orch)
        _agent_row(orch, oid)
        _halt_agent(hub, orch, oid, now, "pausiert_vom_captain")
        row = org.pause(orch.conn, oid, "captain", now)
    orch.audit_event("ORC_AGENT_PAUSED", {"agent_id": oid, "reason": "captain"})
    return {"status": "erledigt", "agent": row["id"], "zustand": row["status"]}


def _agent_binding(orch, oid, op, describe, **more):
    row = _agent_row(orch, oid)
    return dict({"op": op, "agent_id": oid, "agent_revision": row["revision"], "describe": describe}, **more)


def _einordnen(hub, oid, args):
    orch = _need(hub)
    reports_to = _text(args, "reports_to")
    binding = _agent_binding(orch, oid, "einordnen", f"Agent {oid} unter {reports_to} stellen", reports_to=reports_to)
    return _request(hub, "set_org", "agent:" + oid, binding)


def _fortsetzen(hub, oid, args):
    orch = _need(hub)
    return _request(hub, "resume_agent", "agent:" + oid, _agent_binding(orch, oid, "fortsetzen", f"Agent {oid} fortsetzen"))


def _beenden(hub, oid, args):
    orch = _need(hub)
    return _request(hub, "terminate_agent", "agent:" + oid, _agent_binding(orch, oid, "beenden", f"Agent {oid} beenden"))


def _wecken(hub, oid, args):
    """Ein Weckruf des Captains. Der Takt entscheidet dann wie bei jedem Weckruf (D1.5): mit Dauerfreigabe ein Lauf, sonst ein
    Antrag `wecken` mit Aufgabe und Revisionen – so braucht jeder Lauf genau eine Freigabe."""
    orch = _need(hub)
    with orch.lock:
        _agent_row(orch, oid)
        wid = _wake(orch, oid, "captain", None, _now(orch))
    orch.audit_event("ORC_WAKE_REQUESTED", {"agent_id": oid, "wakeup_id": wid})
    return {"status": "erledigt", "weckruf": wid}


def _anweisen(hub, oid, args):
    orch = _need(hub)
    text = _text(args, "text", 8000)
    key = _text(args, "key", 200, required=False)
    _allow(hub, "create_new_artifact", "agent:" + oid)
    with orch.lock:
        now = _now(orch)
        agent = _agent_row(orch, oid)
        if agent["status"] != "aktiv" or not agent.get("can_delegate"):
            raise ValueError("agent_inactive")
        msg = messages.add(orch.conn, oid, "captain", text, now, key=("captain:" + key) if key else None)
        if not msg["neu"]:
            return {"status": "erledigt", "nachricht": msg["id"], "neu": False}
        task = board.create(orch.conn, {"title": text.split("\n")[0].strip()[:200] or "Anweisung", "description": text, "assignee": oid,
                                        "origin": "captain"}, now, "captain")
        orch.conn.execute("UPDATE agent_messages SET issue_id = ? WHERE id = ?", (task["id"], msg["id"]))
        _wake(orch, oid, "captain", wakeplan.key_for("captain", msg["id"]), now, task_id=task["id"])
    orch.audit_event("ORC_MESSAGE", {"agent_id": oid, "message_id": msg["id"], "laenge": len(text), "issue_id": task["id"]})
    return {"status": "erledigt", "nachricht": msg["id"], "issue": task["id"], "neu": True}


def _int_arg(args, key, default, low, high):
    value = args.get(key)
    if value in (None, ""):
        return default
    if type(value) is not int or not low <= value <= high:
        raise ValueError("args_invalid")
    return value


def _dauerfreigabe(hub, oid, args):
    """Antrag auf Dauerfreigabe (D1.4): Aktion `wake_agent`, Ziel `agent:<id>`, Bindung genau wie `guard.grant_standing` sie prüft."""
    orch = _need(hub)
    st = orch.config.standing
    tage = _int_arg(args, "tage", st["days"], 1, st["max_days"])
    laeufe = _int_arg(args, "laeufe", st["uses"], 1, st["max_uses"])
    agent = _agent_row(orch, oid)
    if agent["permission_level"] > st["max_level"]:
        raise ValueError("standing_level_too_high")
    if _standing_view(orch, oid) is not None:
        raise ValueError("standing_active")
    expires = (datetime.strptime(_now(orch), TIME) + timedelta(days=tage)).strftime(TIME)
    binding = {"art": "standing", "agent_id": oid, "fingerprint": org.fingerprint(agent), "max_uses": laeufe, "expires_at": expires}
    req = gated.request(hub, STANDING, "wake_agent", "agent:" + oid, binding, exact=True,
                        describe=f"Dauerfreigabe für {agent['name']}: {laeufe} Läufe, {tage} Tage")
    return {"status": "beantragt", "decision_id": "request:" + req["mission_id"], "text": ANTRAG}


def _widerrufen(hub, oid, args):
    """Widerruf ohne Gate (D1.4): macht das System nur strenger."""
    orch = _need(hub)
    with orch.lock:
        _agent_row(orch, oid)
        count = orch.revoke_standing(oid, "captain")
    return {"status": "erledigt", "widerrufen": count}


def apply_standing(hub, binding, tokens):
    """Nach der Freigabe (G4-Entscheidung HALT 1 A mit Auflage): erst der Fingerabdruck – ist er anders, endet der Antrag mit
    `binding_stale` und der Token bleibt unverbraucht; sonst bekommt der Guard den Token genau einmal (`grant_standing`)."""
    orch = _need(hub)
    with orch.lock:
        agent = _agent_row(orch, binding["agent_id"])
        if org.fingerprint(agent) != binding["fingerprint"]:
            raise ValueError("binding_stale")
        [token] = list(tokens.values())
        out = hub.runtime.guard.grant_standing(token, mission_id=token["mission_id"], agent_id=binding["agent_id"],
                                               fingerprint=binding["fingerprint"], max_uses=binding["max_uses"],
                                               expires_at=binding["expires_at"])
        if not out.get("authorized"):
            raise ValueError(gated.REFUSED + str(out.get("reason")))
        orch.sync_standing(binding["agent_id"])
    orch.audit_event("ORC_STANDING_GRANTED", {"agent_id": binding["agent_id"], "token_id": out["token"]["token_id"]})
    return {"op": "dauerfreigabe", "id": out["token"]["token_id"]}


AM_DB = ("runtime_data", "agent_manager", "registry.sqlite")
FOREMAN = "guppi.orchestra.foreman"


def _am_entry(hub, kind, key):
    """Ein Eintrag der AM-Registry, nur lesend (wie `agent_manager.view`); None, wenn es ihn oder die Datei nicht gibt."""
    path = hub.project_root.joinpath(*AM_DB)
    if not path.is_file():
        return None
    uri = "file:" + str(path).replace("\\", "/").replace("?", "%3f").replace("#", "%23") + "?mode=ro"
    db = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        row = db.execute("SELECT data FROM entries WHERE kind = ? AND key = ?", (kind, key)).fetchone()
    finally:
        db.close()
    return json.loads(row[0]) if row else None


def _instance(hub, instance_id):
    data = _am_entry(hub, "agent", instance_id)
    if data is None:
        raise ValueError("instance_not_found")
    if data.get("lifecycle", "ACTIVE") != "ACTIVE":
        raise ValueError("instance_not_active")
    return data


def _admitted(hub):
    def admitted(instance_id):
        data = _am_entry(hub, "agent", instance_id) or {}
        admission = data.get("admission") or {}
        return (data.get("lifecycle", "ACTIVE") == "ACTIVE" and data.get("qualification") == "VERIFIED" and admission.get("valid") is True
                and not admission.get("revoked"))
    return admitted


def _hire_row(hub, orch, args):
    """Die Zeile für `org.hire` aus Shell-D-Argumenten und Vorlage (Vertrag S1, OP-S1-17): Rolle, Rezept, Stufe aus der Vorlage;
    Delegationsrecht nur für die Vorlage des Unterarbeiters."""
    instance_id = _text(args, "instance_id", 120)
    data = _instance(hub, instance_id)
    if orch.conn.execute("SELECT 1 FROM agents WHERE instance_id = ?", (instance_id,)).fetchone():
        raise ValueError("instance_taken")
    ref = data.get("template_ref") or ""
    template = (_am_entry(hub, "template", ref) or {}).get("template") or {}
    effects = [c.get("side_effect") for c in template.get("capabilities") or [] if isinstance(c, dict)]
    if not effects:
        raise ValueError("template_without_effect")
    level = max(graphs.level_for(e, None) for e in effects)
    budget_tokens = args.get("budget_tokens")
    if budget_tokens not in (None, "") and (type(budget_tokens) is not int or budget_tokens < 0):
        raise ValueError("budget_invalid")
    row = {"id": "A-" + uuid.uuid4().hex[:8].upper(), "instance_id": instance_id, "template_id": ref, "name": _text(args, "name", 80),
           "role": str(template.get("role") or "agent"), "recipe_id": template.get("recipe") or template.get("recipe_id"),
           "reports_to": _text(args, "reports_to", required=False), "permission_level": level,
           "budget_tokens": budget_tokens if budget_tokens not in (None, "") else None,
           "can_delegate": 1 if ref.split("@")[0] == FOREMAN else 0}
    return row, data.get("template_digest")


def _einstellen(hub, oid, args):
    orch = _need(hub)
    row, digest = _hire_row(hub, orch, args)
    binding = {"op": "einstellen", "row": row, "instance_id": row["instance_id"], "template_digest": digest,
               "describe": f"Agent {row['name']} ({row['role']}, Stufe {row['permission_level']}) einstellen"}
    return _request(hub, "set_org", "agent:" + row["id"], binding)


def _apply_hire(hub, orch, binding, now):
    try:
        data = _instance(hub, binding["instance_id"])
    except ValueError:
        raise ValueError("binding_stale") from None
    if data.get("template_digest") != binding["template_digest"]:
        raise ValueError("binding_stale")
    if orch.conn.execute("SELECT 1 FROM agents WHERE instance_id = ?", (binding["instance_id"],)).fetchone():
        raise ValueError("binding_stale")         # Punkt d aus S1.H7: inzwischen vergeben – der Antrag endet, die Mission ist zu
    row = org.hire(orch.conn, binding["row"], now, orch.config.max_depth)
    orch.audit_event("ORC_AGENT_HIRED", {"agent_id": row["id"], "instance_id": row["instance_id"], "template": row["template_id"],
                                         "stufe": row["permission_level"], "reports_to": row["reports_to"]})
    return row


def _agent_verbs():
    active = lambda o: o.get("status") == "aktiv"                                          # noqa: E731
    return [
        Verb("einordnen", "Einordnen", _einordnen, needs_gate=True, when=lambda o: o.get("status") != "beendet"),
        Verb("pausieren", "Pausieren", _pausieren, when=active),
        Verb("fortsetzen", "Fortsetzen", _fortsetzen, needs_gate=True,
             when=lambda o: o.get("status") == "pausiert" and o.get("pause_reason") != "budget"),
        Verb("beenden", "Beenden", _beenden, needs_gate=True, confirm="Den Agenten endgültig beenden?",
             when=lambda o: o.get("status") != "beendet"),
        Verb("wecken", "Wecken", _wecken, needs_gate=True, when=active),
        Verb("anweisen", "Senden", _anweisen, when=lambda o: active(o) and bool(o.get("can_delegate"))),
        Verb("dauerfreigabe", "Dauerfreigabe", _dauerfreigabe, needs_gate=True,
             when=lambda o: active(o) and (o.get("stufe") or 0) <= 3 and o.get("dauerfreigabe") is None),
        Verb("widerrufen", "Dauerfreigabe widerrufen", _widerrufen, when=lambda o: bool(o.get("dauerfreigabe"))),
    ]


# ---- Verben an der Aufgabe
def _assigned(orch, task, by, now, old=None):
    orch.audit_event("ORC_TASK_ASSIGNED", {"task_id": task["id"], "alt": old, "neu": task["assignee"], "by": by})
    _wake(orch, task["assignee"], "zugewiesen", wakeplan.key_for("assign", (task["id"], task["revision"])), now, task_id=task["id"])


def _anlegen_issue(hub, oid, args):
    orch = _need(hub)
    fields = {"title": _text(args, "titel", 200), "origin": "captain"}
    for arg, col in (("beschreibung", "description"), ("vorhaben_id", "goal_ref"), ("bearbeiter", "assignee")):
        value = _text(args, arg, required=False)
        if value is not None:
            fields[col] = value
    _allow(hub, "create_new_artifact", "issue:neu")
    with orch.lock:
        now = _now(orch)
        task = board.create(orch.conn, fields, now, "captain")
        if task["assignee"]:
            _assigned(orch, task, "captain", now)
    return {"status": "erledigt", "issue": task["id"]}


def _zuweisen(hub, oid, args):
    orch = _need(hub)
    agent = _text(args, "bearbeiter")
    _allow(hub, "assign_task", "issue:" + oid)
    with orch.lock:
        now = _now(orch)
        out = board.assign(orch.conn, oid, agent, now, "captain")
        _assigned(orch, out["task"], "captain", now, out["old"])
    return {"status": "erledigt", "issue": oid, "bearbeiter": agent}


def _blocker_setzen(hub, oid, args):
    orch = _need(hub)
    blocker = _text(args, "blocker")
    _allow(hub, "assign_task", "issue:" + oid)
    with orch.lock:
        board.set_blocker(orch.conn, oid, blocker, _now(orch))
    return {"status": "erledigt", "issue": oid, "blocker": blocker}


def _blocker_loesen(hub, oid, args):
    orch = _need(hub)
    blocker = _text(args, "blocker")
    _allow(hub, "assign_task", "issue:" + oid)
    with orch.lock:
        now = _now(orch)
        left = board.clear_blocker(orch.conn, oid, blocker, now)
        task = _task_row(orch, oid)
        if left == 0 and task.get("assignee"):
            _wake(orch, task["assignee"], "antwort", wakeplan.key_for("unblocked", (oid, blocker)), now, task_id=oid)
    return {"status": "erledigt", "issue": oid, "offen": left}


def _kommentieren(hub, oid, args):
    orch = _need(hub)
    text = _text(args, "text", 8000)
    _allow(hub, "create_new_artifact", "issue:" + oid)
    with orch.lock:
        now = _now(orch)
        cid = board.comment(orch.conn, oid, "captain", None, text, now)
        task = _task_row(orch, oid)
        if task.get("assignee"):
            _wake(orch, task["assignee"], "antwort", wakeplan.key_for("comment", cid), now, task_id=oid)
    return {"status": "erledigt", "issue": oid, "kommentar": cid}


def _abbrechen(hub, oid, args):
    orch = _need(hub)
    _allow(hub, "pause_agent", "issue:" + oid)
    with orch.lock:
        out = board.cancel(orch.conn, oid, _now(orch), "captain")
    if out["run_id"] and orch.supervisor is not None:
        try:
            orch.supervisor.cancel(out["run_id"], requested_by="captain", reason="aufgabe_abgebrochen")
        except Exception:
            pass
    return {"status": "erledigt", "issue": oid, "lauf": out["run_id"]}


def _issue_verbs():
    open_ = lambda o: o.get("zustand", o.get("state")) not in ("erledigt", "abgebrochen")   # noqa: E731
    return [
        Verb("zuweisen", "Zuweisen", _zuweisen, when=lambda o: open_(o) and not o.get("ausgecheckt")),
        Verb("blocker_setzen", "Blocker setzen", _blocker_setzen, when=open_),
        Verb("blocker_loesen", "Blocker lösen", _blocker_loesen, when=lambda o: bool(o.get("blocker"))),
        Verb("kommentieren", "Kommentieren", _kommentieren),
        Verb("abbrechen", "Abbrechen", _abbrechen, confirm="Die Aufgabe abbrechen?", when=open_),
    ]


# ---- Routinen (alle als Antrag, set_routine)
def _routine_fields_from(args, partial=False):
    fields = {}
    for arg, col in (("titel", "title"), ("agent_id", "agent_id"), ("cron", "cron"), ("zeitzone", "timezone")):
        value = _text(args, arg, 200, required=not partial and col != "timezone")
        if value is not None:
            fields[col] = value
    nachholen = args.get("nachholen")
    if nachholen is not None and nachholen != "":
        fields["catch_up"] = "nachholen" if nachholen in (True, "nachholen", "true", "ja") else "auslassen"
    elif not partial:
        fields["catch_up"] = "auslassen"
    titel, beschreibung = _text(args, "vorlage_titel", 200, required=False), _text(args, "vorlage_beschreibung", 4000, required=False)
    if titel or beschreibung:
        fields["task_template"] = json.dumps({"titel": titel, "beschreibung": beschreibung}, ensure_ascii=False)
    if "cron" in fields:                                          # ein ungültiger Ausdruck wird schon beim Antrag abgewiesen
        cron.next_after(cron.parse(fields["cron"]), "2026-01-01T00:00:00Z", fields.get("timezone", "Europe/Berlin"))
    return fields


def _routine_snapshot(row):
    return {k: row.get(k) for k in ("agent_id", "title", "cron", "timezone", "catch_up", "enabled", "task_template")}


def _routine_anlegen(hub, oid, args):
    _need(hub)
    fields = _routine_fields_from(args)
    return _request(hub, "set_routine", "routine:neu", {"op": "routine_anlegen", "fields": fields,
                                                         "describe": f"Routine „{fields['title']}“ anlegen ({fields['cron']})"})


def _routine_change(op, describe):
    def run(hub, oid, args):
        orch = _need(hub)
        row = orch.routine(oid)
        if row is None:
            raise ValueError("routine_not_found")
        binding = {"op": op, "routine_id": oid, "stand": _routine_snapshot(row), "describe": describe.format(title=row["title"])}
        if op == "routine_aendern":
            binding["fields"] = _routine_fields_from(args, partial=True)
        return _request(hub, "set_routine", "routine:" + oid, binding)
    return run


def _routine_verbs():
    return [
        Verb("aendern", "Ändern", _routine_change("routine_aendern", "Routine „{title}“ ändern"), needs_gate=True),
        Verb("ausschalten", "Ausschalten", _routine_change("routine_ausschalten", "Routine „{title}“ ausschalten"), needs_gate=True,
             when=lambda o: o.get("state") == "an"),
        Verb("einschalten", "Einschalten", _routine_change("routine_einschalten", "Routine „{title}“ einschalten"), needs_gate=True,
             when=lambda o: o.get("state") == "aus"),
    ]


# ---- Budget
def _festlegen(hub, oid, args):
    orch = _need(hub)
    agent = _agent_row(orch, oid)
    change = {}
    for key in ("budget_tokens", "budget_eur_cent"):
        if key in args:
            value = args[key]
            if value in (None, ""):
                change[key] = None
            elif type(value) is int and value >= 0:
                change[key] = value
            else:
                raise ValueError("budget_invalid")
    if args.get("budget_period") not in (None, ""):
        if args["budget_period"] not in ("gesamt", "monat"):
            raise ValueError("budget_invalid")
        change["budget_period"] = args["budget_period"]
    if not change:
        raise ValueError("args_invalid")
    resume = agent["status"] == "pausiert" and agent.get("pause_reason") == "budget"
    binding = _agent_binding(orch, oid, "budget", f"Budget von {oid} festlegen" + (" und fortsetzen" if resume else ""),
                             change=change, fortsetzen=resume)
    gates = [("set_budget", "agent:" + oid)] + ([("resume_agent", "agent:" + oid)] if resume else [])
    return _request(hub, "set_budget", "agent:" + oid, binding, gates=gates)


def _budget_verbs():
    return [Verb("festlegen", "Festlegen", _festlegen, needs_gate=True)]


# ---- Applier (D1.3.2): nach „Freigeben und anwenden“, je `binding.op`
def _fresh_agent(orch, binding):
    row = _agent_row(orch, binding["agent_id"])
    if row["revision"] != binding["agent_revision"]:
        raise ValueError("binding_stale")
    return row


def apply(hub, binding):
    orch = _need(hub)
    op = binding.get("op")
    with orch.lock:
        now = _now(orch)
        if op == "einstellen":
            row = _apply_hire(hub, orch, binding, now)
        elif op == "einordnen":
            _fresh_agent(orch, binding)
            row = org.set_org(orch.conn, binding["agent_id"], {"reports_to": binding["reports_to"]}, now, orch.config.max_depth)
        elif op == "fortsetzen":
            _fresh_agent(orch, binding)
            row = org.resume(orch.conn, binding["agent_id"], now)
        elif op == "beenden":
            _fresh_agent(orch, binding)
            _halt_agent(hub, orch, binding["agent_id"], now, "agent_beendet")
            row = org.terminate(orch.conn, binding["agent_id"], now)
            orch.conn.execute("UPDATE tasks SET assignee = NULL, state = 'offen', updated_at = ?, revision = revision + 1 "
                              "WHERE assignee = ? AND state IN ('zugewiesen', 'wartet')", (now, binding["agent_id"]))
        elif op == "budget":
            _fresh_agent(orch, binding)
            row = org.set_org(orch.conn, binding["agent_id"], binding["change"], now, orch.config.max_depth)
            for (iid,) in orch.conn.execute("SELECT id FROM budget_incidents WHERE agent_id = ? AND resolved_at IS NULL",
                                            (binding["agent_id"],)).fetchall():
                budget.resolve_incident(orch.conn, iid, "erhoeht", now)
            if binding.get("fortsetzen"):
                row = org.resume(orch.conn, binding["agent_id"], now)
        elif op == "routine_anlegen":
            row = routines.create(orch.conn, binding["fields"], now)
        elif op in ("routine_aendern", "routine_ausschalten", "routine_einschalten"):
            current = orch.routine(binding["routine_id"])
            if current is None or _routine_snapshot(current) != binding["stand"]:
                raise ValueError("binding_stale")
            if op == "routine_aendern":
                row = routines.update(orch.conn, binding["routine_id"], binding["fields"], now)
            else:
                row = routines.set_enabled(orch.conn, binding["routine_id"], op == "routine_einschalten", now)
        elif op == "wecken":
            try:
                return _apply_wake(orch, binding, now)
            except ValueError as exc:
                if str(exc) == "binding_stale":      # der Antrag endet ohne Wirkung; sein Weckruf soll nicht für immer auf `antrag` stehen
                    try:
                        heartbeat.finish(orch.conn, binding["wakeup_id"], "abgelehnt", now)
                    except ValueError:
                        pass                        # der Weckruf ist schon anders beendet: der Grund `binding_stale` bleibt
                raise
        else:
            raise ValueError("decision_cannot_be_applied")
    orch.audit_event("ORC_APPLIED", {"op": op, "agent_id": binding.get("agent_id"), "routine_id": binding.get("routine_id")})
    return {"op": op, "id": row.get("id") if isinstance(row, dict) else None}


def _apply_wake(orch, binding, now):
    """Ein Lauf nach Einzelfreigabe (D1.5): nur wenn Agent und Aufgabe noch im gebundenen Stand sind."""
    agent = _fresh_agent(orch, binding)
    task = _task_row(orch, binding["task_id"])
    if task["revision"] != binding["task_revision"] or agent["status"] != "aktiv":
        raise ValueError("binding_stale")
    wakeup = dict(orch.conn.execute("SELECT * FROM wakeups WHERE id = ?", (binding["wakeup_id"],)).fetchone())
    if not orch.admitted(agent):
        from ..orchestra import tick
        tick.not_admitted(orch, agent, wakeup, now)
        return {"op": "wecken", "id": None, "grund": "nicht_zugelassen"}
    if orch.start_run is None:
        raise ValueError("runner_off")
    if orch.run_blocked() == "supervisor_off":
        raise ValueError("supervisor_off")
    run = orch.start_run(orch, agent, task, wakeup, "einmal") or {}
    heartbeat.finish(orch.conn, wakeup["id"], "lauf", now, job_id=run.get("job_id"), mission_id=run.get("mission_id"))
    return {"op": "wecken", "id": run.get("job_id")}


def reject(hub, binding):
    """„Ablehnen“: ein abgelehnter Lauf beendet seinen Weckruf (`abgelehnt`); die Aufgabe bleibt zugewiesen (D1.5)."""
    orch = _orch(hub)
    if orch is None or binding.get("op") != "wecken":
        return None
    with orch.lock:
        heartbeat.finish(orch.conn, binding["wakeup_id"], "abgelehnt", _now(orch))
    return {"op": "wecken", "weckruf": binding["wakeup_id"]}


def request_run(orch, agent, task, wakeup, hub=None):
    """Der Antrag des Takts für einen Lauf ohne Dauerfreigabe (D1.5); gibt die Missions-ID des Antrags zurück."""
    binding = {"op": "wecken", "agent_id": agent["id"], "agent_revision": agent["revision"], "task_id": task["id"],
               "task_revision": task["revision"], "wakeup_id": wakeup["id"],
               "describe": f"Agent {agent['name']} ({agent['role']}) an Aufgabe {task['id']} arbeiten lassen"}
    return gated.request(hub, KIND, "wake_agent", "agent:" + agent["id"], binding)["mission_id"]


# ---- Register und Start
def register(registry, hub):
    orchestra = _orch(hub)
    if orchestra is None:
        return []
    kinds = [
        registry.Kind("agent", TITLES["agent"], agent_read, agent_listing, verbs=_agent_verbs(),
                      type_verbs=[Verb("einstellen", "Einstellen", _einstellen, needs_gate=True)], source="orchestra", extra=_extra),
        registry.Kind("issue", TITLES["issue"], issue_read, issue_listing, verbs=_issue_verbs(),
                      type_verbs=[Verb("anlegen", "Anlegen", _anlegen_issue)], source="orchestra", extra=_extra),
        registry.Kind("routine", TITLES["routine"], routine_read, routine_listing, verbs=_routine_verbs(),
                      type_verbs=[Verb("anlegen", "Anlegen", _routine_anlegen, needs_gate=True)], source="orchestra", extra=_extra),
        registry.Kind("budget", TITLES["budget"], budget_read, budget_listing, verbs=_budget_verbs(), source="orchestra", extra=_extra),
        registry.Kind("gespraech", TITLES["gespraech"], gespraech_read, gespraech_listing, source="orchestra", extra=_extra_gespraech),
    ]
    for kind in kinds:                                      # alle fünf ersetzen ihren Platzhalter aus builtin_kinds (Spec 4)
        registry.register(kind, replace_placeholder=True)
    gated.register_applier(KIND, apply, on_reject=reject, registry=registry)
    gated.register_applier(STANDING, apply_standing, registry=registry)
    if orchestra.resolve is None:
        orchestra.resolve = _resolver(hub)
    if orchestra.instance_admitted is None:
        orchestra.instance_admitted = _admitted(hub)
    from . import orchestra_runner
    orchestra_runner.wire(hub, orchestra)
    return list(TYPES)


def _resolver(hub):
    """Vorhaben und Projekt für die Zielkette (ORC-13): aus den Vorhaben und Projekten des Hubs; was fehlt, ist None."""
    def look(kind, ref):
        try:
            if kind == "vorhaben":
                entry = hub.intents.get(ref)
                return {"id": ref, "titel": entry.get("title")} if entry else None
            if kind == "projekt":
                p = next((x for x in hub.projects.list() if ref in (x.get("project_id"), x.get("name"))), None)
                return {"id": ref, "titel": p.get("name")} if p else None
        except Exception:
            return None
        return None
    return look


def start(hub):
    """Der Takt der Orchestrierung (Spec 1, ORC-16, G2-S1-15): ein Thread je Prozess unter `tick.lock`, nur bei eingeschaltetem
    Schalter `orchestra` (sonst gibt es keine Fassade). Ein zweiter Takter bekommt `tick_busy` und taktet nicht. Der Antrag für
    einen Lauf wird nur verdrahtet, wenn es einen Lauf gibt (S1.H8)."""
    orch = _orch(hub)
    if orch is None:
        return None
    if orch.start_run is not None and orch.request_run is None:
        orch.request_run = lambda o, agent, task, wakeup: request_run(o, agent, task, wakeup, hub=hub)
    tick = orch.start_tick()                                # wer den Takt hält, arbeitet auch die Läufe ab (S2.H4b)
    if orch.start_run is not None and getattr(orch, "worker_pool", None) is None:
        from . import orchestra_runner
        orch.worker_pool = orchestra_runner.start_pool(hub, orch)
    return tick


# ---- Bausteine aus Spec 0
def _build_links(row, link_specs):
    links = []
    for t, key in link_specs:
        val = row.get(key)
        if val is not None and val != "":
            links.append({"type": t, "id": val})
    return links


def _build_object(obj_type, row_id, title, state, summary, links):
    return {"type": obj_type, "id": row_id, "title": title, "state": state, "summary": summary, "actions": [], "links": links}


def budget_read(hub, oid):
    orch = _orch(hub)
    if orch is None:
        return None
    agent = orch.agent(oid)
    if agent is None:
        return None
    return budget_object(agent, orch.spent(agent["id"]), orch.config.warn_percent, orch.config.stop_percent)


def budget_listing(hub, payload):
    orch = _orch(hub)
    if orch is None:
        return []
    return [budget_object(a, orch.spent(a["id"]), orch.config.warn_percent, orch.config.stop_percent) for a in orch.agents()]


def budget_object(agent, spent, warn_percent=80, stop_percent=100):
    limits = []
    budget_tokens = agent.get("budget_tokens")
    if budget_tokens is not None and budget_tokens != "" and budget_tokens != 0:
        limits.append(("Token", spent.get("tokens", 0), budget_tokens))
    budget_eur_cent = agent.get("budget_eur_cent")
    if budget_eur_cent is not None and budget_eur_cent != "" and budget_eur_cent != 0:
        limits.append(("Cent", spent.get("eur_cent", 0), budget_eur_cent))
    if not limits:
        state = "ohne Grenze"
        summary = "keine Grenze gesetzt"
    else:
        parts = []
        max_ratio = 0
        for label, used, limit in limits:
            parts.append(label + " " + str(used) + "/" + str(limit))
            ratio = used * 100 / limit
            if ratio > max_ratio:
                max_ratio = ratio
        summary = " · ".join(parts)
        if max_ratio >= stop_percent:
            state = "gestoppt"
        elif max_ratio >= warn_percent:
            state = "Warnung"
        else:
            state = "im Rahmen"
    links = [{"type": "agent", "id": agent["id"]}]
    obj = _build_object("budget", agent["id"], "Budget " + agent["name"], state, summary, links)
    obj.update({"agent_id": agent["id"], "pause_reason": agent.get("pause_reason"), "status": agent.get("status")})
    return obj
