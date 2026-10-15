# INTEGRATION_PLAN – Job Supervisor, Routing, Permissions, Hardware

Stand: 2026-10-01 · Grundlage: `ARCHITECTURE_GAP_REPORT.md`
Status: **Entwurf zur Freigabe. Es wurde noch kein Code geändert.**

## 1. Leitentscheidungen

1. **Erweitern statt ersetzen.** Der Supervisor wird eine dünne Schicht über `DevelopmentJobStore` und `step_journal`. Beide behalten ihr Verhalten.
2. **Zuständigkeit nach Handoff §19.** Intelligenz → GUPPI. Kontext → Context Manager. Runtime/Provider/Hardware → Control Master. Queue/Lease/Retry → Supervisor. Code/Test → Entwicklungsumgebung. Grenze/Freigabe → Guard.
3. **Keine neuen Python-Abhängigkeiten.** Nur Standardbibliothek und das vorhandene `yaml`.
4. **Alles hinter Feature Flags, Default AUS.** Neue Datei `config/job_supervisor.yaml`. Ohne Flag verhält sich v1.20 unverändert.
5. **Rückbaubar.** Jede Phase ist ein eigenes Modul. Löschen des Moduls plus Flag AUS stellt v1.20 wieder her. Es gibt keine Änderung am Format bestehender Dateien (nur optionale zusätzliche Felder).

## 2. Voraussetzungen vor dem Supervisor (Phase 0)

Diese Punkte sind kein Ausbau, sondern Reparatur von Bestand. Sie sind Voraussetzung für Parallelität (Befunde F-1 bis F-6 im Gap Report).

| # | Änderung | Datei | Begründung |
|---|---|---|---|
| 0.1 | Audit: letzten Hash und ID **im Speicher** halten, beim Start einmal aus der Datei lesen. Schreiben unter Dateisperre (`mission_lock.exclusive`). Dateiformat unverändert. | `audit.py` | F-2 |
| 0.2 | Gleiches Muster für Evidence-Store | `development_evidence.py` | F-2 |
| 0.3 | `DevelopmentJobStore`: Lesen-Ändern-Schreiben unter Sperre pro Job (`update(job_id, fn)`). Bestehende `load/save/transition` bleiben als API. | `self_development.py` | F-3 |
| 0.4 | Strukturierte Fehlerklasse: `classify_failure` bekommt Reason-Codes (z. B. `feasibility.reason_code`, Exception-Typen). Freitext-Matching nur als letzter Fallback, mit Wortgrenzen und korrekter Reihenfolge. | `self_development.py` + neues `failure_classes.py` | F-1 |
| 0.5 | Core-Ziele in **eine** Quelle (`self_development.yaml: core_targets`), E3 als Obermenge beider Listen. | `evolution.py`, `self_development.py` | F-5 |
| 0.6 | `attach_verification` verlangt Testbelege (Evidence-Referenz mit `trust_level=deterministic`) für `PASS`. Ohne Beleg bleibt `INCONCLUSIVE`. | `self_development.py` | F-6 |

Abnahme Phase 0: bestehende Testsätze laufen unverändert grün **auf dem Zielsystem**, plus neue Tests für Sperren, ID-Eindeutigkeit bei zwei Threads, Fehlerklassifikation.
Risiko: Audit-Änderung berührt alles. Deshalb zuerst, klein, mit Vorher/Nachher-Test auf einer **Kopie** eines echten Audit-Logs.

## 3. Neue und geänderte Module

Alle neuen Module in `runtime/src/guppi_runtime/`. Namen sind Vorschläge.

| Modul | Zweck | Wiederverwendet |
|---|---|---|
| `job_supervisor.py` | Queue, Claim, Lease-Reaper, Retry-Entscheidung, Cancel, Recovery | `DevelopmentJobStore`, `audit`, `mission_lock` |
| `failure_classes.py` | Fehlerklassen + Retry-Regeln als Tabelle | Reason-Codes aus `feasibility` |
| `provider_health.py` | Zustand je Provider, Cooldown, Backoff | `ModelRouter.status/health` |
| `role_routing.py` | `role → capability → Anforderungen` (Konfiguration) und Auflösung **über den Control Master** | `Registry`, `HardwareModelPass` |
| `permission_levels.py` | Abbildung Level 0–6 → erlaubte Guard-Aktionen | `Guard` |
| `resource_scheduler.py` | Slots + Hardware-Signale, später Reservierung | `HardwareManager`, `HardwareModelPass`, `feasibility` |
| `context_manager.py` | Tokenschätzung, Offloading, Checkpoints, Metriken, Repair | `ContextBudgetManager`, `ArtifactStore`, `context_manifest` |
| `config/job_supervisor.yaml` | alle Schwellen, Flags, Rollen, Level-Abbildung | – |

