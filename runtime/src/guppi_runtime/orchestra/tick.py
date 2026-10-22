"""Der Takt der Orchestrierung (Spec 1, D1.1 `tick.py`, ORC-16, S1.H6).

`tick(orch, now)` ist ein Durchlauf in fünf Stufen; jede fängt ihre Fehler, schreibt `ORC_TICK_ERROR` und der Takt läuft weiter:

    1 Routinen        routines.fire_due → board.create(origin routine) + Weckruf `routine` (key routine:<rid>:<due>)
    2 Lauf-Abgleich   Läufe in Arbeit gegen den Supervisor; Job beendet, stehen geblieben oder aufgegeben → Checkout frei (ORC-11 a)
    3 Quarantäne      AM-Instanz in Quarantäne → Agent pausiert (`quarantaene`), Dauerfreigabe widerrufen (ORC-12)
    4 Weckrufe        heartbeat.due → Aufgabe wählen, Budget, Dauerfreigabe → Lauf, Antrag oder Ende ohne Mission (ORC-05, 06, 09, 15)
    5 Berichte        Wurzelaufgabe mit erledigten Kindern und ohne Bericht → Weckruf `antwort` (key report:<root>, ORC-18)

Den Lauf selbst und den Antrag baut der Desk (`orch.start_run`, `orch.request_run`, S1.H7/H8); fehlen sie oder ist der Supervisor
aus, bleibt der Weckruf offen. Höchstens `heartbeat.max_runs_per_tick` neue Läufe je Takt.

`start(orch, lock_path, interval_s)` startet den Takt als Thread unter der Betriebssystem-Sperre `tick.lock` (endet mit dem
Prozess); wer sie nicht bekommt, erhält `tick_busy`. Der erste Takt gleicht verwaiste Checkouts ab (ORC-11 b). Zeit kommt immer
als Argument oder aus `orch.clock()`."""
import json
import threading
from contextlib import ExitStack

from ..core.mission_lock import exclusive
from . import board, budget, budgetcalc, heartbeat, org, routines, wakeplan

STAGES = ("routinen", "laeufe", "quarantaene", "weckrufe", "berichte")
ORPHAN = "lauf_verwaist"
STALLED = "lauf_beendet"


def _rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ---- 1 Routinen
def _make_task(orch, now):
    def make(routine, due_at):
        template = {}
        try:
            template = json.loads(routine.get("task_template") or "{}") or {}
        except ValueError:
            template = {}
        fields = {"title": str(template.get("titel") or routine["title"])[:200], "assignee": routine["agent_id"], "origin": "routine"}
        if template.get("beschreibung"):
            fields["description"] = str(template["beschreibung"])
        task = board.create(orch.conn, fields, now, "routine")
        heartbeat.enqueue(orch.conn, routine["agent_id"], "routine", wakeplan.key_for("routine", (routine["id"], due_at)), now,
                          orch.config.coalesce_s, task_id=task["id"])
        return task["id"]
    return make


def _routines(orch, now, out):
    results = routines.fire_due(orch.conn, now, orch.config.max_catch_up, _make_task(orch, now))
    out["routinen"] = sum(1 for r in results if r["task_id"])


# ---- 2 Lauf-Abgleich
def _runs(orch, now, out):
    for row in heartbeat.in_flight(orch.conn):
        if orch.run_alive(row.get("job_id") or row["run_id"]) is not False:
            continue
        board.release(orch.conn, row["task_id"], row["run_id"], "zugewiesen", now, STALLED)
        orch.audit_event("ORC_RUN_RELEASED", {"task_id": row["task_id"], "run_id": row["run_id"], "agent_id": row["agent_id"],
                                              "reason": STALLED})
        out["freigegeben"] += 1


