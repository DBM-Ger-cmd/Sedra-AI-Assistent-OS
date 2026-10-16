"""Controlled self-development foundation for GUPPI OS v1.20.

This module intentionally orchestrates contracts and state only. It does not grant
new permissions, bypass the Guard, mutate stable code, or install tools.
"""
from __future__ import annotations

import re
import uuid
from copy import deepcopy
from pathlib import Path
import yaml

from ..development_contracts import development_contract, context_manifest, candidate_contract, verification_contract
from contextlib import contextmanager
from ..failure_classes import classify as classify_failure_structured
from ..util import atomic_write_json, load_json, utcnow, append_lock


from ..evolution_targets import CORE_TARGETS, MODULE_TARGETS, classify_target  # re-exported: single source of truth


class CapabilityAdmissionGate:
    """Prove a capability gap before new development is admitted."""
    def __init__(self, registry, audit=None):
        self.registry = registry
        self.audit = audit

    def _known_capabilities(self):
        known = set()
        sources = {}
        for owner, caps in self.registry.capabilities().items():
            for cap in caps or []:
                if isinstance(cap, str):
                    known.add(cap); sources.setdefault(cap, []).append(owner)
        return known, sources

    def evaluate(self, requested_capability, *, evidence, target_type="skill", checked=None,
                 requires_new_tool=False, new_tool_rationale=None):
        if not isinstance(requested_capability, str) or not requested_capability.strip() or len(requested_capability) > 200:
            raise ValueError("invalid_requested_capability")
        if not isinstance(evidence, list) or not evidence or len(evidence) > 64:
            raise ValueError("capability_gap_evidence_required")
        if any(not isinstance(x, dict) or not x for x in evidence):
            raise ValueError("invalid_capability_gap_evidence")
        checked = checked or {}
        required_checks = {"skills", "tools", "modules"}
        if set(k for k, v in checked.items() if v) < required_checks:
            return self._decision("BLOCK", requested_capability, target_type, evidence, checked, reason="existing_capability_checks_incomplete")
        known, sources = self._known_capabilities()
        if requested_capability in known:
            return self._decision("REUSE_EXISTING", requested_capability, target_type, evidence, checked, reason="capability_already_registered", existing_sources=sources.get(requested_capability, []))
        if requires_new_tool and (not isinstance(new_tool_rationale, str) or len(new_tool_rationale.strip()) < 12):
            return self._decision("BLOCK", requested_capability, target_type, evidence, checked, reason="new_tool_requires_explicit_rationale")
        classification = classify_target(target_type)
        return self._decision("ADMIT", requested_capability, target_type, evidence, checked, reason="gap_supported_by_evidence", classification=classification, new_tool_allowed=bool(requires_new_tool))

    def _decision(self, status, capability, target_type, evidence, checked, **extra):
        out = {"schema": 1, "admission_id": f"ADM-{uuid.uuid4().hex[:12].upper()}", "created_at": utcnow(), "status": status,
               "requested_capability": capability, "target_type": target_type, "evidence": deepcopy(evidence), "checked": deepcopy(checked), **extra}
        if self.audit:
            self.audit.append("CAPABILITY_ADMISSION_DECIDED", component="self-development", payload={"admission_id": out["admission_id"], "status": status, "capability": capability, "reason": out.get("reason")})
        return out


class EvolutionPolicy:
    DEFAULT = {
        "E1": {"may_plan": True, "may_build": True, "may_test": True, "may_verify": True, "may_activate": False, "captain_gate": False},
        "E2": {"may_plan": True, "may_build": True, "may_test": True, "may_verify": True, "may_activate": False, "captain_gate": True},
        "E3": {"may_plan": True, "may_build": True, "may_test": True, "may_verify": True, "may_activate": False, "captain_gate": True},
    }
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else None
        self.config = {k: dict(v) for k, v in self.DEFAULT.items()}
        self.feature_flags = {"auto_develop_e1": False, "auto_activate_e1": False}
        if self.config_path and self.config_path.exists():
            data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
            root = data.get("self_development", data)
            for level, values in (root.get("policy") or {}).items():
                if level in self.config and isinstance(values, dict): self.config[level].update(values)
            self.feature_flags.update(root.get("feature_flags") or {})
        # Immutable core protection even if config is edited incorrectly.
        self.config["E3"]["may_activate"] = False

    def for_level(self, level):
        if level not in self.config: raise ValueError("invalid_evolution_level")
        out = deepcopy(self.config[level])
        if level == "E1" and self.feature_flags.get("auto_activate_e1"):
            out["may_activate"] = True
        if level == "E3": out["may_activate"] = False
        return out


