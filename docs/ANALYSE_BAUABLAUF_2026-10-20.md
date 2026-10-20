# Analyse des Bauablaufs (20.10.2026)

Nur gelesen: Dokumente, Skripte, Specs, Tests, Logbuch. Kein Bau, kein Modell, keine GPU. Einzige Ausführung: `spec_check.py k0_kinds` (Referenz auf dem Host, kein Modell): `lint ok, ref register/view/client ok, result ok`. Belege: `Datei:Zeile` oder Logbuch-Datum (`docs/LOGBUCH_AGENT_MANAGER.md`, kurz LB).

## 1. Kurzfassung

Der Bau-Kern ist gesund: Spec, Gegenprobe an der Referenz, Bau mit versteckten Tests, Review. Aus dem Ruder gelaufen ist das Drumherum:

- Seit dem 14.10. 10:06 hat SEDRA kein Modul mehr gebaut. Alles Neue der Builds 7 bis 24 (UIX, Shells, GateWay) hat Claude geschrieben.
- Der Bauweg wurde vier- bis fünfmal parallel gebaut (Skripte, Agent Manager, Buildflow, Qwen-Anschluss).
- Rund ein Drittel aller Bau-Specs hat im LB keinen Bau oder keine Übernahme.
- Dokumente und Logbuch hinken hinterher (Stand 12.10., Lücke 15. bis 20.10.).

Empfehlung zu 18 Uhr: **k0_kinds bauen, aber als begrenzten Test mit klaren Abbruchgrenzen** (Abschnitt 7).

## 2. Soll-Ablauf in 10 Zeilen

(`docs/ENTWICKLUNG.md:15-84`, `docs/BUILDFLOW_2026-10-13.md`)

1. Spec `devvm_specs/<n>.py`: `NOTES`, `STAGES` mit Aufgabe und versteckten Tests, eine Prüfung je `assert`.
2. Referenz `devvm_refs/<n>/` besteht vor dem Bau jede Stufe. Ohne grüne Referenz kein Bau.
3. `spec_check.py <n>` meldet `result ok`: Lint, Referenz, erste Stufe fällt auf der Saat durch.
4. Der Captain gibt Spec und Bau frei, jedes Gate einzeln per ID.
5. `devvm_build.py` hält die GPU-Lease. Je Stufe baut das Modell allein (solo), der versteckte Test läuft in der microVM, bis zu 3 Nacharbeiten, danach Stopp mit Fortsetzungsbefehl.
6. Kandidat unter `runtime_data/devvm_candidates/<n>/attempt_…`, Snapshot je bestandener Stufe.
7. Claude liest jede Zeile (Review); Mängel gehen als Review-Datei zurück an das Modell. Bei Fehlschlag zuerst `spec_check --tree`: liegt der Fehler in der Spec?
8. Der Captain entscheidet die Übernahme. Kopieren ins Paket, betroffene Tests, bei UI-Dateien `uix_check.py`.
9. Logbuch mit `logbook.py add BAU …`, Commit nur eigener Dateien.
10. Ziel: GUPPI/SEDRA schreibt mindestens 50 % des neuen Codes, Claude schreibt Spec, Tests, Referenz, Harness (`ENTWICKLUNG.md:9`).

Das Buildflow-Dokument will dazu den ganzen Weg als eine Aufgabe mit Zustand führen, statt mit losen Skripten.

## 3. Ist-Ablauf

**Was gut läuft**
- Die Gegenprobe ist wirksam: Sie fand 7 falsche Erwartungen in 6 Specs und einen Spec-Fehler, der 30 Minuten GPU gekostet hatte (LB 13.10. 15:20 und 17:55). `spec_check` führt auch `host_hidden` aus, nachdem es JS-Stufen still als bestanden gezählt hatte (LB 13.10. 22:34).
- Die Solo-Methode ist belegt. Beispiele: skill_rank 4/4 in 263 s, skill_rank3 3/3 in 170 s (LB 13.10.), am008 in 3710 s gegen 4740 s.

