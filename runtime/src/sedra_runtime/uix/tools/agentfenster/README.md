# Agentenfenster (`agentfenster`)

Das Gespräch mit einem Agenten, daneben seine Issues, Läufe und sein Budget. Spec 4, D4.2.5 (Gate G2-S4-10).
Zeichnet `agent:*` – die Shell öffnet ein Fenster je Agent im Stapel (`pc-stack`), höchstens vier offen, ältere als Reiter.

## Aufbau
- Kopf: Rolle, Status (aktiv, arbeitet, pausiert, beendet), Budgetbalken mit Prozent (Token; Euro nur mit Daten), offene
  Entscheidungen mit „Im Posteingang“. Der Unterarbeiter trägt „nimmt Anweisungen an und verteilt sie“.
- *Gespräch*: Nachrichten aus `POST /api/objects {type:'gespraech', agent, limit: 50}` (neueste zuletzt, Tagestrenner,
  „Ältere laden“ mit `vor`). Unter jeder Nachricht ihr Status (angekommen – Issue angelegt, wartet auf Freigabe, Lauf läuft,
  Fehler). Antworten aus der Cloud tragen „Cloud · Anbieter / Modell“, lokale nichts.
- Eingabe nur, wenn `actions` das Verb `anweisen` enthält: `POST /api/actions {type:'agent', id, verb:'anweisen', args:{text, key}}`.
  `key` ist neu je Anweisung und bleibt bei einer Wiederholung desselben Texts gleich – so entsteht nie eine doppelte Nachricht.
  Abgewiesen steht der Satz des Servers über der Eingabe, der Text bleibt.
- *Issues* des Agenten (Link auf `issue:<id>`), *Läufe* (Link auf `task:<mission_id>`, wo `live` die Zeilen zeigt).
- Die übrigen Verben (pausieren, fortsetzen, beenden …) stehen im Kopf des Fensters; ein Verb mit Gate meldet „Antrag liegt im Posteingang“.

## Zustände
pausiert (Hinweis, die Eingabe bleibt), beendet (nur Lesen), Budget gestoppt (Hinweis), Agent unbekannt („gibt es nicht mehr“,
das Fenster schließt ✕), Orchestrierung aus (`unknown_object_type`), `gespraech` fehlt („Gespräche gibt es mit der Orchestrierung“),
nicht lesbar (rote Zeile, „Noch einmal lesen“). Kein Zeitgeber: neu gelesen wird bei `agent.changed` dieses Agenten, `issue.changed`,
`budget.warning`, `decision.pending`/`decision.answered`, `desk.resync` – ein Lesen läuft, ein weiteres wird gemerkt.

Den Agenten liest das Fenster aus der Liste `{type:'agent'}` (mit `quelle`), nicht aus der Einzelansicht: der Platzhalter
bei ausgeschalteter Orchestrierung beantwortet nur die Liste.

## Mehrere Instanzen (Nachtrag N2)
Ein Zustand je Container (`instanzen`, eine `Map`); `unmount(el)` und `actions(el)` finden die richtige Instanz.

## Dateien
`verlauf.js` (rein: `mergeMessages`, `statusText`, `byDay`, `cloudText`; Node-Test `verlauf.test.js`), `tool.js`, `tool.css`,
`test.spec.js` (Schein-DOM, `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`).
