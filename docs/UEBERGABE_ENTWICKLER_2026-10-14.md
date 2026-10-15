# Entwicklerübergabe GUPPI – Stand 2026-10-14

Dieses Paket ist der committete Stand des Repos (git archive). Nicht enthalten: Modelle (GGUF), `runtime_data/`, `workspace/`, `.venv`, `local_paths.yaml` (lokale Pfade), Messdaten, uncommittete Arbeitsdateien.

## Einstieg
1. `README.md` (Überblick, Grundsätze), `docs/ARCHITEKTUR.md`, `docs/BETRIEB.md`.
2. `START_HERE.txt`, `ERSTER_START.bat`, `START_GUPPI.bat` (Windows, Python 3.13/3.14).
3. Lokale Pfade: `local_paths.yaml` aus der Vorlage `local_paths.example*` / Platzhaltern anlegen (`runtime/src/guppi_runtime/local_paths.py`).
4. Tests (nur betroffene laufen lassen): `cd runtime; set PYTHONPATH=src; python -m unittest tests.test_buildflow_flow tests.test_buildflow_blocks`.

## Paketstruktur
Module liegen in `runtime/src/guppi_runtime/{core,jobs,models,devenv,selfdev}`. Die Top-Level-Dateien sind Shims – immer die Datei im Unterpaket bearbeiten.

## Arbeitsweise (Selbstentwicklung)
- GUPPI baut, Claude/Entwickler schreibt Spezifikationen, versteckte Tests, Referenzen und Reviews: `docs/ENTWICKLUNG.md`, `docs/SOLO_WORKFLOW.md`.
- Specs `runtime/benchmarks/devvm_specs/`, Referenzen `devvm_refs/`, Prüfung vor dem Bau: `benchmarks/spec_check.py`.
- Buildflow (Spec → Bau → Abnahme → Übernahme) als Befehl: `guppi --root <projekt> buildflow ...`, Beschreibung `docs/BUILDFLOW_2026-10-13.md`.
- GPU-Sperre (TestLab) vor jedem Modellstart halten: `docs/TESTLAB.md`.
- Logbuch: `docs/LOGBUCH_AGENT_MANAGER.md` (Einträge nur über `benchmarks/logbook.py`).

## Stand
- Skill-Bibliothek (`skill_library`) gebaut und gemessen, standardmäßig aus.
- Alle Blöcke der Nachtkette G von GUPPI gebaut und übernommen: assert_catalog, gate_bar, buildflow_core, review_report, adopt_plan, build_log (2 Zeilen von Claude korrigiert), build_request, spec_standards; dazu Buildflow-Store/-Runner/-CLI.

## Offen
- Echte Freigabe-Schalter (`approve-spec`, `approve-adopt`) als Mission-Gates; Anbindung an das Fenster „GUPPI Chat“ und die Freigabe-Leiste unter dem Gespräch (Blöcke G5, G7).
- Erste echte Aufgabe über `guppi buildflow`; Messung Weg B (zweiter Slot).
- Nachtkette B (Kontextleiter, Qwen3-Coder) ist auf 23:00 verschoben; Nachtkette-Dateien der anderen Sitzung sind uncommittet und nicht im Paket.
- Kein Push zu GitHub (Vorgabe des Captains).
