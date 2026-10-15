# Architektur von GUPPI OS

Stand 12.10.2026. Beschreibt den Code in `runtime/src/guppi_runtime/`. Seit der Paketaufteilung vom 12.10. liegen die Module in Unterpaketen: `core/`, `jobs/`, `models/`, `devenv/`, `selfdev/` (dazu die älteren `agent_manager/`, `coder_ext/`, `sandbox/`, `tools/`, `modules/`, `hardware_manager/`, `capabilities/`). Die alten Namen direkt unter `guppi_runtime` sind Weichen auf dieselben Module; oben geblieben sind die Startmodule (`cli`, `uix_start`, `uix_server`, `pc_diagnose`, `devvm_mcp`), `runtime`, `local_paths`, `local_switches` und einige kleine Hilfsmodule. Die formale Architektur, also Registry, Guard-Regeln und Verträge, liegt in
`architecture/GUPPI_Architecture_v1.20_SELF_DEVELOPMENT/` und wird beim Start geladen.

## Überblick

```
 Captain ── Oberfläche (uix_server, Retro-Desktop)  ·  CLI (guppi …)  ·  Agent-Manager-CLI
                │
           GuppiRuntime (runtime.py) ── baut alle Teile beim Start zusammen
                │
   ┌────────── Kern ───────────┐   ┌──── Jobs ────┐   ┌──── Modelle ─────┐   ┌──── Selbstentwicklung ────┐
   │ brain · mission · bus     │   │ job_supervisor│   │ role_routing     │   │ devvm · devvm_agents      │
   │ guard · permission_levels │   │ job_worker    │   │ llama_server_rt  │   │ devvm_tools · coder_ext   │
   │ audit · step_journal      │   │ resource_sched│   │ model_loader     │   │ self_development          │
   │ registry · util           │   │ context_mgr   │   │ gpu_canary       │   │ self_integration          │
   └───────────────────────────┘   └───────────────┘   └──────────────────┘   └───────────────────────────┘
                │                                                                    │
           Tools (filesystem, git, shell, web, sandbox …)            microVM (microsandbox) für alle Tests
```

## 1. Kern

Der Kern ist klein, rund 1.200 Zeilen, und liegt seit dem 12.10.2026 im eigenen Paket **`guppi_runtime/core/`**. Er importiert nichts außerhalb dieses Pakets,
vor allem nichts aus DevVM, Agent Manager oder coder_ext. Das prüft `tests/test_core_boundary_src.py` mit dem von GUPPI gebauten Modul `core_boundary.py`,
direkt und über Umwege.

Die alten Namen (`guppi_runtime.util`, `guppi_runtime.guard` …) sind zweizeilige Weichen auf **dasselbe** Modulobjekt in `core/`. Bestehende Importe,
`mock.patch`-Ziele und laufende Skripte funktionieren deshalb unverändert. Neuer Code importiert aus `guppi_runtime.core`.

| Modul | Aufgabe |
|---|---|
| `mission.py` | Missionsdatei und Zustandsautomat: NEW → UNDERSTAND → PLAN → READY → EXECUTE → VERIFY → COMPLETE, dazu PAUSED, CAPTAIN_REVIEW, REWORK, CANDIDATE_REVIEW und FAILED. `captain_intent` ist unveränderlich. |
| `brain.py` | Führt eine Mission Schritt für Schritt durch die Phasen. Höchstens 3 Nacharbeits-Runden; eine neue Ausführung nach einer Nacharbeit braucht eine Freigabe. |
| `message_bus.py` | Verbindet das Brain mit den Modulen `planning-context`, `control-master`, `verification`, `knowledge` und `communications` (in `modules/`). |
| `guard.py` | Entscheidet jede Aktion nach `core/guard/guard_rules.yaml`: ALLOW, BLOCK oder CAPTAIN_REQUIRED. Eine unbekannte Aktion braucht immer den Captain. Freigaben sind Einmal-Token, an Mission, Aktion, Ziel und Auftrags-Digest gebunden und 24 h gültig. |
| `permission_levels.py` | Stufen 0–6 (READ_ONLY … EXTERNAL_ACTION) als Obergrenze **über** dem Guard: Sie können nur öfter Nein sagen, nie Ja, wo der Guard fragt. |
| `audit.py` | Hash-verkettetes Ereignisprotokoll mit `.head`-Anker gegen Abschneiden; Schlüssel wie `*_token` und `*_password` werden geschwärzt. Reparatur: `guppi audit-repair`. |
| `step_journal.py` | Checkpoints je Planschritt. Ein unterbrochener Schritt wird nie still wiederholt; fertige Artefakte werden per Hash geprüft. |
| `registry.py` | Lädt Module, Dienste, Skills und Tools aus der Architektur und prüft den Kernvertrag. |
| `util.py`, `mission_lock.py` | Atomares Schreiben mit fsync, Datei-Sperren auf Betriebssystemebene (werden beim Prozessende frei). |
| `request_binding.py`, `errors.py`, `manual_plan.py` | Digest, an den eine Freigabe gebunden ist; Fehlerklassen; Prüfung von Artefakt-Plänen, die der Captain vorgibt. |

