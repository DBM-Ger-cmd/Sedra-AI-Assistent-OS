---
name: sedra-workflow-aufbau
description: Den Aufbau (Linien, Kacheln, Abstände) von Workflows im SEDRA Workflow Studio prüfen und ruhig halten - Aufbau-Wächter messen, Grenzen, Tests über alle gespeicherten Workflows, neue Darstellung einhängen. Nutzen, wenn ein Workflow "Liniengewirr" zeigt, Linien durch Kacheln laufen, sich kreuzen oder übereinanderliegen, wenn die Kantenführung oder das Layout geändert wird, oder wenn der Captain "Aufbau", "Linien", "aufräumen" oder "Gewirr" sagt.
---

# Aufbau-Wächter der Workflow-Darstellung

Gilt für **jeden** Workflow in jedem Editor (n8n Workflows, Szenario Studio, Workflow Studio). Nie für einen einzelnen Workflow zurechtbiegen: wird ein Aufbau unruhig, wird die Regel besser, nicht der eine Workflow von Hand verschoben.

## Bausteine (alle unter `runtime/src/sedra_runtime/uix/ui/`)

| Datei | Aufgabe |
|---|---|
| `workflow-layout.js` | Anordnung in Ebenen (`anordnen`, `logisch`) und Kantenführung (`fuehren`, `pfad`). Rein, ohne DOM. |
| `workflow-layout-waechter.js` | `routen` (dieselben Wege wie die Zeichenfläche), `pruefe` (Befund), `besser` (Abstände und Zeilenreihenfolgen durchprobieren, kleinsten Wert nehmen). Rein. |
| `workflow-aufbau.js` | Einbindung in den Editor: `beimOeffnen` (einmal beruhigen, nicht als Änderung), `zeige` (Statuszeile "Aufbau: ruhig / unruhig"), `aufraeumen` (Knopf, rückgängig machbar). |
| `workflow-editor.js` | Zwei Einhängestellen: in `adopt()` und am Ende von `draw()`. Die Datei muss unter 400 Zeilen bleiben (Test in `test_workflow_layout.py`). |
| `desk.html` | Lädt Wächter und Aufbau nach `workflow-layout.js`. |

## Was gemessen wird

Wert = 20 je Linie durch eine Kachel + 8 je übereinanderliegendes Linienstück + 3 je Kreuzung + 4 je großem Umweg. Ruhig heißt: keine Linie durch Kachel, keine Überlappung, höchstens `kreuzungen + je_schleife * Schleifen` Kreuzungen (Standard 2 + 2 je Rücksprung), höchstens 1 Umweg. Grenzen stehen in `GRENZE` im Wächter; Kanten desselben Ausgangs oder Eingangs dürfen sich am Ende berühren.

## Regeln

- **Nur Positionen ändern.** Knoten, Verbindungen, Parameter und die gespeicherte Revision bleiben unberührt; `besser` arbeitet auf einer Kopie.
- **Nie eine Änderung vortäuschen.** Das Beruhigen beim Öffnen setzt `saved` auf den beruhigten Stand, damit "Workflow starten" nicht an "Vor dem Start speichern" hängt. Das ist rein optisch und wird bei jedem Öffnen gleich neu berechnet.
- **Die Aufsicht darf die Zeichenfläche nie stören:** alles in `try/catch`, bei Fehler bleibt das Dokument wie es ist.
- **Messung und Zeichnung müssen dieselben Wege benutzen.** Ändert sich die Kantenführung in `workflow-canvas.js` (Gassen, Querbahnen, Bahnen für Rücksprünge), muss `routen()` im Wächter nachgezogen werden; sonst misst er etwas anderes, als man sieht.
- Neue Kachelgeometrie (`G`) im Canvas: in `TILE`/`CIRCLE` des Wächters ergänzen.

## Prüfen

```bash
node --test runtime/tests/workflow_aufbau_waechter.test.cjs runtime/tests/workflow_logical_layout.test.cjs
cd runtime && PYTHONPATH="src;tests;.venv/Lib/site-packages" .venv/Scripts/python.exe -m unittest test_workflow_layout
```

Der Test `jeder gespeicherte Workflow des Projekts ist nach dem Öffnen ruhig` liest alle Workflows aus `workspace/SEDRA_OS/runtime_data/workflows` (jeweils die letzte Revision). Er fällt, wenn ein neuer oder geänderter Workflow nach dem Beruhigen noch unruhig ist: erst `besser` verbessern (mehr Kandidaten), erst zuletzt die Grenze lockern.

## Sichtprüfung

Ohne laufendes Studio: Wege eines echten Workflows mit `routen` + `pfad` als SVG zeichnen, vorher (gespeicherte Positionen) und nachher (`beimOeffnen`), und im Browser ansehen. Mit laufendem Studio: Skill `sedra-ui-sichtpruefung`.

## Fallen

- Reiner JS-Stand: Änderungen an `uix/ui/*.js` wirken nach Neuladen der Oberfläche, ein Neustart des Dienstes ist nicht nötig.
- Eine lange einzeilige Reihe (zwölf Kacheln nebeneinander) ist ruhig, aber breit; Zoom und Einpassen der Zeichenfläche gleichen das aus. Soll es kompakter sein, neue Kandidaten in `kandidaten()` ergänzen, nicht die Grenzen senken.
- Beim Mergen von `main`: `workflow-editor.js` und `workflow-canvas.js` werden von mehreren Sitzungen geändert; die zwei Einhängestellen sind klein und leicht wieder zu setzen.
