# Harness-Shell (Stufe 5, Version 1.5.0)

Spec: `docs/SPEC_HARNESS_SHELL_v1.md` (G1), `docs/SPEC_HARNESS_SHELL_v1_G2.md` (Design Stufe 1/2), `…_G2_STUFE3.md`/`…_G3_STUFE3.md` (Stufe 3), `…_G2_STUFE4.md`/`…_G3_STUFE4.md` (Stufe 4), `…_G2_STUFE5.md`/`…_G3_STUFE5.md` (Stufe 5).
Starten: `START_SEDRA harness` oder in der Start-Shell „Diese Oberfläche nehmen“. Das Cockpit bleibt unverändert daneben.

## Zonen (HS-01)

| Zone | Klasse | Datei | Inhalt |
|---|---|---|---|
| Seitenleiste | `.hs-seite` | `seite.js` | Neue Sitzung, Projekte mit Sitzungen, Chats, Einstellungen (Stufe 5); Strg+B |
| Reiterleiste | `.hs-reiter` | `reiter.js` | ein Reiter je Sitzung; `+` neu, mittlere Maustaste schließt; `localStorage` `sedra.harness.reiter` |
| Arbeitsfläche | `.hs-flaeche` | `verlauf.js`, `markdown.js` | Gespräch: Strom lesen, Text grau bis geprüft, Denken eingeklappt, Werkzeugzeilen aufklappbar |
| Eingabefeld | `.hs-eingabe` | `eingabe.js` | Enter sendet, Umschalt+Enter Zeile, Stopp/Esc, Schild, Modell, Mikrofon, `/` Befehle |
| Taskleiste | `.hs-taskleiste` | `taskleiste.js` | Start (Start-Menü), offene Sitzungen, Apps und Läufe, Statusbereich aus `/api/strip` (HS-32), Uhr |
| Start-Menü | `.hs-start-menue` | `startmenue.js`, `startliste.js` (rein), `start_gruppen.json` | Apps mit Suche, Gruppen, zuletzt (`uix.shelf.harness`), Oberflächen, Darstellung · Schrift (Stufe 4) |
| App-Reiter | `.hs-app-box` | `app.js` | ein Werkzeug des Vertrags als Reiter `app:<typ>:<id>`, Nachweise rechts, Arbeitsstand (Stufe 4) |
| Einstellungen | `.hs-einst` | `einstellungen.js`, `katalog_editor.js`, `katalog_editor_pruefung.js` (rein) | Reiter `einstellungen:[gruppe/punkt]`: sechs Gruppen, Werkzeuge eingehängt (`app.flaeche`), Katalog-Editor, Grenzen, Schalter – alles Schreiben als Antrag mit Gate (Stufe 5) |

`shell.js` hält den Zustand und registriert die Shell. Seit Stufe 4 steht `umschalter: menue` im Manifest (Vertrag N3): kein Alt+S-Chip, kein
Mini-Hub – Alt+S, der Knopf „Start“ und `/start` öffnen das Start-Menü der Shell; der Rekorder ist dort eine App.

## Wege

`/api/harness/projekte`, `/api/harness/sitzungen[/<id>[/nachricht]]`, `/api/harness/antworten/<id>/strom|stopp` (harness/api.py),
dazu `/api/strip`, `/api/models`, `/api/events`. Der Strom einer Antwort wird mit `fetch` gelesen (Kopf `X-SEDRA-Shell`).

## Stufe 2 – Hände und Grenzen

Werkzeuge `datei_lesen`, `dateien_auflisten`, `suchen`, `datei_schreiben`, `datei_aendern`, `befehl` (harness/werkzeuge.py, befehl.py).
Jeder Aufruf: Vorbehalt → Freigabe-Katalog → Guard (harness/freigabe.py). `frei` läuft sofort; `verboten` bekommt das Modell als Grund;
`captain` erzeugt eine **Karte** im Verlauf (Diff oder Befehlszeile, Erlauben · Diff zeigen · Ablehnen) – dieselbe Karte steht im
Posteingang. Die Werkzeugzeile zeigt Stufe und Regel; das Schild im Eingabefeld zeigt den Katalog. „Diff zeigen“ öffnet den Diff als Reiter.

## Noch nicht da

Dateien anhängen (`+`, `@`); der Systemtext einer Vorlage (`.md`) ist in den Einstellungen nicht lesbar (kein Lese-Weg; die Datei liegt neben der Vorlage).

## Stufe 3 (Version 1.2.0): Vorarbeiter und Aufgaben-Freigabe

- **Karte:** zeigt, wer entscheidet („Beim Vorarbeiter“, „vorgelegt“, „Frist abgelaufen“) und nach einer Entscheidung des Vorarbeiters seine Begründung; der Captain kann übersteuern. Die Karte zieht sich nach, wenn anderswo entschieden wird (`decision.answered`, `harness.karte`).
- **Aufgaben** (`aufgabe.js`, Reiter über „⛨ Aufgaben“ in der Seitenleiste): Vorschläge des Vorarbeiters (Einträge abhaken, Frist und Zähler setzen), aktive Aufgaben mit Rest und „Zurücknehmen“ (Läufe mit stoppen), Formular „Aufgabe freigeben“.
- **Schild** im Eingabefeld: Captain, Vorarbeiter oder „Du bist Vorarbeiter“, dazu die geltende Aufgabe mit Rest.
- **Seitenleiste:** ⚑ markiert den Vorarbeiter; an Sitzungen mit der Vorlage `vorarbeiter` ernennt oder entzieht der Captain. Neue Sitzungen können eine Vorlage wählen.
- Browser-Durchlauf mit Modell-Attrappe: `SEDRA_BROWSER=1 python -m unittest test_uix_harness_browser` (kein Modell).

