"""Tests für Native Workflow Adapter."""
from __future__ import annotations

import unittest
import yaml
import json
from pathlib import Path

from sedra_runtime.adapters.native.native_adapter import NativeWorkflowAdapter
from sedra_runtime.adapters.adapter_base import (
    AdapterType,
    WorkflowSpec,
    WorkflowStep,
    ExecutionContext,
    ValidationResult,
)


class NativeWorkflowAdapterTest(unittest.TestCase):
    """Tests für NativeWorkflowAdapter."""

    def setUp(self):
        self.adapter = NativeWorkflowAdapter()

    # =========================================================================
    # Parsing Tests
    # =========================================================================

    def test_parse_yaml(self):
        yaml_content = """
        id: wf1
        name: Test Workflow
        version: "1.0"
        steps:
          - id: step1
            name: Step 1
            type: script
            config:
              script: "echo hello"
            depends_on: []
        """
        spec = self.adapter.parse(yaml_content)
        self.assertEqual(spec.id, "wf1")
        self.assertEqual(spec.name, "Test Workflow")
        self.assertEqual(len(spec.steps), 1)
        self.assertEqual(spec.steps[0].id, "step1")
        self.assertEqual(spec.steps[0].type, "script")

    def test_parse_json(self):
        json_content = """
        {
            "id": "wf2",
            "name": "JSON Workflow",
            "steps": [
                {"id": "s1", "name": "Step 1", "type": "http", "config": {"url": "http://example.com"}, "depends_on": []}
            ]
        }
        """
        spec = self.adapter.parse(json_content)
        self.assertEqual(spec.id, "wf2")
        self.assertEqual(spec.steps[0].type, "http")

    def test_parse_dict(self):
        data = {
            "id": "wf3",
            "name": "Dict Workflow",
            "steps": [
                {"id": "s1", "name": "Step 1", "type": "condition", "config": {"expression": "true"}, "depends_on": []}
            ]
        }
        spec = self.adapter.parse(data)
        self.assertEqual(spec.id, "wf3")
        self.assertEqual(spec.steps[0].type, "condition")

    def test_parse_invalid_yaml(self):
        invalid_yaml = "invalid: [unclosed"
        with self.assertRaises(ValueError):
            self.adapter.parse(invalid_yaml)

    # =========================================================================
    # Validation Tests
    # =========================================================================

    def test_validate_valid_workflow(self):
        spec = WorkflowSpec(
            name="Valid Workflow",
            steps=[
                WorkflowStep(id="s1", name="Step 1", type="script", config={}, depends_on=[]),
                WorkflowStep(id="s2", name="Step 2", type="script", config={}, depends_on=["s1"]),
            ]
        )
        result = self.adapter.validate(spec)
        self.assertTrue(result.valid)

    def test_validate_missing_name(self):
        spec = WorkflowSpec(name="", steps=[])
        result = self.adapter.validate(spec)
        self.assertFalse(result.valid)
        self.assertTrue(any("missing_name" in i.code for i in result.errors))

    def test_validate_duplicate_step_ids(self):
        spec = WorkflowSpec(
            steps=[
                WorkflowStep(id="s1", name="Step 1", type="script", config={}, depends_on=[]),
                WorkflowStep(id="s1", name="Step 2", type="script", config={}, depends_on=[]),
            ]
        )
        result = self.adapter.validate(spec)
        self.assertFalse(result.valid)
        self.assertTrue(any("duplicate_step_id" in i.code for i in result.errors))

    def test_validate_unknown_step_type(self):
        spec = WorkflowSpec(
            steps=[WorkflowStep(id="s1", name="Step 1", type="unknown_type", config={}, depends_on=[])]
        )
        result = self.adapter.validate(spec)
        self.assertFalse(result.valid)
        self.assertTrue(any("unknown_step_type" in i.code for i in result.errors))

    def test_validate_missing_dependency(self):
        spec = WorkflowSpec(
            steps=[
                WorkflowStep(id="s1", name="Step 1", type="script", config={}, depends_on=[]),
                WorkflowStep(id="s2", name="Step 2", type="script", config={}, depends_on=["nonexistent"]),
            ]
        )
        result = self.adapter.validate(spec)
        self.assertFalse(result.valid)
        self.assertTrue(any("missing_dependency" in i.code for i in result.errors))

    def test_validate_circular_dependency(self):
        spec = WorkflowSpec(
            steps=[
                WorkflowStep(id="a", name="A", type="script", config={}, depends_on=["c"]),
                WorkflowStep(id="b", name="B", type="script", config={}, depends_on=["a"]),
                WorkflowStep(id="c", name="C", type="script", config={}, depends_on=["b"]),
            ]
        )
        result = self.adapter.validate(spec)
        self.assertFalse(result.valid)
        self.assertTrue(any("circular_dependency" in i.code for i in result.errors))

    # =========================================================================
    # Dry Run Tests
    # =========================================================================

    def test_dry_run(self):
        spec = WorkflowSpec(
            name="Dry Run Test",
            steps=[
                WorkflowStep(id="s1", name="Step 1", type="script", config={}, depends_on=[], timeout_ms=100),
                WorkflowStep(id="s2", name="Step 2", type="http", config={"url": "http://example.com"}, depends_on=["s1"], timeout_ms=200),
            ]
        )
        context = ExecutionContext(workflow_id="test", adapter_type=AdapterType.NATIVE)
        result = self.adapter.dry_run(spec, context)

        self.assertTrue(result.success)
        self.assertEqual(len(result.simulated_steps), 2)
        self.assertEqual(result.estimated_duration_ms, 300)
        self.assertIn("memory_mb", result.estimated_resources)

    # =========================================================================
    # Export Tests
    # =========================================================================

    def test_export_yaml(self):
        spec = WorkflowSpec(
            id="export1",
            name="Export Test",
            steps=[WorkflowStep(id="s1", name="Step 1", type="script", config={"cmd": "echo"}, depends_on=[])],
        )
        yaml_output = self.adapter.export(spec, "yaml")
        self.assertIn("id: export1", yaml_output)
        self.assertIn("name: Export Test", yaml_output)
        self.assertIn("script", yaml_output)

    def test_export_json(self):
        spec = WorkflowSpec(
            id="export2",
            name="JSON Export",
            steps=[WorkflowStep(id="s1", name="Step 1", type="http", config={"url": "http://test"}, depends_on=[])],
        )
        json_output = self.adapter.export(spec, "json")
        data = json.loads(json_output)
        self.assertEqual(data["id"], "export2")
        self.assertEqual(data["steps"][0]["type"], "http")

    def test_export_mermaid(self):
        spec = WorkflowSpec(
            steps=[
                WorkflowStep(id="a", name="Step A", type="script", config={}, depends_on=[]),
                WorkflowStep(id="b", name="Step B", type="script", config={}, depends_on=["a"]),
            ]
        )
        mermaid = self.adapter.export(spec, "mermaid")
        self.assertIn("```mermaid", mermaid)
        self.assertIn("flowchart TD", mermaid)
        self.assertIn("Step A", mermaid)
        self.assertIn("Step B", mermaid)

    def test_export_invalid_format(self):
        spec = WorkflowSpec(steps=[])
        with self.assertRaises(ValueError):
            self.adapter.export(spec, "invalid_format")


class NativeAdapterExecutionTest(unittest.TestCase):
    """Tests für Native Adapter Execution (Mock/Integration)."""

    def setUp(self):
        self.adapter = NativeWorkflowAdapter()

    def test_execution_context_creation(self):
        ctx = ExecutionContext(
            workflow_id="exec_test",
            adapter_type=AdapterType.NATIVE,
            parameters={"key": "value"},
            dry_run=True,
        )
        self.assertEqual(ctx.workflow_id, "exec_test")
        self.assertTrue(ctx.dry_run)

    async def test_execute_simple_workflow(self):
        spec = WorkflowSpec(
            id="exec_wf",
            name="Execution Test",
            steps=[
                WorkflowStep(id="s1", name="Step 1", type="delay", config={"delay_ms": 10}, depends_on=[]),
            ],
        )
        context = ExecutionContext(workflow_id="exec_test", adapter_type=AdapterType.NATIVE)
        result = await self.adapter.execute(spec, context)

        self.assertEqual(result.workflow_id, "exec_wf")
        self.assertEqual(result.steps_executed, 1)
        self.assertTrue(result.is_complete)


if __name__ == "__main__":
    unittest.main()