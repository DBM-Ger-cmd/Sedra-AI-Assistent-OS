# Routinen (`routines`)

Wiederkehrende Aufgaben des Teams: Titel, Agent, Zeitplan in Worten (mit Zeitzone), Nachhol-Regel (`auslassen` ist der
Standard), an/aus, letzte Ausführung mit Ausgang (`erzeugt`, `ausgelassen`, `nachgeholt`) und nächste Ausführung.
Spec 4, D4.2.3 (Gate G2-S4-08). Zeichnet `routine:alle` (Tabelle) und `routine:*` (eine Routine mit Aufgabenvorlage und den
letzten 20 Läufen, je mit Link aufs Issue).

## Regeln
- Der Zeitplan in Worten kommt aus `cron.js` (`cronText`): fünf Felder mit `*`, Zahl, Liste, Bereich, Schritt, Wochentag- und
  Monatsnamen. Was der Satz nicht sicher sagen kann, steht als Ausdruck da. Termine (`next_run`) berechnet nur der Server.
- Über der Tabelle steht der Takt aus `quelle.takt`: läuft, aus („Routinen laufen nur, solange die Oberfläche läuft“) oder unbekannt.
- Eine Routine, deren Agent pausiert oder beendet ist, trägt „Agent pausiert – es entstehen keine Aufgaben“.
- Verben nur aus `actions`: `anlegen` (am Typ), `aendern`, `ausschalten`, `einschalten`. `anlegen` und `aendern` öffnen ein Formular;
  unter dem Zeitplan steht sofort der Satz, sonst „Zeitplan wird so gespeichert: …“. `set_routine` ist ein Antrag („Antrag liegt im
  Posteingang“); abgewiesen (`cron_invalid`) steht der Satz des Servers da, das Formular bleibt.
- Leer und Fehler: `quelle` fehlt oder `aus` (auch `unknown_object_type`) → „ausgeschaltet“; `fehler` → Grund; `orchestra_busy` →
  „Datenbank belegt“ mit „Noch einmal lesen“. Kein Zeitgeber; neu gelesen wird bei `agent.changed`, `issue.changed`,
  `decision.answered`, `desk.resync`.

## Dateien
`cron.js` (rein, Node-Test `cron.test.js`), `tool.js`, `tool.css`, `test.spec.js` (Schein-DOM,
`node -r ../../../../../tests/uix_spec_dom.js test.spec.js`).
