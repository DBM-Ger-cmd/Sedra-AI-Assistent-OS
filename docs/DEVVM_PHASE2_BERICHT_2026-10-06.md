# DevVM Phase 2: Werkzeugsatz für die Untermodelle (2026-10-06)

Auftrag: `docs/DEVVM_AUFTRAG_2026-10-05.md` (Anforderung B). Aufbau: `docs/DEVVM_PHASE1_BERICHT_2026-10-06.md`.

## 1. Was gebaut ist
`src/guppi_runtime/devvm_tools.py` mit `DevToolBox` (gleiche Schnittstelle wie `model_tools.ToolBox`, läuft in `run_tool_loop`) und `broker_runner`.

| Werkzeug | Rollen | Wirkung |
|---|---|---|
| `list_dir`, `read_file`, `search_text`, `check_syntax` | Entwickler, Prüfer, Tester | lesen, nur auf dem Host |
| `write_file`, `make_dir`, `move_file`, `delete_file` | Entwickler | ändern im Arbeitsbereich; fehlende Ordner entstehen beim Schreiben; Regeln und Limits des Brokers |
| `diff_files`, `git_status`, `git_log` | Entwickler, Prüfer | Git über `DevWorkspace` (dulwich, keine Hooks) |
| `git_commit` | Entwickler | alle Änderungen einchecken |
| `run_tests`, `run_python` | Entwickler, Tester | **nur wenn der Aufrufer einen `vm_runner` übergibt**; die Box startet nie selbst eine VM |
| `submit_result` / `submit_review` | Abschluss je Rolle | beendet den Lauf |

