"""Tests für Factory CLI Adapter Commands (F2-04 Phase 2)."""
from __future__ import annotations

import unittest
import json
import tempfile
import sys
from io import StringIO
from pathlib import Path

from sedra_runtime.cli import main as cli_main


class FactoryAdapterCLITest(unittest.TestCase):
    """Tests für Adapter CLI Commands."""

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

    # =========================================================================
    # Adapter List / Register
    # =========================================================================

    def test_adapter_list(self):
        code, data = self._run_cli('factory', 'adapter', 'list')
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)
        adapter_ids = {a['adapter_id'] for a in data}
        self.assertIn('native', adapter_ids)
        self.assertIn('n8n', adapter_ids)
        self.assertIn('hybrid', adapter_ids)

    def test_adapter_register_native(self):
        code, data = self._run_cli('factory', 'adapter', 'register', 'native', '--name', 'MyNative')
        self.assertEqual(code, 0)
        self.assertEqual(data['adapter_id'], 'native')
        self.assertEqual(data['name'], 'MyNative')
        self.assertEqual(data['status'], 'registered')
        self.assertIn('yaml', data['formats'])

    def test_adapter_register_n8n(self):
        code, data = self._run_cli('factory', 'adapter', 'register', 'n8n')
        self.assertEqual(code, 0)
        self.assertEqual(data['adapter_id'], 'n8n')
        self.assertIn('n8n.json', data['formats'])

    def test_adapter_register_hybrid(self):
        code, data = self._run_cli('factory', 'adapter', 'register', 'hybrid')
        self.assertEqual(code, 0)
        self.assertEqual(data['adapter_id'], 'hybrid')

    def test_adapter_register_unknown(self):
        code, data = self._run_cli('factory', 'adapter', 'register', 'unknown')
        # argparse validates choices before our code runs, so this exits with 2
        self.assertEqual(code, 2)

    # =========================================================================
    # Parse Command
    # =========================================================================

    def test_adapter_parse_yaml(self):
        workflow_file = self.root / 'workflow.yaml'
        workflow_file.write_text("""
id: test-wf
name: Test Workflow
steps:
  - id: step1
    name: Step 1
    type: script
    config:
      script: "echo hello"
    depends_on: []
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'parse', str(workflow_file), '--adapter', 'native')
        self.assertEqual(code, 0)
        self.assertEqual(data['workflow_id'], 'test-wf')
        self.assertEqual(data['name'], 'Test Workflow')
        self.assertEqual(data['steps'], 1)
        self.assertEqual(data['adapter_type'], 'native')

    def test_adapter_parse_json(self):
        workflow_file = self.root / 'workflow.json'
        workflow_file.write_text(json.dumps({
            "id": "json-wf",
            "name": "JSON Workflow",
            "steps": [
                {"id": "s1", "name": "Step 1", "type": "http", "config": {"url": "http://test"}, "depends_on": []}
            ]
        }), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'parse', str(workflow_file), '--adapter', 'native')
        self.assertEqual(code, 0)
        self.assertEqual(data['workflow_id'], 'json-wf')
        self.assertEqual(data['steps'], 1)

    def test_adapter_parse_invalid_file(self):
        code, data = self._run_cli('factory', 'adapter', 'parse', 'nonexistent.yaml', '--adapter', 'native')
        self.assertEqual(code, 2)
        self.assertEqual(data['status'], 'refused')

    def test_adapter_parse_invalid_yaml(self):
        workflow_file = self.root / 'bad.yaml'
        workflow_file.write_text("invalid: [unclosed", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'parse', str(workflow_file), '--adapter', 'native')
        self.assertEqual(code, 2)
        self.assertEqual(data['status'], 'refused')

    # =========================================================================
    # Validate Command
    # =========================================================================

    def test_adapter_validate_valid(self):
        workflow_file = self.root / 'valid.yaml'
        workflow_file.write_text("""
id: valid-wf
name: Valid Workflow
steps:
  - id: step1
    name: Step 1
    type: script
    config: {}
    depends_on: []
  - id: step2
    name: Step 2
    type: delay
    config:
      delay_ms: 100
    depends_on: [step1]
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'native')
        self.assertEqual(code, 0)
        self.assertTrue(data['valid'])
        self.assertEqual(data['errors'], [])

    def test_adapter_validate_missing_name(self):
        workflow_file = self.root / 'invalid.yaml'
        workflow_file.write_text("""
id: invalid-wf
name: ""
steps: []
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'native')
        self.assertEqual(code, 2)
        self.assertFalse(data['valid'])
        self.assertIn('missing_name', data['errors'])

    def test_adapter_validate_circular_dependency(self):
        workflow_file = self.root / 'circular.yaml'
        workflow_file.write_text("""
id: circular-wf
name: Circular Workflow
steps:
  - id: a
    name: A
    type: script
    config: {}
    depends_on: [c]
  - id: b
    name: B
    type: script
    config: {}
    depends_on: [a]
  - id: c
    name: C
    type: script
    config: {}
    depends_on: [b]
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'native')
        self.assertEqual(code, 2)
        self.assertFalse(data['valid'])
        self.assertIn('circular_dependency', data['errors'])

    def test_adapter_validate_missing_dependency(self):
        workflow_file = self.root / 'missing_dep.yaml'
        workflow_file.write_text("""
id: missing-dep-wf
name: Missing Dependency
steps:
  - id: step1
    name: Step 1
    type: script
    config: {}
    depends_on: [nonexistent]
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'native')
        self.assertEqual(code, 2)
        self.assertFalse(data['valid'])
        self.assertIn('missing_dependency', data['errors'])

    # =========================================================================
    # Dry Run Command
    # =========================================================================

    def test_adapter_dry_run(self):
        workflow_file = self.root / 'dryrun.yaml'
        workflow_file.write_text("""
id: dryrun-wf
name: Dry Run Test
steps:
  - id: step1
    name: Step 1
    type: script
    config:
      script: "echo test"
    depends_on: []
    timeout_ms: 100
  - id: step2
    name: Step 2
    type: delay
    config:
      delay_ms: 200
    depends_on: [step1]
    timeout_ms: 200
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'dry-run', str(workflow_file), '--adapter', 'native')
        self.assertEqual(code, 0)
        self.assertTrue(data['success'])
        self.assertEqual(data['simulated_steps'], 2)
        self.assertEqual(data['estimated_duration_ms'], 300)

    def test_adapter_dry_run_with_params(self):
        workflow_file = self.root / 'dryrun_params.yaml'
        workflow_file.write_text("""
id: dryrun-params
name: Dry Run with Params
parameters:
  env: test
steps:
  - id: step1
    name: Step 1
    type: script
    config:
      script: "echo {{env}}"
    depends_on: []
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'dry-run', str(workflow_file), '--adapter', 'native', '--params', '{"env": "production"}')
        self.assertEqual(code, 0)
        self.assertTrue(data['success'])

    # =========================================================================
    # Execute Command
    # =========================================================================

    def test_adapter_execute_simple(self):
        workflow_file = self.root / 'execute.yaml'
        workflow_file.write_text("""
id: exec-wf
name: Execute Test
steps:
  - id: step1
    name: Step 1
    type: delay
    config:
      delay_ms: 10
    depends_on: []
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'execute', str(workflow_file), '--adapter', 'native', '--timeout-ms', '5000')
        self.assertEqual(code, 0)
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['success'])
        self.assertEqual(data['steps_executed'], 1)
        self.assertEqual(data['steps_total'], 1)

    def test_adapter_execute_with_dependencies(self):
        workflow_file = self.root / 'exec_deps.yaml'
        workflow_file.write_text("""
id: exec-deps
name: Execute with Deps
steps:
  - id: a
    name: A
    type: delay
    config:
      delay_ms: 5
    depends_on: []
  - id: b
    name: B
    type: delay
    config:
      delay_ms: 5
    depends_on: [a]
  - id: c
    name: C
    type: delay
    config:
      delay_ms: 5
    depends_on: [a, b]
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'execute', str(workflow_file), '--adapter', 'native', '--timeout-ms', '10000')
        self.assertEqual(code, 0)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['steps_executed'], 3)

    def test_adapter_execute_timeout(self):
        workflow_file = self.root / 'exec_timeout.yaml'
        workflow_file.write_text("""
id: exec-timeout
name: Execute Timeout
steps:
  - id: slow
    name: Slow Step
    type: delay
    config:
      delay_ms: 5000
    depends_on: []
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'execute', str(workflow_file), '--adapter', 'native', '--timeout-ms', '100')
        self.assertEqual(code, 2)
        self.assertEqual(data['status'], 'failed')
        self.assertIn('Timeout', data['error'])

    # =========================================================================
    # Export Command
    # =========================================================================

    def test_adapter_export_yaml(self):
        workflow_file = self.root / 'export.yaml'
        workflow_file.write_text("""
id: export-wf
name: Export Test
steps:
  - id: s1
    name: Step 1
    type: script
    config:
      cmd: echo
    depends_on: []
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'export', str(workflow_file), '--adapter', 'native', '--format', 'yaml')
        self.assertEqual(code, 0)
        # Export to stdout returns raw YAML, not JSON
        self.assertIn('id: export-wf', data)
        self.assertIn('name: Export Test', data)

    def test_adapter_export_json(self):
        workflow_file = self.root / 'export.yaml'
        workflow_file.write_text("""
id: export-wf
name: Export Test
steps:
  - id: s1
    name: Step 1
    type: script
    config:
      cmd: echo
    depends_on: []
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'export', str(workflow_file), '--adapter', 'native', '--format', 'json')
        self.assertEqual(code, 0)
        # JSON export to stdout returns raw JSON
        self.assertEqual(data['id'], 'export-wf')
        self.assertEqual(data['steps'][0]['type'], 'script')

    def test_adapter_export_mermaid(self):
        workflow_file = self.root / 'export.yaml'
        workflow_file.write_text("""
id: export-wf
name: Export Test
steps:
  - id: a
    name: Step A
    type: script
    config: {}
    depends_on: []
  - id: b
    name: Step B
    type: delay
    config:
      delay_ms: 100
    depends_on: [a]
""", encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'export', str(workflow_file), '--adapter', 'native', '--format', 'mermaid')
        self.assertEqual(code, 0)
        self.assertIn('```mermaid', data)
        self.assertIn('flowchart TD', data)
        self.assertIn('Step A', data)
        self.assertIn('Step B', data)

    def test_adapter_export_to_file(self):
        workflow_file = self.root / 'export.yaml'
        workflow_file.write_text("""
id: export-wf
name: Export Test
steps:
  - id: s1
    name: Step 1
    type: script
    config: {}
    depends_on: []
""", encoding='utf-8')

        output_file = self.root / 'exported.yaml'
        code, data = self._run_cli('factory', 'adapter', 'export', str(workflow_file), '--adapter', 'native', '--format', 'yaml', '--output', str(output_file))
        self.assertEqual(code, 0)
        self.assertTrue(data['success'])
        self.assertEqual(data['output'], str(output_file))
        self.assertTrue(output_file.exists())

    # =========================================================================
    # n8n Adapter Tests
    # =========================================================================

    def test_adapter_n8n_parse(self):
        n8n_workflow = {
            "name": "n8n Test Workflow",
            "nodes": [
                {
                    "id": "node1",
                    "name": "Start",
                    "type": "n8n-nodes-base.start",
                    "position": [100, 100],
                    "parameters": {}
                },
                {
                    "id": "node2",
                    "name": "HTTP Request",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [300, 100],
                    "parameters": {"url": "http://example.com"}
                }
            ],
            "connections": {
                "node1": {
                    "main": [[{"node": "node2", "type": "main", "index": 0}]]
                }
            },
            "active": False
        }

        workflow_file = self.root / 'n8n_workflow.json'
        workflow_file.write_text(json.dumps(n8n_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'parse', str(workflow_file), '--adapter', 'n8n')
        self.assertEqual(code, 0)
        self.assertEqual(data['workflow_id'], '')
        self.assertEqual(data['name'], 'n8n Test Workflow')
        self.assertEqual(data['steps'], 2)
        self.assertEqual(data['adapter_type'], 'n8n')

    def test_adapter_n8n_validate(self):
        n8n_workflow = {
            "name": "Valid n8n",
            "nodes": [
                {"id": "n1", "name": "Node 1", "type": "n8n-nodes-base.noOp", "position": [0, 0], "parameters": {}}
            ],
            "connections": {},
            "active": False
        }

        workflow_file = self.root / 'n8n_valid.json'
        workflow_file.write_text(json.dumps(n8n_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'n8n')
        self.assertEqual(code, 0)
        self.assertTrue(data['valid'])

    # =========================================================================
    # Hybrid Adapter Tests
    # =========================================================================

    def test_adapter_hybrid_parse(self):
        hybrid_workflow = {
            "id": "hybrid-wf",
            "name": "Hybrid Workflow",
            "steps": [
                {"id": "s1", "name": "Native Step", "type": "script", "adapter_type": "native", "config": {"script": "echo native"}, "depends_on": []},
                {"id": "s2", "name": "n8n Step", "type": "n8n_node", "adapter_type": "n8n", "config": {"n8n_type": "n8n-nodes-base.httpRequest", "parameters": {"url": "http://test"}}, "depends_on": ["s1"]}
            ]
        }

        workflow_file = self.root / 'hybrid.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'parse', str(workflow_file), '--adapter', 'hybrid')
        self.assertEqual(code, 0)
        self.assertEqual(data['workflow_id'], 'hybrid-wf')
        self.assertEqual(data['adapter_type'], 'hybrid')
        self.assertEqual(data['steps'], 2)

    def test_adapter_hybrid_execute(self):
        hybrid_workflow = {
            "id": "hybrid-exec",
            "name": "Hybrid Execute",
            "steps": [
                {"id": "s1", "name": "Delay", "type": "delay", "adapter_type": "native", "config": {"delay_ms": 5}, "depends_on": []},
            ]
        }

        workflow_file = self.root / 'hybrid_exec.json'
        workflow_file.write_text(json.dumps(hybrid_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'execute', str(workflow_file), '--adapter', 'hybrid', '--timeout-ms', '5000')
        self.assertEqual(code, 0)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['steps_executed'], 1)


if __name__ == '__main__':
    unittest.main()