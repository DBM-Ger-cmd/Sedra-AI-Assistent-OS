import os
import threading
from datetime import datetime, timezone

from . import board, chain as chain_mod
from ..jobs.job_supervisor import FINAL_STATES

# Spec 1 (D1.1 Fassade, S1.H6): Brain, Router, Web, AM-Status, Auflöser, Vertrag, Ausgabegrenze und Uhr kommen von außen;
# `start_run`/`request_run` (Lauf und Antrag, S1.H7/H8) baut der Desk und gibt sie hier hinein.
PARTS = ("guard", "supervisor", "templates", "brain", "model_router", "web", "instance_status", "instance_admitted", "resolve",
         "contract_for", "token_cap", "clock", "start_run", "request_run")
TIME = "%Y-%m-%dT%H:%M:%SZ"
STALE_TICKS = 3                 # D1.7: nach 3 × tick_s ohne Takt läuft er nicht mehr


def utc_now():
    return datetime.now(timezone.utc).strftime(TIME)


def _error_text(exc, prefix, fallback):
    if isinstance(exc, ValueError) and str(exc).startswith(prefix):
        return str(exc)
    return fallback


def _query(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    if not rows:
        return []
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


class Orchestra:
    def __init__(self, config, conn, audit=None, guard=None, supervisor=None, templates=None, brain=None, model_router=None, web=None,
                 instance_status=None, resolve=None, contract_for=None, token_cap=None, clock=None, start_run=None, request_run=None,
                 data_dir=None, instance_admitted=None):
        self.config = config
        self.conn = conn
        self.audit = audit
        self.guard = guard
        self.supervisor = supervisor
        self.templates = templates
        self.brain = brain
        self.model_router = model_router
        self.web = web
        self.instance_status = instance_status
        self.instance_admitted = instance_admitted     # AM-Zulassung (VERIFIED, gültig, nicht widerrufen); fehlt der Teil: nicht zugelassen
        self.resolve = resolve
        self.contract_for = contract_for
        self._token_cap = token_cap
        self._clock = clock or utc_now
        self.start_run = start_run
        self.request_run = request_run
        self.data_dir = data_dir
        self.lock = threading.RLock()          # eine Verbindung, mehrere Threads: Takt und Desk schreiben nacheinander
        self.tick_thread = None
        self._blocked_noted = set()

    # ---- Uhr, Audit, Grenzen
    def clock(self):
        return self._clock()

    def token_cap(self, role):
        return int(self._token_cap(role)) if self._token_cap is not None else 0

    def audit_event(self, event, payload):
        if self.audit is not None:
            self.audit(event, payload)

    def tick_error(self, stage, exc, **extra):
        self.audit_event("ORC_TICK_ERROR", {"stage": stage, "error": str(exc) or type(exc).__name__, **extra})

    # ---- Takt (ORC-16): Zeitstempel in meta, Zustand für boot() und quelle
    def mark_tick(self, now):
        for key, value in (("last_tick_at", now), ("tick_owner", str(os.getpid()))):
            self.conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))

    def _meta(self, key):
        rows = _query(self.conn, "SELECT value FROM meta WHERE key = ?", (key,))
        return rows[0]["value"] if rows else None

    def takt(self):
        last = self._meta("last_tick_at")
        running = False
        if last:
            try:
                age = (datetime.strptime(self.clock(), TIME) - datetime.strptime(last, TIME)).total_seconds()
                running = age <= STALE_TICKS * self.config.tick_s
            except ValueError:
                running = False
        return {"laeuft": running, "letzter": last, "owner": self._meta("tick_owner")}

    def start_tick(self):
        """Startet den Takt-Thread (einmal); ein zweiter Takter bekommt `tick_busy`."""
        from . import tick
        if self.tick_thread is None:
            self.sync_all_standing()
            self.tick_thread = tick.start(self, self.data_dir / "tick.lock", self.config.tick_s)
        return self.tick_thread

    def stop_tick(self, wait_s=5):
        pool, self.worker_pool = getattr(self, "worker_pool", None), None
        if pool is not None:
            pool.stop(wait_s)
        thread, self.tick_thread = self.tick_thread, None
        if thread is not None:
            thread.stop.set()
            thread.join(wait_s)

    # ---- Lauf: lebt er noch, darf einer starten
    def run_alive(self, job_id):
        """True: der Job lebt; False: beendet, stehen geblieben oder aufgegeben (kein laufender Versuch mehr); None: unbekannt."""
        if self.supervisor is None or not job_id:
            return False if not job_id else None
        try:
            job = self.supervisor.store.load(job_id)
        except Exception:
            return False
        if job.get("state") in FINAL_STATES:
            return False
        attempts = job.get("attempt_log") or []
        return not attempts or attempts[-1].get("outcome") == "RUNNING"

    def run_blocked(self):
        if self.supervisor is None or not getattr(self.supervisor, "enabled", False):
            return "supervisor_off"
        if self.start_run is None or self.request_run is None:
            return "runner_off"
        return None

    def note_blocked(self, reason):
        if reason not in self._blocked_noted:
            self._blocked_noted.add(reason)
            self.tick_error("weckrufe", ValueError(reason))

    def admitted(self, agent):
        """Entscheidung Zulassung vor erstem Lauf (Captain 22.10.2026): ohne AM-Zulassung kein Lauf; ohne Prüfer heißt es nein."""
        if self.instance_admitted is None:
            return False
        try:
            return bool(self.instance_admitted(agent["instance_id"]))
        except Exception:
            return False

    def set_task_mission(self, task_id, mission_id):
        """Die Lauf-Mission an der Aufgabe (D1.5 Schritt 4); `board` hat dafür keinen Setter."""
        self.conn.execute("UPDATE tasks SET mission_id = ? WHERE id = ?", (mission_id, task_id))

    def mark_reported(self, task_id, now):
        """Ein Bericht je Wurzelaufgabe (ORC-18): `reported_at` gesetzt, der Takt weckt nicht noch einmal."""
        self.conn.execute("UPDATE tasks SET reported_at = ?, updated_at = ?, revision = revision + 1 WHERE id = ?", (now, now, task_id))

    def revoke_standing(self, agent_id, reason):
        if self.guard is not None:
            count = self.guard.revoke_standing(agent_id, reason=reason)
            self.sync_standing(agent_id)
            return count
        return 0

    MIRROR = {"active": "aktiv", "spent": "verbraucht", "expired": "abgelaufen"}

    def sync_standing(self, agent_id):
        """Spiegel `standing_approvals` (D1.2): nur Anzeige; maßgeblich ist der Guard. Abgleich nach jedem Guard-Aufruf und beim Start."""
        status = getattr(self.guard, "standing_status", None)
        token = status(agent_id) if status is not None else None
        if token is None:
            return None
        state = self.MIRROR.get(token["status"])
        if state is None:
            state = "widerrufen" if str(token.get("end_reason") or "").startswith("widerrufen") else "erloschen"
        now = self.clock()
        with self.lock:
            self.conn.execute("UPDATE standing_approvals SET status = 'erloschen', end_reason = 'ersetzt', updated_at = ? "
                              "WHERE agent_id = ? AND status = 'aktiv' AND token_id <> ?", (now, agent_id, token["token_id"]))
            self.conn.execute("INSERT OR REPLACE INTO standing_approvals (token_id, agent_id, granted_at, expires_at, max_uses, uses, status, "
                              "end_reason, fingerprint_digest, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (token["token_id"], agent_id, token["granted_at"], token["validity"]["expires_at"], token["limits"]["max_uses"],
                               token["uses"], state, token.get("end_reason"), token["grants"]["request_digest"], now))
        return state

    def sync_all_standing(self):
        for row in self.agents():
            self.sync_standing(row["id"])

    def schema_version(self):
        rows = _query(self.conn, "SELECT value FROM meta WHERE key = ?", ("schema_version",))
        if not rows:
            return 0
        return int(rows[0]["value"])

    def close(self):
        self.stop_tick()
        self.conn.close()

    def agents(self):
        return _query(self.conn, "SELECT * FROM agents ORDER BY id")

    def agent(self, agent_id):
        rows = _query(self.conn, "SELECT * FROM agents WHERE id = ?", (agent_id,))
        return rows[0] if rows else None

    def routines(self):
        return _query(self.conn, "SELECT * FROM routines ORDER BY id")

    def routine(self, routine_id):
        rows = _query(self.conn, "SELECT * FROM routines WHERE id = ?", (routine_id,))
        return rows[0] if rows else None

    def spent(self, agent_id):
        rows = _query(self.conn, "SELECT tokens_in, tokens_out, eur_cent, requests FROM spend WHERE agent_id = ?", (agent_id,))
        if not rows:
            return {"tokens": 0, "eur_cent": 0, "requests": 0}
        total_tokens = sum(r["tokens_in"] + r["tokens_out"] for r in rows)
        total_eur_cent = sum(r["eur_cent"] for r in rows)
        total_requests = sum(r["requests"] for r in rows)
        return {"tokens": total_tokens, "eur_cent": total_eur_cent, "requests": total_requests}

    def issues(self, state=None, assignee=None):
        sql = "SELECT * FROM tasks"
        params = []
        conditions = []
        if state is not None:
            conditions.append("state = ?")
            params.append(state)
        if assignee is not None:
            conditions.append("assignee = ?")
            params.append(assignee)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY priority DESC, created_at, id"
        return _query(self.conn, sql, tuple(params))

    def issue(self, task_id):
        rows = _query(self.conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
        return rows[0] if rows else None

    # ---- Leser für Shell D (Vertrag S1, „Felder, die Shell D zusätzlich erwartet“; OP-16: in der Fassade)
    def agent_runs(self, agent_id, limit=20):
        """`laeufe` am Agenten: die neuesten Weckrufe mit Ausgang."""
        return _query(self.conn, "SELECT due_at, outcome, task_id, mission_id FROM wakeups WHERE agent_id = ? AND outcome IS NOT NULL "
                                 "AND coalesced_into IS NULL ORDER BY id DESC LIMIT ?", (agent_id, int(limit)))

    def routine_runs(self, routine_id, limit=20):
        """`laeufe` an der Routine: die neuesten Termine mit Ausgang."""
        return _query(self.conn, "SELECT due_at, outcome, task_id FROM routine_runs WHERE routine_id = ? ORDER BY due_at DESC LIMIT ?",
                      (routine_id, int(limit)))

    def comments(self, task_id, limit=None):
        """`kommentare` am Issue als Liste, älteste zuerst; mit `limit` nur die letzten."""
        sql = "SELECT id, author_kind, author_id, text, ts FROM comments WHERE task_id = ? ORDER BY id DESC"
        rows = _query(self.conn, sql + (" LIMIT ?" if limit is not None else ""), (task_id, int(limit)) if limit is not None else (task_id,))
        return list(reversed(rows))

    def chain(self, task_id):
        """`kette` am Issue (ORC-13): Vorhaben und Projekt über den Auflöser der Fassade, None ohne Aufgabe."""
        try:
            rows = board.chain_rows(self.conn, task_id)
        except ValueError:
            return None
        task = rows["task"]
        look = self.resolve or (lambda kind, ref: None)
        goal = look("vorhaben", task["goal_ref"]) if task.get("goal_ref") else None
        project = look("projekt", task["project_id"]) if task.get("project_id") else None
        return chain_mod.build(task, rows["parents"], project, goal, max_chars=self.config.runner["chain_max_chars"])


def build(switch_on, load_config, open_db, config_path, runtime_data, audit=None, **parts):
    for key in parts:
        if key not in PARTS:
            raise TypeError(f"Unexpected part: {key}")
    if switch_on is not True:
        return (None, None)
    try:
        config = load_config(config_path)
    except Exception as exc:
        error = _error_text(exc, "orchestra_config_", "orchestra_config_invalid:unreadable")
        if audit is not None:
            audit("ORCHESTRA_OFF", {"reason": error})
        return (None, error)
    try:
        conn = open_db(config.database_path(runtime_data))
    except Exception as exc:
        error = _error_text(exc, "orchestra_", "orchestra_db_error:open")
        if audit is not None:
            audit("ORCHESTRA_OFF", {"reason": error})
        return (None, error)
    return (Orchestra(config, conn, audit=audit, data_dir=config.database_path(runtime_data).parent, **parts), None)


def boot_entry(orchestra, error):
    entry = {
        "enabled": orchestra is not None,
        "error": error,
        "schema_version": orchestra.schema_version() if orchestra is not None else None,
    }
    if orchestra is not None:                  # aus bleibt der Eintrag wie in Spec 0
        entry["takt"] = orchestra.takt()
    return entry
