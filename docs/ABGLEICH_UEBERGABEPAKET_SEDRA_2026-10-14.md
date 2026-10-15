# Abgleich: Übergabepaket „GUPPI / SEDRA“ (13.10.) gegen den Code von Runtime v1.20 (Stand 13.10.)

Das Paket `GUPPI_SEDRA_Uebergabepaket_2026-10-13` ist ein Konsolidat aus Projektgesprächen und sagt das selbst: kein Repository gelesen, Statusmatrix am Code zu prüfen, Referenzpfad ein Backup vom 05.10. Dieses Dokument macht genau diese Prüfung gegen den Quellstand, der gestern analysiert wurde (`GUPPI_UIX_Developer_2026-10-13`, Git `ca7be40`, 127 Testdateien mit 1.979 Testfunktionen). Regel des Pakets übernommen: **EXISTING** = am Code/Tests nachgewiesen, **REPORTED** = berichtet, **PROPOSED** = geplant, **OPEN** = unklar.

Kurzfassung: Das Paket unterschätzt den Stand erheblich. Fast alles, was es als PROPOSED oder REPORTED führt (Control Core, Gates mit Bindung, Leases, Recovery, Agent Manager, Modell-Router, Hardware-Pass, Shell), ist in v1.20 vorhanden und getestet – oft unter anderem Namen. Umgekehrt sind einige Entscheidungen im Paket vom realen Stand überholt (Modelle, Verifier, Laufzeit). Wer nach dem Paket arbeitet, würde Dinge zum zweiten Mal bauen.

## 1. Begriffe des Pakets ↔ Module im Code

| Paket (Schiffsmetapher) | Im Code v1.20 | Status |
|---|---|---|
| Kapitän | Captain: Gates per ID (`core/guard.py`, Einmal-Token, 24 h, an Mission/Aktion/Ziel/Digest gebunden) | EXISTING |
| Erster Offizier `guppi_officer` | kein Paket dieses Namens; die Rolle verteilt sich auf `brain.py` (verstehen/planen), `uix_server.chat_reply` (Dialog) und den Entwurf `ABLAUF_GESPRAECH_2026-10-13.md` (G1–G7). Der Name taucht nur als `acceptance.authority` in `agent_manager/devvm_crews.py` auf. | PROPOSED (Entwurf vorhanden) |
| Navigator | `core/brain.py` + `modules/planning.py`: UNDERSTAND → PLAN → READY, Plan-Schritte, Skill-/Tool-Routing (`capability_router`) | EXISTING |
| Maschinenraum / Control Core | `modules/control.py` („control-master“), Guard, `permission_levels`, `step_journal`; in der Oberfläche das Fenster „Maschinenraum“ | EXISTING |
| Seekarte `guppi_knowledge` | `knowledge.py`, `modules/knowledge_module.py`, `devenv/lesson_store.py`, `skill_library/` (Suche mit IDF, 63/366 Skills) | EXISTING (als Modul, nicht als eigenes Paket) |
| Logbuch | `core/audit.py` (hash-verkettet, `.head`-Anker, Schwärzung), `docs/LOGBUCH_AGENT_MANAGER.md`, Fenster „Logbuch“ mit Kettenprüfung | EXISTING |
| Brücke | `uix/` Retro-Desktop (9 Fenster), Fenster „Brücke“; Voice: nicht vorhanden | EXISTING (Desktop) / OPEN (Voice) |
| Funkraum | `tools/web.py`, `tools/git.py`, `tools/shell.py`, alle hinter Guard (externe Schreibaktion = Captain) | EXISTING (Web/Git/Shell) / OPEN (E-Mail, weitere Konnektoren) |
| Laderaum | `artifacts.py`, `runtime_data/context_artifacts`, Kandidaten unter `runtime_data/devvm_candidates` mit Digest | EXISTING |
| Navigation Card | `docs/UIX_ROADMAP.md`, `BUILDFLOW_2026-10-13.md`, `ABLAUF_GESPRAECH_2026-10-13.md`, `historie/DEVELOPMENT_TICKETS_3_PHASES_v1.20.md` | EXISTING (verteilt, kein einzelnes Dokument) |
| GUPPI Entwicklungsumgebung (statt „Sandbox“) | genau so umgesetzt: UI sagt „Entwicklungsumgebung“, technisch `sandbox/` mit microsandbox 0.7.4 (microVM), `technical_backend: sandbox` im API | EXISTING |
| `SOUL.md` je Agent | `agent_manager/devvm_templates.py` schreibt je Rolle `template.yaml` + `SOUL.md` (Version, SHA-256 im Template); Test `test_agent_service.py` | EXISTING |

