---
name: sedra-nachtlauf
description: Einen unbeaufsichtigten Nachtlauf von SEDRA planen, absichern, starten und am Morgen auswerten (Nachtplan, Freigaben vorab, Protokoll, Bau, Messung, Testsuite, nichts integrieren). Nutzen, wenn der Captain "Nachtlauf", "über Nacht laufen lassen", "lass das bis morgen früh laufen" sagt, wenn ein langer Lauf ohne Aufsicht geplant wird oder wenn das Ergebnis einer Nacht ausgewertet werden soll.
---

# Nachtlauf

In der Nacht ist niemand da, der nachfragt oder abbricht. Alles, was ein Ja braucht, wird deshalb vorher geklärt, und der Lauf darf nichts tun, was sich nicht zurücknehmen lässt. Frühere Nächte liefern die Gründe: ein harter Neustart des PC mitten in einer Messung, Ketten, die nach dem Neustart tot waren, und Wiederholungen ohne Befund.

Platzhalter: `<umgebung>` ist der Ordner über dem Repo.

## Plan (vor der Nacht)

Der Plan liegt als Entwurf unter `<umgebung>\KOORDINATION_SEDRA\09_PLAN\NACHTPLAN_<JJJJ-MM-TT>_ENTWURF.md` und wartet auf die Freigabe des Captains. Er enthält:

- Ziel der Nacht und die Aufträge aus dem Register, die es betrifft.
- Eine Tabelle: Zeit, wer, was, erwartetes Ergebnis. Zuerst die Vorprüfung, am Ende der Abschlussbericht.
- Die Endzeit. Kein Schritt startet danach.
- Die Sicherheiten (siehe unten).
- Die offenen Entscheidungen des Captains, jede mit Vorschlag.

Was der Lauf braucht (Spec, Referenz, Stempel, Skript), entsteht vor der Nacht und wird vorher einmal kurz geprüft. Ein Werkzeug, das erst in der Nacht zum ersten Mal läuft, ist der wahrscheinlichste Grund für eine verlorene Nacht.

## Freigaben vorab, im Chat dieser Sitzung

- Der Lauf selbst mit Start- und Endzeit.
- Modell laden und GPU-Nutzung, mit Rezept und Fenster.
- Das Beenden des Routers, falls ein Bau oder eine Messung ihn verdrängt.
- Eine geplante Windows-Aufgabe, falls der Start nicht von Hand erfolgt.

Eine Freigabe aus einer anderen Sitzung zählt nicht. Steht in der Nachtsitzung ein "Nein, später", gilt das, bis der Captain dort Ja sagt.

## Sicherheiten

- Keine Integration, kein Merge, kein Push, kein Löschen. Kandidaten bleiben zur Durchsicht liegen.
- Die Haltemarke (roter Knopf der Fabrik) wird vor jedem Schritt geprüft.
- Vorprüfung mit dem Skill `sedra-schnellpruefung`: GPU frei (höchstens 3 GiB belegt), kein fremder Modellserver, Register gültig, Platz auf dem Laufwerk. Bei Rot startet nichts.
- Nur gemessene und stabile Einstellungen. Keine Kontext-Leiter und keine neue Quantisierung ohne Aufsicht.
- Nach einem Neustart des PC ist der Debug-Modus der NVIDIA-App aus. Vor der Nacht fragen, ob er an ist.
- Jeder Schritt hat ein Zeitlimit. Scheitert ein Schritt, geht es mit dem nächsten weiter, ohne Wiederholung.
- **Läuft ein Modellserver oder der Router, startet der Bau nicht** (Vorprüfung der Schleife). Vor der Nacht mit dem Captain klären, ob er entladen werden darf; `nachtlauf.py` meldet seit 11.11. „Bau nicht angelaufen“ mit dem Grund aus `bau_schleife_status.log`, statt „Bau beendet“ mit altem Stand.
- Das Rezept für Bauten ist `coder.local_primary_1x80k` (`--rezept`, `--kontext 81920`); mehrere Specs nacheinander mit `--specs a,b,c`. Ein zweiter Lauf derselben Spec setzt fort und baut nichts, außer der Stand wird vorher beiseite gelegt.
- Tests und Messungen des Einbaus nicht parallel zu den Bauten fahren, wenn deren Zeit verglichen wird.
- Die Kandidaten der Nacht sind erst nach dem Lesen etwas wert (`sedra-bau-starten` §Nach dem Bau): bestanden heißt nicht richtig.

## Start

Der Läufer ist ein Skript je Nacht unter `runtime/benchmarks/nachtlauf.py`:

```
python benchmarks/nachtlauf.py <projekt> --bis 07:00 --protokoll <umgebung>\KOORDINATION_SEDRA\09_PLAN\NACHTPROTOKOLL_<JJJJ-MM-TT>.md
```

Die Schritte stehen fest im Skript. Vor dem Start prüfen, ob das Skript im verwendeten Arbeitsstand liegt und zur geplanten Nacht passt. Im Hintergrund starten und die PID notieren. Das Monitor-Werkzeug endet nach 30 Minuten und taugt nicht als Nachtwache; das Protokoll ist die Quelle.

## Auswertung am Morgen

1. Protokoll lesen: jede Zeile hat Uhrzeit, Schritt und Ergebnis.
2. Lebt der Lauf noch? Nach PID **und** Prozessname mit Startzeit prüfen. Nach einem Neustart vergibt Windows alte PIDs neu.
3. Bau: `bau_schleife_status.log`, Kurzbericht, Kandidat unter `devvm_candidates` (Skill `sedra-bau-starten`). Messung und Testsuite: Zahlen mit Datei.
4. Hat der PC neu gestartet? Die Windows-Ereignisse zeigen es (Skill `sedra-logs-lesen`).
5. Bericht an den Captain: was lief, Zeiten, VRAM-Spitze, was scheiterte und warum, was nicht geprüft ist, Vorschlag für die Übernahme.
6. Register und Dashboard nachziehen (Skill `sedra-register-dashboard`). Der Status bleibt höchstens `AWAITING_CAPTAIN`.

Übernommen wird erst nach dem Ja des Captains, mit dem Skill `sedra-git-uebernahme`.
