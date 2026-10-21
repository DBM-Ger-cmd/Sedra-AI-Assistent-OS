# Issues (`board`)

Die Aufgaben des Teams als *Liste* (Standard) oder *Board* nach Zustand, und ein Issue im Einzelnen.
Spec 4, D4.2.2 (Gate G2-S4-07). Zeichnet `issue:alle` (Sammlung, auch als kompakte Dashboard-Karte) und `issue:*` (ein Issue).
Solange es den Desk-Typ `issue` nicht gibt, öffnet die Navigation „Issues“ die Missionen (`task:alle`, `issuesTarget` der Shell).

## Sammlung
- Spalten in der Reihenfolge von D3.3: offen, zugewiesen, in Arbeit, wartet, erledigt, abgebrochen (die letzten zwei eingeklappt,
  nur die Zahl); ein unbekannter Zustand steht unter „Sonstige“, nie verschwindet ein Issue.
- Kein Ziehen von Karten: den Zustand ändert die Orchestrierung (Checkout, Lauf, Blocker) oder das Verb `abbrechen`.
- Filter: Bearbeiter, Text, „nur offene“. Ordnung: Zustand, Priorität absteigend, jüngste Änderung.
- Liste/Board wechselt über `object.open` mit `view: 'board'`; die Shell merkt die Ansicht im Verlauf.

## Einzelansicht (`detail.js`)
Kopf (Titel, Zustand, Bearbeiter, `zuweisen`), Zielkette (Vorhaben › Projekt › Elternaufgaben › Issue; ein fehlendes Glied
steht als „nicht gefunden“), Blocker (`blocker_setzen`), Unteraufgaben, Kommentare (Cloud-Kennzeichen bei `route: cloud`) mit
Eingabe `kommentieren`, „Lauf ansehen“ (`task:<mission_id>`). Ohne Formular laufen Verben wie `abbrechen` aus der Kopfzeile, mit
Bestätigung. Daneben zeigt der Nachweis `costs` Budget und Token.

## Regeln
- Lesen `POST /api/objects` (`issue`, `agent` für Namen), Handeln `POST /api/actions` nur mit Verben aus `actions`.
  Ein Verb mit Gate meldet „Antrag liegt im Posteingang“; abgewiesen steht der Satz des Servers da, die Eingabe bleibt.
- Leer und Fehler: `quelle` fehlt oder `aus` (auch `unknown_object_type`) → „ausgeschaltet“ mit „Läufe (Missionen) ansehen“;
  `fehler` → Grund; `orchestra_busy` → „Datenbank belegt“ mit „Noch einmal lesen“.
- Kein Zeitgeber; neu gelesen wird bei `issue.changed`, `agent.changed`, `decision.answered`, `desk.resync` (ein Lesen läuft,
  ein weiteres wird gemerkt).

## Dateien
`spalten.js` (rein: `boardColumns`, `listRows`, `chain`, `feld`; Node-Test `spalten.test.js`), `detail.js`, `tool.js`, `tool.css`,
`test.spec.js` (Schein-DOM, `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`).
