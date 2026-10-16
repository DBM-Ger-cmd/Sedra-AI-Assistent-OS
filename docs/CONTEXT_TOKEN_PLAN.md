# CONTEXT_TOKEN_PLAN – Context Manager für GUPPI

Stand: 2026-10-01 · Grundlage: `ARCHITECTURE_GAP_REPORT.md` §2.4
Status: **Entwurf zur Freigabe. Es wurde noch kein Code geändert.**
Leitregel (Handoff §9): *Minimum Sufficient Context* – so wenig wie möglich, so viel wie nötig. Qualität vor Token-Sparen.

## 1. Ist-Zustand

### 1.1 Was existiert
- **`ContextBudgetManager`** (`context_budget.py`): rechnet aus einem Kontextfenster ein Budget (Output-Reserve, Sicherheitsmarge, fünf Subbudgets) und bewertet einen Füllstand gegen Watermarks (55/70/85 %, konfigurierbar, validiert). `health()` liefert Zustand und **Aktionsnamen als Strings**.
- **`context_manifest()`** (`development_contracts.py`): hash-gebundenes Manifest mit allen im Handoff §9.4 geforderten Feldern.
- **`ArtifactStore`**: ART-ID, Pfad, sha256, Provenienz. Mission-gebunden.
- **`KnowledgeStore`**: JSONL, Substring-Suche. Einzige Memory-Schicht.
- **Hash-Ketten** (Audit, Evidence) für kritische Fakten.
- **`HardwareModelPass`**: sichere Kontextobergrenze je Hardwareklasse (z. B. 8192 bei `nvidia_small`, 16384 bei `cpu_32plus`) und effektives Profil mit `context.recommended/maximum`.

### 1.2 Was fehlt
Tokenzählung · Ausführung der Watermark-Aktionen · Offloading großer Ausgaben · strukturierte Checkpoints · Weitergabe des Manifests an einen Child · Fresh-Context-Aufbau · Relevanz-Auswahl · Kontext-Repair · Token-/Kontextmetriken · Verbindung Budget ↔ Hardware-Pass.

### 1.3 Aktueller Tokenfluss (soweit aus dem Code ersichtlich)

```text
Mission/Plan ──▶ ControlMaster._model_inference
                    messages (vom Planer/Caller gebaut, ungekürzt)
                    ──▶ ModelRouter.chat ──▶ Adapter (lm-studio | llama.cpp)
                    ◀── result (Audit: nur Provider+Modell, keine Usage)

Code-Generierung: code_generation.generate
   ausgewählte Quelldateien im Volltext (Limit 64 KiB gesamt, sonst Abbruch)
   max_tokens fest 4096, Temperatur 0.1
```

Befunde:
1. **Kein Eingabe-Budget wird angewendet.** `ContextBudgetManager` ist an `SelfDevelopmentManager.start()` angebunden und dort nur zur Manifest-Erzeugung. Kein Aufruf im Chat-/Inference-Pfad.
2. **Kein Tokenzähler.** Die einzige Größenprüfung ist ein Byte-Limit (64 KiB) in `code_generation`. 64 KiB Quelltext sind grob 16–25 k Token und überschreiten damit ein 8192er-Fenster deutlich. Das Byte-Limit ersetzt also kein Token-Budget.
3. **Tool-Ausgaben:** `tool_call`/`tool_sequence` geben das Ergebnis im Ganzen zurück. `_register_result_artifact` legt nur Dateiergebnisse mit `register_artifact` ab. Ob Ergebnisse später in Prompts landen, hängt vom Planer ab und ist nicht begrenzt. (Planer-Modul `modules/planning.py` nicht im Detail gelesen.)
4. **Child-Kontext:** Es gibt keine Child-Agenten. Das Manifest wird erzeugt, aber nirgends konsumiert.
5. **Metriken:** nicht erfasst. Ob Adapter `usage` zurückgeben, ist offen (`models/openai_local.py` prüfen).

## 2. Zielbild

