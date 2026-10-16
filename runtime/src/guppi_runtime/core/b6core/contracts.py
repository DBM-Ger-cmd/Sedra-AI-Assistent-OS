"""Immutable, versioned application contracts; no external dependencies."""
from dataclasses import dataclass, field, asdict
from enum import Enum
from hashlib import sha256
import json
from typing import Optional

SCHEMA_VERSION = '0.2'

class Route(str, Enum):
    LOCAL_ONLY = 'LOCAL_ONLY'
    CLOUD_ALLOWED_SIMULATED = 'CLOUD_ALLOWED_SIMULATED'
    CLOUD_PSEUDONYMIZED_SIMULATED = 'CLOUD_PSEUDONYMIZED_SIMULATED'

class Decision(str, Enum):
    ALLOW = 'ALLOW'
    HUMAN_REVIEW = 'HUMAN_REVIEW'
    BLOCK = 'BLOCK'

class PolicyStatus(str, Enum):
    """B6-P0-10a / K-04 Abschnitt 5: Policy-Ergebnis, getrennt von Route und Review-Status."""
    AUTO_APPROVED = 'AUTO_APPROVED'
    HUMAN_REVIEW_REQUIRED = 'HUMAN_REVIEW_REQUIRED'
    BLOCKED = 'BLOCKED'

class ReviewStatus(str, Enum):
    NOT_REQUIRED = 'NOT_REQUIRED'
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'

class CaseState(str, Enum):
    RECEIVED = 'RECEIVED'
    PRIVACY_CHECKED = 'PRIVACY_CHECKED'
    POLICY_DECIDED = 'POLICY_DECIDED'
    R1_PENDING = 'R1_PENDING'
    READY_LOCAL = 'READY_LOCAL'
    READY_SIMULATION = 'READY_SIMULATION'
    BLOCKED = 'BLOCKED'
    PAUSED_ERROR = 'PAUSED_ERROR'
    DRAFT_CREATED = 'DRAFT_CREATED'
    R2_PENDING = 'R2_PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    CLOSED = 'CLOSED'

class FindingKind(str, Enum):
    PERSON = 'PERSON'
    EMAIL = 'EMAIL'
    PHONE = 'PHONE'
    IDENTIFIER = 'IDENTIFIER'
    SECRET = 'SECRET'
    PROMPT_INJECTION = 'PROMPT_INJECTION'
    UNKNOWN = 'UNKNOWN'
    CONTEXT_ATTRIBUTE = 'CONTEXT_ATTRIBUTE'   # B6-P0-10a: Schutzmerkmal aus Schluesselwortkontext (P02..V01, G01, G02, R01)
    FINANCIAL = 'FINANCIAL'                   # B6-P0-10a: Bank-/Kartendaten (IBAN, PAN)
    INVISIBLE_CHARS = 'INVISIBLE_CHARS'   # B6-P0-09a; Schwere ueber rule_id INVISIBLE_BLOCK_V1 / INVISIBLE_REVIEW_V1

@dataclass(frozen=True)
class PrivacyFinding:
    finding_id: str
    case_id: str
    kind: FindingKind
    offset_start: int
    offset_end: int
    confidence: float
    rule_id: str
    # No raw matched text; can be looked up only in access-controlled original.
    def __post_init__(self):
        if not 0 <= self.confidence <= 1 or self.offset_start < 0 or self.offset_end < self.offset_start:
            raise ValueError('B6_VALIDATION_FINDING')

@dataclass(frozen=True)
class SourceReference:
    source_id: str
    version: str
    title: str
    approval_status: str
    protection_class: str
    cloud_suitability: str
    valid_from: str
    valid_to: str

@dataclass(frozen=True)
class ProcessingIntent:
    purpose: str
    requested_route: str
    model_id: str
    input_sha256: str
    source_refs: tuple[tuple[str, str], ...] = ()

@dataclass(frozen=True)
class PolicyDecision:
    decision_id: str
    case_id: str
    run_id: str
    decision: Decision
    route: Optional[Route]
    policy_version: str
    reason_code: str
    binding_hash: str

@dataclass(frozen=True)
class ApprovalBinding:
    case_id: str
    run_id: str
    stage: str
    document_sha256: str
    purpose: str
    source_refs: tuple[tuple[str, str], ...]
    policy_version: str
    model_id: str
    route: str
    def fingerprint(self) -> str:
        payload = asdict(self)
        payload['source_refs'] = sorted(map(list, self.source_refs))
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        return sha256(raw).hexdigest()

@dataclass(frozen=True)
class ProcessingRun:
    run_id: str
    case_id: str
    attempt: int
    status: CaseState

@dataclass(frozen=True)
class OutputFinding:
    finding_id: str
    run_id: str
    rule_id: str
    category: str
    reason_code: str

@dataclass(frozen=True)
class ReviewDecision:
    review_id: str
    case_id: str
    run_id: str
    stage: str
    actor_id: str
    verdict: str
    binding_hash: str

@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    case_id: str
    run_id: str
    event_type: str
    reason_code: str
    event_time: str
    metadata_json: str = '{}'
