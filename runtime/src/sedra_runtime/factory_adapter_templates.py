"""Factory Templates für Workflow Adapters (F2-04 Phase 3)."""

from pathlib import Path


# =============================================================================
# Adapter Project Template
# =============================================================================

ADAPTER_PROJECT_TEMPLATE = {
    "README.md": """# {{PROJECT_NAME}}

Workflow Adapter Projekt für SEDRA Factory.

## Adapter Types

- **native** - In-Process YAML/JSON Workflows
- **n8n** - n8n Workflow JSON Import/Export/Execution
- **hybrid** - Kombinierte Native + n8n Workflows

## Structure

```
{{PROJECT_NAME}}/
├── adapters/
│   ├── native/
│   │   └── workflows/
│   ├── n8n/
│   │   └── workflows/
│   └── hybrid/
│       └── workflows/
├── factory_registry.json
└── local_config/
    └── evidence/
        └── evidence.db
```

## Usage

```bash
# Adapter registrieren
sedra factory adapter register native
sedra factory adapter register n8n
sedra factory adapter register hybrid

# Workflow ausführen
sedra factory adapter execute workflow.yaml --adapter native
sedra factory adapter execute workflow.json --adapter n8n
sedra factory adapter execute workflow.json --adapter hybrid
```

## Factory Integration

Dieses Projekt kann als Factory Type registriert werden:

```bash
sedra factory register adapter-project "Adapter Project" --functions "parse,validate,execute,export" --gate
sedra factory build-project adapter-project my-adapter-project --gate
```
""",
    "factory_templates/adapter_project/README.md": """# {{PROJECT_NAME}} - Adapter Project

Factory Template für Workflow Adapter Projekte.

## Struktur

```
{{PROJECT_NAME}}/
├── adapters/
│   ├── native/
│   │   └── workflows/
│   ├── n8n/
│   │   └── workflows/
│   └── hybrid/
│       └── workflows/
├── .gitignore
├── pyproject.toml
└── local_config/
    ├── factory_registry.json
    └── evidence/
        └── evidence.db
```

## Factory Type Registration

```json
{
  "typ_id": "adapter-project",
  "name": "Workflow Adapter Project",
  "funktionen": ["parse", "validate", "execute", "export", "benchmark"],
  "manifest_ref": "adapters/manifest.json",
  "gate_freigabe": true
}
```
""",
    "factory_templates/adapter_project/.gitignore": """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.env

# SEDRA
local_config/
runtime_data/
*.log

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
""",
    "factory_templates/adapter_project/pyproject.toml": """[project]
name = "{{PROJECT_NAME_SANITIZED}}"
version = "0.1.0"
description = "SEDRA Workflow Adapter Project"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "asyncio",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
]
n8n = [
    "aiohttp>=3.8",
]

[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
""",
    "factory_templates/adapter_project/adapters/native/workflows/.gitkeep": "",
    "factory_templates/adapter_project/adapters/n8n/workflows/.gitkeep": "",
    "factory_templates/adapter_project/adapters/hybrid/workflows/.gitkeep": "",
    "factory_templates/adapter_project/local_config/factory_registry.json": "{}",
}


# =============================================================================
# Native Workflow Template
# =============================================================================

NATIVE_WORKFLOW_TEMPLATE = """id: {{WORKFLOW_ID}}
name: {{WORKFLOW_NAME}}
version: "1.0.0"
description: {{WORKFLOW_DESCRIPTION}}
parameters:
  env: development
  debug: false
steps:
  - id: step1
    name: Initialize
    type: script
    config:
      script: |
        echo "Starting workflow: {{WORKFLOW_NAME}}"
        echo "Environment: {{env}}"
    depends_on: []
    timeout_ms: 5000
  - id: step2
    name: Process
    type: delay
    config:
      delay_ms: 100
    depends_on: [step1]
    timeout_ms: 5000
  - id: step3
    name: Finalize
    type: script
    config:
      script: |
        echo "Workflow {{WORKFLOW_NAME}} completed successfully"
    depends_on: [step2]
    timeout_ms: 5000
"""


# =============================================================================
# n8n Workflow Template
# =============================================================================

N8N_WORKFLOW_TEMPLATE = """{
  "name": "{{WORKFLOW_NAME}}",
  "nodes": [
    {
      "id": "start",
      "name": "Start",
      "type": "n8n-nodes-base.start",
      "position": [250, 300],
      "parameters": {}
    },
    {
      "id": "http-request",
      "name": "HTTP Request",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 300],
      "parameters": {
        "url": "https://api.example.com/{{env}}",
        "method": "GET",
        "options": {}
      }
    },
    {
      "id": "set",
      "name": "Set Response",
      "type": "n8n-nodes-base.set",
      "position": [650, 300],
      "parameters": {
        "keepOnlySet": true,
        "values": {
          "string": [
            {
              "name": "workflow",
              "value": "{{WORKFLOW_NAME}}"
            },
            {
              "name": "timestamp",
              "value": "={{$now}}"
            }
          ]
        }
      }
    }
  ],
  "connections": {
    "Start": {
      "main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]
    },
    "HTTP Request": {
      "main": [[{"node": "Set Response", "type": "main", "index": 0}]]
    }
  },
  "active": false,
  "settings": {},
  "id": "{{WORKFLOW_ID}}"
}"""


# =============================================================================
# Hybrid Workflow Template
# =============================================================================