class DevelopmentJobStore:
    ALLOWED = {
        "CREATED": {"PLANNING", "BLOCKED", "REJECTED"},
        "PLANNING": {"READY", "BLOCKED", "REJECTED"},
        "READY": {"BUILDING", "BLOCKED", "REJECTED"},
        "BUILDING": {"TESTING", "REWORK", "BLOCKED", "REJECTED"},
        "TESTING": {"VERIFYING", "REWORK", "BLOCKED", "REJECTED"},
        "VERIFYING": {"READY_FOR_ACCEPTANCE", "REWORK", "BLOCKED", "REJECTED"},
        "REWORK": {"BUILDING", "REJECTED"},
        "READY_FOR_ACCEPTANCE": {"ACTIVATION_PENDING", "REJECTED"},
        "ACTIVATION_PENDING": {"ACTIVATED", "REJECTED", "ROLLED_BACK"},
        "ACTIVATED": {"ROLLED_BACK"},
        "BLOCKED": {"PLANNING", "REJECTED"},
        "REJECTED": set(), "ROLLED_BACK": set(),
    }
    def __init__(self, root: Path, audit=None):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True); self.audit = audit
    def path(self, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r"SDJ-[A-F0-9]{12}", job_id): raise ValueError("invalid_development_job_id")
        return self.root / f"{job_id}.json"
    def create(self, admission, contract, *, parent_job_id=None):
        job = {"schema": 1, "job_id": f"SDJ-{uuid.uuid4().hex[:12].upper()}", "parent_job_id": parent_job_id,
               "created_at": utcnow(), "state": "CREATED", "admission": deepcopy(admission), "contract": deepcopy(contract),
               "attempts": 0, "lease": None, "last_heartbeat": None, "last_progress": None,
               "candidate": None, "verification": None, "comparison": None, "activation": None, "checkpoint": None, "errors": []}
        atomic_write_json(self.path(job["job_id"]), job)
        if self.audit:self.audit.append("SELF_DEVELOPMENT_JOB_CREATED", component="self-development", payload={"job_id": job["job_id"], "classification": contract["classification"]})
        return job
    def load(self, job_id):
        value = load_json(self.path(job_id))
        if value is None: raise KeyError(job_id)
        return value
    def _lock(self):
        # One lock for the whole store: jobs are few and writes are short.
        return append_lock(self.root / "store")
    def save(self, job):
        """Write a job. Refuses to overwrite a newer record (lost-update protection).

        `rev` counts writes. Records written by v1.20 have no `rev` and count as 0.
        """
        with self._lock():
            path = self.path(job["job_id"])
            current = load_json(path)
            if current is not None and int(current.get("rev", 0)) != int(job.get("rev", 0)):
                raise ValueError("stale_job_record")
            job["rev"] = int(job.get("rev", 0)) + 1
            atomic_write_json(path, job)
    @contextmanager
    def mutate(self, job_id):
        """Load the job under the store lock, yield it, and save it if the block succeeds and changed something.

        A block that changes nothing (for example an idempotent repeat) writes nothing and leaves `rev` alone.
        """
        with self._lock():
            job = self.load(job_id)
            yield job
            if load_json(self.path(job_id)) != job:
                self.save(job)
    def transition(self, job, state, *, progress=None):
        old = job["state"]; old_progress = job["last_progress"]
        if state not in self.ALLOWED.get(old, set()): raise ValueError(f"invalid_development_transition:{old}->{state}")
        job["state"] = state; job["last_progress"] = progress or utcnow()
        try: self.save(job)
        except Exception:
            job["state"] = old; job["last_progress"] = old_progress; raise
        if self.audit:self.audit.append("SELF_DEVELOPMENT_STATE_CHANGED", component="self-development", payload={"job_id": job["job_id"], "from": old, "to": state})
        return job
    def heartbeat(self, job, worker_id, lease_until=None, marker=None):
        # Heartbeats come from workers holding possibly stale copies: re-read, set only heartbeat fields, refresh caller's copy.
        with self.mutate(job["job_id"]) as fresh:
            fresh["last_heartbeat"] = utcnow(); fresh["lease"] = {"worker_id": worker_id, "lease_until": lease_until, "marker": marker}
        job.clear(); job.update(fresh); return job
    def list(self):
        return [load_json(p) for p in sorted(self.root.glob("SDJ-*.json"))]


