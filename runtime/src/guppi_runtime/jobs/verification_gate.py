"""The verification gate (Phase 8d): when may a job be called verified?

`JobSupervisor.mark_passed` and `accept_verification` ask this gate. It answers with a list of gaps; an empty list means the PASS
may stand. It never decides to pass anything itself and never writes to a job. It reads the job, the hash-chained evidence store and
the reviewing job, and it trusts a claim only as far as a record backs it:

  1. The verification record is intact (its digest recomputes) and belongs to THIS job's candidate and contract.
  2. The candidate is pinned: it has a content hash, and every piece of deterministic evidence was produced for exactly that hash.
  3. Every acceptance criterion with an id is covered by a deterministic PASS bound to the job and candidate. One failing
     deterministic record vetoes the PASS. A model's opinion is never deterministic evidence.
  4. The evidence chain is valid (no record was edited or removed).
  5. If the plan asks for an independent review, a REVIEW JOB exists that is a child of this job, finished successfully, answered
     PASS, ran on a model whose independence key is known and different from the builder's, and is the job the evidence names.
     The same key, or an unknown one, is "not independent" (docs contract 8.4).

Model assessments (Kev, reviewers) are recorded as evidence of trust level `model_assessment`; they can add a requirement (5) but can
never replace deterministic evidence (3).
"""
from __future__ import annotations

from copy import deepcopy

from ..jobs.context_manager import _SECRET
from ..selfdev.development_contracts import canonical_digest
from ..models.role_routing import check_independence

REVIEW_ROLES = frozenset({"verifier", "security_reviewer"})
REVIEW_EVIDENCE = "independent_review"
CHECK_EVIDENCE = "deterministic_check"


class VerificationGate:
    def __init__(self, evidence_store, load_job):
        self.evidence = evidence_store
        self.load_job = load_job                        # callable(job_id) -> job, raising KeyError/ValueError when unknown

    # ---- the question
    def gaps(self, job, verification):
        gaps = []
        if not isinstance(verification, dict):
            return ["verification_record_required"]
        gaps += self._record_gaps(job, verification)
        if gaps:
            return sorted(set(gaps))                    # a record that is not even intact is not looked at further
        candidate = job["candidate"]
        if self.evidence is None:
            return ["evidence_store_unavailable"]
        if not self.evidence.verify_chain():
            return ["evidence_chain_invalid"]
        records = {r["evidence_id"]: r for r in self.evidence.list(job["job_id"])}
        refs = list(verification.get("evidence_refs") or [])
        cited = []
        for ref in refs:
            record = records.get(ref)
            if record is None:
                gaps.append(f"evidence_not_found_for_job:{ref}")
            elif record.get("candidate_id") != candidate["candidate_id"]:
                gaps.append(f"evidence_not_bound_to_candidate:{ref}")
            else:
                cited.append(record)
        gaps += self._deterministic_gaps(job, candidate, cited)
        gaps += self._review_gaps(job, candidate, cited)
        return sorted(set(gaps))

    # ---- 1 and 2: the record and the candidate
    def _record_gaps(self, job, verification):
        gaps = []
        if verification.get("result") != "PASS":
            gaps.append("passing_verification_required")
        body = {k: v for k, v in verification.items() if k != "verification_digest"}
        if not verification.get("verification_digest") or canonical_digest(body) != verification["verification_digest"]:
            gaps.append("verification_digest_mismatch")
        candidate = job.get("candidate")
        if not isinstance(candidate, dict):
            return gaps + ["candidate_required"]
        cbody = {k: v for k, v in candidate.items() if k != "candidate_contract_digest"}
        if not candidate.get("candidate_contract_digest") or canonical_digest(cbody) != candidate["candidate_contract_digest"]:
            gaps.append("candidate_digest_mismatch")
        if candidate.get("development_contract_digest") != (job.get("contract") or {}).get("contract_digest"):
            gaps.append("candidate_not_for_this_contract")
        if verification.get("candidate_id") != candidate.get("candidate_id") or verification.get("candidate_contract_digest") != candidate.get("candidate_contract_digest"):
            gaps.append("verification_not_for_this_candidate")
        if not candidate.get("candidate_hash"):
            gaps.append("candidate_hash_required")
        if verification.get("verifier") == candidate.get("builder"):
            gaps.append("verifier_is_builder")
        return gaps

    # ---- 3: deterministic coverage
    def _deterministic_gaps(self, job, candidate, cited):
        gaps = []
        chash = candidate.get("candidate_hash")
        passing, covered = [], set()
        for record in cited:
            if record.get("trust_level") != "deterministic":
                continue
            payload = record.get("payload") or {}
            if payload.get("status") != "PASS":
                gaps.append(f"deterministic_evidence_not_passing:{record['evidence_id']}")          # a failing check vetoes
                continue
            if chash and record.get("artifact_sha256") != chash:
                gaps.append(f"evidence_for_other_candidate_hash:{record['evidence_id']}")
                continue
            passing.append(record)
            if payload.get("criterion_id"):
                covered.add(payload["criterion_id"])
        if not passing:
            gaps.append("deterministic_test_evidence_required")
        for criterion in (job.get("contract") or {}).get("acceptance_criteria", []):
            cid = criterion.get("id") if isinstance(criterion, dict) else None
            if not cid:
                gaps.append("acceptance_criterion_without_id")
            elif cid not in covered:
                gaps.append(f"acceptance_criterion_not_covered:{cid}")
        return gaps

    # ---- 5: the independent review
    def _review_gaps(self, job, candidate, cited):
        plan = (job.get("contract") or {}).get("verification_plan") or []
        needed = any(isinstance(p, dict) and p.get("type") == "independent_review" for p in plan)
        reviews = [r for r in cited if r.get("evidence_type") == REVIEW_EVIDENCE]
        if needed and not reviews:
            return ["independent_review_required"]
        gaps = []
        for record in reviews:
            payload = record.get("payload") or {}
            if record.get("trust_level") not in {"model_assessment", "human_review"}:
                gaps.append(f"review_evidence_trust_level_invalid:{record['evidence_id']}")
            if payload.get("verdict") != "PASS":
                gaps.append(f"independent_review_not_passing:{record['evidence_id']}")
                continue
            gaps += self._reviewer_gaps(job, candidate, payload, record["evidence_id"])
        return gaps

    def _reviewer_gaps(self, job, candidate, payload, evidence_id):
        tag = f":{evidence_id}"
        try:
            reviewer = self.load_job(payload.get("verifier_job_id"))
        except (KeyError, ValueError, TypeError):
            return ["review_job_not_found" + tag]
        gaps = []
        if reviewer.get("parent_job_id") != job["job_id"]:
            gaps.append("review_job_not_a_child_of_this_job" + tag)
        if reviewer.get("kind") != "review" or reviewer.get("requested_role") not in REVIEW_ROLES:
            gaps.append("review_job_has_wrong_kind_or_role" + tag)
        if reviewer.get("state") != "READY_FOR_ACCEPTANCE":
            gaps.append("review_job_not_finished" + tag)
        done = [a for a in reviewer.get("attempt_log", []) if a.get("attempt_id") == payload.get("attempt_id") and a.get("outcome") == "SUCCEEDED"]
        if not done:
            gaps.append("review_attempt_not_successful" + tag)
        built = [a for a in job.get("attempt_log", []) if a.get("outcome") == "SUCCEEDED"]
        status = check_independence(built[-1].get("independence_key") if built else None, done[-1].get("independence_key") if done else None)
        if status != "INDEPENDENT":
            gaps.append(f"review_not_independent:{status.lower()}" + tag)
        if payload.get("independence_key") not in (None, (done[-1].get("independence_key") if done else None)):
            gaps.append("review_evidence_names_another_model" + tag)
        return gaps


