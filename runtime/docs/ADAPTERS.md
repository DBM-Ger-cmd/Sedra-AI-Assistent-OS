# SEDRA Factory Adapters — Dokumentation

## Übersicht

SEDRA Factory Adapters bieten eine einheitliche Schnittstelle für Workflow-Ausführung über verschiedene Backends:

| Adapter | Format | Backend | Use Case |
|---------|--------|---------|----------|
| **Native** | YAML/JSON | In-Process (Python) | Schnelle, lokale Workflows ohne externe Dependencies |
| **n8n** | JSON | n8n CLI / REST API | Visuelle Workflow-Editor Integration, komplexe Automatisierungen |
| **Hybrid** | JSON | Native + n8n | Gemischte Workflows mit Native Performance + n8n Features |

---

## Quick Start

### Adapter registrieren

```bash
# Alle Adapter registrieren
sedra factory adapter register native
sedra factory adapter register n8n
sedra factory adapter register hybrid

# Oder als Factory Type (persistiert)
sedra factory register adapter-project "Adapter Project" --functions "parse,validate,execute,export,benchmark" --gate
sedra factory build-adapter-project adapter-project my-adapter-project --gate
```

### Workflow ausführen

```bash
# Native Workflow (YAML)
sedra factory adapter execute workflow.yaml --adapter native

# n8n Workflow (JSON)
sedra factory adapter execute workflow.json --adapter n8n

# Hybrid Workflow (JSON mit adapter_type pro Step)
sedra factory adapter execute workflow.json --adapter hybrid
```

---

## Native Adapter

### Format (YAML)

```yaml
id: my-workflow
name: My Workflow
version: "1.0.0"
description: "Beispiel Workflow"
parameters:
  env: development
  debug: false
steps:
  - id: step1
    name: Initialize
    type: script
    config:
      script: |
        echo "Starting: {{env}}"
    depends_on: []
    timeout_ms: 5000
  - id: step2
    name: Process Data
    type: delay
    config:
      delay_ms: 100
    depends_on: [step1]
    timeout_ms: 5000
  - id: step3
    name: Finalize
    type: script
    config:
      script: echo "Done"
    depends_on: [step2]
    timeout_ms: 5000
```

### Step Types

| Type | Beschreibung | Config |
|------|--------------|--------|
| `script` | Python/Shell Script ausführen | `script: "echo hello"` |
| `http` | HTTP Request | `url`, `method`, `headers`, `body` |
| `condition` | Bedingung evaluieren | `expression: "true"` |
| `delay` | Warten | `delay_ms: 1000` |
| `parallel` | Sub-Steps parallel | `steps: [...]` |
| `loop` | Iteration | `iterations: 3, steps: [...]` |
| `native_function` | Registrierte Funktion | `function: "my_func", args: [], kwargs: {}` |

### Policies (Captain Gates)

```yaml
steps:
  - id: critical_step
    name: Critical Operation
    type: script
    config:
      script: "dangerous_operation"
    policies: ["production-deploy", "data-migration"]  # Erfordert Captain Approval
    depends_on: []
```

---

## n8n Adapter

### Format (n8n JSON)

```json
{
  "name": "API Workflow",
  "nodes": [
    {
      "id": "webhook",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300],
      "parameters": {
        "httpMethod": "POST",
        "path": "api/webhook"
      }
    },
    {
      "id": "http",
      "name": "HTTP Request",
      "type": "n8n-nodes-base.httpRequest",
      "position": [500, 300],
      "parameters": {
        "url": "https://api.example.com/data",
        "method": "GET"
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]
    }
  },
  "active": false
}
```

### Voraussetzungen

- n8n CLI installiert: `npm install -g n8n`
- Oder n8n REST API erreichbar (Standard: `http://localhost:5678`)

### Credentials (nur Referenzen!)