**Wo der Ablauf abweicht**
- **Bau seit dem 14.10. durch Claude.** Der letzte SEDRA-Bau mit Übernahme steht im LB am 14.10. 10:06 (spec_standards). Danach folgen die Builds 7 bis 24 bis zum 15.10. (UIX, Shells, GateWay, Creator, Cockpit), alle von Claude. Unter den Builds 16 bis 24 steht kein SEDRA-Bau.
- **Wenige Module von SEDRA übernommen.** Übernommen und nachgewiesen sind etwa 20 Module mit zusammen rund 3.450 Zeilen. Das sind rund 8 % der 43.220 Zeilen Python unter `src/guppi_runtime`. Das Ziel in `ENTWICKLUNG.md:9` sind 50 % des neuen Codes. Am 8.10. waren es 40 % (LB 8.10. 09:52). Am 9.10. 09:12 kam die Entscheidung „Claude baut die Module selbst fertig“ (LB 9.10. 09:12). Das 50-%-Ziel wurde dabei nicht angepasst.
- **Vier bis fünf Wege zum Bau.**
  1. Direkter Aufruf `devvm_build.py` mit 37 Optionen. Der Standardbefehl in `ENTWICKLUNG.md:42-44` hat 9 Flags.
  2. 9 `day_queue_*`, 4 `night_queue_*`, `resume_queue.py`, `ab_queue.py` (Ketten als Einmal-Skripte).
  3. Agent Manager: `agent_manager/run_worker.py` ruft `devvm_build.py` mit einer Optionsdatei, die nur wenige feste Schlüssel kennt.
  4. Buildflow: `devenv/buildflow_runner.py` (88 Zeilen), `buildflow_store.py`, `buildflow_cli.py`, zusammen 538 Zeilen mit `buildflow_core.py`.
  5. `qwen_build.py` (292 Zeilen) für den Qwen-Code-Anschluss.

  Buildflow sollte die Skripte ersetzen („es muss kein neues Skript entstehen“, `BUILDFLOW_2026-10-13.md:22`). Einen Tag später entstand `resume_queue.py` (LB 14.10. 07:49), und `BETRIEB.md:123` nennt weiter „eine Kette ist ein Python-Skript“. Im LB ist kein einziger Lauf über `guppi buildflow` belegt. Ob Aufgaben-Dateien existieren, konnte ich nicht prüfen (`runtime_data` liegt nicht im Repo).
- **Zwei Übernahmewege.** Dokumentiert sind das manuelle Kopieren mit `adopt_plan` (`ENTWICKLUNG.md:76`) und der E1-Weg `self-integrate` mit Rücknahme. Der E1-Weg umfasst 2.215 Zeilen in `selfdev/` und rund 660 Zeilen Tests. Er kommt in keiner Übernahme eines SEDRA-Baus im LB vor.
- **Logbuch-Regel gebrochen.** Regel 5 lautet „Jeder Schritt wird eingetragen“. Es gibt keinen Eintrag vom 15.10. 19:50 bis zum 20.10. 13:07. Dazwischen liegen BUILD_20 (19.10.), REVIEW_GESAMT, REVIEW_ARCHITEKTUR und PLAN_STUFE_C (alle 19.10.). Heute (20.10.) stehen elf Einträge, alle als `DOKU`.
- **Spec-Check prüft auf anderem Python als der Bau.** `spec_check.py:105` startet die Tests mit `sys.executable` (Host, hier 3.13), der Bau führt sie in der microVM mit älterem Python aus. Das hat bereits einen Fehler versteckt: `ast.Str` in review_report (LB 14.10. 07:49). `result ok` beweist also nur „besteht auf dem Host“.
- **`devvm_build.py` verlangt kein `spec_check ok`.** Keine Prüfung auf Referenz oder Spec-Check im Aufruf (Grep ohne Treffer). Das Verbot „ohne grüne Referenz kein Bau“ liegt nur im Text.

