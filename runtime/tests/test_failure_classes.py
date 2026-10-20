"""Phase 0.4: structured failure classification (finding F-1)."""
import subprocess
import unittest

from guppi_runtime.jobs.failure_classes import FAILURE_CLASSES, RETRY_RULES, REASON_CODES, classify, retry_rule
from guppi_runtime.feasibility import AdmissionUnavailable
from guppi_runtime.selfdev.self_development import SelfDevelopmentManager
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests


class ClassifyTests(unittest.TestCase):
    def test_every_class_has_a_retry_rule(self):
        self.assertEqual(set(FAILURE_CLASSES), set(RETRY_RULES))
        self.assertEqual(len(FAILURE_CLASSES), 12)

    def test_every_mapped_reason_code_yields_a_known_class(self):
        for code, kind in REASON_CODES.items():
            self.assertIn(kind, FAILURE_CLASSES, code)
            self.assertEqual(classify(code), kind)

    def test_runtime_reason_codes(self):
        self.assertEqual(classify("JOB_LIMIT"), "hardware_pressure")
        self.assertEqual(classify("THERMAL_HOT"), "hardware_pressure")
        self.assertEqual(classify("PROVIDER_UNAVAILABLE"), "model_unavailable")
        self.assertEqual(classify("provider_unavailable:lm-studio"), "model_unavailable")
        self.assertEqual(classify("CLOUD_NOT_IMPLEMENTED"), "policy_denied")
        self.assertEqual(classify("UNKNOWN_EXECUTION_OUTCOME"), "unknown_failure")

    def test_exception_types_and_attached_reason_code(self):
        self.assertEqual(classify(exception=TimeoutError()), "timeout")
        self.assertEqual(classify(exception=subprocess.TimeoutExpired("x", 1)), "timeout")
        self.assertEqual(classify(exception=MemoryError()), "hardware_pressure")
        self.assertEqual(classify(exception=ConnectionResetError()), "transient_provider_error")
        self.assertEqual(classify(exception=AdmissionUnavailable("JOB_LIMIT")), "hardware_pressure")

    def test_findings_from_the_old_substring_classifier(self):
        # F-1: "context window exceeded" used to become context_quality_degraded.
        self.assertEqual(classify(message="context window exceeded"), "context_overflow")
        self.assertEqual(classify(message="token limit reached"), "context_overflow")
        # F-1: "test" matched inside unrelated words.
        self.assertEqual(classify(message="latest release attested"), "unknown_failure")
        self.assertEqual(classify(message="3 tests failed"), "deterministic_test_failure")
        # F-1: rate limits and transient errors could not be expressed.
        self.assertEqual(classify(message="HTTP 429 Too Many Requests"), "rate_limit")
        self.assertEqual(classify(message="upstream returned http 503"), "transient_provider_error")

    def test_numbers_alone_do_not_trigger_http_classes(self):
        self.assertEqual(classify(message="limit is 512 files"), "unknown_failure")
        self.assertEqual(classify(message="processed 429 items"), "unknown_failure")

    def test_policy_wins_over_everything_else(self):
        for message in ("policy denied after timeout", "rate limit hit but policy forbids fallback",
                        "context window exceeded: permission denied", "guard_blocked while unavailable"):
            self.assertEqual(classify(message=message), "policy_denied", message)

    def test_unknown_and_empty_input_is_never_retryable(self):
        for value in (None, "", "something odd happened"):
            kind = classify(value)
            self.assertEqual(kind, "unknown_failure")
        rule = retry_rule("unknown_failure")
        self.assertFalse(rule["retry_same_request"])
        self.assertFalse(rule["fallback_allowed"])
        self.assertTrue(rule["escalate"])

    def test_retry_rules_follow_the_handoff(self):
        self.assertFalse(retry_rule("policy_denied")["fallback_allowed"])
        self.assertTrue(retry_rule("policy_denied")["escalate"])
        self.assertFalse(retry_rule("deterministic_test_failure")["retry_same_request"])
        self.assertFalse(retry_rule("context_overflow")["retry_same_request"])
        self.assertEqual(retry_rule("context_overflow")["next_action"], "reduce_context")
        self.assertFalse(retry_rule("validation_failure")["fallback_allowed"])
        self.assertEqual(retry_rule("not_a_class"), retry_rule("unknown_failure"))

    def test_only_transient_classes_may_resend_identical_request(self):
        resend = {k for k, v in RETRY_RULES.items() if v["retry_same_request"]}
        self.assertEqual(resend, {"transient_provider_error", "timeout"})

    def test_manager_classify_failure_stays_compatible(self):
        self.assertEqual(SelfDevelopmentManager.classify_failure("policy violation"), "policy_denied")
        self.assertEqual(SelfDevelopmentManager.classify_failure("vram exhausted"), "hardware_pressure")
        self.assertEqual(SelfDevelopmentManager.classify_failure(None), "unknown_failure")
        self.assertEqual(SelfDevelopmentManager.classify_failure(exception=TimeoutError()), "timeout")


if __name__ == "__main__":
    unittest.main()
