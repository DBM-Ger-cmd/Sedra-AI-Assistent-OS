# Organigramm (`org`)

Das Team als Baum: Captain oben, darunter der Unterarbeiter (der Agent ohne Vorgesetzten), darunter seine Untergebenen.
Jede Karte zeigt Name, Rolle, Status (aktiv, arbeitet, pausiert, beendet), den Budgetbalken in Token mit Prozentzahl und
die Zahl offener Entscheidungen. Klick auf eine Karte öffnet das Agentenfenster; das Menü ⋯ zeigt die Verben des Agenten.

Spec 4, D4.2.1 (Gate G2-S4-06). Zeichnet `agent:alle` (Seite und Dashboard-Karte mit `kompakt`).

## Ansichten
- *Baum* (Standard) und *Liste* (Tabelle). Der Umschalter sendet `object.open` mit `view: 'liste'`; die Shell merkt die Ansicht.
- Beendete Agenten sind ausgeblendet; „Beendete zeigen“ blendet sie ein.
- Agenten, die der Baum nicht erreicht (Zyklus, unbekannter Vorgesetzter), stehen unter „Nicht eingeordnet“.

## Daten und Handlungen
- Lesen: `POST /api/objects {type:'agent'}` – eine Anfrage für den ganzen Baum. Felder `rolle`, `reports_to`, `status`,
  `arbeitet`, `budget`, `offene_entscheidungen` liefert Spec 1 (G2-S4-16); fehlt ein Feld, fehlt nur seine Anzeige.
- Handeln: nur Verben aus `actions` über `POST /api/actions`. `einstellen` (am Typ, aus `actions` der Liste) und `einordnen`
  bekommen ein kleines Formular; ein Verb mit Gate meldet „Antrag liegt im Posteingang“.
- Einstellen (Entscheidung HALT 3 B, Captain 22.10.2026) ist der zweite von zwei Anträgen: die AM-Instanz entsteht vorher im
  Agent-Manager, `einstellen` ordnet sie ein – Argumente `{name, instance_id, reports_to, budget_tokens}`. Liefert die Liste
  `freie_instanzen`, ist `instance_id` eine Auswahl, sonst ein Eingabefeld mit Hinweis. `instance_taken`, `binding_stale`,
  `instance_not_found`, `instance_not_active` erscheinen als deutscher Satz; die Eingabe bleibt stehen.
- Leer und Fehler (UIX-10): `quelle.zustand` `aus` oder fehlend → „ausgeschaltet“; `fehler` → „ausgefallen: Grund“;
  `orchestra_busy` → „Datenbank belegt“ mit „Noch einmal lesen“.
- Kein Zeitgeber: neu gelesen wird bei `agent.changed`, `budget.warning`, `decision.pending`, `decision.answered`, `desk.resync`
  (ein Lesen läuft, ein weiteres wird gemerkt).

## Dateien
- `baum.js` – rein: `layoutTree`, `budgetStufe`, `budgetBalken` (Node-Test `baum.test.js`).
- `tool.js`, `tool.css` – Zeichnen und Verben; `test.spec.js` – Werkzeug im Schein-DOM (`node -r ../../../../../tests/uix_spec_dom.js test.spec.js`).