## 4. Zahlen

| Größe | Wert | Beleg |
|---|---|---|
| Skripte in `runtime/benchmarks/` | 84 `.py`-Dateien (plus .bat, .ps1), rund 8.500 Zeilen | Zählung |
| davon Ketten und Einmal-Läufe mit Datum im Namen | 17 (9 `day_queue_*`, 4 `night_queue_*`, 4 `mtp_*`) | Dateinamen |
| weitere Ketten und Messer | `resume_queue`, `ab_queue`, `moe_sweep`, `context_ladder`, `cuda_crash_hunt`, `rework_bench`, `small_team` und weitere | Dateinamen |
| Ordner mit Saaten, Reviews, Fixtures | 10 `*_seed`, `devvm_seeds`, `resume_seeds`, `g1_seed`, `g2_seed`, `bench_std_seed`, zwei Review-Ordner (`devvm_reviews`, `reviews`) | `ls` |
| Bau-Specs | 61 Dateien | `devvm_specs/` |
| Referenzen | 40 Ordner (21 Specs ohne gleichnamige Referenz, u. a. `am002` bis `am010`, `bench_std`, `e01` bis `e05`, `e07` bis `e09`, `e20`, `phase5_*`) | `devvm_refs/` |
| Specs mit nachgewiesener Übernahme | rund 20 (`e06`, `e10`, `e11`, `layer_summary`, `s0_conn_check`, `mcp_shield`, `core_boundary`, `vm_process`, `lesson_proposer`, `skill_unify/rank/rank3`, `am008`, sieben aus Nachtkette G) | LB, Importe in `src/` |
| Specs ohne Bau- oder Übernahme-Eintrag im LB | mindestens 9: `cchat`, `chat_diag`, `chat_store`, `window_state`, `mission_filter`, `churn_guard`, `skill_digest`, `skill_fences`, `phase5_*` | Grep im LB |
| Specs als Messaufgabe oder Test | `ag01_shop`, `bench_std`, `coin_hole`, `bg_report`, `skill_need`, `am006` bis `am010` (am009/am010 hat Claude selbst gebaut, LB 9.10. 09:12) | LB |
| Schwere Fehlschläge bei SEDRA | am003, am007 (4/7 in drei Läufen, 6.181 bis 9.538 s), assert_catalog (5.845 s, 3 Nacharbeiten, Rest durchgefallen), build_log 2/4, build_request 1/4 | LB, `AM007_LAEUFE_AUSWERTUNG` |
| Tests | 191 Dateien in `tests/`, rund 30.800 Zeilen, rund 2.600 `def test_` | Zählung |
| Tests mit `env_skip` | 25 Dateien | Grep |
| Dateien am Paket-Stamm, die nur eine 7-Zeilen-Weiche sind | 78 von 121 | Zählung |
| Quellcode Python gesamt | 43.220 Zeilen; davon von SEDRA übernommen rund 3.450 (8 %) | Zählung |
| Logbuch | 301 Zeilen, 108 KB, rund 70 verschiedene Eintragsarten | Zählung |
| Dokumente in `docs/` | 133 Dateien, davon 14 `BUILD_*`, 4 `*_PROPOSED` | `ls` |

**GPU-Zeit.** Die Zeiten stehen verstreut im LB. Nachgerechnet kommen die belegten Baulaufzeiten auf mindestens etwa 35 bis 40 Stunden (am002 bis am008: grob 20 h, davon am007 allein rund 11 h in vier Läufen, jeweils aus den Einträgen addiert; Nachtlauf 11.10. rund 7,5 h; Nachtkette G 2,5 h; assert_catalog 1,6 h; Rest kleiner). Das ist eine Untergrenze aus den Einträgen. Die Messläufe (Kontextleiter, MoE, MTP, Standardtest) sind nicht enthalten. Eine belastbare Gesamtsumme gibt es nicht, weil die Laufprotokolle unter `runtime_data/measurements/logs` nicht im Repo liegen.