```json
{
  "name": "Secure Workflow",
  "nodes": [
    {
      "id": "db",
      "name": "Database Query",
      "type": "n8n-nodes-base.postgres",
      "credentials": {
        "postgres": {
          "id": "cred-123",
          "name": "Production DB"
        }
      }
    }
  ]
}
```

---

## Hybrid Adapter

### Format

```json
{
  "id": "hybrid-workflow",
  "name": "Hybrid Workflow",
  "version": "1.0.0",
  "parameters": {
    "env": "production",
    "api_base": "https://api.example.com"
  },
  "steps": [
    {
      "id": "native_init",
      "name": "Native Initialize",
      "type": "script",
      "adapter_type": "native",
      "config": {
        "script": "echo 'Starting hybrid workflow'"
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
}
```

### Architektur

```
┌─────────────────────────────────────┐
│        Hybrid Workflow              │
├─────────────────────────────────────┤
│  Step 1: native (script)            │
│  Step 2: n8n (httpRequest)          │
│  Step 3: native (script)            │
└─────────────────────────────────────┘
         │              │
         ▼              ▼
    ┌─────────┐    ┌─────────┐
    │ Native  │    │  n8n    │
    │ Adapter │    │ Adapter │
    └─────────┘    └─────────┘
```

---

## CLI Referenz

### Adapter Commands

```bash
# Adapter registrieren
sedra factory adapter register <native|n8n|hybrid> [--name <custom>]

# Adapter auflisten
sedra factory adapter list

# Workflow parsen
sedra factory adapter parse <file> [--adapter <native|n8n|hybrid>]

# Workflow validieren
sedra factory adapter validate <file> [--adapter <native|n8n|hybrid>]

# Dry Run
sedra factory adapter dry-run <file> [--adapter <native|n8n|hybrid>] [--params '{}'] [--timeout-ms 300000]

# Workflow ausführen
sedra factory adapter execute <file> [--adapter <native|n8n|hybrid>] [--params '{}'] [--timeout-ms 300000]

# Workflow exportieren
sedra factory adapter export <file> [--adapter <native|n8n|hybrid>] [--format <yaml|json|mermaid|n8n.json>] [--output <file>]
```

### Factory Integration

```bash
# Factory Types für Adapter
sedra factory register adapter-native "Native Adapter" --functions "parse,validate,dry-run,execute,export,benchmark" --gate
sedra factory register adapter-n8n "n8n Adapter" --functions "parse,validate,dry-run,execute,export" --gate
sedra factory register adapter-hybrid "Hybrid Adapter" --functions "parse,validate,dry-run,execute,export" --gate
sedra factory register adapter-project "Adapter Project" --functions "parse,validate,execute,export,benchmark" --gate

# Adapter Project bauen
sedra factory build-adapter-project adapter-project my-project --gate

# Benchmarks
sedra factory benchmark run adapter-native --variant default --iterations 3 --gate
sedra factory benchmark compare adapter-native --variants "default,optimized" --iterations 3 --gate
```

---

## Factory Studio Integration (MOD-04)

### Project Browser

Adapter-Projekte werden im Factory Studio unter "Adapter Projects" angezeigt:

- Project Browser → Filter: "Adapter Project"
- Graph View zeigt Dependencies zwischen Native/n8n Steps
- Execution View für Benchmarks und Dry-Runs

### Gate Panel

Captain Gates für Adapter-Workflows:

```yaml
# In Workflow definiert
policies: ["production-deploy", "data-migration"]

# Im Gate Panel: Approve/Reject mit Begründung
```

### Status Dashboard

- Adapter Health: Native/n8n/Hybrid Status
- Letzte Ausführungen mit Duration
- Benchmark Scores pro Adapter Type

---

## Evidence Store Integration (F2-03)

Jede Adapter-Ausführung wird im Evidence Store protokolliert:

```bash
# Runs anzeigen
sedra factory evidence list --typ-id adapter-native --limit 10

# Run Details
sedra factory evidence show <run_id>

# Export
sedra factory evidence export adapter_runs.jsonl --typ-id adapter-native
```

