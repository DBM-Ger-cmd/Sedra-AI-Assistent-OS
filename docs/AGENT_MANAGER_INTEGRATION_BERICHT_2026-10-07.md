# Agent Manager: Integrationsbericht (2026-10-07)

Auftrag: Das Archiv `GUPPI_Agent_Manager_Developer_Archive_v1.0.zip` (Spezifikation) in GUPPI integrieren, soweit ohne Hardware-Messung möglich. Das Logbuch (`docs/LOGBUCH_AGENT_MANAGER.md`) enthält jeden Schritt; Fehleranalyse in `docs/AM_BAU_FEHLERANALYSE_2026-10-07.md`; Auswertung der Eingriffe (Entwurf) in `docs/EINGRIFFE_CLAUDE_AUSWERTUNG_2026-10-07.md`.

## 1. Stand je Stufe des Ablaufplans
| Stufe | Inhalt | Stand |
|---|---|---|
| 0 | Kandidaten in der DevVM bauen (AM-002 bis AM-005) | **fertig**: alle 4 Kandidaten bestehen die versteckten Abnahmetests |
| 1 | Übernahme nach `src/guppi_runtime/agent_manager/` | **fertig**: AM-002, 003, 004, 005 |
| 2 | Nur lesen: strenger YAML-Loader, Dienst, Templates als UNVERIFIED, Route | **fertig**: `yaml_loader`, `service`, `view`, `/api/agents` |
| 3 | Matcher | **fertig**: `agent_matcher` (GUPPI), im Dienst als `match_templates` |
| 4 | Fake-Brücke mit Guard (D05/D09) | **fertig**: `bridge.py`, nur Fake-Runtime, alle Antworten `demo: true` |
| 5 | DevVM anbinden | **teilweise**: 5 DevVM-Rollen als Templates (`devvm_templates`, `bootstrap`); Lauf über den Manager **offen** |
| 6 | Fenster (nur lesend) | **fertig**: Fenster „Besatzung", Icon, Startmenü, Taskleiste, Brückenleiste |
| 7 | Echte Isolation, GPU-Reservierung, Messung | **zurückgestellt** (Captain: bis zum Abschluss ohne Hardware-Messung) |
| 8 | Release, Packs, Logbuch-Betrieb | offen |

## 2. Was jetzt im System ist
- **Paket** `runtime/src/guppi_runtime/agent_manager/` (1833 Zeilen): `agent_contracts`, `agent_registry`, `agent_import`, `agent_matcher` (von GUPPI gebaut, 1419 Zeilen), `yaml_loader`, `service`, `bridge`, `view`, `devvm_templates`, `bootstrap` (von Claude, 414 Zeilen).
- **Oberfläche** `uix/js/agents.js` und Änderungen an `retro_desktop.html`, `desktop.css`, `missions.js`; Route `/api/agents` in `uix_server.py`.
- **Daten** `workspace/GUPPI_OS/runtime_data/agent_manager/registry.sqlite` mit den 5 DevVM-Rollen (UNVERIFIED, ohne Befund).
- **Tests** 2329 Zeilen in 14 Testdateien; Lauf 2026-10-07: **272 Tests grün** (1 übersprungen), darunter `test_uix_server` (57), die DevVM-Tests (50) und alle Agent-Manager-Tests mit Abnahmetests von außen.
- `control.py` und `guard.py` sind **unverändert**. Geänderte bestehende Dateien (alle mit Sicherung unter `archiv/`): `uix_server.py`, `devvm_agents.py`, `devvm_build.py`, `devvm_agents_bench.py`, `retro_desktop.html`, `desktop.css`, `missions.js`.

## 3. Sicherheitslage
- Zulassung nur über den Guard (D05): Zuweisung braucht ein Token, das für genau diesen Agenten, diese Mission und diese Eingabe ausgestellt wurde, einmalig.
- Alle Templates sind UNVERIFIED und haben keine Rechte; behauptetes Vertrauen im YAML wird gemeldet (`claimed_trust`) und nicht übernommen. Fremde YAML mit doppelten Schlüsseln, Ankern, Tags, Merge-Keys werden abgelehnt.
- Ausführung nur über die Fake-Runtime; ein unsicherer Start wird nie wiederholt, `unknown` wird nie zu `failed`.
- Kein Netz, kein Image-Wechsel, `target_qualified` unberührt, nichts nach GitHub gepusht (lokales Git mit 3 Commits).

