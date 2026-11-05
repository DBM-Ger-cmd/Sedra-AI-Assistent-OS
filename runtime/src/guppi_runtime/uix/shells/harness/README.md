# One Sedra – die Harness-Shell (Stufe 6 + Bau 1.11.2026, Version 1.9.0)

**Name seit 05.11.2026:** die Oberfläche heißt **One Sedra** und bündelt die Fähigkeiten der anderen Shells (Cockpit, Translator, Gateway, Paperclip, Wissensbasis, Minimal). Nur der Anzeigename ist neu; die technische Kennung bleibt `harness` (Adressen, `/api/harness/*`, Ordner, `START_SEDRA harness`), damit nichts bricht.

Spec: `docs/SPEC_HARNESS_SHELL_v1.md` (G1), `docs/SPEC_HARNESS_SHELL_v1_G2.md` (Design Stufe 1/2), `…_G2_STUFE3.md`/`…_G3_STUFE3.md` (Stufe 3), `…_G2_STUFE4.md`/`…_G3_STUFE4.md` (Stufe 4), `…_G2_STUFE5.md`/`…_G3_STUFE5.md` (Stufe 5), `…_G2_STUFE6.md` (Stufe 6); Analyse und Bau 1.11.2026: `docs/ANALYSE_HARNESS_2026-11-01.md`, `docs/BAUBERICHT_HARNESS_BAU_2026-11-01.md`.
Starten: `START_SEDRA harness` oder in der Start-Shell „Diese Oberfläche nehmen“. Das Cockpit bleibt unverändert daneben.

## Zonen (HS-01)

| Zone | Klasse | Datei | Inhalt |
|---|---|---|---|
| Seitenleiste | `.hs-seite` | `seite.js` | Neue Sitzung, Projekte mit Sitzungen, Chats, Einstellungen (Stufe 5); Strg+B |
| Reiterleiste | `.hs-reiter` | `reiter.js` | ein Reiter je Sitzung; `+` neu, mittlere Maustaste schließt; `localStorage` `sedra.harness.reiter` |
| Arbeitsfläche | `.hs-flaeche` | `verlauf.js`, `markdown.js` | Gespräch: Strom lesen, Text grau bis geprüft, Denken eingeklappt, Werkzeugzeilen aufklappbar |
| Eingabefeld | `.hs-eingabe` | `eingabe.js`, `anhang.js`, `modell.js`, `projekt.js` | Enter sendet, Umschalt+Enter Zeile, Stopp/Esc, `+`/`@` Datei anhängen (Stufe 6), Schild, Modell-Steuerung (Laden/Wechseln/Entladen, „passt es?“), Mikrofon (→ Einstellungen → Rekorder), `/` Befehle; Projektzeile mit „Ordner öffnen …“ und „Als Vorgabe merken“ |
| Vorschau | `.hs-vorschau` | `vorschau.js`, `vorschau.css` | Stufe 6: neben dem Gespräch die Datei, an der gearbeitet wird (Diff, Lauf-Log); Seite wechseln, zuklappen, festhalten (Strg+Umschalt+X) |
| Taskleiste | `.hs-taskleiste` | `taskleiste.js` | Start (Start-Menü), Läufe, Aufnahme-Knopf (`schnell.js`), Statusbereich aus `/api/strip` (HS-32), Uhr |
| Start-Menü | `.hs-start-menue` | `startmenue.js`, `startliste.js` (rein), `start_gruppen.json` | Apps mit Suche, Gruppen, zuletzt (`uix.shelf.harness`), Oberflächen, Darstellung · Schrift (Stufe 4) |
| App-Reiter | `.hs-app-box` | `app.js` | ein Werkzeug des Vertrags als Reiter `app:<typ>:<id>`, Nachweise rechts, Arbeitsstand (Stufe 4) |
| Einstellungen | `.hs-einst` | `einstellungen.js`, `einstellungen.css`, `katalog_editor.js`, `katalog_editor_pruefung.js` (rein), `erlaubnisse.js` | Reiter `einstellungen:[gruppe/punkt]`: sechs Gruppen, Werkzeuge eingehängt (`app.flaeche`), Katalog-Editor, Sitzungs-Erlaubnisse, Grenzen, Schalter – alles Schreiben als Antrag mit Gate (Stufe 5) |

`shell.js` hält den Zustand und registriert die Shell. Seit Stufe 4 steht `umschalter: menue` im Manifest (Vertrag N3): kein Alt+S-Chip, kein
Mini-Hub – Alt+S, der Knopf „Start“ und `/start` öffnen das Start-Menü der Shell; der Rekorder ist dort eine App.