**Nutzen gegen Aufwand.** Der einfache Bau gelingt schnell: Stufen mit höchstens 20 neuen Prüfungen schafft SEDRA meist im ersten Anlauf in 3 bis 10 Minuten. Alles darüber kostet das Mehrfache: assert_catalog 82 Prüfungen und 5.845 s, build_request 34 Prüfungen und zwei Fortsetzungen, am007 11 Stunden ohne Erfolg. Der Aufwand pro übernommenem Modul besteht zum großen Teil aus Spec, Tests, Referenz und Review durch Claude.

## 5. Befunde nach Schwere

### Hoch

**H1. Der Bauablauf wird nicht mehr benutzt, wo die meiste Arbeit anfällt.** Seit dem 14.10. 10:06 kein SEDRA-Bau; Builds 7 bis 24 sind ausschließlich Claude-Code (LB 14. und 15.10.). Das 50-%-Ziel gilt auf dem Papier (`ENTWICKLUNG.md:9`), gezählt wird es nicht mehr (letzte Zählung 8.10.). Ohne Entscheidung des Captains driften Regel und Praxis weiter auseinander.

**H2. Spec-Aufwand und Modell-Aufwand stehen im Missverhältnis.** Für die sechs k0-Bauten hat Claude 1.303 Zeilen Spec samt versteckten Tests und 568 Zeilen Referenz geschrieben. Die Referenz ist das ganze Produkt, das SEDRA nachbauen soll (`k0_kinds`: Referenz 125 Zeilen). Der Mehrwert liegt dann vor allem im Test des Modells, nicht in der Entlastung von Claude. Für die Ziele „SEDRA schreibt 50 % des Codes“ und „SEDRA baut sich selbst weiter“ ist das nur dann ein Gewinn, wenn die Bau-Specs deutlich billiger sind als der Code (bisher gelang das bei skill_rank, 43 Zeilen Referenz).

**H3. Mehrere Wege zum selben Bau, ohne einen führenden.** Siehe Abschnitt 3: Direktaufruf, Skripte, Agent Manager, Buildflow, qwen_build. Buildflow ist fertig gebaut, aber im LB nicht benutzt und in `BETRIEB.md`, `ARCHITEKTUR.md` und `CHANGELOG.md` nicht erwähnt. Wer baut, wählt nach Gedächtnis; die GPU-Regeln (Lease, Vorrang, Startstunde) stecken in jedem Weg anders. Beleg für das Risiko: Kette B lief am 14.10. morgens an, weil sie keine Startstunde hatte, und hielt die GPU (LB 14.10. 08:55).

### Mittel

**M1. Spec-Check und Bau laufen auf verschiedenen Pythons** (`spec_check.py:105`, LB 14.10. 07:49). Ein „result ok“ kann in der VM trotzdem scheitern. Der Bau wird nicht an `result ok` geknüpft.

**M2. Bau-Specs ohne Ergebnis.** Neun Specs oder mehr haben keinen Bau- oder Übernahme-Eintrag (Abschnitt 4). Dazu 21 Specs ohne Referenz, bei denen die Gegenprobe nicht nachprüfbar ist (teils bewusste Altlast der ersten Woche).

**M3. Logbuch lückenhaft und überladen.** Lücke 15. bis 20.10. (Regel 5). Dazu Art-Spalte uneinheitlich (`AENDERUNG`/`ÄNDERUNG`, `ART` dreimal als Kopfzeile, `HAERTUNG1/3`), Einträge mit mehreren tausend Zeichen. Wer wissen will, ob ein Modul gebaut wurde, muss suchen. `logbook.py` verhindert nur Laufwerksbuchstaben.

