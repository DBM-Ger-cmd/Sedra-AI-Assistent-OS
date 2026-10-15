"""Structured failure classification with retry rules (Herdr-handoff section 7).

Order of evidence: explicit reason code, then exception type, then free text. Free text is the
weakest source and is matched on word boundaries. `policy_denied` is always tested first, so a
message that mentions a policy can never be classified as something retryable or fallback-able.
"""
from __future__ import annotations

import re
import subprocess

FAILURE_CLASSES = (
    "transient_provider_error", "timeout", "rate_limit", "runtime_crash", "model_unavailable",
    "hardware_pressure", "context_overflow", "context_quality_degraded", "validation_failure",
    "policy_denied", "deterministic_test_failure", "unknown_failure",
)

# What the supervisor may do next. `retry_same_request=False` means: never resend the identical
# request; change something first (context, code, provider, queue position).
RETRY_RULES = {
    "transient_provider_error": {"retry_same_request": True, "next_action": "retry_with_backoff", "fallback_allowed": True, "escalate": False},
    "timeout": {"retry_same_request": True, "next_action": "retry_limited_then_fallback", "fallback_allowed": True, "escalate": False},
    "rate_limit": {"retry_same_request": False, "next_action": "wait_or_other_provider", "fallback_allowed": True, "escalate": False},
    "runtime_crash": {"retry_same_request": False, "next_action": "restart_runtime_then_fallback", "fallback_allowed": True, "escalate": False},
    "model_unavailable": {"retry_same_request": False, "next_action": "fallback_within_policy", "fallback_allowed": True, "escalate": False},
    "hardware_pressure": {"retry_same_request": False, "next_action": "queue_or_smaller_model", "fallback_allowed": True, "escalate": False},
    "context_overflow": {"retry_same_request": False, "next_action": "reduce_context", "fallback_allowed": False, "escalate": False},
    "context_quality_degraded": {"retry_same_request": False, "next_action": "fresh_context_from_checkpoint", "fallback_allowed": True, "escalate": False},
    "validation_failure": {"retry_same_request": False, "next_action": "rework", "fallback_allowed": False, "escalate": False},
    "policy_denied": {"retry_same_request": False, "next_action": "stop_and_escalate", "fallback_allowed": False, "escalate": True},
    "deterministic_test_failure": {"retry_same_request": False, "next_action": "rework_with_changed_code", "fallback_allowed": False, "escalate": False},
    "unknown_failure": {"retry_same_request": False, "next_action": "escalate", "fallback_allowed": False, "escalate": True},
}

# Exact reason codes already used by the runtime (feasibility, hardware manager, router, journal).
REASON_CODES = {
    "JOB_LIMIT": "hardware_pressure",
    "RAM_RESERVE_UNAVAILABLE": "hardware_pressure",
    "PROVIDER_UNAVAILABLE": "model_unavailable",
    "UNKNOWN_PROVIDER": "model_unavailable",
    "NO_MODEL_ROUTER": "model_unavailable",
    "TOOL_UNAVAILABLE": "transient_provider_error",
    "HARDWARE_PROFILE_UNAVAILABLE": "hardware_pressure",
    "CONTEXT_CAPACITY_UNQUALIFIED": "context_overflow",
    "INVALID_CONTEXT_REQUIREMENT": "validation_failure",
    "INVALID_EXECUTION_LOCATION": "policy_denied",
    "INVALID_DATA_CLASS": "policy_denied",
    "CLOUD_NOT_IMPLEMENTED": "policy_denied",
    "TOOL_NOT_SELECTED": "policy_denied",
    "UNSUPPORTED_REQUIREMENT": "validation_failure",
    "NO_HANDLER": "validation_failure",
    "NO_TOOL_OPERATION": "validation_failure",
    "UNKNOWN_EXECUTION_OUTCOME": "unknown_failure",
    "provider_unavailable": "model_unavailable",
    "no_healthy_local_model_provider": "model_unavailable",
    "unknown_provider": "model_unavailable",
    "model_router_unavailable": "model_unavailable",
    "missing_permission": "policy_denied",
    "token_already_used": "policy_denied",
    "target_out_of_scope": "policy_denied",
    "request_digest_mismatch": "policy_denied",
    "expected_source_sha256_mismatch": "validation_failure",
    "plan_changed_after_checkpoint": "validation_failure",
    "model_source_context_limit": "context_overflow",
    # Role resolution (role_routing.ResolutionError.code). Configuration problems need a human decision, so they escalate.
    "no_capability": "unknown_failure",
    "requirements_unmet": "unknown_failure",
    "policy_denied": "policy_denied",
    "hardware_pressure": "hardware_pressure",
    "provider_unavailable": "model_unavailable",
}
# A reason code that is itself a failure class means that class (a handler can say `validation_failure` directly).
for _name in FAILURE_CLASSES:
    REASON_CODES.setdefault(_name, _name)