Guard-Regeln, die man kennen sollte: Lesen und neue Artefakte sind erlaubt. Überschreiben, Löschen, Shell, Sandbox-Läufe, Modellsteuerung, Selbst-Integration,
Modell-Entfernung und jede externe Schreibaktion brauchen den Captain. `modify_core_invariants`, `bypass_guard` und `silent_stable_replacement` sind gesperrt.

## 2. Jobs und Ressourcen (`jobs/`)

| Modul | Aufgabe |
|---|---|
| `job_supervisor.py` | Entwicklungs-Jobs mit Warteschlange, Leases, Herzschlag, Stillstand-Erkennung, Wiederholungsregeln und Freigaben über das Permission-Gate. |
| `job_worker.py` | Führt Jobs mit einem Modell aus; erkennt Müll-Ausgabe (`degenerate`) und startet den Server dann neu. |
| `resource_scheduler.py` | Reserviert VRAM, RAM und KV-Cache vor dem Start, mit Reserve. |
| `context_manager.py`, `context_assembly.py`, `working_set.py`, `context_budget.py` | Messen, Auslagern und Zusammenfassen von Kontext, damit ein Job im Fenster des Modells bleibt. |
| `token_policy.py` | Denkaufwand und Ausgabebudget je Rolle. |
| `testlab.py` | **GPU-Lease** (SQLite unter `runtime_data/testlab/testlab.db`): Nur ein Prozess darf zur Zeit Modelle laden. Der Herzschlag läuft im Hintergrund, ein toter Halter wird abgelöst. |

Diese Teile lassen sich einzeln ein- und ausschalten. Eine fehlende oder kaputte Konfiguration schaltet den Teil ab; `boot()` meldet dann den Grund (`*_error`), statt abzubrechen.

## 3. Modelle (`models/`)

Die Adapter (`models/base.py`, `router.py`, `lmstudio.py`, `llamacpp.py`, `openai_local.py`, `runtime_control.py`) lagen schon dort; dazu kamen am 12.10. Routing, Server, Laden, Canary, Engine und Messungen.

| Modul | Aufgabe |
|---|---|
| `role_routing.py`, `routing_profiles.py` | **Rezepte** in `workspace/GUPPI_OS/local_config/role_routing.yaml`: welches Modell welche Rolle übernimmt (coder, planner, reviewer, verifier …), mit Datei, Servereinstellungen, gemessenem VRAM und Kontextgrenzen. Dazu die Gesundheit der Anbieter und Profile, die der Captain umschalten kann. |
| `llama_server_runtime.py` | GUPPIs eigener llama-server (Engine `engines/llama.cpp/b11160`, Port 8089), starten, überwachen, MTP-Vorhersage. |
| `gpu_canary.py` | GPU-Selbsttest mit kleinem Modell auf Port 8093: einmal pro Windows-Start und nach jedem Server-Absturz. Schlägt er fehl, werden keine Modelle geladen (`gpu_canary_failed`). |
| `model_loader.py`, `models/` | Laden und Entladen, Adapter für llama.cpp und LM Studio. LM Studio ist auf Wunsch des Captains abgeschaltet. |
| `model_removal.py` | Modelle sicher entfernen: Die Dateien kommen in die Quarantäne `_guppi_entfernt/<ID>/`, die zugehörigen Rezepte werden ausgeschaltet. Wiederherstellen mit `guppi model-restore`. Endgültig löscht nur der Captain. |

## 4. Selbstentwicklung (`devenv/`: Entwicklungsumgebung und Coder · `selfdev/`: E1–E3, Kandidaten, Abnahme, Integration)

