# CONTEXT_MANAGER_CONTRACTS

Stand: 2026-10-01 · Status: **Entwurf zur Freigabe (Phase 1). Kein Context-Manager-Code existiert.**
Grundlage: `CONTEXT_TOKEN_PLAN.md`, `JOB_SUPERVISOR_CONTRACTS.md`, Code v1.20 (`context_budget.py`, `development_contracts.py`, `artifacts.py`, `hardware_pass.py`, `feasibility.py`).
Leitregel: **Minimum Sufficient Context.** Qualität und Vollständigkeit gehen vor Token-Sparen.
Normative Wörter: **MUSS**, **SOLL**, **DARF NICHT**.

---

## 1. Zuständigkeit und Abgrenzung

| Der Context Manager | Der Context Manager DARF NICHT |
|---|---|
| Budget je Modell/Job berechnen lassen (über `ContextBudgetManager`) | eigene Budgetformeln führen (Duplikat) |
| Kontext für einen Job zusammenstellen (Manifest, Schichten) | Jobzustand ändern (Supervisor) |
| große Ausgaben auslagern, Kurzfassung liefern | Provider/Modell wählen (Control Master) |
| Checkpoints schreiben, Kontext reparieren | Fakten zusammenfassen **statt** sie strukturiert zu speichern |
| Metriken erfassen | Policies lockern oder Rechte vergeben |
| Füllstand bewerten, Watermark-Aktionen ausführen | eine zweite Memory-Schicht neben `KnowledgeStore` aufbauen |

Er liefert **Kontext und Zahlen**. Entscheidungen (Retry, Eskalation, Modellwechsel) treffen Supervisor und Control Master.

## 2. Grundprinzipien

1. **Eine Budgetquelle:** `ContextBudgetManager.build_budget` bleibt maßgeblich, `health()` liefert Zustand und Aktionsnamen. Der Context Manager führt die Aktionen aus.
2. **Fenster kommt vom Control Master:** effektives Fenster = Minimum aus Modellfenster, `HardwareModelPass.context_limits.effective_maximum` und tatsächlich geladenem Laufzeitkontext. Der Default 8192 in `SelfDevelopmentManager.start()` ist nur Notnagel und wird mit einer Warnung im Manifest markiert (`budget_source: "default"`).
3. **Kritische Fakten stehen strukturiert, nie nur in Prosa** (Abschnitt 7). Eine Zusammenfassung dient der Navigation, nicht dem Beweis.
4. **Index first, Details on demand.** Kinder bekommen Verweise, keine Volltexte.
5. **Die Schätzung ist pessimistisch.** Unsicherheit geht in den Sicherheitsabstand, nie in ein knapperes Budget.
6. **Offload verliert nichts:** Volltext bleibt als Artefakt mit Hash erhalten.
7. **Feature Flag:** `context_manager.enabled` (Default AUS). Ohne Flag verhält sich v1.20 unverändert.

## 3. Datenverträge

Alle Records sind JSON-kompatibel, haben `schema` (int) und, wo unten genannt, einen `…_digest` (SHA-256 über kanonisches JSON, wie `canonical_digest` in `development_contracts.py`). Enums sind **append-only** mit `UNKNOWN`-Fallback beim Lesen.

### 3.1 ContextBudget (bestehend, ergänzt)
Unverändert aus `build_budget`: `context_window, max_input_tokens, reserved_output_tokens, reserved_reasoning_tokens, safety_margin, system_budget, project_context_budget, task_context_budget, tool_result_budget, recent_history_budget, watermarks`.
Neu, optional: `budget_source` (`"model_pass" | "runtime" | "default"`), `estimator` (`{name, safety_factor}`), `model_ref` (opak).

### 3.2 ContextManifest (bestehend, ergänzt)
Felder wie `context_manifest()` in v1.20. Ergänzungen, alle optional:
```text
layers              {L0:[piece_id], L1:[…], L2:[…], L3:[…]}     # welche Stücke in welcher Schicht
pins                [Pin]                                       # siehe 3.6
budget_digest       sha256 des Budgets
token_estimate      {total, by_layer:{L0..L3}, method}
excluded            [{piece_id, reason}]                        # absichtlich weggelassen, nachvollziehbar
```
`manifest_digest` MUSS über **alle** Felder (außer sich selbst) gebildet werden. Ein Kind-Manifest verweist per `parent_manifest_id` und `checkpoint_id`. **Es enthält nie den Verlauf des Parents.**

