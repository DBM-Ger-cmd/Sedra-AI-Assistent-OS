# Baubericht Inhaltsschutz (28.10.2026)

Auftrag des Captains 28.10.2026: „Inhaltsschutz reparieren und prüfen, ob es dort weitere Fehler gibt … eine Lösung, dass man auf dem eigenen
PC schreiben kann und der Inhalt geprüft wird, wenn man in der Cloud arbeitet.“ Gebaut von Claude auf `claude/stufe-1-64f713` (nach der
Übernahme von Harness Stufe 1). `core/**` ist Captain-Vorbehalt (HS-28); Auftrag und Weg „Eigenes frei“ vom Captain bestätigt.

## Befund aus dem Audit (`workspace/GUPPI_OS/runtime_data/audit/events.jsonl`)

| Ereignis | Zahl | Wirklich ein Eingriff des Schutzes? |
|---|---|---|
| `SG_STOPPED` Cloud, Status ERROR (`SG_MODEL_ERROR`) | 204 | nein – Fehler des Cloud-Anbieters, als Schutz-Stopp protokolliert |
| `SG_STOPPED` lokal, WITHHELD (`SG_OUTPUT_EMPTY`) | 6 | nein – das Modell lieferte nichts |
| `SG_BLOCKED`, `SG_DECISION_PENDING` | 0 | – |

Im Projekt hat der Schutz nie eine Nachricht des Captains gesperrt; was wie eine Sperre aussah, waren Anbieterfehler und leere Antworten.
Die harten lokalen Regeln für eigenen Text (Schlüssel, Kartennummern, Steuerzeichen, unbekannte Funde) hätten aber jederzeit gegriffen.

## Behoben

| Nr | Fehler | Behebung | Test |
|---|---|---|---|
| 1 | `_prepare` baute jede Nachricht nur aus Rolle und Inhalt neu: `tool_calls` und `tool_call_id` fielen weg, das Modell sah Ergebnisse ohne eigenen Aufruf (Nemotron: 3× `get_model_status`, dann „nicht abgerufen“; vermutlich Wurzel von B4/4) | lokal bleibt die Werkzeugstruktur erhalten; Cloud weiter nur geprüfter Inhalt | `test_locally_the_tool_structure_of_the_history_is_kept` |
| 2 | leere Antwort hieß „zurückgehalten“ (`ContentGuardStop WITHHELD SG_OUTPUT_EMPTY`) | `OK` mit leerem Text, Audit `SG_OUTPUT_OK` mit `output_empty`; im Werkzeug „schutz“ „Leer – kein Eingriff des Schutzes“ | `test_an_empty_answer_is_not_withheld_by_the_guard` |
| 3 | Anbieterfehler als `SG_STOPPED` im Logbuch | eigenes Ereignis `SG_MODEL_ERROR` | `test_the_model_error_is_not_swallowed…` |
| 4 | Harness zeigte rohe Codes (`NEEDS_DECISION:SG_…`) ohne nächsten Schritt | Klartext aus `reason_text`, bei Rückfrage „Entscheide im Posteingang (Cockpit) und sende die Nachricht dann noch einmal“ | `test_rueckfrage_des_schutzes_sagt_was_zu_tun_ist` |

## Neu: „Eigenes frei“ (Entscheidung des Captains)

| Inhalt | Lokal | Cloud |
|---|---|---|
| eigener Text (Captain, Systemvorgabe, eigenes Projekt) | frei; Funde nur als Notiz `…_EIGEN` im Audit | voll geprüft (Sperre, Pseudonymisierung wie bisher) |
| Fremdes (Werkzeugergebnisse, Web, fremde Dateien) | geschützt wie bisher (Anweisungen → Rückfrage, Schlüssel → Sperre, als Daten markiert) | voll geprüft |
| Antworten des Modells | nur beobachtet | voll geprüft (zurückgehalten) |
| Grundschutz (Form, Prüffehler, Logbuch) | immer | immer |

Umsetzung: `content_policy.judge` (eigener Text lokal → `NOTE`), `content_guard._finish` (Antworten nur in der Cloud zurückhalten).
9 Tests, die die alte Regel festschrieben, prüfen jetzt den Schutzweg dort, wo er gilt (Cloud, fremder Inhalt); neu
`test_own_text_is_free_locally_and_checked_for_the_cloud`, `test_foreign_content_stays_protected_locally`.

## Prüfung

- `run_tests all`: 3193 Tests, 0 rot (Browser-Bahn ausgelassen); die 16 DevVM-Dateien (ohne `dulwich` im System-Python übersprungen) mit dem `.venv`: 239 Tests, 0 rot.
- Nicht geprüft: Lauf mit echtem Modell, ob Nemotron mit erhaltener Werkzeugstruktur die Ergebnisse jetzt nutzt (eigenes Ja nötig).

## Offen

- `chat_reply` im Cockpit zeigt Schutz-Gründe weiter als Code (Cockpit in Stufe 1 unverändert).
- Spec `SPEC_EIN_SICHERER_WEG_v1` S5 („der Modus steuert die Schärfe“) gilt lokal jetzt nur noch für Fremdes – die Spec braucht einen Nachtrag.
