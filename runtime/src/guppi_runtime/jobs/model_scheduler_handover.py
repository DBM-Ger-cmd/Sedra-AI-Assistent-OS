"""Stopping the server and handing the GPU to another process (Spec 2, D2.6, D2.7, SCH-10), part of `ModelScheduler`. `stop_server` is the
workshop's unload; a process that waits in `TestLab.acquire` stands in `handover_requests`, and `poll` drains the slots, stops the own
server and frees the lease. Nothing is killed."""
from __future__ import annotations

from . import slot_store


class HandoverMixin:
    def stop_server(self, *, owner="werkstatt", force=False):
        """Unload (workshop). With active runs nothing happens unless `force` (the Captain's `erzwingen`): their leases end `unterbrochen`."""
        self._require()
        with self._lock:
            with self._conn() as conn:
                server, active = self._server(conn), self._active(conn)
            if active and not force:
                return {"status": "leases_active", "active": sorted(r["run_id"] for r in active)}
            if server["state"] == "gesperrt":
                return {"status": "gesperrt", "interrupted": []}            # only the Captain's answer to the question unlocks it (D2.8)
            if server["state"] in ("aus", "exklusiv") and self._token is None:
                return {"status": "already_off", "interrupted": []}
            if server["state"] == "drain" and (server["reason"] or "").startswith("exklusiv:"):
                # the Captain forces the handover (D2.7, point 4): the server goes, the request of the waiting process stays
                self._shutdown("exklusiv", owner=server["owner"], reason=server["reason"])
                ended = sorted(r["run_id"] for r in active)
                with self._conn() as conn:                                 # `exklusiv` does not end leases by itself: forcing does
                    conn.execute("UPDATE slot_leases SET state = 'unterbrochen', reason = 'erzwungen' WHERE state = 'aktiv'")
                return {"status": "stopped", "interrupted": ended}
            out = self._shutdown("aus", reason=f"stop:{owner}" + (":erzwungen" if force else ""))
            return {"status": "stopped", "interrupted": out["interrupted"]}

    # ---- handover to other processes
    def exclusive(self, owner, purpose, *, priority=0, pid=None, ttl_s=60):
        """Ask for the GPU from this process (same entry a waiting `TestLab.acquire` writes), then take one poll step."""
        self._require()
        with self._conn() as conn:
            slot_store.handover_request(conn, owner, purpose, priority, pid, self._now(), ttl_s=ttl_s)
        return self.poll()

    def poll(self):
        """One step, called every `poll_s` from the desk's poller: notice a crashed server, and hand the GPU over to a waiting process
        (drain: no new slots, wait for the active runs at most `drain_max_s`, stop the own server, free the lease). Kills nothing."""
        self._require()
        if not self._lock.acquire(blocking=False):
            return {"state": None, "action": "busy"}      # a model is being loaded: the desk's poller must not stand still meanwhile
        try:
            out = self._poll()
            try:
                self.offer_step()                   # D2.10: a run that waits too long gets one cloud offer (never a switch)
            except Exception as exc:
                self._audit("SLOT_OFFER_FAILED", error=type(exc).__name__)
            return out
        finally:
            self._lock.release()

    def _poll(self):
        now = self._now()
        with self._conn() as conn:
            server, active, pending = self._server(conn), self._active(conn), slot_store.handover_pending(conn, now)
        state = server["state"]
        if state == "bereit" and not self._alive():
            return {"state": self._server_gone(), "action": "server_exited"}
        if not pending:
            if state == "exklusiv" or (state == "drain" and (server["reason"] or "").startswith("exklusiv:")):
                with self._conn() as conn:
                    back = "bereit" if state == "drain" else "aus"         # the waiting process gave up or is done
                    slot_store.set_server(conn, now, back, owner=None, reason=None)
                self._drain_since, self._drain_overdue = None, False
                return {"state": back, "action": "handover_ended"}
            return {"state": state, "action": None}
        first = pending[0]
        if state == "bereit":
            with self._conn() as conn:
                slot_store.set_server(conn, now, "drain", owner=first["owner"], reason=f"exklusiv:{first['owner']}")
            self._drain_since, self._drain_overdue = self.lab.clock(), False
            self._audit("SLOT_DRAIN", owner=first["owner"], purpose=first["purpose"], active=len(active))
            state = "drain"
        if state == "drain":
            if active:
                since = self._drain_since if self._drain_since is not None else self.lab.clock()
                self._drain_since = since
                if self.lab.clock() - since > self.config.drain_max_s and not self._drain_overdue:
                    self._drain_overdue = True                      # the request stays, nobody is killed; the Captain may force it
                    self._audit("SLOT_DRAIN_OVERDUE", owner=first["owner"], active=sorted(r["run_id"] for r in active))
                return {"state": "drain", "action": "draining", "active": len(active)}
            self._shutdown("exklusiv", owner=first["owner"], reason=f"exklusiv:{first['owner']}")
            self._drain_since, self._drain_overdue = None, False
            return {"state": "exklusiv", "action": "handed_over", "owner": first["owner"]}
        if state == "aus":
            self._release_gpu()
            with self._conn() as conn:
                slot_store.set_server(conn, now, "exklusiv", owner=first["owner"], reason=f"exklusiv:{first['owner']}")
            return {"state": "exklusiv", "action": "handed_over", "owner": first["owner"]}
        return {"state": state, "action": None}
