"""Tests für Policy Evaluator (Z4)."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from sedra_runtime.policy.registry import (
    PolicyRegistry,
    PolicyDefinition,
    PolicySeverity,
    PolicyEvaluatorType,
    create_default_registry,
)
from sedra_runtime.policy.evaluator import (
    PolicyEvaluator,
    AsyncPolicyEvaluator,
    PolicyContext,
    PolicyResult,
    PolicyDecision,
    create_evaluator,
    create_async_evaluator,
)


class PolicyEvaluatorTest(unittest.TestCase):
    """Tests für PolicyEvaluator (Sync)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmpdir.name) / "policies.json"
        self.registry = PolicyRegistry(self.store_path)
        self.registry.register(PolicyDefinition(
            id="auto-policy",
            name="Auto Policy",
            description="Auto approve in dev",
            severity=PolicySeverity.MEDIUM,
            evaluator=PolicyEvaluatorType.AUTO,
            config={"environments": ["development", "staging"]},
        ))
        self.registry.register(PolicyDefinition(
            id="captain-policy",
            name="Captain Policy",
            description="Requires captain approval",
            severity=PolicySeverity.HIGH,
            evaluator=PolicyEvaluatorType.CAPTAIN_GATE,
        ))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_evaluate_auto_approved(self):
        evaluator = create_evaluator(self.registry)
        
        context = PolicyContext(
            workflow_id="wf-1",
            step_id="step-1",
            step_name="Test Step",
            adapter_type="native",
            environment="development",
        )
        
        result = evaluator.evaluate("auto-policy", context)
        self.assertEqual(result.decision, PolicyDecision.APPROVED)
        self.assertEqual(result.evaluator, "auto")

    def test_evaluate_auto_rejected_wrong_env(self):
        evaluator = create_evaluator(self.registry)
        
        context = PolicyContext(
            workflow_id="wf-1",
            step_id="step-1",
            step_name="Test Step",
            adapter_type="native",
            environment="production",  # Nicht in allowed environments
        )
        
        result = evaluator.evaluate("auto-policy", context)
        self.assertEqual(result.decision, PolicyDecision.REJECTED)
        self.assertIn("production", result.reason)

    def test_evaluate_auto_with_role_requirement(self):
        # Policy mit role requirement
        self.registry.register(PolicyDefinition(
            id="role-policy",
            name="Role Policy",
            description="Requires admin role",
            severity=PolicySeverity.HIGH,
            evaluator=PolicyEvaluatorType.AUTO,
            config={"required_roles": ["admin"]},
        ))
        
        evaluator = create_evaluator(self.registry)
        
        # Ohne Rolle
        context = PolicyContext(
            workflow_id="wf-1",
            step_id="step-1",
            step_name="Test",
            adapter_type="native",
            environment="development",
            user_roles=["user"],
        )
        result = evaluator.evaluate("role-policy", context)
        self.assertEqual(result.decision, PolicyDecision.REJECTED)
        
        # Mit Rolle
        context.user_roles = ["admin", "user"]
        result = evaluator.evaluate("role-policy", context)
        self.assertEqual(result.decision, PolicyDecision.APPROVED)

    def test_evaluate_unknown_policy(self):
        evaluator = create_evaluator(self.registry)
        
        context = PolicyContext(
            workflow_id="wf-1",
            step_id="step-1",
            step_name="Test",
            adapter_type="native",
        )
        
        result = evaluator.evaluate("nonexistent", context)
        self.assertEqual(result.decision, PolicyDecision.ERROR)
        self.assertIn("nicht gefunden", result.reason)

    def test_evaluate_captain_gate_no_callback(self):
        evaluator = create_evaluator(self.registry)
        
        context = PolicyContext(
            workflow_id="wf-1",
            step_id="step-1",
            step_name="Test",
            adapter_type="native",
        )
        
        result = evaluator.evaluate("captain-policy", context)
        self.assertEqual(result.decision, PolicyDecision.ERROR)
        self.assertIn("Kein Gate Callback", result.reason)

    def test_evaluate_captain_gate_with_callback(self):
        mock_callback = MagicMock(return_value="approved")
        evaluator = create_evaluator(self.registry, gate_callback=mock_callback)
        
        context = PolicyContext(
            workflow_id="wf-1",
            step_id="step-1",
            step_name="Test",
            adapter_type="native",
        )
        
        result = evaluator.evaluate("captain-policy", context)
        self.assertEqual(result.decision, PolicyDecision.APPROVED)
        mock_callback.assert_called_once()

    def test_evaluate_captain_gate_rejected(self):
        mock_callback = MagicMock(return_value="rejected")
        evaluator = create_evaluator(self.registry, gate_callback=mock_callback)
        
        context = PolicyContext(
            workflow_id="wf-1",
            step_id="step-1",
            step_name="Test",
            adapter_type="native",
        )
        
        result = evaluator.evaluate("captain-policy", context)
        self.assertEqual(result.decision, PolicyDecision.REJECTED)

    def test_evaluate_multiple_policies(self):
        mock_callback = MagicMock(return_value="approved")
        evaluator = create_evaluator(self.registry, gate_callback=mock_callback)
        
        context = PolicyContext(
            workflow_id="wf-1",
            step_id="step-1",
            step_name="Test",
            adapter_type="native",
        )
        
        results = evaluator.evaluate_multiple(["auto-policy", "captain-policy"], context)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].decision, PolicyDecision.APPROVED)
        self.assertEqual(results[1].decision, PolicyDecision.APPROVED)

    def test_evaluate_multiple_stops_on_reject(self):
        mock_callback = MagicMock(return_value="rejected")
        evaluator = create_evaluator(self.registry, gate_callback=mock_callback)
        
        context = PolicyContext(
            workflow_id="wf-1",
            step_id="step-1",
            step_name="Test",
            adapter_type="native",
        )
        
        results = evaluator.evaluate_multiple(["auto-policy", "captain-policy"], context)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].decision, PolicyDecision.APPROVED)
        self.assertEqual(results[1].decision, PolicyDecision.REJECTED)


