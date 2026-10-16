# Anschluss-Skript: Qwen Code in der Bau-Schleife (2026-10-10)

`runtime/benchmarks/qwen_build.py` lässt Qwen Code (Node, eigener Ordner) an einer DevVM-Stufe arbeiten, **mit demselben Modellserver, demselben Arbeitsordner und demselben versteckten Test** wie unser Solo-Entwickler. Über das Gate-System startet man es als `probe_qwen` (`benchmarks/probes/qwen_probe.py`, Optionsdatei `seeds/probe_qwen.options.json`).

## Ablauf
1. **Vorprüfung vor jedem Lauf** (`--skip-preflight` nur für Proben ohne Modell): Der Agent wird mit einem Fake-Modell gestartet, die Liste der Werkzeuge, die er dem Modell zeigt, wird aufgezeichnet und mit unserer verglichen. Jedes andere Werkzeug, jedes fehlende, bricht den ganzen Lauf mit Exit 3 ab, **bevor** ein Modell etwas sieht.
2. Modellserver wie bei `devvm_build.py` (GPU-Lease, `BenchLoader`, Rezept `coder.local_primary`, Fenster 32k) oder mit `--fake-model` ein Fake zur Probe ohne GPU.
3. Je Stufe: Aufgabe ohne Testpflicht (`without_test_duty`) plus unsere Solo-Anweisung (dieselbe Formulierung wie bei `solo`, mit Hinweis auf die Werkzeuge des Servers). Qwen Code läuft **headless** (`-p ... --output-format json`) in einem **leeren** Arbeitsordner mit eigenem Home (`HOME`/`USERPROFILE`), ohne Schlüssel und Tokens des Rechners (`qwen_env` entfernt alles mit KEY, TOKEN, SECRET und die Vorgaben der Anbieter), mit Dummy-Schlüssel und der Adresse unseres Servers. Die Werkzeuge kommen **nur** vom MCP-Server `guppi_runtime.devvm_mcp`, der an den Arbeitsordner der Stufe **angehängt** ist (`--attach`).
4. Danach Commit und **versteckter Abnahmetest in der microVM** (`acceptance`); bei Fehlschlag derselbe lesbare Fehlerbericht wie beim Solo (`hidden_report`), die Nacharbeit **setzt die Sitzung fort** (`--continue`), bis zu `--rework` Mal.
5. Ergebnis in dieselben Dateien wie `devvm_build.py` (`devvm_build_<spec>_*.json/.log`, `agent: qwen-code`, Spalte Modus in der Vergleichstabelle „Qwen Code + none|light|full"), Kandidat nach `runtime_data/devvm_candidates`, **Zwischenstand je bestandener Stufe** nach `runtime_data/devvm_snapshots`. Aufrufe je Werkzeug stammen aus dem Journal des MCP-Servers; Token aus der JSON-Ausgabe des Agenten, soweit lesbar. Das Protokoll hat dieselben Zeilen wie beim Solo, damit der Schichtenbericht (`failure_layers.py`) greift.

## Einstellungen, die Vergleichbarkeit sichern
Prüfumfang `--self-check none|light|full` (Standard `none`: der Agent kann keinen Code ausführen, wie `solo-none`; `light`/`full` bieten `run_python` in der microVM mit 2 beziehungsweise 8 Läufen), Temperatur 0,1 (wie unser Solo), `--max-turns 40`, `--max-seconds 1200` je Lauf des Agenten, `reasoning off` am Server.

## Probe ohne GPU (heute gelaufen)
`--fake-model`: ein Skript-Modell ruft `write_file` und `submit_result` auf. Ergebnis: Vorprüfung „ONLY OUR TOOLS" (16 Werkzeuge mit `run_python`), Lauf mit Abgabe, Abnahmetest in der microVM (durchgefallen wie erwartet), Nacharbeit mit `--continue` (kein Absturz), Ergebnisdateien geschrieben. Die Zeilen der Probe tragen das Modell `fake-model` und werden von `model_compare` ausgeblendet.

## Grenzen
- Der Agentenprozess läuft auf dem Rechner (Node). Seine Sicherheit hängt an der Konfiguration, die die Vorprüfung vor **jedem** Lauf bestätigt; nach einem Update von Qwen Code gilt sie nur so lange, bis die Vorprüfung etwas anderes zeigt.
- Offen bis zum ersten Lauf mit echtem Modell: ob die JSON-Ausgabe Token liefert (sonst Nullen), ob Qwen Code die Fenstergröße 32k beim Verdichten beachtet (`contextWindowSize` ist gesetzt), wie es auf unsere Werkzeug-Fehlermeldungen reagiert, ob die Sitzung mit `--continue` über die Stufen hinweg sauber getrennt bleibt (jede Stufe beginnt ohne `--continue`).
- Die Aufrufe der Brücke und der übrigen Qwen-Werkzeuge sind entfernt; Qwen Code kann deshalb weder Unter-Agenten noch Pläne oder Zeitpläne benutzen. Das ist gewollt (gleiche Werkzeuge wie unser Solo), schränkt aber ab, was der fremde Agent normalerweise kann.

## Erster Lauf mit echtem Modell (run-a880f5fce467, Gate HG-6A1D5901, 2026-10-10 16:41 bis 16:58)
Standardtest, Qwen Code (eigene Systemanweisung), Prüfumfang `qwen-none`, Qwen3.6 IQ4_XS, zwei Läufe; zum Vergleich unser `solo-none` aus demselben Tag.

| | Qwen Code Lauf 1 | Qwen Code Lauf 2 | unser `solo-none` (2 Läufe) |
|---|---|---|---|
| Stufen bestanden | 4/4 | 4/4 | 4/4 und 4/4 |
| Dauer | 334 s | 603 s | 124 s und 119 s |
| Aufrufe | 63 | 141 | 25 und 26 |
| Nacharbeiten | 1 (`move`) | 3 (`slug` zweimal, `move`) | 0 und 0 |
| Prompt je Anfrage (Mittel) | etwa 13.000 bis 15.000 Token | ebenso | höchstens 3.000 bis 3.500 |

**Was im Journal steht**
1. **`submit_result` wurde 4- bis 5-mal je Lauf aufgerufen, einmal 34-mal.** Der Server antwortete auf die Abgabe nur mit „received"; Qwen Code kennt kein Ende durch ein bestimmtes Werkzeug und fragte weiter. Beim 34-maligen Fall griff die **eigene Schleifenerkennung von Qwen Code** („consecutive_identical_tool_calls") beziehungsweise das **Rundenlimit** (`FatalTurnLimitedError`, 40 Runden), und die Stufe hatte schon abgegeben. Das ist ein Fehler der Anbindung (Schicht 2/3), nicht des Modells. **Behoben:** nach der Abgabe antwortet der Server auf jeden Aufruf mit „The work is handed in and the task is over ... stop".
2. **Die Systemanweisung von Qwen Code ist etwa 20.000 Zeichen lang** (rund 5.000 Token), dazu 15 Werkzeugbeschreibungen: etwa ein Drittel des 32k-Fensters ist belegt, bevor die Aufgabe beginnt. Bei schweren Stufen (am007) wäre das entscheidend. Neue Option `--system append|lean` (unsere Anweisung zusätzlich oder statt der eigenen).
3. **Die Anweisung ist nicht dieselbe wie bei unserem Solo:** unser Entwickler bekommt als Systemtext die Regeln „kleinste Änderung, jedes konkrete Beispiel einschließlich None, leer, Grenzfälle, Aufgabe gegen den Code lesen". Qwen Code sah nur die Aufgabe und die Kurzanweisung. Das erklärt wahrscheinlich einen Teil der Nacharbeiten (`move` fiel in beiden Läufen zuerst durch); **belegt ist es nicht.**
4. **Korrektur der Vorprüfung:** Die Vorprüfung sah nur die Werkzeugliste der ersten Anfrage. Im Start-Ereignis des echten Laufs standen zusätzlich **`manage_memory` und `search_memory`** (Gedächtniswerkzeuge von Qwen Code, schreiben in den leeren Home-Ordner des Agenten). Genutzt wurden sie laut Journal nicht (das Journal kennt nur unsere Werkzeuge), aber sie waren registriert. Sie sind jetzt abgeschaltet (`tools.disabled`), und die Vorprüfung vergleicht ab jetzt **die Vereinigung aus Start-Ereignis und allen Anfragen**.
5. Eine Lauf-Ausgabe (`qwen_output_4`) hatte keine auswertbaren Token (`FatalTurnLimitedError` statt Ergebnisliste): dort stehen Nullen.