class BaselineCandidateComparator:
    def compare(self, baseline, candidate):
        if not isinstance(baseline, dict) or not isinstance(candidate, dict): raise ValueError("comparison_records_required")
        btests, ctests = baseline.get("tests", {}), candidate.get("tests", {})
        if not isinstance(btests, dict) or not isinstance(ctests, dict): raise ValueError("test_maps_required")
        if set(btests) != set(ctests): return {"status": "INCONCLUSIVE", "reason": "test_inventory_changed"}
        improved = []; regressed = []; unchanged = []
        for test_id in sorted(btests):
            b, c = btests[test_id], ctests[test_id]
            if b == c: unchanged.append(test_id)
            elif b in {"FAIL", "BLOCKED"} and c == "PASS": improved.append(test_id)
            elif b == "PASS" and c != "PASS": regressed.append(test_id)
            else: unchanged.append(test_id)
        status = "REGRESSED" if regressed else "IMPROVED" if improved else "UNCHANGED"
        return {"status": status, "improved": improved, "regressed": regressed, "unchanged": unchanged}


class SelfDevelopmentManager:
    def __init__(self, registry, data_root: Path, *, audit=None, knowledge=None, context_budget=None, kev=None, config_path=None, evidence_store=None):
        self.audit = audit; self.knowledge = knowledge; self.context_budget = context_budget; self.kev = kev
        self.evidence_store = evidence_store
        self.independence_check = None      # callable(builder_role, verifier_role) -> INDEPENDENT | SAME | UNVERIFIABLE; None keeps the v1.20 name check
        self.admission = CapabilityAdmissionGate(registry, audit)
        self.policy = EvolutionPolicy(config_path)
        self.data_root = Path(data_root)
        self.jobs = DevelopmentJobStore(self.data_root / "self_development" / "jobs", audit)
        self.learning_path = self.data_root / "self_development" / "capability_learning.json"
        self.comparator = BaselineCandidateComparator()

    def start(self, requested_capability, *, evidence, target_type="skill", objective=None, checked=None,
              acceptance_criteria=None, verification_plan=None, context_window=None,
              requires_new_tool=False, new_tool_rationale=None, source_gap_id=None, budget=None):
        """`budget` (from the Context Manager's resolver) wins over `context_window`. Without either, the budget uses the
        8192 fallback and says so in `budget_source`, so nobody mistakes a guess for a measured window."""
        admission = self.admission.evaluate(requested_capability, evidence=evidence, target_type=target_type,
                                            checked=checked or {"skills": True, "tools": True, "modules": True},
                                            requires_new_tool=requires_new_tool, new_tool_rationale=new_tool_rationale)
        if admission["status"] != "ADMIT": return {"status": admission["status"], "admission": admission, "job": None}
        level = admission["classification"]; policy = self.policy.for_level(level)
        if not policy["may_plan"]: return {"status": "BLOCK", "admission": admission, "job": None, "reason": "policy_denies_planning"}
        contract = development_contract(objective=objective or f"Develop capability: {requested_capability}", classification=level,
                                        scope={"requested_capability": requested_capability, "target_type": target_type},
                                        permission_level=2 if level == "E1" else 3,
                                        acceptance_criteria=acceptance_criteria or [{"type": "capability_smoke_test", "capability": requested_capability}],
                                        verification_plan=verification_plan or [{"type": "deterministic_tests"}, {"type": "independent_review"}],
                                        rollback_required=True, captain_gate_required=policy["captain_gate"], source_gap_id=source_gap_id)
        job = self.jobs.create(admission, contract)
        self.jobs.transition(job, "PLANNING")
        if budget is not None:
            if not isinstance(budget, dict) or int(budget.get("max_input_tokens", 0) or 0) <= 0: raise ValueError("valid_context_budget_required")
            budget = deepcopy(budget)
        else:
            window, source = (8192, "default") if context_window is None else (int(context_window), "caller")
            budget = self.context_budget.build_budget(window) if self.context_budget else {"max_input_tokens": window}
            budget["budget_source"] = source
        job["context_manifest"] = context_manifest(goal=contract["objective"], current_task="Plan the minimal candidate change", budget=budget,
                                                    constraints=contract["forbidden_actions"], acceptance_criteria=contract["acceptance_criteria"],
                                                    permissions={"max_level": contract["permission_level"]}, parent_job_id=job["job_id"])
        self.jobs.save(job)
        return {"status": "ADMITTED", "admission": admission, "job": job}

    def bind_candidate(self, job_id, *, attempt_id, stage, parent_version, changed_files=None, candidate_hash=None, rollback_point=None, builder="coder",
                       builder_key=None):
        """`builder_key` is the independence key of the model that really wrote the candidate (role routing's resolution at
        that moment). Recorded next to the contract so verification compares who acted, not who would be chosen later."""
        with self.jobs.mutate(job_id) as job:
            if job["state"] not in {"READY", "BUILDING", "REWORK"}: raise ValueError("development_job_not_ready_for_candidate")
            record = candidate_contract(development_contract_record=job["contract"], attempt_id=attempt_id, stage=stage, parent_version=parent_version,
                                        changed_files=changed_files, candidate_hash=candidate_hash, status="BUILDING", rollback_point=rollback_point, builder=builder)
            # Only after the contract is valid (a refused bind leaves the state). REWORK -> BUILDING too: a reworked candidate is a new
            # build (before 2026-10-02 the job stayed on REWORK and the next verification failed with REWORK->REWORK).
            if job["state"] in {"READY", "REWORK"}: self.jobs.transition(job, "BUILDING")
            job["attempts"] = int(job.get("attempts",0)) + 1
            job["candidate"] = record
            job["candidate_builder_key"] = builder_key if isinstance(builder_key, str) and builder_key else None
        return record

    def _pass_evidence_gaps(self, job, evidence_refs):
        """Why a claimed PASS is not backed by evidence. Empty list means the PASS may stand.

        A PASS needs at least one referenced record in the hash-chained evidence store that is
        deterministic, reports status PASS, and belongs to this job and candidate. A referenced
        deterministic record that reports anything else vetoes the PASS. Model assessments
        (e.g. Kev) are recorded but never sufficient on their own.
        """
        if self.evidence_store is None: return ["evidence_store_unavailable"]
        if not self.evidence_store.verify_chain(): return ["evidence_chain_invalid"]
        refs = set(evidence_refs or [])
        if not refs: return ["deterministic_test_evidence_required"]
        candidate_id = (job.get("candidate") or {}).get("candidate_id")
        records = {r["evidence_id"]: r for r in self.evidence_store.list(job["job_id"])}
        passing, vetoes, ignored = 0, [], []
        for ref in sorted(refs):
            record = records.get(ref)
            if record is None: ignored.append(f"evidence_not_found_for_job:{ref}"); continue
            if record.get("candidate_id") != candidate_id: ignored.append(f"evidence_not_bound_to_candidate:{ref}"); continue
            if record.get("trust_level") != "deterministic": ignored.append(f"evidence_not_deterministic:{ref}"); continue
            if (record.get("payload") or {}).get("status") == "PASS": passing += 1
            else: vetoes.append(f"deterministic_evidence_not_passing:{ref}")
        if vetoes: return vetoes
        if passing == 0: return ignored + ["deterministic_test_evidence_required"]
        return []

    def attach_verification(self, job_id, *, verifier, result, evidence_refs=None, confidence=None, findings=None, verifier_key=None):
        """`verifier_key`: independence key of the model that really reviewed. With the builder's key recorded at bind time the
        two actual identities are compared. Without both, the role check stands: who would each role resolve to now (which can
        be UNVERIFIABLE under hardware pressure, e.g. right after a model was unloaded; seen 2026-10-02)."""
        with self.jobs.mutate(job_id) as job:
            if not job.get("candidate"): raise ValueError("candidate_required_before_verification")
            if verifier == job["candidate"].get("builder"): raise ValueError("independent_verifier_required")
            if result == "PASS":
                gaps = self._pass_evidence_gaps(job, evidence_refs)
                if gaps:  # an unsupported PASS is downgraded, never accepted
                    result = "INCONCLUSIVE"; findings = list(findings or []) + [f"pass_downgraded:{g}" for g in gaps][:64]
            builder_key = job.get("candidate_builder_key")
            actual = isinstance(verifier_key, str) and verifier_key and builder_key
            if result == "PASS" and (actual or self.independence_check is not None):
                # Builder and verifier must be provably different models: the recorded actual identities when both are known,
                # otherwise (role routing on) the roles' current resolution.
                if actual:
                    status = "SAME" if builder_key == verifier_key else "INDEPENDENT"
                    job["verification_identities"] = {"builder_key": builder_key, "verifier_key": verifier_key}
                else:
                    status = self.independence_check(job["candidate"].get("builder"), verifier)
                if status != "INDEPENDENT":
                    result = "INCONCLUSIVE"; findings = list(findings or []) + [f"pass_downgraded:independence_{str(status).lower()}"]
            if job["state"] == "BUILDING": self.jobs.transition(job, "TESTING")
            if job["state"] == "TESTING": self.jobs.transition(job, "VERIFYING")
            record = verification_contract(candidate_contract_record=job["candidate"], verifier=verifier, evidence_refs=evidence_refs,
                                           result=result, confidence=confidence, findings=findings)
            job["verification"] = record; self.jobs.save(job)
            if result == "PASS": self.jobs.transition(job, "READY_FOR_ACCEPTANCE")
            elif result == "FAIL": self.jobs.transition(job, "REWORK")
            else: self.jobs.transition(job, "BLOCKED")
        return record

    def compare(self, job_id, baseline, candidate):
        with self.jobs.mutate(job_id) as job:
            result = self.comparator.compare(baseline, candidate); job["comparison"] = result
        return result

    def activation_decision(self, job_id, *, captain_approved=False):
        job = self.jobs.load(job_id); level = job["contract"]["classification"]; policy = self.policy.for_level(level)
        if job["state"] != "READY_FOR_ACCEPTANCE": return {"status": "BLOCK", "reason": "candidate_not_ready"}
        if not job.get("verification") or job["verification"].get("result") != "PASS": return {"status": "BLOCK", "reason": "passing_verification_required"}
        if (job.get("comparison") or {}).get("status") == "REGRESSED": return {"status": "BLOCK", "reason": "regression_detected"}
        if level == "E3": return {"status": "CAPTAIN_REQUIRED", "reason": "e3_auto_activation_forbidden"}
        if policy.get("captain_gate") and not captain_approved: return {"status": "CAPTAIN_REQUIRED", "reason": "policy_requires_captain_gate"}
        if not policy.get("may_activate"): return {"status": "READY_FOR_CAPTAIN", "reason": "automatic_activation_disabled"}
        return {"status": "ACTIVATION_ALLOWED", "reason": "policy_and_verification_passed"}

    def record_capability_learning(self, job_id):
        job = self.jobs.load(job_id)
        if job["state"] not in {"READY_FOR_ACCEPTANCE", "ACTIVATION_PENDING", "ACTIVATED"}: raise ValueError("verified_candidate_required_for_learning")
        if not job.get("verification") or job["verification"].get("result") != "PASS": raise ValueError("passing_verification_required_for_learning")
        capability = job["admission"]["requested_capability"]
        record = {"capability":capability,"source":"GUPPI_GENERATED","trust_level":"candidate","job_id":job_id,
                  "classification":job["contract"]["classification"],"verification_digest":job["verification"]["verification_digest"],
                  "recorded_at":utcnow()}
        with append_lock(self.learning_path):
            data = load_json(self.learning_path, {"schema":1,"capabilities":{}})
            data["capabilities"][capability]=record; atomic_write_json(self.learning_path,data)
        return record

    def promote_learned_capability(self, capability, *, captain_approved=False):
        with append_lock(self.learning_path):
            data = load_json(self.learning_path, {"schema":1,"capabilities":{}}); record=(data.get("capabilities") or {}).get(capability)
            if not record: raise KeyError("learned_capability_not_found")
            if not captain_approved: return {"status":"CAPTAIN_REQUIRED","capability":capability}
            record["trust_level"]="KNOWN_GOOD"; record["promoted_at"]=utcnow(); atomic_write_json(self.learning_path,data)
        if self.audit:self.audit.append("LEARNED_CAPABILITY_PROMOTED",component="self-development",payload={"capability":capability,"job_id":record["job_id"]})
        return {"status":"PROMOTED","record":record}

    def checkpoint(self, job_id, *, summary, next_steps=None):
        with self.jobs.mutate(job_id) as job:
            checkpoint = {"checkpoint_id": f"CP-{uuid.uuid4().hex[:12].upper()}", "created_at": utcnow(), "summary": str(summary)[:4000], "next_steps": list(next_steps or [])[:32], "state": job["state"]}
            job["checkpoint"] = checkpoint
        if self.audit:self.audit.append("SELF_DEVELOPMENT_CHECKPOINT", component="self-development", payload={"job_id": job_id, "checkpoint_id": checkpoint["checkpoint_id"]})
        return checkpoint

    def prepare_development_environment(self, job_id, sandbox_status):
        with self.jobs.mutate(job_id) as job:
            if job["state"] != "PLANNING": raise ValueError("development_job_not_planning")
            ready = bool((sandbox_status or {}).get("execution_ready"))
            job["development_environment"] = {"ui_name": "GUPPI Entwicklungsumgebung", "backend": "sandbox", "execution_ready": ready}
            self.jobs.save(job)
            self.jobs.transition(job, "READY" if ready else "BLOCKED")
        return job["development_environment"]

    def assign_roles(self, job_id, roles):
        allowed = {"planner", "coder", "tester", "reviewer", "verifier", "documentation", "security_reviewer", "context_curator"}
        if not isinstance(roles, list) or not roles or any(r not in allowed for r in roles): raise ValueError("invalid_worker_roles")
        with self.jobs.mutate(job_id) as job: job["roles"] = list(dict.fromkeys(roles))
        return job["roles"]

    @staticmethod
    def classify_failure(reason=None, *, exception=None):
        """Kept for compatibility; delegates to the structured classifier in failure_classes.py."""
        return classify_failure_structured(reason, exception=exception)

    # ------------------------------------------------------------------ acceptance binding (candidate_acceptance.py)
    def jobs_for_mission(self, mission_id):
        """Jobs whose bound candidate is this mission's stage (`guppi-candidates/<mission>`, set by bind_candidate)."""
        stage = f"guppi-candidates/{mission_id}"
        return [j for j in self.jobs.list() if j and (j.get("candidate") or {}).get("stage") == stage]

    def acceptance_refusal(self, job):
        """Why this job's candidate may not be taken over now, or None. Needs a verified PASS with proven independence."""
        if job["state"] != "READY_FOR_ACCEPTANCE": return f"development_job_not_ready:{job['state']}"
        verification = job.get("verification") or {}
        if verification.get("result") != "PASS": return "passing_verification_required"
        identities = job.get("verification_identities") or {}
        if self.independence_check is None and not identities: return "independence_not_recorded"
        if identities and identities.get("builder_key") == identities.get("verifier_key"): return "verifier_not_independent"
        decision = self.activation_decision(job["job_id"], captain_approved=True)
        if decision["status"] == "BLOCK": return f"activation_blocked:{decision['reason']}"
        return None

    def mark_activation(self, job_id, phase):
        """Record what the take-over did: started -> ACTIVATION_PENDING, applied -> ACTIVATED, rolled_back -> ROLLED_BACK."""
        target = {"started": "ACTIVATION_PENDING", "applied": "ACTIVATED", "rolled_back": "ROLLED_BACK"}[phase]
        with self.jobs.mutate(job_id) as job:
            if job["state"] != target: self.jobs.transition(job, target)
            job.setdefault("activation_log", []).append({"phase": phase, "at": utcnow()})
        return target

    def view(self):
        jobs = self.jobs.list()
        return {"schema": 1, "policy": {level: self.policy.for_level(level) for level in ("E1", "E2", "E3")},
                "feature_flags": dict(self.policy.feature_flags), "kev": self.kev.status() if self.kev else {"provider": "kev", "enabled": False},
                "jobs": [{"job_id": j["job_id"], "state": j["state"], "classification": j["contract"]["classification"], "capability": j["admission"]["requested_capability"], "created_at": j["created_at"]} for j in jobs[-50:]]}
