# Solo-Workflow des Coders (Standard seit 2026-10-10)

Entscheidung des Captains nach den Messungen vom 2026-10-09: Qwen3.6-35B-A3B baut allein, ein Entwickler pro Aufgabe.

## Ablauf je Stufe
1. **Ein Entwickler** (`solo`) liest die Aufgabe einmal und baut. Er ist zugleich sein eigener Prüfer: Er schreibt ein kleines `check_*.py`, lässt es mit `run_python` in der microVM laufen und korrigiert (höchstens 8 VM-Läufe, 80 Aufrufe, 45 Runden, 20 Minuten). Lange Dateien schreibt er in Teilen (`write_file`, dann `append_file`).
2. **Keine eigenen Tests**: Die Aufgabe verliert die Pflicht, Tests zu schreiben (`--no-own-tests`, automatisch im Modus solo). Die `check_*.py` werden danach aufgeräumt.
3. **Aufräumen** (`tidy`): Kommentare und Docstrings werden gesichert (Kommentar-Archiv) und entfernt, neue Hilfsdateien gelöscht.
4. **Der versteckte Abnahmetest urteilt** (unabhängig, in der microVM).
5. **Fehlschlag → Nacharbeit beim selben Entwickler**, bis zu 3-mal: Er setzt sein Gespräch fort (gekürzt, `compact_history`) und bekommt einen Fehlerbericht (was der Test erwartet, was die Arbeit liefert, erste 2 Fehler). Ist das Gespräch weg (Serverfehler), startet er frisch aus Aufgabe und Bericht.

## Aufruf
`devvm_build.py <spec>` nutzt jetzt `--mode solo` mit `--rework 3 --hidden-feedback --tidy --no-own-tests`. Andere Modi: `--mode escalating|pipeline|delegating` (dann Rework 0, sofern nicht gesetzt).

## Messwerte
| Test | solo | escalating |
|---|---|---|
| Standardtest (2 Läufe) | 4/4, 197 s und 274 s | 4/4, 370 s und 353 s |
| am009 Sammler | 3/3 in 707 s, 24.050 Token | 3/3 in 2206 s, 74.321 Token |
| am009, Qwen3-Coder (alter Lauf) | | 0/3 in 7362 s |

Grenzen: je Modus nur 1 bis 2 Läufe; der Test am009 ist mittelschwer. Prüfer aus dem Modell sind unzuverlässig (Prüfer-Test: 0/4 brauchbar bei beiden Modellen), deshalb urteilt allein der versteckte Test.

## Schritt-Plan (`--plan-steps`, Option, Stand 2026-10-10)
Der Planer (gleiches Modell, nur Lesewerkzeuge und `outline`) teilt eine lange Stufe in 1 bis 4 Schritte; jeder Schritt wird in einer **neuen, kurzen Unterhaltung** gebaut. Damit nichts verloren geht:
1. **Wörtliche Auszüge:** Die Aufgabe wird in nummerierte Einheiten geschnitten (Zeile oder Satzgruppe, höchstens etwa 450 Zeichen, der Text bleibt unverändert). Der Planer ordnet jedem Schritt Einheiten zu; der Entwickler bekommt genau diese **wörtlich**. Einheiten, die kein Schritt beansprucht (allgemeine Regeln wie der Stil), gehen an **jeden** Schritt; ein Schritt ohne gültige Nummern bekommt die ganze Aufgabe.
2. **Schnittstellen:** Je Schritt eine Zeile (Namen, Argumente, Ergebnisse), alle Schritte sehen den ganzen Plan mit diesen Zeilen.
3. **Übergabenotiz:** Die Abschlusszeile (`submit_result`) jedes Schritts steht im nächsten.
4. **Karte des Arbeitsbereichs:** Klassen und Funktionen aller Python-Dateien im Wurzelordner mit Zeilennummern (höchstens 3000 Zeichen).
5. **Zwang zum Teilen:** Über 1800 Zeichen Aufgabentext muss der Planer in mindestens zwei Schritte schneiden (an natürlichen Nahtstellen); darunter bleibt ein Schritt erlaubt (dann wie normaler Solo-Modus).
Die Prüfskripte des Planers werden nicht benutzt; es urteilt nur der versteckte Test. Bei einem Fehlschlag setzt der Entwickler des **letzten Schritts** fort (Fehlerbericht plus vollständige Aufgabe).