# --------------------------------------------------------------------------- evidence writers (what the harness records)

def record_check(store, job, *, criterion_id, status, check, detail=None):
    """A deterministic check result, bound to the job, its candidate and the candidate's content hash."""
    candidate = job.get("candidate") or {}
    if not candidate.get("candidate_hash"):
        raise ValueError("candidate_hash_required_for_evidence")
    if status not in {"PASS", "FAIL"}:
        raise ValueError("invalid_check_status")
    return store.add(CHECK_EVIDENCE, job_id=job["job_id"], candidate_id=candidate["candidate_id"], source_ref=check,
                     artifact_sha256=candidate["candidate_hash"], trust_level="deterministic",
                     payload={"status": status, "criterion_id": criterion_id, "check": check, "detail": deepcopy(detail or {})})


def record_review(store, job, reviewer_job, attempt, *, verdict, summary):
    """An independent reviewer's verdict. A model assessment: it can be required, but it never counts as deterministic."""
    candidate = job.get("candidate") or {}
    return store.add(REVIEW_EVIDENCE, job_id=job["job_id"], candidate_id=candidate.get("candidate_id"), source_ref=reviewer_job["job_id"],
                     artifact_sha256=candidate.get("candidate_hash"), trust_level="model_assessment",
                     payload={"verdict": verdict, "verifier_job_id": reviewer_job["job_id"], "attempt_id": attempt["attempt_id"],
                              "independence_key": attempt.get("independence_key"), "model": attempt.get("model"), "summary": str(summary)[:1000]})


# --------------------------------------------------------------------------- a deterministic check for text candidates

def document_check(text, *, max_bytes=262144, min_chars=20, forbidden=()):
    """Checks that need no model: it is text, it has substance, it is bounded, it holds no secret-shaped value, none of the
    forbidden phrases, and it was not cut off in the middle of a line of code fence. Returns {"status", "checks", "sha256"}."""
    import hashlib
    checks = []
    def add(name, ok, note=None): checks.append({"check": name, "ok": bool(ok), "note": note})
    raw = text.encode("utf-8") if isinstance(text, str) else b""
    add("is_text", isinstance(text, str))
    add("size_within_limit", 0 < len(raw) <= max_bytes, f"{len(raw)} bytes")
    add("has_substance", isinstance(text, str) and len(text.strip()) >= min_chars)
    add("no_secret_shaped_values", isinstance(text, str) and not _SECRET.search(text))
    add("no_forbidden_phrases", isinstance(text, str) and not any(f.lower() in text.lower() for f in forbidden))
    add("code_fences_balanced", isinstance(text, str) and text.count("```") % 2 == 0)
    return {"status": "PASS" if all(c["ok"] for c in checks) else "FAIL", "checks": checks,
            "sha256": hashlib.sha256(raw).hexdigest() if raw else None}