### 3.3 ContextPiece
Ein adressierbares Kontextstück.
```text
piece_id        "CPC-<hex12>"
layer           "L0" | "L1" | "L2" | "L3" | "L4" | "L5"
kind            "policy" | "contract" | "snapshot" | "file_excerpt" | "symbol" | "decision" |
                "failure" | "tool_summary" | "history_summary" | "pin"
ref             {artifact_id? | path? | symbol? | range? }       # woher
content_digest  sha256 des Inhalts (der Inhalt selbst liegt nicht im Record)
tokens_est      int
score           {total, parts{task, file, decision, safety, pinned, recency, done_penalty}}
critical        bool                                            # nie verwerfbar
created_at
```

### 3.4 OffloadRecord (große Tool-Ausgabe)
```text
offload_id        "OFF-<hex12>"
artifact_id       "ART-…"                 # über ArtifactStore
job_id, attempt_id, source {tool, operation}
bytes, lines, sha256
created_at
summary           {status, counts{…}, first_error{file,line,message<=300}, relevant_ranges:[{start,end,why}], truncated:false}
summary_method    "deterministic"          # nie "llm" in v1
redacted          bool                     # siehe 6.3
```
Die **Kurzfassung ist deterministisch** (Zählen, erste Fehlerzeile, Statuscodes). Sie enthält nie Text, der nicht im Original vorkommt. `summary.truncated` MUSS `true` sein, wenn Teile der Ausgabe nicht berücksichtigt wurden.

### 3.5 ContextCheckpoint (strukturiert)
```text
checkpoint_id     "CKP-<hex12>"
job_id, attempt_id, created_at
goal              str (<=500)
manifest_id, manifest_digest
changed           [{path, sha256}]
artifacts         [artifact_id]
tests             [{id, result, evidence_id}]
open_errors       [{class, reason_code, summary<=300, artifact_id?}]
decisions         [{text<=300, decided_by, ref}]
next_steps        [str<=200]
permission_state  {level, tokens_used:[APR-…], gates_pending:[HG-…]}
pins              [Pin]
token_stats       {input_total, output_total, peak_fill, compactions, offloaded_bytes}
checkpoint_digest sha256
```
**Maximalgröße** konfigurierbar. Überschreitung ⇒ Fehler `checkpoint_too_large`, **keine stille Kürzung** von `pins`, `tests`, `permission_state`. Gekürzt werden dürfen nur `next_steps` und Freitextfelder, mit Markierung `truncated_fields`.
Abgrenzung: Das ist der **Kontext**-Checkpoint. Er ersetzt weder das Audit-Log noch den Ausführungs-Checkpoint des `step_journal`. Das alte Freitext-`checkpoint` im Job bleibt lesbar.

### 3.6 Pin
Ein Fakt, der in **jedem** Fresh Context vorkommen MUSS.
```text
pin_id, kind ("policy_hash"|"approval"|"test_result"|"code_change"|"hash"|"path"|"security_decision"|"constraint"),
ref {evidence_id? | gate_id? | token_id? | path? | artifact_id?}, digest, value (kurz, <=200), created_at
```
Pins stammen aus **strukturierten Quellen** (Evidence-Store, Guard, Job), nie aus Modelltext.

### 3.7 ContextMetric (eine Zeile je Attempt)
```text
job_id, attempt_id, role, model_ref(opak), recorded_at
input_tokens, output_tokens, cached_tokens (null)
usage_source      "provider" | "estimate"
context_window, peak_fill
compaction_count, checkpoint_count, fresh_context_count
tool_output_offloaded_bytes, estimated_tokens_saved   # Name trägt "estimated"
estimator_error_ratio (null)  # nur wenn usage vom Provider kam
provider_cost (null)
```
Ablage: `runtime_data/context_metrics/<job_id>.jsonl` (append, unter `append_lock`). **Nicht** ins hash-verkettete Audit. Zusammenfassung bei Job-Ende: **ein** Audit-Event `CONTEXT_METRICS_SUMMARY`.

