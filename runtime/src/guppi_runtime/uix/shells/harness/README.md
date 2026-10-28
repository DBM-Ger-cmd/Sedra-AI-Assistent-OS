# Harness-Shell (Stufe 1)

Spec: `docs/SPEC_HARNESS_SHELL_v1.md` (G1), `docs/SPEC_HARNESS_SHELL_v1_G2.md` (Design), `docs/SPEC_HARNESS_SHELL_v1_G3_STUFE1.md` (Bau).
Starten: `START_SEDRA harness` oder in der Start-Shell „Diese Oberfläche nehmen“. Das Cockpit bleibt unverändert daneben.

## Zonen (HS-01)

| Zone | Klasse | Datei | Inhalt |
|---|---|---|---|
| Seitenleiste | `.hs-seite` | `seite.js` | Neue Sitzung, Projekte mit Sitzungen, Chats, Einstellungen (Stufe 5); Strg+B |
| Reiterleiste | `.hs-reiter` | `reiter.js` | ein Reiter je Sitzung; `+` neu, mittlere Maustaste schließt; `localStorage` `sedra.harness.reiter` |
| Arbeitsfläche | `.hs-flaeche` | `verlauf.js`, `markdown.js` | Gespräch: Strom lesen, Text grau bis geprüft, Denken eingeklappt, Werkzeugzeilen aufklappbar |
| Eingabefeld | `.hs-eingabe` | `eingabe.js` | Enter sendet, Umschalt+Enter Zeile, Stopp/Esc, Schild, Modell, Mikrofon, `/` Befehle |
| Taskleiste | `.hs-taskleiste` | `taskleiste.js` | Start (Liste der Oberflächen), offene und laufende Sitzungen, Status aus `/api/strip`, Uhr |

`shell.js` hält den Zustand und registriert die Shell. Der schwebende Mini-Hub der Seite ist ausgeblendet; „Start“ öffnet sein
Oberflächen-Menü, das Mikrofon seinen Rekorder.

## Wege

`/api/harness/projekte`, `/api/harness/sitzungen[/<id>[/nachricht]]`, `/api/harness/antworten/<id>/strom|stopp` (harness/api.py),
dazu `/api/strip`, `/api/models`, `/api/events`. Der Strom einer Antwort wird mit `fetch` gelesen (Kopf `X-SEDRA-Shell`).

## Stufe 1 – was noch nicht da ist

Werkzeuge mit Wirkung, Freigabe-Katalog und Karten (Stufe 2); Dateien anhängen (`+`, `@`) ab Stufe 2; Vorlagen und Vorarbeiter (Stufe 3);
Start-Menü mit Apps und Statusbereich statt Leiste (Stufe 4); Einstellungen (Stufe 5).