# Prefix families (reason codes that carry a suffix, e.g. THERMAL_HOT).
REASON_PREFIXES = (("THERMAL_", "hardware_pressure"), ("provider_unavailable:", "model_unavailable"), ("unknown_provider:", "model_unavailable"),
                   ("provider_cooldown:", "model_unavailable"))

EXCEPTION_TYPES = (
    (subprocess.TimeoutExpired, "timeout"),
    (TimeoutError, "timeout"),
    (MemoryError, "hardware_pressure"),
    (ConnectionError, "transient_provider_error"),
)

# Ordered text rules. Most safety-relevant first. All use word boundaries or fixed phrases.
TEXT_RULES = tuple((re.compile(p, re.I), kind) for p, kind in (
    (r"\bpolic(?:y|ies)\b|\bguard[_ ]blocked\b|\bcaptain[_ ]required\b|\bnot (?:allowed|permitted)\b|\bforbidden\b|\bpermission\b", "policy_denied"),
    (r"\brate[ _-]?limit(?:ed)?\b|\btoo many requests\b|\b(?:http|status)[ :=]*429\b", "rate_limit"),
    (r"\bcontext[ _-](?:window|length|limit)\b|\bmaximum context\b|\btoken[s]? (?:limit|budget)\b|\bcontext_length_exceeded\b|\bcontext overflow\b", "context_overflow"),
    (r"\bcontext[ _-]quality\b|\bstale context\b|\brepeat(?:ed|ing) (?:the )?(?:same|old)\b", "context_quality_degraded"),
    (r"\bout of memory\b|\boom\b|\bvram\b|\bmemory pressure\b|\binsufficient memory\b", "hardware_pressure"),
    (r"\btime[ _-]?out\b|\btimed out\b", "timeout"),
    (r"\bcrash(?:ed)?\b|\bsegfault\b|\bsegmentation fault\b|\bexited with code\b|\bprocess (?:died|killed)\b", "runtime_crash"),
    (r"\bunavailable\b|\bconnection refused\b|\bno healthy\b|\bmodel not found\b", "model_unavailable"),
    (r"\b(?:tests?|assertions?) failed\b|\bassertion ?error\b|\bfailing tests?\b|\btest[_ ]failure\b", "deterministic_test_failure"),
    (r"\bvalidation\b|\binvalid[_ ]\w+|\bschema\b|\bsha256 mismatch\b", "validation_failure"),
    (r"\b(?:http|status)[ :=]*5\d\d\b|\btemporar(?:y|ily)\b|\btransient\b|\bconnection reset\b|\bbad gateway\b", "transient_provider_error"),
))


def classify(reason_code=None, *, exception=None, message=None):
    """Return one of FAILURE_CLASSES. Unknown input yields `unknown_failure`, never a retryable class."""
    if isinstance(reason_code, str) and reason_code:
        if reason_code in REASON_CODES:
            return REASON_CODES[reason_code]
        for prefix, kind in REASON_PREFIXES:
            if reason_code.startswith(prefix):
                return kind
    if exception is not None:
        for exc_type, kind in EXCEPTION_TYPES:
            if isinstance(exception, exc_type):
                return kind
        classified = getattr(exception, "reason_code", None)  # e.g. feasibility.AdmissionUnavailable
        if isinstance(classified, str) and classified:
            return classify(classified)
        if message is None:
            message = str(exception)
    text = str(message if message is not None else (reason_code or ""))
    for pattern, kind in TEXT_RULES:
        if pattern.search(text):
            return kind
    return "unknown_failure"


def retry_rule(failure_class):
    """Retry guidance for a class. Unknown class names are treated as `unknown_failure`."""
    return dict(RETRY_RULES.get(failure_class, RETRY_RULES["unknown_failure"]))
