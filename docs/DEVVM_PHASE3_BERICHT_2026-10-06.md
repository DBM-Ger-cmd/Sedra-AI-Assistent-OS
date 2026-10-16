# DevVM Phase 3: Unter-Agenten (2026-10-06)

Auftrag: `docs/DEVVM_AUFTRAG_2026-10-05.md` (Anforderung C und D). Vorarbeit: Phase 1 (Arbeitsbereich, Git, Ordnerexport) und Phase 2 (Werkzeugsatz).

## 1. Was gebaut ist

`src/guppi_runtime/devvm_agents.py`:

| Teil | Aufgabe |
|---|---|
| `run_agent` | ein Agentenlauf mit Rolle, Auftrag, Werkzeugsatz, Budget; Ergebnis mit Abgabe, Stopp-Grund, Journal; Audit-Ereignis `DEVVM_AGENT_RUN` |
| `AgentBudget` | je Lauf: 40 Aufrufe, 600 s, 30 Runden, 40 000 erzeugte Token, 3 blockierte Wiederholungen |
| `ModelHost` | immer nur **ein** Modell auf der GPU; Wechsel kostet die Ladezeit; ein abgestürzter Server wird **einmal** neu gestartet und der Aufruf wiederholt |
| `DevOrchestrator` | Planer, dann je Schritt Entwickler, Test als Richter, Prüfer, Wiederholung bei FAIL, Commit |

**Regeln aus dem Auftrag, wie sie umgesetzt sind**
- **Tiefe 1:** `run_agent` weist `depth > 1` ab, und es gibt kein Werkzeug, das einen Agenten startet (geprüft). Nur der Orchestrator startet Agenten.
- **Ein Modell zugleich:** `ModelHost.use(modell)` entlädt vor dem Laden; derselbe Modellschlüssel bleibt geladen (Planer und starker Entwickler sind beide Qwen3-Coder).
- **Schleifenschutz:** der bestehende `LoopGuard` sitzt in der Werkzeugbox (gleicher Lesezugriff mit gleichem Ergebnis: Warnung beim 3., Blockade ab dem 4. Mal); nach 3 Blockaden endet der Lauf mit `loop`. Der bestehende `RunawayGuard` prüft jede Antwort auf einen sich wiederholenden Block (`runaway`). Dazu Rundenlimit mit Hinweis kurz davor, Zeit- und Token-Budget. Alle Stopp-Gründe: `hand_in`, `no_tool_call`, `calls`, `time`, `tokens`, `loop`, `runaway`, `turns`, `answer_cut`, `error`.
- **Journal und Protokoll:** jeder Lauf trägt das Journal seiner Werkzeugaufrufe, einen Audit-Eintrag (Rolle, Modell, Stopp-Grund, Aufrufe, Dauer, Token) und optional eine Zeile im Run-Log. Dazu `DEVVM_PLAN`, `DEVVM_STEP`, `DEVVM_RUN_DONE` mit der Mission.
- **Der ausgeführte Test entscheidet:** nur mit `vm_runner` (in Produktion der Broker mit Guard und Captain-Karte). Der Planer schreibt je Schritt ein kurzes **Prüfskript** aus den Beispielen der Aufgabe; es läuft in der VM nach dem Entwickler. Nach dem **letzten** Schritt laufen zusätzlich die Unit-Tests des Arbeitsbereichs.
- **Eskalation:** schafft der kleine Entwickler (Jan) einen Schritt nicht, übernimmt für die Wiederholung das starke Modell (Qwen3-Coder).

**Schutz vor schlechten Prüfskripten des Planers** (alle gemessen, siehe 3): ein Skript, das Dateien anlegt oder schreibt oder die zu prüfende Funktion selbst definiert, wird vor dem Einsatz verworfen; der Planer wird **einmal** um einen Plan mit brauchbaren Skripten gebeten; ein Skript, das selbst einen `NameError` oder `SyntaxError` wirft, zählt nicht gegen den Entwickler; scheitert die Prüfung in der letzten Runde dennoch, entscheidet der Prüfer als Schiedsrichter (nur ein ausdrückliches PASS nimmt an); „NO TESTS RAN" zählt nicht als Fehlschlag; der Unittest-Aufruf folgt dem Aufbau (`-s tests`, wenn es einen Ordner `tests/` gibt).

## 2. Abnahme: Team gegen Jan allein (`benchmarks/devvm_agents_bench.py`)
Dieselben drei Aufgaben wie in Phase 2, je 3 Durchgänge; Erfolg = versteckte Prüfungen in der VM auf einer Kopie des Arbeitsbereichs (die Agenten sehen sie nie).

| | Erfolg | Zeit je Lauf (Median) | Aufrufe (Median) | Modellwechsel |
|---|---:|---:|---:|---:|
| **Jan allein** | **1/9** | 14,5 s | 10 | 1 |
| Team, Messung 2 (Planer teilt in bis zu 3 Schritte) | 8/9 | 215 s | 93 | 7 |
| Team, Messung 3 (ein Schritt, Prüfskripte validiert) | 8/9 | 70 s | 36 | 3 bis 4 |
| **Team, Messung 4 (plus einmalige Wiederholung des Plans)** | **8/9** | **65 s** | **32** | 3 bis 4 |

