"""Tests für Adapter Base Classes."""
from __future__ import annotations

import unittest
from dataclasses import dataclass

from sedra_runtime.adapters.adapter_base import (
    AdapterType,
    WorkflowStatus,
    ValidationSeverity,
    GateDecision,
    ValidationIssue,
    ValidationResult,
    DryRunResult,
    ExecutionResult,
    ExecutionContext,
    WorkflowStep,
    WorkflowSpec,
    AdapterRegistry,
)


class AdapterBaseTest(unittest.TestCase):
    """Tests für Adapter Base Classes."""

    def test_adapter_type_enum(self):
        self.assertEqual(AdapterType.NATIVE.value, "native")
        self.assertEqual(AdapterType.N8N.value, "n8n")
        self.assertEqual(AdapterType.HYBRID.value, "hybrid")

    def test_workflow_status_enum(self):
        self.assertEqual(WorkflowStatus.PENDING.value, "pending")
        self.assertEqual(WorkflowStatus.SUCCESS.value, "success")
        self.assertEqual(WorkflowStatus.FAILED.value, "failed")

    def test_validation_result(self):
        result = ValidationResult(valid=True)
        self.assertTrue(result.valid)
        
        result.add_error("test_error", "Error message")
        self.assertFalse(result.valid)
        self.assertEqual(len(result.errors), 1)
        
        result.add_warning("test_warning", "Warning message")
        self.assertEqual(len(result.warnings), 1)
        
        result.add_info("test_info", "Info message")
        self.assertEqual(len([i for i in result.issues if i.severity == ValidationSeverity.INFO]), 1)

    def test_workflow_step(self):
        step = WorkflowStep(
            id="step1",
            name="Test Step",
            type="script",
            config={"command": "echo hello"},
            depends_on=[],
            timeout_ms=5000,
        )
        self.assertEqual(step.id, "step1")
        self.assertEqual(step.type, "script")

    def test_workflow_spec(self):
        spec = WorkflowSpec(
            id="wf1",
            name="Test Workflow",
            adapter_type=AdapterType.NATIVE,
            steps=[
                WorkflowStep(id="s1", name="Step 1", type="script", config={}, depends_on=[]),
                WorkflowStep(id="s2", name="Step 2", type="script", config={}, depends_on=["s1"]),
            ],
        )
        
        self.assertEqual(spec.id, "wf1")
        self.assertEqual(len(spec.steps), 2)
        
        # Dependencies
        s2 = spec.get_step("s2")
        deps = spec.get_dependencies("s2")
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].id, "s1")

    def test_execution_context(self):
        ctx = ExecutionContext(
            workflow_id="wf1",
            adapter_type=AdapterType.NATIVE,
            parameters={"param1": "value1"},
        )
        self.assertEqual(ctx.workflow_id, "wf1")
        self.assertEqual(ctx.parameters["param1"], "value1")
        self.assertFalse(ctx.dry_run)

    def test_validation_issue(self):
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code="test_code",
            message="Test error",
            path="test.path",
        )
        self.assertEqual(issue.severity, ValidationSeverity.ERROR)
        self.assertEqual(issue.code, "test_code")

    def test_dry_run_result(self):
        result = DryRunResult(
            success=True,
            simulated_steps=[{"step_id": "s1", "estimated_duration_ms": 100}],
            estimated_duration_ms=100,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.estimated_duration_ms, 100)

    def test_execution_result(self):
        result = ExecutionResult(
            workflow_id="wf1",
            status=WorkflowStatus.RUNNING,
        )
        self.assertEqual(result.workflow_id, "wf1")
        self.assertEqual(result.status, WorkflowStatus.RUNNING)
        self.assertFalse(result.is_complete)


