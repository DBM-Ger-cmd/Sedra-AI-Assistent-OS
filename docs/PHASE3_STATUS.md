# PHASE3_STATUS – Context Manager v1

Stand: 2026-10-01 · Testumgebung: Windows 11, Python 3.14.7. **Keine Modelle, kein Zielgerät.**

**Ergebnis:** `python -m unittest discover -s tests` → **553 Tests, 0 Fehler, 5 übersprungen** (die 5 sind Symlink-Tests, siehe PHASE0_STATUS). `validate_package.py` und `compileall` OK.
Der Context Manager ist **standardmäßig AUS** (`context_manager.enabled: false` in `config/job_supervisor.yaml`). Dann wird nichts gemessen, ausgelagert oder gespeichert.

## Umfang (Schritte 1–5 aus `CONTEXT_TOKEN_PLAN.md` §7)

Child-Isolation, Fresh-Context-Aufbau und Repair (Schritt 6) sind **Phase 4** und noch nicht vorhanden.

| Schritt | Umsetzung | Datei |
|---|---|---|
| 1 Messen | `TokenEstimator`, `MetricsRecorder` | `context_manager.py` |
| 2 Budget | `BudgetResolver` (kleinstes bekanntes Fenster, nutzt weiter `ContextBudgetManager`) | dito |
| 3 Offloading | `OutputOffloader`, `ArtifactStore.get`, `register(job_id=…)`, `read_range` | dito, `artifacts.py` |
| 4 Checkpoint | `CheckpointWriter`, `collect_pins` | dito |
| 5 Watermarks | `ContextManager.on_watermark`, `trim_to_target`, `health` | dito |

Weitere Änderungen: `models/openai_local.py` reicht `usage` durch (`normalize_usage`, nie geraten), `modules/control.py` misst Inferenz (nur mit Flag, ein Fehler dabei bricht nichts und wird auditiert), `runtime.py` verdrahtet und meldet Status in `boot()`, `uix_server.py` hat `/api/context` (nur lesend), `self_development.start()` nimmt ein fertiges `budget` an und markiert ein geratenes Fenster (`budget_source: "default"`).

## Was belegt ist (Tests, 70 neue)

- **Schätzer:** pessimistisch, zählt Zeichen statt Bytes, Code dichter als Prosa. Die Schätzung liegt in allen Testfällen **nicht unter** der Provider-Zahl. Die Kalibrierung hebt den Faktor **sofort** an, lockert erst nach `calibrate_after` Messungen und **nie unter den schlechtesten gemessenen Wert** (mal 1,05). Sie wird je Modell gespeichert. Unbrauchbare Messwerte und eine beschädigte Kalibrierdatei ändern nichts.
- **Metriken:** Provider-Usage wird exakt gespeichert. Ohne Usage steht die **Schätzung mit Kennzeichnung** (`usage_source: estimate`, Ausgabe `null` statt 0). Peak-Fill ist das Maximum. **Genau ein** Audit-Event je Job (`CONTEXT_METRICS_SUMMARY`), Metriken selbst nicht im Audit. 6 Threads verlieren keine Zeile. Eine beschädigte Zeile bricht die Zusammenfassung nicht.
- **Budget:** Fenster = Minimum aus Modell, Hardware-Pass, Laufzeit. Gleiche Zahlen wie die bestehende Formel. Unbekanntes Fenster: sichtbarer Fallback 8192 (`default`) oder Fehler mit `strict`.
- **Offloading:** Kleine Ausgabe bleibt inline (geschwärzt). Große Ausgabe wird **im Original** gespeichert (Hash stimmt, Geheimnis im Original unverändert), im Kontext steht eine deterministische Kurzfassung ohne Geheimnisse. Relevante Bereiche sind **exakte Byte-Bereiche**, die sich zurücklesen lassen. `truncated` wird gesetzt, wenn mehr Fehler als Bereiche existieren. Saubere Ausgabe erzeugt keine erfundenen Befunde. Die Schwelle sinkt mit dem Watermark (1500/750/375/187). Zu große Ausgabe wird abgelehnt statt still gekürzt.
- **Artefaktzugriff:** begrenzte Länge, Hash-Prüfung (Manipulation erkannt), Pfad außerhalb des Speichers abgelehnt, Allow-Liste des Manifests wird erzwungen, Prompt-Lesen geschwärzt.
- **Checkpoints:** strukturiert, mit Digest. Veränderung wird erkannt und ein beschädigter gilt nicht als „letzter". **Pins brauchen eine prüfbare Quelle** (Evidence-ID und Artefakt-ID werden im Store geprüft). Zu große Checkpoints kürzen nur Freitext und markieren es. **Pins, Tests und Permission-State werden nie gekürzt**, im Zweifel Fehler `checkpoint_too_large`, ohne halb geschriebene Datei. `collect_pins` nimmt nur strukturierte Quellen (eine Modell-Einschätzung ist kein Testergebnis).
- **Watermarks:** Die Aktionen werden **tatsächlich ausgeführt**. Eine Checkpoint-Datei existiert, erledigte Schritte sind aus dem Kontext, ein großer Tool-Output ist durch seine Kurzfassung ersetzt, Zähler stehen in den Metriken. Kritische Stücke überleben jede Reaktion. Das am wenigsten relevante Stück geht zuerst (alt und unreferenziert vor frisch; erledigt vor unerledigt). Fehlt die Checkpoint-Quelle, steht `skipped` im Protokoll statt einer vorgetäuschten Aktion. Unbekannte Aktionen sind sichtbar. Eingabestücke werden nicht verändert.
- **Grenzen:** Der Quelltext enthält keinen Provider- oder Modellnamen und fasst keinen Jobzustand an (statischer Test).

