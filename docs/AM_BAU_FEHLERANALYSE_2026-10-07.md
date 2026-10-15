# Fehleranalyse der Agent-Manager-Baulaeufe AM-002 und AM-003 (2026-10-06/07)

Messung: `devvm_build.py`, Modelle qwen3-coder-30b-a3b (Coder, Pruefer, Planer, Schiedsrichter), versteckte Abnahme von aussen (gegen eigene Referenz geprueft). Logs: `measurements/logs/devvm_build_am00{2,3}_*`.

## 1. Ergebnis
| Lauf | Stufen | Ergebnis |
|---|---|---|
| AM-002 Lauf 1 (alles in einem, 68 min) | digest, version, validate_record, seal | 2 von 4: `version` liess Nicht-ASCII-Ziffern zu, `seal`/`make_id`/`open_sealed` fehlten |
| AM-002 Nacharbeit (nur `version`, 4,5 min; nur `seal`, 14 min) | | **alle 4 Stufen und eigene Tests bestanden** (Kandidat `attempt_01_20261006_192851`) |
| AM-003 (Registry, 4 Stufen, 49 min) | crud, revision_cas, commands, outbox | 1 von 4 (`revision_cas`); eigene Tests 4 Fehler |

## 2. Ursachen (belegt)
1. **Der eigene Check ist leer.** In AM-003 war jede Stufe `unjudged=True`: der Planer lieferte nichts Brauchbares ("the planner handed in nothing usable"), der Pruefer meldete "has no check". Trotzdem steht im Protokoll `own check accepted=True`. Diese Zahl ist wertlos, wenn `unjudged` gesetzt ist. Nur die versteckte Abnahme urteilte.
2. **Ein Fehler aus Stufe 1 zog alle Folgestufen mit.** `create` benutzt `INSERT OR REPLACE`: ein vorhandener Eintrag wird still ueberschrieben, der Fehlercode `exists` kommt nie. Zwei Nacharbeitsrunden mit der Fehlerausgabe haben das nicht behoben (Runde 2: `answer_cut`/`error`). Die Stufe `outbox` scheiterte nur wegen dieses einen Fehlers.
3. **Zu grosse Antworten werden abgeschnitten** (`answer_cut` in 11 von 19 Laeufen, auch bei 2668 bis 11 000 Tokens). Die Modelle schreiben `agent_registry.py` mit ca. 400 Zeilen, mit vielen Kommentaren und derselben Pruefung in jeder Methode kopiert (`create`, `update`, `delete`, `command` je eigene Kopie). Der Kopierstil erzeugt Widersprueche zwischen den Kopien und macht Reparaturen mit `edit_file` schwer.
4. **`command` ist nicht atomar und der Replay-Vergleich ist falsch.** Nach `update` wird die Wiederholung desselben Befehls als `command_conflict` abgelehnt (`json.dumps(data)` im Vergleich, andere Felder gespeichert). Kein `BEGIN`/`COMMIT` um Aenderung, Beleg und Outbox: die Vorgabe "alles oder nichts" ist nicht erfuellt.
5. **Wiederkehrend (wie Phase 5):** Randfaelle fehlen (Nicht-ASCII-Ziffern in AM-002), Aufgaben mit vielen genauen Verhalten pro Stufe scheitern. Stufen mit 4 bis 6 Verhalten (AM-002) gingen gut, Stufen mit 10 und mehr (AM-003 `commands`, `outbox`) nicht.
6. **Prozess:** Der erste Lauf brach um 17:35 ohne Meldung ab (an die Tool-Sitzung gebunden). Entkoppelt gestartete Laeufe (`Start-Process`) liefen stabil.

## 3. Was geaendert werden sollte
| Massnahme | Wirkung | Aufwand |
|---|---|---|
| `devvm_build.py`: bei `unjudged` nie "own check accepted" melden (`own_check_accepted: null`) und im Bericht als "ungeprueft" zaehlen | ehrliche Zahlen | klein |
| Aufgaben noch kleiner schneiden: AM-003 in 8 Stufen (je 3 bis 5 Verhalten): `create`/`get`/`list`, Fehlercodes, `update`, `delete`, Receipt, Replay/Konflikt, Transaktion, Outbox, Ack | hoehere Trefferquote, Fehler in einer Stufe zieht keine Folgestufen mit | mittel |
| Aufgabentext: "eine gemeinsame Hilfsfunktion fuer die Eingabepruefung, keine Kopien, keine Kommentare" | kuerzere Dateien, weniger `answer_cut` | klein |
| Nacharbeit auf eine Stufe gezielt (`--only crud --review`) statt blind 2 Runden | wie bei AM-002 `version` (4,5 min, bestanden) | klein, per Hand |
| Antwortlimit fuer den Coder pruefen (Phase-5-Vorschlag: 8000) | weniger `answer_cut` | klein |
| Vorab: Hilfsmodul `agent_registry_common` (Pruefung, Fehler) als Seed liefern | nimmt den Kopierzwang | mittel |

## 4. Folgerung fuer den Ablauf
- **AM-002 ist abnahmefaehig** (alle versteckten Tests, eigene Tests gruen). Integrationsstufe 1 (Dateien nach `src/guppi_runtime/agent_manager/`) kann damit beginnen.
- **AM-003 ist nicht abnahmefaehig.** Nicht integrieren. Naechster Schritt: gezielte Nacharbeit je Stufe mit dem Fehlerbefund (Punkt 2 und 4) und danach feinere Stufen.
