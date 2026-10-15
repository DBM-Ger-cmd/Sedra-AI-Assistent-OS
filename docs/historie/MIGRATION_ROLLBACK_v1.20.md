# GUPPI v1.20 – Migration und Rollback

## Migration von v1.19

v1.20 ist additiv aufgebaut.

Neue Runtime-Dateien:

- `development_contracts.py`
- `context_budget.py`
- `development_evidence.py`
- `kev.py`
- `self_development.py`
- `config/self_development.yaml`
- `config/kev.yaml`

Bestehende Dateien wurden gezielt erweitert:

- `runtime.py`
- `evolution.py`
- `hardware_pass.py`
- `model_runtime.py`
- `model_profiles.py`
- `uix_server.py`
- `model_profiles.yaml`

## Daten

Neue persistente Daten liegen nur unter:

```text
runtime_data/self_development/
```

Damit werden v1.19-Missions-, Guard-, Candidate- und Artifact-Daten nicht migriert oder überschrieben.

## Rollback auf v1.19

1. v1.20 beenden.
2. v1.19 Runtime wieder verwenden.
3. `runtime_data/self_development/` kann archiviert oder ignoriert werden.
4. Bestehende v1.19 Mission-/Candidate-Daten bleiben unabhängig davon erhalten.

## Model Profiles

v1.20 Built-ins verwenden Qwen3.5 + Kev. Bestehende Captain Custom Profiles bleiben schema-kompatibel; `verification` ist für alte Custom Profiles optional.

## Feature Flags

Standard:

```yaml
auto_develop_e1: false
auto_activate_e1: false
```

Diese Defaults dürfen erst nach PC-Abnahme bewusst geändert werden.