**Aussage:** Mit dieser Anbindung ist Qwen Code bei gleicher Trefferzahl 2,7- bis 5-mal langsamer als unser Solo ohne Prüfung. Der Hauptteil davon ist die wiederholte Abgabe (4 bis 34 zusätzliche Anfragen mit je 13.000 Token) und die größere Anfrage, also Anbindung und Anweisung, nicht die Schleife als solche. Ein fairer Vergleich braucht den Lauf mit den Korrekturen (Abgabe-Ende, `--system append|lean`).

Zahlen zum Journal: `submit_result` war **18 von 63** Aufrufen (29 %) im ersten und **58 von 141** (41 %) im zweiten Lauf. Ohne diese wiederholten Abgaben wären es 45 und 83 Aufrufe gewesen.

## Auswertung des zweiten Gates (run-0f384d74a5d8, 17:04 bis 17:38) und zwei Korrekturen
Vier Läufe, alle 4/4: `qwen-none` 442 s (49 Aufrufe, 1 Nacharbeit) und 494 s (68, 1); `qwen-lean-none` 531 s (55, 1) und 490 s (52, 2). `submit_result` kam jetzt 5- bis 7-mal je Lauf (eine Abgabe je Stufe plus Nacharbeit): der Fehler mit der wiederholten Abgabe ist behoben.