HYBRID_WORKFLOW_TEMPLATE = """{
  "id": "{{WORKFLOW_ID}}",
  "name": "{{WORKFLOW_NAME}}",
  "version": "1.0.0",
  "description": "{{WORKFLOW_DESCRIPTION}}",
  "parameters": {
    "env": "development",
    "api_base": "https://api.example.com"
  },
  "steps": [
    {
      "id": "native_init",
      "name": "Native Initialize",
      "type": "script",
      "adapter_type": "native",
      "config": {
        "script": "echo 'Hybrid workflow started: {{WORKFLOW_NAME}}'"
      },
      "depends_on": [],
      "timeout_ms": 5000
    },
    {
      "id": "n8n_api_call",
      "name": "n8n API Call",
      "type": "n8n_node",
      "adapter_type": "n8n",
      "config": {
        "n8n_type": "n8n-nodes-base.httpRequest",
        "parameters": {
          "url": "{{api_base}}/data",
          "method": "GET"
        }
      },
      "depends_on": ["native_init"],
      "timeout_ms": 10000
    },
    {
      "id": "native_process",
      "name": "Native Process Result",
      "type": "script",
      "adapter_type": "native",
      "config": {
        "script": "echo 'Processing n8n result...'\necho 'Done'"
      },
      "depends_on": ["n8n_api_call"],
      "timeout_ms": 5000
    }
  ]
}"""


# =============================================================================
# Factory Registry Entry für Adapter
# =============================================================================

ADAPTER_FACTORY_TYPES = {
    "adapter-native": {
        "typ_id": "adapter-native",
        "name": "Native Workflow Adapter",
        "funktionen": ["parse", "validate", "dry-run", "execute", "export", "benchmark"],
        "manifest_ref": "adapters/native/manifest.json",
        "description": "In-Process YAML/JSON Workflow Execution mit Async/Retry/Timeout"
    },
    "adapter-n8n": {
        "typ_id": "adapter-n8n",
        "name": "n8n Workflow Adapter",
        "funktionen": ["parse", "validate", "dry-run", "execute", "export"],
        "manifest_ref": "adapters/n8n/manifest.json",
        "description": "n8n Workflow JSON Import/Export/Execution via n8n CLI"
    },
    "adapter-hybrid": {
        "typ_id": "adapter-hybrid",
        "name": "Hybrid Workflow Adapter",
        "funktionen": ["parse", "validate", "dry-run", "execute", "export"],
        "manifest_ref": "adapters/hybrid/manifest.json",
        "description": "Orchestrator für gemischte Native + n8n Workflows"
    },
    "adapter-project": {
        "typ_id": "adapter-project",
        "name": "Workflow Adapter Project",
        "funktionen": ["parse", "validate", "execute", "export", "benchmark"],
        "manifest_ref": "adapters/manifest.json",
        "description": "Vollständiges Adapter-Projekt mit allen drei Adapter-Typen"
    },
}


def create_adapter_templates(builder, project_path: Path, project_name: str):
    """Erstellt Adapter-Templates in einem Projekt."""
    sanitized = project_name.replace("-", "_").replace(" ", "_")
    
    # Adapter-Verzeichnisse
    adapters_dir = project_path / "adapters"
    (adapters_dir / "native" / "workflows").mkdir(parents=True, exist_ok=True)
    (adapters_dir / "n8n" / "workflows").mkdir(parents=True, exist_ok=True)
    (adapters_dir / "hybrid" / "workflows").mkdir(parents=True, exist_ok=True)
    
    # Example Workflows
    workflow_id = f"{sanitized}-workflow"
    workflow_name = project_name.replace("-", " ").title()
    workflow_desc = f"Example workflow for {project_name}"
    
    # Native Workflow
    native_content = NATIVE_WORKFLOW_TEMPLATE.replace("{{WORKFLOW_ID}}", workflow_id)\
        .replace("{{WORKFLOW_NAME}}", workflow_name)\
        .replace("{{WORKFLOW_DESCRIPTION}}", workflow_desc)
    (adapters_dir / "native" / "workflows" / f"{workflow_id}.yaml").write_text(native_content)
    
    # n8n Workflow
    n8n_content = N8N_WORKFLOW_TEMPLATE.replace("{{WORKFLOW_ID}}", workflow_id)\
        .replace("{{WORKFLOW_NAME}}", workflow_name)\
        .replace("{{env}}", "development")
    (adapters_dir / "n8n" / "workflows" / f"{workflow_id}.json").write_text(n8n_content)
    
    # Hybrid Workflow
    hybrid_content = HYBRID_WORKFLOW_TEMPLATE.replace("{{WORKFLOW_ID}}", workflow_id)\
        .replace("{{WORKFLOW_NAME}}", workflow_name)\
        .replace("{{WORKFLOW_DESCRIPTION}}", workflow_desc)
    (adapters_dir / "hybrid" / "workflows" / f"{workflow_id}.json").write_text(hybrid_content)
    
    # Manifest
    manifest = {
        "version": "1.0.0",
        "adapters": {
            "native": {
                "path": "adapters/native/workflows",
                "format": "yaml",
                "workflows": [f"{workflow_id}.yaml"]
            },
            "n8n": {
                "path": "adapters/n8n/workflows",
                "format": "json",
                "workflows": [f"{workflow_id}.json"]
            },
            "hybrid": {
                "path": "adapters/hybrid/workflows",
                "format": "json",
                "workflows": [f"{workflow_id}.json"]
            }
        }
    }
    import json
    (adapters_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    
    return True