## 2. Statusmatrix des Pakets, am Code geprüft

| Bereich | Paket | Befund v1.20 | Neuer Status |
|---|---|---|---|
| Control Core ACM v0.2.4, Variante B | REPORTED | Kein Modul heißt mehr ACM; der Kern (`core/`, ~1.200 Zeilen) ist die Weiterentwicklung: Zustandsautomat NEW…COMPLETE, `captain_intent` unveränderlich, Guard, Audit. Kerngrenze wird von `test_core_boundary_src.py` erzwungen. | EXISTING (Variante B ist vollzogen) |
| Sprint 3 Mission/Run/Steps/Gates, Resume | REPORTED (87 Tests) | `core/mission.py`, `step_journal.py` (Checkpoint je Schritt, unterbrochener Schritt wird nie still wiederholt), `/api/mission/run|approve|reject` | EXISTING |
| Sprint 4 Leases, Heartbeat/Fencing, in_doubt | REPORTED | `jobs/testlab.py` (GPU-Lease SQLite, Herzschlag, toter Halter wird abgelöst, seit 13.10. Reservierung mit Vorrang), `jobs/job_supervisor.py` (Leases, Stillstand), `mission_lock.py`; `in_doubt` im Agent Manager ohne Auto-Replay („bewusst kein Knopf erneut starten“) | EXISTING |
| v0.9 Apply & Recovery, Gate-Bindung an Workspace/Patch/Hash | REPORTED | `request_binding.py` (Digest), Schalter-/Routing-Änderung mit `file_sha256`-Bindung und Sicherung, Kandidaten-Übernahme mit `bind_candidate_digest`, `self_integration` mit Rücknahme | EXISTING |
| v1.8 Ready-Test 111 Tests | REPORTED | `READY_TEST_WINDOWS.bat`, `ready_test.py`; aktuelle Suite deutlich größer | EXISTING (Zahl veraltet) |
| Runtime v1.20 | OPEN | liegt vor; Doku `ARCHITEKTUR.md`, `BETRIEB.md`, `ENTWICKLUNG.md`, `MODELLE.md` (alle Stand 12./13.10.) | EXISTING |
| Control Contracts v0.1 (Mission, MissionStep, ControlPort …) | PROPOSED | Verträge existieren unter anderen Namen: Mission-Datensatz (`identity`, `lifecycle`, `plan.steps`, `human_gates`, `execution`, `result`), `modules/base.py` (Modulvertrag), `CONTEXT_MANAGER_CONTRACTS.md`, `JOB_SUPERVISOR_CONTRACTS.md`, Schemas in `architecture/…/schemas/` (44 Dateien). Ein `ExecutionService` gibt es nicht; die Rolle hat `control.execute(mission, action)`. | EXISTING (Namen weichen ab) – **nicht neu entwerfen, sondern dokumentieren** |
| `guppi_common`, `guppi_contract_testkit` | PROPOSED | nicht vorhanden; Funktion teilweise: `core/util.py`, `tests/host_isolation.py`, `suite_helper.py`, G0-Testkatalog `devenv/assert_catalog.py` (von GUPPI gebaut, 13.10.) | PROPOSED – Bedarf prüfen, bevor ein Paket entsteht |
| Officer / Navigator / Seekarte | PROPOSED | Navigator und Seekarte EXISTING (Tabelle oben); Officer als Gesprächsablauf im Entwurf, Chat-Fenster vorhanden, Freigabe-Leiste G7 beschlossen | teils EXISTING, Officer PROPOSED |
| Agent Manager | PROPOSED („DEV-Subagenten berichtet“) | `agent_manager/` (22 Dateien): Registry (SQLite), Templates mit SOUL, Crews, Zuweisungen, Bridge, CLI, Fenster „Besatzung“; Zustände prepared/running/succeeded/failed/in_doubt; alles UNVERIFIED ohne Rechte, Instanz nur über Gate. Hermes ist abgeschlossen (nur noch Quellenangabe in `coder_ext/README.md`, Modell in Quarantäne). | EXISTING (Isolation: microVM für Tests; Agentenprozesse selbst laufen auf dem Host hinter Guard – siehe Punkt 4) |
| Model Router / Hardware-Pass / Profile / USB | PROPOSED | `models/` (23 Dateien): `role_routing`, `routing_profiles` (Modellkombinationen), `hardware_pass`, `gpu_preflight`, `gpu_canary`, `model_loader`, `llama_server_runtime`, `tuning`, `recipe_measure`, `model_removal` (Quarantäne); Hardware-Manager mit Profilen; portable Laufzeit `build_offline_runtime.py`, `local_paths.yaml` (`<modelle>`) | EXISTING; USB-Härtung OPEN |
| Shell / Desktop | PROPOSED („HTML-Demo“) | produktive Oberfläche: `uix_server.py` (Loopback, Token, CSP, Whitelist), 15 JS-Module, 9 Fenster, alle an `/api/...`; Browser-Abnahme `uix_check.py` seit 13.10. | EXISTING |
| Design-Skills (2 Stück) | PROPOSED | nicht vorhanden | PROPOSED |
| Linux VM | OPEN | nicht vorhanden; Server ist plattformneutral, nur `processes_view`/`uix_start` nutzen PowerShell | OPEN |