def orphans(orch, now):
    """Neustart-Abgleich (ORC-11 b): Checkouts, deren Lauf nicht mehr lebt, werden frei; die Aufgabe geht an den Bearbeiter zurück."""
    rows = heartbeat.in_flight(orch.conn)
    live = [r["run_id"] for r in rows if orch.run_alive(r.get("job_id") or r["run_id"])]
    freed = 0
    for task in board.orphans(orch.conn, live):
        board.release(orch.conn, task["id"], task["checkout_run"], "zugewiesen", now, ORPHAN)
        orch.audit_event("ORC_RUN_RELEASED", {"task_id": task["id"], "run_id": task["checkout_run"], "agent_id": task["checkout_by"],
                                              "reason": ORPHAN})
        freed += 1
    return freed


# ---- 3 Quarantäne
def _quarantine(orch, now, out):
    if orch.instance_status is None:
        return
    for agent in org.list(orch.conn, status="aktiv"):
        if orch.instance_status(agent["instance_id"]) != "QUARANTINED":
            continue
        org.pause(orch.conn, agent["id"], "quarantaene", now)
        orch.revoke_standing(agent["id"], "quarantaene")
        orch.audit_event("ORC_AGENT_PAUSED", {"agent_id": agent["id"], "reason": "quarantaene"})


# ---- 4 Weckrufe
def _tasks_of(conn, agent_id):
    tasks = _rows(conn, "SELECT * FROM tasks WHERE assignee = ? OR checkout_by = ?", (agent_id, agent_id))
    ids = [t["id"] for t in tasks]
    blockers = []
    if ids:
        marks = ",".join("?" * len(ids))
        blockers = _rows(conn, "SELECT b.task_id, b.blocked_by_task_id, t.state FROM blockers b JOIN tasks t ON t.id = b.blocked_by_task_id "
                               f"WHERE b.task_id IN ({marks})", ids)
    return tasks, blockers


def _budget_state(orch, agent, now):
    view = budget.state(orch.conn, agent, now, orch.config.warn_percent, orch.config.stop_percent)
    if view["stufe"] == "gestoppt":
        return "gestoppt", view
    try:
        budgetcalc.precheck(agent.get("budget_tokens"), view["verbraucht_token"], orch.token_cap(agent["role"]))
    except ValueError:
        return "zu_wenig", view
    return view["stufe"], view


def _stop_for_budget(orch, agent, view, now):
    budget.open_incident(orch.conn, agent["id"], "stopp", view["prozent"] if view["prozent"] is not None else 100, now)
    org.pause(orch.conn, agent["id"], "budget", now)
    orch.revoke_standing(agent["id"], "budget")
    orch.audit_event("ORC_BUDGET_STOP", {"agent_id": agent["id"], "prozent": view["prozent"]})


def _wake(orch, group, now, out):
    leader = group["leader"]
    conn = orch.conn
    agent = org.get(conn, leader["agent_id"])
    if agent is None or agent["status"] != "aktiv":
        heartbeat.finish(conn, leader["id"], "pausiert", now)
        return
    tasks, blockers = _tasks_of(conn, agent["id"])
    if sum(1 for t in tasks if t.get("checkout_by") == agent["id"]) >= (agent.get("max_parallel") or 1):
        return                                              # ein Lauf läuft schon: der Weckruf bleibt offen (nächster Takt)
    task, reason = wakeplan.pick_task([t for t in tasks if t.get("assignee") == agent["id"]], blockers, leader.get("task_id"))
    stage, view = _budget_state(orch, agent, now) if reason == "ok" else ("ok", None)
    outcome = wakeplan.decide_run(agent, stage, True, reason)
    if outcome in ("blockiert", "keine_aufgabe", "pausiert"):
        heartbeat.finish(conn, leader["id"], outcome, now)
        return
    if outcome == "laeuft_schon":
        return
    if outcome == "kein_budget":
        heartbeat.finish(conn, leader["id"], "kein_budget", now)
        _stop_for_budget(orch, agent, view, now)
        return
    blocked = orch.run_blocked()
    if blocked:                                             # Supervisor aus oder kein Lauf verdrahtet: offen lassen, einmal melden
        orch.note_blocked(blocked)
        return
    if out["laeufe"] < orch.config.max_runs_per_tick and orch.guard is not None:
        allowed = orch.guard.authorize_standing(agent["id"], fingerprint=org.fingerprint(agent), budget_stage=stage,
                                                run_ref=leader["id"])
        if allowed.get("authorized"):
            run = orch.start_run(orch, agent, task, leader, "standing") or {}
            heartbeat.finish(conn, leader["id"], "lauf", now, job_id=run.get("job_id"), mission_id=run.get("mission_id"))
            out["laeufe"] += 1
            return
    elif out["laeufe"] >= orch.config.max_runs_per_tick:
        return                                              # Grenze je Takt: der Weckruf wartet auf den nächsten
    waiting = heartbeat.pending_request(conn, agent["id"])
    if waiting is not None:
        heartbeat.finish(conn, leader["id"], "antrag", now, request_mission_id=waiting.get("request_mission_id"))
        return
    request_mission_id = orch.request_run(orch, agent, task, leader)
    heartbeat.finish(conn, leader["id"], "antrag", now, request_mission_id=request_mission_id)
    out["antraege"] += 1


