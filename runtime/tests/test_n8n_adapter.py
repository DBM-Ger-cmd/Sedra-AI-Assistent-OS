"""Tests für n8n Workflow Adapter (F2-04 Phase 4)."""
from __future__ import annotations

import unittest
import json
import tempfile
import sys
from io import StringIO
from pathlib import Path

from sedra_runtime.cli import main as cli_main


class N8nAdapterTest(unittest.TestCase):
    """Tests für n8n Adapter."""

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

    def test_n8n_parse_simple(self):
        """Test parsing simple n8n workflow."""
        n8n_workflow = {
            "name": "Simple n8n Workflow",
            "nodes": [
                {
                    "id": "start",
                    "name": "Start",
                    "type": "n8n-nodes-base.start",
                    "position": [250, 300],
                    "parameters": {}
                },
                {
                    "id": "noop",
                    "name": "No Operation",
                    "type": "n8n-nodes-base.noOp",
                    "position": [450, 300],
                    "parameters": {}
                }
            ],
            "connections": {
                "Start": {
                    "main": [[{"node": "No Operation", "type": "main", "index": 0}]]
                }
            },
            "active": False,
            "settings": {},
            "id": "test-workflow"
        }

        workflow_file = self.root / 'simple_n8n.json'
        workflow_file.write_text(json.dumps(n8n_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'parse', str(workflow_file), '--adapter', 'n8n')
        self.assertEqual(code, 0)
        self.assertEqual(data['name'], 'Simple n8n Workflow')
        self.assertEqual(data['steps'], 2)
        self.assertEqual(data['adapter_type'], 'n8n')

    def test_n8n_validate_valid(self):
        """Test validating valid n8n workflow."""
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

    def test_n8n_validate_missing_name(self):
        """Test validating n8n workflow without name."""
        n8n_workflow = {
            "name": "",
            "nodes": [],
            "connections": {},
            "active": False
        }

        workflow_file = self.root / 'n8n_invalid.json'
        workflow_file.write_text(json.dumps(n8n_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'n8n')
        self.assertEqual(code, 2)
        self.assertFalse(data['valid'])
        self.assertIn('missing_name', data['errors'])

    def test_n8n_dry_run(self):
        """Test dry run n8n workflow."""
        n8n_workflow = {
            "name": "Dry Run n8n",
            "nodes": [
                {"id": "n1", "name": "HTTP Request", "type": "n8n-nodes-base.httpRequest", "position": [0, 0], "parameters": {"url": "http://test"}},
                {"id": "n2", "name": "Set", "type": "n8n-nodes-base.set", "position": [200, 0], "parameters": {}}
            ],
            "connections": {
                "HTTP Request": {
                    "main": [[{"node": "Set", "type": "main", "index": 0}]]
                }
            },
            "active": False
        }

        workflow_file = self.root / 'n8n_dryrun.json'
        workflow_file.write_text(json.dumps(n8n_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'dry-run', str(workflow_file), '--adapter', 'n8n')
        self.assertEqual(code, 0)
        self.assertTrue(data['success'])
        self.assertEqual(data['simulated_steps'], 2)
        self.assertGreater(data['estimated_duration_ms'], 0)

    def test_n8n_export_json(self):
        """Test exporting n8n workflow to JSON."""
        n8n_workflow = {
            "name": "Export Test",
            "nodes": [
                {"id": "n1", "name": "Start", "type": "n8n-nodes-base.start", "position": [0, 0], "parameters": {}}
            ],
            "connections": {},
            "active": False
        }

        workflow_file = self.root / 'n8n_export.json'
        workflow_file.write_text(json.dumps(n8n_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'export', str(workflow_file), '--adapter', 'n8n', '--format', 'json')
        self.assertEqual(code, 0)
        self.assertEqual(data['name'], 'Export Test')
        self.assertEqual(len(data['nodes']), 1)

    def test_n8n_export_yaml(self):
        """Test exporting n8n workflow to YAML."""
        n8n_workflow = {
            "name": "Export Test",
            "nodes": [
                {"id": "n1", "name": "Start", "type": "n8n-nodes-base.start", "position": [0, 0], "parameters": {}}
            ],
            "connections": {},
            "active": False
        }

        workflow_file = self.root / 'n8n_export.json'
        workflow_file.write_text(json.dumps(n8n_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'export', str(workflow_file), '--adapter', 'n8n', '--format', 'yaml')
        self.assertEqual(code, 0)
        self.assertIn('name: Export Test', data)

    def test_n8n_export_n8n_json(self):
        """Test exporting n8n workflow to n8n.json format."""
        n8n_workflow = {
            "name": "Export Test",
            "nodes": [
                {"id": "n1", "name": "Start", "type": "n8n-nodes-base.start", "position": [0, 0], "parameters": {}}
            ],
            "connections": {},
            "active": False
        }

        workflow_file = self.root / 'n8n_export.json'
        workflow_file.write_text(json.dumps(n8n_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'export', str(workflow_file), '--adapter', 'n8n', '--format', 'n8n.json')
        self.assertEqual(code, 0)
        self.assertEqual(data['name'], 'Export Test')
        self.assertIn('nodes', data)
        self.assertIn('connections', data)

    def test_n8n_http_request_workflow(self):
        """Test n8n workflow with HTTP Request node."""
        n8n_workflow = {
            "name": "API Workflow",
            "nodes": [
                {
                    "id": "webhook",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "position": [250, 300],
                    "parameters": {
                        "httpMethod": "POST",
                        "path": "api/webhook",
                        "options": {}
                    }
                },
                {
                    "id": "http",
                    "name": "HTTP Request",
                    "type": "n8n-nodes-base.httpRequest",
                    "position": [500, 300],
                    "parameters": {
                        "url": "https://api.example.com/data",
                        "method": "GET",
                        "options": {}
                    }
                },
                {
                    "id": "respond",
                    "name": "Respond to Webhook",
                    "type": "n8n-nodes-base.respondToWebhook",
                    "position": [750, 300],
                    "parameters": {
                        "options": {},
                        "respondWith": "json",
                        "responseData": {
                            "json": "{{$json}}"
                        }
                    }
                }
            ],
            "connections": {
                "Webhook": {
                    "main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]
                },
                "HTTP Request": {
                    "main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]
                }
            },
            "active": False
        }

        workflow_file = self.root / 'n8n_api.json'
        workflow_file.write_text(json.dumps(n8n_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'parse', str(workflow_file), '--adapter', 'n8n')
        self.assertEqual(code, 0)
        self.assertEqual(data['steps'], 3)
        self.assertEqual(data['adapter_type'], 'n8n')

    def test_n8n_conditional_workflow(self):
        """Test n8n workflow with IF node (conditional)."""
        n8n_workflow = {
            "name": "Conditional Workflow",
            "nodes": [
                {"id": "start", "name": "Start", "type": "n8n-nodes-base.start", "position": [0, 0], "parameters": {}},
                {"id": "if", "name": "IF", "type": "n8n-nodes-base.if", "position": [200, 0], "parameters": {"conditions": {"string": [{"value1": "{{$json.status}}", "operation": "equal", "value2": "active"}]}}},
                {"id": "true", "name": "True Path", "type": "n8n-nodes-base.noOp", "position": [400, -100], "parameters": {}},
                {"id": "false", "name": "False Path", "type": "n8n-nodes-base.noOp", "position": [400, 100], "parameters": {}}
            ],
            "connections": {
                "Start": {
                    "main": [[{"node": "IF", "type": "main", "index": 0}]]
                },
                "IF": {
                    "main": [
                        [{"node": "True Path", "type": "main", "index": 0}],
                        [{"node": "False Path", "type": "main", "index": 0}]
                    ]
                }
            },
            "active": False
        }

        workflow_file = self.root / 'n8n_conditional.json'
        workflow_file.write_text(json.dumps(n8n_workflow, indent=2), encoding='utf-8')

        code, data = self._run_cli('factory', 'adapter', 'validate', str(workflow_file), '--adapter', 'n8n')
        self.assertEqual(code, 0)
        self.assertTrue(data['valid'])


if __name__ == '__main__':
    unittest.main()