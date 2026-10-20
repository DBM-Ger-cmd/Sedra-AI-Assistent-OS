"""Typed-ish, hash-bound contracts for controlled GUPPI self-development.

These helpers intentionally stay dependency-free. They create bounded JSON-compatible
records that can be audited, hashed and persisted by the existing runtime.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from copy import deepcopy
from ..core.util import utcnow

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical_digest(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _bound_text(value, name, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"invalid_{name}")
    return value.strip()


def _string_list(value, name, limit=64, item_limit=500):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"invalid_{name}")
    out = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or len(item) > item_limit:
            raise ValueError(f"invalid_{name}")
        out.append(item.strip())
    return out


def development_contract(*, objective, classification, scope=None, allowed_actions=None,
                         forbidden_actions=None, permission_level=2, acceptance_criteria=None,
                         verification_plan=None, rollback_required=True,
                         required_artifacts=None, captain_gate_required=None,
                         source_gap_id=None, contract_id=None):
    if classification not in {"E1", "E2", "E3"}:
        raise ValueError("invalid_evolution_classification")
    if type(permission_level) is not int or not 0 <= permission_level <= 6:
        raise ValueError("invalid_permission_level")
    criteria = acceptance_criteria or []
    if not isinstance(criteria, list) or not criteria or len(criteria) > 64:
        raise ValueError("acceptance_criteria_required")
    if any(not isinstance(x, dict) or not x for x in criteria):
        raise ValueError("invalid_acceptance_criteria")
    plan = verification_plan or []
    if not isinstance(plan, list) or not plan or len(plan) > 64:
        raise ValueError("verification_plan_required")
    if any(not isinstance(x, dict) or not x for x in plan):
        raise ValueError("invalid_verification_plan")
    if captain_gate_required is None:
        captain_gate_required = classification in {"E2", "E3"}
    record = {
        "schema": 1,
        "contract_id": contract_id or f"DEV-{uuid.uuid4().hex[:12].upper()}",
        "created_at": utcnow(),
        "source_gap_id": source_gap_id,
        "objective": _bound_text(objective, "objective"),
        "classification": classification,
        "scope": deepcopy(scope or {}),
        "allowed_actions": _string_list(allowed_actions or ["develop_candidate", "run_tests", "verify_candidate"], "allowed_actions"),
        "forbidden_actions": _string_list(forbidden_actions or ["modify_stable_directly", "increase_permissions", "bypass_guard", "silent_cloud_fallback"], "forbidden_actions"),
        "permission_level": permission_level,
        "acceptance_criteria": deepcopy(criteria),
        "verification_plan": deepcopy(plan),
        "rollback_required": bool(rollback_required),
        "required_artifacts": _string_list(required_artifacts or [], "required_artifacts"),
        "captain_gate_required": bool(captain_gate_required),
    }
    record["contract_digest"] = canonical_digest(record)
    return record


def context_manifest(*, goal, current_task, budget, constraints=None, relevant_decisions=None,
                     required_files=None, exact_symbols=None, open_questions=None,
                     acceptance_criteria=None, known_failures=None, permissions=None,
                     artifact_refs=None, parent_job_id=None, checkpoint_id=None,
                     parent_manifest_id=None, layers=None, pins=None, snapshot=None, token_estimate=None, excluded=None):
    """Optional trailing fields (Phase 4) are only written when given, so manifests built the old way are unchanged."""
    if not isinstance(budget, dict) or int(budget.get("max_input_tokens", 0) or 0) <= 0:
        raise ValueError("valid_context_budget_required")
    manifest = {
        "schema": 1,
        "manifest_id": f"CTX-{uuid.uuid4().hex[:12].upper()}",
        "created_at": utcnow(),
        "goal": _bound_text(goal, "context_goal"),
        "current_task": _bound_text(current_task, "current_task"),
        "constraints": _string_list(constraints or [], "constraints"),
        "relevant_decisions": _string_list(relevant_decisions or [], "relevant_decisions"),
        "required_files": _string_list(required_files or [], "required_files"),
        "exact_symbols": _string_list(exact_symbols or [], "exact_symbols"),
        "open_questions": _string_list(open_questions or [], "open_questions"),
        "acceptance_criteria": deepcopy(acceptance_criteria or []),
        "known_failures": _string_list(known_failures or [], "known_failures"),
        "permissions": deepcopy(permissions or {}),
        "artifact_refs": _string_list(artifact_refs or [], "artifact_refs"),
        "parent_job_id": parent_job_id,
        "checkpoint_id": checkpoint_id,
        "budget": deepcopy(budget),
    }
    optional = {"parent_manifest_id": parent_manifest_id, "layers": layers, "pins": pins, "snapshot": snapshot,
                "token_estimate": token_estimate, "excluded": excluded}
    for key, value in optional.items():
        if value is not None:
            manifest[key] = deepcopy(value)
    if pins is not None:
        manifest["budget_digest"] = canonical_digest(manifest["budget"])
    manifest["manifest_digest"] = canonical_digest(manifest)
    return manifest


def candidate_contract(*, development_contract_record, attempt_id, stage, parent_version,
                       changed_files=None, candidate_hash=None, status="DRAFT",
                       rollback_point=None, builder="coder"):
    if not isinstance(development_contract_record, dict):
        raise ValueError("development_contract_required")
    expected = development_contract_record.get("contract_digest")
    unsigned = deepcopy(development_contract_record)
    unsigned.pop("contract_digest", None)
    if expected != canonical_digest(unsigned):
        raise ValueError("development_contract_digest_mismatch")
    if not isinstance(stage, str) or not stage.startswith("guppi-candidates/") or ".." in stage:
        raise ValueError("candidate_stage_must_be_development_namespace")
    if candidate_hash is not None and (not isinstance(candidate_hash, str) or not _HEX64.fullmatch(candidate_hash)):
        raise ValueError("invalid_candidate_hash")
    if status not in {"DRAFT", "BUILDING", "TESTING", "VERIFYING", "READY", "REJECTED", "SUPERSEDED"}:
        raise ValueError("invalid_candidate_status")
    record = {
        "schema": 1,
        "candidate_id": f"CAND-{uuid.uuid4().hex[:12].upper()}",
        "created_at": utcnow(),
        "development_contract_digest": expected,
        "attempt_id": _bound_text(attempt_id, "attempt_id", 128),
        "stage": _bound_text(stage, "candidate_stage", 1000),
        "parent_version": _bound_text(str(parent_version), "parent_version", 128),
        "changed_files": _string_list(changed_files or [], "changed_files", limit=256, item_limit=1000),
        "candidate_hash": candidate_hash,
        "rollback_point": rollback_point,
        "builder": _bound_text(builder, "candidate_builder", 100),
        "status": status,
    }
    record["candidate_contract_digest"] = canonical_digest(record)
    return record


def verification_contract(*, candidate_contract_record, verifier, verification_type="independent",
                          evidence_refs=None, result="PENDING", confidence=None, findings=None):
    if result not in {"PENDING", "PASS", "FAIL", "INCONCLUSIVE"}:
        raise ValueError("invalid_verification_result")
    if confidence is not None and (not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1):
        raise ValueError("invalid_verification_confidence")
    if not isinstance(candidate_contract_record, dict):
        raise ValueError("candidate_contract_required")
    expected = candidate_contract_record.get("candidate_contract_digest")
    unsigned = deepcopy(candidate_contract_record)
    unsigned.pop("candidate_contract_digest", None)
    if expected != canonical_digest(unsigned):
        raise ValueError("candidate_contract_digest_mismatch")
    record = {
        "schema": 1,
        "verification_id": f"VER-{uuid.uuid4().hex[:12].upper()}",
        "created_at": utcnow(),
        "candidate_id": candidate_contract_record["candidate_id"],
        "candidate_contract_digest": expected,
        "verifier": _bound_text(verifier, "verifier", 200),
        "verification_type": _bound_text(verification_type, "verification_type", 100),
        "evidence_refs": _string_list(evidence_refs or [], "evidence_refs", limit=256, item_limit=500),
        "result": result,
        "confidence": None if confidence is None else float(confidence),
        "findings": _string_list(findings or [], "verification_findings", limit=128, item_limit=1000),
    }
    record["verification_digest"] = canonical_digest(record)
    return record