### 3.8 ContextHealth
```text
state            "GREEN"|"YELLOW"|"ORANGE"|"RED"            # aus ContextBudgetManager.health
fill_ratio, used_tokens, max_input_tokens
tool_output_ratio, historical_ratio, unresolved_decision_count
duplicate_ratio, stale_candidates, last_checkpoint_age_s, relevance_density
method           "heuristic"                                 # nie als gemessene Qualität ausgeben
actions          [str]                                       # wie ContextBudgetManager
```

## 4. Schnittstelle (Zielbild)

```text
class ContextManager:
    resolve_budget(role, resolution) -> ContextBudget
    build_manifest(job, *, parent_checkpoint=None, task, files=(), symbols=(), extra_pins=()) -> ContextManifest
    assemble(manifest, *, retriever) -> AssembledContext          # L0..L3, bis Budget
    estimate(text_or_messages, *, model_ref) -> int               # pessimistisch
    offload(job_id, attempt_id, source, payload: bytes|str) -> OffloadRecord
    read_artifact_range(artifact_id, start, length) -> bytes      # begrenzt, siehe 6.2
    checkpoint(job, *, reason) -> ContextCheckpoint
    health(job_id, used_tokens) -> ContextHealth
    on_watermark(job, health) -> [Action]                         # führt aus, gibt Protokoll zurück
    plan_repair(job, *, trigger) -> RepairPlan
    record_usage(job_id, attempt_id, usage|None, estimate) -> ContextMetric
```
`retriever` ist ein Hook, den GUPPI/Control Master liefert (liest Dateiausschnitte, Wissen). Der Context Manager liest **nicht selbst** das Projekt am Guard vorbei: jedes Lesen läuft über das bestehende `filesystem`-Tool bzw. die Guard-Aktion `read_project_file`.

Fehlercodes: `context_window_unknown, budget_invalid, manifest_invalid, piece_not_found, offload_failed, artifact_range_too_large, checkpoint_too_large, pin_missing_source, minimum_context_exceeds_window, repair_not_possible`.

## 5. Kontextschichten und Auswahl

### 5.1 Schichten (Handoff §9.5)
| Schicht | Inhalt | Immer? | Quelle |
|---|---|---|---|
| L0 | System, Policies, Sicherheitsregeln | ja | Konfiguration/Contract |
| L1 | Task Contract (Ziel, Akzeptanz, Rechte, Verbote) | ja | `development_contract` |
| L2 | Projekt-Snapshot (kompakt, feste Obergrenze) | ja | Projektinspektion |
| L3 | Dateien/Symbole **ausgeschnitten** | bei Bedarf | `required_files`, `exact_symbols` |
| L4 | Historische Details | nein, nur Abruf | Wissen, frühere Ergebnisse |
| L5 | Rohlogs, große Ausgaben | nein, nur Artefakt-Verweis | `OffloadRecord` |

### 5.2 Minimum Working Context (MWC)
`MWC = L0 + L1 + L2 + Pins + aktueller Schritt`. Passt der MWC nicht unter die **Orange-Marke**, ist das Fenster für die Aufgabe zu klein ⇒ `minimum_context_exceeds_window` ⇒ Supervisor-Klasse `context_overflow` ⇒ **Eskalation**, kein Retry. (Control Master kann ein größeres Fenster/anderes Profil anbieten.)

### 5.3 Auswahl nach Relevanz (v1, Heuristik)
`score = w_task·task + w_file·file + w_dec·offene_entscheidung + w_safe·sicherheit + w_pin·gepinnt + w_rec·aktualität − w_done·erledigt`
- Gewichte stehen in der Konfiguration. Startwerte sind **Annahmen ohne Messgrundlage** und werden nach Phase 3 (Messung) angepasst.
- Stücke mit `critical == true` oder `kind == "pin"` werden **nie** verworfen.
- Gleichstand: gepinnt > sicherheitsrelevant > offene Entscheidung > neueste.
- Entfernte Stücke stehen in `manifest.excluded` mit Grund (nachvollziehbar, nicht stillschweigend).

## 6. Offloading und Artefakte

### 6.1 Auslösung
Ausgabe > `tool_output_inline_max_tokens` (Config; im Watermark-Zustand YELLOW halbiert) ⇒ Offload. Darunter: inline. Schwellenwert ist **Annahme**, siehe Offene Punkte.

