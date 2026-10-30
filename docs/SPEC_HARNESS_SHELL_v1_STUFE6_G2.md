# SPEC Harness-Shell Stufe 6 – G2 Design: Zweck der Aufgaben, Projekte erklärt, Vorschau im Reiter (30.10.2026)

Grundlage: `SPEC_HARNESS_SHELL_v1_STUFE6_G1.md` (G1 freigegeben vom Captain 30.10.2026: HQ-1 bis HQ-5 wie vorgeschlagen). Nichts gebaut; diese Datei ist G2.

## 1. Teil A – Zweck und Klartext der Aufgaben (HS-60 bis HS-64)

**Daten.** `harness/aufgabe.py`: `pruefen_neu` nimmt `zweck` (Text, getrimmt, 1 bis 160 Zeichen; sonst `zweck_fehlt` bzw. `zweck_zu_lang`) und legt es in die Aufgabe (`zweck`). Es ist **Anzeige**: `aufgabe_deckung.deckt` und `Aufgaben.deckt` lesen es nie. Alte Dateien ohne `zweck` bleiben gültig (kein Zwang beim Laden, nichts wird nachgeschrieben).

**Klartext.** Neue reine Funktion `aufgabe.klartext(erlaubt)` → ein Satz „Darf: …“, ohne Modell, aus einer festen Tabelle:

| Werkzeug | Satzteil |
|---|---|
| `datei_lesen`, `dateien_auflisten`, `suchen` | „Dateien lesen“ (mit Muster in Klammern, wenn nicht `**`) |
| `datei_schreiben` | „Dateien neu schreiben in <Muster>“ |
| `datei_aendern` | „Dateien ändern in <Muster>“ |
| `befehl` | „Befehl ausführen: <Muster>“ |
| `lauf_starten` | „Lauf <ID> starten“ (Namen aus `harness_laeufe.yaml`, sonst die ID) |
| `lauf_stoppen`, `modell_laden`, `modell_entladen` | „Lauf stoppen“, „Modell laden“, „Modell entladen“ |

Gleiche Werkzeuge werden zusammengefasst, höchstens 4 Satzteile, dann „und n weitere“. `oeffentlich(a)` fügt `klartext` hinzu (immer berechnet, nie gespeichert); fehlt der Zweck, liefert es `zweck_anzeige = klartext` (HS-62).

**Wege.** `POST aufgaben` und der Vorschlag des Vorarbeiters (`aufgabe_vorschlagen`, Schema in `vorarbeiter.py`) bekommen das Feld `zweck` (im Schema Pflicht). Die Vorschlag-Karte trägt es in `args`. Die Werkzeugzeile bei Deckung (HS-63) nennt `aufgabe:T-…` schon; die Klartext-Zeile kommt aus `GET aufgaben` (Cache im Verlauf: `aufgabe_zweck[<id>]`), kein neuer Weg.

**Oberfläche.** `aufgabe.js`: Formular mit Feld Zweck an erster Stelle (Platzhalter „z. B. Testläufe der Gruppe harness starten und das Ergebnis lesen“, Zähler 0/160) und einem Satz „Freigabe heißt: Innerhalb dieser Liste arbeitet der Agent ohne Karte.“; Karten (aktiv, vorgeschlagen, beendet) zeigen in dieser Reihenfolge: Titel · **Zweck** (oder Klartext) · „Darf: …“ · Rest an Aufrufen und Zeit · `<details>` „Technische Muster“ (die heutige Liste). Daten werden nie zu HTML (`sedraDom`).

## 2. Teil B – Projekte erklärt (HS-65 bis HS-67)

