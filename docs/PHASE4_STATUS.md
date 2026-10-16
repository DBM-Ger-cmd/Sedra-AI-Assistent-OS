# PHASE4_STATUS – Child-Kontext, Fresh Context, Repair

Stand: 2026-10-01 · Testumgebung: Windows 11, Python 3.14.7. **Keine Modelle, kein Zielgerät.**

**Ergebnis:** `python -m unittest discover -s tests` → **597 Tests, 0 Fehler, 5 übersprungen** (die 5 sind Symlink-Tests, siehe PHASE0_STATUS). `validate_package.py` und `compileall` OK.
Alles bleibt **hinter den Flags** `context_manager.enabled` und `job_supervisor.enabled` (beide AUS). Nichts davon läuft von allein.

## Umgesetzt

| Baustein | Datei | Inhalt |
|---|---|---|
| Manifest | `context_assembly.py` | `build_manifest`, `load_manifest` |
| Zusammenbau | dito | `assemble` (Schichten L0–L5 bis zum Budget, mit Nachladen über einen Retriever) |
| Fresh Context | dito | `fresh_context` |
| Repair | dito | `plan_repair` (Trockenlauf), `repair`, `detect_repetition` |
| Anbindung an den Supervisor | `job_repair.py` | `repair_job`, `trigger_for` |
| Supervisor | `job_supervisor.py` | `role_mutates`, `escalate`, `confirm_start` übernimmt vorbereitete Attempt-ID, Manifest und Checkpoint |
| Manifest-Vertrag | `development_contracts.py` | `context_manifest` nimmt optionale Felder (`layers`, `pins`, `snapshot`, `token_estimate`, `excluded`, `parent_manifest_id`) und schreibt sie **nur wenn gegeben**, alte Manifeste bleiben byte-gleich |
| Fassade | `context_manager.py` | `build_manifest`, `assemble`, `fresh_context`, `plan_repair`, `repair`, `detect_repetition` |

## Was belegt ist (44 neue Tests)

**Child-Isolation (Gruppe M)**
- `build_manifest` hat **keinen Parameter**, der einen Verlauf tragen könnte (Signatur wird geprüft).
- Ein Child mit einem Parent-Chat aus 50 Nachrichten und einer Marker-Zeichenkette erhält den Marker **weder im Manifest noch im zusammengebauten Kontext**, wohl aber Constraints, Akzeptanzkriterien, die nachgeladenen Dateien und Symbole, Entscheidungen, offene Fehler und Artefakt-IDs.
- Artefakt-Inhalte werden **nie** eingefügt, nur ihre IDs. Lesen ist auf die Artefakte des Manifests begrenzt, ein fremdes Artefakt → `policy_denied`.
- Ein Checkpoint eines **fremden** Jobs wird abgelehnt, einer des Parent-Jobs ist erlaubt. Ein Checkpoint mit **höherer** Berechtigung als der Job wird abgelehnt (ein frischer Kontext kann Rechte senken, nie erhöhen). Ein veränderter Checkpoint oder ein verändertes Manifest wird erkannt (`checkpoint_digest_mismatch`, `manifest_invalid`).
- Manifest wird gespeichert, auditiert und bei jedem Laden per Digest geprüft.
- Zu große Eingaben ergeben `manifest_invalid` statt eines Absturzes. Ein Snapshot über dem Projektbudget wird abgelehnt.
- **Minimum Working Context:** Passt der feste Teil (Policies, Vertrag, Snapshot, Pins) nicht unter die Orange-Marke, kommt `minimum_context_exceeds_window` mit Zahlen, und es bleibt **nichts halb Gebautes** liegen.

**Zusammenbau**
- Schichten sind geordnet. Policy, Vertrag, Snapshot und Pins werden **nie** gestrichen, auch unter Druck. Unter Druck fallen nur Dateiauszüge weg, jeder Ausschluss steht mit Grund im Ergebnis.
- Fehlt ein angefordertes Detail, ist das Ergebnis `INCOMPLETE` mit der Liste des Fehlenden (statt stillschweigend kleiner). Ohne Retriever ist alles fehlend.
- Zu große Auszüge werden gekürzt **und als gekürzt gekennzeichnet**.
- Jede Pin-ID steht im zusammengebauten Text. Die strukturierte Pin-Liste ist identisch zum Manifest (Gruppe N).
- Pins stammen nur aus strukturierten Quellen: eine Modell-Einschätzung ist kein Testergebnis.