def _wakeups(orch, now, out):
    groups = heartbeat.due(orch.conn, now, orch.config.coalesce_s)
    out["weckrufe"] = len(groups)
    for group in groups:
        try:
            _wake(orch, group, now, out)
        except Exception as exc:                             # ein Agent hält die anderen nicht auf
            orch.tick_error("weckrufe", exc, agent_id=group["leader"]["agent_id"])
            out["fehler"].append("weckrufe")


# ---- 5 Berichte
def _reports(orch, now, out):
    roots = _rows(orch.conn, "SELECT id, assignee FROM tasks WHERE parent_id IS NULL AND reported_at IS NULL AND assignee IS NOT NULL "
                             "AND state NOT IN ('erledigt', 'abgebrochen') ORDER BY id")
    for root in roots:
        if board.children_done(orch.conn, root["id"]):
            heartbeat.enqueue(orch.conn, root["assignee"], "antwort", wakeplan.key_for("report", (root["id"],)), now,
                              orch.config.coalesce_s, task_id=root["id"])


STEPS = (("routinen", _routines), ("laeufe", _runs), ("quarantaene", _quarantine), ("weckrufe", _wakeups), ("berichte", _reports))


def tick(orch, now):
    out = {"weckrufe": 0, "laeufe": 0, "antraege": 0, "routinen": 0, "freigegeben": 0, "fehler": []}
    with orch.lock:
        for name, step in STEPS:
            try:
                step(orch, now, out)
            except Exception as exc:
                orch.tick_error(name, exc)
                out["fehler"].append(name)
        orch.mark_tick(now)
    return out


def run_once(orch, first=False):
    """Ein Takt mit der Uhr der Fassade; beim ersten nach dem Start vorher der Neustart-Abgleich."""
    now = orch.clock()
    if first:
        with orch.lock:
            try:
                orphans(orch, now)
            except Exception as exc:
                orch.tick_error("neustart", exc)
    return tick(orch, now)


def start(orch, lock_path, interval_s):
    stack = ExitStack()
    try:
        stack.enter_context(exclusive(lock_path))
    except RuntimeError as exc:
        stack.close()
        if str(exc) == "mission_execution_busy":
            raise ValueError("tick_busy") from None
        raise
    stop = threading.Event()

    def loop():
        with stack:
            first = True
            while not stop.is_set():
                try:
                    run_once(orch, first)
                except Exception as exc:                     # der Takt stirbt nicht an einem Durchlauf
                    orch.tick_error("takt", exc)
                first = False
                stop.wait(interval_s)

    thread = threading.Thread(target=loop, name="orchestra-tick", daemon=True)
    thread.stop = stop
    thread.start()
    return thread
