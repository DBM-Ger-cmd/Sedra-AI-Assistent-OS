# Buildflow: der Ablauf "Aufgabe → Spec → Bau → Abnahme → Übernahme" als Funktion von GUPPI

Stand 13.10.2026, Entwurf von Claude (Auftrag des Captains: "schaffe eine richtige Funktion in GUPPI für so einen Workflow"). Heute läuft dieser Ablauf aus losen Skripten (`benchmarks/spec_check.py`, `devvm_build.py`, `night_queue_*`, `logbook.py`) und mit mir als Handarbeit dazwischen. Buildflow macht daraus **eine Aufgabe mit Zustand**, die GUPPI selbst führt, auf der Kommandozeile, später im Chat.

## Was eine Aufgabe ist

Eine Aufgabe (`BF-xxxxxxxx`) liegt als Datei unter `runtime_data/buildflow/<id>.json`. Sie hat Titel, Spec-Name, Saat, Review-Datei, Anzahl Nacharbeiten, Vorrang, Fenster (`jetzt` oder `nacht`), Zustand, Verlauf und Ergebnis. Sie kennt Freigaben (Gates) für **Spec**, **Bau** und **Übernahme**.

## Zustände und Übergänge

```
draft ──check_ok──► checked ──approve_spec──► spec_approved ──queue──► queued ──start──► building ──finish_ok──► built ──report──► reported ──approve_adopt──► adopt_approved ──adopt──► adopted
  │ ▲                                                            ▲                       │
  │ └─check_failed (bleibt draft, Probleme im Verlauf)           └────── requeue ◄────── failed ◄─finish_failed
  └── cancel (aus jedem Zustand außer adopted) ──► cancelled        (mit Review-Datei: Fortsetzung ab der gescheiterten Stufe)
```

Jeder Übergang schreibt eine Verlaufszeile mit Uhrzeit. Ein unerlaubter Übergang wird abgelehnt (`illegal_transition`), nie stillschweigend ausgeführt.

## Die Warteschlange (Nacht inbegriffen)

`queued`-Aufgaben laufen nach **Vorrang** (höher zuerst), dann nach Anlage. Fenster `nacht` heißt: nur ab der Nachtstunde (22 Uhr). Der Läufer (`buildflow run`) reserviert die GPU-Lease mit dem Vorrang der Aufgabe (`TestLab.reserve`), baut mit `devvm_build.py` und trägt Stufenzeilen als Ereignisse in den Verlauf ein. Er ersetzt die einzelnen `night_queue_*`-Skripte für diesen Zweck: eine Aufgabe einreihen genügt, es muss kein neues Skript entstehen.

## Freigaben

Die Gates für Spec, Bau und Übernahme sind echte Gates des Missionssystems (`guard.create_gate`, Entscheidung über `/api/mission/approve` und `/reject`). Damit erscheinen sie später ohne Zusatzarbeit in der Freigabe-Leiste (Baustein G7). Der Läufer baut nur, wenn das Gate "Bau" freigegeben ist; jedes Gate wird einzeln per ID entschieden.

## Module

| Modul | Aufgabe | Wer |
|---|---|---|
| `devenv/buildflow_core.py` | reine Logik: Aufgabe anlegen, Zustandsautomat (`transition`, `can`), Reihenfolge der Warteschlange (`pick_next`), Zeilen für Listen | **GUPPI** (Spec `buildflow_core`) |
| `devenv/spec_tools.py` | Spec prüfen (aus `spec_check.py` verschoben): Lint, Referenz, Saat, Kandidat, Snapshots | Claude (Umzug), danach GUPPI-Pflege |
| `devenv/buildflow_store.py` | Aufgaben als Dateien lesen und schreiben (atomar, mit Sperre) | Claude |
| `devenv/buildflow_runner.py` | Bau starten, Ausgabe lesen, Gates abfragen, Vorrang und Nachtfenster | Claude |
| `cli.py` | `guppi buildflow add / list / show / check / request-gate / queue / run / report / adopt / cancel` | Claude |
| später: `uix_server.py`, Chat | `/api/buildflow/*`, Slash-Befehle `/bauen`, `/stand`, `/uebernehmen` | nach "GUPPI Chat" |

## Reihenfolge

1. `buildflow_core` als Spec an GUPPI (Nachtkette G, Spec fertig vor 22 Uhr).
2. `spec_tools` verschieben, `buildflow_store`, `buildflow_runner`, CLI verdrahten (Claude, nach dem Kern).
3. Erste echte Aufgabe durch den Ablauf schicken (statt Skript: `guppi buildflow add …`).
4. Nach "GUPPI Chat": API, Slash-Befehle, Freigabe-Leiste.