### 6.2 Artefaktzugriff
- Ablage unter `runtime_data/context_artifacts/<job_id>/`, Registrierung über `ArtifactStore`. Dafür wird `register()` um **optionale** Job-Zuordnung ergänzt (bestehende Aufrufe unverändert).
- `read_artifact_range` begrenzt `length` pro Aufruf (Config), prüft, dass der Pfad **innerhalb** des Artefaktordners liegt (kein Traversal, kein Symlink), prüft den SHA-256 beim Lesen. Abweichung ⇒ `artifact_integrity_failed`, Job `BLOCKED`.
- Ein Kind-Job darf **nur Artefakte lesen, die im Manifest (`artifact_refs`) stehen**. Alles andere ⇒ `policy_denied`.

### 6.3 Geheimnisse
Vor der Weitergabe an ein Modell wird nach der `audit._redact`-Regel geschwärzt (Schlüssel `password, secret, token, api_key, apikey, credential, credentials`). Das Original-Artefakt bleibt **unverändert** (Beweiswert); `redacted: true` im Record. **Entscheidung offen (E-C3):** ob das Original selbst Geheimnisse enthalten darf.

## 7. Kritische Fakten (Critical Fact Preservation)

Kritisch sind: Policies/Policy-Hash, Genehmigungen (`APR-`, `HG-`), Testergebnisse (Evidence-IDs), Codeänderungen (Pfad + SHA-256), Hashes, Versionen, Fehlermeldungen, Dateipfade, Sicherheitsentscheidungen.

Regeln:
- C1 Kritische Fakten werden **nur** aus strukturierten Quellen als Pins übernommen (Evidence-Store, Guard, Job-/Contract-Datensatz).
- C2 Ein Pin ohne prüfbare Quelle (`pin_missing_source`) wird abgelehnt.
- C3 Jeder Fresh Context und jeder Checkpoint enthält **alle** aktiven Pins. Fehlt einer, ist der Aufbau ungültig (`manifest_invalid`).
- C4 Zusammenfassungen DÜRFEN Pins nicht ersetzen. Sie dürfen sie ergänzen.
- C5 Nach Compaction MUSS ein Test beweisen, dass die Pin-Menge vorher == nachher (Gruppe N).

## 8. Watermarks, Repair, Fresh Context

### 8.1 Aktionen (führt `on_watermark` aus)
| Zustand | Aktion | Wirkung |
|---|---|---|
| GREEN | – | – |
| YELLOW | `trim_tool_outputs`, `avoid_irrelevant_history` | Offload-Schwelle halbieren; Historie nach Relevanz beschneiden |
| ORANGE | `checkpoint`, `compact_completed_work`, `artifact_offload` | Checkpoint schreiben; erledigte Schritte aus aktivem Kontext; offene Großobjekte auslagern |
| RED | `checkpoint`, `context_rebuild`, `fresh_task_context`, `block_large_tool_dump` | Neuaufbau aus Checkpoint + Pins; keine neue Großausgabe inline; Eskalation, wenn nach Neuaufbau nicht unter ORANGE |

Jede Aktion erzeugt einen Eintrag im Rückgabeprotokoll **und** Metrik (`compaction_count`, `checkpoint_count`).

### 8.2 Repair (statt blindem Retry)
Auslöser (vom Supervisor gemeldet oder selbst erkannt):
- Klasse `context_overflow` oder `context_quality_degraded` (siehe `failure_classes`)
- Stagnation (Supervisor 6.2: Heartbeat ohne Progress)
- Wiederholungsmuster: gleicher Request-Digest K-mal, gleiche Fehlermeldung K-mal
```text
plan_repair(job, trigger) -> RepairPlan{
   steps: ["checkpoint","drop_irrelevant","reassemble_from_pins","optional_other_worker"],
   new_manifest_id, attempt_id_new, preserves: {job_id, pins, permission_state},
   worker_change_requested: bool        # nur WUNSCH an den Control Master
}
```
Regeln:
- Gleiche `job_id`, **neue** `attempt_id`.
- Ein **mutierender Schritt mit unbekanntem Ausgang wird nie durch Repair wiederholt** (`UNKNOWN_EXECUTION_OUTCOME`, wie `step_journal`).
- Repair-Versuche je Job begrenzt (Config). Danach Eskalation an GUPPI.
- Ein Modellwechsel ist ein **Wunsch** (`worker_change_requested`), keine Anweisung.

