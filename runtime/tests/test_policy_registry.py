"""Tests für Policy Registry (Z5) und Policy Evaluator (Z4)."""

from __future__ import annotations

import json
import tempfile
import unittest
import asyncio
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sedra_runtime.policy.registry import (
    PolicyRegistry,
    PolicyDefinition,
    PolicySeverity,
    PolicyEvaluatorType,
    DEFAULT_POLICIES,
    create_default_registry,
)
from sedra_runtime.policy.evaluator import (
    PolicyEvaluator,
    AsyncPolicyEvaluator,
    PolicyContext,
    PolicyResult,
    PolicyDecision,
    GateCallback,
    AsyncGateCallback,
    create_evaluator,
    create_async_evaluator,
)


class PolicyRegistryTest(unittest.TestCase):
    """Tests für PolicyRegistry (Z5)."""

    def setUp(self):
        """Create a temporary registry file for each test."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmpdir.name) / "policies.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_registry_creation_empty(self):
        """Test creating empty registry."""
        registry = PolicyRegistry(self.store_path)
        self.assertEqual(len(registry.list()), 0)

    def test_register_policy(self):
        """Test registering a new policy."""
        registry = PolicyRegistry(self.store_path)

        policy = PolicyDefinition(
            id="test-policy",
            name="Test Policy",
            description="Test Description",
            severity=PolicySeverity.HIGH,
            evaluator=PolicyEvaluatorType.CAPTAIN_GATE,
        )

        registered = registry.register(policy)
        self.assertEqual(registered.id, "test-policy")
        self.assertEqual(registered.name, "Test Policy")
        self.assertEqual(registered.severity, PolicySeverity.HIGH)

    def test_register_duplicate_fails(self):
        """Test that registering duplicate policy raises ValueError."""
        registry = PolicyRegistry(self.store_path)

        policy = PolicyDefinition(
            id="test-policy",
            name="Test Policy",
            description="Test",
            severity=PolicySeverity.HIGH,
        )
        registry.register(policy)

        with self.assertRaises(ValueError):
            registry.register(policy)

    def test_get_policy(self):
        """Test retrieving a policy by ID."""
        registry = PolicyRegistry(self.store_path)

        policy = PolicyDefinition(
            id="get-test",
            name="Get Test",
            description="Test",
            severity=PolicySeverity.MEDIUM,
        )
        registry.register(policy)

        retrieved = registry.get("get-test")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "get-test")

        # Non-existent policy
        self.assertIsNone(registry.get("nonexistent"))

    def test_update_policy(self):
        """Test updating an existing policy."""
        registry = PolicyRegistry(self.store_path)

        policy = PolicyDefinition(
            id="update-test",
            name="Original",
            description="Test",
            severity=PolicySeverity.LOW,
        )
        registry.register(policy)

        policy.name = "Updated"
        policy.severity = PolicySeverity.HIGH
        updated = registry.update(policy)

        self.assertEqual(updated.name, "Updated")
        self.assertEqual(updated.severity, PolicySeverity.HIGH)

        retrieved = registry.get("update-test")
        self.assertEqual(retrieved.name, "Updated")

    def test_delete_policy(self):
        """Test deleting a policy."""
        registry = PolicyRegistry(self.store_path)

        policy = PolicyDefinition(
            id="delete-test",
            name="Delete Test",
            description="Test",
            severity=PolicySeverity.LOW,
        )
        registry.register(policy)
        self.assertTrue(registry.delete("delete-test"))
        self.assertIsNone(registry.get("delete-test"))
        self.assertFalse(registry.delete("delete-test"))  # Already deleted

    def test_list_policies(self):
        """Test listing all policies."""
        registry = PolicyRegistry(self.store_path)

        for i in range(3):
            policy = PolicyDefinition(
                id=f"policy-{i}",
                name=f"Policy {i}",
                description="Test",
                severity=PolicySeverity.MEDIUM,
            )
            registry.register(policy)

        policies = registry.list()
        self.assertEqual(len(policies), 3)
        ids = {p.id for p in policies}
        self.assertEqual(ids, {"policy-0", "policy-1", "policy-2"})

    def test_list_by_severity(self):
        """Test filtering policies by severity."""
        registry = PolicyRegistry(self.store_path)

        registry.register(PolicyDefinition(id="p1", name="P1", description="", severity=PolicySeverity.HIGH))
        registry.register(PolicyDefinition(id="p2", name="P2", description="", severity=PolicySeverity.LOW))
        registry.register(PolicyDefinition(id="p3", name="P3", description="", severity=PolicySeverity.HIGH))

        high = registry.list_by_severity(PolicySeverity.HIGH)
        low = registry.list_by_severity(PolicySeverity.LOW)

        self.assertEqual(len(high), 2)
        self.assertEqual(len(low), 1)

    def test_list_by_evaluator(self):
        """Test filtering policies by evaluator type."""
        registry = PolicyRegistry(self.store_path)

        registry.register(PolicyDefinition(
            id="captain", name="Captain", description="",
            severity=PolicySeverity.HIGH, evaluator=PolicyEvaluatorType.CAPTAIN_GATE))
        registry.register(PolicyDefinition(
            id="auto", name="Auto", description="",
            severity=PolicySeverity.MEDIUM, evaluator=PolicyEvaluatorType.AUTO))

        captain = registry.list_by_evaluator(PolicyEvaluatorType.CAPTAIN_GATE)
        auto = registry.list_by_evaluator(PolicyEvaluatorType.AUTO)

        self.assertEqual(len(captain), 1)
        self.assertEqual(len(auto), 1)

    def test_persistence(self):
        """Test that policies persist to disk and reload."""
        registry1 = PolicyRegistry(self.store_path)
        policy = PolicyDefinition(
            id="persist-test",
            name="Persist Test",
            description="Test Persistence",
            severity=PolicySeverity.CRITICAL,
        )
        registry1.register(policy)

        # New registry instance loads from disk
        registry2 = PolicyRegistry(self.store_path)
        retrieved = registry2.get("persist-test")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Persist Test")
        self.assertEqual(retrieved.severity, PolicySeverity.CRITICAL)

    def test_create_default_registry(self):
        """Test creating registry with default policies."""
        registry = create_default_registry(self.store_path)
        policies = registry.list()

        # Default Policies should be loaded
        self.assertGreaterEqual(len(policies), len(DEFAULT_POLICIES))

        # Specific default policies check
        expected_ids = {"production-deploy", "data-migration", "schema-change", "external-api-call", "resource-intensive"}
        actual_ids = {p.id for p in policies}
        self.assertTrue(expected_ids.issubset(actual_ids))

    def test_default_policies_are_captain_gate(self):
        """Test that default captain gate policies have correct evaluator."""
        registry = create_default_registry(self.store_path)

        for policy in registry.list():
            if policy.id in {"production-deploy", "data-migration", "schema-change", "resource-intensive"}:
                self.assertEqual(policy.evaluator, PolicyEvaluatorType.CAPTAIN_GATE)

    def test_external_api_call_is_auto(self):
        """Test that external-api-call policy is AUTO type."""
        registry = create_default_registry(self.store_path)
        policy = registry.get("external-api-call")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.evaluator, PolicyEvaluatorType.AUTO)
        self.assertIn("development", policy.config.get("environments", []))
        self.assertIn("staging", policy.config.get("environments", []))

    def test_resource_intensive_has_config(self):
        """Test that resource-intensive policy has resource thresholds."""
        registry = create_default_registry(self.store_path)
        policy = registry.get("resource-intensive")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.config.get("cpu_threshold_percent"), 80)
        self.assertEqual(policy.config.get("memory_threshold_mb"), 1024)

    def test_policy_to_from_dict(self):
        """Test PolicyDefinition serialization round-trip."""
        policy = PolicyDefinition(
            id="dict-test",
            name="Dict Test",
            description="Test",
            severity=PolicySeverity.HIGH,
            evaluator=PolicyEvaluatorType.AUTO,
            config={"environments": ["dev", "staging"]},
        )

        d = policy.to_dict()
        self.assertEqual(d["id"], "dict-test")
        self.assertEqual(d["severity"], "high")
        self.assertEqual(d["evaluator"], "auto")

        restored = PolicyDefinition.from_dict(d)
        self.assertEqual(restored.id, "dict-test")
        self.assertEqual(restored.severity, PolicySeverity.HIGH)
        self.assertEqual(restored.evaluator, PolicyEvaluatorType.AUTO)
        self.assertEqual(restored.config, {"environments": ["dev", "staging"]})


class PolicyDefinitionTest(unittest.TestCase):
    """Tests für PolicyDefinition Dataclass."""

    def test_defaults(self):
        """Test default values for optional fields."""
        policy = PolicyDefinition(
            id="default-test",
            name="Default Test",
            description="Test",
            severity=PolicySeverity.MEDIUM,
        )
        self.assertEqual(policy.evaluator, PolicyEvaluatorType.CAPTAIN_GATE)
        self.assertEqual(policy.requires, [])
        self.assertEqual(policy.config, {})


class PolicyEvaluatorTest(unittest.TestCase):
    """Tests für PolicyEvaluator (sync Z4)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmpdir.name) / "policies.json"
        self.registry = create_default_registry(self.store_path)
        self.evaluator = PolicyEvaluator(self.registry)

    def tearDown(self):
        self.tmpdir.cleanup()

    def create_context(self, **kwargs) -> PolicyContext:
        """Helper to create a PolicyContext."""
        defaults = {
            "workflow_id": "test-workflow",
            "step_id": "test-step",
            "step_name": "Test Step",
            "adapter_type": "native",
            "parameters": {},
            "user_roles": [],
            "environment": "development",
            "metadata": {},
        }
        defaults.update(kwargs)
        return PolicyContext(**defaults)

    def test_evaluate_auto_policy_external_api_call_allowed_env(self):
        """Test AUTO policy for external-api-call in allowed environment."""
        context = self.create_context(environment="development")
        result = self.evaluator.evaluate("external-api-call", context)

        self.assertEqual(result.decision, PolicyDecision.APPROVED)
        self.assertEqual(result.evaluator, "auto")

    def test_evaluate_auto_policy_external_api_call_disallowed_env(self):
        """Test AUTO policy for external-api-call in disallowed environment."""
        context = self.create_context(environment="production")
        result = self.evaluator.evaluate("external-api-call", context)

        self.assertEqual(result.decision, PolicyDecision.REJECTED)
        self.assertIn("nicht erlaubt", result.reason)

    def test_evaluate_auto_policy_with_required_roles(self):
        """Test AUTO policy with required roles."""
        # Add a policy with required roles
        policy = PolicyDefinition(
            id="role-test",
            name="Role Test",
            description="Test role requirement",
            severity=PolicySeverity.MEDIUM,
            evaluator=PolicyEvaluatorType.AUTO,
            config={"required_roles": ["admin", "deployer"]},
        )
        self.registry.register(policy)

        # User has required role
        context = self.create_context(user_roles=["user", "admin"])
        result = self.evaluator.evaluate("role-test", context)
        self.assertEqual(result.decision, PolicyDecision.APPROVED)

        # User lacks required role
        context = self.create_context(user_roles=["user"])
        result = self.evaluator.evaluate("role-test", context)
        self.assertEqual(result.decision, PolicyDecision.REJECTED)
        self.assertIn("fehlen", result.reason)

    def test_evaluate_captain_gate_without_callback_returns_error(self):
        """Test Captain Gate without callback returns ERROR."""
        context = self.create_context()
        result = self.evaluator.evaluate("production-deploy", context)

        self.assertEqual(result.decision, PolicyDecision.ERROR)
        self.assertIn("Callback", result.reason)

    def test_evaluate_captain_gate_with_callback_approved(self):
        """Test Captain Gate with callback returning approved."""
        def gate_callback(policy_id, context):
            return "approved"

        evaluator = PolicyEvaluator(self.registry, gate_callback=gate_callback)
        context = self.create_context()
        result = evaluator.evaluate("production-deploy", context)

        self.assertEqual(result.decision, PolicyDecision.APPROVED)
        self.assertEqual(result.reason, "Captain approved")
        self.assertEqual(result.evaluator, "captain_gate")

    def test_evaluate_captain_gate_with_callback_rejected(self):
        """Test Captain Gate with callback returning rejected."""
        def gate_callback(policy_id, context):
            return "rejected"

        evaluator = PolicyEvaluator(self.registry, gate_callback=gate_callback)
        context = self.create_context()
        result = evaluator.evaluate("production-deploy", context)

        self.assertEqual(result.decision, PolicyDecision.REJECTED)
        self.assertEqual(result.reason, "Captain rejected")

    def test_evaluate_captain_gate_with_callback_unknown(self):
        """Test Captain Gate with callback returning unknown decision."""
        def gate_callback(policy_id, context):
            return "maybe"

        evaluator = PolicyEvaluator(self.registry, gate_callback=gate_callback)
        context = self.create_context()
        result = evaluator.evaluate("production-deploy", context)

        self.assertEqual(result.decision, PolicyDecision.PENDING)
        self.assertIn("Unbekannte", result.reason)

    def test_evaluate_nonexistent_policy(self):
        """Test evaluating non-existent policy returns ERROR."""
        context = self.create_context()
        result = self.evaluator.evaluate("nonexistent", context)

        self.assertEqual(result.decision, PolicyDecision.ERROR)
        self.assertIn("nicht gefunden", result.reason)

    def test_evaluate_multiple_policies_all_approved(self):
        """Test evaluating multiple policies where all approve."""
        def gate_callback(policy_id, context):
            return "approved"

        evaluator = PolicyEvaluator(self.registry, gate_callback=gate_callback)
        context = self.create_context()
        results = evaluator.evaluate_multiple(["production-deploy", "data-migration"], context)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].decision, PolicyDecision.APPROVED)
        self.assertEqual(results[1].decision, PolicyDecision.APPROVED)

    def test_evaluate_multiple_policies_early_exit_on_reject(self):
        """Test evaluating multiple policies stops on first reject."""
        def gate_callback(policy_id, context):
            if policy_id == "production-deploy":
                return "rejected"
            return "approved"

        evaluator = PolicyEvaluator(self.registry, gate_callback=gate_callback)
        context = self.create_context()
        results = evaluator.evaluate_multiple(["production-deploy", "data-migration", "schema-change"], context)

        # Should stop after first reject
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].decision, PolicyDecision.REJECTED)

    def test_evaluate_script_policy_not_implemented(self):
        """Test SCRIPT evaluator returns PENDING (not implemented)."""
        policy = PolicyDefinition(
            id="script-test",
            name="Script Test",
            description="Test script evaluator",
            severity=PolicySeverity.MEDIUM,
            evaluator=PolicyEvaluatorType.SCRIPT,
            config={"script": "return true"},
        )
        self.registry.register(policy)

        context = self.create_context()
        result = self.evaluator.evaluate("script-test", context)

        self.assertEqual(result.decision, PolicyDecision.PENDING)
        self.assertIn("nicht implementiert", result.reason)

    def test_evaluate_script_policy_no_script(self):
        """Test SCRIPT evaluator without script returns ERROR."""
        policy = PolicyDefinition(
            id="script-test-no-script",
            name="Script Test No Script",
            description="Test",
            severity=PolicySeverity.MEDIUM,
            evaluator=PolicyEvaluatorType.SCRIPT,
            config={},  # No script
        )
        self.registry.register(policy)

        context = self.create_context()
        result = self.evaluator.evaluate("script-test-no-script", context)

        self.assertEqual(result.decision, PolicyDecision.ERROR)
        self.assertIn("Kein Script", result.reason)

    def test_policy_result_has_evidence_data(self):
        """Test that PolicyResult includes evidence data for captain gate."""
        def gate_callback(policy_id, context):
            return "approved"

        evaluator = PolicyEvaluator(self.registry, gate_callback=gate_callback)
        context = self.create_context(
            step_id="step-123",
            metadata={"custom_field": "test_value"}
        )
        result = evaluator.evaluate("production-deploy", context)

        self.assertIsNotNone(result.evidence_data)
        self.assertEqual(result.evidence_data["policy_id"], "production-deploy")
        self.assertEqual(result.evidence_data["step_id"], "step-123")
        self.assertEqual(result.evidence_data["adapter_type"], "native")
        self.assertEqual(result.evidence_data["metadata"]["custom_field"], "test_value")

    def test_create_evaluator_factory(self):
        """Test create_evaluator factory function."""
        evaluator = create_evaluator(self.registry)
        self.assertIsInstance(evaluator, PolicyEvaluator)

        evaluator = create_evaluator(self.registry, gate_callback=lambda p, c: "approved")
        self.assertIsInstance(evaluator, PolicyEvaluator)
        self.assertIsNotNone(evaluator.gate_callback)


