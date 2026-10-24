"""GUPPI Job Supervisor, minimal version (Phase 2): queue, claim, lease, retry, cancel, recovery.

Infrastructure only. It owns job state and nothing else:
 - it never picks a provider or model (it only knows roles and reason codes),
 - it never changes policy or permissions,
 - it never runs work itself (`run_next` hands a job to a caller-supplied handler).
Contract: docs/JOB_SUPERVISOR_CONTRACTS.md. Off unless config/job_supervisor.yaml sets `enabled: true`.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import time

import yaml

from ..jobs.failure_classes import classify, retry_rule
from ..jobs.slotplan import effective_priority
from ..jobs.rework_watch import ReworkWatch, failure_signature
from ..selfdev.development_contracts import candidate_contract
from ..models.model_loader import LoadError
from ..models.role_routing import REQUIREMENT_KEYS, RESOLUTION_CODES, check_independence
from ..selfdev.self_development import DevelopmentJobStore
from ..core.util import load_json, utcnow

WORKER_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
OP_ID = re.compile(r"[A-Za-z0-9_.:-]{1,80}")
FINAL_STATES = frozenset({"REJECTED", "ROLLED_BACK", "ACTIVATED", "CANCELLED", "DEAD"})
ACTIVE_STATES = frozenset({"BUILDING", "TESTING", "VERIFYING"})
SUPERVISOR_ENUMS_APPEND_ONLY = True  # readers treat unknown states as UNKNOWN and leave the job alone


class _ResourceDenied:
    """A refused reservation, shaped like a resolution error so the start path treats it the same way."""
    code = "hardware_pressure"

    def __init__(self, grant):
        self.reason = grant.get("reason")
        self.grant = grant


class _SlotRefused:
    """A model scheduler refusal (`SchedulerError`), shaped like a resolution error: `code` is a known reason, `reason` the scheduler's."""
    def __init__(self, error):
        self.code = error.code
        self.reason = error.reason


# Scheduler reasons that mean "not now" (D2.4, D2.12): the job goes back to the queue, no attempt is used up.
SLOT_WAIT_REASONS = ("server_startet", "model_swap_not_allowed", "drain", "exklusiv:", "gesperrt", "gpu_lease_busy:", "gpu_lease_deferred:")


class _LoadFailed:
    """A refused or failed model load, shaped like a resolution error. `code` is already a known failure reason."""
    def __init__(self, error):
        self.code = error.code
        self.reason = error.reason


class JobError(Exception):
    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


# --------------------------------------------------------------------------- configuration

class SupervisorConfig:
    """Validated settings. Invalid values refuse start; safety-relevant numbers are never clamped."""

    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("job_supervisor_config_invalid")
        self.raw = deepcopy(raw)
        self.enabled = raw.get("enabled", False)
        if not isinstance(self.enabled, bool):
            raise ValueError("job_supervisor_config_invalid:enabled")
        self.workers = self._int(raw, "workers", 1, 1, 8)  # Spec 2 (G2-S2-04): up to 8; more than 1 only with the model scheduler on
        self.claim_timeout_s = self._int(raw, "claim_timeout_s", 30, 1, 3600)
        self.lease_s = self._int(raw, "lease_s", 120, 2, 86400)
        self.max_lease_s = self._int(raw, "max_lease_s", 900, 2, 86400)
        self.heartbeat_interval_s = self._int(raw, "heartbeat_interval_s", 20, 1, 3600)
        self.suspect_after_s = self._int(raw, "suspect_after_s", 60, 1, 86400)
        self.grace_s = self._int(raw, "grace_s", 60, 0, 86400)
        self.stall_after_s = self._int(raw, "stall_after_s", 300, 1, 86400)
        self.reap_interval_s = self._int(raw, "reap_interval_s", 30, 1, 3600)
        if self.lease_s > self.max_lease_s:
            raise ValueError("job_supervisor_config_invalid:lease_s_exceeds_max_lease_s")
        if self.heartbeat_interval_s * 2 > self.lease_s:
            raise ValueError("job_supervisor_config_invalid:heartbeat_interval_too_long_for_lease")
        retry = raw.get("retry") or {}
        self.retry_limit = self._int(retry, "limit", 3, 0, 10)
        self.timeout_retry_limit = self._int(retry, "timeout_retry_limit", 2, 0, 10)
        self.backoff_base_s = self._int(retry, "backoff_base_s", 2, 0, 3600)
        self.backoff_max_s = self._int(retry, "backoff_max_s", 120, 0, 86400)
        crit = raw.get("critical") or {}
        self.critical_priority = self._int(crit, "min_priority", 8, 0, 9)
        self.critical_level = self._int(crit, "min_permission_level", 4, 0, 6)
        states = raw.get("dependency_satisfied_states") or ["READY_FOR_ACCEPTANCE", "ACTIVATION_PENDING", "ACTIVATED"]
        if not isinstance(states, list) or not states or any(s not in SupervisorJobStore.ALLOWED for s in states):
            raise ValueError("job_supervisor_config_invalid:dependency_satisfied_states")
        self.dependency_states = frozenset(states)
        roles = raw.get("roles")
        if not isinstance(roles, dict) or not roles:
            raise ValueError("job_supervisor_config_invalid:roles")
        self.roles = {}
        for name, spec in roles.items():
            if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", name) or not isinstance(spec, dict) \
                    or not isinstance(spec.get("mutates"), bool) or not isinstance(spec.get("capability"), str) or not spec["capability"]:
                raise ValueError(f"job_supervisor_config_invalid:role:{name}")
            independent = spec.get("independent_of", [])
            if not isinstance(independent, list) or any(not isinstance(x, str) for x in independent):
                raise ValueError(f"job_supervisor_config_invalid:role:{name}:independent_of")
            self.roles[name] = {"mutates": spec["mutates"], "capability": spec["capability"], "independent_of": list(independent)}
        for name, spec in self.roles.items():
            if set(spec["independent_of"]) - set(self.roles) or name in spec["independent_of"]:
                raise ValueError(f"job_supervisor_config_invalid:role:{name}:independent_of")

    @staticmethod
    def _int(section, key, default, low, high):
        value = section.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"job_supervisor_config_invalid:{key}")
        return value

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            raise ValueError("job_supervisor_config_missing")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(data.get("job_supervisor") or {})


# --------------------------------------------------------------------------- store

