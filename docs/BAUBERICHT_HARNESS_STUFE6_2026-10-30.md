# Baubericht Harness-Shell Stufe 6 (30.10.2026), Teil A: Zweck und Klartext der Aufgaben

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

## Offen

Teil B (Projekte, N4) und Teil C (Vorschau, N5 bis N8) stehen aus; je Teil eine Abnahme.