## 4. Bekannte Grenzen und offene Punkte
1. **Die Oberfläche zeigt das neue Fenster erst nach Neustart** (die Startseite wird beim Start geladen): `START_GUPPI_UIX.bat` (nutzt `uix_start --replace`). Ich habe die UIX nicht selbst gestartet, weil sie Modelle laden kann und die GPU gerade vom Bau gehalten wurde.
2. **Lauf über den Manager** mit dem echten DevVM-Orchestrator fehlt (braucht Ausführung auf der GPU, Isolation und Messung, also Stufe 7).
3. **Keine Instanzen**: Es gibt Templates, aber noch keine zugelassenen Agenteninstanzen; der Matcher schließt Templates deshalb zu Recht aus. Instanziierung braucht eine GUPPI-Entscheidung und ein Gate.
4. **Modelltests**: 35 fehlerhafte Tests der Modelle (4 + 13 + 18) wurden entfernt, die Originale liegen unter `archiv/bak_dateien/runtime/*.model-original-2026-10-07`.
5. **Codequalität der Modelle**: `agent_matcher.py` 486 Zeilen mit 41 Kommentarzeilen trotz Regel „keine Kommentare"; `agent_registry.py` 454 Zeilen. Aufräumen steht in der Auswertung.
6. **Crews, DAG, Packs, Logbuch-Betrieb** (AM-009, 013 bis 016) sind nicht begonnen.

## 5. Nächste Schritte (Vorschlag)
1. UIX neu starten und das Fenster mit den echten Daten ansehen.
2. Auswertung „warum musste Claude eingreifen" (siehe Entwurf), Lösungen b, c, g zuerst bauen und messen.
3. MCP-Zugang Stufe 1 (nur lesend, mit Schutz vor Prompt-Injektion beidseitig).
4. Danach Hardware-Stufe, Instanzen, Crews.

## Nachtrag 2026-10-08
Stand je Stufe nach dem zweiten Tag (Details im Logbuch):
| Stufe | Stand |
|---|---|
| 4 Fake-Brücke | fertig; **echter Runtime-Anschluss** (`devvm_runtime.py`, `run_worker.py`): Lauf = DevVM-Build einer benannten Spec, losgelöster Worker, nur Spec-Name als Eingabe, `stop` mit Prozessbaum nach PID, Ausgang in `done.json`; Kommandozeile `agent_manager.cli` (propose, approve, reject, submit, stop, status); alles über Gates und im Audit; 3 Läufe gemacht (1 gestoppt wegen Konfigurationsfehler, 1 gestoppt auf Anweisung, 1 beendet) |
| 5 DevVM anbinden | **fertig für Läufe über den Manager**; DevVM-Rollen als Templates; Orchestrator-Optionen `check_first`, `parallel_check`, `checker`, `arbiter`, `tidy` (alle standardmäßig aus), Belege für den Schiedsrichter (`devvm_evidence.py`) |
| Instanzen und Beförderung | **neu fertig**: `instances.py`, Gates `agent.instantiate` und `agent.promote`, Abnahme-Suiten als Voraussetzung, unabhängige Prüfung, `revoke` ohne Gate, Matcher auf Instanzen |
| Abnahme-Suiten | **neu fertig**: `acceptance_suite.py`, `acceptance_vm.py`, `benchmarks/acceptance_suites.py`; 5 Suiten (29 Kriterien) ausserhalb jedes Modell-Arbeitsbereichs |
| 6 Fenster | Reiter Besatzung zeigt Instanzen (Stufe, Zulassung, Status, Abnahme, Prüfung, Läufe) |
| Crews, DAG, Packs (AM-009, AM-015) | offen |
| 7 Hardware, 8 Release | zurückgestellt bzw. offen |

Tests am 2026-10-08: 185 Agent-Manager-Tests, 292 weitere (DevVM, Suiten, UIX, Runtime, Rechtestufen) grün; Probe an den echten Daten in einem Kopie-Ordner (Registry-Kopie, echter Guard, Suite und microVM-Richter): jeder Schritt wie vorgesehen, die echte Registry blieb unberührt. Bekannte Grenzen: Der Prüfer in der Probe war simuliert (ein zweites Modell hat noch nichts geprüft); Instanzen in der echten Registry gibt es erst nach einem Gate des Captains (`cli hire`).
