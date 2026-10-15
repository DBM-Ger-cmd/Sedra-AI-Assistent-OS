# Analyse: GUPPIs Modell in Cline (VS Code) gegen den DevVM-Bau, 2026-10-09

Aufgabe in beiden Fällen: das Meter-Datenmodul `am008_meter` (drei Funktionen mit versteckter Abnahme), Modell Qwen3.6-35B-A3B (`n_cpu_moe` 28, 32k, ohne Denkmodus) auf GUPPIs eigenem `llama-server`. Cline 4.1.23 in VS Code, ein Auftrag in einem Stück, ohne Eingriff.
Quellen: Serverlog (`runtime_data/vscode_serve/server.log`), Cline-Sitzung (`~/.cline/data/sessions/1791552021693_r24v4/`), Tabelle `docs/MODELL_VERGLEICH_ERGEBNISSE.md`.

## Zahlen (Cline nach 61 Minuten, Sitzung noch offen)

| | Cline in VS Code | DevVM-Bau (Qwen3.6, gleiches Modell) |
|---|---|---|
| Dauer | über 61 min, nicht fertig | 62 min, fertig |
| Ergebnis versteckte Suite | daily und cards bestanden, heatmap und all durchgefallen | 4 von 4 bestanden |
| Anfragen an das Modell | 128+ | 16 Agentenläufe mit 259 Aufrufen (Modell- und Werkzeugaufrufe) |
| Prompt-Token (eingelesen) | 453.562 (rund 28 min Einlesezeit bei 265 Token/s) | nicht erfasst |
| Erzeugte Token | 76.147 (bis jetzt) | 115.385 |
| Werkzeugaufrufe | 109 (49 Befehle, 31 Bearbeitungen, 28 Lesezugriffe) | |
| Werkzeugaufrufe mit Fehler | 34 von 109 (31 %) | |
| Testläufe | 5 von 49 Befehlen | je Stufe ein Lauf im microVM-Judge |
| Hilfsdateien im Ordner | `fix_main.py`, `fix_temp.py` (nicht aufgeräumt) | `tidy` räumt auf |

## Wo Cline Zeit und Fehler verliert

1. **Bearbeitungen scheitern jede zweite Runde.** 16 von 31 Aufrufen des Editors meldeten, dass der zu ersetzende Text nicht gefunden wurde. Das Modell schreibt den alten Text nicht genau so, wie er in der Datei steht (Leerzeichen, Einrückung, Zeilenenden).
2. **Shell-Syntax von Windows.** 18 von 49 Befehlen scheiterten an PowerShell (`> $null` als eigener Befehl, `dir /b` und Bash-Muster, Pfade mit `\t`, die als Tabulator gelesen wurden). Cline läuft in PowerShell, das Modell denkt in Bash.
3. **Befehle als Lesewerkzeug.** Das Modell liest Dateien über `python -c "open(...)"` oder `Get-Content` statt über das Lesewerkzeug, und wiederholt dieselben Befehle (einer sechsmal). Jeder Fehlversuch kostet einen Umlauf von etwa 10 s Mittel, in der Spitze 160 s.
4. **Viel Testcode, wenige Läufe.** Die Testdatei ist dreimal so groß wie der Code (13,7 KB gegen 4,8 KB), ausgeführt wurden die Tests nur fünfmal. Die Heatmap ist trotzdem noch falsch: die eigenen Tests haben den Fehler nicht gefunden.
5. **Der Werkzeugrahmen kostet Einlesezeit.** 453.562 Prompt-Token bei 128 Anfragen: Cline schickt bei jedem Schritt Systemtext und Verlauf mit. Bei 265 Token/s sind das rund 28 der 61 Minuten, also fast die halbe Zeit (der Server belegt 3.479 s, davon laut Zahlen etwa 1.700 s Einlesen). Im DevVM sind die Prompt-Token nicht erfasst; das sollte für einen sauberen Vergleich nachgetragen werden.

## Was Cline besser macht (zum Lernen)

1. **Größenlimit je Bearbeitung mit klarer Fehlermeldung.** Neuer Text ist je Aufruf auf 6.000 Zeichen begrenzt; zwei Aufrufe liefen in das Limit und wurden in Stücken wiederholt. Das ist die Antwort auf unsere abgeschnittenen Antworten (`answer_cut`): Das Modell lernt früh, in Teilen zu schreiben, statt erst bei 8.000 Token zu scheitern.
2. **Kontext-Kompaktierung.** Bei etwa 43 Nachrichten ersetzt Cline den Verlauf durch eine Zusammenfassung (Ziel, Stand: erledigt, in Arbeit, blockiert, nächster Schritt) und kann so lange Läufe führen. Unser Agent hat nichts dergleichen und stößt an das Fenster.
3. **Drei Werkzeuge statt zehn** (`editor`, `run_commands`, `read_files`), und `read_files` liest mehrere Dateien in einem Aufruf.
4. **Rückfrage-Werkzeug** (`ask_question`, einmal benutzt) und **Prüfpunkt** per `git stash` vor Beginn.

## Was bei uns besser ist

1. **Unabhängige Abnahme.** Der versteckte Test im microVM-Judge entscheidet. Cline hat keinen und merkt nicht, dass die Heatmap falsch ist.
2. **Keine Shell.** Unsere Coder arbeiten ohne PowerShell oder Bash, mit festen Werkzeugen. Damit entfällt die ganze Fehlerklasse „Shell-Syntax“ (18 Fehler hier).
3. **Aufräumen und Kommentarlog:** `tidy` entfernt Hilfsdateien, und die Kommentare werden vorher gesichert.
4. **Kleiner Kontext je Agentenlauf.** Unsere Läufe sind kurz und bekommen nur, was sie brauchen. Das spart vermutlich Prompt-Token; das ist nicht gemessen (DevVM erfasst nur erzeugte Token).

## Vorschläge zur Übernahme (nach Wirkung geordnet)

1. **Fehlermeldung des Edit-Werkzeugs verbessern:** Wenn der alte Text nicht passt, die ähnlichste Stelle der Datei mit Zeilennummern zurückgeben. Bei Cline scheitert jede zweite Bearbeitung, bei unserem `edit_file` sahen wir in der Probe abwechselnd Bearbeiten und Prüfen, vermutlich aus demselben Grund.
2. **Größenlimit je `write_file`/`edit_file` (etwa 6.000 Zeichen) mit klarer Fehlermeldung,** zusätzlich zur Wiederholung nach `answer_cut`.
3. **Kontext-Kompaktierung für lange Coder-Läufe** (Zusammenfassung im Cline-Stil statt Abbruch am Zuglimit).
4. **Mehrere Dateien in einem Lesezugriff** (bei uns jeweils eine?).
5. **Prüfpunkt vor jeder Stufe** (Rückkehr zu einem guten Stand, wenn Nacharbeit alles verschlechtert).

## Grenzen dieser Messung

Eine Sitzung, ein Modell, eine Aufgabe. Die Sitzung war bei der Auswertung nicht beendet. Cline lief mit den Voreinstellungen des Captains, Qwen3.6 mit Temperatur und Werten aus Cline selbst (nicht aus unserem DevVM). Unterschiede kommen aus Werkzeug und Ablauf, nicht allein aus dem Modell.