class AsyncPolicyEvaluatorTest(unittest.TestCase):
    """Tests für AsyncPolicyEvaluator (Z4 async)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmpdir.name) / "policies.json"
        self.registry = create_default_registry(self.store_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def create_context(self, **kwargs) -> PolicyContext:
        """Helper to create a PolicyContext."""
        defaults = {
            "workflow_id": "test-workflow",
            "step_id": "test-step",
            "step_name": "Test Step",
            "adapter_type": "native",
            "parameters": {},
            "user_roles": [],
            "environment": "development",
            "metadata": {},
        }
        defaults.update(kwargs)
        return PolicyContext(**defaults)

    def test_async_evaluator_creation(self):
        """Test creating AsyncPolicyEvaluator with gate callback."""
        async def gate_callback(policy_id, context):
            return "approved"

        evaluator = AsyncPolicyEvaluator(
            self.registry,
            gate_callback=gate_callback,
            default_timeout_seconds=10,
        )

        self.assertEqual(evaluator.default_timeout, 10)
        self.assertIsNotNone(evaluator.gate_callback)

    def test_async_evaluator_creation_with_webhook(self):
        """Test creating AsyncPolicyEvaluator with webhook URL."""
        evaluator = AsyncPolicyEvaluator(
            self.registry,
            webhook_url="http://localhost:8080/webhook",
            default_timeout_seconds=60,
        )

        self.assertEqual(evaluator.webhook_url, "http://localhost:8080/webhook")
        self.assertEqual(evaluator.default_timeout, 60)

    def test_async_evaluate_auto_policy(self):
        """Test async evaluation of AUTO policy."""
        evaluator = AsyncPolicyEvaluator(self.registry, default_timeout_seconds=10)
        context = self.create_context(environment="development")

        result = asyncio.run(evaluator.evaluate("external-api-call", context))

        self.assertEqual(result.decision, PolicyDecision.APPROVED)
        self.assertEqual(result.evaluator, "auto")

    def test_async_evaluate_captain_gate_with_async_callback(self):
        """Test async evaluation with async gate callback."""
        async def gate_callback(policy_id, context):
            await asyncio.sleep(0.01)  # Simulate async work
            return "approved"

        evaluator = AsyncPolicyEvaluator(
            self.registry,
            gate_callback=gate_callback,
            default_timeout_seconds=10,
        )

        context = self.create_context()
        result = asyncio.run(evaluator.evaluate("production-deploy", context))

        self.assertEqual(result.decision, PolicyDecision.APPROVED)
        self.assertEqual(result.evaluator, "captain_gate")

    def test_async_evaluate_captain_gate_with_sync_callback(self):
        """Test async evaluation with sync gate callback (runs in thread pool)."""
        def gate_callback(policy_id, context):
            return "approved"

        evaluator = AsyncPolicyEvaluator(
            self.registry,
            gate_callback_sync=gate_callback,
            default_timeout_seconds=10,
        )

        context = self.create_context()
        result = asyncio.run(evaluator.evaluate("production-deploy", context))

        self.assertEqual(result.decision, PolicyDecision.APPROVED)

    def test_async_evaluate_captain_gate_callback_rejects(self):
        """Test async evaluation where callback rejects."""
        async def gate_callback(policy_id, context):
            return "rejected"

        evaluator = AsyncPolicyEvaluator(
            self.registry,
            gate_callback=gate_callback,
            default_timeout_seconds=10,
        )

        context = self.create_context()
        result = asyncio.run(evaluator.evaluate("production-deploy", context))

        self.assertEqual(result.decision, PolicyDecision.REJECTED)
        self.assertEqual(result.reason, "Captain rejected")

    def test_async_evaluate_timeout(self):
        """Test async evaluation times out."""
        async def slow_callback(policy_id, context):
            await asyncio.sleep(2)
            return "approved"

        evaluator = AsyncPolicyEvaluator(
            self.registry,
            gate_callback=slow_callback,
            default_timeout_seconds=0.1,  # Very short timeout
        )

        context = self.create_context()
        result = asyncio.run(evaluator.evaluate("production-deploy", context))

        self.assertEqual(result.decision, PolicyDecision.REJECTED)
        self.assertIn("Timeout", result.reason)

    def test_async_evaluate_no_callback_no_webhook_returns_error(self):
        """Test async evaluation without callback or webhook returns ERROR."""
        evaluator = AsyncPolicyEvaluator(
            self.registry,
            default_timeout_seconds=10,
        )

        context = self.create_context()
        result = asyncio.run(evaluator.evaluate("production-deploy", context))

        self.assertEqual(result.decision, PolicyDecision.ERROR)
        self.assertIn("Callback", result.reason)

    def test_async_evaluate_nonexistent_policy(self):
        """Test async evaluating non-existent policy returns ERROR."""
        evaluator = AsyncPolicyEvaluator(self.registry, default_timeout_seconds=10)
        context = self.create_context()
        result = asyncio.run(evaluator.evaluate("nonexistent", context))

        self.assertEqual(result.decision, PolicyDecision.ERROR)
        self.assertIn("nicht gefunden", result.reason)

    def test_create_async_evaluator_factory(self):
        """Test create_async_evaluator factory function."""
        evaluator = create_async_evaluator(self.registry)
        self.assertIsInstance(evaluator, AsyncPolicyEvaluator)

        async def cb(p, c): return "approved"
        evaluator = create_async_evaluator(
            self.registry,
            gate_callback=cb,
            default_timeout_seconds=60,
            webhook_url="http://test.com"
        )
        self.assertIsInstance(evaluator, AsyncPolicyEvaluator)
        self.assertEqual(evaluator.default_timeout, 60)
        self.assertEqual(evaluator.webhook_url, "http://test.com")


class PolicyDecisionEnumTest(unittest.TestCase):
    """Tests für PolicyDecision Enum."""

    def test_enum_values(self):
        """Test PolicyDecision enum has expected values."""
        self.assertEqual(PolicyDecision.APPROVED.value, "approved")
        self.assertEqual(PolicyDecision.REJECTED.value, "rejected")
        self.assertEqual(PolicyDecision.PENDING.value, "pending")
        self.assertEqual(PolicyDecision.ERROR.value, "error")


if __name__ == "__main__":
    unittest.main()