class SupervisorJobStore(DevelopmentJobStore):
    """DevelopmentJobStore plus the supervisor states. v1.20 transitions stay valid."""

    ALLOWED = {
        **{k: set(v) for k, v in DevelopmentJobStore.ALLOWED.items()},
    }
    ALLOWED["CREATED"] |= {"CANCELLED"}
    ALLOWED["PLANNING"] |= {"CANCELLED"}
    ALLOWED["READY"] |= {"QUEUED", "CANCELLED"}
    ALLOWED["QUEUED"] = {"BUILDING", "BLOCKED", "CANCELLED"}
    ALLOWED["BUILDING"] |= {"QUEUED", "DEAD", "CANCELLED"}
    ALLOWED["TESTING"] |= {"QUEUED", "DEAD", "CANCELLED"}
    ALLOWED["VERIFYING"] |= {"QUEUED", "DEAD", "CANCELLED"}
    ALLOWED["REWORK"] |= {"QUEUED", "BLOCKED", "DEAD", "CANCELLED"}
    ALLOWED["BLOCKED"] |= {"QUEUED", "CANCELLED", "REWORK"}
    ALLOWED["READY_FOR_ACCEPTANCE"] |= {"CANCELLED"}
    ALLOWED["ACTIVATION_PENDING"] |= {"CANCELLED"}
    ALLOWED["CANCELLED"] = set()
    ALLOWED["DEAD"] = set()

    def create_supervisor_job(self, contract, *, kind, requested_role, parent_job_id, depends_on, priority, permission_level, admission=None):
        job = {
            "schema": 1, "job_id": f"SDJ-{uuid.uuid4().hex[:12].upper()}", "parent_job_id": parent_job_id,
            "created_at": utcnow(), "state": "CREATED", "admission": deepcopy(admission), "contract": deepcopy(contract),
            "attempts": 0, "lease": None, "last_heartbeat": None, "last_progress": None,
            "candidate": None, "verification": None, "comparison": None, "activation": None, "checkpoint": None, "errors": [],
            "kind": kind, "depends_on": list(depends_on), "requested_role": requested_role, "selected_capability": None,
            "permission_level": permission_level, "policy_hash": None,
            "queue": {"enqueued_at": None, "priority": priority, "not_before": None},
            "worker": None, "heartbeat_seq": 0, "progress_seq": 0, "progress_marker": None, "attempt_log": [],
            "retry": {"count": 0, "timeout_count": 0, "next_not_before": None, "last_class": None, "awaiting_change": None,
                      "last_candidate_hash": None, "last_manifest_id": None, "exclude": [], "watch": [], "captain_hint": None},
            "cancel": None, "supervisor_flags": {"escalated_to": None, "dead": False, "rollback": None, "stalled": False},
            "last_error": None, "context_checkpoint_id": None, "ops": [],
        }
        self.save(job)
        return job

    def scan(self):
        """All readable jobs. A damaged file is copied to `_corrupt/` and skipped, never overwritten."""
        jobs, damaged = [], []
        for path in sorted(self.root.glob("SDJ-*.json")):
            try:
                value = load_json(path)
                if not isinstance(value, dict) or "job_id" not in value:
                    raise ValueError("not_a_job_record")
                jobs.append(value)
            except (ValueError, OSError):
                damaged.append(self._quarantine(path))
        return jobs, damaged

    def _quarantine(self, path):
        raw = path.read_bytes()
        tag = hashlib.sha256(raw).hexdigest()[:12]
        folder = self.root / "_corrupt"
        folder.mkdir(exist_ok=True)
        target = folder / f"{path.name}.{tag}.bak"
        if not target.exists():
            target.write_bytes(raw)
            keep = sorted(folder.glob(f"{path.name}.*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in keep[3:]:
                old.unlink(missing_ok=True)
        return {"file": path.name, "backup": target.name}


# --------------------------------------------------------------------------- pure state view

def supervisor_state(job):
    """Derived state (contract 4.1/4.2). Unknown stored states map to UNKNOWN and are left alone."""
    flags = job.get("supervisor_flags") or {}
    state = job.get("state")
    if state == "DEAD" or flags.get("dead"):
        return "DEAD"
    if state == "CANCELLED":
        return "CANCELLED"
    if flags.get("escalated_to") == "captain":
        return "ESCALATED_TO_CAPTAIN"
    if flags.get("escalated_to") == "guppi":
        return "ESCALATED_TO_GUPPI"
    if flags.get("rollback") == "pending":
        return "ROLLBACK_PENDING"
    if state == "ROLLED_BACK":
        return "ROLLED_BACK"
    if (job.get("approval") or {}).get("status") == "pending":
        return "WAITING_APPROVAL"                      # parked until the Captain decides
    if state == "VERIFYING" and flags.get("awaiting_verification") and not job.get("worker"):
        return "WAITING_VERIFICATION"                  # built and tested; parked (no worker, no reserved room) until an independent review is in
    worker = job.get("worker")
    if worker and worker.get("state") == "claimed":
        return "CLAIMED"
    if state == "QUEUED":
        return "QUEUED"
    return {"CREATED": "CREATED", "PLANNING": "PLANNING", "READY": "READY", "BUILDING": "RUNNING", "TESTING": "RUNNING",
            "VERIFYING": "VERIFYING", "REWORK": "RETRY_PENDING", "READY_FOR_ACCEPTANCE": "PASSED",
            "ACTIVATION_PENDING": "WAITING_APPROVAL", "ACTIVATED": "COMPLETED", "BLOCKED": "BLOCKED",
            "REJECTED": "FAILED"}.get(state, "UNKNOWN")


# --------------------------------------------------------------------------- supervisor

class JobSupervisor:
    def __init__(self, store, config, *, audit=None, guard=None, clock=None, monotonic=None,
                 health_check=None, pass_gate=None, rng=None, resolver=None, provider_report=None, permissions=None, scheduler=None):
        self.store = store
        self.config = config
        self.audit = audit
        self.guard = guard
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._mono = monotonic or time.monotonic
        self.health_check = health_check          # callable(worker_id) -> bool; missing means "not alive"
        self.pass_gate = pass_gate                # callable(job, verification) -> list of gaps; missing blocks PASSED
        self._rng = rng or random.Random()
        self._obs = {}                            # job_id -> observation (in memory, per process)
        # Both hooks belong to the Control Master. The supervisor only passes roles and reason codes through and never
        # looks inside a provider reference.
        self.resolver = resolver                  # callable(role, requirements, *, exclude, independent_of) -> resolution dict, may raise ResolutionError
        self.provider_report = provider_report    # callable(provider_ref, outcome, failure_class) -> None
        self.permissions = permissions            # PermissionGate (permission_levels.py); None means no action can be checked, so none is allowed
        self.scheduler = scheduler                # ResourceScheduler (resource_scheduler.py); None or disabled means nothing is reserved
        self.loader = None                        # ModelLoader (model_loader.py); None or disabled means the provider keeps its own context default
        self.slots = None                         # ModelScheduler (model_scheduler.py); None or disabled means one worker and a reservation per job
        self._slot_recipes = {}                   # role -> recipe of its last resolution, so claim can see a recipe swap early (OP-S2-05)

    # ---- helpers
    @property
    def enabled(self):
        return self.config.enabled

    def _require_enabled(self):
        if not self.config.enabled:
            raise JobError("supervisor_disabled")

    def _now(self):
        return self._clock()

    def _iso(self, moment):
        return moment.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _parse(value):
        return datetime.fromisoformat(value) if value else None

    def _audit(self, event, job, **extra):
        if not self.audit:
            return
        payload = {"job_id": job["job_id"], "parent_job_id": job.get("parent_job_id"), "rev": job.get("rev"),
                   "requested_role": job.get("requested_role"), "permission_level": job.get("permission_level")}
        payload.update({k: v for k, v in extra.items() if v is not None})
        self.audit.append(event, component="job-supervisor", payload=payload)

    @staticmethod
    def _worker_id(value):
        if not isinstance(value, str) or not WORKER_ID.fullmatch(value):
            raise JobError("invalid_worker_id")
        return value

    def _role_mutates(self, job):
        role = job.get("requested_role")
        spec = self.config.roles.get(role)
        return True if spec is None else spec["mutates"]   # unknown role: assume it can change things

    def _slots_on(self):
        return self.slots is not None and self.slots.enabled

    def _worker_limit(self):
        """`workers` jobs at a time. The runtime sets it to 1 while the model scheduler is off (D2.1: off is today's behaviour)."""
        return self.config.workers

    def _release(self, job_id):
        """Give the job's promised RAM/VRAM and its slot back. Called wherever an attempt ends; a failure here never touches the job."""
        if self._slots_on():
            try:
                self.slots.release(job_id, "fertig")
            except Exception as exc:
                if self.audit:
                    self.audit.append("JOB_SLOT_RELEASE_FAILED", component="job-supervisor", payload={"job_id": job_id, "error": type(exc).__name__})
        if self.scheduler is None:
            return
        try:
            self.scheduler.release_job(job_id)
        except Exception as exc:
            if self.audit:
                self.audit.append("JOB_RESOURCE_RELEASE_FAILED", component="job-supervisor", payload={"job_id": job_id, "error": type(exc).__name__})

    def _slot_requeue(self, job):
        """A claim that ended before its attempt started: the job's slot goes back to the queue (it keeps its place in line)."""
        if not self._slots_on():
            return
        try:
            self.slots.wait_for_job(job["job_id"], job["queue"]["priority"], agent_id=job.get("agent_id"), task_id=job.get("task_id"), enqueued=self._utc_text(job))
        except Exception as exc:
            if self.audit:
                self.audit.append("JOB_SLOT_RELEASE_FAILED", component="job-supervisor", payload={"job_id": job["job_id"], "error": type(exc).__name__})

    def _reap_slots(self, jobs):
        """Slot leases of jobs that can no longer ask (finished, cancelled, gone) end; waiting and running jobs keep theirs."""
        if not self._slots_on():
            return
        live = {j["job_id"] for j in jobs if j.get("worker") or (j.get("state") == "QUEUED" and not j.get("cancel"))}
        try:
            self.slots.reap(live)
        except Exception as exc:
            if self.audit:
                self.audit.append("JOB_SLOT_REAP_FAILED", component="job-supervisor", payload={"error": type(exc).__name__})

    @staticmethod
    def _utc_text(job_or_moment):
        """A job's arrival in the queue (or a moment) as the UTC text of the slot tables; None when unknown."""
        moment = job_or_moment
        if isinstance(moment, dict):
            moment = moment["queue"].get("enqueued_at")
            moment = datetime.fromisoformat(moment) if moment else None
        return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None

    def _claim_key(self, job, now):
        """Priority, then arrival, then id. With the model scheduler on, a waiting job ages one step every `age_after_s` (SCH-04)."""
        priority = job["queue"]["priority"]
        if self._slots_on() and job["queue"].get("enqueued_at"):
            priority = effective_priority({"priority": priority, "enqueued": self._utc_text(job)}, self._utc_text(now), self.slots.config.plan())
        return (-priority, job["queue"]["enqueued_at"] or "", job["job_id"])

    def _reconcile_resources(self, jobs):
        """Drop reservations of jobs that no longer have a running worker (the ledger follows state, not the clock)."""
        if self.scheduler is None:
            return
        try:
            self.scheduler.reconcile({j["job_id"] for j in jobs if (j.get("worker") or {}).get("state") == "running"})
        except Exception as exc:
            if self.audit:
                self.audit.append("JOB_RESOURCE_RECONCILE_FAILED", component="job-supervisor", payload={"error": type(exc).__name__})

    def _models_in_use(self):
        """Models that a running attempt is using right now; the loader must never evict these."""
        keys = set()
        for job in self.store.scan()[0]:
            if (job.get("worker") or {}).get("state") != "running":
                continue
            running = [a for a in job.get("attempt_log", []) if a.get("outcome") == "RUNNING"]
            for attempt in running[-1:]:
                keys.update(x for x in (attempt.get("model"), attempt.get("model_identifier")) if x)
        return keys

    def _report(self, attempt, outcome, failure_class=None):
        """Tell the Control Master how an attempt on its provider ended. Never lets a reporting problem touch the job."""
        ref = (attempt or {}).get("provider_ref")
        if self.provider_report is None or not ref:
            return
        try:
            self.provider_report(ref, outcome, failure_class)
        except Exception as exc:
            if self.audit:
                self.audit.append("JOB_PROVIDER_REPORT_FAILED", component="job-supervisor", payload={"error": type(exc).__name__})

    def _builder_keys(self, job):
        """Independence keys of the attempts that built what this job verifies; None marks an unknown identity."""
        spec = self.config.roles.get(job.get("requested_role")) or {}
        keys = []
        # A review job is a child of the job it reviews (that job is still VERIFYING, so it cannot be a dependency).
        for ref in list(job.get("depends_on", [])) + ([job["parent_job_id"]] if job.get("parent_job_id") else []):
            try:
                other = self.store.load(ref)
            except (KeyError, ValueError):
                continue
            if other.get("requested_role") in spec.get("independent_of", []):
                done = [a for a in other.get("attempt_log", []) if a.get("outcome") == "SUCCEEDED"] or other.get("attempt_log", [])
                keys.append(done[-1].get("independence_key") if done else None)
        return keys or [None]

    def _resolve(self, job):
        """Ask the Control Master for a provider. Returns (resolution, None) or (None, error with .code)."""
        spec = self.config.roles.get(job.get("requested_role")) or {}
        requirements = dict(job.get("role_requirements") or {})
        requirements.setdefault("permission_level", job.get("permission_level", 0))
        independent_of = self._builder_keys(job) if spec.get("independent_of") else []
        try:
            return self.resolver(job["requested_role"], requirements, exclude=list(job["retry"].get("exclude", [])), independent_of=independent_of), None
        except Exception as exc:
            if getattr(exc, "code", None) in RESOLUTION_CODES:
                return None, exc
            raise

    def _seen(self, job, operation_id, name):
        if operation_id is None:
            return False
        if not isinstance(operation_id, str) or not OP_ID.fullmatch(operation_id):
            raise JobError("invalid_operation_id")
        return any(o.get("id") == operation_id and o.get("op") == name for o in job.get("ops", []))

    @staticmethod
    def _remember(job, operation_id, name):
        if operation_id is None:
            return
        ops = job.setdefault("ops", [])
        ops.append({"id": operation_id, "op": name})
        del ops[:-64]

    def _set_state(self, job, state):
        """Transition inside an open `mutate` block; audits the v1.20 event and the supervisor event."""
        old = job["state"]
        self.store.transition(job, state)
        self._audit("JOB_STATE_CHANGED", job, **{"from": old, "to": state})

    def _load(self, job_id):
        try:
            return self.store.load(job_id)
        except KeyError as exc:
            raise JobError("unknown_job") from exc

    def _running_attempt(self, job):
        for attempt in reversed(job["attempt_log"]):
            if attempt["outcome"] == "RUNNING":
                return attempt
        return None

    def _own(self, job, worker_id, attempt_required=True):
        worker = job.get("worker")
        if not worker or worker.get("worker_id") != worker_id:
            raise JobError("lease_lost")
        if attempt_required and (worker.get("state") != "running" or not self._running_attempt(job)):
            raise JobError("lease_lost")
        return worker

    # ---- creation and queueing
    def create_job(self, contract, *, requested_role, kind="development", parent_job_id=None, depends_on=(),
                   priority=5, permission_level=None, ready=True, admission=None, requirements=None, scope_roots=None):
        self._require_enabled()
        if scope_roots is not None and (not isinstance(scope_roots, (list, tuple)) or any(not isinstance(r, (str, Path)) or not str(r) for r in scope_roots)):
            raise JobError("invalid_scope_roots")
        if requirements is not None and (not isinstance(requirements, dict) or set(requirements) - REQUIREMENT_KEYS):
            raise JobError("invalid_requirements", sorted(set(requirements or {}) - REQUIREMENT_KEYS) if isinstance(requirements, dict) else None)
        if not isinstance(contract, dict) or not isinstance(contract.get("contract_digest"), str):
            raise JobError("invalid_contract")
        unsigned = {k: v for k, v in contract.items() if k != "contract_digest"}
        from ..selfdev.development_contracts import canonical_digest
        if canonical_digest(unsigned) != contract["contract_digest"]:
            raise JobError("invalid_contract", "digest_mismatch")
        if requested_role not in self.config.roles:
            raise JobError("unknown_role", requested_role)
        if type(priority) is not int or not 0 <= priority <= 9:
            raise JobError("invalid_priority")
        level = contract.get("permission_level", 2) if permission_level is None else permission_level
        if type(level) is not int or not 0 <= level <= 6 or level > contract.get("permission_level", 6):
            raise JobError("invalid_permission_level")
        depends_on = list(depends_on)
        for ref in [parent_job_id] * (parent_job_id is not None) + depends_on:
            try:
                self.store.load(ref)
            except (KeyError, ValueError) as exc:
                raise JobError("unknown_parent" if ref == parent_job_id else "unknown_dependency", ref) from exc
        job = self.store.create_supervisor_job(contract, kind=kind, requested_role=requested_role, parent_job_id=parent_job_id,
                                               depends_on=depends_on, priority=priority, permission_level=level, admission=admission)
        job["selected_capability"] = self.config.roles[requested_role]["capability"]
        job["role_requirements"] = dict(requirements or {})
        job["scope"] = {"roots": [str(Path(r).resolve()) for r in (scope_roots or [])]}       # the job's development environment
        if self.permissions is not None:
            job["policy_hash"] = self.permissions.policy_hash()                                 # rules must not change under a running job
        job["retry"]["limit"] = self.config.retry_limit
        self.store.save(job)
        self._audit("JOB_CREATED", job, selected_capability=job["selected_capability"], kind=kind)
        if ready:
            with self.store.mutate(job["job_id"]) as live:
                self._set_state(live, "PLANNING")
                self._set_state(live, "READY")
            job = self._load(job["job_id"])
        return job

    def _dependencies_met(self, job, states):
        for ref in job.get("depends_on", []):
            try:
                if states.get(ref) not in self.config.dependency_states:
                    return False
            except KeyError:
                return False
        return True

    def enqueue(self, job_id, *, priority=None, not_before=None, operation_id=None):
        self._require_enabled()
        with self.store.mutate(job_id) as job:
            if "queue" not in job or "retry" not in job:      # a v1.20 development job: not ours to schedule
                raise JobError("not_a_supervisor_job")
            if self._seen(job, operation_id, "enqueue"):
                return {"status": "duplicate", "job": job}
            if job["state"] not in {"READY", "REWORK", "BLOCKED"}:
                raise JobError("not_ready", job["state"])
            if (job.get("approval") or {}).get("status") == "pending":
                raise JobError("approval_pending")
            if (job.get("supervisor_flags") or {}).get("escalated_to") == "captain":
                raise JobError("captain_resolution_required")
            if job["state"] == "BLOCKED" and (job.get("supervisor_flags") or {}).get("escalated_to"):
                raise JobError("escalation_must_be_resolved_first")
            if job["retry"].get("awaiting_change"):
                raise JobError("change_required", job["retry"]["awaiting_change"])
            states = {}
            for ref in job.get("depends_on", []):          # read only the jobs this one waits for, not the whole store
                try:
                    states[ref] = self.store.load(ref)["state"]
                except (KeyError, ValueError, OSError):
                    pass
            if not self._dependencies_met(job, states):
                raise JobError("dependency_unmet")
            if priority is not None:
                if type(priority) is not int or not 0 <= priority <= 9:
                    raise JobError("invalid_priority")
                job["queue"]["priority"] = priority
            floor = job["retry"].get("next_not_before")
            requested = self._iso(not_before) if isinstance(not_before, datetime) else not_before
            job["queue"]["not_before"] = max([x for x in (requested, floor) if x], default=None)
            job["queue"]["enqueued_at"] = self._iso(self._now())
            self._set_state(job, "QUEUED")
            self._remember(job, operation_id, "enqueue")
            self._audit("JOB_ENQUEUED", job, priority=job["queue"]["priority"], not_before=job["queue"]["not_before"])
        return {"status": "queued", "job": job}

    def supply_change(self, job_id, *, candidate_hash=None, context_manifest_id=None, input_digest=None):
        """The change a retry needs. Without it the identical request is never queued again."""
        self._require_enabled()
        refused = None
        with self.store.mutate(job_id) as job:
            need = job["retry"].get("awaiting_change")
            if not need:
                raise JobError("no_change_awaited")
            retry = job["retry"]
            if need == "candidate_hash":
                if not candidate_hash or candidate_hash == retry.get("last_candidate_hash"):
                    if candidate_hash:
                        # the old candidate again is no progress: the rework watch counts it (item C of the 2026-10-04 plan); it is
                        # recorded inside the block and the refusal is raised after it, because a raise inside would drop the record
                        self._stall_if_repeating(job, failure_signature("gen", "candidate_unchanged"))
                    refused = JobError("change_not_different", "candidate_hash")
                else:
                    retry["last_candidate_hash"] = candidate_hash
            elif need == "context_manifest":
                if not context_manifest_id or context_manifest_id == retry.get("last_manifest_id"):
                    raise JobError("change_not_different", "context_manifest")
                retry["last_manifest_id"] = context_manifest_id
            elif need == "input":
                if not input_digest or input_digest == retry.get("last_input_digest"):
                    raise JobError("change_not_different", "input")
                retry["last_input_digest"] = input_digest
            if refused is None:
                retry["awaiting_change"] = None
                self._audit("JOB_CHANGE_SUPPLIED", job, kind=need)
        if refused is not None:
            raise refused
        return job

    # ---- claim and run
    def claim(self, worker_id, roles, *, operation_id=None):
        self._require_enabled()
        self._worker_id(worker_id)
        if not isinstance(roles, (list, tuple, set)) or not roles or any(r not in self.config.roles for r in roles):
            raise JobError("invalid_roles")
        now = self._now()
        with self.store._lock():
            jobs, _ = self.store.scan()
            busy = [j for j in jobs if j.get("worker")]
            if len(busy) >= self._worker_limit():
                raise JobError("worker_busy")
            states = {j["job_id"]: j["state"] for j in jobs}
            ready = []
            for job in jobs:
                if job["state"] != "QUEUED" or job.get("worker") or job.get("cancel"):
                    continue
                if job.get("requested_role") not in roles:
                    continue
                not_before = self._parse(job["queue"].get("not_before"))
                if not_before and not_before > now:
                    continue
                if not self._dependencies_met(job, states):
                    continue
                ready.append(job)
            if not ready:
                raise JobError("no_job")
            ready.sort(key=lambda j: self._claim_key(j, now))
            chosen = ready[0]
            if self._slots_on():
                chosen = self._take_slot(ready)       # a job is claimed only with a slot; the others stay QUEUED and lose nothing
            with self.store.mutate(chosen["job_id"]) as job:
                job["worker"] = {"worker_id": worker_id, "claimed_at": self._iso(now), "lease_until": None,
                                 "grace_until": None, "state": "claimed"}
                self._audit("JOB_CLAIMED", job, worker_id=worker_id)
        return {"status": "claimed", "job": job}

    def _take_slot(self, ready):
        """The first job in line that gets a slot (D2.4). Every ready job stands in the slot queue first, so direct calls and jobs share one
        order. None gets one: `no_slot` with the scheduler's reason (`kein_slot`, `server_startet`, ...)."""
        reasons = []
        for job in ready:
            self.slots.wait_for_job(job["job_id"], job["queue"]["priority"], agent_id=job.get("agent_id"), task_id=job.get("task_id"), enqueued=self._utc_text(job))
        for job in ready:
            grant = self.slots.take_for_job(job["job_id"], job["queue"]["priority"], recipe=self._slot_recipes.get(job.get("requested_role")),
                                            agent_id=job.get("agent_id"), task_id=job.get("task_id"), enqueued=self._utc_text(job))
            if grant["granted"]:
                return job
            reasons.append(grant["reason"])
        raise JobError("no_slot", reasons[0] if reasons else None)

    def _unclaim(self, job_id, worker_id, reason):
        """The scheduler said "not now" after the claim (the server is starting, another recipe runs, a handover): the job goes back
        to the queue without an attempt, and its slot back to waiting."""
        ours = False
        with self.store.mutate(job_id) as job:
            worker = job.get("worker")
            if worker and worker["worker_id"] == worker_id and worker["state"] == "claimed":
                job["worker"] = None
                ours = True
                self._audit("JOB_SLOT_WAITING", job, worker_id=worker_id, reason_code=str(reason)[:100])
        if ours:                                  # a claim that is no longer ours must not take another worker's slot away
            self._slot_requeue(job)
        return {"status": "waiting", "reason": reason, "job": job}

    def confirm_start(self, job_id, worker_id, *, attempt_id=None):
        self._require_enabled()
        now = self._now()
        resolution = resolution_error = reservation = None
        snapshot = self._load(job_id)
        # A repair (job_repair.py) leaves a prepared attempt id, manifest and checkpoint; the next attempt takes them over.
        planned_attempt = attempt_id or snapshot.get("pending_attempt_id") or f"ATT-{uuid.uuid4().hex[:12].upper()}"
        if self.resolver is not None:     # outside the store lock: the Control Master may take a moment
            resolution, resolution_error = self._resolve(snapshot)
            if self._slots_on():
                return self._confirm_with_slot(job_id, worker_id, now, planned_attempt, snapshot, resolution, resolution_error)
            if (resolution_error is not None and resolution_error.code == "hardware_pressure" and self.loader is not None and self.loader.enabled
                    and self.loader.evict_idle(self._models_in_use())):
                # Idle models held the room. They are gone now: look at the card again and resolve once more.
                if self.scheduler is not None:
                    self.scheduler.refresh()
                resolution, resolution_error = self._resolve(snapshot)
        if resolution is not None and resolution_error is None and self.loader is not None and self.loader.enabled:
            try:
                self.loader.clear_stale(resolution)   # before the reservation, so the room it holds counts as free again
            except LoadError as exc:
                resolution_error = _LoadFailed(exc)
        if resolution is not None and resolution_error is None and self.scheduler is not None and self.scheduler.enabled:
            # Room is promised before anything starts. A refusal is "not now", handled like any other resolution failure.
            extra = {}
            resident = self.loader.resident_vram_gb(resolution) if self.loader is not None and self.loader.enabled else 0.0
            if resident > 0:
                extra["resident_vram_gb"] = resident     # the instance already on the card is not a second copy to fit
            grant = self.scheduler.reserve(job_id, planned_attempt, resolution["estimated_resources"],
                                           exclusive=bool((snapshot.get("role_requirements") or {}).get("exclusive")), **extra)
            if grant["status"] == "DENIED":
                resolution_error = _ResourceDenied(grant)
            else:
                reservation = grant["reservation"]
        if resolution is not None and resolution_error is None and self.loader is not None and self.loader.enabled:
            # The reserved room is only real once the provider holds the model with the window that was resolved.
            try:
                resolution = dict(resolution, load=self.loader.ensure(resolution))
            except LoadError as exc:
                resolution_error = _LoadFailed(exc)
                if reservation is not None:
                    self._release(job_id)             # nothing was loaded, so nothing stays promised
                    reservation = None
        try:
            return self._start_attempt(job_id, worker_id, now, planned_attempt, resolution, resolution_error, reservation)
        except Exception:
            self._release(job_id)             # the start failed (claim lost or expired): give the promised room back
            raise

    def _confirm_with_slot(self, job_id, worker_id, now, planned_attempt, snapshot, resolution, resolution_error):
        """The start of a job that holds a slot (D2.4): the server has the one reservation, so the job reserves nothing and loads
        nothing itself; `ensure_server` reuses the running server or starts it (this job is then the starter)."""
        from .model_scheduler import SchedulerError
        if resolution is not None and resolution_error is None:
            self._slot_recipes[snapshot.get("requested_role")] = resolution.get("capability_id")
            try:
                out = self.slots.ensure_server(resolution, run_id=job_id)
                resolution = dict(resolution, load=out["load"])
            except SchedulerError as exc:
                if str(exc.reason).startswith(SLOT_WAIT_REASONS):
                    return self._unclaim(job_id, worker_id, exc.reason)
                resolution_error = _SlotRefused(exc)
        try:
            return self._start_attempt(job_id, worker_id, now, planned_attempt, resolution, resolution_error, None)
        except Exception:
            self._release(job_id)
            raise

    def _start_attempt(self, job_id, worker_id, now, planned_attempt, resolution, resolution_error, reservation):
        with self.store.mutate(job_id) as job:
            worker = job.get("worker")
            if not worker or worker["worker_id"] != worker_id or worker["state"] != "claimed":
                raise JobError("not_claimed")
            if self._parse(worker["claimed_at"]) + timedelta(seconds=self.config.claim_timeout_s) < now:
                raise JobError("claim_expired")
            job.pop("pending_attempt_id", None)
            attempt = {"attempt_id": planned_attempt, "reservation_id": reservation["reservation_id"] if reservation else None,
                       "started_at": self._iso(now), "ended_at": None,
                       "worker_id": worker_id, "role": job["requested_role"],
                       "capability": resolution["capability_id"] if resolution else job["selected_capability"],
                       # A start that was refused never ran on the provider, so the provider is neither blamed nor excluded for it.
                       "provider_ref": resolution["provider_ref"] if resolution and resolution_error is None else None,
                       "refused_provider_ref": resolution["provider_ref"] if resolution and resolution_error is not None else None,
                       "outcome": "RUNNING", "failure_class": None,
                       "reason_code": None, "retry_decision": None, "context_manifest_id": job.get("context_manifest_id"),
                       "context_checkpoint_id": job.get("context_checkpoint_id"), "usage": None,
                       "independence_key": resolution["independence_key"] if resolution else None,
                       "resolved_context_window": resolution["context_window"] if resolution else None,
                       # What the worker must call, and the window the provider really applied (None: not enforced by GUPPI).
                       "model": resolution["model"] if resolution else None,
                       "model_identifier": (resolution.get("load") or {}).get("identifier", resolution["model"]) if resolution else None,
                       "loaded_context": (resolution.get("load") or {}).get("context_length") if resolution else None}
            job["attempt_log"].append(attempt)
            job["attempts"] = int(job.get("attempts", 0)) + 1
            worker.update(state="running", lease_until=self._iso(now + timedelta(seconds=self.config.lease_s)), grace_until=None)
            job["progress_seq"] += 1
            self._set_state(job, "BUILDING")
            self._audit("JOB_STARTED", job, attempt_id=attempt["attempt_id"], worker_id=worker_id)
            if resolution_error is not None:
                # No provider could be chosen. Nothing ran, so the failure is known and nothing is in doubt.
                code = resolution_error.code
                decision = self._apply_failure(job, classify(code), reason_code=code,
                                               message=f"start refused: {code}" + (f" ({resolution_error.reason})" if getattr(resolution_error, "reason", None) else ""),
                                               mutated=False, outcome_known=True, outcome="FAILED")
                return {"status": "resolution_failed", "code": code, "decision": decision, "job": job}
        self._obs[job_id] = self._observe(job)
        return {"status": "running", "job": job, "attempt_id": attempt["attempt_id"]}

    def heartbeat(self, job_id, worker_id, *, lease_extend_s=None):
        self._require_enabled()
        now = self._now()
        extend = self.config.lease_s if lease_extend_s is None else lease_extend_s
        if type(extend) is not int or extend < 1:
            raise JobError("invalid_lease_extension")
        extend = min(extend, self.config.max_lease_s)
        with self.store.mutate(job_id) as job:
            worker = self._own(job, worker_id)
            job["heartbeat_seq"] += 1
            job["last_heartbeat"] = self._iso(now)
            worker["lease_until"] = self._iso(now + timedelta(seconds=extend))
            worker["grace_until"] = None
            cancel_requested = job.get("cancel") is not None
        if self._slots_on():
            try:
                self.slots.beat(job_id)            # the slot lease lives as long as the run beats (D2.4)
            except Exception as exc:
                if self.audit:
                    self.audit.append("JOB_SLOT_BEAT_FAILED", component="job-supervisor", payload={"job_id": job_id, "error": type(exc).__name__})
        return {"status": "ok", "cancel_requested": cancel_requested, "heartbeat_seq": job["heartbeat_seq"]}

    def report_progress(self, job_id, worker_id, marker):
        """Progress counts only when the step marker changes; a heartbeat alone is not progress."""
        self._require_enabled()
        if not isinstance(marker, str) or not marker or len(marker) > 200:
            raise JobError("invalid_progress_marker")
        with self.store.mutate(job_id) as job:
            self._own(job, worker_id)
            changed = marker != job.get("progress_marker")
            if changed:
                job["progress_marker"] = marker
                job["progress_seq"] += 1
                job["last_progress"] = self._iso(self._now())
        return {"status": "progress" if changed else "no_change", "progress_seq": job["progress_seq"]}

    def complete_step(self, job_id, worker_id, next_state, *, operation_id=None):
        """BUILDING -> TESTING -> VERIFYING. PASSED is only reachable through `mark_passed`."""
        self._require_enabled()
        if next_state not in {"TESTING", "VERIFYING"}:
            raise JobError("invalid_transition", next_state)
        with self.store.mutate(job_id) as job:
            if self._seen(job, operation_id, f"complete:{next_state}"):
                return {"status": "duplicate", "job": job}
            self._own(job, worker_id)
            if next_state not in self.store.ALLOWED.get(job["state"], set()):
                raise JobError("invalid_transition", f"{job['state']}->{next_state}")
            self._set_state(job, next_state)
            job["progress_seq"] += 1
            self._remember(job, operation_id, f"complete:{next_state}")
        return {"status": next_state, "job": job}

    def mark_passed(self, job_id, worker_id, verification):
        """VERIFYING -> READY_FOR_ACCEPTANCE. Needs a verification PASS and the evidence gate to agree."""
        self._require_enabled()
        if self.pass_gate is None:
            raise JobError("verification_gate_unavailable")
        if not isinstance(verification, dict) or verification.get("result") != "PASS" or not verification.get("verification_digest"):
            raise JobError("passing_verification_required")
        with self.store.mutate(job_id) as job:
            worker = self._own(job, worker_id)
            if job["state"] != "VERIFYING":
                raise JobError("invalid_transition", f"{job['state']}->READY_FOR_ACCEPTANCE")
            gaps = list(self.pass_gate(job, verification) or [])
            if gaps:
                raise JobError("verification_gate_failed", gaps)
            attempt = self._running_attempt(job)
            if (self.config.roles.get(job["requested_role"]) or {}).get("independent_of"):
                # A verifier must be provably independent of whoever built the candidate. Unknown is not independent.
                statuses = [check_independence(builder, attempt.get("independence_key")) for builder in self._builder_keys(job)]
                if any(s != "INDEPENDENT" for s in statuses):
                    raise JobError("verification_inconclusive", {"independence": statuses})
            job["verification"] = deepcopy(verification)
            attempt.update(outcome="SUCCEEDED", ended_at=self._iso(self._now()))
            self._release(job_id)
            self._report(attempt, "success")
            job["worker"] = None
            self._set_state(job, "READY_FOR_ACCEPTANCE")
        return {"status": "PASSED", "job": job}

    # ---- candidate, review and acceptance (Phase 8d)
    def bind_candidate(self, job_id, worker_id, *, stage, parent_version, candidate_hash, changed_files=None, rollback_point=None):
        """Pin what this job built: a content hash the evidence must refer to. Only the worker that holds the job may do it."""
        self._require_enabled()
        with self.store.mutate(job_id) as job:
            self._own(job, worker_id)
            if job["state"] != "BUILDING":
                raise JobError("invalid_transition", f"{job['state']}:bind_candidate")
            attempt = self._running_attempt(job)
            job["candidate"] = candidate_contract(development_contract_record=job["contract"], attempt_id=attempt["attempt_id"], stage=stage,
                                                  parent_version=parent_version, changed_files=changed_files, candidate_hash=candidate_hash,
                                                  status="BUILDING", rollback_point=rollback_point, builder=job["requested_role"])
            job["progress_seq"] += 1
            self._audit("JOB_CANDIDATE_BOUND", job, candidate_id=job["candidate"]["candidate_id"], candidate_hash=candidate_hash)
        return job["candidate"]

    def park_for_verification(self, job_id, worker_id, *, allow_without_candidate=False):
        """The build is done and tested (VERIFYING). Give the worker and the reserved room back while the independent review runs.
        The build attempt ends SUCCEEDED; nothing is promoted: only `accept_verification` can move the job on.

        `allow_without_candidate` (the worker's own clean-up): a job without a bound candidate is parked too, flagged
        `no_candidate`; the evidence gate can never pass it, but it no longer holds the worker until its lease runs out."""
        self._require_enabled()
        with self.store.mutate(job_id) as job:
            self._own(job, worker_id)
            if job["state"] != "VERIFYING" or not (job.get("candidate") or allow_without_candidate):
                raise JobError("invalid_transition", f"{job['state']}:park_for_verification")
            if not job.get("candidate"):
                job["supervisor_flags"]["no_candidate"] = True
            attempt = self._running_attempt(job)
            attempt.update(outcome="SUCCEEDED", ended_at=self._iso(self._now()))
            self._release(job_id)
            self._report(attempt, "success")
            job["worker"] = None
            job["supervisor_flags"]["awaiting_verification"] = True
            job["progress_seq"] += 1
            self._audit("JOB_PARKED_FOR_VERIFICATION", job, attempt_id=attempt["attempt_id"])
        return {"status": "WAITING_VERIFICATION", "job": job}

    def complete_review(self, job_id, worker_id):
        """A review job (kind=review) is finished: its output is an assessment, not a claim, so it has no gate of its own.
        Its attempt ends SUCCEEDED and the job becomes READY_FOR_ACCEPTANCE; the reviewed job's gate decides what it is worth."""
        self._require_enabled()
        with self.store.mutate(job_id) as job:
            self._own(job, worker_id)
            if job.get("kind") != "review":
                raise JobError("not_a_review_job")
            if job["state"] == "BUILDING":
                self._set_state(job, "TESTING")
            if job["state"] == "TESTING":
                self._set_state(job, "VERIFYING")
            if job["state"] != "VERIFYING":
                raise JobError("invalid_transition", f"{job['state']}:complete_review")
            attempt = self._running_attempt(job)
            attempt.update(outcome="SUCCEEDED", ended_at=self._iso(self._now()))
            self._release(job_id)
            self._report(attempt, "success")
            job["worker"] = None
            self._set_state(job, "READY_FOR_ACCEPTANCE")
        return {"status": "REVIEWED", "job": job}

    def accept_verification(self, job_id, verification):
        """A parked job gets its verdict. The gate must agree; if it does not, the job stays parked and the gaps are the answer."""
        self._require_enabled()
        if self.pass_gate is None:
            raise JobError("verification_gate_unavailable")
        with self.store.mutate(job_id) as job:
            if job["state"] != "VERIFYING" or not job["supervisor_flags"].get("awaiting_verification"):
                raise JobError("invalid_transition", f"{job['state']}:accept_verification")
            gaps = list(self.pass_gate(job, verification) or [])
            if gaps:
                self._audit("JOB_VERIFICATION_REFUSED", job, gaps=gaps[:20])
                raise JobError("verification_gate_failed", gaps)
            job["verification"] = deepcopy(verification)
            job["supervisor_flags"]["awaiting_verification"] = False
            self._set_state(job, "READY_FOR_ACCEPTANCE")
        return {"status": "PASSED", "job": job}

    def reject_verification(self, job_id, *, findings):
        """The review found the candidate wanting. The job goes to rework and waits for a DIFFERENT candidate."""
        self._require_enabled()
        with self.store.mutate(job_id) as job:
            if job["state"] != "VERIFYING" or not job["supervisor_flags"].get("awaiting_verification"):
                raise JobError("invalid_transition", f"{job['state']}:reject_verification")
            job["supervisor_flags"]["awaiting_verification"] = False
            job["retry"]["awaiting_change"] = "candidate_hash"
            job["retry"]["last_candidate_hash"] = (job.get("candidate") or {}).get("candidate_hash")
            job["last_error"] = {"class": "deterministic_test_failure", "reason_code": "verification_failed",
                                 "message": "; ".join(str(f) for f in list(findings)[:5])[:500], "at": self._iso(self._now())}
            if not self._stall_if_repeating(job, failure_signature("review")):
                self._set_state(job, "REWORK")
            self._audit("JOB_VERIFICATION_REJECTED", job)
        return {"status": job["state"], "job": job}      # REWORK, or BLOCKED when the rework watch stalled the job

    # ---- failure handling
    def decide(self, job, failure_class, *, mutated, outcome_known):
        """Retry decision (contract 7). Pure: reads the job, changes nothing."""
        rule = retry_rule(failure_class)
        retry = job["retry"]
        if mutated and not outcome_known:
            return {"action": "DEAD", "escalate_to": "guppi", "reason": "unknown_outcome_of_mutating_attempt"}
        if rule["escalate"]:
            return {"action": "ESCALATE", "escalate_to": "captain" if failure_class == "policy_denied" else "guppi", "reason": failure_class}
        if retry["count"] > retry["limit"]:
            return {"action": "ESCALATE", "escalate_to": "guppi", "reason": "retry_limit_reached"}
        backoff = min(self.config.backoff_base_s * (2 ** max(retry["count"] - 1, 0)), self.config.backoff_max_s)
        backoff = backoff * (0.8 + 0.4 * self._rng.random())
        if failure_class == "transient_provider_error":
            return {"action": "RETRY", "backoff_s": backoff}
        if failure_class == "timeout":
            if retry["timeout_count"] <= self.config.timeout_retry_limit:
                return {"action": "RETRY", "backoff_s": backoff}
            return {"action": "FALLBACK", "backoff_s": backoff, "reason": "timeout_retries_exhausted"}
        if failure_class == "context_overflow":
            return {"action": "AWAIT_CHANGE", "need": "context_manifest"}
        if failure_class == "context_quality_degraded":
            return {"action": "AWAIT_CHANGE", "need": "context_manifest"}
        if failure_class == "validation_failure":
            return {"action": "AWAIT_CHANGE", "need": "input"}
        if failure_class == "deterministic_test_failure":
            return {"action": "AWAIT_CHANGE", "need": "candidate_hash"}
        if rule["fallback_allowed"]:   # rate_limit, runtime_crash, model_unavailable, hardware_pressure
            return {"action": "FALLBACK", "backoff_s": backoff, "reason": failure_class}
        return {"action": "ESCALATE", "escalate_to": "guppi", "reason": failure_class}

    def _end_attempt(self, job, outcome, failure_class=None, reason_code=None, decision=None):
        attempt = self._running_attempt(job)
        if attempt:
            attempt.update(outcome=outcome, ended_at=self._iso(self._now()), failure_class=failure_class,
                           reason_code=reason_code, retry_decision=decision)
        self._release(job["job_id"])              # the attempt is over: its promised RAM/VRAM is free again
        return attempt

    def _apply_failure(self, job, failure_class, *, reason_code, message, mutated, outcome_known, outcome):
        """Inside an open `mutate` block. Records the failure and moves the job per the decision."""
        retry = job["retry"]
        retry["count"] += 1
        retry["last_class"] = failure_class
        if failure_class == "timeout":
            retry["timeout_count"] += 1
        decision = self.decide(job, failure_class, mutated=mutated, outcome_known=outcome_known)
        attempt = self._running_attempt(job)
        if attempt and attempt.get("provider_ref") and decision["action"] == "FALLBACK":
            if attempt["provider_ref"] not in retry.setdefault("exclude", []):
                retry["exclude"].append(attempt["provider_ref"])
        self._report(attempt, "failure", failure_class)
        job["last_error"] = {"class": failure_class, "reason_code": reason_code, "message": (message or "")[:500], "at": self._iso(self._now())}
        self._end_attempt(job, outcome, failure_class, reason_code,
                          {k: v for k, v in decision.items() if k != "reason"} | {"reason": decision.get("reason")})
        job["worker"] = None
        flags = job["supervisor_flags"]
        action = decision["action"]
        self._audit("JOB_FAILED", job, failure_class=failure_class, reason_code=reason_code, attempt_id=attempt and attempt["attempt_id"])
        if action == "DEAD":
            flags["dead"] = True
            flags["escalated_to"] = decision["escalate_to"]
            self._set_state(job, "DEAD")
            self._audit("JOB_ESCALATED", job, failure_class=failure_class, reason_code=decision["reason"])
        elif action == "ESCALATE":
            flags["escalated_to"] = decision["escalate_to"]
            self._set_state(job, "BLOCKED")
            self._audit("JOB_ESCALATED", job, failure_class=failure_class, reason_code=decision["reason"])
        elif action == "AWAIT_CHANGE":
            retry["awaiting_change"] = decision["need"]
            if failure_class == "deterministic_test_failure":
                retry["last_candidate_hash"] = (job.get("candidate") or {}).get("candidate_hash")
            signature = failure_signature("test", message or "") if failure_class == "deterministic_test_failure"                 else failure_signature("gen", reason_code or failure_class)
            # A context repair (need context_manifest) is a real change of the next attempt and has its own limit (repair max_per_job, then
            # escalation to guppi), so it is not a repeat of the same call: only the other kinds of awaited change go through the watch.
            if decision["need"] == "context_manifest" or not self._stall_if_repeating(job, signature):
                self._set_state(job, "REWORK")
                self._audit("JOB_RETRY_SCHEDULED", job, failure_class=failure_class, kind=f"await_change:{decision['need']}")
        else:  # RETRY or FALLBACK: the changed element is the delay and, for FALLBACK, the excluded provider
            retry["next_not_before"] = self._iso(self._now() + timedelta(seconds=decision["backoff_s"]))
            self._set_state(job, "REWORK")
            if action == "FALLBACK":
                self._audit("JOB_FALLBACK_DECIDED", job, failure_class=failure_class, reason_code=decision.get("reason"))
            self._audit("JOB_RETRY_SCHEDULED", job, failure_class=failure_class, kind=action.lower())
            self._queue_again(job)
        return decision

    def _stall_if_repeating(self, job, signature):
        """Inside an open `mutate` block. Records how a rework attempt ended (a failure signature) and asks the rework watch whether the
        next attempt would only repeat it (same failure 3 times, or two failures alternating 4 times; plan 2026-10-04). If so the job
        goes to the Captain (BLOCKED, escalated_to captain, reason `rework_stalled`) instead of REWORK; `give_hint` resolves it. The watch
        advises; it never cancels the job."""
        retry = job["retry"]
        watch = ReworkWatch(retry.get("watch"))
        watch.record(signature, retry.get("captain_hint"))
        retry["watch"] = list(watch.entries)
        verdict = watch.check(retry.get("captain_hint"))
        if not verdict["stuck"]:
            return False
        job["supervisor_flags"]["escalated_to"] = "captain"
        job["last_error"] = {"class": (job.get("last_error") or {}).get("class", "unknown_failure"), "reason_code": "rework_stalled",
                             "message": verdict["message"][:500], "at": self._iso(self._now())}
        self._set_state(job, "BLOCKED")
        self._audit("JOB_REWORK_STALLED", job, detector=verdict["detector"], count=verdict["count"], failure=verdict["repeated_failure"])
        self._audit("JOB_ESCALATED", job, reason_code="rework_stalled", escalated_to="captain")
        return True

    def give_hint(self, job_id, text, *, resolved_by):
        """The Captain's answer to a stalled rework: a hint for the next attempt. A new hint changes the rework call, so the watch lets
        the next attempt run; the job returns to REWORK and still needs a different candidate (`supply_change`) before it is queued."""
        self._require_enabled()
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise JobError("invalid_hint")
        with self.store.mutate(job_id) as job:
            flags = job["supervisor_flags"]
            if job["state"] != "BLOCKED" or flags.get("escalated_to") != "captain" or (job.get("last_error") or {}).get("reason_code") != "rework_stalled":
                raise JobError("no_stalled_rework", job["state"])
            if text.strip() == (job["retry"].get("captain_hint") or ""):
                raise JobError("hint_not_new")
            job["retry"]["captain_hint"] = text.strip()
            flags["escalated_to"] = None
            self._set_state(job, "REWORK")
            self._audit("JOB_HINT_GIVEN", job, reason_code=str(resolved_by)[:100], kind="rework_stalled")
        return job

    def _queue_again(self, job):
        job["queue"]["not_before"] = job["retry"]["next_not_before"]
        job["queue"]["enqueued_at"] = self._iso(self._now())
        self._set_state(job, "QUEUED")

    def fail(self, job_id, worker_id, *, reason_code=None, exception=None, message=None, mutated=None, outcome_known=True):
        self._require_enabled()
        failure_class = classify(reason_code, exception=exception, message=message)
        with self.store.mutate(job_id) as job:
            self._own(job, worker_id)
            was_mutating = self._role_mutates(job) if mutated is None else bool(mutated)
            decision = self._apply_failure(job, failure_class, reason_code=reason_code, message=message or (str(exception) if exception else None),
                                           mutated=was_mutating, outcome_known=outcome_known, outcome="FAILED" if outcome_known else "UNKNOWN")
        return {"status": "failed", "failure_class": failure_class, "decision": decision, "job": job}

    def role_mutates(self, job):
        """Public form of the role rule: may an attempt of this job have changed something?"""
        return self._role_mutates(job)

    def escalate(self, job_id, *, to, reason):
        """Hand a job that cannot continue to GUPPI or the Captain. BLOCKED stays resolvable only at that level."""
        self._require_enabled()
        if to not in {"guppi", "captain"}:
            raise JobError("invalid_escalation_target")
        with self.store.mutate(job_id) as job:
            if job["state"] in FINAL_STATES:
                raise JobError("already_final", job["state"])
            if job["state"] != "BLOCKED":
                if "BLOCKED" not in self.store.ALLOWED.get(job["state"], set()):
                    raise JobError("invalid_transition", f"{job['state']}->BLOCKED")
                self._set_state(job, "BLOCKED")
            job["supervisor_flags"]["escalated_to"] = to
            job["last_error"] = {"class": (job.get("last_error") or {}).get("class", "unknown_failure"), "reason_code": str(reason)[:200],
                                 "message": "escalated", "at": self._iso(self._now())}
            self._audit("JOB_ESCALATED", job, reason_code=str(reason)[:200], escalated_to=to)
        return job

    # ---- permissions and approvals (Phase 6)
    def _gate(self):
        if self.permissions is None:
            raise JobError("permission_gate_unavailable")     # no gate, no action: fail closed
        return self.permissions

    def check_action(self, job_id, worker_id, action, target, *, token=None):
        """May this job do `action` on `target`? A denial fails the job as `policy_denied` (Captain escalation).

        The answer is the permission gate's, which asks the Guard last. ALLOWED means "go ahead and let the executor
        call the Guard", APPROVAL_REQUIRED means "call request_approval".
        """
        self._require_enabled()
        gate = self._gate()
        with self.store.mutate(job_id) as job:
            self._own(job, worker_id)
            result = gate.check(job, action, target, token=token)
            if result["status"] == "DENIED":
                decision = self._apply_failure(job, "policy_denied", reason_code=result["reason"], message=f"action {action} denied: {result['reason']}",
                                               mutated=False, outcome_known=True, outcome="FAILED")
                return {**result, "job_failed": True, "decision": decision, "job": job}
        return {**result, "job_failed": False, "job": job}

    def request_approval(self, job_id, worker_id, action, target):
        """Park the job until the Captain decides. Not a failure: the retry counter does not move and no provider is blamed."""
        self._require_enabled()
        gate = self._gate()
        with self.store.mutate(job_id) as job:
            self._own(job, worker_id)
            result = gate.check(job, action, target)
            if result["status"] != "APPROVAL_REQUIRED":
                raise JobError("approval_not_required", {"status": result["status"], "reason": result["reason"]})
            binding = gate.binding(job, action, target)
            captain_gate = self.guard.create_gate(job_id, action, str(target), risks=[f"level {result['level']} action requested by a job"],
                                                  rollback_available=bool(job["contract"].get("rollback_required")), request_binding=binding)
            attempt = self._running_attempt(job)
            attempt.update(outcome="SUSPENDED", ended_at=self._iso(self._now()), reason_code="awaiting_approval")
            self._release(job_id)                       # a parked job holds no hardware while the Captain decides
            job["worker"] = None
            job["approval"] = {"status": "pending", "gate": captain_gate, "gate_id": captain_gate["gate_id"], "action": action,
                               "target": str(target), "binding": binding, "requested_at": self._iso(self._now()), "attempt_id": attempt["attempt_id"]}
            self._set_state(job, "BLOCKED")
            self._audit("JOB_APPROVAL_REQUESTED", job, attempt_id=attempt["attempt_id"], action=action, gate_id=captain_gate["gate_id"])
        return {"status": "approval_requested", "gate": captain_gate, "job": job}

    def resolve_approval(self, job_id, token):
        """The Captain approved: check the token is real and still fits this job, then queue the job again."""
        self._require_enabled()
        gate = self._gate()
        with self.store.mutate(job_id) as job:
            approval = job.get("approval") or {}
            if approval.get("status") != "pending":
                raise JobError("no_approval_pending")
            if gate.binding(job, approval["action"], approval["target"]) != approval["binding"]:
                raise JobError("approval_stale", "job_contract_or_policy_changed_since_the_request")
            checked = self.guard.check_token(token, mission_id=job_id, action=approval["action"], target=approval["target"], request_binding=approval["binding"])
            if not checked["authorized"]:
                raise JobError("approval_invalid", checked["reason"])
            approval.update(status="granted", resolved_at=self._iso(self._now()), token=deepcopy(token))
            job["retry"]["next_not_before"] = None
            self._audit("JOB_APPROVAL_RESOLVED", job, action=approval["action"], decision="granted", token_id=token.get("token_id"))
            self._queue_again(job)
        return job

    def deny_approval(self, job_id, *, decided_by, reason):
        """The Captain said no: the job ends, cancelled. Nothing is retried around the refusal."""
        self._require_enabled()
        with self.store.mutate(job_id) as job:
            approval = job.get("approval") or {}
            if approval.get("status") != "pending":
                raise JobError("no_approval_pending")
            approval.update(status="denied", resolved_at=self._iso(self._now()), reason=str(reason)[:300])
            self._audit("JOB_APPROVAL_RESOLVED", job, action=approval["action"], decision="denied")
            job["cancel"] = {"requested_at": self._iso(self._now()), "requested_by": str(decided_by)[:100], "reason": "approval_denied"}
            self._finish_cancel(job)
        return job

    def consume_approval(self, job_id, worker_id):
        """Hand the granted token to the worker that now runs the job, once. The executor spends it at the Guard."""
        self._require_enabled()
        with self.store.mutate(job_id) as job:
            self._own(job, worker_id)
            approval = job.get("approval") or {}
            if approval.get("status") != "granted" or "token" not in approval:
                raise JobError("no_granted_approval")
            token = approval.pop("token")
            approval.update(status="handed_over", handed_over_at=self._iso(self._now()))
        return {"token": token, "action": approval["action"], "target": approval["target"]}

    def lower_permission_level(self, job_id, level):
        """A job's level can go down, never up. More rights mean a new job under a new contract."""
        self._require_enabled()
        if type(level) is not int or not 0 <= level <= 6:
            raise JobError("invalid_permission_level")
        with self.store.mutate(job_id) as job:
            if job["state"] in FINAL_STATES:
                raise JobError("already_final", job["state"])
            if level > job["permission_level"]:
                raise JobError("permission_cannot_be_raised")
            if level < job["permission_level"]:
                self._audit("JOB_PERMISSION_LOWERED", job, **{"from": job["permission_level"], "to": level})
                job["permission_level"] = level
        return job

    # ---- cancel
    def cancel(self, job_id, *, requested_by, reason, operation_id=None):
        self._require_enabled()
        with self.store.mutate(job_id) as job:
            if self._seen(job, operation_id, "cancel"):
                return {"status": "duplicate", "job": job}
            if job["state"] in FINAL_STATES:
                raise JobError("already_final", job["state"])
            if job.get("cancel") is None:
                job["cancel"] = {"requested_at": self._iso(self._now()), "requested_by": str(requested_by)[:100], "reason": str(reason)[:300]}
                self._audit("JOB_CANCEL_REQUESTED", job)
            running = job.get("worker") and job["worker"].get("state") == "running"
            if not running:
                self._finish_cancel(job)
            self._remember(job, operation_id, "cancel")
        return {"status": "cancelled" if job["state"] == "CANCELLED" else "cancel_requested", "job": job}

    def _finish_cancel(self, job):
        if (job.get("approval") or {}).get("status") == "pending":
            job["approval"]["status"] = "cancelled"
        attempt = self._running_attempt(job)
        if attempt:
            self._end_attempt(job, "ABANDONED", None, "cancelled")
        job["worker"] = None
        self._set_state(job, "CANCELLED")
        self._audit("JOB_CANCELLED", job)

    def acknowledge_cancel(self, job_id, worker_id):
        self._require_enabled()
        with self.store.mutate(job_id) as job:
            self._own(job, worker_id)
            if job.get("cancel") is None:
                raise JobError("no_cancel_requested")
            self._finish_cancel(job)
        return {"status": "cancelled", "job": job}

    # ---- reaper
    def _observe(self, job):
        return {"hb": job.get("heartbeat_seq", 0), "hb_t": self._mono(), "pg": job.get("progress_seq", 0), "pg_t": self._mono(), "suspect": False}

    def reap(self):
        """Lease, grace and stall checks. Safe against wall-clock jumps: expiry needs a stale heartbeat_seq too."""
        self._require_enabled()
        now, mono = self._now(), self._mono()
        events = []
        jobs, damaged = self.store.scan()
        for item in damaged:
            events.append({"event": "JOB_CORRUPT_RECORD", **item})
            if self.audit:
                self.audit.append("JOB_CORRUPT_RECORD", component="job-supervisor", payload=item)
        for snapshot in jobs:
            worker = snapshot.get("worker")
            if not worker or snapshot["state"] in FINAL_STATES:
                self._obs.pop(snapshot["job_id"], None)
                continue
            job_id = snapshot["job_id"]
            if worker["state"] == "claimed":
                if self._parse(worker["claimed_at"]) + timedelta(seconds=self.config.claim_timeout_s) < now:
                    expired = False
                    with self.store.mutate(job_id) as job:
                        if job.get("worker") and job["worker"]["state"] == "claimed":
                            job["worker"] = None
                            expired = True
                            self._audit("JOB_CLAIM_EXPIRED", job)
                            events.append({"event": "JOB_CLAIM_EXPIRED", "job_id": job_id})
                    if expired:
                        self._slot_requeue(job)
                continue
            obs = self._obs.get(job_id)
            if obs is None:
                obs = self._obs[job_id] = self._observe(snapshot)
            if snapshot["heartbeat_seq"] != obs["hb"]:
                obs.update(hb=snapshot["heartbeat_seq"], hb_t=mono, suspect=False)
            if snapshot["progress_seq"] != obs["pg"]:
                obs.update(pg=snapshot["progress_seq"], pg_t=mono)
            expired = self._parse(worker.get("lease_until")) is not None and now > self._parse(worker["lease_until"])
            stale = mono - obs["hb_t"] >= self.config.suspect_after_s
            if expired and stale:
                events += self._handle_expired(job_id, obs, now)
            elif snapshot["heartbeat_seq"] > 0 and mono - obs["pg_t"] >= self.config.stall_after_s and not snapshot["supervisor_flags"].get("stalled"):
                events += self._handle_stall(job_id)
        if self.scheduler is not None or self._slots_on():
            after = self.store.scan()[0]
            if self.scheduler is not None:
                self._reconcile_resources(after)     # after the reaping above, so abandoned jobs free their room too
            self._reap_slots(after)
        return events

    def _handle_expired(self, job_id, obs, now):
        events = []
        with self.store.mutate(job_id) as job:
            worker = job.get("worker")
            if not worker or worker["state"] != "running":
                return events
            if not obs["suspect"]:
                obs["suspect"] = True
                self._audit("JOB_LEASE_SUSPECT", job, worker_id=worker["worker_id"])
                alive = False
                if self.health_check:
                    try:
                        alive = bool(self.health_check(worker["worker_id"]))
                    except Exception:
                        alive = False
                if alive:
                    worker["lease_until"] = self._iso(now + timedelta(seconds=self.config.grace_s or self.config.lease_s))
                    obs.update(suspect=False, hb_t=self._mono())
                    self._audit("JOB_LEASE_GRACE", job, worker_id=worker["worker_id"])
                    events.append({"event": "JOB_LEASE_GRACE", "job_id": job_id})
                else:
                    worker["grace_until"] = self._iso(now + timedelta(seconds=self.config.grace_s))
                    events.append({"event": "JOB_LEASE_SUSPECT", "job_id": job_id})
                return events
            if self._parse(worker.get("grace_until")) and now <= self._parse(worker["grace_until"]):
                return events
            self._audit("JOB_LEASE_EXPIRED", job, worker_id=worker["worker_id"])
            if job.get("cancel") is not None:
                self._finish_cancel(job)
                events.append({"event": "JOB_CANCELLED", "job_id": job_id})
            else:
                self._abandon(job, reason="lease_expired")
                events.append({"event": "JOB_ABANDONED", "job_id": job_id})
        self._obs.pop(job_id, None)
        return events

    def _handle_stall(self, job_id):
        with self.store.mutate(job_id) as job:
            if not job.get("worker") or job["worker"]["state"] != "running":
                return []
            job["supervisor_flags"]["stalled"] = True
            self._audit("JOB_STALLED", job, worker_id=job["worker"]["worker_id"])
            self._apply_failure(job, "context_quality_degraded", reason_code="progress_stalled", message="heartbeats without progress",
                                mutated=self._role_mutates(job), outcome_known=False, outcome="UNKNOWN")
            job["supervisor_flags"]["stalled"] = False
        self._obs.pop(job_id, None)
        return [{"event": "JOB_STALLED", "job_id": job_id}]

    def _abandon(self, job, *, reason):
        mutates = self._role_mutates(job)
        critical = job["queue"]["priority"] >= self.config.critical_priority or job["permission_level"] >= self.config.critical_level
        attempt = self._running_attempt(job)
        self._audit("JOB_ABANDONED", job, attempt_id=attempt and attempt["attempt_id"], reason_code=reason)
        if not mutates:
            self._report(attempt, "failure", "timeout")     # mutating jobs report through _apply_failure below
        if critical and not mutates:
            # Critical but read-only: do not replay silently, hand it to GUPPI.
            self._end_attempt(job, "UNKNOWN", None, reason)
            job["worker"] = None
            job["supervisor_flags"]["escalated_to"] = "guppi"
            self._set_state(job, "BLOCKED")
            self._audit("JOB_ESCALATED", job, reason_code="critical_job_abandoned")
            return
        if mutates:
            self._apply_failure(job, "runtime_crash", reason_code=reason, message="worker lost; outcome unknown",
                                mutated=True, outcome_known=False, outcome="UNKNOWN")
            return
        self._end_attempt(job, "ABANDONED", None, reason)
        job["worker"] = None
        job["queue"]["not_before"] = None
        job["queue"]["enqueued_at"] = self._iso(self._now())
        self._set_state(job, "QUEUED")

    # ---- recovery
    def startup_recovery(self):
        """Run once at start. Fixes what a crashed process left behind (contract 6.3)."""
        self._require_enabled()
        self._obs.clear()
        report = {"claims_released": [], "abandoned": [], "dead": [], "cancel_finished": [], "corrupt": []}
        jobs, damaged = self.store.scan()
        report["corrupt"] = damaged
        for item in damaged:
            if self.audit:
                self.audit.append("JOB_CORRUPT_RECORD", component="job-supervisor", payload=item)
        if self.audit:
            self.audit.append("JOB_RECOVERY_STARTED", component="job-supervisor", payload={"jobs": len(jobs)})
        for snapshot in jobs:
            job_id, worker = snapshot["job_id"], snapshot.get("worker")
            if snapshot["state"] in FINAL_STATES:
                continue
            if worker is None and snapshot.get("cancel") is not None:
                with self.store.mutate(job_id) as job:
                    self._finish_cancel(job)
                report["cancel_finished"].append(job_id)
                continue
            if worker is None:
                continue
            with self.store.mutate(job_id) as job:
                worker = job["worker"]
                if worker["state"] == "claimed":
                    job["worker"] = None
                    report["claims_released"].append(job_id)
                    self._slot_requeue(job)
                    continue
                if job.get("cancel") is not None:
                    self._finish_cancel(job)
                    report["cancel_finished"].append(job_id)
                    continue
                self._abandon(job, reason="process_restart")
                (report["dead"] if job["state"] == "DEAD" else report["abandoned"]).append(job_id)
        after = self.store.scan()[0]
        self._reconcile_resources(after)         # whatever the crashed process had promised is gone with it
        self._reap_slots(after)
        if self.audit:
            self.audit.append("JOB_RECOVERY_FINISHED", component="job-supervisor", payload={k: len(v) for k, v in report.items()})
        return report

    def resume(self, job_id, *, resolved_by):
        """GUPPI-level escalation resolved: BLOCKED -> QUEUED. Captain escalations cannot be resumed here."""
        self._require_enabled()
        with self.store.mutate(job_id) as job:
            flags = job["supervisor_flags"]
            if job["state"] != "BLOCKED":
                raise JobError("not_blocked", job["state"])
            if (job.get("approval") or {}).get("status") == "pending":
                raise JobError("approval_pending")
            if flags.get("escalated_to") == "captain":
                raise JobError("captain_resolution_required")
            if job["retry"].get("awaiting_change"):
                raise JobError("change_required", job["retry"]["awaiting_change"])
            flags["escalated_to"] = None
            job["last_error"] = job.get("last_error")
            self._audit("JOB_RECOVERED", job, kind="resume", reason_code=str(resolved_by)[:100])
            self._queue_again(job)
        return job

    def recover(self, job_id, resolution, *, approval_token=None):
        """Captain-gated resolution of an unknown outcome. `abort` closes the escalation; replay of mutating work is refused."""
        self._require_enabled()
        if resolution not in {"abort", "retry_readonly"}:
            raise JobError("unsupported_recovery_resolution")
        job = self._load(job_id)
        unknown = any(a["outcome"] == "UNKNOWN" for a in job["attempt_log"])
        if not unknown or job["state"] not in {"DEAD", "BLOCKED"}:
            raise JobError("no_unknown_outcome_to_recover")
        if resolution == "retry_readonly" and (self._role_mutates(job) or job["state"] == "DEAD"):
            raise JobError("mutating_job_cannot_be_replayed")
        if self.guard is None:
            raise JobError("guard_unavailable")
        target = f"recovery:{job_id}"
        binding = {"job_id": job_id, "rev": job["rev"], "resolution": resolution, "attempts": job["attempts"]}
        verdict = self.guard.evaluate("execution_recovery", mission_id=job_id, target=target)
        if verdict["decision"] == "BLOCK":
            return {"status": "blocked", "guard": verdict}
        auth = self.guard.authorize(approval_token, mission_id=job_id, action="execution_recovery", target=target, request_binding=binding) \
            if approval_token else {"authorized": False}
        if not auth["authorized"]:
            gate = self.guard.create_gate(job_id, "execution_recovery", target, request_binding=binding)
            return {"status": "captain_required", "gate": gate, "binding": binding}
        with self.store.mutate(job_id) as live:
            if live["rev"] != binding["rev"]:
                raise JobError("stale_job_record")
            live["supervisor_flags"]["escalated_to"] = None
            live.setdefault("decisions", []).append({"type": "execution_recovery", "resolution": resolution, "at": utcnow()})
            self._audit("JOB_RECOVERED", live, kind=resolution)
            if resolution == "retry_readonly":
                self._queue_again(live)
            elif live["state"] == "BLOCKED":   # abort closes a blocked job; a DEAD job is already final
                live["cancel"] = {"requested_at": self._iso(self._now()), "requested_by": "recovery", "reason": "aborted_after_unknown_outcome"}
                self._finish_cancel(live)
        return {"status": "completed", "job": self._load(job_id)}

    # ---- views
    def view(self):
        jobs, damaged = self.store.scan()
        counts = {}
        for job in jobs:
            name = supervisor_state(job)
            counts[name] = counts.get(name, 0) + 1
        return {"schema": 1, "enabled": self.config.enabled, "workers": self._worker_limit(), "counts": counts,
                "corrupt_records": len(damaged),
                "jobs": [{"job_id": j["job_id"], "state": j["state"], "supervisor_state": supervisor_state(j), "role": j.get("requested_role"),
                          "priority": (j.get("queue") or {}).get("priority"), "attempts": j.get("attempts"), "kind": j.get("kind")}
                         for j in jobs[-50:]]}

    # ---- helper that runs one job through a caller-supplied handler (used by tests and the first golden path)
    def run_next(self, worker_id, roles, handler):
        """Claim, start, call `handler(job, ctx)`, then fail or step forward. The handler does the actual work."""
        try:
            claimed = self.claim(worker_id, roles)
        except JobError as exc:
            if exc.code in {"no_job", "no_slot"}:
                return {"status": "idle"}
            raise
        job_id = claimed["job"]["job_id"]
        started = self.confirm_start(job_id, worker_id)
        if started["status"] == "waiting":
            return {"status": "waiting", "reason": started["reason"]}
        ctx = WorkerContext(self, job_id, worker_id)
        try:
            result = handler(started["job"], ctx)
        except Exception as exc:
            return self.fail(job_id, worker_id, exception=exc, mutated=ctx.mutated or None)
        if ctx.cancel_seen:
            return self.acknowledge_cancel(job_id, worker_id)
        return {"status": "handled", "result": result, "job": self._load(job_id)}


class WorkerContext:
    """What a handler may do while it holds a job: stay alive, report progress, flag that it changed something."""

    def __init__(self, supervisor, job_id, worker_id):
        self.supervisor, self.job_id, self.worker_id = supervisor, job_id, worker_id
        self.mutated = False
        self.cancel_seen = False

    def heartbeat(self):
        out = self.supervisor.heartbeat(self.job_id, self.worker_id)
        self.cancel_seen = self.cancel_seen or out["cancel_requested"]
        return out

    def progress(self, marker):
        return self.supervisor.report_progress(self.job_id, self.worker_id, marker)

    def mark_mutated(self):
        self.mutated = True