- **Rollen** bestimmen die Werkzeuge: Ein Prüfer kann nicht schreiben, ein Entwickler sieht `run_tests` nur mit Läufer. Ein Werkzeug außerhalb der Rolle ist eine Fehlermeldung, die die echten Werkzeuge nennt.
- **Grenzen je Agentenlauf** (Entscheidung des Captains): 40 Werkzeugaufrufe und 10 Minuten; danach antworten alle Werkzeuge außer der Abgabe mit einem Fehler („hand in your result now"). Höchstens 2 VM-Läufe je Agentenlauf.
- **Journal:** jeder Aufruf (Werkzeug, gekürzte Argumente ohne Dateiinhalt, ok, Fehlertext, Millisekunden).
- **Fehler kommen als Text zurück**, nie als Ausnahme; Pfadfehler tragen einen Hinweis („paths are relative to the workspace root", erlaubte Dateitypen, „use list_dir").
- **VM nur über den Broker:** `broker_runner` bildet den Plan mit dem Broker und fragt ihn. Ohne Freigabe antwortet er `captain_required` (mit der Karte), das Modell liest „NOT STARTED … Continue without it". Mit der Freigabe für genau diesen Plan läuft es auf einer Kopie des Arbeitsbereichs.

## 2. Messung mit den echten Modellen (`benchmarks/devvm_tools_bench.py`)
Vier Aufgaben in einem frischen Git-Arbeitsbereich je Lauf, 2 Durchgänge. Erfolg wird mit versteckten Prüfungen in der VM auf einer Kopie bestimmt.

| Modell (Rolle) | Lauf | Erfolg | abgegeben | Fehlaufrufe | Aufrufe (Median) | Zeit je Lauf |
|---|---|---:|---:|---:|---:|---:|
| Qwen3-Coder 30B (Entwickler) | vor Pfad-Hinweis | **6/6** | 6/6 | 0 % | 16 | 35 s |
| Jan-code-4b (Entwickler) | vor Pfad-Hinweis | 3/6 | 4/6 | 6 % | 9 | 4,5 s |
| Jan-code-4b (Entwickler) | nach Pfad-Hinweis | 2/6 | **6/6** | **0 %** | 7 | 4,3 s |
| SWE-Review-8B (Prüfer) | vor Pfad-Hinweis | **4/4** | 4/4 | 41 % (17 von 23 Aufrufen in einem Lauf) | 8 | 4,2 s |
| SWE-Review-8B (Prüfer) | nach Pfad-Hinweis | **4/4** | 4/4 | **3 %** | 9,5 | 5,3 s |

Dateien: `logs/devvm_tools_bench_2026-10-06_074324.*` (vor), `…_074949.*` (nach, nur Jan und SWE-Review).

- **Das Werkzeugformat taugt für alle drei Modelle:** 0 ungültige JSON-Argumente, 0 unbekannte Werkzeugnamen, die 40-Aufrufe-Grenze wurde nie erreicht (höchstens 22).
- **Fehlaufrufe hatten eine einzige Ursache:** die Modelle nennen das Wurzelverzeichnis `.`, `/`, `/workspace` oder `workspace` (SWE-Review rief `list_dir` so 17 Mal auf). Die Werkzeugschicht versteht diese Schreibweisen jetzt als Wurzel; andere absolute Pfade, `..` und Punktnamen werden weiter abgelehnt (getestet).
- **Qualität:** SWE-Review gibt als Prüfer mit Diff und Werkzeugen in 4 von 4 Fällen das richtige Urteil ab (die richtige Änderung besteht, die falsche fällt durch). Qwen3-Coder löst alle Aufgaben. Jan scheitert bei zwei Aufgaben am Inhalt, nicht an den Werkzeugen: Bei `fix_and_commit` übersieht er das Zusammenfassen mehrfacher Leerzeichen (4 von 4 Läufen), bei `move_and_update` verschiebt er die Datei, vergisst aber den Import in `main.py` (3 von 4 Läufen).

## 3. Abnahme des Freigabe-Wegs in der echten VM (`benchmarks/devvm_phase2_check.py`)
Ein Entwickler-Kasten mit `broker_runner`, echter Guard, echter Broker, echte VM (die Probe spielt den Captain nur für ihre eigenen temporären Freigaben):
1. **Ohne Freigabe:** `run_tests` meldet „NOT STARTED … gate HG-…", **0 VM-Läufe gestartet**.
2. **Mit freigegebener Karte für genau diesen Plan:** der Test läuft in der VM, das Modell sieht die `unittest`-Ausgabe (`… ok`, `OK`).
3. **Nach einer Codeänderung:** die alte Freigabe deckt den neuen Plan nicht ab, es wird nichts gestartet, eine neue Karte ist nötig.
4. **Audit:** die Ereignisse des Arbeitsbereichs (`DEVVM_CREATED`, `DEVVM_WRITE`, `DEVVM_COMMIT`) stehen mit der Mission in der Kette.

Tests der berührten Module: `test_devvm_tools` 14, `test_devvm` 11, `test_model_tools` 7 (1 übersprungen, Symlink-Recht fehlt auf dem Rechner); alle grün.

## 4. Offen und Grenzen
- **Freigabe je VM-Lauf bleibt** (Stufe 3 und Captain-Karte); bei mehr als wenigen VM-Läufen je Agent braucht es die Entscheidung zu CW-001 (siehe Phase-1-Bericht, Punkt 2). Die Werkzeugbeschreibung sagt dem Modell, dass `run_tests` die Freigabe braucht, und bei „NOT STARTED" arbeitet es ohne weiter.
- **Nicht gemessen:** `run_python` und die Tester-Rolle mit echter VM (nur mit gespieltem Läufer getestet, der Weg ist derselbe wie bei `run_tests`); gpt-oss (sein Chat-Template läuft mit `--no-jinja`, Werkzeugaufrufe werden dort nicht geparst); Gemma (bewusst nicht).
- Jan braucht für Aufgaben mit mehreren Anforderungen mehr Hilfe als die Werkzeuge: Phase 3 (Planer und Unter-Agenten mit Prüfer und Test als Richter) setzt genau da an.
