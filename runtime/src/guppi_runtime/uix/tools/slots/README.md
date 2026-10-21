# Slots (`slots`)

Die Seite „Modelle und Slots“ oben: das geladene Modell, die Slots des Modellservers (Nummer, frei/belegt, Agent, Lauf,
Priorität Captain/Agent/Routine, seit wann als Uhrzeit) und die Warteschlange in Reihenfolge mit Wartebeginn. Wartet ein Lauf
länger als `warte_max_s`, steht eine Warnzeile da – mit „Cloud-Vorschlag liegt im Posteingang“, wenn eine Entscheidung vorliegt.
Spec 4, D4.2.4 (Gate G2-S4-09). Zeichnet `model:alle` vor der Werkstatt (`order: 5`); Laden und Entladen bleibt in der Werkstatt darunter.

## Regeln
- Lesen nur `POST /api/objects {type:'model'}` (Feld `slots` von Spec 2: `{gesamt, belegt, schlange, modell, warte_max_s}`) und
  `{type:'agent'}` für Namen. Keine Verben.
- Ohne `slots`: „Ein Modellserver, ein Platz. Parallele Slots kommen mit dem Scheduler (Spec 2).“ und das laufende Modell;
  ohne geladenes Modell: „Kein Modell geladen – Slots gibt es erst nach dem Laden (Werkstatt unten).“
- Kein Zeitgeber: neu gelesen wird bei `slot.changed`, `model.changed`, `agent.changed`, `desk.resync`.

## Dateien
`tool.js` (rein: `slotRows`, `wartetZuLange`, `ohneSlots`), `tool.css`, `test.spec.js` (Schein-DOM,
`node -r ../../../../../tests/uix_spec_dom.js test.spec.js`).