**M4. Regeln und Dokumente widersprechen sich.**
- `ENTWICKLUNG.md:107` (Regel 8) „Commits gehen auf `main`“ gegen Regel 12 (`:115`) „jede Sitzung auf eigenem Branch“; heute laufen sechs Spec-Sitzungen in eigenen Branches.
- `BUILDFLOW_2026-10-13.md:22` gegen `BETRIEB.md:123` und `resume_queue.py`.
- `ENTWICKLUNG.md:9` (SEDRA schreibt 50 %) gegen LB 9.10. 09:12 (Claude schreibt) ohne Nachtrag.
- Stand der Kerndokumente: `ENTWICKLUNG.md`, `ARCHITEKTUR.md`, `BETRIEB.md` tragen „Stand 12.10.2026“, enthalten aber Teile bis 14.10. Desk, Shells, GateWay und Orchestra (Spec vom 20.10.) kommen darin kaum vor (4 bis 5 Erwähnungen von „desk/shell/gateway“ je Datei).
- Spec-Dokument: K0.6 (Doku auf „Local First, Cloud Second“) ist offen.

**M5. 78 von 121 Dateien am Paket-Stamm sind 7-Zeilen-Weichen** (z. B. `candidate_tests.py`, `devvm.py`). Sie sichern alte Importe seit der Aufteilung vom 12.10. Neue Leser (und Modelle) sehen zwei Orte je Modul; `ENTWICKLUNG.md:76` verlangt deshalb ausdrücklich „die Unterpaket-Datei, nicht die Weiche“.

**M6. Der E1-Übernahmeweg ist ungenutzt.** 2.215 Zeilen `selfdev/` plus Tests, aber keine Übernahme von SEDRA-Code geht darüber. Das ist toter oder Reserve-Aufwand, solange die Übernahme von Hand läuft.

### Niedrig

**N1. Einmal-Skripte mit Datum im Namen** (17 Dateien: `day_queue_2026-10-12*`, `night_queue_2026-10-11*`, `mtp_*`), die nur noch Dokumentation sind. Ohne Verweis aus Code nur in Docs und Tests (Dateiliste per `git grep`: höchstens 2 bis 3 Treffer, meist Logbuch).

**N2. Saaten, Reviews und Fixtures verstreut** (Abschnitt 4): zwei Review-Ordner, zehn `*_seed`, drei Seed-Sammlungen.

**N3. `devvm_build.py` mit 37 Optionen**, viele davon abgeschlossene Experimente (`--plan-steps`, `--fresh-rework`, `--step-syntax-check`, `--parallel-check`, `--checker`, `--arbiter`; laut `ENTWICKLUNG.md:50` „im Test, standardmäßig aus“).

**N4. 133 Dokumente in `docs/`**, davon 14 `BUILD_*`, 8 `DEVVM_*/PHASE*_BERICHT`, vier `*_PROPOSED`. Es gibt keine Übersicht, was gilt.

**N5. Tests.** Aufbau gesund (zentral `env_skip.py`, 33 Tests mit Grund übersprungen, LB 14.10. 11:58; `host_isolation`). Nicht geprüft: Laufzeit, Doppelungen und einzelne reine Umgebungstests. Auffällig sind nur `test_night_modules.py` (lässt die versteckten Tests übernommener Module erneut laufen; das ist gut) und acht Dateien, die Spec-Dateien lesen. Die Suite hat Entwicklerprüfungen und Spezifikationstests im selben Ordner; das ist unkritisch.

## 6. Die heutigen Bau-Specs gegen bisherige Erfolge

Verglichen sind versteckte Prüfungen je Stufe (kumulativ, `assert` und `raises(`) und Länge der Aufgabe.