**Fresh Context (Gruppe P)**
- Der neue Kontext enthält alle Pins des Checkpoints, übernimmt **ungelöste Fehler** und Entscheidungen und holt Limits aus dem **Vertrag des Jobs**, nicht aus dem Gedächtnis. Verschwindet die Quelle eines Pins, bricht der Aufbau mit `pin_missing_source` ab.
- Der Folgejob startet aus Checkpoint und Artefakten, **nicht** aus dem Verlauf (Marker-Test).

**Repair (Gruppe O)**
- Gleiche Job-ID, **neue** Attempt-ID, Checkpoint-Datei existiert, Berechtigungsstand bleibt erhalten, Audit `CONTEXT_REPAIR`.
- **Verweigert** wird: ein finaler Job, ein **mutierender Versuch mit unbekanntem Ausgang** (ein lesender Versuch darf wiederholt werden), fehlende Checkpoint-Quelle, das Limit (`max_per_job`, hier 2). Jede Verweigerung wird auditiert (`CONTEXT_REPAIR_REFUSED`) und schreibt nichts.
- 6 gleichzeitige Reparaturen mit Limit 2: genau 2 gelingen, 4 scheitern am Limit (die Reservierung geschieht unter Sperre).
- Wiederholungserkennung: gleiche Anfrage oder gleicher Fehler N-mal **hintereinander**, nicht bei Abwechslung und nicht über eine Lücke hinweg.

**Verbindung Supervisor ↔ Context**
- Eine **Stagnation** (Heartbeat ohne Fortschritt) endet in `REWORK` mit `awaiting_change: context_manifest`. `repair_job` baut den neuen Kontext, registriert ihn (`supply_change`) und hinterlegt Attempt-ID, Manifest und Checkpoint am Job. Der nächste `claim`/`confirm_start` startet dann **denselben Job als neuen Versuch** mit genau diesen IDs (`attempt_log` zeigt `UNKNOWN`, dann `SUCCEEDED`). Das Einreihen bleibt ein bewusster `enqueue`.
- `context_overflow` wird genauso repariert.
- Ein **stagnierender mutierender Job ist `DEAD`** und wird weder repariert noch wiederholt (`no_change_awaited`, kein Checkpoint geschrieben). Ein mutierender Job mit **bekanntem** Überlauf (nichts im Zweifel) darf repariert werden.
- Wird das Limit erreicht oder ein Pin unbrauchbar, **eskaliert** der Job an GUPPI, statt zu schleifen.
- Golden Path im Test: Arbeit, Stagnation, Reparatur, neuer Versuch, Verifikation, `READY_FOR_ACCEPTANCE`, Audit-Kette gültig.

**Grenzen**
- Weder `context_assembly.py` noch `job_repair.py` nennen einen Provider/ein Modell. `context_assembly.py` ändert keinen Jobzustand. `job_repair.py` reiht nie ein, bricht nie ab und ruft keinen Guard (statische Tests).

## Neu gefundener Befund im Bestand

**(Korrigiert in PHASE5_STATUS: die wirkliche Untergrenze ist 3145, nicht 3133; die Aufteilung ist knapp darüber nicht monoton. F-9 ist in Phase 5 behoben.)**
**F-9 (niedrig): `ContextBudgetManager.build_budget` liefert unter 3133 Token kein Budget, obwohl die Prüfung erst unter 1024 anspringt.** Gemessen: 1024 → `context_reservations_exceed_window`, 2048 und 2560 → `context_subbudgets_exceed_available_tokens`, 4096 → ok. Grund sind feste Untergrenzen der Teilbudgets (je 256, zuletzt 128) und feste Reserven (je 512). Praktisch ohne Folge: der Hardware-Model-Pass setzt nie weniger als 4096. Die Fehlermeldung ist aber irreführend, und ein Modell mit 2k–3k Kontext ließe sich nicht budgetieren. **Nicht geändert**, weil das die Budgetformel berührt, die als einzige Quelle gilt. Entscheidung offen (siehe unten).

## Nicht umgesetzt / offene Grenzen (ehrlich)

