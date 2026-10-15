# AM-001: Inventar des Checkouts und Abgleich mit dem DevVM-Auftrag (2026-10-06)

Quelle: `GUPPI_Agent_Manager_Developer_Archive_v1.0.zip` (Spezifikation, kein Code). Dieser Bericht ändert keinen Code.

## 1. Checkout (belegt)
| Punkt | Befund |
|---|---|
| Pfad | `GUPPI v1.20_S D A/GUPPI_Runtime_v1.20/runtime` |
| Commit | **keiner**: kein Git-Repository. Stand = Paket v1.20.0 (`pyproject.toml`) plus Änderungen bis 2026-10-06; Sicherungen unter `archiv/`. |
| Python / Pakete | `.venv`, Python >= 3.11; PyYAML, dulwich 1.2.17, urllib3. Kein pytest (Tests laufen mit `unittest`). |
| Datenhaltung | JSON-Dateien (`MissionStore`, atomares Schreiben), SQLite nur im Test-Lab (`testlab.py`). Keine Registry-DB. |
| Ports | UIX-Server `ThreadingHTTPServer` auf 127.0.0.1; llama-server 8080/8089/18080; LM Studio 1234; Kev 8008 (aus). |
| OS / VM | Windows 11; microsandbox 0.7.4, Image `python:3.12-slim`, `target_qualified: true`. |
| Tests | 200 Tests (Rollen-Routing, Rechtestufen, Schrittjournal, Capability-Router, DevVM-Agenten) laufen grün (1 übersprungen), 56 s. Volle Suite nicht gelaufen (GPU/VM-Last), nicht nötig solange kein Code geändert wird. |

## 2. Ist/Soll: was das Archiv voraussetzt und was es wirklich gibt
Das Archiv baut auf `guppi_control_core` v0.9.1 (Mission, ControlRun, MissionLease, WorkspaceService, ArtifactStore, `ControlPort.execute_step`). **Dieser Checkout hat dieses Paket nicht.** Der Ersatz heißt:

| Archiv | Hier vorhanden | Lücke |
|---|---|---|
| Control Core / Mission / Step | `modules/control.py` (ControlMaster), `mission.py` (MissionStore), `guard.py` (Gates mit Token und Request-Bindung), `permission_levels.py` (Stufen 0-6) | Kein `ControlRun`, keine Lease/Fencing-Primitive für Missionen (nur `mission_lock.py`), kein `in_doubt`-Status |
| Durable Runtime, unknown/in_doubt | `job_supervisor.py`, `job_worker.py`, `step_journal.py`, `run_log.py` | keine Dispatch-Receipts, kein Reconciliation-Protokoll |
| Artifact-Store | `artifacts.py` (1,8 KB) | Hash-Immutability und Ownerbinding prüfen |
| Registry | `registry.py`: YAML-Manifeste für Module, Dienste, Skills, Tools | keine Templates, Instanzen, Crews, Reifegrade, keine Revisions-CAS, keine Outbox |
| Matching | `capability_router.py` (Intent → Module/Skills/Tools), `role_routing.py` (Rolle → Provider/Modell, deklarativ, aus) | kein Hardfilter/Score/CapabilityGap-Modell für Agenten |
| Entwicklung/Abnahme | `self_development.py`, `candidate_*`, `verification_gate.py`, `rework_watch.py`, Kev-Anbindung (aus) | Plan → Code → Prüfer → Abnahme existiert, aber nicht als Zustandsmaschine mit Digest-gebundener Abnahme je Ticket |
| Hardware/Ressourcen | `resource_scheduler.py`, `hardware_manager/`, GPU-Lease im Test-Lab | keine Reservierung mit TTL/Generation |
| VM-Broker | `sandbox/` (microsandbox), `devvm.py`, `devvm_tools.py`, `devvm_agents.py` | **eine VM je Job**, kein dauerhafter Agentenlauf in der VM; Modelle laufen auf dem Host, nur Code läuft in der VM |
| Fenster | `uix_server.py`, `capabilities/uix_window.py`; DevVM-Fenster nur als Kandidat | AgentManager-Fenster fehlt |
| Entscheidungen D01-D10 | D01: oben; D02: In-Process-Ports; D03: eigene JSON/SQLite-Datei, nicht die Mission-Dateien; D04: microsandbox; D05-D07, D09: Captain (offen); D08: Messung | siehe Abschnitt 5 |