## Wege

`/api/harness/projekte` (GET; POST = Antrag „Ordner öffnen“), `/api/harness/sitzungen[/<id>[/nachricht]]`, `/api/harness/antworten/<id>/strom|stopp`,
`/api/harness/vorgaben`, `/api/harness/modelle`, `/api/harness/dateien`, `/api/harness/vorschau` (harness/api.py, Kopf der Datei listet alle),
dazu `/api/strip`, `/api/models`, `/api/model/load|unload`. Der Strom einer Antwort wird mit `fetch` gelesen (Kopf `X-SEDRA-Shell`).

## Stufe 2 – Hände und Grenzen

Werkzeuge `datei_lesen`, `dateien_auflisten`, `suchen`, `datei_schreiben`, `datei_aendern`, `befehl` (harness/werkzeuge.py, befehl.py).
Jeder Aufruf: Vorbehalt → Freigabe-Katalog → Guard (harness/freigabe.py). `frei` läuft sofort; `verboten` bekommt das Modell als Grund;
`captain` erzeugt eine **Karte** im Verlauf (Diff oder Befehlszeile, Erlauben · Diff zeigen · Ablehnen) – dieselbe Karte steht im
Posteingang. Die Werkzeugzeile zeigt Stufe und Regel; das Schild im Eingabefeld zeigt den Katalog. „Diff zeigen“ öffnet den Diff als Reiter.

## Noch nicht da

Der Systemtext einer Vorlage (`.md`) ist in den Einstellungen nicht lesbar (kein Lese-Weg; die Datei liegt neben der Vorlage). Suche über Sitzungen,
Verlauf mit Werkzeugergebnissen und „Karte → Katalog“ sind eigene kleine Specs (Analyse 1.11. V4/V5/V7).

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
  Unten die anderen Oberflächen (Wechsel über `sedraWechsel.wechseln`, offene Apps gehen mit), ein Knopf „Darstellung und Schrift …“ (führt in die Einstellungen), „Gedächtnis leeren“.
- **App-Reiter** (`app.js`): `ctx.tools.forObject` → `ctx.makeContext` → `sedraLifecycle.mountTool` – derselbe Weg wie Cockpit und Minimal.
  `inhalt` in der Fläche, `nachweis` rechts zum Aufklappen; `shellApi.open(objekt)` öffnet oder aktiviert; höchstens 8 Apps (der älteste
  nicht aktive geht mit Satz zu); Objekte werden an `sedraStand` gemeldet und beim Start aus dem Arbeitsstand übernommen.
- **Statusbereich** (`taskleiste.js`, HS-32/43): Freigaben, Modell, GPU · RAM (eine Zelle: Temperatur mit Quelle, VRAM belegt/gesamt, thermischer Zustand, RAM), Modellserver, Scheduler, Zustand, Uhr – alles aus `/api/strip` (≤ alle 2 s). Zellen ohne Wert sind ausgeblendet; ein Klick öffnet die App.
- Reine Teile mit `node`: `tests/test_uix_harness_start.py`; Browser: `benchmarks/uix_check.py --shell harness`, `harness_abnahme.py --stufe4`.

## Stufe 5 (Version 1.5.0): Einstellungen und Katalog-Editor

- **Einstellungen** (`einstellungen.js`, HS-42): Reiter `einstellungen:` über den Knopf in der Seitenleiste, die Kachel „Einstellungen“ im Start-Menü,
  `/einstellungen [gruppe/punkt]` und die Zelle „Zustand“ (D-U6). Sechs Gruppen, 21 Punkte (G2 §3.1). Die meisten Punkte sind vorhandene
  Werkzeuge, eingehängt über `app.flaeche` (derselbe Weg wie der App-Reiter, nur auf das genannte Werkzeug beschränkt) – kein Nachbau (D-U1).
  Eigene Flächen: Darstellung, Benachrichtigungen (K9: Browser-Hinweis „eine Freigabe wartet“ nur nach Klick-Erlaubnis, Blinken an/aus),
  Vorlagen, Freigabe-Modus, Züge je Vorlage, Quelle, MCP (`GET /api/uix/clients`, nie der Token), Laufzeit, Schalter (`switch_request`).
