"""What the scheduler asks the Captain (Spec 2, D2.8, D2.10), part of `ModelScheduler`: a cloud offer for a run that waits too long
(`cloud_offload`, display and "reject" only, never a switch) and the locked server (`slot_server`: "Modellserver gesperrt, bitte prüfen").
It also takes the garbage reports (`report`) that end in a controlled restart. The scheduler knows no desk: `decisions()` returns plain
records, `uix_server` puts them into the Captain's list and hands the answer back to `answer()`."""
from __future__ import annotations

from datetime import datetime, timezone

from . import slot_store
from .slotplan import needs_cloud_offer

CLOUD_WAYS = ("ablehnen", "cloud_diesen_lauf")
SERVER_WAYS = ("bestaetigen", "ablehnen")


class DecisionMixin:
    def _init_decisions(self):
        self._offers = {}                  # decision id -> record (open cloud offers)
        self._offer_at = {}                # run id -> clock seconds of its last offer (one per run and `offer_every_s`)
        self._dismissed = set()            # `slot_server` decisions the Captain declined (the server stays locked)
        self.canary_invalidate = None      # callable(reason): the next load runs the canary again (gpu_canary.invalidate); wired by the runtime

    # ---- cloud offer (SCH-07)
    def offer_step(self):
        """One look at the line: open at most one offer for the oldest waiting run when the line is too long or the wait too long, and not again
        for that run within `offer_every_s`. Offers of runs that no longer wait vanish. Never switches anything."""
        now_text, clock = self._now(), self.lab.clock()
        with self._conn() as conn:
            waiting = [dict(r) for r in conn.execute("SELECT * FROM slot_leases WHERE state = 'wartend'")]
        ids = {r["run_id"] for r in waiting}
        for did in [d for d, o in self._offers.items() if o["run_id"] not in ids]:
            self._offers.pop(did)
        found = needs_cloud_offer(waiting, now_text, self.config.plan())
        if found is None:
            return None
        run_id = found["run_id"]
        did = f"cloud_offload:{run_id}"
        last = self._offer_at.get(run_id)
        if did in self._offers or (last is not None and clock - last < self.config.offer_every_s):
            return None
        row = next(r for r in waiting if r["run_id"] == run_id)
        minutes = max(0, int((clock - self._epoch(row["enqueued"])) // 60))
        what = row.get("task_id") or run_id
        self._offers[did] = {"id": did, "kind": "cloud_offload", "run_id": run_id, "agent_id": row.get("agent_id"), "grund": found["grund"],
                             "title": f"Lauf {what} wartet seit {minutes} Minuten auf einen Slot. Cloud-Stufe nutzen?",
                             "describe": "Die Warteschlange ist zu lang" if found["grund"] == "schlange" else "Der Lauf wartet länger als erlaubt",
                             "created_at": now_text, "ways": list(CLOUD_WAYS)}
        self._offer_at[run_id] = clock
        self._audit("SLOT_CLOUD_OFFER", run_id=run_id, grund=found["grund"], minutes=minutes)
        return self._offers[did]

    @staticmethod
    def _epoch(text):
        return datetime.strptime(text, slot_store.FORMAT).replace(tzinfo=timezone.utc).timestamp()

    # ---- the Captain's list
    def decisions(self):
        """Open questions to the Captain: cloud offers and the locked server. Plain records `{id, kind, title, describe, created_at, ways, ...}`."""
        if not self.config.enabled:
            return []
        out = list(self._offers.values())
        try:
            with self._conn() as conn:
                server = self._server(conn)
        except Exception:
            return out
        did = f"slot_server:{server['gen']}"
        if server["state"] == "gesperrt" and did not in self._dismissed:
            out.append({"id": did, "kind": "slot_server", "title": "Modellserver gesperrt, bitte prüfen",
                        "describe": f"Grund: {server['reason'] or 'unbekannt'}. Bestätigen entsperrt ihn; der nächste Lauf startet ihn dann neu.",
                        "created_at": server["since"], "ways": list(SERVER_WAYS), "reason": server["reason"]})
        return out

    def answer(self, decision_id, way):
        """The Captain's answer. `cloud_offload`: reject closes it; `cloud_diesen_lauf` closes it and returns `approved` (the caller marks the
        job `cloud_offload_approved`; what that does is Spec 3). `slot_server`: confirm unlocks, reject leaves it locked and closes the question."""
        self._require()
        with self._lock:
            offer = self._offers.get(decision_id)
            if offer is not None:
                if way not in CLOUD_WAYS:
                    raise ValueError("way_not_offered")
                self._offers.pop(decision_id)
                self._audit("SLOT_CLOUD_OFFER_ANSWERED", run_id=offer["run_id"], way=way)
                return {"kind": "cloud_offload", "run_id": offer["run_id"], "approved": way == "cloud_diesen_lauf"}
            current = next((d for d in self.decisions() if d["id"] == decision_id and d["kind"] == "slot_server"), None)
            if current is None:
                raise ValueError("unknown_decision")
            if way not in SERVER_WAYS:
                raise ValueError("way_not_offered")
            if way == "ablehnen":
                self._dismissed.add(decision_id)
                return {"kind": "slot_server", "unlocked": False}
            with self._conn() as conn:
                conn.execute("UPDATE slot_server SET restarts = '[]', garbage = '[]' WHERE name = 'main'")
                slot_store.set_server(conn, self._now(), "aus", owner=None, reason="entsperrt")
            self._audit("SLOT_SERVER_ENTSPERRT", decision=decision_id)
            return {"kind": "slot_server", "unlocked": True}

    # ---- garbage (SCH-08)
    def report(self, run_id, kind="garbage"):
        """A run met garbage from the server. From `garbage.count` reports within `garbage.window_s` the server is suspect: a controlled
        restart (own stop over the own pid, canary invalid; started again lazily by the next run, counted as a restart)."""
        self._require()
        if kind != "garbage":
            raise ValueError("report_kind_invalid")
        with self._lock:
            with self._conn() as conn:
                count = slot_store.note(conn, "garbage", self._now(), self.config.garbage_window_s)
                state = self._server(conn)["state"]
            if count < self.config.garbage_count or state != "bereit":
                return {"count": count, "restart": False}
            with self._conn() as conn:
                conn.execute("UPDATE slot_server SET garbage = '[]' WHERE name = 'main'")
            self._audit("SLOT_SERVER_GARBAGE", run_id=run_id, count=count)
            return {"count": count, "restart": True, "state": self._server_gone(reason="garbage")}

    def _invalidate_canary(self, reason):
        if self.canary_invalidate is not None:
            try:
                self.canary_invalidate(reason)
            except Exception as exc:
                self._audit("SLOT_CANARY_INVALIDATE_FAILED", error=type(exc).__name__)