Dateien: `logs/devvm_agents_bench_2026-10-06_081254.*` (Jan allein und Team, Messung 2), `…_084747.*` (Messung 3), `…_090044.*` (Messung 4).

- **Das Team hebt Jan von 1 von 9 auf 8 von 9** und hat dabei aufgeholt, was an Zeit verloren ging: von 215 auf 65 Sekunden, weil der Planer nur noch einen Schritt macht (weniger Modellwechsel).
- Bei `fix_and_commit` (Jans Schwachstelle) gelingt es in Messung 4 **3 von 3**: Jan scheitert zuerst an der Abnahmeprüfung (mehrfache Leerzeichen), das starke Modell behebt es, der Prüfer sagt PASS. So war es gedacht.
- **Schleifenschutz und Budgets greifen:** über die Läufe stoppte der Schutz Agenten wegen `loop` (7 Mal in Messung 2, 2 in 3, 1 in 4, fast immer der Prüfer), wegen `turns` (5, 1, 1) und einmal wegen `runaway`. Die 40-Aufrufe- und 10-Minuten-Grenze wurde nie erreicht (höchstens 73 Aufrufe für einen ganzen Teamlauf mit 4 Agenten).
- **Eine Aufgabe bleibt jeweils offen:** `move_and_update` #1 in Messung 4 (versteckter Test scheitert trotz PASS des Prüfers), `fix_and_commit` #1 in Messung 3 (Prüfskript war unbrauchbar und wurde verworfen, der Prüfer übersah die mehrfachen Leerzeichen; dafür gibt es seitdem die Wiederholung des Plans).

## 3. Fehler, die die Messung gefunden hat (alle behoben, mit Tests)
| Befund | Ursache | Behebung |
|---|---|---|
| Arbeitsbereich unbrauchbar für die VM | beim Schreiben blieb unter Windows eine `….tmp-write`-Datei liegen (Umbenennen kurz gesperrt) | Wiederholung, Aufräumen bei Fehler, Helferdateien zählen nicht zum Arbeitsbereich |
| Test-Richter bestrafte Zwischenschritte | `unittest discover` meldet „NO TESTS RAN" als Fehler; Tests in `tests/` ohne `__init__.py` werden von der Wurzel nicht gefunden | Aufruf nach Aufbau; „NO TESTS RAN" zählt nicht; Unit-Tests nur nach dem letzten Schritt |
| Prüfskripte des Planers wertlos oder falsch | Skripte legten Dateien selbst an, definierten die geprüfte Funktion selbst, lasen nach dem Verschieben noch alte Pfade, nutzten Hilfsfunktionen, die es in der VM nicht gibt | Anweisung an den Planer, statische Prüfung, Erkennung kaputter Skripte, einmalige Wiederholung des Plans, Schiedsrichter |
| Prüfer wanderte ohne Ziel (Schleifenschutz, kein Urteil) | suchte nach dem Verschieben die alte Datei | der Prüfer bekommt Diff und Liste der Änderungen im Auftrag (Prüfskripte ausgenommen) |
| Warnhinweis hob den Schutz auf | der Hinweis veränderte das Ergebnis, die Serie war damit unterbrochen | der Schutz protokolliert das Ergebnis ohne Hinweis; blockierte Aufrufe stehen nicht im Verlauf |

## 4. Grenzen und offene Punkte
- **Die Aufgaben dienten auch zum Abstimmen:** Prompts und Schutzregeln wurden an genau diesen drei Aufgaben entwickelt (Messung 2 bis 4). Die 8 von 9 sind ein Zeichen, kein Beweis für beliebige Aufgaben. Eine unabhängige Aufgabenmenge fehlt noch.
- **Freigaben in Produktion:** Der Läufer der Messung ist ein Benchmark-Läufer ohne Freigabe. In Produktion geht jeder VM-Lauf über `broker_runner` mit Captain-Karte. Ein Teamlauf braucht etwa 2 bis 4 VM-Läufe (Prüfskript je Runde, Unit-Tests am Ende) und damit ebenso viele Freigaben; die Entscheidung zu CW-001 (Phase-1-Bericht, Punkt 2) bleibt offen. Ohne Läufer arbeitet das Team nur mit dem Prüfer, und dann sind die Ergebnisse deutlich schlechter (Jan-Fehler werden übersehen).
- Der Prüfer (SWE-Review-8B) liefert bei etwa jedem vierten Schritt kein Urteil (`loop`, `turns`); der Orchestrator nimmt den Schritt dann an. Das ist unkritisch, solange ein ausgeführter Test mitentscheidet.
- Nicht gemessen: Aufgaben mit mehreren echten Teilen (der Planer teilt jetzt nur noch selten); die Tester-Rolle; Last mit mehr als einem Agentenlauf gleichzeitig (bewusst nicht vorgesehen, eine GPU).

## 5. Tests der berührten Module
`test_devvm_agents` 26, `test_devvm_tools` 18, `test_devvm` 14 (1 übersprungen, Symlink-Recht fehlt auf dem Rechner), `test_model_tools` 7, `test_sandbox` 46, `test_run_log` 3; alle grün.
