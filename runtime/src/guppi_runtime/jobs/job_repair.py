"""Glue between the job supervisor and the context manager: a job that waits for new context gets it.

The supervisor says *a different context is needed* (`awaiting_change == "context_manifest"`), the context manager can build
one. Neither knows the other; this module is the only place that calls both, so the state change stays with the supervisor
and the context work stays with the manager.
"""
from __future__ import annotations

from ..context_manager import ContextError
from ..job_supervisor import JobError

# Supervisor failure class / reason -> context repair trigger
def trigger_for(job):
    error = job.get("last_error") or {}
    if error.get("class") == "context_overflow":
        return "context_overflow"
    if error.get("reason_code") == "progress_stalled":
        return "stagnation"
    return "context_quality_degraded"


def repair_job(supervisor, manager, job_id, *, task, checkpoint_source, trigger=None, **manifest_kw):
    """Repair a job that awaits a new context manifest. Returns the repair plan, or escalates when repair is not possible.

    On success the job still waits in REWORK: its new manifest is registered (`supply_change`) and the next attempt id,
    manifest and checkpoint are stored on the job, but queueing it stays an explicit `enqueue` by the caller.
    """
    job = supervisor.store.load(job_id)
    if (job.get("retry") or {}).get("awaiting_change") != "context_manifest":
        raise JobError("no_change_awaited", "context_manifest")
    trigger = trigger or trigger_for(job)
    try:
        plan = manager.repair(job, trigger=trigger, task=task, checkpoint_source=checkpoint_source,
                              mutating=supervisor.role_mutates(job), **manifest_kw)
    except ContextError as exc:
        if exc.code in {"repair_not_possible", "minimum_context_exceeds_window", "checkpoint_too_large", "pin_missing_source", "policy_denied"}:
            supervisor.escalate(job_id, to="guppi", reason=f"context_repair_failed:{exc.code}:{exc.detail}")
        raise
    manifest = plan["new_manifest"]
    supervisor.supply_change(job_id, context_manifest_id=manifest["manifest_id"])
    with supervisor.store.mutate(job_id) as live:
        live["pending_attempt_id"] = plan["attempt_id_new"]
        live["context_manifest_id"] = manifest["manifest_id"]
        live["context_checkpoint_id"] = plan["checkpoint"]["checkpoint_id"]
    return plan
