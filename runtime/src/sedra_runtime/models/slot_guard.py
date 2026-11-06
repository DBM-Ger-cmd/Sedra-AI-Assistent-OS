"""The router's slot hook (Spec 2, D2.6, SCH-11): a local llama call without a slot lease of its mission takes one from the model scheduler
around the request. `ModelRouter.slot_guard` is None (off, behaviour as before) or a `SlotGuard`."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager, nullcontext

from .base import ModelAdapterError

CAPTAIN_OWNERS = ("captain-chat", "captain")
PRIORITY_CAPTAIN, PRIORITY_OTHER = 7, 5


class SlotGuard:
    def __init__(self, scheduler, *, wait_s=30, applies=("llama-cpp-server",)):
        self.scheduler, self.wait_s, self.applies = scheduler, wait_s, tuple(applies)

    def _holds(self, run_id):
        """True when this run (job id) already holds an active slot lease: the call then belongs to it."""
        if not run_id:
            return False
        with self.scheduler._conn() as conn:
            return conn.execute("SELECT 1 FROM slot_leases WHERE run_id = ? AND state = 'aktiv'", (run_id,)).fetchone() is not None

    def around(self, adapter, mission_id, run_id=None, owner=None):
        """Context manager for one request. Nothing for a cloud or non-llama adapter, a disabled scheduler or a run that holds its lease;
        otherwise `scheduler.slot(...)`, which raises `SchedulerError('slot_wait_timeout')` with the reason after `wait_s`."""
        if getattr(adapter, "id", None) not in self.applies or getattr(adapter, "route", "local") == "cloud" or not self.scheduler.enabled:
            return nullcontext()
        if self._holds(run_id) or self._holds(mission_id):
            return nullcontext()
        who = owner or f"direkt:{mission_id or '-'}"
        return self._slot(who, PRIORITY_CAPTAIN if owner in CAPTAIN_OWNERS else PRIORITY_OTHER)

    @contextmanager
    def _slot(self, who, priority):
        """Errors of getting the slot become `ModelAdapterError("slot_wait_timeout:<grund>")`; errors of the request itself pass unchanged."""
        from ..jobs.model_scheduler import SchedulerError
        with ExitStack() as stack:
            try:
                lease = stack.enter_context(self.scheduler.slot(who, priority, wait_s=self.wait_s))
            except SchedulerError as exc:
                grund = (exc.detail or {}).get("grund") if isinstance(exc.detail, dict) else None
                raise ModelAdapterError(f"{exc.reason}:{grund}" if grund else exc.reason) from exc
            yield lease