### Metriken

| Metrik | Beschreibung |
|--------|--------------|
| `duration_ms` | Ausführungsdauer |
| `steps_executed` | Anzahl ausgeführter Steps |
| `success_rate` | Erfolgsrate |
| `adapter_type` | native/n8n/hybrid |

---

## Policy Integration (MOD-02)

### Policy Definition

```yaml
# policies/production-deploy.yaml
id: production-deploy
name: Production Deployment
description: "Erfordert Captain Approval für Production Deployments"
severity: high
requires:
  - role: captain
  - approval: manual
```

### Policy Enforcement

```bash
# Workflow mit Policy
sedra factory adapter execute deploy.yaml --adapter native

# Bei Policy: Wartet auf Gate Callback
# Captain: sedra approve <mission_id> --gate-id production-deploy
```

---

## Performance Tuning

### Native Adapter

- **Async Execution**: Alle Steps laufen asynchron
- **Connection Pooling**: HTTP Client Pooling für `http` Steps
- **Caching**: Parsed Specs werden gecacht (LRU, max 100)

### n8n Adapter

- **Subprocess Reuse**: n8n CLI Process Pool (configurable)
- **Temp File Cleanup**: Automatisch nach Execution
- **Timeout Handling**: Graceful Shutdown bei Timeout

### Hybrid Adapter

- **Parallel Execution**: Native + n8n Steps parallel wo möglich
- **Shared Context**: Parameter werden zwischen Adaptern geteilt
- **Memory Efficiency**: Streaming für große Payloads

---

## Troubleshooting

### n8n nicht gefunden

```bash
# n8n installieren
npm install -g n8n

# Oder Pfad angeben
sedra factory adapter execute workflow.json --adapter n8n --n8n-path /usr/local/bin/n8n
```

### Timeout Errors

```bash
# Timeout erhöhen
sedra factory adapter execute workflow.yaml --adapter native --timeout-ms 600000
```

### Circular Dependencies

```bash
# Validierung zeigt Zirkel
sedra factory adapter validate workflow.yaml --adapter hybrid
# Fehler: circular_dependency
```

### Permission Denied (Captain Gate)

```bash
# Gate Status prüfen
sedra candidate-status <mission_id>

# Approve
sedra approve <mission_id> --gate-id <policy_id>
```

---

## Best Practices

1. **Native für Performance**: Einfache, schnelle Workflows → Native
2. **n8n für Komplexität**: Visuelle Editor, viele Integrationen → n8n
3. **Hybrid für Beste aus beiden**: Performance-kritisch + n8n Features → Hybrid
4. **Parameter nutzen**: `{{env}}`, `{{api_base}}` statt Hardcoding
5. **Timeouts setzen**: Immer `timeout_ms` pro Step definieren
6. **Policies sparsam**: Nur für echte Risk-Schritte (Production, Data Migration)
7. **Evidence nutzen**: Runs analysieren für Regression Detection

---

## Migration Guide

### Von Legacy GUPPI

```bash
# Alte GUPPI Workflows → Native
# 1. Export als YAML
# 2. Steps anpassen (type: script, config.script)
# 3. Dependencies als depends_on
```

### Von n8n Export

```bash
# n8n Workflow exportieren → JSON
# Direkt mit n8n Adapter nutzbar
# Credentials werden als Referenzen beibehalten
```

---

## Changelog

| Version | Datum | Änderungen |
|---------|-------|------------|
| 1.0.0 | 13.11.2026 | Initial Release: Native, n8n, Hybrid Adapters |
| 1.0.1 | 13.11.2026 | CLI Integration, Factory Templates, Tests |
| 1.0.2 | 13.11.2026 | Policy Integration, Evidence Store, Docs |

---

## Support

- **Issues**: GitHub Issues im SEDRA Repository
- **Docs**: `docs/ADAPTERS.md` (diese Datei)
- **Examples**: `factory_templates/adapter_project/adapters/*/workflows/`