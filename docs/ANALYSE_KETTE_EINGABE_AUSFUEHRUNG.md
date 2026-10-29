# Analyse: die Kette von der Eingabe bis zur Ausführung

Stand 28.10.2026, Branch `spec/agenten-orchestrierung`. Grundlage: der Code, das Audit-Log und die Werte aus dem Lauf
`M-5A3A1A70` (08:59 Uhr). Die Analyse ändert nichts.

## 1. Eingabe (Oberfläche)

- Der Master-Chat ist das Werkzeug `entwurf` (`uix/tools/entwurf/tool.js`, Titel „Master-Chat“). Er ist unten im Cockpit
  fest verankert (`shells/cockpit/shell.js`, „kein Reiter, nur der Cursor in das Eingabefeld“).
- Eine lokale Nachricht geht als `POST /api/chat/reply` mit `text`, `history` und `mission_id: ''`.
- Eine Cloud-Nachricht geht als `POST /api/chat/cloud`.

## 2. Vorabweg ohne Modell (`uix_server.chat_reply`, Zeile 1886)

1. Fragen an das KI-GateWay beantwortet `GatewayWissen` deterministisch, ohne Modellaufruf.
2. Fragen nach dem Arbeitsplatz beantwortet `arbeitsplatz.antwort` aus Code und Live-Stand, ebenfalls ohne Modell.
3. Erst danach kommt das Modell.

## 3. Das Modell (Werkzeugschleife)

- Es wird eine Mission `Chat-Sitzung mit dem lokalen Modell` (S1) angelegt, die alle Modellaufrufe dieses Fensters bündelt.
- Die Werkzeuge kommen aus `chat_tools.py`. Sie lesen den Zustand, oder sie **bieten** eine Handlung an: `open_place`,
  `open_object`, `propose_action`, `propose_intent`. Die Handlung wird nur als `ui_actions` in die Antwort gelegt und
  ausgeführt wird nichts.
- Die Schleife (`devenv/model_tools.py`, `run_tool_loop`) läuft höchstens 8 Züge. Jeder Zug geht über
  `control.execute(model_inference)` → `model_router.chat` → Inhaltsschutz → Adapter.
- Gibt es ein Stichwort wie „Aufgabe“, „Fenster“ oder „Modell“, erzwingt der erste Zug ein Werkzeug (`tool_choice=required`).

## 4. Inhaltsschutz und Antwort

- `core/content_guard.py` prüft Eingabe und Antwort. Eine leere Antwort wird als `SG_OUTPUT_EMPTY` zurückgehalten.
- Werkzeugaufrufe kommen beim lokalen Adapter in `message.tool_calls`. Bis 28.10. las der Router nur das Ergebnis oben,
  dadurch war eine reine Werkzeugantwort leer, und mit Text liefen die Aufrufe ungeprüft durch. Behoben in `f044f11`.
- Hat die Schleife am Limit keinen Text, gibt es jetzt eine letzte Antwort ohne Werkzeuge (`FINAL_ANSWER_NOTE`).
  Das ist noch nicht im laufenden Cockpit geprüft.

## 5. Vom Knopf zur Ausführung

1. Der Captain klickt den Knopf. Die Oberfläche ruft `POST /api/actions` (`uix_server.act`).
2. `desk/actions.run` liest den Zustand **frisch**. Ein Verb, das jetzt nicht angeboten wird, läuft nicht.
3. Das Verb `ausfuehren` ruft `hub.run_mission` → `brain.run`.
4. `brain.run` führt die Schritte des Plans aus. Jeder Schritt geht durch `control.execute`, und dort greifen die Guard-Regeln
   (z. B. `GR-002` für neue Artefakte).
5. Ein Schritt `create_text_artifact` schreibt nur eine Datei `result.txt` mit dem Auftragstext.
6. Die Prüfung (`verification`) verlangt nur `artifact_exists ≥ 1`. Dann steht die Mission auf `COMPLETE`.

## 6. Befunde

| # | Stelle | Befund | Stand |
|---|---|---|---|
| 1 | Prüfung (`verification`) | Ein Plan-Artefakt besteht die Prüfung, obwohl nichts ausgeführt wurde. | Anzeige korrigiert (`nur Plan`), die Prüfung selbst nicht |
| 2 | `chat_tools.py` | Es gibt kein Werkzeug, das Oberflächen-Code schreibt. Ein Auftrag wie „Master-Chat-Fenster bauen“ kann nicht ausgeführt werden. | offen |
| 3 | Router | Werkzeugaufrufe in `message.tool_calls` wurden nicht geprüft. | behoben, `f044f11` |
| 4 | Werkzeugschleife | Das Modell kann dasselbe Werkzeug achtmal rufen. Eine Wiederholung wird nicht erkannt. | nur die Notantwort am Limit, offen |
| 5 | Erzwungenes Werkzeug | Stichwörter wie „Aufgabe“ zwingen den ersten Zug zu einem Werkzeug. Kleine Modelle antworten dann ohne Text. | offen |
| 6 | Oberfläche | Eine Aufgabe ohne Werkzeug wurde „fertig“ genannt. | behoben, nicht im Cockpit geprüft |

## 7. Offen

- Die Prüfung soll einen Plan ohne Ausführung nicht mehr als Erfolg werten.
- Wiederholte Werkzeugaufrufe sollen abgebrochen werden, statt bis zum Limit weiterzulaufen.
- Die Stichwort-Erzwingung (`CHAT_MOVE_WORDS`, `asks_state`) braucht einen Test mit einem kleinen Modell.
- Ein Werkzeug für „Oberfläche bauen“ fehlt. Das ist eine eigene Entwicklung und kein Fehler der Kette.