- **Katalog-Editor** (`katalog_editor.js`, G2 §4): Tabelle aller Regeln mit Herkunft (Vorlage/Datei/neu), alle Felder bearbeitbar (D-U3);
  Vorlage-`verboten` gesperrt; Befunde live aus `katalog_editor_pruefung.js` (Fehler, Lockerung und weite Muster rot, Diff, YAML-Vorschau).
  Der Editor schreibt nie: „Antrag stellen“ → `POST /api/harness/katalog/antrag` (Art `harness_katalog`, `HARNESS_KATALOG_WRITE`, Bindung
  = Hash von Entwurf und Stand, Risiken = Befunde); erst „Freigeben und anwenden“ im Posteingang schreibt (`harness/antraege.py`: Stand
  verändert → `binding_stale`; Sicherung `.bak-<zeit>`; Audit `HARNESS_KATALOG_WRITTEN`). „Zurück zur Vorlage“ ist der Antrag `katalog/entfernen`.
- **Grenzen** (D-U4): `max_zuege` je Vorlage → `POST /api/harness/vorlagen/grenzen` (Art `harness_vorlage`) → Kopie nach
  `local_config/harness_vorlagen/`; die Datei im Repo bleibt. Herkunftsprüfung S7 auf allen drei Antrag-Wegen (403 aus einem Harness-Prozess).
- Reine Teile mit `node`: `tests/test_uix_harness_einstellungen.py`; Server: `tests/test_harness_katalog_editor.py`; Browser:
  `benchmarks/uix_check.py --shell harness` (Prüfung „einstellungen“), `harness_abnahme.py --stufe5`.

## Stufe 6 (Version 1.8.0): Dateien, Modell, Vorschau

- **Anhängen** (`anhang.js`, HS-82): `+` oder `@` öffnet die Dateiauswahl des Projekts (`GET /api/harness/dateien`, nur Namen, Einstufung wie `datei_lesen`;
  gesperrte Ordner erscheinen nicht); gewählte Dateien stehen als `@pfad` im Text, das Modell liest sie mit `datei_lesen`.
- **Modell im Eingabebereich** (`modell.js`, HS-80/81): Rezept wählen, Laden/Wechseln/Entladen – dieselben Wege wie die Werkstatt.
- **Vorschau** (`vorschau.js`): die Datei, an der gearbeitet wird, neben dem Gespräch; folgt den Werkzeugaufrufen, lässt sich festhalten.

## Bau 1.11.2026 (Version 1.9.0): Analyse + Harness-Vergleich

- **Sitzungs-Erlaubnis** (P0 M1, `harness/erlaubnis.py`, `erlaubnisse.js`): Knopf „Für diese Sitzung erlauben“ auf der Karte (`POST karten/<id> {weg: sitzung}`) –
  gleichartige Aufrufe (Ordner der Datei, Anfang des Befehls) laufen bis zum Schließen der Sitzung ohne Karte (Audit `HARNESS_APPROVED_BY sitzung:<karte>`);
  nie bei Vorbehalt, Warnkarte, Modellen. Liste und „Zurücknehmen“ unter Einstellungen → Agent → Freigabe-Modus. Vorlage: `${schreibbereich}`-Regel frei,
  Testbefehle (`python -m unittest*`, `pytest*`) frei.
- **Modell halten / Auto-Laden** (P0 M2): laufende Antworten, offene Karten und 60 s Nachlauf halten das Modell (`JobSupervisor.in_use_extra`);
  ohne Modell lädt die Shell beim Senden das Standard-Rezept selbst – nur wenn der Katalog `modell_laden` dafür `frei` stellt (`GET vorgaben`).
- **Ordner öffnen / Vorgaben** (P0 M3, `projekt.js`): Antrag `harness_projekt` → Laufzeitdatei `runtime_data/harness/projekte.yaml` (nie `local_config/`),
  kein Neustart; „Als Vorgabe merken“ für Projekt und Rezept (`POST vorgaben`).
- **„Passt das Modell?“** (V1, `GET modelle`): je Rezept Bedarf gegen freien Speicher mit Grund, passende zuerst. **Erststart-Schritte** (V2) in der leeren
  Sitzung; **Zeitlinie** (V3) im Reiter („denkt · 12 s“, „Werkzeug befehl“, „wartet auf Freigabe“, „Stopp angefordert“); Fehlerzeile mit „Logbuch öffnen“ (V9).
- Befunde A1–A30 der Analyse (Antwort nie hängend, Herkunft S7 auf allen Schreibwegen, Mikrofon, Seitenleiste, Status-Takt, Sitzungsliste mit Zwischenspeicher …):
  `docs/BAUBERICHT_HARNESS_BAU_2026-11-01.md`; Tests `tests/test_harness_bau_2026_11_01.py`.

## Kontextmenü und Module (05.11.2026)