Geändert, minimal:
- `modules/control.py`: neue Aktion `resolve_role` (liefert Provider/Modell/Profil für Rolle + Anforderungen). Bestehende Aktionen unberührt.
- `models/router.py`: optional `provider_health` einhängen. `choose()` bleibt Standard, solange das Flag aus ist.
- `runtime.py`: Komponenten instanziieren, in `observability` registrieren, in `boot()` einen Statusblock ergänzen.
- `uix_server.py`: `/api/supervisor` (nur lesend zunächst) neben `/api/self-development`.
- `cli.py`: Befehle `jobs`, `job-show`, `job-cancel`, `job-recover`. Für Cancel/Recover Guard-Aktion verwenden, wie bei `recover`.

## 4. Schnittstellen (Entwurf)

```text
GUPPI ──create_job(kind, contract, role_requests, parent?)──▶ JobSupervisor
JobSupervisor ──build_manifest(job, parent_checkpoint)──▶ ContextManager ──▶ manifest (hash)
JobSupervisor ──resolve_role(role, requirements)──▶ ControlMaster ──▶ {provider, model, profile, ctx_window}
ControlMaster ──fit?(profile, requirements)──▶ HardwareModelPass / HardwareManager
JobSupervisor ──claim/heartbeat/progress──▶ Job-Datei (+ Audit nur bei Zustandswechsel)
Worker-Ausführung ──▶ ControlMaster.execute(...)   (kein Direktweg zu Providern)
ControlMaster ──result + usage──▶ ContextManager.record(metrics, offload(large_output))
JobSupervisor ──approval_needed──▶ Guard.create_gate  ──▶ Captain
```

Regeln:
- Der Supervisor ruft Provider **nie** direkt, nur über `ControlMaster.execute`.
- Fallback-Entscheidung = Supervisor **erkennt** die Fehlerklasse, `role_routing` über Control Master **wählt** die Alternative **innerhalb der Policy**. `policy_denied` führt nie zu einem Fallback.
- Heartbeat/Progress werden **nicht** ins hash-verkettete Audit geschrieben, sondern in die Job-Datei und in `ContextMetric`/Health-Log. Audit bekommt Zustandswechsel, Lease-Ablauf, Retry, Fallback, Approval.

## 5. Job-Datenmodell (Schema 2, rückwärtskompatibel)

Schema 1 bleibt lesbar. Neue Felder werden beim ersten Schreiben ergänzt, `schema` bleibt 1 oder wird auf 2 gesetzt mit Lese-Migration (siehe Migrationen).

```text
kind: development | mission_step | maintenance
supervisor_state: <Handoff §4 Zustand>      # abgeleitet/gespiegelt, siehe 5.1
depends_on: [job_id]
requested_role, selected_capability, provider_ref
permission_level, policy_hash
attempt_log: [{attempt_id, started, ended, error_class, provider, usage?}]
retry: {limit, count, next_not_before, reason}
lease: {worker_id, lease_until(ISO UTC), grace_until?}
heartbeat_at, progress_at, progress_marker(step hash)
last_error, last_checkpoint_id, context_manifest_id
```

### 5.1 Zustandsabbildung (kein Umbau von `ALLOWED`)

| Dev-Job-Zustand (v1.20) | Supervisor-Sicht (Handoff §4) |
|---|---|
| CREATED | CREATED |
| PLANNING | PLANNING |
| READY | READY (→ QUEUED, wenn eingereiht) |
| BUILDING | RUNNING (CLAIMED zwischen Einreihung und Start) |
| TESTING | RUNNING |
| VERIFYING | VERIFYING |
| REWORK | RETRY_PENDING |
| READY_FOR_ACCEPTANCE | PASSED |
| ACTIVATION_PENDING | WAITING_APPROVAL |
| ACTIVATED | COMPLETED |
| BLOCKED | BLOCKED |
| REJECTED | FAILED |
| ROLLED_BACK | ROLLED_BACK |