```text
GUPPI
  └─▶ ContextManager  (context_manager.py)
        ├─ TokenEstimator        konservativ, Provider-usage bevorzugt
        ├─ BudgetResolver        Fenster aus ControlMaster/HardwareModelPass → ContextBudgetManager
        ├─ ManifestBuilder       Manifest je Child (index first → detail on demand)
        ├─ OutputOffloader       Volltext → Artefakt, Kurzfassung + Referenz
        ├─ CheckpointWriter      strukturiert, mit Pin-Liste
        ├─ WatermarkActions      führt ORANGE/RED-Aktionen aus
        ├─ RepairPlanner         CONTEXT_REPAIR statt Retry
        └─ MetricsRecorder       pro Attempt
```

`ContextBudgetManager` bleibt unverändert die **einzige** Budgetberechnung. Der Context Manager ruft ihn auf.

## 3. Komponenten im Detail

### 3.1 TokenEstimator
- Quelle 1: `usage` aus der Provider-Antwort (wenn vorhanden → exakt, nur nachträglich).
- Quelle 2: Schätzung **vor** dem Aufruf: `ceil(zeichen / 3)` für Code, `ceil(zeichen / 3.5)` für Prosa. Absichtlich pessimistisch.
- Kalibrierung: der Recorder vergleicht Schätzung und `usage` je Modell und speichert das Verhältnis. Ab N Messungen darf die Schätzung gelockert werden. Nie unter den gemessenen Wert.
- Kein Tokenizer-Paket in v1 (Entscheidung 6 im Integrationsplan). Schnittstelle so, dass ein Tokenizer später einhängbar ist.

### 3.2 BudgetResolver
- Eingabe: Rolle/Capability → Control Master liefert Modell und **effektives Profil** → `HardwareModelPass.evaluate(...)["context_limits"]["effective_maximum"]`.
- Fenster = `min(Modellfenster, effective_maximum, laufzeitseitig geladener Kontext)`. Der niedrigste Wert gewinnt.
- Ergebnis wird als Budget an den Job gehängt (`context_budget` im Job, Feld existiert bereits im Manifest).
- Löst `feasibility`-Code `CONTEXT_CAPACITY_UNQUALIFIED` auf: `context_min_tokens` wird gegen das **tatsächliche** effektive Fenster geprüft statt pauschal abgelehnt. Das ist eine Änderung in `feasibility.py` und braucht einen Test, der das alte Verhalten (Ablehnung bei unbekanntem Fenster) beibehält.

### 3.3 ManifestBuilder (Child Context Isolation)
Ein Child erhält **nur**:
- Schicht 0/1: System/Policies + Task Contract (immer)
- Schicht 2: kompakter Projekt-Snapshot (feste Größe)
- Schicht 3: genannte Dateien und Symbole, **ausgeschnitten** (nicht ganze Dateien, wenn Symbole bekannt)
- Schicht 4: nichts. Nur Retrieval auf Anforderung.
- Schicht 5: nichts. Nur Artefakt-Referenz.

Nie vererbt: Parent-Chatverlauf, Roh-Logs, frühere Fehlversuche außer `known_failures` (Kurzform).
Das Manifest wird hash-gebunden im Job gespeichert und im Audit referenziert (`context_manifest_id`).

### 3.4 OutputOffloader
Schwelle konfigurierbar (`tool_output_inline_max_tokens`, Vorschlag 1 500 Token ≈ 4,5 KB).
Ablauf:
1. Ergebnis > Schwelle → vollständig als Datei unter `runtime_data/context_artifacts/<job>/` speichern.
2. Über `ArtifactStore` registrieren (ART-ID, sha256). Dafür wird `register()` um **optionale** Job-Zuordnung ergänzt statt Mission-Zwang. Bestehende Aufrufe bleiben gleich.
3. Aktiver Kontext erhält strukturierte Kurzfassung:
   `{status, counts, first_error, artifact_id, relevant_ranges, bytes, sha256}`.