**FEHLER DER ANBINDUNG, die Läufe sind für `fix` und `move` NICHT vergleichbar:** Der Standardtest braucht seine Saat-Dateien (`benchmarks/bench_std_seed`: `ledger.py`, `util.py`, `main.py`). Unser `solo-none` bekam sie (`stdbench_probe` übergibt `--seed`), **`qwen_probe` übergab sie nicht**. Im Journal von `move` steht als Erstes `read_file util.py` und `read_file main.py` mit `file_not_found`: der Agent musste die Dateien erfinden, schrieb `util.py`, `main.py` und `mathkit.py` neu und fiel deshalb in **allen sechs Läufen** (beide Gates) beim ersten Versuch durch. Gültig sind nur die **Stufen ohne Saat**, `slug` und `extend`. Behoben: `qwen_build.py` nimmt für `bench_std` ohne Angabe die Saat des Standardtests (Test dazu). Alle bisherigen Qwen-Code-Zeiten des Standardtests sind daher zu hoch und gelten nicht als Ergebnis.

**Gültig sind aus diesen Läufen:**
- `slug` und `extend` (ohne Saat): Qwen Code 70 bis 101 s je Stufe bei 4 bis 7 Aufrufen; unser `solo-none` braucht für den **ganzen** Test mit vier Stufen 120 s, also etwa 30 s je Stufe. Der Abstand hat einen festen Teil je Lauf des Agenten (Start von Node und MCP-Server, erste Anfrage mit 4.000 bis 8.000 Token).
- Erzeugte Token je Lauf (aus dem Ergebnis-Ereignis, siehe unten): Qwen Code 8.000 bis 13.500 (ohne den Ausreißer 19.400 des ersten Gates), unser `solo-none` 3.000 bis 3.400.

**Zweite Korrektur, Token:** Meine Auswertung zählte die Token doppelt (Nutzung der einzelnen Antworten **und** die Gesamtnutzung im Ergebnis-Ereignis). Die Angaben „13.000 bis 15.000 Token je Anfrage" im Abschnitt davor sind etwa **doppelt zu hoch**. Richtig (aus der Gesamtnutzung des Ergebnis-Ereignisses, `parse_qwen_output` korrigiert): etwa **9.000 Token je Anfrage** bei `asis` und 7.000 bis 8.000 bei `lean`, davon rund 90 bis 95 % aus dem Zwischenspeicher des Servers. Messung der ersten Anfrage mit dem Fake-Modell: `asis` rund 7.700 Token (Systemtext 20.159 Zeichen, Werkzeuge 5.627 Zeichen), `lean` rund 4.300 Token (Systemtext 8.183 Zeichen: Qwen Code behält auch bei `--system-prompt` etwa 6.000 Zeichen eigenen Text). Die gespeicherten Zahlen in den bisherigen Ergebnisdateien (`prompt_tokens`) sind für die Qwen-Läufe doppelt gezählt.

**Was bleibt als Befund:**
1. Der Hauptunterschied in der Zeit steckt (auf den gültigen Stufen) im festen Aufwand je Lauf des Agenten, nicht in vielen Aufrufen.
2. Qwen Code liest und prüft deutlich mehr (`read_file` 18 bis 20, `check_syntax` 9 bis 13 je Lauf gegen 9 bis 10 und 4 bis 5 bei uns), und erzeugt 2,5- bis 4-mal so viele Token.
3. `lean` spart etwa 20 bis 25 % Eingabe je Anfrage, nicht mehr.

## Auswertung des dritten Gates mit Saat (run-b4ae2778019e, 2026-10-10 20:00) – gültiger Vergleich
Alle 16 Stufen bestanden. `qwen-none`: 362 s (1 Nacharbeit) und 293 s; `qwen-lean-none`: 284 s und 677 s (2 Nacharbeiten bei `slug`, dort 467 s mit 6.900 und 10.400 erzeugten Token in der Nacharbeit). Ohne den Ausreißer 65 bis 78 s je Stufe, 3.700 bis 4.800 erzeugte Token je Lauf (korrekt gezählt), `submit_result` 5 bis 7-mal, keine Schleifen, Werkzeugliste in jedem Lauf bestätigt.

Gegen unser `solo-none` (119 und 124 s, 3.000 bis 3.400 Token): bei fast gleicher Token-Menge etwa 2,3-mal so langsam. Der Abstand (35 bis 40 s je Stufe) ist **fester Aufwand je Lauf des Agenten** (Start von Node und MCP-Server, langer Systemtext, mehrere Anfragen), nicht das Modell. `lean` spart auf diesen Stufen keine Zeit. Der Ausreißer ist ein Modellverhalten (lange Nacharbeit), kein Anschlussfehler. Schluss: Qwen Code ist als externer Agent brauchbar und sicher eingeschlossen, aber für den Standardweg nicht schneller als unser Solo-Entwickler; Zeit lässt sich nur über den festen Aufwand gewinnen (ein Lauf für mehrere Stufen), nicht über den Systemtext.
