---
name: sedra-spec-schreiben
description: Eine Bau-Spec für SEDRAs lokale Modelle schreiben - Aufgabe in Stufen, versteckte Tests, Referenz, Saat und Stempel (benchmarks/devvm_specs, devvm_refs, spec_check.py). Nutzen, wenn eine Aufgabe an SEDRA zum Bauen gegeben werden soll, wenn versteckte Tests oder eine Referenz geschrieben oder geschärft werden, wenn spec_check Fehler meldet oder wenn ein Bau an der Spec statt am Modell gescheitert sein könnte.
---

# Bau-Spec schreiben

Das Modell sieht nur den Aufgabentext und den Arbeitsbereich. Richter ist allein der versteckte Test; von Modellen geschriebene Prüfungen waren unzuverlässig (0 von 4). Eine schwache Spec lässt falschen Code durch, eine falsche kostet GPU-Zeit: sieben falsche Erwartungen in sechs Specs und ein Stufentest, der die Regel einer späteren Stufe brauchte, haben das gezeigt. Deshalb beweist eine Referenz die Tests, bevor ein Modell läuft.

Vor der Spec stehen die Gates: Anforderungen (G1), Design (G2), Bau (G3). Jedes entscheidet der Captain. Fragen mit einem Vorschlag stellen.

## Lohnt sich die Spec?

Sind Spec, Tests und Referenz zusammen größer als der Code, den sie verlangen, schreibt Claude das Teil direkt (Regel V4) und trägt es im Logbuch als eigene Zeilen ein.

## Dateien

| Was | Wo (unter `runtime/benchmarks/`) |
|---|---|
| Spec | `devvm_specs/<name>.py` |
| Referenz | `devvm_refs/<name>/` (die Lösung, die jeden Test besteht) |
| Saat, falls auf vorhandenem Code aufgebaut wird | `<name>_seed/`, in der Spec als `SEED = "benchmarks/<name>_seed"` |

Als Vorlage eine kleine vorhandene Spec kopieren, zum Beispiel `devvm_specs/skill_rank3.py` oder `bench_std.py`. Eine Spec enthält `NOTES` (Regeln für das Modell), die Testtexte und die Liste `STAGES`. Jede Stufe hat `name`, `task` und `hidden` (Dateiname des Tests und sein Text), meist mit `no_own_check: True`.

Die versteckten Tests liegen nie im Arbeitsbereich des Modells.

## Regeln für die Aufgabe

- **Alles Nötige mitgeben.** Schemata, Feldnamen und Regeln stehen in `NOTES` oder in der Saat. Fehlen sie, erfindet das Modell Strukturen (Factory-Bau v4 und v5). Für Schemata erzeugt `regeln_aus_schema.py` Regelblätter.
- **Kleine Stufen.** Höchstens etwa 20 neue Prüfungen je Stufe; über 20 warnt `spec_check`, über 30 ist es ein Fehler. Eine Stufe mit 30.000 Token Code ist für ein Fenster von 32k zu groß.
- **Genaue Sprache.** Namen, Parameter, Rückgabewerte und Ausnahmen ausschreiben. Aufträge der Form "alter Text wird neuer Text" mit erwarteten Zahlen gelingen in einer Antwort.
- **Keine eigenen Tests verlangen.** Sie kosten Zeit und finden die Fehler nicht.
- **Höchstens eine Lektion** aus der Wissensbasis je Aufgabe. Mehr verschlechtert kleine Modelle.

## Regeln für die versteckten Tests

- **Eine Prüfung je `assert`.** Keine Ketten mit `and`: der Fehlerbericht nennt sonst nicht, welcher Teil falsch war. Kein `or`: das ist ein schwacher Test, `spec_check` lehnt ihn ab.
- **Rückgabewerte prüfen**, nicht nur, dass ein Aufruf nicht abbricht. Ein Bau hat schwache Prüfungen bestanden und die geschärften nicht.
- **Fehlerfälle und Grenzen:** leere Eingabe, `None`, falscher Typ, unbekannte Schlüssel. Bei Schemaregeln ein Negativfall je Regel.
- **Die Randfälle nennen, die der Coder sonst übersieht** (Katalog in `docs/CODER_PROFIL_UND_WORKFLOW_2026-11-11.md` §4): ein Wert im Eintrag, der vom berechneten abweicht (sonst fällt „neu berechnen“ nicht auf); `²` und `٣` wo Ziffern geprüft werden; dasselbe Muster mitten im Pfad und als Vorsilbe; Namen wie `constructor`, `__proto__`, `hasOwnProperty` als Schlüssel; Objekte ohne Prototyp (JavaScript); Listen und dicts, wo ein Text erwartet wird; die eigene Fehlermeldung wörtlich. Im Nachtlauf bestanden 6 von 9 Kandidaten die ungeschärften Tests mit genau diesen Fehlern.
- **Gegenprobe vor dem Stempel:** die Tests gegen bewusst naive Varianten laufen lassen (`--tree`); sie müssen durchfallen.
- **Keine Regel einer späteren Stufe voraussetzen.** Der Test von Stufe 2 muss auf dem Stand nach Stufe 2 bestehen.
- **Die Saat muss an Stufe 1 scheitern.** Sonst beweist der Bau nichts.
- Der Test läuft als `python <datei>` im Arbeitsbereich; Exit-Code 0 heißt bestanden.

## Prüfen und stempeln

Im Ordner `runtime`:

```
.venv\Scripts\python.exe benchmarks/spec_check.py <name>
.venv\Scripts\python.exe benchmarks/spec_check.py <name> --vm --project <projekt>
```

Der erste Aufruf prüft Form, Referenz und Größe auf dem Host. Der zweite prüft zusätzlich im Python der microVM und schreibt den Stempel nach `<projekt>/runtime_data/spec_stamps/<name>.json`. Ohne Stempel startet kein Bau (`spec_not_checked`). Die microVM hat ein älteres Python als der PC; was nur auf dem Host läuft, fällt dort auf.

Weitere Prüfungen: `--seed <ordner>` (Stufe 1 muss scheitern), `--tree <ordner> --host-ok` (welche Stufentests ein Kandidat besteht), `--snapshots <ordner>` (jeder Stufentest gegen seinen eigenen Zwischenstand). `spec_testnames.py` prüft die Testnamen von Abnahmetabellen.

Jede Änderung an Spec, Referenz oder Saat macht den Stempel ungültig. Dann neu prüfen.

## Danach

Der Bau läuft mit dem Skill `sedra-bau-starten`. Scheitert eine Stufe nach allen Nacharbeiten, zuerst den versteckten Test gegen den Kandidaten laufen lassen: der Fehler kann in der Spec liegen. Den Befund ins Logbuch (`benchmarks/logbook.py add SPEC "Text" --ref "Datei"`).