4. Teilbereiche werden über `read_artifact_range(artifact_id, start, length)` nachgeladen, mit Obergrenze pro Aufruf.
Die Kurzfassung wird **deterministisch** erzeugt (Zählen, erste Fehlerzeile, Statuscodes), nicht per LLM. Zusammenfassung dient Navigation, nicht Beweisführung (Handoff §9.9). Der Volltext bleibt der Beleg.
Geheimnisse: Redaktion wie `audit._redact`, **bevor** ein Artefakt in Prompts geht. Die Datei selbst enthält das Original nur, wenn die Quelle es erlaubt. Das ist in Phase 1 (Contracts) festzulegen.

### 3.5 Checkpoint (strukturiert)

```text
context_checkpoint:
  checkpoint_id, job_id, attempt_id, created_at, manifest_id, manifest_digest
  goal
  changed:   [{path, sha256}]
  artifacts: [artifact_id]
  tests:     [{id, result, evidence_id}]
  open_errors: [{class, summary, artifact_id?}]
  decisions: [{text, decided_by, ref}]
  next_steps: [text]
  permission_state: {level, tokens_used: [APR-…], gates_pending: [HG-…]}
  pins: [{kind, ref, digest}]          # Policy-Hash, Freigaben, Testresultate, Hashes, Pfade
  token_stats: {…}
```
- Maximalgröße konfigurierbar (Vorschlag 3 000 Token). Überschreitung → Fehler, keine stille Kürzung der `pins`.
- Ersetzt das Audit **nicht**. Wird unter einem anderen Namen als `step_journal`-Checkpoint geführt (`context_checkpoint`).
- Das alte `checkpoint()`-Objekt bleibt lesbar. Das neue wird zusätzlich geschrieben.

### 3.6 WatermarkActions
`ContextBudgetManager.health()` bleibt. Der Manager übersetzt die Aktionsnamen in Handlungen:

| Zustand | Aktion | Umsetzung |
|---|---|---|
| GREEN | – | – |
| YELLOW | `trim_tool_outputs`, `avoid_irrelevant_history` | Offload-Schwelle halbieren, Historie auf Relevanz statt Recency beschneiden |
| ORANGE | `checkpoint`, `compact_completed_work`, `artifact_offload` | Checkpoint schreiben, erledigte Schritte entfernen, offene Großobjekte auslagern |
| RED | `checkpoint`, `context_rebuild`, `fresh_task_context`, `block_large_tool_dump` | Neuaufbau aus Checkpoint + Pins, kein neuer Großdump, Eskalation wenn Neuaufbau nicht unter ORANGE kommt |

Grenzfall: Wenn selbst das **Minimum Working Context** (Schicht 0–2 + Pins) über 85 % liegt, ist das Fenster für die Aufgabe zu klein. Ergebnis: Fehlerklasse `context_overflow`, **Eskalation**, kein Retry. Passendes Modell oder anderes Profil wählt der Control Master.

### 3.7 Relevance Selection (v1, Heuristik)
Score je Kontextstück, keine KI:
`score = 3·task_bezug + 3·datei_symbol_bezug + 2·offene_entscheidung + 4·sicherheitsrelevant + 4·gepinnt + 1·aktualität − 2·bereits_erledigt`
- Gepinntes und Sicherheitsrelevantes wird **nie** verworfen.
- Task-/Symbolbezug über exakte Treffer auf `required_files`/`exact_symbols` und Schlüsselwörter aus dem Contract (keine Embeddings).
- Gewichte in der Konfiguration, damit sie durch Messung angepasst werden können.

### 3.8 Context Health (v1)
Berechnet aus Zählern, die der Manager ohnehin führt: `token_fill_ratio`, `tool_output_ratio`, `historical_context_ratio`, `unresolved_decision_count`, `last_checkpoint`-Alter, `stale_context_candidates` (Stücke mit Alter > X und Score < Y), `duplicate_ratio` (identische sha256 von Stücken). `estimated_relevance_density` = Anteil Tokens mit Score ≥ Schwelle. Alles Heuristik und als solche gekennzeichnet.

