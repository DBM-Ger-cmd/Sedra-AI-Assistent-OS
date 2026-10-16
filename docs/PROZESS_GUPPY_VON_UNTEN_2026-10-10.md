# Prozess für GUPPIs Entwickler-Workflow: von unten nach oben (2026-10-10)

Anlass (Captain): Wir wissen jetzt, wo die Fehler liegen. In little-coder und Hermes lagen die Hauptfehler bei **Modell und Anbindung**, nicht bei den Agenten. Daraus soll ein eigener Prozess für GUPPI werden. Die Hermes-Erfahrungen des Captains sind hier noch nicht im Einzelnen eingearbeitet (mir liegen nur seine Aussage und unsere eigenen Funde vor, siehe unten).

## Der Befund aus unseren Läufen
`benchmarks/failure_layers.py` sortiert jeden Solo-Entwicklerlauf nach der Schicht, auf die sein Ende zeigt (Auswertung der Protokolle von heute: am007 A/B/C, am009, Standardtest; 82 Läufe):

| Schicht | Läufe | Zeit | erzeugte Token |
|---|---|---|---|
| 1 Server/Modell (Absturz, Müllausgabe) | 0 % | 0 % | 0 % |
| 2 Anbindung (HTTP 4xx, keine Werkzeugaufrufe, kaputte Argumente) | 5 % | 7 % | 8 % |
| 3 Modellverhalten (`answer_cut`, `runaway`, `loop`) | 16 % | 30 % | 33 % |
| 4 Agenten-Budget (Rundenlimit, Zeitlimit) | 21 % | 35 % | 33 % |
| 5 Verständnis (abgegeben, Abnahmetest fällt durch) | 13 % | 14 % | 11 % |
| in Ordnung (abgegeben, Stufe bestanden) | 45 % | 15 % | 16 % |

Lesart:
- **Zwei Drittel der Zeit und der Token** (Schichten 3 und 4) gehen in Läufe, die gar nichts abgeben: das Modell wird abgeschnitten, wiederholt sich, oder verbraucht seine 45 Runden. Nicht in falsche Antworten (Schicht 5: 14 % der Zeit).
- Schicht 2 war im ersten am007-Lauf mit 30 % der Zeit noch der größte Einzelposten und ist nach den Korrekturen von heute (4xx kein Absturz, Fensterkürzung) in den Läufen B und C auf **0** gesunken. Das ist die Bestätigung der Aussage des Captains: die Unterschicht hat am meisten bewegt.
- Schicht 1 ist heute 0 %, weil Flash Attention aus ist und die gewählten Modelle laufen; die Funde der letzten Tage (Jan: CUDA-Absturz mit Flash Attention, Gemma: `<unused49>`-Müll, DeepSeek-V2-Lite: Chat-Vorlage kennt keine Werkzeuge, Hermes-4-14B 1/4) lagen alle in Schicht 1 und 2.

## Der Prozess (von unten nach oben)
Grundregel: **Ein Fehler wird in der untersten Schicht behoben, in der er sichtbar ist. Eine höhere Schicht wird erst gemessen, wenn die darunter grün ist.** Jede Schicht hat eine eigene Prüfung, eigene Kennzahl und einen Verantwortlichen im Code.