## 3. Wo das Paket vom realen Stand überholt ist

1. **Modelle.** Paket: „Qwen3.5-Familie, Kev einziger Verifikationsbaustein, Jev entfällt, Ollama/LM Studio in Benutzung.“ Code und `MODELLE.md`: Hauptmodell **Qwen3.6-35B-A3B** auf eigenem **llama-server** (Engine b11160, Flash Attention, KV q8_0); Qwen3.5-9B nur als schneller Unteragent/Canary; Prüfer ist **Gemma-4-12B** (`verifier.llama_gemma`); das Rezept `verifier.local_kev` existiert, ist aber **deaktiviert**; LM Studio ist nur noch Erkennung fremder Server (`models/lmstudio.py`), Ollama kommt im Code nicht vor. → Modellstrategie des Pakets nicht übernehmen; `MODELLE.md` ist die Quelle.
2. **Hermes.** Paket: „Pilot, unflexibel, künftig direkt.“ Erledigt: direkte Subagenten in `devvm_agents.py`/`agent_manager`, Hermes-Modell am 12.10. in Quarantäne, zwei Coder-Erweiterungen (E-01, E-08) haben Hermes-Code als Quelle.
3. **Begriff „Sandbox“.** Paket fordert die Umbenennung in der Oberfläche – ist umgesetzt (`ui_name: GUPPI Entwicklungsumgebung`, `technical_backend: sandbox`).
4. **Referenzpfad.** `…_Backup_2026-10-05` ist acht Tage und mehrere hundert Commits-Äquivalente hinter dem Stand vom 13.10. (Paketaufteilung 12.10., Solo-Workflow 10.10., Testkatalog 13.10.). Für jede weitere Übergabe das Archiv vom 13.10. oder neuer nehmen.
5. **Name SEDRA.** Kommt im gesamten Repository nicht vor (0 Treffer). Wenn der öffentliche Name gilt, ist das eine bewusste Entscheidung für README/Produkttexte; im Code bleibt GUPPI, wie das Paket es auch vorsieht.
6. **Testzahlen.** 87 / 111 sind historisch; heute 1.979 Testfunktionen in 127 Dateien, Regel „nur betroffene Tests“ aus `ENTWICKLUNG.md`.

## 4. Offene Prüfungen des Pakets – beantwortet, soweit der Code es hergibt