Neu hinzu kommen nur die Zustände, die der Dev-Pfad nicht kennt: `QUEUED`, `CLAIMED`, `DEAD`, `CANCELLED`, `ROLLBACK_PENDING`, `ESCALATED_TO_GUPPI`, `ESCALATED_TO_CAPTAIN`. Sie werden als **zusätzliche** Einträge in einer erweiterten Übergangstabelle geführt. Bestehende Übergänge bleiben gültig.

Entscheidung offen (siehe 9): ob `supervisor_state` gespeichert oder nur berechnet wird. Empfehlung: **berechnet**, damit es keine zwei Wahrheiten gibt. Gespeichert wird nur, was der Dev-Pfad nicht ausdrücken kann.

## 6. Phasen, Reihenfolge, Abnahme

| Phase | Inhalt | Abhängig von | Abnahme (Auszug aus Handoff §17) |
|---|---|---|---|
| 0 | Reparaturen aus Abschnitt 2 | – | Bestandstests grün, Sperrtests |
| 1 | **Contracts** `JOB_SUPERVISOR_CONTRACTS.md`, `CONTEXT_MANAGER_CONTRACTS.md` | Freigabe dieses Plans | Review durch Captain |
| 2 | **Minimal-Supervisor**: Queue, Claim, Lease-Reaper (suspect → Healthcheck → Grace → Freigabe), Retry-Limit, Cancel, Recovery. Ein Worker, **ohne** Parallelität | 0 | A, B, C, J |
| 3 | **Context v1**: Tokenschätzung, Offloading, strukturierter Checkpoint, Metriken, Watermark-Aktionen **ausführend** | 0 | K, L, N, Q |
| 4 | Child-Manifest + Fresh Task Boundary + Context Repair | 2, 3 | M, O, P |
| 5 | **Routing**: Rollen, ProviderHealth, Cooldown, Fallback mit Policy-Prüfung, Verifier-Unabhängigkeit auf Modellebene | 2 | D, H |
| 6 | **Permissions**: Level-Abbildung, Dev-Environment-Bindung, Approval-Zustand | 2, 5 | E, F, I |
| 7 | **Hardware**: Slots, dann VRAM-/KV-Reservierung, Anbindung `HardwareModelPass` an Budget | 2, 5 | G |
| 8 | Self-Development-Loop auf dem Supervisor (E1-Testfall) | 1–7 stabil | Golden Path auf realer Hardware |

Phase 3 kann parallel zu Phase 2 laufen (keine Überschneidung außer `Job.context_manifest_id`).
Phase 8 startet erst nach einer **echten** Windows-PC-Abnahme der Phasen 2–7. Simulierte Ergebnisse zählen nicht (Auftrag v1.19).

## 7. Migrationen und Rückwärtskompatibilität

| Thema | Maßnahme |
|---|---|
| Job-Dateien `SDJ-*.json` | Lesen toleriert fehlende neue Felder (Defaults). Keine Massenmigration. Schreibt ein Job neue Felder, bleibt die Datei für v1.20-Code lesbar (zusätzliche Schlüssel werden ignoriert). |
| Audit/Evidence-Format | unverändert (nur interne Implementierung, Phase 0) |
| `checkpoint` im Job | altes Freitextobjekt bleibt gültig. Neues Feld `context_checkpoint` daneben. |
| Registry-YAML | neue Felder optional. Fehlen sie, gelten Defaults: `roles: []`, `permissions.max_level: 2`, `trust_level: BUILT_IN`. |
| Guard-Regeln | **keine** Änderung an bestehenden Regeln. Neue Aktionen (z. B. `job_cancel`) nur **hinzufügen**, mit `CAPTAIN_REQUIRED` als Default (unbekannte Aktionen sind das bereits). |
| Rollback | Flag `job_supervisor.enabled: false` + Modul entfernen → v1.20-Verhalten. Dokumentation in `historie/MIGRATION_ROLLBACK_v1.20.md` ergänzen. |

## 8. Risiken