## Gefundene und behobene Fehler im Bestand

| Befund | Behebung |
|---|---|
| `ArtifactStore.register` las den Index, hängte an und schrieb ihn **ohne Sperre**. Parallele Registrierungen konnten sich Einträge gegenseitig löschen | Sperre über `append_lock` (Test: 8 Threads × 5, alle 40 Einträge, 40 eindeutige IDs) |
| `atomic_write_json` scheiterte unter Last auf Windows sporadisch mit `PermissionError` beim Umbenennen (ein anderer Handle, vermutlich Virenscanner, hielt die Zieldatei kurz fest). Im Test fehlten dadurch 7 von 40 Einträgen | `_replace_with_retry`: bis zu 12 Versuche mit kurzer Wartezeit, **nur unter Windows und nur bei `PermissionError`** |

Der zweite Befund kann überall dort auftreten, wo JSON-Dateien geschrieben werden (Jobs, Missionen, Guard-Tokens). Bisher sind keine Fälle in Produktivläufen bekannt. Die Ursache (Virenscanner) ist vermutet, nicht bewiesen.

## Nicht umgesetzt / nicht verdrahtet (ehrlich)

1. **Der Kontext wird noch nirgends erzwungen.** Das Control Master **misst** nur. Es prüft die Eingabe **nicht** gegen das Budget und kürzt nichts. Die Watermark-Reaktion läuft nur, wenn ein Aufrufer sie anstößt. Nichts im Runtime tut das automatisch.
2. **Keine Verbindung zum Supervisor:** Stagnation (Supervisor) → Repair (Context) ist erst in Phase 4 geschlossen. `on_watermark` meldet `rebuild_required`, baut aber nichts neu.
3. **`feasibility.context_min_tokens` ist unverändert:** meldet weiter pauschal `UNSUPPORTED/CONTEXT_CAPACITY_UNQUALIFIED`. Die Umstellung auf das effektive Fenster ist nicht erfolgt.
4. **`ModelRuntimeManager.profile_for` wird nicht aufgerufen:** Die Kopplung an den Hardware-Model-Pass geschieht nur über das Argument `hardware_effective_max` (Test mit nachgebautem Pass-Ergebnis, nicht mit einem echten Pass-Lauf).
5. **Kein Tokenizer.** Die Schätzung ist eine Näherung (Zeichen pro Token). Ihre Genauigkeit für Qwen3.5 ist **nicht gemessen**. Ob `usage` der echten Adapter (LM Studio, llama.cpp) die erwarteten Felder liefert, ist **nicht gegen echte Server geprüft**, nur gegen nachgebaute Antworten.
6. **Kein Relevanzsystem jenseits der Gewichte.** Die Signale (`task`, `file`, …) setzt der Aufrufer. Der Manager findet sie nicht selbst. Die Gewichte sind **ungemessene Startwerte**.
7. **Keine Aufbewahrung:** `retention` ist in der Konfiguration, wird aber nicht durchgesetzt. Offload-Dateien, Metriken und Checkpoints wachsen unbegrenzt.
8. **Schwärzung ist heuristisch:** erkennt `schlüssel=wert`-Formen, nicht jedes Geheimnis (z. B. frei im Text stehende Tokens).
9. **Zusammenfassung ist Schlüsselwort-Heuristik** (`status_method: keyword_heuristic`). „error" in einer harmlosen Zeile zählt als Fehler, ein Fehler ohne diese Wörter wird nicht erkannt. Das Original bleibt immer abrufbar.
10. **Eine große Ausgabe wird komplett in den Speicher gelesen** (Obergrenze 64 MiB).
11. **Der A/B-Test mit echten Modellen fehlt:** ob reduzierter Kontext die Antwortqualität hält, ist **nicht gemessen** (Abnahmekriterium des Handoffs).
12. Die Metriken in `runtime_data/context_metrics/` nutzen dieselben Sperren wie das Audit. Last unter Windows-Antivirus ist nicht gemessen.

## Abweichungen vom Vertrag

| Vertrag | Umsetzung |
|---|---|
| `build_manifest`, `assemble`, `plan_repair` | Phase 4 |
| `context_manifest.layers/pins/excluded/token_estimate` | nicht in das Manifest geschrieben. Pins stehen im Checkpoint, ausgeschlossene Stücke im Rückgabeprotokoll von `on_watermark` |
| ContextPiece `ref`/`score`/`created_at` | als Dict im Speicher, mit `signals` statt gespeicherter Teilwerte. `score_piece` berechnet bei Bedarf |
| Checkpoint `manifest_id` | wird nur gesetzt, wenn ein Manifest übergeben wird (heute übergibt keiner eines) |
| Konfiguration | als Abschnitt `context_manager` in `config/job_supervisor.yaml`, wie im Vertrag; das Feld `max_offload_bytes` und `default_context_window` kamen hinzu |

## Nächster Schritt: Phase 4

`build_manifest` (Kind bekommt nie den Verlauf des Parents, nur erlaubte Artefakte), `assemble` (Schichten bis zum Budget, MWC-Prüfung), Fresh-Context an Task-Grenzen, `plan_repair` (gleiche Job-ID, neue Attempt-ID, kein Wiederholen mutierender Schritte) und die Verbindung Supervisor-Stagnation → Repair.