| Spec | Stufen | neue Prüfungen in der größten Stufe | Referenz (Zeilen) | Bekanntes Ergebnis |
|---|---|---|---|---|
| skill_rank3 | 3 | 6 / 6 / 6 | 89 | 3/3 in 170 s |
| skill_rank | 4 | 19 / 9 / 12 / 11 | 43 | 4/4 in 263 s |
| skill_unify | 4 | 12 / 8 / 8 / 15 | 72 | 4/4 in 421 s, 1 Nacharbeit |
| gate_bar | 4 | 17 / 12 / 9 | 81 | 4/4 in 546 s |
| e06_bg_jobs | 3 | 32 / 23 / 0 | 120 | erster Lauf nicht bestanden, mit Saat und Review 3/3 in 2.951 s |
| build_request | 4 | 12 / 13 / 4 / 5 | 741 (mit Saat) | 1/4, dann Fortsetzung 1.599 s |
| assert_catalog | 4 | 34 / 21 / 20 / 7 | 278 | Stufe „rest“ nach 3 Nacharbeiten durchgefallen, 5.845 s |
| **k0_kinds** | 3 | **39 / 43 / 19** | 125 | noch nicht gebaut |
| k0_extensions | 2 | 18 / 6 | 47 | noch nicht gebaut |
| k0_orchestra_config | 3 | 35 / 12 / 17 | 94 | noch nicht gebaut |
| k0_orchestra_store | 3 | 14 / **64** / 22 | 127 | noch nicht gebaut |
| k0_orchestra_service | 2 | 37 / 0 | 85 | noch nicht gebaut |
| k0_orchestra_kinds | 2 | 37 / 29 | 90 | noch nicht gebaut |

**Einschätzung.**
- Die Aufgabentexte sind genau (Fehlertexte wörtlich, Reihenfolge und Randfälle benannt) und folgen den Lehren (reine Logik, nichts importieren, Leser und Verben werden übergeben, keine Regel späterer Stufen).
- Die Größe liegt am oberen Rand dessen, was SEDRA bisher im ersten Anlauf geschafft hat. Die Stufe `view` von k0_kinds (43 neue Prüfungen) und die Stufe `schema` von k0_orchestra_store (64 neue Prüfungen, 3.724 Zeichen Aufgabe) sind größer als jede bisher bestandene Einzelstufe. Das Muster aus `AM_BAU_FEHLERANALYSE` (3 bis 6 Verhalten pro Stufe gelingen, 10 und mehr nicht) gilt hier wieder: Die Stufe `view` hat 6 Verben/Regeln in einem Absatz und viele Fehlerfälle.
- `k0_orchestra_store` ist am schwierigsten (SQLite, Schema, WAL, Transaktionsregeln) und sollte nicht zuerst laufen. `k0_extensions` und `k0_orchestra_config` sind die kleinsten und besten Kandidaten für einen Anlauf ohne Nacharbeit.
- Die Referenzen sind klein (47 bis 127 Zeilen). Damit ist die Aufgabe lösbar, aber der Nutzen eines SEDRA-Baus ist klein (siehe H2).

## 7. Ist der Bau von k0_kinds um 18 Uhr sinnvoll?

**Ja, als begrenzter Test; nicht als Nachweis, dass alle sechs Specs so laufen.**

Dafür spricht:
- `spec_check` heute: `result ok` (von mir bestätigt). Die Spec ist ohne Abhängigkeit zu Harness oder Desk, nur Standardbibliothek.
- Der Aufgabentext ist präzise, drei Stufen, Referenz 125 Zeilen.
- G3-S0-02 ist erteilt (LB 20.10. 13:49).
- Es wäre der erste SEDRA-Bau seit sechs Tagen; er zeigt, ob Setup und Methode noch funktionieren.

Dagegen oder zu beachten:
- Die Stufe `view` ist größer als jede bisher im ersten Anlauf bestandene (43 neue Prüfungen). Erwartung: erster Anlauf Stufe `register` besteht, `view` braucht eine bis drei Nacharbeiten oder scheitert; Dauer grob 30 bis 90 Minuten, im ungünstigen Fall wie assert_catalog rund 100 Minuten.
- `spec_check` lief auf dem Host-Python; die VM hat ein älteres Python (LB 14.10. 07:49). Vor dem Bau gilt: einmal die Referenz in der VM laufen lassen (kostet keine GPU), sonst kann eine Stufe wegen des Pythons scheitern.
- Stand der Maschine: Ich habe nicht geprüft, ob die GPU frei ist, ob der Canary durchläuft und ob die Engine b11160 so eingestellt ist wie in `ENTWICKLUNG.md:42-44` verlangt. Auch nicht, ob andere Sitzungen die Lease halten.