class AdapterRegistryTest(unittest.TestCase):
    """Tests für AdapterRegistry."""

    def test_registry_creation(self):
        registry = AdapterRegistry()
        self.assertEqual(len(registry.list_adapters()), 0)

    def test_adapter_registration(self):
        registry = AdapterRegistry()
        
        # Mock Adapter
        class MockAdapter:
            adapter_type = AdapterType.NATIVE
            supported_formats = ["yaml", "json"]
            
            def parse(self, source):
                return WorkflowSpec(name="test")
            
            def validate(self, spec):
                return ValidationResult(valid=True)
            
            def dry_run(self, spec, context):
                return DryRunResult(success=True)
            
            async def execute(self, spec, context):
                return ExecutionResult(workflow_id="test", success=True)
            
            def export(self, spec, format):
                return "yaml"
        
        adapter = MockAdapter()
        registry.register(adapter)
        
        self.assertIn(AdapterType.NATIVE, registry.list_adapters())
        self.assertEqual(registry.get(AdapterType.NATIVE), adapter)
        self.assertEqual(registry.get_by_format("yaml"), adapter)
        self.assertEqual(registry.get_by_format("json"), adapter)

    def test_parse_auto(self):
        registry = AdapterRegistry()
        
        # Native adapter mock
        class NativeMock:
            adapter_type = AdapterType.NATIVE
            supported_formats = ["yaml", "json"]
            
            def parse(self, source):
                spec = WorkflowSpec(name="native_parsed")
                return spec
            
            def validate(self, spec):
                return ValidationResult(valid=True)
            
            def dry_run(self, spec, context):
                return DryRunResult(success=True)
            
            async def execute(self, spec, context):
                return ExecutionResult(workflow_id="test", success=True)
            
            def export(self, spec, format):
                return "yaml"
        
        registry.register(NativeMock())
        
        # Test auto-detect für n8n (hat nodes/connections)
        n8n_source = {"nodes": [], "connections": {}}
        # Würde n8n adapter brauchen, aber wir haben nur native
        # So fällt es auf native zurück


class WorkflowSpecTest(unittest.TestCase):
    """Tests für WorkflowSpec Funktionalität."""

    def test_topological_sort_simple(self):
        spec = WorkflowSpec(
            steps=[
                WorkflowStep(id="a", name="A", type="script", config={}, depends_on=[]),
                WorkflowStep(id="b", name="B", type="script", config={}, depends_on=["a"]),
                WorkflowStep(id="c", name="C", type="script", config={}, depends_on=["b"]),
            ]
        )
        
        # Manuell topologische Sortierung testen
        from sedra_runtime.adapters.native.native_adapter import NativeWorkflowAdapter
        adapter = NativeWorkflowAdapter()
        order = adapter._topological_sort(spec)
        
        self.assertEqual([s.id for s in order], ["a", "b", "c"])

    def test_circular_dependency_detection(self):
        spec = WorkflowSpec(
            steps=[
                WorkflowStep(id="a", name="A", type="script", config={}, depends_on=["c"]),
                WorkflowStep(id="b", name="B", type="script", config={}, depends_on=["a"]),
                WorkflowStep(id="c", name="C", type="script", config={}, depends_on=["b"]),
            ]
        )
        
        from sedra_runtime.adapters.native.native_adapter import NativeWorkflowAdapter
        adapter = NativeWorkflowAdapter()
        has_circular = adapter._has_circular_dependencies(spec)
        self.assertTrue(has_circular)

    def test_step_dependencies(self):
        spec = WorkflowSpec(
            steps=[
                WorkflowStep(id="step1", name="Step 1", type="script", config={}, depends_on=[]),
                WorkflowStep(id="step2", name="Step 2", type="script", config={}, depends_on=["step1"]),
                WorkflowStep(id="step3", name="Step 3", type="script", config={}, depends_on=["step1", "step2"]),
            ]
        )
        
        step3 = spec.get_step("step3")
        deps = spec.get_dependencies("step3")
        self.assertEqual(len(deps), 2)
        dep_ids = {d.id for d in deps}
        self.assertEqual(dep_ids, {"step1", "step2"})


if __name__ == "__main__":
    unittest.main()