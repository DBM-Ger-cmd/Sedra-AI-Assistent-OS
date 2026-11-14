"""View methods for ModelScheduler (Spec 2, D2.2): what the desk and the Guard see.

This module was split out to keep the main scheduler file under 400 lines.
"""
from __future__ import annotations

from . import slot_store


class ViewMixin:
    """View methods for ModelScheduler."""

    # ---- views
    def view(self):
        """The shape of Spec 4 D4.2.4 plus server, exklusiv, warnung. Never raises."""
        if not self.config.enabled:
            return {"enabled": False, "error": None}
        try:
            now = self._now()
            with self._conn() as conn:
                out = slot_store.view(conn, now, self.config.plan())
                server = self._server(conn)
                pending = slot_store.handover_pending(conn, now)
                enqueued = {r["run_id"]: r["enqueued"] for r in conn.execute("SELECT run_id, enqueued FROM slot_leases WHERE state = 'wartend'")}
        except Exception as exc:
            return {"enabled": True, "error": type(exc).__name__}
        warn = out.get("warnung")
        out["warnung"] = {"art": warn["grund"], "run_id": warn["run_id"], "seit": enqueued.get(warn["run_id"])} if warn else None
        exclusive = None
        if server["state"] in ("drain", "exklusiv") and (server["reason"] or "").startswith("exklusiv:"):
            req = next((p for p in pending if p["owner"] == server["owner"]), None)
            exclusive = {"eigner": server["owner"], "zweck": req["purpose"] if req else None, "seit": req["since"] if req else server["since"]}
        out.update(enabled=True, error=None, modell=server["recipe"], warte_max_s=self.config.wait_max_s, exklusiv=exclusive,
                   lease=self._token is not None, slots_cap=self._cap(), standard_slots=dict(self.config.standard_slots))
        return out

    def events(self, limit=20):
        with self._conn() as conn:
            return slot_store.events(conn, limit)