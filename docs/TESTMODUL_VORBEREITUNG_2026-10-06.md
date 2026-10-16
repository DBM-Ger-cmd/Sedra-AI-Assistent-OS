# Vorbereitung: umfassendes Testlauf-Modul (2026-10-06)

Stand: **Entwurf, nichts gebaut.** Ziel: ein Modul, das Aufgabenmengen, Läufer, Richter und Ergebnisse an einer Stelle bündelt, damit jeder Test (Modelle, Orchestrator-Modi, Rezepte) gleich ablaufen, nicht verloren gehen und sich vergleichen lassen.

## 1. Was es schon gibt (wird wiederverwendet, nicht ersetzt)
| Baustein | Datei | Aufgabe |
|---|---|---|
| GPU-Freigabe, Warteschlange, Läufe, Ergebnisse, Ereignisse | `testlab.py` (SQLite) | Koordination mehrerer Chats; kein Urteil über Code |
| Messprotokoll je Lauf | `run_log.py` → `measurements/logs/*.log/.json`, `MESSUNGEN.md` | nichts geht verloren |
| Aufgabenmengen | `benchmarks/team_tasks.py` (`base`, `hard`, `all`, `rework8`) | Aufgabentexte und Prüfungen |
| Ausgeführter Test als Richter | `benchmarks/judge.py` (Hidden-Prüfungen, VM) | Urteil, das Agenten nie sehen |
| Läufer | `small_team.py`, `devvm_agents_bench.py`, `devvm_tools_bench.py`, `cuda_crash_hunt.py` u. a. | je ein eigener Aufbau |
| Kandidaten-Tests, Abnahme | `candidate_tests.py`, `candidate_acceptance.py` | gesicherter Missionspfad, Captain-Freigabe |

## 2. Lücken, die das Modul schließen soll
1. **Jeder Läufer baut seine eigene Schleife** (Aufgaben, Seeds, Lease, Log, Zusammenfassung). Änderungen müssen mehrfach gemacht werden.
2. **Keine unabhängige Aufgabenmenge:** Orchestrator und Prompts wurden an `rework8` abgestimmt (Überanpassungsrisiko). Es fehlt ein Holdout, der nie zum Abstimmen benutzt wird.
3. **Kein Vergleich über Läufe:** Die Tabellen (solo / Pipeline / Delegation / Eskalation) wurden von Hand gebaut. TestLab kennt `runs` und `results`, aber die Läufer schreiben nicht einheitlich hinein.
4. **Keine Regressionsschwelle:** Es gibt kein „dieser Stand darf nicht schlechter sein als der letzte“.
5. **Check-Qualität nicht gemessen:** Wie oft ist der Check des Planers falsch (Hidden grün, eigener Check rot)? Das ist bisher nur Einzelbeobachtung.

## 3. Vorschlag: `guppi_runtime/test_suite.py` (dünn, kein neues Speichersystem)
- **Aufgabe** = `{id, text, tags, set, hidden_tests}`; Register der Mengen: `tune` (zum Abstimmen), `holdout` (nie zum Abstimmen), `smoke` (3 Aufgaben, schnell).
- **Variante** = benannter Läufer mit Konfiguration: `solo`, `team`, `delegating`, `escalating`, `escalating+same_model`; Modelle kommen aus den Rezepten.
- **Lauf** = Menge × Variante × Seeds; hält die GPU-Freigabe, schreibt in TestLab `runs`/`results` (ein einheitliches Ergebnisformat) und in `RunLog`.
- **Bericht** = Tabelle je Variante (Erfolg, Hidden-Erfolg, Zeit Mittel und Median, Aufrufe, Wechsel, Eskalationen, Check-Streit) und Vergleich zum letzten Lauf derselben Variante.
- **Schwellen** (Konfiguration, Vorschlag): Holdout-Erfolg ≥ 14/16 bei Eskalation, Median ≤ 90 s, kein Lauf > 300 s.
- **CLI:** `test_suite.py run --set holdout --variant escalating --seeds 2`, `test_suite.py compare <run_a> <run_b>`, `test_suite.py list`.

## 4. Bausteine in Reihenfolge
1. Ergebnisformat festlegen und `devvm_agents_bench.py` darauf umstellen (kleinste Änderung, ein Läufer zuerst).
2. Zweite Aufgabenmenge `holdout` mit mindestens 8 neuen Aufgaben schreiben (**Entscheidung des Captains:** welche Art Aufgaben; Vorschlag: andere Standardbibliotheks-Themen als `rework8`, dazu 2 Mehrdatei-Aufgaben mit Ordnerstruktur für Phase 6).
3. `compare` und Schwellen.
4. Restliche Läufer (`small_team`, `tools_bench`) auf das Modul umstellen.
5. UIX-Anzeige nur lesend (gehört zu Phase 5, DevVM-Fenster).

## 5. Was ich nicht tue, ohne dass der Captain es sagt
- Kandidaten-Test- und Abnahmepfad verändern.
- Eine VM-Freigabe je Lauf umgehen (CW-001 bleibt offen und ungebaut).
- Den Holdout zum Abstimmen verwenden.

## 6. Ergänzungen des Captains (2026-10-06)
- **Das Testmodul darf GUPPI selbst als Aufgabe bauen** (als Kandidat über die DevVM; Bau freigegeben, Integration nicht).
- **Live-Ticker auf dem GUPPI-Desktop:** ein kleines Fenster im UIX, das lesend zeigt, was gerade passiert (laufender Agent und Modell, Werkzeugaufrufe, Testergebnis, Eskalation, Lease-Halter). Datenquelle: Journal und Audit der DevVM sowie TestLab-`events`/`activity`. Gehört zu Phase 5 und teilt sich das Fenster mit dem DevVM-Fenster (Reiter „Live“).
- **Testmodus misst, wie viele Unter-Agenten ein Modell zuverlässig unterstützt:** neue Messreihe je Modell mit 1, 2, 3, 4 gleichzeitig oder verschachtelt gestarteten Helfern (`max_subagents`, Tiefe 2). Gemessen werden Erfolg, Hand-in-Quote, Schleifen-/Abbruchquote und Zeit; „zuverlässig“ = Abbruchquote ≤ 10 % und Erfolg nicht unter dem Wert mit 0 Helfern. Ergebnis je Modell als empfohlene Obergrenze in die Rezepte. Hinweis: Auf einer GPU laufen Helfer nacheinander, nicht parallel; gezählt wird also die Zahl der Helfer je Lauf.