### Optionen zum Ausarbeiten
- **`--step-syntax-check`** (Option 6): Nach jedem Schritt wird jede Python-Datei im Wurzelordner geparst; eine Datei, die nicht parst, geht höchstens zweimal an denselben Entwickler zurück (Gespräch gekürzt fortgesetzt). Idee dahinter: Ein halber Umbau wie `NameError: _match` (am007, Stufe `all`) fiele sofort auf. *Zu klären:* nur Syntax oder auch Importfehler und nicht definierte Namen (`python -m py_compile` reicht dafür nicht; ein `pyflakes`-artiger Lauf in der microVM wäre nötig); Dateien in Unterordnern (`tests/`) fehlen noch; was passiert, wenn ein Schritt absichtlich eine Datei halb lässt.
- **`--fresh-rework`** (Option 7): Die Nacharbeit startet eine **neue** Unterhaltung (vollständige Aufgabe, Karte des Arbeitsbereichs, Fehlerbericht) statt das alte Gespräch fortzusetzen. Vorteil: kurz, kein Ballast, kein Hängenbleiben an einer falschen Idee. Nachteil: der Entwickler weiß nicht mehr, was er schon probiert hat. *Zu klären:* ob man dem neuen Gespräch eine Notiz „bisher versucht" aus den Übergabenotizen mitgibt; ob es besser ist, nur beim zweiten Fehlschlag zu wechseln (erst fortsetzen, dann frisch); Messung am007 und am009 mit und ohne.
- Weitere Ideen: Nachplanen nach einem Fehlschlag (der Planer sieht den Bericht und schneidet den Rest neu); Schritte parallel, wenn sie getrennte Dateien betreffen (braucht zwei Server, 11,5 GB reichen nicht).

## Abnahmetests schreiben, damit die Nacharbeit etwas damit anfangen kann
Der Entwickler sieht den versteckten Test nicht, nur den Fehlerbericht (`devvm_evidence.bug_report`): die ersten zwei falschen Prüfungen mit Zeile, erwartetem und geliefertem Wert. Der Treiber zerlegt seit 2026-10-10 auch verkettete Bedingungen (`assert a == 1 and b == 2 and ...`) und nennt den **ersten falschen Teil** mit beiden Werten (bei `==` erwartet/geliefert, bei `in`, `is`, `!=` linke und rechte Seite). Trotzdem gilt für **neue** Tests:
1. **Eine Prüfung pro `assert`**, besser mehrere kurze als eine Kette (der Bericht zeigt dann auch die weiteren falschen Prüfungen, nicht nur die erste einer Kette).
2. **Vergleiche mit `==`** statt `is`/`in`, wo es geht: nur dort steht der erwartete Wert eindeutig im Bericht.
3. Die Prüfung `chained_asserts(text)` in `devvm_evidence` listet Ketten mit drei oder mehr Teilen. Bestand (Stand 2026-10-10, Ketten mit mindestens drei Teilen): am002 9, am003 6, am004 16, am005 18, am006 0, am007 20, am008 12, am009 2, am010 6. **Bestehende Tests werden nicht umgeschrieben**, damit die Läufe vom 2026-10-09 und 2026-10-10 vergleichbar bleiben; das gilt erst für neue Specs.

## Umfang der Selbstprüfung (`--self-check`, Option, Stand 2026-10-10)
Auf Anregung des Captains ("vielleicht sind unsere zusätzlichen Prüfschritte zu aufwendig und zu oft eingesetzt") ist der Umfang der Selbstprüfung des Solo-Entwicklers wählbar: `full` (Standard, wie bisher: ein `check_*.py`, bis 8 VM-Läufe), `light` (ein kleines `check_*.py`, höchstens 2 VM-Läufe, eine Prüfung nicht debuggen, bei Widerspruch der Aufgabe vertrauen), `none` (`run_python` und `run_tests` entfallen, er liest die Aufgabe gegen seinen Code). Messung über die Standardtest-Modi `solo`, `solo-light`, `solo-none` (Optionsdatei `probe_stdbench`: `"modes"`, bis 4). Ergebnis offen.

## Von little-coder übernommen (2026-10-10)
1. `write_file` lehnt das Ersetzen einer bestehenden Datei von mehr als 10 Zeilen ab (mit fertigem `edit_file`-Beispiel; ganze Datei ersetzen: erst `delete_file`).
2. `edit_file` nimmt bis zu 8 Änderungen je Aufruf (`edits`), alle gegen den aktuellen Dateistand gesucht, nichts wird geschrieben, wenn eine nicht passt oder sich überlappt.
3. Bei einer Schleife (`loop`) oder einer sich wiederholenden Antwort (`runaway`) gibt es **eine** Korrekturnachricht (bei `runaway` wird die Antwort verworfen und nach dem Abbruchpfad neu gefragt), erst danach endet der Lauf.