### 3.9 Context Repair
Auslöser: `context_overflow`, `context_quality_degraded`, oder Indikatoren: keine Änderung am `progress_marker` über N Turns, identische Tool-Aufrufe wiederholt (gleicher Request-Digest), dieselbe Fehlermeldung K-mal.
Ablauf (gleiche Job-ID, neue Attempt-ID):
1. Checkpoint schreiben
2. Kontext aus Schicht 0–2 + Pins + relevante Artefakte neu zusammenbauen
3. Optional anderes Modell: **Wunsch** an Control Master, kein Direktzugriff
4. Attempt fortsetzen, Audit-Event `CONTEXT_REPAIR`
Erlaubte Wiederholungen begrenzt. Danach Eskalation an GUPPI.
Das Journal-Verhalten bleibt maßgeblich: Ein mutierender Schritt mit unbekanntem Ausgang wird **nicht** durch Repair wiederholt.

### 3.10 MetricsRecorder
Pro Attempt eine Zeile in `runtime_data/context_metrics/<job>.jsonl` (nicht im hash-verketteten Audit, weil hochfrequent):
`input_tokens, output_tokens, cached_tokens?, context_window, peak_context_fill, compaction_count, checkpoint_count, fresh_context_count, tool_output_offloaded_bytes, estimated_tokens_saved, provider_cost?, estimator_error_ratio`
- `estimated_tokens_saved` = Tokens des Volltexts − Tokens der Kurzfassung. Das ist eine **Schätzung**, im Feldnamen gekennzeichnet.
- Zusammenfassung wird bei Job-Ende als **ein** Audit-Event geschrieben.
- Auswertung für Hardware-Model-Pass und Routing: spätere Phase, hier nur Erfassung.

## 4. Datei- und Konfigurationsänderungen

| Datei | Änderung |
|---|---|
| `context_manager.py` (neu) | Komponenten 3.1–3.10 |
| `config/job_supervisor.yaml` (neu) | Schwellen, Gewichte, Flags (`context_manager.enabled: false`) |
| `artifacts.py` | optionale Job-Zuordnung in `register()`, neue Methode `read_range()` |
| `feasibility.py` | `context_min_tokens` gegen effektives Fenster prüfen (nur wenn Flag an) |
| `modules/control.py` | `model_inference`: bei aktivem Flag Eingabe über Context Manager prüfen/kürzen, `usage` zurückgeben |
| `models/openai_local.py` | `usage` durchreichen (nur falls fehlt; erst prüfen) |
| `self_development.py` | `checkpoint()` ruft zusätzlich `CheckpointWriter`. Manifest wird über Manager erzeugt |
| `code_generation.py` | Byte-Limit bleibt als harte Sperre. Zusätzlich Token-Budget-Prüfung |
| `uix_server.py` | `/api/context` (lesend: Füllstand, Checkpoints, Metriken je Job) |

Alles hinter Feature Flag. Ohne Flag: kein Verhaltensunterschied zu v1.20.

## 5. Teststrategie

Alle Tests deterministisch, ohne echtes Modell. Ein **FakeAdapter** liefert definierte `usage`-Werte und verschiedene Antwortgrößen. Das prüft die Mechanik. Es prüft **nicht**, ob echte Modelle mit dem reduzierten Kontext gleich gut arbeiten. Dafür ist ein realer Lauf nötig (siehe 6).

