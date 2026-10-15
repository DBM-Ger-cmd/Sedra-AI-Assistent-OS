# am007 (Besatzungs-Planer): drei Läufe mit Qwen3.6 im Vergleich (2026-10-10)

Aus den Lauf-Protokollen berechnet (pro Stufe: Entwicklerläufe, Aufrufe, erzeugte Token, Enden der Läufe). Die Journale der einzelnen Aufrufe (welches Werkzeug, wie oft) wurden von diesen Läufen **nicht gespeichert**; das schreibt `devvm_build.py` erst seit 14:20 (`agent_detail` mit `tool_counts`). Die Aussagen über Hilfsdateien stammen aus den Aufräumzeilen des Protokolls.

| Lauf | Aufbau | Dauer | Stufen bestanden | Erzeugte Token | Bestanden |
|---|---|---|---|---|---|
| A (09:00) | solo, Verlauf nicht gekürzt, ohne Plan | 6181 s | 4/7 | etwa 198.000 | basics, slots, graph, rules |
| B (10:31) | solo, Kürzen im Lauf, ohne Plan | 8587 s | 4/7 | etwa 254.000 | basics, slots, graph, rules |
| C (13:10) | solo, Kürzen, Schritt-Plan (verbessert) | 9538 s | 4/7 | etwa 281.000 | basics, slots, graph, assemble_global |

Pro Stufe (Dauer s / erzeugte Token / Enden der Entwicklerläufe):

| Stufe | A | B | C |
|---|---|---|---|
| basics | 99 / 2.700 / hand_in | 157 / 4.900 / hand_in | 118 / 2.800 / 2 hand_in |
| slots | 267 / 11.400 / hand_in | 196 / 8.100 / hand_in | **1418 / 44.400** / 2 hand_in, 1 time |
| graph | 570 / 22.700 / loop | 512 / 19.200 / hand_in | 744 / 18.100 / hand_in, turns |
| rules | 711 / 37.800 / answer_cut, 2 hand_in | 424 / 14.900 / hand_in | **durchgefallen** 694 / 37.100 / 2 hand_in, 2 turns, runaway |
| assemble_basic | durchgefallen 559 / 63.200 / 2 error, answer_cut, hand_in | durchgefallen 920 / 56.600 / turns, 2 hand_in, runaway | durchgefallen 431 / 25.800 / 2 hand_in, 3 turns |
| assemble_global | durchgefallen 608 / 46.300 / answer_cut, turns, 2 error | durchgefallen 1207 / 111.500 / time, 3 loop | **bestanden** 1586 / 44.700 / hand_in, 2 turns |
| all | durchgefallen 154 / 14.500 | durchgefallen 489 / 39.000 | durchgefallen 802 / **108.000** / hand_in, 2 turns, 2 answer_cut |

## Was daraus folgt
1. **Der Schritt-Plan ist nicht nachweislich besser.** Gleiche Zahl bestandener Stufen (4/7), 10 % bis 55 % mehr Zeit, mehr Token. Er bestand `assemble_global`, an der A und B scheiterten, fiel aber bei `rules` durch, die A und B bestanden, und machte `slots` fünfmal langsamer (zwei Schritte, der zweite lief ans Zeitlimit mit 39.000 Token).
2. **Ein Lauf je Variante reicht nicht.** `rules` bestand in zwei Läufen und fiel im dritten durch, `assemble_global` umgekehrt. Mit nur einem Versuch je Variante messen wir überwiegend Zufall. Ein am007-Lauf kostet 2 bis 3 Stunden; für Vergleiche brauchen wir Einzelstufen mit Wiederholungen (siehe unten).
3. **Die Zeit steckt in den fehlgeschlagenen Stufen.** Die Stufen `assemble_basic`, `assemble_global` und `all` verbrauchen in jedem Lauf den größten Teil der Token (bis zu 111.000 für eine Stufe). Rework 1 bis 3 erzeugen jeweils 20.000 bis 35.000 Token und enden oft am Rundenlimit (45), am Zeitlimit oder als abgeschnittene Antwort (`answer_cut`). Von den Entwicklerläufen in C endeten 10 von 18 am Rundenlimit, in A und B etwa 3 und 2.
4. **Hilfsdateien:** Der Entwickler legt in den schweren Stufen immer wieder `check_*.py` und `debug_*.py` an (in C bis zum Ende 9 allein im ersten Teil). Das passt zur Vermutung, dass die Selbstprüfung Runden frisst; die Messung dazu (Standardtest `solo`, `solo-light`, `solo-none`) läuft.
5. **Rückgriff greift:** `rescue` hat mehrfach eine nicht parsbare Hilfsdatei nach einem Rundenlimit gelöscht (check_crew.py, debug_assemble.py, check_assemble.py).

## Fehlerbericht war an einer Stelle noch blind
Die Stufen `rules` und `all` in C scheiterten mit `AssertionError: an invalid crew has no levels`: der Test prüft in einer Schleife (`for bad in (...)`, `try / except ValueError / else: raise AssertionError`), ob `step_levels` für drei ungültige Besatzungen `ValueError` wirft. Die Meldung nennt nicht, welcher Fall fehlt; der Bericht für die Nacharbeit zeigte nur die Zeile. Behoben (2026-10-10, nach dem Lauf): der Treiber meldet jetzt bei einem Abbruch des Prüfskripts die Zeile **und die Werte der Variablen** an dieser Stelle (hier `bad=...`), sodass sichtbar wird, welcher Fall durchfällt. Kommt erst in künftigen Läufen zum Tragen.

## Nächste Schritte (Vorschlag)
a) Standardtest mit den Prüf-Modi abwarten (läuft, Gate HG-5200D203).
b) Pro bestandener Stufe einen **Zwischenstand speichern** (`devvm_snapshots/<spec>/.../after_<stufe>`), damit eine schwere Stufe mit `--only <stufe> --seed <Zwischenstand>` allein und mehrfach getestet werden kann (statt 2 bis 3 Stunden je Lauf etwa 15 bis 30 Minuten je Versuch).
c) Rework begrenzen: nach zwei erfolglosen Reworks mit hohem Tokenverbrauch nicht noch einen dritten Lauf auf demselben Weg, sondern frischen Neustart der Stufe mit Bericht (Option `--fresh-rework` ist gebaut, ungemessen).