## 3. Abgleich mit dem DevVM-Auftrag (Phasen 0-5 abgeschlossen)
| Agent-Manager-Thema | DevVM liefert schon | Überschneidung |
|---|---|---|
| Rollen (Planner, Coder, Prüfer) | `devvm_agents.py`: `run_agent`, `DevOrchestrator`, Rollen planner/coder/coder_strong/reviewer/explorer/tester, Delegation Tiefe 2 | **hoch**: AM-008 (Entwicklungszyklus) ist im Kern vorhanden |
| Budget je Lauf | `AgentBudget` (10 min / 40 Aufrufe, Captain-Beschluss 2026-10-05) | AM-008 Iterationenlimit; passt |
| Isolierte Arbeit | `DevWorkspace`, `devvm_tools.py`, Richter in der microVM | AM-010 (VM-Broker): Teil da, aber Zielbild abweichend |
| Schrittjournal / Audit | `step_journal.py`, `audit.py`, `run_log.py` | AM-014 Logbuch teilweise |
| Fenster | `devvm_view.py` + `devvm.js` (Kandidat, nicht abnahmefähig) | AM-013 sollte dasselbe Fenster nutzen, nicht ein zweites |
| Nicht abgedeckt | Registry, Templates, SOUL, Crew-DAG, Matching, Packs, Admission/Widerruf | **das ist der echte Neubau** (AM-003 bis AM-005, AM-009, AM-015) |

Folge: DevVM Phase 6 (Abnahmelauf) und der Agent Manager sollen nicht doppelt gebaut werden. DevVM-Rollen werden die ersten Agent-Templates (`planner`, `coder`, `reviewer`), der Orchestrator wird die Ausführung hinter dem Manager.

## 4. Empfohlene Anpassung der Reihenfolge
1. AM-001 (dieser Bericht) → ADR bestätigen (Captain).
2. AM-002 Contracts (reine DTOs, ohne I/O, kein Modell nötig): **geeignet für den ersten Eigenentwicklungslauf**.
3. AM-003 bis AM-005 (Registry, Libraries, Matcher), alles ohne Netz/VM/GPU, rein deterministisch und testbar: **geeignet**.
4. AM-006/AM-007 (Bridge, Fake-Dispatch) erst nach Entscheidung D05/D09 (Captain). Core wird nicht verändert (E3 nie automatisch): die Bridge ist ein **neues Modul** neben `control.py`.
5. AM-008 bis AM-016: abhängig von DevVM Phase 6 und Captain-Entscheidungen. Nicht jetzt.

## 5. Offene Entscheidungen für den Captain
- **D01/D03:** Bestätigung: neues Paket `guppi_agent_manager` unter `src/guppi_runtime/agent_manager/`, eigene SQLite-Datei unter `runtime_data/`, kein Eingriff in Mission-JSON.
- **D05:** Wer stellt Admissions aus? Vorschlag: nur der Guard (Captain-Gate), serverseitige Referenz.
- **D09:** Policy für Cloud/Schreiben/Privilegien: Standard bleibt gesperrt.
- **Integration:** wie bei DevVM Phase 5: *Bau ja, Integration nein* (Ergebnisse als Kandidaten unter `devvm_candidates/`).

### Entscheidung des Captains (2026-10-06)
**D01/D03 bestätigt:** eigenes Paket `src/guppi_runtime/agent_manager/` mit eigener SQLite-Datei (`runtime_data/agent_manager/registry.sqlite`), keine Mission-JSON-Dateien, kein Eingriff in `control.py`. Bau als Kandidat in der DevVM (Bau ja, Integration nein). Zuerst AM-002 (Contracts), dann AM-003 (Registry/Persistenz/Outbox).

**D05 festgelegt:** Admissions stellt nur der Guard aus (Captain-Gate), serverseitige Referenz, keine Selbstzulassung.
**D09 festgelegt:** Cloud, Schreiben außerhalb des Arbeitsbereichs und Rechtestufe über 2 bleiben gesperrt, bis der Captain sie ausdrücklich freigibt.
**Gate-Freigabe (Chat, 2026-10-06):** Der Captain gibt die Gates des Integrationsprojekts (Stufen 1 bis 4 des Ablaufplans) frei. Weiter gelten: Core (`control.py`, `guard.py`) wird nicht geändert, kein Gastimage-Wechsel, kein Netz, `target_qualified` bleibt Sache des Captains. Jede Stufe bekommt Sicherung unter `archiv/`, Test und Bericht.

## 6. Abweichungen und Risiken
- Das Archiv nennt `MissionLease`, `WriteLease`, `ControlRun`, `DurableMissionRuntime` als Basis. Alles davon fehlt hier. Tickets AM-006 bis AM-012 gelten deshalb nur als Zielbild und müssen auf `ControlMaster` und `Guard` neu geschnitten werden (eigener ADR).
- Die Archivprüfung (`validate_archive.py`) prüft nur Spezifikation, keinen Produktcode.
- Kleine Modelle vergessen Randfälle (Phase-5-Bericht): AM-002 und AM-005 brauchen Abnahmetests **von außen** (hier von Claude geschrieben, Modell sieht sie nicht), sonst nimmt GUPPI falschen Code an.