### 8.3 Fresh Context an Task-Grenzen
Nach abgeschlossenem Subtask startet der nächste Job mit **System + Policies + Task Contract + Checkpoint + relevanten Artefakten** (`Fresh = L0 + L1 + Checkpoint + Pins + artifact_refs`). Er erhält **nicht** den Chatverlauf. Fresh Context bedeutet **nie**: Entscheidungen, Constraints, Sicherheitsregeln oder ungelöste Fehler vergessen (C3 gilt).

## 9. Tokenschätzung

- `usage` des Providers hat Vorrang (nachträglich, exakt).
- Vorab-Schätzung: `ceil(zeichen / 3.0)` für Code/strukturierten Text, `ceil(zeichen / 3.5)` für Prosa, mal `safety_factor` (Start 1,15). Bewusst pessimistisch.
- Kalibrierung je Modell: gemessen wird `estimator_error_ratio = usage_input / estimate`. Gelockert werden darf der Faktor erst ab N Messungen und **nie unter den höchsten gemessenen Wert**.
- Kein Tokenizer-Paket in v1 (Entscheidung E-C1). Die Schnittstelle erlaubt später einen Tokenizer je Modellfamilie.
- Zeichenanzahl zählt **Unicode-Zeichen**, nicht Bytes (Umlaute, Emojis, CJK sind pessimistisch abgedeckt durch den Faktor; **nicht gemessen**).

## 10. Integration in den Bestand (minimal-invasiv)

| Stelle | Änderung | Flag |
|---|---|---|
| `SelfDevelopmentManager.start()` | Manifest über `ContextManager.build_manifest`; `context_window` vom Control Master statt Default | `context_manager.enabled` |
| `SelfDevelopmentManager.checkpoint()` | schreibt zusätzlich strukturierten `ContextCheckpoint`; altes Feld bleibt | dito |
| `ControlMasterModule._model_inference` | prüft Eingabe gegen Budget, liefert `usage` zurück | dito |
| `feasibility.assess` | `context_min_tokens` gegen effektives Fenster statt pauschal `UNSUPPORTED`; **altes Verhalten bleibt bei unbekanntem Fenster** | dito |
| `ArtifactStore.register` | optionale Job-Zuordnung | immer rückwärtskompatibel |
| `code_generation.generate` | Byte-Limit (64 KiB) bleibt als harte Sperre, zusätzlich Token-Budget | dito |
| `models/openai_local.py` | `usage` durchreichen, falls nicht vorhanden | dito |
| `uix_server.py` | `/api/context` **nur lesend** | dito |

## 11. Konfiguration `config/job_supervisor.yaml` → Abschnitt `context_manager` (Entwurf)

```yaml
context_manager:
  enabled: false
  watermarks: {green: 0.55, yellow: 0.70, orange: 0.85}      # wie ContextBudgetManager
  estimator: {code_chars_per_token: 3.0, prose_chars_per_token: 3.5, safety_factor: 1.15, calibrate_after: 20}
  tool_output_inline_max_tokens: 1500
  artifact_read_max_bytes: 65536
  checkpoint_max_tokens: 3000
  repair: {max_per_job: 2, repeat_threshold: 3}
  retention: {artifacts_days: 14, metrics_days: 60}
  relevance_weights: {task: 3, file: 3, decision: 2, safety: 4, pinned: 4, recency: 1, done_penalty: 2}
```
Ungültige Werte (Watermarks nicht aufsteigend, Faktor < 1,0) ⇒ Start verweigert (Wiederverwendung der Prüfung in `ContextBudgetManager.__init__`).

## 12. Testmatrix (Handoff §17 K–Q)

Alle Tests mit `FakeAdapter` (definierte `usage`, definierte Antwortgrößen) und `FakeClock`. Sie prüfen die **Mechanik**, nicht die Antwortqualität echter Modelle.