| Risiko | Wahrscheinlichkeit | Gegenmaßnahme |
|---|---|---|
| Audit-Umbau (0.1) beschädigt Hash-Kette | mittel | Test auf Kopie echter Logs, Kette vor/nach verifizieren, Format unverändert |
| Dateibasierte Queue unter Windows: Sperren, AV-Scanner, Rename-Fehler | mittel | `atomic_write_json` und `mission_lock` bereits im Einsatz, trotzdem Test auf realem Windows. Nicht von Linux-Läufen ableiten. |
| Lease-Zeitbasis (Systemuhr springt) | niedrig | monotone Zeit für Laufzeit, UTC-ISO nur für Persistenz, großzügige Grace |
| Tokenschätzung ungenau (kein Tokenizer) | hoch | konservativ schätzen (Zeichen/3), Provider-`usage` vorziehen, wenn vorhanden, Unsicherheit im Watermark-Puffer berücksichtigen |
| Zwei Wahrheiten bei Zuständen | mittel | `supervisor_state` berechnen, nicht speichern |
| Rollen-Routing wird heimlich zur Modellwahl im Supervisor | mittel | Test: Supervisor-Code enthält keine Modell-/Provider-Namen. Statische Prüfung im Test. |
| Fallback umgeht Policy | hoch (Schaden) | explizite Tests für `policy_denied`, `data_class=restricted`, Cloud verboten |
| Umfang zu groß | hoch | strikt phasenweise, jede Phase einzeln abnehmbar |
| Kev nicht verfügbar, Verifier-Unabhängigkeit nicht prüfbar | sicher (heute) | Zustand `INCONCLUSIVE`, nicht `PASS` |
| Reale Hardware nicht verfügbar im Build | sicher (heute) | Abnahme klar als „nicht real qualifiziert" kennzeichnen |

## 9. Offene Entscheidungen für den Captain

1. **Phase 0 zuerst?** Empfehlung: ja, besonders Audit (F-2) und Sperren (F-3).
2. **`supervisor_state` berechnet statt gespeichert?** Empfehlung: berechnet.
3. **Ein Worker zuerst, Parallelität erst in Phase 7?** Empfehlung: ja.
4. **Cloud-/CLI-Provider:** weiter zurückstellen? Empfehlung: ja, bis Routing + Policies stehen.
5. **herdr-Fremdcode:** verzichten und nur Ideen übernehmen? Empfehlung: ja. Begründung im Gap Report §5.0: herdr ist ein Rust-Terminal-Multiplexer (v0.9.3, Apache-2.0), kein Job-Supervisor. Queue, Heartbeat, Lease, Cooldown und Token-Metriken **gibt es dort nicht**. Das Handoff beschreibt herdr in diesen Punkten falsch. Übernommen werden nur: die Zustände inkl. `unknown ≠ erfolgreich`, Stall-Erkennung bei der Übergabe, Sequenznummern für Abschluss, Sicherung beschädigter Dateien vor dem Überschreiben, nie wiederverwendete IDs, append-only-Enums mit `UNKNOWN`-Fallback.
   - **Folge für Phase 2:** Lease-Reaper und Retry sind **Eigenentwurf**, nicht Portierung. Das erhöht den Testbedarf.
   - Zusätzliche kleine Punkte aus herdr für Phase 0/2: Defektdatei sichern statt überschreiben (Job-Store, Evidence); Fortschritt über **monotone Sequenznummer** (`progress_seq`) statt nur Zeitstempel; Übergabe-Bestätigung „Arbeit hat begonnen" als eigener Schritt zwischen CLAIMED und RUNNING (Timeout → Stall).
6. **Tokenzählung:** reicht eine konservative Schätzung für v1, oder soll ein lokaler Tokenizer pro Modellfamilie (Qwen) mitgeliefert werden? Zweites bräuchte eine neue Abhängigkeit.
7. **Ablage der Job-Daten:** weiter unter `runtime_data/self_development/jobs/`, oder neuer Ordner `runtime_data/jobs/` mit `kind`? Empfehlung: neuer Ordner, Dev-Jobs bleiben, wo sie sind, bis Phase 8.

## 10. Nächster konkreter Schritt nach Freigabe

Phase 0, Punkt 0.1 (Audit-Performance und Sperre) mit Tests, als kleinste eigenständige Änderung. Danach Phase 1 (Contracts-Dokumente).