## Stufe 4 (Version 1.4.0): Start-Menü, Apps, Statusbereich

- **Start-Menü** (`startmenue.js`, HS-40/41): Knopf „Start“, Alt+S, `/start`. Suche über Name, Hinweis und die Suchwörter aus `ui/places.js`;
  „Zuletzt benutzt“ liegt in `uix.shelf.harness` (`/api/uix/shelf`, auf dem Rechner, nicht im Browser); Gruppen aus `start_gruppen.json`
  (Ort-ID oder Objekttyp → Gruppe) oder aus dem Manifest-Feld `gruppe` (Vertrag N2); „Prüfung“ nur, wenn ein reiner Prüf-Ort geladen ist.
  Unten die anderen Oberflächen (Wechsel über `sedraWechsel.wechseln`, offene Apps gehen mit), Darstellung, Schrift, „Gedächtnis leeren“.
- **App-Reiter** (`app.js`): `ctx.tools.forObject` → `ctx.makeContext` → `sedraLifecycle.mountTool` – derselbe Weg wie Cockpit und Minimal.
  `inhalt` in der Fläche, `nachweis` rechts zum Aufklappen; `shellApi.open(objekt)` öffnet oder aktiviert; höchstens 8 Apps (der älteste
  nicht aktive geht mit Satz zu); Objekte werden an `sedraStand` gemeldet und beim Start aus dem Arbeitsstand übernommen.
- **Statusbereich** (`taskleiste.js`, HS-32/43): Freigaben, Modell, GPU (Temperatur mit Quelle, VRAM belegt/gesamt, thermischer Zustand),
  RAM, Modellserver, Scheduler, Zustand, Uhr – alles aus `/api/strip` (≤ alle 2 s). Zellen ohne Wert sind ausgeblendet; ein Klick öffnet die App.
- Reine Teile mit `node`: `tests/test_uix_harness_start.py`; Browser: `benchmarks/uix_check.py --shell harness`, `harness_abnahme.py --stufe4`.

## Stufe 5 (Version 1.5.0): Einstellungen und Katalog-Editor

- **Einstellungen** (`einstellungen.js`, HS-42): Reiter `einstellungen:` über den Knopf in der Seitenleiste, Start → System → Einstellungen,
  `/einstellungen [gruppe/punkt]` und die Zelle „Zustand“ (D-U6). Sechs Gruppen, 21 Punkte (G2 §3.1). Die meisten Punkte sind vorhandene
  Werkzeuge, eingehängt über `app.flaeche` (derselbe Weg wie der App-Reiter, nur auf das genannte Werkzeug beschränkt) – kein Nachbau (D-U1).
  Eigene Flächen: Darstellung, Benachrichtigungen (K9: Browser-Hinweis „eine Freigabe wartet“ nur nach Klick-Erlaubnis, Blinken an/aus),
  Vorlagen, Freigabe-Modus, Grenzen der Schleife, Quelle, MCP (`GET /api/uix/clients`, nie der Token), Laufzeit, Schalter (`switch_request`).
- **Katalog-Editor** (`katalog_editor.js`, G2 §4): Tabelle aller Regeln mit Herkunft (Vorlage/Datei/neu), alle Felder bearbeitbar (D-U3);
  Vorlage-`verboten` gesperrt; Befunde live aus `katalog_editor_pruefung.js` (Fehler, Lockerung und weite Muster rot, Diff, YAML-Vorschau).
  Der Editor schreibt nie: „Antrag stellen“ → `POST /api/harness/katalog/antrag` (Art `harness_katalog`, `HARNESS_KATALOG_WRITE`, Bindung
  = Hash von Entwurf und Stand, Risiken = Befunde); erst „Freigeben und anwenden“ im Posteingang schreibt (`harness/antraege.py`: Stand
  verändert → `binding_stale`; Sicherung `.bak-<zeit>`; Audit `HARNESS_KATALOG_WRITTEN`). „Zurück zur Vorlage“ ist der Antrag `katalog/entfernen`.
- **Grenzen** (D-U4): `max_zuege` je Vorlage → `POST /api/harness/vorlagen/grenzen` (Art `harness_vorlage`) → Kopie nach
  `local_config/harness_vorlagen/`; die Datei im Repo bleibt. Herkunftsprüfung S7 auf allen drei Antrag-Wegen (403 aus einem Harness-Prozess).
- Reine Teile mit `node`: `tests/test_uix_harness_einstellungen.py`; Server: `tests/test_harness_katalog_editor.py`; Browser:
  `benchmarks/uix_check.py --shell harness` (Prüfung „einstellungen“), `harness_abnahme.py --stufe5`.
