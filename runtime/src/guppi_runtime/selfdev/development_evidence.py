"""Append-only evidence chain for development claims and verification receipts."""
from __future__ import annotations
from pathlib import Path
import json
import uuid
from ..util import sha256_bytes, utcnow, read_last_jsonl, append_lock


class DevelopmentEvidenceStore:
    MAX_LINE_BYTES = 1024 * 1024

    def __init__(self, path: Path, audit=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.audit = audit

    def _last(self):
        return read_last_jsonl(self.path)

    def add(self, evidence_type, *, job_id=None, candidate_id=None, source_ref=None,
            artifact_sha256=None, payload=None, trust_level="observed"):
        if not isinstance(evidence_type, str) or not evidence_type.strip() or len(evidence_type) > 100:
            raise ValueError("invalid_evidence_type")
        if trust_level not in {"observed", "deterministic", "model_assessment", "human_review", "external_unverified"}:
            raise ValueError("invalid_evidence_trust_level")
        with append_lock(self.path):
            last = self._last()
            record = {
                "schema": 1,
                "evidence_id": f"EVD-{uuid.uuid4().hex[:12].upper()}",
                "created_at": utcnow(),
                "evidence_type": evidence_type,
                "job_id": job_id,
                "candidate_id": candidate_id,
                "source_ref": source_ref,
                "artifact_sha256": artifact_sha256,
                "trust_level": trust_level,
                "payload": payload or {},
                "previous_evidence_hash": last.get("evidence_hash") if last else None,
                "evidence_hash": None,
            }
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            record["evidence_hash"] = sha256_bytes(canonical)
            encoded = json.dumps(record, ensure_ascii=False, sort_keys=True)
            if len(encoded.encode("utf-8")) > self.MAX_LINE_BYTES:
                raise ValueError("evidence_record_too_large")
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(encoded + "\n")
        if self.audit:
            self.audit.append("DEVELOPMENT_EVIDENCE_RECORDED", component="self-development", payload={"evidence_id": record["evidence_id"], "type": evidence_type, "job_id": job_id})
        return record

    def verify_chain(self):
        previous = None
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("previous_evidence_hash") != previous:
                return False
            expected = record.get("evidence_hash")
            copy = dict(record); copy["evidence_hash"] = None
            canonical = json.dumps(copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            if sha256_bytes(canonical) != expected:
                return False
            previous = expected
        return True

    def list(self, job_id=None):
        if not self.path.exists():
            return []
        records = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [r for r in records if job_id is None or r.get("job_id") == job_id]