1. **Nichts ruft die Reparatur automatisch.** Es gibt keinen Treiber, der `reap()` ausführt, die Stagnation erkennt, `repair_job` aufruft und neu einreiht. Die Teile sind getestet und passen zusammen, der Treiber fehlt (Worker-Loop mit Control Master).
2. **Der Retriever ist nur ein Schnittstellenvertrag** (`fetch(kind, ref) -> Text | None`). Eine echte Implementierung über das `filesystem`-Tool und die Guard-Aktion `read_project_file` gibt es **nicht**. Bis dahin gilt: Dateiauszüge kommen aus dem, was der Aufrufer liefert.
3. **Relevanzsignale** (`task`, `file`, …) setzt der Aufrufer. Im Zusammenbau haben alle nachgeladenen Auszüge dieselben Signale, die Reihenfolge beim Streichen entscheidet dann die Aktualität. Echte Relevanz-Auswahl (Symbolbezug, Abhängigkeit) fehlt.
4. **`worker_change_requested` ist nur ein Wunsch** im Plan. Nichts reicht ihn an einen Control Master weiter (Phase 5).
5. **Wiederholungserkennung** ist eine reine Funktion. Wer die `request_digest`/`error_signature`-Ereignisse liefert, ist offen (der Supervisor erzeugt sie noch nicht).
6. **Das Manifest-Feld `excluded` bleibt beim Bauen leer**, ausgeschlossene Stücke stehen im Ergebnis von `assemble`.
7. **Reparaturversuche werden gezählt, sobald sie starten**, auch wenn sie danach scheitern. Das ist konservativ gewollt, kann aber ein Limit durch Fehlversuche aufbrauchen.
8. **Der A/B-Test mit echten Modellen fehlt weiterhin:** ob der kuratierte, kleinere Kontext die Antwortqualität hält, ist **nicht gemessen**. Ebenso fehlen reale Werte für Token-Schätzer und Relevanzgewichte (Phase 3).
9. Die Tests verwenden die Uhr und die IDs aus dem Test, keine echten Last- und Dauerläufe. Windows unter Antivirus-Last ist nicht gemessen.
10. `feasibility.context_min_tokens` meldet weiter pauschal `UNSUPPORTED` (siehe PHASE3_STATUS).

## Abweichungen vom Vertrag

| Vertrag | Umsetzung |
|---|---|
| `build_manifest(job, *, parent_checkpoint, task, files, symbols, extra_pins)` | zusätzlich `budget`, `snapshot`, `decisions`, `open_questions`, `known_failures`, `artifact_refs`, `approvals`. Weiterhin ohne Verlaufs-Parameter |
| `assemble(manifest, *, retriever)` → `AssembledContext` | liefert ein Dict (`pieces`, `text`, `tokens`, `excluded`, `missing`, `truncated`, `pins`, `allowed_artifacts`, `state`, `status`) |
| `plan_repair` liefert den Plan | `plan_repair` ist ein Trockenlauf. `repair` führt aus und liefert den Plan mit Ergebnis |
| 8.2 „Reparatur-Versuche je Job begrenzt, danach Eskalation an GUPPI" | Eskalation macht `repair_job` über `supervisor.escalate`. Der Context Manager selbst eskaliert nicht |
| Manifest `layers` | Deskriptoren (Art, Digest, Referenz), keine Stücke |

## Entscheidungen für den Captain

1. **F-9 / Budgetformel:** Untergrenzen der Teilbudgets nach unten skalieren (Modelle mit 2k–3k Kontext werden budgetierbar), oder die Prüfung auf „mindestens 3133" anheben und die Meldung vereinheitlichen? Empfehlung: Meldung vereinheitlichen und die Untergrenze **ausdrücklich** festlegen, Formel sonst unverändert lassen.
2. **Retriever:** Zuerst eine Implementierung über `filesystem` + Guard (`read_project_file`) bauen, oder zusammen mit dem Worker-Loop in Phase 5/8? Empfehlung: zusammen mit dem Worker-Loop.

## Nächster Schritt: Phase 5 (Routing)

Rollen → Capability → Anforderungen, Provider Health und Cooldown, Fallback mit Policy-Prüfung, `independence_key` für den unabhängigen Verifier. Das schließt F-4 und füllt `provider_ref`, `worker_change_requested` und `retry.exclude` mit Bedeutung. Der Control Master bleibt der einzige, der wählt.
