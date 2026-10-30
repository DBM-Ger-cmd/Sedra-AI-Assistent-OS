# SPEC Harness-Shell Stufe 6 – G3 Bau-Aufgaben (30.10.2026)

G2 freigegeben vom Captain 30.10.2026 (D-S1 bis D-S5 wie vorgeschlagen). Baut: **Claude allein**, Branch `harness/stufe-6` (Worktree), kein Push. Je Teil eine Abnahme (D-S5).

| Nr | Teil | Aufgabe | Dateien | Fertig wenn |
|---|---|---|---|---|
| N1 | A | `zweck` (Pflicht, ≤ 160), `klartext`, `oeffentlich` | `harness/aufgabe.py` | Tests Zweck, Klartext, alte Aufgabe, Zweck deckt nichts |
| N2 | A | Wege: `zweck` in Schema und Karte des Vorschlags, Klartext in `GET aufgaben` | `harness/vorarbeiter.py`, `harness/api.py` | Tests der Wege |
| N3 | A | Oberfläche: Zweckfeld, Zweckzeile, „Darf“, Muster einklappbar | `uix/shells/harness/aufgabe.js`, `shell.css` | `uix_check` (Browser) |
| N4 | B | Projekte erklärt: Kopfzeile, „?“-Hilfe, Leerzustand, Tooltip, ältere Sitzungen einklappen | `seite.js`, `shell.css` | `uix_check` |
| N5 | C | Lese-Weg `GET /api/harness/vorschau` mit Regeln von `datei_lesen` | `harness/api.py` | `test_harness_vorschau.py` |
| N6 | C | `vorschau.js`: Folgen des Objekts, Anzeige, Pin | `uix/shells/harness/vorschau.js`, `verlauf.js` | Tests |
| N7 | C | Aufbau im Reiter: zwei Hälften, Tauschen, Zuklappen, Trennbalken, unter 1100 px eine Fläche | `shell.js`, `reiter.js`, `shell.css` | `uix_check` bei 1024×700 und 1400×860 |
| N8 | C | Abnahme ohne Modell, Bericht | `benchmarks/harness_abnahme_stufe6.py`, Bericht | Bericht mit Belegen |

Berechtigungen: P6-1 bis P6-5 (G1 §5, G2 §6). Nicht: Modelle, Läufe mit Modell, `local_config/`, Löschen, Push, Installation von Playwright ohne Ja.
