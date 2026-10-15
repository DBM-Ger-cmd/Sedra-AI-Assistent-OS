# GUPPI Architecture v0.1

Dieses Paket beschreibt die beschlossene Entwicklungsarchitektur von GUPPI OS.

## Kerngedanke
- **GUPPI Stable** arbeitet produktiv.
- **GUPPI Development** entwickelt den nächsten Kandidaten.
- Der laufende Stable-Stand wird niemals direkt überschrieben.
- GUPPI ist das zentrale ansprechbare Gehirn.
- Module dürfen kontrolliert untereinander kommunizieren.
- Relevante Ergebnisse fließen zurück in den Mission State von GUPPI.
- Guard/Human Gates begrenzen kritische Aktionen.
- Updates werden als prüfbare Pakete mit Rollback erstellt.

## Dateien
- `guppi.manifest.yaml` – installierter Systemstand
- `GUPPI_EVOLUTION.yaml` – maschinenlesbarer Entwicklungsauftrag
- `core_invariants.yaml` – unveränderliche Schutzregeln
- `module_manifest_template.yaml` – Vorlage für neue Module
- `core_contract.md` – Schnittstellen zwischen Core und Modulen
- `concept_overview.txt` – fachliches Architekturkonzept
- `technical_architecture.txt` – technische Zielstruktur

## v0.2 – Kernmodule
Neu hinzugefügt:
- `modules/planning-context/module.yaml`
- `modules/control-master/module.yaml`
- `modules/verification/module.yaml`
- `module_interfaces.txt`

Diese drei Module bilden den ersten ausführbaren Funktionskern um das zentrale GUPPI Brain.

## v0.4 – GUPPI Brain / Mission Loop
Neu:
- `core/brain/brain_manifest.yaml`
- `core/brain/mission_loop.yaml`
- `core/brain/decision_rules.yaml`
- `schemas/state_transitions_v1.yaml`
- `brain_mission_loop_spec.txt`
- `mission_loop_pseudocode.txt`

Damit ist definiert, wie GUPPI selbst zwischen Planen, Guard, Ausführen,
Prüfen, Rework und Abschluss entscheidet.

## v0.5 – Guard + Human Gate
Neu:
- `core/guard/guard_manifest.yaml`
- `core/guard/guard_rules.yaml`
- `schemas/guard_request_v1.yaml`
- `schemas/human_gate_v1.yaml`
- `schemas/approval_token_v1.yaml`
- `guard_human_gate_spec.txt`
- `guard_flow.txt`

Damit ist definiert, welche Aktionen automatisch erlaubt, blockiert oder
dem Captain zur Freigabe vorgelegt werden.

## v0.6 – Registry + Boot/Lifecycle
Neu:
- `core/registry/registry_manifest.yaml`
- `core/registry/module_registry.yaml`
- `core/registry/skill_registry.yaml`
- `core/registry/tool_registry.yaml`
- `schemas/skill_manifest_v1.yaml`
- `schemas/tool_manifest_v1.yaml`
- `core/lifecycle/boot_sequence.yaml`
- `core/lifecycle/lifecycle_states.yaml`
- `core/lifecycle/recovery_policy.yaml`
- `registry_boot_lifecycle_spec.txt`
- `boot_flow.txt`

GUPPI kann damit Komponenten kontrolliert registrieren, beim Start auf
Kompatibilität prüfen und bei Fehlern in Safe Mode oder Recovery wechseln.

## v0.7 – Update Builder + Candidate/Release Pipeline
Neu:
- `core/lifecycle/update_builder.yaml`
- `core/lifecycle/release_pipeline.yaml`
- `schemas/candidate_manifest_v1.yaml`
- `schemas/update_manifest_v1.yaml`
- `schemas/rollback_bundle_v1.yaml`
- `schemas/verification_bundle_v1.yaml`
- `update_release_pipeline_spec.txt`
- `candidate_release_flow.txt`
- `update_package_layout.txt`

Damit ist erstmals definiert, wie aus einer Evolution-Anforderung ein isolierter
Candidate, ein verifiziertes Update-Paket und bei Bedarf ein Rollback entsteht.

## v0.8 – Evolution Manager
Neu:
- `core/evolution/evolution_manager.yaml`
- `core/evolution/classification_rules.yaml`
- `core/evolution/proposal_policy.yaml`
- `core/evolution/evolution_flow.yaml`
- `schemas/capability_gap_v1.yaml`
- `schemas/evolution_proposal_v1.yaml`
- `schemas/evolution_decision_v1.yaml`
- `evolution_manager_spec.txt`
- `evolution_flow.txt`

GUPPI kann damit Fähigkeitslücken strukturiert erkennen, sammeln, klassifizieren
und als kontrollierte Entwicklungsanforderung vorbereiten.

## v1.0 – Architecture Baseline Complete
Abgeschlossen wurden:
- Audit/Event Log
- Knowledge
- Communications
- Artifact Store
- Observability
- Config/Secrets
- Provenance/Checksums
- Service Registry
- finaler Boot-Flow
- Architecture Acceptance Checks
- Implementierungsplan

`STATUS_v1.txt` markiert die Architekturphase als abgeschlossen.
Der nächste Schritt ist die Implementierung des Runtime-Kerns gegen diese Spezifikation.