| Gruppe | Fälle |
|---|---|
| **K Budget** | Fenster 8192 → Summen stimmen. 56 %/71 %/86 % → YELLOW/ORANGE/RED, Aktion **wurde ausgeführt** (Checkpoint-Datei existiert). Fenster aus Hardware-Pass kleiner als Modellfenster → kleineres gilt. `budget_source=="default"` wird markiert. |
| **L Offloading** | 5 MB Ausgabe → Artefakt mit korrektem SHA-256, Kurzfassung unter Schwelle, `summary.truncated` korrekt. `read_artifact_range` liefert exakt die Bytes, lehnt Überlänge ab, erkennt manipuliertes Artefakt. Ausgabe unter Schwelle bleibt inline. |
| **M Child-Isolation** | Parent mit 50 Nachrichten + Marker-Zeichenkette → Kind-Manifest und assemblierter Kontext enthalten den Marker **nicht**, aber `constraints`, `acceptance_criteria`, `required_files`. Zugriff auf Artefakt außerhalb `artifact_refs` → `policy_denied`. |
| **N Critical Facts** | Nach Compaction ist die Pin-Menge identisch. Fehlender Pin → `manifest_invalid`. Pin ohne Quelle → `pin_missing_source`. Checkpoint über Maximalgröße → Fehler, `pins` unverändert. |
| **O Repair** | Überladene Session → Checkpoint → neuer Kontext unter ORANGE → gleiche `job_id`, neue `attempt_id`, Abschluss. Wiederholungsmuster löst Repair statt Retry aus. **Mutierender Schritt mit unbekanntem Ausgang wird nicht wiederholt.** Repair-Limit → Eskalation. |
| **P Fresh Boundary** | Folgejob startet mit Checkpoint + Artefakten, **nicht** mit Verlauf (Marker-Test). |
| **Q Metriken** | `usage=(1200,300)` → Metrikzeile korrekt. Peak-Fill = Maximum. Ein Audit-Event bei Job-Ende. `usage_source` ehrlich (`estimate` ohne Provider). |
| **MWC** | MWC > 85 % → `minimum_context_exceeds_window`, Eskalation, kein Retry-Loop. |
| **Schätzer** | Schätzung ≥ `usage` in allen Fake-Fällen. Kalibrierung senkt nie unter den Höchstwert. |
| **Sicherheit** | Traversal/Symlink im Artefaktpfad. Redaktion von `token`/`password`. Lesen läuft über Guard (`read_project_file`). |
| **Kompatibilität** | Flag aus ⇒ alle bestehenden Tests unverändert. Altes `checkpoint` bleibt lesbar. v1.20-Jobdatei ohne neue Felder funktioniert. |
| **Windows** | CRLF/UTF-8-Dateien: Hash über Bytes, Offsets in Bytes (siehe Befund 0.7). Symlink-Tests nur mit Entwicklermodus. |

## 13. Offene Entscheidungen

| # | Frage | Empfehlung |
|---|---|---|
| E-C1 | Tokenizer: konservative Schätzung oder mitgelieferter Tokenizer (neue Abhängigkeit)? | Schätzung für v1, Schnittstelle austauschbar |
| E-C2 | Inline-Schwelle 1 500 Token als Startwert? | ja, nach Messung in Phase 3 anpassen |
| E-C3 | Dürfen Offload-Artefakte Originalgeheimnisse enthalten? | ja im Artefakt (Beweiswert), nie im Prompt |
| E-C4 | Aufbewahrung Artefakte/Metriken (Speicherplatz auf dem PC) | 14/60 Tage, konfigurierbar |
| E-C5 | `/api/context` nur lesend oder auch Checkpoint auslösen? | nur lesend, bis eine Guard-Aktion existiert |
| E-C6 | Relevanzgewichte | Startwerte, **ungemessen**; Messung vor Verwendung produktiv |
| E-C7 | Wo liegt das Wissen für L4 (Retrieval)? | `KnowledgeStore` (Substring-Suche). Reicht nur für v1, kein semantisches Retrieval |

## 14. Abnahme dieses Vertrags (Phase 1)

- [ ] Captain hat Abschnitte 3, 5.2, 7, 8 und E-C1 bis E-C7 geprüft.
- [ ] Verzahnung mit `JOB_SUPERVISOR_CONTRACTS.md` bestätigt: Stagnation (Supervisor 6.2) ↔ Repair (8.2), Manifest-ID im Attempt (Supervisor 3), `independence_key` (Supervisor 8.4).
- [ ] Kein zweites Gedächtnis, keine zweite Budgetformel, kein zweites Audit-Format.
- [ ] **Nicht geprüft und für die Abnahme nötig:** A/B-Lauf mit echten Modellen (Qualität bei reduziertem Kontext, Handoff-Kriterium „Token-Sparen verschlechtert nicht die Vollständigkeit"). Das ist ein Ticket für die PC-Abnahme.