Vorschlag für den Rahmen:
1. Nur `k0_kinds`, nicht die Kette der sechs. Ergebnis erst nach Review bewerten.
2. Standardbefehl aus `ENTWICKLUNG.md:42-44` mit `--attempts 1`, ohne `--keep-going`, Pidfile, Lease-Vorrang normal.
3. Abbruchgrenzen im Voraus: Wenn nach Stufe `view` mit 3 Nacharbeiten kein Erfolg, Stopp; vor jeder weiteren Nacharbeit `spec_check --tree` (liegt der Fehler in der Spec?).
4. Danach Logbuch-Eintrag (Zeit, Dauer, Aufrufe, Nacharbeiten, GPU-Zeit) mit `logbook.py add BAU`.
5. Zählung mitführen: Zeilen von SEDRA gegen Zeilen von Claude für diese Aufgabe (Spec, Tests, Referenz, Review, Übernahme).
6. Erst danach entscheiden, ob `k0_extensions` und `k0_orchestra_config` folgen. `k0_orchestra_store` zuletzt oder in kleinere Stufen schneiden.

## 8. Vorschläge als Gate (alles Vorschläge, einzeln zu entscheiden)

| Gate | Vorschlag | Aufwand | Nutzen |
|---|---|---|---|
| **ANA-01** | **Einen Bauweg festlegen.** `guppi buildflow` (oder `devvm_build.py` direkt) als einzigen Weg bestimmen; Eintrag in `ENTWICKLUNG.md` und `BETRIEB.md`; `resume_queue.py`, `night_queue_*`, `day_queue_*` als „Archiv“ kennzeichnen (nicht löschen). | klein (1 bis 2 h) | beendet H3, Lease und Startstunde an einer Stelle |
| **ANA-02** | **Spec-Check in der VM.** `spec_check.py` führt die Referenz zusätzlich in der microVM aus (Flag `--vm`), `devvm_build.py` verlangt einen Stempel `spec_check ok` für die Spec-Datei (Hash) und bricht sonst ab (Ausnahme per Option). | mittel (halber Tag) | schließt M1 und die Lücke „ohne grüne Referenz kein Bau“ |
| **ANA-03** | **Messbare SEDRA-Quote.** `code_meter` je Monat und je Aufgabe (SEDRA gegen Claude, inklusive Spec und Referenz) als Zeile im Logbuch; Ziel „50 %“ entweder bestätigen oder auf einen Wert für „neue Module mit klarer Schnittstelle“ ändern. | klein bis mittel | macht H1/H2 sichtbar und entscheidbar |
| **ANA-04** | **Stufengröße begrenzen.** `spec_standards` um eine Regel erweitern: höchstens 20 neue Prüfungen je Stufe, Warnung ab 30 (Maßstab aus Abschnitt 6); `k0_kinds.view` und `k0_orchestra_store.schema` danach teilen. | klein (Regel) bis mittel (Spec teilen) | höhere Trefferquote im ersten Anlauf |
| **ANA-05** | **Ketten und Einmal-Skripte aufräumen.** 17 Dateien mit Datum im Namen und `ab_queue`-Vorläufer nach `benchmarks/archiv/` verschieben, mit Hinweis in der README; Tests und Docs anpassen, die darauf verweisen. | klein (1 bis 2 h) | weniger Wildwuchs; `benchmarks/` von 84 auf rund 65 Dateien |
| **ANA-06** | **Specs ohne Ergebnis abschließen.** Für `cchat`, `chat_diag`, `chat_store`, `window_state`, `mission_filter`, `churn_guard`, `skill_digest`, `skill_fences`, `phase5_*` je entscheiden: bauen, verschieben nach `devvm_specs/archiv/` oder streichen; Liste im Logbuch. | klein (Entscheidung), mittel (falls gebaut) | beendet M2 |
| **ANA-07** | **Logbuch und Doku auf Stand bringen.** Nachtrag 15. bis 20.10. (Builds 20 bis 24, Reviews vom 19.10.); Art-Spalte auf eine feste Liste von rund 10 Arten; `ENTWICKLUNG.md`, `BETRIEB.md`, `ARCHITEKTUR.md` auf Stand 20.10. (Regel 8 gegen 12 klären, Buildflow, Desk/Shells, Orchestra). | mittel (halber Tag) | beendet M3/M4; `logbook.py` könnte die Art prüfen |
| **ANA-08** | **Weichen am Paket-Stamm entscheiden.** Die 78 Weichen bis zu einem Stichtag behalten, danach Importe in Code und Tests auf die Unterpakete umstellen und die Weichen entfernen (mit Prüfung per `git grep`). Bis dahin eine Zeile in `ENTWICKLUNG.md` als Warnung. | mittel (Tag) bei Entfernung, klein bei Dokumentation | M5 |
| **ANA-09** | **E1-Übernahmeweg bewerten.** Entscheiden, ob `self-integrate` der Standardweg für SEDRA-Module wird (dann zuerst mit `k0_kinds` erproben) oder ob `adopt_plan` plus Handkopie der offizielle Weg ist und `selfdev/` als Reserve markiert wird. | klein (Entscheidung), mittel (Erprobung) | M6 |
| **ANA-10** | **`devvm_build.py` entschlacken.** Optionen aus abgeschlossenen Messungen (`--plan-steps`, `--fresh-rework`, `--step-syntax-check`, `--parallel-check`, `--checker`, `--arbiter`) hinter ein `--experimental`-Flag stellen oder ausbauen; Standardbefehl als Profil `--profile standard` (ersetzt die 9 Flags). | mittel | N3, weniger Bedienfehler |