| Modul | Aufgabe |
|---|---|
| `self_development.py` | Stufen E1/E2/E3. E1 = neue Fähigkeit, E2 = Erweiterung, E3 = Kern. Keine Stufe aktiviert sich selbst. E2 und E3 brauchen immer den Captain, E3 wird nie automatisch aktiviert. |
| `self_integration.py`, `candidate_acceptance.py` | Übernahme eines abgenommenen E1-Moduls nach `guppi_runtime/capabilities/` (nur neue Dateien), mit Rücknahme. Guard-Regeln GR-025/026. |
| `devvm.py` | Arbeitsordner mit Git (in Python) auf dem Host; Code wird nur in einer Kopie in der microVM ausgeführt. |
| `devvm_tools.py`, `model_tools.py` | Werkzeuge der Modelle: Datei lesen (in Teilen), schreiben, `edit_file`, Gliederung, Syntaxprüfung, Tests in der VM, Abgabe. |
| `devvm_agents.py` | Orchestrator und Agenten-Schleife: Modi solo (Standard), escalating, pipeline, delegating; Verdichtung des Verlaufs bei 60 % des Fensters, Schleifenwächter. |
| `devvm_evidence.py` | Liest das Ergebnis eines versteckten Tests aus und nennt die erste falsche Aussage mit beiden Werten. Das ist der Fehlerbericht für die Nacharbeit. |
| `devvm_style.py` | Aufräumen nach jedem Coder-Zug: Kommentare und Hilfsdateien entfernen, lange Funktionen und kopierten Code melden. |
| `coder_ext/` | Von GUPPI gebaute Erweiterungen des Coders, mit `--coder-ext` einschaltbar: E-01 erst lesen, dann ändern · E-02 Denkbudget · E-03 Antworten ohne Werkzeugaufruf · E-04 Aufzeichnen und Abspielen · E-05 alte Ergebnisse kürzen · E-07 Werkzeugkarten · E-08 tolerantes Ändern · E-09 Syntaxhinweis · bg_jobs · lesson_cards. |
| `sandbox/` | microVM über microsandbox: Broker, Provider, Worker. Ohne qualifizierte VM werden keine Tests auf dem Host ersatzweise ausgeführt. |
| `loop_guard.py`, `rework_watch.py`, `runaway_guard.py` | Erkennen Wiederholungsschleifen, endlose Nacharbeit und ausufernde Ausgaben. |
| `acceptance_suite.py`, `acceptance_vm.py` | Abnahme-Suiten für Agenten und Module in der microVM. |

Wie ein Bau abläuft, beschreibt [ENTWICKLUNG.md](ENTWICKLUNG.md).

## 5. Agent Manager

`agent_manager/`: Register von Agenten-Vorlagen (SQLite), Import mit Vorprüfung, Instanzen, Crews, Beförderung nur über eine Abnahme-Suite und ein Code-Zähler
(`code_meter`, `meter_service`: wie viel Code GUPPI und wie viel Claude geschrieben hat). Die CLI ist `python -m guppi_runtime.agent_manager.cli`, Befehle:
propose, hire, suite, review, gaps, promote, crew, plan, stop, status … Jeder Lauf, der Modelle startet, ist ein Gate, das der Captain freigibt
(`run_worker.py` startet ihn erst dann). Logbuch: [LOGBUCH_AGENT_MANAGER.md](LOGBUCH_AGENT_MANAGER.md).

## 6. Oberfläche und Werkzeuge

- `uix_server.py` + `uix/` – Retro-Desktop mit den Fenstern Missionen, Agenten, Modelle, Chat, Nacharbeit, Status und Code-Zähler. `uix_start.py` ist der einzige Start:
  Es gibt keinen zweiten Server neben einem laufenden, übrig gebliebene llama-Server werden beendet, und `--replace` ersetzt eine laufende Oberfläche.
- `cli.py` – `guppi …` (bzw. `python -m guppi_runtime …`): doctor, Missionen, Freigaben, Modelle, Hardware, Sandbox, Kandidaten, Audit. Liste: [BETRIEB.md](BETRIEB.md#befehle).
- `tools/` – filesystem (nur im Werkzeugordner, keine Symlinks), git, shell (Gate), web (nur lesend, Liste in `config/web_access.yaml`), Hardware- und Modellsteuerung.
- `hardware_manager/` – Hardware erfassen, Energieprofile (mit Gate), Dashboard.
- `devvm_mcp.py` – MCP-Server für einen DevVM-Arbeitsordner ([MCP_SERVER_DEVVM.md](MCP_SERVER_DEVVM.md)).

## 7. Daten und Ordner

| Ort | Inhalt | im Git? |
|---|---|---|
| `runtime/src/guppi_runtime/` | Quellcode | ja |
| `runtime/config/` | Konfiguration (Paket-Vorgaben) | ja |
| `runtime/tests/` | 117 Testdateien (unittest) | ja |
| `runtime/benchmarks/` | Bau- und Messskripte, Specs, versteckte Tests, Referenzen, Seeds, Proben | ja |
| `architecture/` | formale Architektur, Guard-Regeln, Registry | ja |
| `workspace/GUPPI_OS/` | **Projektordner im Betrieb**: `local_config/` (Rezepte, Schalter), `runtime_data/` (Missionen, Audit, Jobs, Messungen, Kandidaten, Logs) | nein |
| `engines/` | llama.cpp-Builds | nein |
| `<modelle>\` | GGUF-Modelldateien | nein |
