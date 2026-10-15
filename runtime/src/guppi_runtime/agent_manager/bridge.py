"""Assignment bridge with a FAKE runtime (integration stage 4). New module next to the control master; it changes nothing in `control.py` or `guard.py`.

An assignment needs an approval token that the Guard issued for exactly this agent and mission (decision D05: only the Guard admits). Records carry `"demo"`: True for the fake runtime below, False for a real runtime (`DevVmRuntime.demo`). The bridge never replays an uncertain start: when the start answer is lost, the run is `in_doubt` until the
runtime itself says what happened (`reconcile`); `unknown` is never turned into `failed`.

States: prepared (written before the runtime is called) -> running | failed (start refused, certainly not started) | in_doubt (answer lost) -> succeeded | failed (reconcile).
"""
import sqlite3

from .agent_contracts import ContractError, canonical_digest, make_id

ACTION = "agent.assign"
OPEN_STATES = ("prepared", "running", "in_doubt")


class FakeRuntime:
    """Scripted stand-in for a runtime: start_error None | "refused" (certainly not started) | "timeout" (maybe started); outcome what a started run ends with."""

    demo = True

    def __init__(self, outcome="succeeded", start_error=None, forget=False):
        self.outcome, self.start_error, self.forget = outcome, start_error, forget
        self.runs, self.start_calls = {}, 0

    def start(self, run_id, assignment):
        self.start_calls += 1
        if self.start_error == "refused":
            raise ConnectionRefusedError("fake runtime refused")
        self.runs[run_id] = "running"
        if self.start_error == "timeout":
            raise TimeoutError("fake runtime did not answer")

    def stop(self, run_id, reason):
        running = self.runs.get(run_id) == "running"
        if running:
            self.runs[run_id] = "failed"
        return running

    def finish(self):
        for run_id, state in self.runs.items():
            if state == "running":
                self.runs[run_id] = self.outcome

    def inspect(self, run_id):
        return "unknown" if self.forget else self.runs.get(run_id, "unknown")


class AgentBridge:
    def __init__(self, db_path, guard, runtime, registry):
        self.guard, self.runtime, self.registry = guard, runtime, registry
        self.db = sqlite3.connect(str(db_path), isolation_level=None, timeout=30)
        self.db.execute("CREATE TABLE IF NOT EXISTS assignments (command_id TEXT PRIMARY KEY, request TEXT NOT NULL, assignment_id TEXT NOT NULL, run_id TEXT NOT NULL, "
                        "agent_ref TEXT NOT NULL, mission_id TEXT NOT NULL, state TEXT NOT NULL, detail TEXT)")
        if "demo" not in [column[1] for column in self.db.execute("PRAGMA table_info(assignments)")]:
            self.db.execute("ALTER TABLE assignments ADD COLUMN demo INTEGER NOT NULL DEFAULT 1")

    def close(self):
        self.db.close()

    def submit(self, command_id, agent_ref, mission_id, input_ref, token):
        if not isinstance(command_id, str) or not command_id:
            raise ContractError("bad_command", "command_id must be a non-empty string")
        request = canonical_digest([agent_ref, mission_id, input_ref])
        stored = self._row(command_id)
        if stored is not None:
            if stored["request"] != request:
                raise ContractError("command_conflict", "command_id already used with another request")
            return self._record(stored, replayed=True)
        self._check_agent(agent_ref)
        binding = {"agent_ref": agent_ref, "mission_id": mission_id, "input_ref": input_ref}
        decision = self.guard.authorize(token, mission_id=mission_id, action=ACTION, target=agent_ref, request_binding=binding)
        if not decision.get("authorized"):
            raise ContractError("admission_refused", str(decision.get("reason")))
        ids = {"assignment_id": make_id("asg", {"c": command_id}), "run_id": make_id("run", {"c": command_id})}
        demo = 1 if getattr(self.runtime, "demo", True) else 0
        self.db.execute("INSERT INTO assignments (command_id, request, assignment_id, run_id, agent_ref, mission_id, state, detail, demo) VALUES (?, ?, ?, ?, ?, ?, 'prepared', NULL, ?)",
                        (command_id, request, ids["assignment_id"], ids["run_id"], agent_ref, mission_id, demo))
        self._start(command_id, ids["run_id"], {"agent_ref": agent_ref, "mission_id": mission_id, "input_ref": input_ref})
        return self._record(self._row(command_id), replayed=False)

    def _check_agent(self, agent_ref):
        entry = self.registry.get("template", agent_ref) if isinstance(agent_ref, str) and agent_ref else None
        if entry is None:
            raise ContractError("agent_unknown", "no such template")
        if not entry["data"]["preview"]["ok"]:
            raise ContractError("agent_not_importable", "the import preview of this template has problems")

    def _start(self, command_id, run_id, assignment):
        try:
            self.runtime.start(run_id, assignment)
        except ConnectionRefusedError as exc:
            self._set(command_id, "failed", f"start refused: {exc}")
        except Exception as exc:
            self._set(command_id, "in_doubt", f"{type(exc).__name__}: {exc}")
        else:
            self._set(command_id, "running", None)

    def reconcile(self):
        changed = 0
        for row in self._rows(OPEN_STATES):
            seen = self.runtime.inspect(row["run_id"])
            new = {"succeeded": "succeeded", "failed": "failed", "running": "running"}.get(seen, "in_doubt")
            if new != row["state"]:
                self._set(row["command_id"], new, f"runtime says {seen}")
                changed += 1
        return changed

    def stop(self, assignment_id, reason):
        row = self.db.execute("SELECT * FROM assignments WHERE assignment_id = ?", (assignment_id,)).fetchone()
        if row is None:
            raise ContractError("assignment_unknown", "no such assignment")
        row = self._named(row)
        if row["state"] not in OPEN_STATES:
            raise ContractError("not_running", "the assignment is not running: " + row["state"])
        stopped = self.runtime.stop(row["run_id"], reason)
        self._set(row["command_id"], "failed", "stopped: " + str(reason)[:200])
        return {**self._record(self._row(row["command_id"]), replayed=False), "was_running": stopped}

    def get(self, assignment_id):
        row = self.db.execute("SELECT * FROM assignments WHERE assignment_id = ?", (assignment_id,)).fetchone()
        return None if row is None else self._record(self._named(row), replayed=False)

    def list(self):
        return [self._record(row, replayed=False) for row in self._rows(None)]

    def _set(self, command_id, state, detail):
        self.db.execute("UPDATE assignments SET state = ?, detail = ? WHERE command_id = ?", (state, detail, command_id))

    def _row(self, command_id):
        row = self.db.execute("SELECT * FROM assignments WHERE command_id = ?", (command_id,)).fetchone()
        return None if row is None else self._named(row)

    def _rows(self, states):
        rows = [self._named(r) for r in self.db.execute("SELECT * FROM assignments ORDER BY assignment_id")]
        return rows if states is None else [r for r in rows if r["state"] in states]

    def _named(self, row):
        names = [c[1] for c in self.db.execute("PRAGMA table_info(assignments)")]
        return dict(zip(names, row))

    @staticmethod
    def _record(row, replayed):
        return {"assignment_id": row["assignment_id"], "run_id": row["run_id"], "agent_ref": row["agent_ref"], "mission_id": row["mission_id"], "state": row["state"],
                "detail": row["detail"], "demo": bool(row["demo"]), "replayed": replayed}