`seite.js`: Kopfzeile der Gruppe Projekte mit dem Satz aus HS-65 und einem „?“-Knopf, der eine Hilfe-Karte (Popover, schließt mit Esc) öffnet: vier Zeilen (Was ist ein Projekt · Sitzung anlegen · Flagge/Vorarbeiter · wo die Aufgaben stehen). Leerzustand eines Projekts: eine Zeile mit dem Knopf „Neue Sitzung“ (nutzt die vorhandene `neu`-Funktion). Die Tooltip-Zeile des Projektnamens: „<n> Sitzungen · Vorarbeiter: <Titel> · <m> offene Aufgaben“ (aus `S.sitzungen`, `S.vorarbeiter`, `S.aufgaben`; kein neuer Weg). Sitzungen mit `zuletzt` älter als 7 Tage stehen in `<details>` „Ältere Sitzungen (n)“, Zustand je Projekt in `sedra.harness.projekte.zu`-Schlüssel `alt:<projekt>`; die aktive Sitzung und Sitzungen mit Vorlage `vorarbeiter` bleiben immer oben. Löschen unverändert nur nach Nachfrage (HS-18).

## 3. Teil C – Vorschau neben dem Gespräch (HS-70 bis HS-75)

**Aufbau.** Neue Datei `uix/shells/harness/vorschau.js` (Ziel ≤ 250 Zeilen). `shell.js` verpackt die Ansicht eines Sitzungsreiters in `div.hs-flaeche` mit zwei Kindern: `.hs-fl-gespraech` (die bisherige `verlauf`-Ansicht, unverändert) und `.hs-fl-vorschau`. Auswahl durch CSS `grid-template-columns` (`--vs-links`, Voreinstellung 50 %); Reihenfolge Gespräch rechts, Vorschau links (HQ-3), Tauschen setzt `order` und ändert nichts am Dokument. Der Trennbalken (`role=separator`, Pfeiltasten ±5 %) ist ziehbar; je Fläche mindestens 420 px.

**Zustand je Reiter** (nur Browser, localStorage `sedra.harness.vorschau`, nie Inhalt): `{seite: 'links'|'rechts', offen: bool, pin: null | {typ, ref}, breite}`. Unter 1100 px: nur eine Fläche, Umschalter „Gespräch | Vorschau“ in der Reiterzeile (HS-74).

**Was die Vorschau folgt (HS-71).** Aus Ereignissen, die es schon gibt – kein Polling:

| Auslöser (Strom der Sitzung / Bus) | Vorschau zeigt | Quelle des Inhalts |
|---|---|---|
| `werkzeug.ende` mit `datei_schreiben` oder `datei_aendern` (`args.pfad`) | die Datei; bei `datei_aendern` der Diff aus der Karten-Vorschau | neuer Lese-Weg (unten) |
| Ereignis `harness.karte` (offene Karte dieser Sitzung) | die Karte mit ihrer Vorschau (Vorschau-Text steht schon in der Karte, kein Datei-Lesen) | `GET karten/<id>` |
| Ereignis `harness.lauf` eines Laufs dieser Sitzung | Fortschritt und letzte Zeilen der Ausgabe (der Lauf-Reiter in klein) | `GET laeufe` (vorhanden) |
| geöffnete App (`app:`) oder Seite | wird **nicht** eingebettet; die Vorschau zeigt einen Verweis „im Reiter öffnen“ | – |

Nach jedem Auslöser wird das jüngste Objekt gezeigt, solange kein Pin gesetzt ist. Die Kopfzeile nennt Objekt und Grund („Datei docs/x.md – eben geändert“). Pin (HS-72): Klick auf die Reißnadel oder auf eine Werkzeugzeile/einen Dateinamen im Gespräch; ein erneuter Klick löst ihn.

**Lese-Weg (neu, einziger Serverteil).** `GET /api/harness/vorschau?sitzung=S-…&pfad=<relativ>`: liest die Datei **mit denselben Regeln wie das Werkzeug `datei_lesen`** (`werkzeuge._lesen`: Projektwurzel, kein `..`, Vorbehalte und Sperrliste greifen; gesperrte Datei → `{status: 'gesperrt'}`, die Vorschau zeigt „nicht anzeigbar“). Höchstens 200 KB / 600 Zeilen, Rest abgeschnitten mit Vermerk; Binärdateien nur als „Binärdatei, n Bytes“. **Nur Lesen**, kein Schreiben, kein Token in der Antwort. Der Pfad muss in der Verlaufszeile der Sitzung als Ziel eines Werkzeugs vorkommen (kein freies Durchsuchen des Projekts über diesen Weg). Der Weg steht im `WEG`-Muster, nicht im `GESCHUETZT`-Muster (Lesen ohne Herkunftsprüfung wie `GET sitzungen`).