| Gruppe (Handoff §17) | Testfall |
|---|---|
| K Context Budget | Fenster 8192 → Budget summiert korrekt. Füllstand 56 %/71 %/86 % → YELLOW/ORANGE/RED, die jeweiligen Aktionen werden **ausgeführt** (Checkpoint-Datei existiert, Offload gelaufen). Ungültige Watermarks → Fehler. |
| K+ Budget/Hardware | `effective_maximum` kleiner als Modellfenster → Budget nutzt das kleinere. `cpu_small` → 4096. |
| L Tool Offloading | 5 MB Ausgabe → Volltext im Artefakt (sha256 stimmt), Kontext enthält nur Kurzfassung unter Schwelle, `read_range` liefert exakt die Bytes. Ausgabe unter Schwelle wird **nicht** ausgelagert. |
| M Child Isolation | Parent mit 50 Nachrichten + Marker-String. Child-Manifest enthält den Marker **nicht**, enthält aber `required_files`, `constraints`, `acceptance_criteria`. Child kann Detail per Referenz nachladen. |
| N Critical Fact Preservation | Checkpoint nach ORANGE enthält Policy-Hash, Testresultat-ID, Pfad und Genehmigungs-Token-ID. Ein Versuch, `pins` zu überschreiten/zu kürzen → Fehler. Rekonstruktion: aus dem Checkpoint allein sind diese Fakten maschinell auslesbar, ohne Zusammenfassungstext. |
| O Context Repair | Künstlich überladener Verlauf (RED) → Checkpoint → neuer Kontext unter ORANGE → Job mit **gleicher Job-ID, neuer Attempt-ID** läuft zu Ende. Zusätzlich: Wiederholungs-Erkennung löst Repair aus, nicht Retry. Mutierender Schritt mit unbekanntem Ausgang wird **nicht** wiederholt. |
| P Fresh Boundary | Abgeschlossener Subtask → nächster Job startet mit Checkpoint + Artefakten, **nicht** mit dem Verlauf (Marker-Test wie M). |
| Q Token Metrics | FakeAdapter `usage=(1200, 300)` → Metrikzeile stimmt. Peak-Fill = Maximum über Turns. Job-Ende schreibt genau **ein** Audit-Event. |
| Grenzfall | Minimum Working Context > 85 % → `context_overflow` + Eskalation, **kein** Retry-Loop. |
| Schätzer | Schätzung ≥ `usage` in 100 % der Fake-Fälle (pessimistisch). Kalibrierung senkt nie unter den Messwert. |
| Rückwärtskompatibilität | Flag aus → alle 303 bestehenden Tests unverändert. Altes `checkpoint` bleibt lesbar. |
| Sicherheit | Offload-Artefakt außerhalb des erlaubten Wurzelpfads nicht lesbar (Pfad-Traversal). Redaktion von `token`/`password`-Keys vor Prompt. |

## 6. Was Tests nicht belegen (ehrlich)

- Ob reduzierter Kontext die **Antwortqualität** hält, lässt sich nur mit realen Modellen messen. Abnahmekriterium aus dem Handoff („Token-Sparen verschlechtert nicht die fachliche Vollständigkeit") braucht einen A/B-Lauf: gleiche Aufgaben mit/ohne Context Manager, Auswertung durch deterministische Tests der Ergebnisse. Das ist ein Ticket für die PC-Abnahme.
- Die Tokenschätzung ist eine Näherung, solange kein Tokenizer vorliegt.
- Die Relevanz-Gewichte sind Startwerte ohne Messgrundlage.
- Die Latenz des Offloadings (Dateisystem unter Windows mit AV-Scanner) ist nicht gemessen.

## 7. Reihenfolge innerhalb Phase 3 (Context v1)

1. `TokenEstimator` + `MetricsRecorder` (reine Erfassung, kein Eingriff) → misst zuerst den Ist-Zustand
2. `BudgetResolver` + Anbindung `HardwareModelPass`
3. `OutputOffloader` + `ArtifactStore`-Erweiterung
4. `CheckpointWriter` (strukturiert)
5. `WatermarkActions` (ab hier greift der Manager ein)
6. Phase 4: `ManifestBuilder`-Child-Isolation, Fresh Boundary, Repair

Schritt 1 liefert die Datenbasis, um die Schwellen aus Schritt 3 und 5 zu begründen, statt sie zu raten.

## 8. Offene Entscheidungen

1. Tokenizer: konservative Schätzung (empfohlen) oder lokaler Tokenizer (neue Abhängigkeit)?
2. Offload-Schwelle: 1 500 Token als Startwert akzeptabel?
3. Dürfen Offload-Artefakte Originaldaten mit Geheimnissen enthalten (Quelle erlaubt) oder immer redigiert (sicherer, aber nicht beweiskräftig)?
4. Soll `/api/context` in der UIX nur lesen oder auch Checkpoints auslösen können? Empfehlung: nur lesen, bis Guard-Aktion dafür definiert ist.
5. Aufbewahrungsdauer der Offload-Artefakte und Metriken (Speicherplatz auf dem Test-PC).
