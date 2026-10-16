# DevVM Phase 4: Test als Richter, höchstens eine Lektion, Delegations-Vergleich (2026-10-06)

Auftrag: `docs/DEVVM_AUFTRAG_2026-10-05.md` (Anforderung D, Phase 4: „Wiederholung des Teamtests (8 Aufgaben): mindestens so gut wie 15 von 16 bei ≤ 1 Lektion"). Dazu der Auftrag des Captains vom 2026-10-06: ein Lauf, in dem die wichtigsten Akteure Unter-Agenten selbst einsetzen dürfen und sollen, und der Vergleich mit dem bisherigen Ablauf.

## 1. Höchstens eine Lektion für kleine Modelle (Anforderung D2)
- `KnowledgeStore.lessons_for(text, limit, rank, min_specificity)`: neue, optionale Parameter. **Ohne sie ist das Verhalten unverändert** (älteste zuerst, höchstens `limit`); mit `rank=True` kommen die am besten passenden zuerst (mehr Trigger, dann längere Trigger), mit `min_specificity=8` zählt ein allgemeines Wort wie `port` oder `digits` allein nicht (vorher bekam ein Wörterbuch-Zugriff eine Lektion über Unicode-Ziffern).
- `small_team.py`: `pick_lessons` → standardmäßig **eine** Lektion (`--max-lessons`, `--all-lessons` für den alten Zustand).
- `DevOrchestrator.run(task, lessons=...)`: es erreicht **höchstens eine** Lektion den Entwickler (`MAX_LESSONS = 1`), Planer und Prüfer bekommen keine.

**Abnahme: der Teamtest mit acht Aufgaben** (`small_team.py --tasks all`, 2 Durchgänge, ausgeführter Test als Richter in der VM, Flash-Attention aus, Datei `logs/smallteam_2026-10-06_*`):

| | vorher (alle Lektionen) | jetzt (≤ 1 Lektion) |
|---|---:|---:|
| Jan allein | 13/16 | **14/16** |
| Team `test` | 14/16 | **16/16** |
| Team `test+review` | 15/16 | **16/16** |

**Ziel „mindestens 15 von 16 bei höchstens einer Lektion" erreicht (16 von 16).**

## 2. Dieselben acht Aufgaben durch den ganzen Orchestrator (`devvm_agents_bench.py --taskset rework8`)
Das ist der Test mit einer **anderen** Aufgabenmenge als in Phase 3: fünf der acht Aufgaben waren dem Orchestrator neu. Erfolg = die Prüfungen von `judge.py` in der VM auf dem Ergebnis (die Agenten sehen sie nie). Je 2 Durchgänge, 16 Läufe je Variante.

| Variante | Erfolg | Zeit je Lauf (Mittel) | Aufrufe (Mittel) | Agentenläufe | Modellwechsel | Token (Mittel) |
|---|---:|---:|---:|---:|---:|---:|
| **Jan allein** | 13/16 | 10,9 s | 3,6 | 1 | – | 502 |
| **Team (feste Pipeline)**: Planer, Entwickler, Prüfer, Test, starker Entwickler bei Fehlschlag | 14/16 | 165 s | 45 | 3,6 | 3,6 | 4 616 |
| **Delegation**: nur Planer und Entwickler als Akteure, sie setzen Helfer selbst ein | **16/16** | 207 s | 51 | 5,4 | 5,9 | 4 929 |

Dateien: `logs/devvm_agents_bench_2026-10-06_100958.*` (allein und Team), `…_105738.*` (Delegation).

**Je Aufgabe:** `pair_parse` (Jans schwächste: 0/2) wird von Team und Delegation 2/2 gelöst, `regex_trailing_newline` von 1/2 auf 2/2. Das Team scheitert noch bei `isoformat_date` (1/2) und `nested_lookup` (1/2), die Delegation nirgends.

### Was im Delegations-Lauf tatsächlich passierte
- **Jan delegierte selbst:** 50 Aufrufe von `delegate` in 16 Läufen (3,1 je Lauf): 18 Mal ein Prüfer, 13 Mal der **starke Entwickler (Qwen3-Coder) in 12 von 16 Läufen**, dazu 17 Mal der Planer an einen Erkunder.
- **Der Erfolg kommt zu einem großen Teil vom starken Modell als Helfer.** Jan hat bei drei von vier Aufgaben Qwen3-Coder um Hilfe gebeten. Das ist keine Fähigkeit des kleinen Modells, sondern wirkt wie die Eskalation des Teams, nur früher und öfter.
- **Die Prüfer-Helfer waren schwach:** 8 von 18 gaben kein Urteil ab, 6 sagten FAIL, 4 PASS.
- **Der Erkunder war überflüssig:** Der Hinweis „sollst delegieren" ließ den Planer auch bei einem Arbeitsbereich mit einer einzigen Datei einen Erkunder schicken (17 Mal).
- Schutz und Grenzen griffen: Stopp-Gründe über alle Agentenläufe `hand_in` 56, `no_tool_call` 16, `turns` 10, `loop` 3, `answer_cut` 1; die Helfer-Obergrenze (4 je Lauf) und die Tiefe 2 wurden eingehalten (geprüft).

## 3. Einordnung (ehrlich)
- **Die Zahlen sind klein:** 16 Läufe je Variante. 14/16 gegen 16/16 sind zwei Läufe Unterschied, kein gesicherter Vorsprung. Dass Team und Delegation Jan allein übertreffen (13/16), ist nur bei den schweren Aufgaben (`pair_parse`) deutlich.
- **Der Preis ist hoch:** 15 bis 19 Mal so viel Zeit (165 bis 207 s statt 11 s) und rund 10 Mal so viele Token. Auf den einfachen Aufgaben (Jan löst sie allein) ist das reiner Aufwand.
- Die Delegation ist langsamer als die Pipeline (mehr Modellwechsel: 5,9 gegen 3,6), aber in diesem Lauf erfolgreicher; bei `accepted` liegt sie niedriger (13 gegen 14 von 16), weil das Prüfskript des Planers dreimal etwas verlangte, das das Ergebnis trotz bestandener Hidden-Prüfung nicht erfüllte.
- Alle drei Varianten nutzen dieselbe Aufgabenmenge, an der der Orchestrator in Phase 3 nicht abgestimmt wurde (nur `isoformat_date`/`nested_lookup`-Anweisungen aus dem Teamtest stammen aus früheren Läufen). Eine wirklich unabhängige Aufgabenmenge fehlt weiter.

## 4. Was der Vergleich nahelegt
Ein dritter Weg dürfte billiger sein als beide: **zuerst Jan allein, danach der ausgeführte Test, erst bei Fehlschlag das starke Modell** (die Pipeline-Eskalation ohne festen Prüfer-Schritt und ohne Planer bei einfachen Aufgaben). Das wäre bei bestandenem Test so schnell wie Jan allein. Das ist noch nicht gebaut oder gemessen.

## 5. Umsetzung des Delegations-Modus (opt-in)
- `DevOrchestrator(mode="delegating", max_depth=2)`; ohne `max_depth=2` verweigert der Konstruktor den Modus (`delegation_needs_depth_2`). Der Standard bleibt: Tiefe 1, keine von Agenten gestarteten Helfer.
- Werkzeug `delegate(role, instruction)` für Entwickler (`reviewer`, `strong_coder`) und Planer (`explorer`); Rollen ergeben sich aus den konfigurierten Modellen. Höchstens 3 Aufrufe je Agent, höchstens 4 Helfer je Lauf, Helfer sind Blätter (kein `delegate` bei ihnen), kleineres Budget (25 Aufrufe, 5 Minuten).
- `ModelHost.call(key, ...)`: jeder Aufruf stellt zuerst sicher, dass das **eigene** Modell des Agenten geladen ist; ohne das hätte ein Elternlauf nach seinen Helfern das Modell eines Helfers angesprochen.
- Nur Planer und Entwickler sind feste Akteure; kein fester Prüfer-Schritt, keine automatische Eskalation; der ausgeführte Check urteilt, ein Fehlschlag gibt dem Entwickler eine weitere Runde.
- Journal und Audit: jeder Helferlauf trägt `parent`, `depth` und steht im Audit (`DEVVM_AGENT_RUN` mit `delegations` und `depth`).

## 6. Tests
`test_devvm_delegation` 12, `test_devvm_agents` 27, `test_devvm_tools` 18, `test_devvm` 14 (1 übersprungen), `test_knowledge_lessons` 4 (neu), `test_small_team` 6, `test_judge` 6, `test_team_tasks` 4, `test_model_tools` 7, `test_sandbox` 46; alle grün.

## 7. Offen
- CW-001 (Freigaben je VM-Lauf) unverändert offen; ein Teamlauf braucht 2 bis 4 VM-Läufe, ein Delegationslauf ebenso (der Check läuft in beiden gleich).
- Unabhängige Aufgabenmenge; der „erst allein, dann eskalieren"-Weg; Prüfer-Helfer ohne Urteil; Phase 5 (DevVM-Fenster) und Phase 6 (Abnahmelauf von Grund auf).