**Anzeige.** Text und Diff werden als Text gezeichnet (`textContent`, nie HTML); Markdown-Dateien rendert `markdown.js` wie im Gespräch. Fremder Dateitext ist Daten, keine Anweisung (wie die Ausgabe der Läufe).

**Leere Sitzung (HS-75).** Ohne Objekt bleibt die Vorschau zu; mit dem ersten Objekt klappt sie auf und zeigt einmal „Hier erscheint, woran ich arbeite“. Zwei Reiter derselben Sitzung gibt es schon heute nicht (Reiter = Sitzung).

## 4. Dateien und Tests

| Datei | Änderung |
|---|---|
| `harness/aufgabe.py` | `zweck`, `klartext`, `oeffentlich` (neu) |
| `harness/vorarbeiter.py`, `harness/api.py` | Schema `zweck`; `GET vorschau` (neu) |
| `uix/shells/harness/aufgabe.js`, `seite.js`, `shell.js`, `shell.css`, `reiter.js` (Umschalter), `verlauf.js` (Klick auf Werkzeugzeile → Pin), neu `vorschau.js` | Oberfläche |
| `tests/test_harness_aufgabe.py` (+), neu `test_harness_vorschau.py`, `test_uix_harness_vorschau.py` | Prüfungen unten |
| `benchmarks/harness_abnahme_stufe6.py`, `uix_check.py` (Profil harness) | Abnahme ohne Modell |

Prüfungen: Zweck Pflicht/zu lang/alt ohne Zweck; Klartext je Werkzeug und Kürzung; Zweck deckt nichts (Aufruf ohne passendes `erlaubt` bleibt Karte); Vorschlag ohne Zweck abgelehnt; `GET vorschau`: Datei, Diff, gesperrt, zu groß, Pfad nicht aus dem Verlauf, `..`; Browser (Playwright, **Paket fehlt in der `.venv`: Installation nur nach Ja**): zwei Hälften, Tauschen, Zuklappen, Pin, unter 1100 px eine Fläche, 1024×700 ohne waagerechtes Rollen, Projekte-Hilfe und Leerzustand, Zweckzeile in der Karte. Alle Shell-Dateien bleiben ≤ 400 Zeilen (Vertrag).

## 5. Entscheidungen des Captains (offen)

| Nr | Frage | Vorschlag |
|---|---|---|
| D-S1 | Vorschau liest Dateien über einen neuen Lese-Weg mit den Regeln von `datei_lesen`, nur für Pfade aus dem Verlauf der Sitzung | ja |
| D-S2 | Apps und Seiten nicht einbetten (Verweis), nur Dateien, Diffs, Karten, Läufe | ja |
| D-S3 | Klartext aus fester Tabelle, nie von einem Modell erzeugt | ja |
| D-S4 | Zweck-Pflicht auch für Vorschläge des Vorarbeiters (Schema) | ja |
| D-S5 | Bau durch Claude allein (reine Anzeige, kein SEDRA-Bau), Reihenfolge Teil A, B, dann C mit je einer Abnahme | ja |

## 6. Berechtigungen vorab

Wie G1 §5 (P6-1 bis P6-4) plus: **P6-5** neuer Lese-Weg `GET /api/harness/vorschau` in `harness/api.py` (nur Lesen, mit den Vorbehalten von `datei_lesen`). Nicht enthalten: Modelle, Läufe mit Modell, `local_config/`, Löschen, Push, Installation von Playwright ohne Ja.

## 7. Nächste Gates

- **G2** (diese Datei): Captain beantwortet D-S1 bis D-S5.
- **G3** Bau-Aufgaben S6-N1 bis S6-N8 (Teil A: N1 Daten und Klartext, N2 Wege, N3 Oberfläche; Teil B: N4; Teil C: N5 Lese-Weg, N6 `vorschau.js`, N7 Reiter, Umschalter, Pin, N8 Abnahme und Bericht), dann **G4** Abnahme am PC.
