# GUPPI v1.20 – Implementation Report: 3-Phasen Self-Development

## Ausgangsbasis

Basis war `GUPPI_Developer_Archive_v1.19_PC_TEST.zip`.

Die bestehende Architektur wurde **nicht ersetzt**. Insbesondere bleiben erhalten:

- GUPPI als First Officer / zentrale Intelligenz
- Control Master als Maschinenraum
- Guard / Captain Gates
- Candidate Lifecycle
- Sandbox / GUPPI Entwicklungsumgebung
- Candidate Testing / Verification / Acceptance / Rollback
- Capability Router
- Hardware Manager
- Hardware-Model-Pass
- Model Runtime

## Architekturentscheidung

Neue Selbstentwicklung wird als **kontrollierte Schicht über vorhandenen Mechanismen** aufgebaut.

```text
Capability Gap
  -> Capability Admission
  -> Development Contract
  -> Context Manifest
  -> Development Job
  -> GUPPI Entwicklungsumgebung
  -> Candidate
  -> Tests
  -> Verification
  -> Baseline Comparison
  -> Activation Decision
  -> Captain/Policy
  -> Stable
```

## Capability Before Tool

Ein neues Tool wird nicht allein wegen Verfügbarkeit aufgenommen. Vor Zulassung werden Skills, Tools und Module geprüft. Für neue Tools ist zusätzlich eine explizite Begründung erforderlich.

## Context als Ressource

`ContextBudgetManager` führt modellabhängige Reserven und Watermarks ein:

- GREEN
- YELLOW
- ORANGE
- RED

RED fordert Checkpoint, Context Rebuild und Fresh Task Context statt blindem Retry.

## Evidence Chain

Self-Development-Belege werden append-only hashverkettet gespeichert. Manipulation wird durch `verify_chain()` erkannt.

## Candidate / Verification

Self-Development-Candidates sind an Development Contract und Candidate Hash gebunden. Der Builder darf nicht zugleich der unabhängige Verifier sein.

## E1 / E2 / E3

- E1: Entwicklung vorbereitet; Auto-Aktivierung standardmäßig AUS.
- E2: Candidate-Entwicklung möglich; Aktivierung policy-/Captain-kontrolliert.
- E3: Candidate/Experiment möglich; Auto-Aktivierung im Code unveränderlich verboten.

## Qwen3.5 + Kev

Built-in Hardwareprofile wurden auf Qwen3.5 umgestellt und um Kev ergänzt. Der Hardware-Model-Pass bewertet zusätzlich Pair-Fit und Execution Mode:

- `DUAL_LOADED`
- `SWAP_MODE`
- `CPU_GPU_SPLIT`

Kev ist als **lokaler Loopback Provider** vorbereitet. Es werden keine Kev-Gewichte gebündelt und keine Cloud-Verbindung eingeführt.

## Keine neue Fremdabhängigkeit

Es wurden keine neuen Python-Paketabhängigkeiten aufgenommen.

## Noch offen

- echter Kev-Server + Modellgewichte auf Zielhardware
- echter Qwen3.5-Coder-Loop innerhalb der Entwicklungsumgebung
- automatischer Red-Baseline-Sandbox-Lauf
- vollwertige Job Queue / Concurrency Supervisor
- dynamische Capability Registry Aufnahme nach Promotion
- echte Windows-PC-Abnahme