| Stufe | Schicht | Prüfung vor jeder Messung | Kennzahl | Stand |
|---|---|---|---|---|
| S0 | Server und Modell, Anbindung | **Anbindungsprüfung** je Rezept: Start ohne Absturz über N Anfragen; Werkzeugaufruf-Rundlauf (die Vorlage kennt Werkzeuge); lange Argumente (6.000 Zeichen) kommen unverändert an; Fenster zu 90 % gefüllt geht, darüber wird sauber abgelehnt; Prompt-Cache trifft bei gleichem Anfang; keine Müllausgabe; keine Wiederholungsschleife bei der gewählten Temperatur | bestanden / nicht bestanden je Rezept, gespeichert beim Rezept | Teile vorhanden (`cuda_crash_hunt`, `garbage_hunt`, `answer_cut_probe`, `moe_sweep`); **zusammenführen, fehlt** |
| S1 | Werkzeuge | Einheitentests für Verhalten, das für kleine Modelle gemacht ist: Schreiben statt Ersetzen, mehrere Änderungen, Lesen in Teilen, `outline`, Fehlermeldungen mit Rezept | Tests grün | gebaut, 162 Tests |
| S2 | Schleife und Wächter | Budgets aus dem Fenster abgeleitet, Kürzen, eine Korrektur vor Ende, Rückgriff auf den letzten Stand, Zurücksetzen des Schleifenwächters | Tests grün; `prompt_peak`, `nudges` je Lauf | gebaut |
| S3 | Modell-Qualifikation | Standardtest `bench_std` (4 Stufen) **mit Schichtenbericht** | Stufen, Zeit, Verteilung nach Schichten | Test läuft; Schichtenbericht neu |
| S4 | Workflow (Solo, Plan, Prüfumfang, Rework) | nur wenn S0 bis S3 für das Rezept grün sind; Einzelstufe mit Zwischenstand, mehrere Wiederholungen je Variante | bestandene Versuche / Versuche, Zeit, Anteil Schicht 3 und 4 | Zwischenstände fehlen noch |
| S5 | Aufgaben und Tests (Claude) | Stufen so schneiden, dass eine Stufe mit etwa 100 Zeilen Code lösbar ist; Regeln mit Beispiel je Fall; Tests mit Nummer der Anforderung, lesbarer Fehlerbericht | Anteil Schicht 5 | teilweise (Bericht lesbar) |

Jede Messung (jeder Lauf) bekommt automatisch die Schichtentabelle in die Ergebnisdatei und die Vergleichstabelle. Ein Fix zählt, wenn der Anteil **seiner** Schicht sinkt, nicht wenn ein Gesamtergebnis zufällig besser aussieht (Einzelläufe sind Zufall, siehe am007 `rules`).

## Was wir von little-coder lernen
- **Werkzeuge für das Modell zuschneiden, nicht den Ablauf aufblähen:** Write-Verbot, `edits[]`, Lese-Schutz, Fehlermeldung mit fertigem Beispiel; kleine Werkzeug-Karten; fester Systemtext (Cache); Korrektur statt Abbruch. Fast alles ist Schicht 1 bis 3.
- **Ein gesunder Start beweist nicht, dass die Konfiguration trägt** (Hinweis in deren README zu einem Modell, das lädt und nichts erzeugt): daher S0 als Pflicht vor jeder Messung.
- **Wenige Agenten:** nur lesende Unter-Coder; die Last trägt ein Entwickler mit guten Werkzeugen. Das hat unser Rückbau von Team auf Solo bestätigt.
- Bei Hermes (Captain): Modell und Anbindung waren die Hauptfehler. Bitte eure konkreten Fälle nachtragen; ich übernehme sie in S0 als Prüfpunkte.

## Wo der Plan in diesem Prozess steht
Der Plan gehört zu **S4/S5**: Er strukturiert die Arbeit (Reihenfolge, Grenze, Zuordnung Anforderung zu Code, Bericht je Anforderung), er behebt kein Anbindungsproblem. Er wird erst gegen die schnelle Variante gemessen, wenn S0 bis S3 grün sind.

## Nächste Schritte
1. Schichtenbericht in jede Messdatei und in `model_compare` (klein, `failure_layers.py` ist da).
2. `connection_check.py` (S0) bauen und je Rezept ausführen; Ergebnis beim Rezept speichern.
3. Zwischenstände je Stufe (nach dem Standardtest).
4. Danach Einzelstufen-Messungen für die Schichten 3 und 4: Selbstprüfungsumfang, `write_file`-Verbot, Temperatur, Denk-Budget.
5. S5: Stufen schneiden und Anforderungsnummern in die Tests (Claude).