Rechtsklick auf etwas in der Harness öffnet ein Menü innerhalb von Sedra (`kontext.js`, `kontext.css`). Jedes Modul der Oberfläche meldet sich mit `root.sedraHarness.kontext.registrieren({id, titel, selektor, dateien, eintraege?})` an: Name im Menü, Selektor, an dem man es erkennt, die Dateien, in denen es lebt, und optional eigene Einträge (`eintraege(S, element)` → `[{text, tun}]`). Die Tabelle der bestehenden Module steht in `kontextmodule.js`; ein neues Modul trägt sich in seiner eigenen Datei ein.

Das Menü nennt den Ort („Sedra Harness › Taskleiste › Statuszelle“) und bietet: die Einträge des Moduls, **Im Chat anpassen …** (legt Ort, Modul, Dateien und den sichtbaren Text als Entwurf ins Eingabefeld, der Captain schreibt dazu, was anders sein soll; ohne Gespräch öffnet sich ein neues), **Frage dazu stellen**, Kopieren, Aus Zwischenablage einfügen, Neues Gespräch, Datei anhängen. Umschalt+Rechtsklick und Eingabefelder behalten das Menü des Browsers (wie bei herdr; die Einträge „Neuer Chat“ und „Dokument öffnen“ stammen aus dem Desktop-Menü der alten Oberfläche). Texte kommen nur als `textContent` in die Oberfläche. Test: `tests/test_uix_harness_kontext.py`.

## Desktop Builder und Profile (05.11.2026)

Start → System → **Desktop Builder** (`builder.js`, `desktop.js`, Server `harness/desktop.py`, `GET/POST /api/harness/desktop`): vier Reiter – **Module** (die Landkarte der Oberfläche aus `kontext.js`), **Start-Menü** (Apps aus- und einblenden, Gruppe wählen), **Taskleiste** (Zellen aus- und einblenden, Reihenfolge) und **Profile und Marke** (Name, Akzentfarbe, Profile je Auftraggeber speichern, anwenden, exportieren, importieren). Leer heißt die Vorgabe der Shell (`start_gruppen.json`). Posteingang, Aufgaben und die Zelle Freigaben lassen sich nie ausblenden (Client und Server prüfen es). Ein Profil ist nur Zuschnitt der Oberfläche, keine Sperre; Rechte sind Sache der Richtlinie (Stufe 4). Entwurf und Ablauf für einen neuen Auftraggeber: `docs/ENTWURF_AUFTRAGGEBER_PROFILE_2026-11-05.md`. **Layout (Baukasten und Raster)**, Reiter *Layout*: `bausteine.js` (Tabelle der Bausteine, Klemmen ins Raster, Anwenden), `layouteditor.js` (die **Bühne**: verkleinertes Abbild der leeren Sitzung mit Rahmen und grünen Hilfslinien; Bausteine ziehen, Größe an der Ecke, Pfeiltasten, Chips der Leisten per Ziehen tauschen oder mit dem Kreuz ausblenden, darunter die genauen Zahlen). Teile mit `data-baustein` in `eingabe.js`, `projekt.js`, `verlauf.js` (`startbild`) und `startmenue.js` (Abschnitte und Kacheln des Start-Menüs). **Seitenaufbau** (`layout.zonen`, `bausteine.js` `zonenAnwenden`, CSS in `kontext.css`): Seitenleiste links/rechts, Taskleiste unten/oben, Eingabefeld unten/oben, Breiten in Pixel; die Klassen `hs-seite-rechts`, `hs-leiste-oben`, `hs-eingabe-oben` und die Variablen `--hs-seite-w`, `--hs-eingabe-w` stehen auf `#sedra-root`. Tests: `tests/test_harness_desktop.py`, `tests/test_uix_harness_desktop.py`, `tests/test_uix_harness_bausteine.py`.

## Belohnungssystem (05.11.2026)

Ein Lobwort („danke“, „das hast du gut gemacht“, „perfekt“) direkt nach einer Antwort merkt sie als **gute Antwort** (★, bei „perfekt“ und ähnlichen ★★): Eintrag in der Sitzung, Tagesdatei unter `runtime_data/harness/belohnungen/` für die Wissensdatenbank, bei Code mit den geänderten Dateien. Server `harness/belohnung.py`, Wörter `config/belohnung.yaml` (eigene in `local_config/belohnung.yaml`), Anzeige `verlauf.js` (`lobZeichen`, `lobMarkieren`) und Info-Seite (`infoseite.js`). Entwurf, Hermes-Vergleich und Stufen L2 bis L4: `docs/ENTWURF_BELOHNUNG_UND_LERNEN_2026-11-05.md`. Test: `tests/test_harness_belohnung.py`.
