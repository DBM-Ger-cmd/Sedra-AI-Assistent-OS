# Workflow-Optimierung ohne Qualitätsverlust (Maßnahme für die Zukunft, Idee des Captains 2026-10-06)

Stand: **Plan, nichts gebaut.** Reihenfolge: erst messen, dann ändern, jede Änderung gegen die Qualität absichern.

## 1. Wo die Zeit heute hinläuft (Eskalationsmodus, `rework8`, zwei Läufe zu je 16 Aufgaben)
| Anteil | Lauf 1 (1826 s) | Lauf 2 (2124 s) |
|---|---:|---:|
| Starker Entwickler (nur in 4 von 16 Läufen) | 42 % | 45 % |
| Checker (Qwen3-Coder schreibt den Check) | 31 % | 32 % |
| Modell laden und wechseln | 13 % | 11 % |
| Jan allein | 6 % | 5 % |
| Schlichter | – | 2 % |

Jan kostet fast nichts. Teuer sind der starke Entwickler (190 bis 250 s je Einsatz), der Check (40 bis 130 s, bei großen Aufgaben bis 400 s) und das Laden. Beim Bau von `devvm_view.py` (große Aufgabe) kamen dazu ein unbrauchbarer Check und viele vergebliche Runden.

## 2. Maßnahmen, nach erwartetem Nutzen
1. **Aufgabenumfang entscheidet den Weg:** kleine Fehlerbehebung → Eskalation (Jan allein); große Aufgabe mit vielen Anforderungen → Planer teilt in Schritte (Pipeline) und das starke Modell baut direkt. Der Umfang wird aus Textlänge und Zahl der Anforderungen geschätzt. Spart die vergeblichen Jan-Runden und Checks bei großen Aufgaben.
2. **Prüfungen stapeln statt je Aufgabe wechseln:** in einer Testreihe erst alle Jan-Versuche, dann alle Checks, dann alle starken Versuche. Modellwechsel je Aufgabe 2 → je Stapel 2 (spart die 11 bis 13 % Ladezeit, nur in Testreihen, nicht im Einzelauftrag).
3. **Check schneller und besser:** Denken des Checkers begrenzen (kurze Antwort, ein Assert je Beispiel), Check-Vorlagen aus der Wissensbasis nach Aufgabenart. Ziel: weniger Fehlurteile (zu schwache Checks haben 3 von 32 Läufen falsch durchgelassen).
4. **Prompt-Cache der Server nutzen:** gleiche Systemtexte und Werkzeugbeschreibungen bleiben vorn im Prompt, damit llama.cpp sie nicht neu verarbeitet. Erst messen, ob `cache_prompt` schon wirkt.
5. **Früher abbrechen:** gleicher Fehler zweimal → Schlichtung (gebaut); zusätzlich Gesamtbudget je Auftrag, damit kein Lauf 17 Minuten für einen Misserfolg braucht.
6. **Gleiches Modell für Helfer** (`same_model`, gebaut, noch nicht gemessen).

## 3. Absicherung der Qualität
Jede Änderung läuft gegen dieselbe Aufgabenmenge, und der Hidden-Erfolg darf nicht unter dem Ausgangswert liegen (Eskalation: 29 von 32). Dafür braucht es die Holdout-Menge und die Schwellen aus dem Testmodul (`TESTMODUL_VORBEREITUNG_2026-10-06.md`); ohne sie wäre das Tuning wieder an `rework8` überangepasst.

## 4. Nicht tun
- Den Check weglassen, um Zeit zu sparen: er ist das Urteil, das Jans Ergebnisse trägt.
- Die Schlichtung großzügiger machen: sie könnte falschen Code durchlassen.
