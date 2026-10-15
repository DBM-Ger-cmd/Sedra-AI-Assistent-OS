# GUPPI v1.20 – Ticketmatrix 3 Phasen

Status: **DONE** = implementiertes Fundament und getestet; **PARTIAL** = sichere Grundlage vorhanden, reale Runtime-/PC-Integration noch offen; **REUSE** = vorhandene v1.19-Funktion bleibt verbindlich.

## Phase 1 – DNA / Contracts

| Ticket | Titel | Status | Umsetzung |
|---|---|---|---|
| P1-001 | Capability Admission Gate | DONE | `self_development.py` |
| P1-002 | Mission / Development Contract | DONE | `development_contracts.py` |
| P1-003 | Context Manifest + Budget | DONE | `context_budget.py`, `development_contracts.py` |
| P1-004 | Evidence Chain | DONE | `development_evidence.py` |
| P1-005 | Candidate Contract | DONE | hashgebunden; vorhandener Candidate Lifecycle bleibt bestehen |
| P1-006 | Verification Contract | DONE | PASS/FAIL/INCONCLUSIVE, unabhängiger Verifier |
| P1-007 | Red-Baseline + Negative Tests | PARTIAL | Comparator + Negativtests vorhanden; automatischer Baseline-Sandbox-Lauf noch offen |
| P1-008 | Phase-1 Integration Test | DONE | `test_self_development.py` |

## Phase 2 – Self-Development Loop

| Ticket | Titel | Status | Umsetzung |
|---|---|---|---|
| P2-001 | Evolution Manager Pipeline v2 | DONE | Bridge `handoff_to_self_development()` |
| P2-002 | Development Job Orchestrator | PARTIAL | persistente State Machine, Heartbeat/Lease-Felder; keine volle Worker-Queue. 2026-10-02 behoben: ein fertiger Job (VERIFYING), den der Handler nicht selbst parkt, hielt den einzigen Worker bis zum Lease-Ablauf; danach wurde ein lesender Job erneut ausgeführt, ein ändernder endete DEAD. Der Worker parkt ihn jetzt (`_release_finished`), Prüf-Jobs werden abgeschlossen. |
| P2-003 | Entwicklungsumgebung vorbereiten | PARTIAL | Sandbox-Readiness-Gate; reale Snapshot-/Build-Ausführung nutzt weiter vorhandene Sandboxpfade |
| P2-004 | Worker Role Delegation | DONE | Rollenvertrag ohne Modell-Hardcoding |
| P2-005 | Kev Verification Provider | PARTIAL | Loopback-only Adapter implementiert; reale Gewichte/Server nicht gebündelt |
| P2-006 | Baseline-vs-Candidate Comparator | DONE | IMPROVED/UNCHANGED/REGRESSED/INCONCLUSIVE |
| P2-007 | Rework/Retry/Failure Classification | PARTIAL | Fehlerklassifikation vorhanden; kein neuer paralleler Retry-Scheduler. Seit 2026-10-02: Missions-Rework funktioniert (vorher pausierte jede Mission nach Verifier-FAIL dauerhaft). Neue Ausführung nur über Captain-Gate `execution_recovery` (`replan:<Mission>:<Revision>`), gebunden an Plan-Digest + Befunde; alter Versuch wird unter `previous_executions` archiviert, nur wenn jeder Schritt COMPLETED/PENDING ist (der in STEP_RECOVERY v1.15 offene „explicit new-execution contract“). `tests/test_brain_rework.py` |
| P2-008 | Audit + Checkpoint + Learning | DONE | Audit, Checkpoint, Learning Store |
| P2-009 | Self-Development Golden Path | DONE (1 echter Lauf) | 2026-10-02 auf dem Captain-PC, `runtime/benchmarks/e1_golden_path.py`, Job `SDJ-3089918D73A9`: rote Ausgangslage (AssertionError), gpt-oss-20b schreibt den Fix (Mission `M-40B53FC2`), Test in GUPPIs microVM grün (`SBX-13db46a0…`, `MICROVM_RESULT`, verifiziert), Gemma 4 prüft unabhängig (PASS, Identitäten gpt-oss ≠ gemma4 festgehalten) → `READY_FOR_ACCEPTANCE`, Aktivierung beim Captain. Ein Lauf ist ein Existenzbeweis, keine Abnahme. |

## Phase 3 – Kontrollierte Eigenentwicklung

| Ticket | Titel | Status | Umsetzung |
|---|---|---|---|
| P3-001 | Evolution Policy E1/E2/E3 | DONE | `self_development.yaml` + Runtime-Enforcement |
| P3-002 | E1 Auto-Development | PARTIAL | vorbereitet hinter Feature Flag; Default AUS |
| P3-003 | E2 Controlled Module Development | PARTIAL | Candidate/Gate-Policy vorhanden; realer Agent-Loop offen |
| P3-004 | E3 Core Protection | DONE | `may_activate=False` wird im Code erzwungen |
| P3-005 | Activation Gate | DONE | Verification/Regression/Policy-Prüfung. Seit 2026-10-02 auch ausgeführt: `candidate_acceptance` verlangt bei einem gebundenen Job READY_FOR_ACCEPTANCE + unabhängiges PASS und führt den Job auf ACTIVATED/ROLLED_BACK |
| P3-006 | Rollback + Recovery | REUSE | bestehende v1.19 `candidate_acceptance.py` bleibt maßgeblich; `self_integration.py` hat eigenen Rollback (nur bei unverändertem Hash, eigenes Gate) |
| P3-010 | Selbstintegration in GUPPIs Code | DONE (eng) | `self_integration.py` + CLI `self-integrate*`: nur E1, nur neue Module in `guppi_runtime/capabilities/`, Gate GR-025/GR-026, Stufe 5. Erste Fähigkeit: `capabilities/path_health.py` (gpt-oss, VM 13/13, Gemma PASS, Job `SDJ-3DC38FDB63EA` ACTIVATED, Gate `HG-E2847E15`). Noch nicht in GUPPIs Abläufe eingebunden. |
| P3-007 | Capability Registry Learning | PARTIAL | Learning Store + Captain-Promotion; noch keine automatische Aufnahme in statische Registry |
| P3-008 | Self-Development Dashboard/ViewModel | DONE | Runtime/UIX Status + `/api/self-development` |
| P3-009 | PC Acceptance Scenario | PARTIAL | automatisierte Foundations-Tests; echter Windows-PC-Lauf offen |

## Captain-Wünsche (offen, nicht umgesetzt)

| Ticket | Titel | Status | Notiz |
|---|---|---|---|
| CW-001 | Option für wiederholte gleiche Freigaben (Session-Freigabe) | OFFEN | Wunsch des Captains vom 2026-10-02: Für eine gleichartige Tätigkeit soll nicht jedes Mal ein eigenes Gate nötig sein. Ein Entwurf (befristete, nutzungsbegrenzte Freigabe je Aktionsart im Guard) wurde in der Claude-Code-Sitzung vom Sicherheitsfilter abgelehnt und vollständig zurückgenommen. Der Guard arbeitet weiter mit Einzel-Gates. Über Umfang und Umsetzung entscheidet der Captain selbst; bis dahin gilt: weniger Freigaben nur durch weniger Fehlversuche, nicht durch Lockerung. |
