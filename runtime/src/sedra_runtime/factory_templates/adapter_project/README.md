# {{PROJECT_NAME}} - Adapter Project

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