| Verifikationsfrage (Paket, Abschnitt 10) | Antwort |
|---|---|
| 1. Welche Module/Ports/Tests existieren? | `ARCHITEKTUR.md` (12.10.) listet jedes Modul mit Aufgabe; API-Routen in `uix_server.py` (26 GET- und 25 POST-Routen, Lese-Routen im Code markiert). |
| 2. Welche ACM-Contracts weiterverwenden? | Die Frage ist überholt: ACM ist im Kern aufgegangen. Verträge = Missionsdatensatz, Modulvertrag `modules/base.py`, Schemas im Architekturordner. |
| 3. Commit-/Versionsbelege, Testreports? | Git lokal ab 01.10. (6 Tage mit Commits, kein Push: Entscheidung 07.10.), `TEST_REPORT_2026-10-05.md`, Logbuch mit Uhrzeiten, `historie/TEST_REPORT_v1.20.txt`. |
| 4. Was ist read-only verlässlich? | Alle `/api/...`-GET-Routen und die als read-only markierten POSTs; schreibend nur über Gate (Schalter, Routing, Kandidat, Modell laden unter Lease). |
| 5. Welche Agenten/Isolation sind real? | Tests der Kandidaten laufen in der microVM (microsandbox, Grenzprüfung `SANDBOX_BOUNDARY_STATUS.md`, `target_qualified` weiter `false`, einziger Blocker `target_boundary_acceptance_pending`); die Modellaufrufe der Agenten laufen auf dem Host über den Control Master hinter Guard. Fenster „Besatzung“ zeigt echte und Demo-Zuweisungen getrennt. **Vollständige Prozess-Isolation der Agenten: OPEN.** |
| 6. Recovery, unknown, paralleler Resume? | `step_journal` (kein stilles Wiederholen), `mission_lock.execution_lock`, Leases mit Herzschlag, `in_doubt` ohne Auto-Replay, `uix_start` räumt verwaiste Server nur auf, wenn der Starter tot ist. Gezielte Race-/Crash-Tests: `test_job_store_locking.py`, Sperrtests in den Missions-/TestLab-Tests; ein dedizierter Doppelausführungs-Test über zwei Prozesse fehlt → **OPEN, kleines Ticket.** |
| 7. UI-Schnittstellen für Design-Skills? | Vorhanden und stabil: `/api/status`, `/api/missions`, `/api/mission/details`, `/api/models`, `/api/processes`, `/api/diagnose`, `/api/agents`, `/api/meter`, `/api/resources`, `/api/routing`, `/api/context`, `/api/audit`; Dateien `uix/css/desktop.css` (Tokens als `:root`-Variablen), `uix/js/*.js`, `retro_desktop.html`. |

## 5. Der UI-Teil des Pakets (04) gegen die Oberfläche von heute

Beschlossenes Prinzip laut Paket: XP-nahe Shell, Icons sind nur Launcher, Module in getrennten Fenstern, Agent Manager eigenes Fenster, Trennung UI / Control Core / Betriebssystem. **Alles davon ist umgesetzt** – die UIX liest nur über `/api`, speichert keinen Runtime-Zustand, Launcher öffnen Fenster, „Besatzung“ hat Icon und Fenster. Die Taskleisten-Launcher sind seit gestern an ihr Fenster gekoppelt (ein Knopf je Fenster), ohne technische Kopplung an eine Runtime.

Was aus dem Paket noch fehlt und wie es zur bestehenden UIX-Roadmap passt:

| Paket (verbindliche Reihenfolge) | Stand | Anschluss an `UIX_ANALYSE_2026-10-13.md` |
|---|---|---|
| 1. Style Manifest v0.2 | nicht im Repo; Ist-Zustand: 13 Farb-/Schatten-Tokens in `:root`, Schrift Tahoma/Verdana, Fensterrahmen, Karten, Badges, Phasenfarben – implizit konsistent, nirgends aufgeschrieben | Ein kurzes `docs/UIX_STYLE_MANIFEST.md` aus dem vorhandenen CSS ableiten (Tokens, Karten, Badges, Abstände, Zustandsfarben ok/warn/bad). 1–2 Stunden, kein Code. |
| 2. Shell Architecture (UI / Core / OS trennen) | de facto vorhanden (Server = Vermittler, UIX = Darstellung, Runtime = Zustand) | In das Manifest aufnehmen: Welche Datei was darf (JS liest `/api`, schreibt nie Runtime-Zustand; `localStorage` nur Anzeige-Komfort). Die Browser-Abnahme `uix_check.py` ist der Beleg dafür. |
| 3. Design-Tokens + Komponenten-Katalog | Tokens teilweise; Komponenten ohne Katalog (9 fast identische Titelleisten im HTML) | = Vorschlag 4.3 Nr. 12 der Analyse (Fenstervorlage `<template>` + `makeWindow`). Das ist der erste echte Komponenten-Katalog-Schritt und zugleich Voraussetzung für mehrere Verarbeitungsfenster. |
| Themes zur Laufzeit, Mac-Skins als Option | nicht vorhanden; Hardware-Seite dunkel, Desktop hell (Bruch) | = Vorschlag 4.3 Nr. 15. Erst nach Tokens sinnvoll: ein Theme = ein zweiter `:root`-Block, umschaltbar, rückgängig per Reload. |
| 4. Linux-Machbarkeit in VM | OPEN | Server läuft bereits unter Linux (gestrige Prüfung lief dort); nur `processes_view`/`uix_start`/`gpu_preflight` brauchen PowerShell → `platform`-Weiche mit `ps`/`nvidia-smi`. Kleines Ticket, wenn gewünscht. |
| Zwei Design-Skills | PROPOSED | Erst nach Manifest + Katalog, sonst bauen sie auf erdachten Ports auf – das Paket sagt das selbst richtig. |

## 6. Empfehlung: Navigation Card auf den echten Stand setzen

- **Priorität 0 (Inventar, Port-Landkarte, Statusabgleich):** mit `ARCHITEKTUR.md`, `UIX_ANALYSE_2026-10-13.md` und diesem Dokument erledigt. Offen bleibt nur ein Zwei-Prozess-Test für parallele Ausführung (Punkt 4, Frage 6).
- **Phase 1 (Verträge, lesender Golden Path):** existiert – Chat → Plan-Karte → `/api/mission/details` → Ergebnis ist genau dieser Pfad. Nicht neu bauen. Sinnvoll: die vorhandenen Verträge an einem Ort beschreiben (ein `docs/VERTRAEGE.md`, das Missionsdatensatz, Modulvertrag, Gate-Bindung und API-Routen zusammenfasst), statt `guppi_common`/`contract_testkit` als neue Pakete anzulegen.
- **Phase 2 (schreibender Golden Path mit Gate, Apply, Recovery):** existiert für Schalter, Routing, Kandidaten-Übernahme und Selbst-Integration. Offen: der im Entwurf `BUILDFLOW_2026-10-13.md` beschriebene Ablauf Aufgabe → Spec → Bau → Abnahme → Übernahme als eine Funktion – das ist die eigentliche nächste Baustelle, nicht Phase 1.
- **Phase 3 (Officer, Freigabe-Leiste, Shell):** Officer = Gesprächsablauf G1–G7 (Specs `gate_bar`, `buildflow_core`, `build_request`, `spec_standards` liegen in der Nachtkette G); Shell = Manifest → Fenstervorlage → Themes wie oben.
- **Nicht übernehmen:** Modellstrategie „Qwen3.5 + Kev“, Begriff ACM, Testzahlen, Referenzpfad vom 05.10.
- **Namensfrage SEDRA:** Entscheidung des Captains; technisch berührt sie nur README und Fenstertitel.

## 7. Dateien

- Dieses Dokument: `docs/ABGLEICH_UEBERGABEPAKET_SEDRA_2026-10-14.md`
- Grundlage: `GUPPI_SEDRA_Uebergabe_2026-10-13/*` (10 Dateien, 16,7 KB) und das Repository vom 13.10. (`ca7be40` + die UIX-Korrekturen vom 13.10.)
