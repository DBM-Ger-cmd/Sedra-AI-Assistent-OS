"""Tests für Hybrid Workflow Adapter (F2-04 Phase 4)."""
from __future__ import annotations

import unittest
import json
import tempfile
import sys
from io import StringIO
from pathlib import Path

from sedra_runtime.cli import main as cli_main


class HybridAdapterTest(unittest.TestCase):
    """Tests für Hybrid Adapter."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.arch_root = Path("E:/Sedra Umgebung/A1 Sedra Main Branch Entwicklungs umgebung/architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _run_cli(self, *args) -> tuple[int, any]:
        """Führt CLI Command aus und gibt (exit_code, parsed_json) zurück."""
        full_args = ['--root', str(self.root), '--architecture', str(self.arch_root), *args]
        old_argv = sys.argv
        old_stdout = sys.stdout
        try:
            sys.argv = ['sedra', *full_args]
            sys.stdout = StringIO()
            exit_code = cli_main()
            output = sys.stdout.getvalue()
        except SystemExit as e:
            exit_code = e.code
            output = sys.stdout.getvalue()
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout

        try:
            parsed = json.loads(output) if output.strip() else None
        except json.JSONDecodeError:
            parsed = output
        return exit_code, parsed

    def test_hybrid_parse_simple(self):
        """Test parsing simple hybrid workflow."""
        hybrid_workflow = {
            "id": "hybrid-simple",
            "name": "Simple Hybrid Workflow",
            "version": "1.0.0",
            "description": "Test hybrid workflow",
            "parameters": {
                "env": "test"
            },
            "steps": [
                {
                    "id": "native_step",
                    "name": "Native Step",
                    "type": "script",
                    "adapter_type": "native",
                    "config": {
                        "script": "echo 'Native step executed'"
                    },
                    "depends_on": [],
                    "timeout_ms": 5000
                },
                {
                    "id": "n8n_step",
                    "name": "n8n Step",
                    "type": "n8n_node",
                    "adapter_type": "n8n",
                    "config": {
                        "n8n_type": "n8n-nodes-base.httpRequest",
                        "parameters": {
                            "url": "http://api.example.com",
                            "method": "GET"
                        }
                    },
                    "depends_on": ["native_step"],
                    "timeout_ms": 10000
                }
            ]
        }

        workflow_file = self.root / 'hybrid_simple.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'parse', str(workflow_file), '--adapter', 'hybrid')
        self.assertEqual(code, 0)
        self.assertEqual(data['workflow_id'], 'hybrid-simple')
        self.assertEqual(data['name'], 'Simple Hybrid Workflow')
        self.assertEqual(data['steps'], 2)
        self.assertEqual(data['adapter_type'], 'hybrid')

    def test_hybrid_validate_valid(self):
        """Test validating valid hybrid workflow."""
        hybrid_workflow = {
            "id": "hybrid-valid",
            "name": "Valid Hybrid",
            "steps": [
                {"id": "s1", "name": "Native", "type": "delay", "adapter_type": "native", "config": {"delay_ms": 10}, "depends_on": []},
                {"id": "s2", "name": "n8n", "type": "n8n_node", "adapter_type": "n8n", "config": {"n8n_type": "n8n-nodes-base.noOp", "parameters": {}}, "depends_on": ["s1"]}
            ]
        }

        workflow_file = self.root / 'hybrid_valid.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'hybrid')
        self.assertEqual(code, 0)
        self.assertTrue(data['valid'])

    def test_hybrid_validate_mixed_dependencies(self):
        """Test validating hybrid workflow with mixed dependencies."""
        hybrid_workflow = {
            "id": "hybrid-mixed",
            "name": "Mixed Dependencies",
            "steps": [
                {"id": "native1", "name": "Native 1", "type": "script", "adapter_type": "native", "config": {"script": "echo 1"}, "depends_on": []},
                {"id": "n8n1", "name": "n8n 1", "type": "n8n_node", "adapter_type": "n8n", "config": {"n8n_type": "n8n-nodes-base.httpRequest", "parameters": {"url": "http://test"}}, "depends_on": ["native1"]},
                {"id": "native2", "name": "Native 2", "type": "delay", "adapter_type": "native", "config": {"delay_ms": 50}, "depends_on": ["n8n1"]},
                {"id": "n8n2", "name": "n8n 2", "type": "n8n_node", "adapter_type": "n8n", "config": {"n8n_type": "n8n-nodes-base.set", "parameters": {}}, "depends_on": ["native2", "native1"]}
            ]
        }

        workflow_file = self.root / 'hybrid_mixed.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'hybrid')
        self.assertEqual(code, 0)
        self.assertTrue(data['valid'])

    def test_hybrid_dry_run(self):
        """Test dry run hybrid workflow."""
        hybrid_workflow = {
            "id": "hybrid-dryrun",
            "name": "Hybrid Dry Run",
            "steps": [
                {"id": "s1", "name": "Delay", "type": "delay", "adapter_type": "native", "config": {"delay_ms": 100}, "depends_on": [], "timeout_ms": 100},
                {"id": "s2", "name": "HTTP", "type": "n8n_node", "adapter_type": "n8n", "config": {"n8n_type": "n8n-nodes-base.httpRequest", "parameters": {"url": "http://test"}}, "depends_on": ["s1"], "timeout_ms": 2000}
            ]
        }

        workflow_file = self.root / 'hybrid_dryrun.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'dry-run', str(workflow_file), '--adapter', 'hybrid')
        self.assertEqual(code, 0)
        self.assertTrue(data['success'])
        self.assertEqual(data['simulated_steps'], 2)
        self.assertEqual(data['estimated_duration_ms'], 2100)

    def test_hybrid_execute_simple(self):
        """Test executing simple hybrid workflow."""
        hybrid_workflow = {
            "id": "hybrid-exec",
            "name": "Hybrid Execute",
            "steps": [
                {"id": "s1", "name": "Delay", "type": "delay", "adapter_type": "native", "config": {"delay_ms": 10}, "depends_on": []},
                {"id": "s2", "name": "Script", "type": "script", "adapter_type": "native", "config": {"script": "echo done"}, "depends_on": ["s1"]}
            ]
        }

        workflow_file = self.root / 'hybrid_exec.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'execute', str(workflow_file), '--adapter', 'hybrid', '--timeout-ms', '5000')
        self.assertEqual(code, 0)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['steps_executed'], 2)

    def test_hybrid_execute_mixed(self):
        """Test executing hybrid workflow with native and n8n steps (mock)."""
        hybrid_workflow = {
            "id": "hybrid-mixed-exec",
            "name": "Hybrid Mixed Execute",
            "steps": [
                {"id": "native1", "name": "Native Init", "type": "delay", "adapter_type": "native", "config": {"delay_ms": 5}, "depends_on": []},
                {"id": "n8n1", "name": "n8n HTTP", "type": "n8n_node", "adapter_type": "n8n", "config": {"n8n_type": "n8n-nodes-base.httpRequest", "parameters": {"url": "http://mock", "method": "GET"}}, "depends_on": ["native1"]},
                {"id": "native2", "name": "Native Finalize", "type": "script", "adapter_type": "native", "config": {"script": "echo complete"}, "depends_on": ["n8n1"]}
            ]
        }

        workflow_file = self.root / 'hybrid_mixed_exec.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'execute', str(workflow_file), '--adapter', 'hybrid', '--timeout-ms', '10000')
        self.assertEqual(code, 0)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['steps_executed'], 3)

    def test_hybrid_export_json(self):
        """Test exporting hybrid workflow to JSON."""
        hybrid_workflow = {
            "id": "hybrid-export",
            "name": "Hybrid Export",
            "steps": [
                {"id": "s1", "name": "Step 1", "type": "script", "adapter_type": "native", "config": {"script": "echo 1"}, "depends_on": []},
                {"id": "s2", "name": "Step 2", "type": "n8n_node", "adapter_type": "n8n", "config": {"n8n_type": "n8n-nodes-base.noOp", "parameters": {}}, "depends_on": ["s1"]}
            ]
        }

        workflow_file = self.root / 'hybrid_export.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'export', str(workflow_file), '--adapter', 'hybrid', '--format', 'json')
        self.assertEqual(code, 0)
        self.assertEqual(data['id'], 'hybrid-export')
        self.assertEqual(data['steps'][0]['adapter_type'], 'native')
        self.assertEqual(data['steps'][1]['adapter_type'], 'n8n')

    def test_hybrid_export_yaml(self):
        """Test exporting hybrid workflow to YAML."""
        hybrid_workflow = {
            "id": "hybrid-export",
            "name": "Hybrid Export",
            "steps": [
                {"id": "s1", "name": "Step 1", "type": "script", "adapter_type": "native", "config": {"script": "echo 1"}, "depends_on": []}
            ]
        }

        workflow_file = self.root / 'hybrid_export.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'export', str(workflow_file), '--adapter', 'hybrid', '--format', 'yaml')
        self.assertEqual(code, 0)
        self.assertIn('id: hybrid-export', data)
        self.assertIn('adapter_type: native', data)

    def test_hybrid_parallel_execution(self):
        """Test hybrid workflow with parallel-like structure (fan-out)."""
        hybrid_workflow = {
            "id": "hybrid-parallel",
            "name": "Parallel Hybrid",
            "steps": [
                {"id": "init", "name": "Initialize", "type": "script", "adapter_type": "native", "config": {"script": "echo init"}, "depends_on": []},
                {"id": "n8n_a", "name": "n8n A", "type": "n8n_node", "adapter_type": "n8n", "config": {"n8n_type": "n8n-nodes-base.httpRequest", "parameters": {"url": "http://a"}}, "depends_on": ["init"]},
                {"id": "n8n_b", "name": "n8n B", "type": "n8n_node", "adapter_type": "n8n", "config": {"n8n_type": "n8n-nodes-base.httpRequest", "parameters": {"url": "http://b"}}, "depends_on": ["init"]},
                {"id": "native_merge", "name": "Merge Results", "type": "script", "adapter_type": "native", "config": {"script": "echo merged"}, "depends_on": ["n8n_a", "n8n_b"]}
            ]
        }

        workflow_file = self.root / 'hybrid_parallel.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'execute', str(workflow_file), '--adapter', 'hybrid', '--timeout-ms', '10000')
        self.assertEqual(code, 0)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['steps_executed'], 4)

    def test_hybrid_circular_dependency_detection(self):
        """Test that circular dependencies are detected in hybrid workflows."""
        hybrid_workflow = {
            "id": "hybrid-circular",
            "name": "Circular Hybrid",
            "steps": [
                {"id": "a", "name": "A", "type": "script", "adapter_type": "native", "config": {"script": "a"}, "depends_on": ["c"]},
                {"id": "b", "name": "B", "type": "n8n_node", "adapter_type": "n8n", "config": {"n8n_type": "n8n-nodes-base.noOp", "parameters": {}}, "depends_on": ["a"]},
                {"id": "c", "name": "C", "type": "script", "adapter_type": "native", "config": {"script": "c"}, "depends_on": ["b"]}
            ]
        }

        workflow_file = self.root / 'hybrid_circular.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'hybrid')
        self.assertEqual(code, 2)
        self.assertFalse(data['valid'])
        self.assertIn('circular_dependency', data['errors'])

    def test_hybrid_unknown_adapter_type(self):
        """Test validation fails for unknown adapter_type."""
        hybrid_workflow = {
            "id": "hybrid-unknown",
            "name": "Unknown Adapter Type",
            "steps": [
                {"id": "s1", "name": "Step", "type": "script", "adapter_type": "unknown", "config": {}, "depends_on": []}
            ]
        }

        workflow_file = self.root / 'hybrid_unknown.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'hybrid')
        self.assertEqual(code, 2)
        self.assertFalse(data['valid'])
        self.assertIn('unknown_adapter_type', data['errors'])


if __name__ == '__main__':
    unittest.main()