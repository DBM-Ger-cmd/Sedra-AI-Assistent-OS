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

## Stufe 2 – Hände und Grenzen

Werkzeuge `datei_lesen`, `dateien_auflisten`, `suchen`, `datei_schreiben`, `datei_aendern`, `befehl` (harness/werkzeuge.py, befehl.py).
Jeder Aufruf: Vorbehalt → Freigabe-Katalog → Guard (harness/freigabe.py). `frei` läuft sofort; `verboten` bekommt das Modell als Grund;
`captain` erzeugt eine **Karte** im Verlauf (Diff oder Befehlszeile, Erlauben · Diff zeigen · Ablehnen) – dieselbe Karte steht im
Posteingang. Die Werkzeugzeile zeigt Stufe und Regel; das Schild im Eingabefeld zeigt den Katalog. „Diff zeigen“ öffnet den Diff als Reiter.

## Noch nicht da

Vorlagen und Vorarbeiter, Aufgaben-Freigabe, Läufe in der Taskleiste (Stufe 3); Dateien anhängen (`+`, `@`); Start-Menü mit Apps und
Statusbereich statt Leiste (Stufe 4); Einstellungen und Katalog-Editor (Stufe 5).

## Stufe 3 (Version 1.2.0): Vorarbeiter und Aufgaben-Freigabe

- **Karte:** zeigt, wer entscheidet („Beim Vorarbeiter“, „vorgelegt“, „Frist abgelaufen“) und nach einer Entscheidung des Vorarbeiters seine Begründung; der Captain kann übersteuern. Die Karte zieht sich nach, wenn anderswo entschieden wird (`decision.answered`, `harness.karte`).
- **Aufgaben** (`aufgabe.js`, Reiter über „⛨ Aufgaben“ in der Seitenleiste): Vorschläge des Vorarbeiters (Einträge abhaken, Frist und Zähler setzen), aktive Aufgaben mit Rest und „Zurücknehmen“ (Läufe mit stoppen), Formular „Aufgabe freigeben“.
- **Schild** im Eingabefeld: Captain, Vorarbeiter oder „Du bist Vorarbeiter“, dazu die geltende Aufgabe mit Rest.
- **Seitenleiste:** ⚑ markiert den Vorarbeiter; an Sitzungen mit der Vorlage `vorarbeiter` ernennt oder entzieht der Captain. Neue Sitzungen können eine Vorlage wählen.
- Browser-Durchlauf mit Modell-Attrappe: `SEDRA_BROWSER=1 python -m unittest test_uix_harness_browser` (kein Modell).