Reihenfolge, wenn nur wenig Zeit ist: ANA-01, ANA-07, ANA-02, ANA-03. Die übrigen sind unabhängig und können später folgen.

## 9. Offene Fragen an den Captain

- Gilt das 50-%-Ziel noch (ANA-03), oder gilt es nur für Module mit klarer Schnittstelle?
- Soll Claude bei UIX- und Harness-Arbeit weiter selbst bauen (wie seit dem 9.10. und 14.10.)? Dann Regel in `ENTWICKLUNG.md` anpassen statt sie zu ignorieren.
- Soll der E1-Weg (`self-integrate`) für die k0-Module benutzt werden (ANA-09), oder bleibt es bei Handkopie?

## 10. Nicht geprüft

- Laufdaten unter `runtime_data/` (Messprotokolle, Buildflow-Aufgaben, Kandidaten, Snapshots): nicht im Repo. Alle GPU-Zeiten und Ergebnisse stammen aus dem Logbuch.
- Ob `guppi buildflow` je benutzt wurde, und ob die sechs k0-Bauten schon Läufe hatten.
- Laufzeit der Test-Suite und ihr aktueller Stand (nicht ausgeführt). Zahlen zur Suite aus dem Logbuch (2.093 Tests am 15.10.) und aus der Zählung der `def test_` (rund 2.600, gezählt über alle Dateien einschließlich Hilfsklassen).
- Einzelne Tests auf „prüft nur die Umgebung“ und Doppelungen unter den 191 Testdateien.
- Zustand der Maschine heute: GPU, Canary, Engine, Lease, Modellserver.
- Inhalt von `docs/` außerhalb der genannten Dokumente (rund 110 Dateien nur nach Namen und Stichworten gesichtet).
- Ob das Python der microVM zu den Referenzen von k0_kinds passt (nur indirekt aus LB 14.10. bekannt).
- Wirkung der Fassade `agent_manager` auf den Bau in der Praxis (nur `run_worker.py` und `devvm_runtime.py` überflogen).
- Die JS/CSS-Dateien der UIX: ob und wie viele davon von SEDRA stammen.
