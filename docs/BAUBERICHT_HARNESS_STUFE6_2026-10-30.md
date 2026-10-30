# Baubericht Harness-Shell Stufe 6 (30.10.2026): Zweck der Aufgaben, Projekte erklärt, Vorschau im Reiter

Spec: `SPEC_HARNESS_SHELL_v1_STUFE6_G1.md`, `…_G2.md`, `SPEC_HARNESS_SHELL_v1_G3_STUFE6.md`. Branch `harness/stufe-6` auf `main` (`8941601`), kein Push. Baut: Claude allein.

## Teil A (N1 bis N3): gebaut

| Nr | Ergebnis |
|---|---|
| N1 | `aufgabe.py`: `zweck` Pflicht (1 bis 160 Zeichen, `zweck_fehlt` / `zweck_zu_lang`), in der Aufgabe gespeichert und nie für die Deckung gelesen; `klartext(erlaubt, lauf_namen)` fest aus einer Tabelle, höchstens 4 Satzteile, dann „und n weitere“; `oeffentlich` liefert `klartext` und `zweck_anzeige` (alte Aufgaben ohne Zweck zeigen den Klartext). |
| N2 | `vorarbeiter.py`: `aufgabe_vorschlagen` mit `zweck` (im Schema Pflicht, durchgereicht); `api.py`: Vorschau der Vorschlag-Karte nennt Zweck und Klartext, `GET`/`POST aufgaben` liefern den Klartext mit den Namen der Lauf-Typen (`_lauf_namen`). |
| N3 | `aufgabe.js` (198 Zeilen): Formular mit Zweckfeld an erster Stelle (Zähler, Beispiel, Satz zur Bedeutung der Freigabe); Karten zeigen Titel, Zweck, „Darf: …“, Rest, darunter einklappbar „Technische Muster“; Vorschlag-Karte zeigt den Zweck. `shell.css` (387 Zeilen) vier Regeln. |

## Prüfung (ohne Modell, ohne Browser)

`scheduler desk orchestra uix harness`: **1343 Tests, 14 übersprungen, 0 rot** (vorher 1339; vier neue Tests: Pflicht und Grenze, Klartext, alte Aufgabe, Zweck deckt nichts). Bestehende Tests und `harness_abnahme.py` (S3-C) tragen jetzt einen Zweck. `node --check aufgabe.js` ok.

**Nicht geprüft:** die Oberfläche im Browser (Playwright fehlt in der `.venv`), `uix_check`; das sieht der Captain im Cockpit. Ein einzelner Lauf zeigte einmal `PermissionError` beim Aufräumen eines temporären Ordners (`test_harness_lauf`, Windows hält die Ausgabe-Datei), im Wiederholungslauf grün.

## Teil B (N4): gebaut

`seite.js` (188 Zeilen): Kopfzeile der Gruppe Projekte mit Erklärsatz und „?“ (Hilfe-Karte mit vier Zeilen, Esc schließt); Leerzustand eines Projekts mit Knopf „Neue Sitzung starten“; Tooltip des Projektnamens mit Pfad, Zahl der Sitzungen, Vorarbeiter und aktiven Aufgaben; Sitzungen älter als 7 Tage stehen in `<details>` „Ältere Sitzungen (n)“ (Zustand je Projekt im Browser, die aktive Sitzung, Vorarbeiter-Sitzungen und laufende bleiben oben). Nichts wird gelöscht oder verschoben.

## Teil C (N5 bis N7): gebaut

| Nr | Ergebnis |
|---|---|
| N5 | `harness/vorschau.py` (neu) und `GET /api/harness/vorschau?sitzung=&pfad=` in `api.py`: nur Lesen; Pfad relativ, ohne `..`, im Projekt (auch gegen Verknüpfungen); der Pfad muss im Verlauf der Sitzung als Ziel von `datei_lesen/-schreiben/-aendern` stehen; Einstufung wie bei `datei_lesen` (Katalog `verboten` oder fester Vorbehalt → `gesperrt`, kein Inhalt); höchstens 200 KB und 600 Zeilen, Binärdateien nur mit Größe. Tests: `test_harness_vorschau.py` (rein, 6) und `test_uix_harness_vorschau.py` (mit Server, 4). |
| N6 | `vorschau.js` (180 Zeilen): Fläche je Sitzungsreiter mit Gespräch und Vorschau; die Vorschau folgt aus den vorhandenen Ereignissen der Datei (`werkzeug.start/-ende`, auch beim Öffnen eines Reiters die zuletzt berührte Datei), der Freigabe-Karte (`karte`) und dem Lauf (`harness.lauf`); Anzeige nur als Text (Markdown über `markdown.js`); Festhalten (📌, auch Klick auf „▸ Vorschau“ an einer Werkzeugzeile mit Datei), das Objekt bleibt nach dem Neuladen. |
| N7 | `shell.js`: ein Sitzungsreiter wird in `div.hs-teilung` gelegt (Gespräch rechts, Vorschau links, 50/50, Trennbalken mit Maus und Pfeiltasten, mindestens 420 px je Seite); Knöpfe Tauschen (⇄ und Strg+Umschalt+X) und Zuklappen (✕, dann „Vorschau“-Knopf oben rechts im Gespräch); ohne Objekt keine Vorschau (leere Sitzung wie bisher, beim ersten Objekt ein Hinweis); unter 1100 px eine Fläche mit Umschalter „Gespräch | Vorschau“. Zustand je Sitzung im Browser (`sedra.harness.vorschau`). `vorschau.css` (neu, 24 Zeilen; `shell.css` bleibt bei 388), `shell.yaml` 1.6.0. |

## Prüfung (ohne Modell, ohne Browser)

`scheduler desk orchestra uix harness`: **1353 Tests, 15 übersprungen**, außer einem Test 0 rot (zuvor 1343; zehn neue Tests der Vorschau). Der eine rote Test, `test_harness_lauf … test_abbruch_durch_aufgabe_hat_einen_eigenen_status`, scheitert am Aufräumen eines Ordners (`PermissionError`: die Hülle des Laufs hält `ausgabe.log` noch), auch auf `main` allein gelaufen – nicht durch Stufe 6 verursacht, aber nicht behoben. `node --check` für `aufgabe.js`, `seite.js`, `vorschau.js`, `verlauf.js`, `shell.js` ok; ein Rauchtest von `vorschau.js` gegen ein Minimal-DOM (Objekt folgt, Tauschen, Pin, Merken, schmal) lief ohne Fehler.

**Nicht geprüft:** das Aussehen und Verhalten im echten Browser (Playwright fehlt in der `.venv`, Installation nur nach Ja); `uix_check`, `harness_abnahme_stufe6.py` (N8) und Bilder fehlen deshalb. Das prüft der Captain im Cockpit.

## Offen

N8 (Abnahmeskript mit Browser, Bilder) nach Installation von Playwright; Abnahme am PC durch den Captain; Merge nach `main` erst auf sein Ja.