class AsyncPolicyEvaluatorTest(unittest.TestCase):
    """Tests für AsyncPolicyEvaluator."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmpdir.name) / "policies.json"
        self.registry = PolicyRegistry(self.store_path)
        self.registry.register(PolicyDefinition(
            id="auto-policy",
            name="Auto Policy",
            description="Auto approve in dev",
            severity=PolicySeverity.MEDIUM,
            evaluator=PolicyEvaluatorType.AUTO,
            config={"environments": ["development"]},
        ))
        self.registry.register(PolicyDefinition(
            id="captain-policy",
            name="Captain Policy",
            description="Captain Gate",
            severity=PolicySeverity.HIGH,
            evaluator=PolicyEvaluatorType.CAPTAIN_GATE,
        ))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_async_evaluate_auto(self):
        async def test():
            evaluator = create_async_evaluator(self.registry)
            context = PolicyContext(
                workflow_id="wf-1",
                step_id="step-1",
                step_name="Test",
                adapter_type="native",
                environment="development",
            )
            result = await evaluator.evaluate("auto-policy", context)
            self.assertEqual(result.decision, PolicyDecision.APPROVED)
        
        asyncio.run(test())

    def test_async_evaluate_captain_gate_async_callback(self):
        async def test():
            async_callback = AsyncMock(return_value="approved")
            evaluator = create_async_evaluator(
                self.registry,
                gate_callback=async_callback,
            )
            
            context = PolicyContext(
                workflow_id="wf-1",
                step_id="step-1",
                step_name="Test",
                adapter_type="native",
            )
            
            result = await evaluator.evaluate("captain-policy", context)
            self.assertEqual(result.decision, PolicyDecision.APPROVED)
            async_callback.assert_called_once()
        
        asyncio.run(test())

    def test_async_evaluate_captain_gate_sync_callback(self):
        async def test():
            mock_callback = MagicMock(return_value="approved")
            evaluator = create_async_evaluator(
                self.registry,
                gate_callback_sync=mock_callback,
            )
            
            context = PolicyContext(
                workflow_id="wf-1",
                step_id="step-1",
                step_name="Test",
                adapter_type="native",
            )
            
            result = await evaluator.evaluate("captain-policy", context)
            self.assertEqual(result.decision, PolicyDecision.APPROVED)
            mock_callback.assert_called_once()
        
        asyncio.run(test())

    def test_async_evaluate_timeout(self):
        async def test():
            async def slow_callback(policy_id, context):
                await asyncio.sleep(2)
                return "approved"
            
            evaluator = create_async_evaluator(
                self.registry,
                gate_callback=slow_callback,
                default_timeout_seconds=0.1,  # Sehr kurzer Timeout
            )
            
            context = PolicyContext(
                workflow_id="wf-1",
                step_id="step-1",
                step_name="Test",
                adapter_type="native",
            )
            
            result = await evaluator.evaluate("captain-policy", context)
            self.assertEqual(result.decision, PolicyDecision.REJECTED)
            self.assertIn("Timeout", result.reason)
        
        asyncio.run(test())

    def test_async_evaluate_no_callback(self):
        async def test():
            evaluator = create_async_evaluator(self.registry)
            
            context = PolicyContext(
                workflow_id="wf-1",
                step_id="step-1",
                step_name="Test",
                adapter_type="native",
            )
            
            result = await evaluator.evaluate("captain-policy", context)
            self.assertEqual(result.decision, PolicyDecision.ERROR)
            self.assertIn("Kein Gate Callback", result.reason)
        
        asyncio.run(test())

    def test_async_evaluate_unknown_policy(self):
        async def test():
            evaluator = create_async_evaluator(self.registry)
            context = PolicyContext(
                workflow_id="wf-1",
                step_id="step-1",
                step_name="Test",
                adapter_type="native",
            )
            result = await evaluator.evaluate("nonexistent", context)
            self.assertEqual(result.decision, PolicyDecision.ERROR)
        
        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()