# Test-Labor: gemeinsame GPU-Sperre und Ergebnis-Datenbank (Phase 9c)

Für alle Chats, Skripte und GUPPI-Instanzen auf diesem PC. Zweck: Es gibt **eine** GPU (12 GB) und **einen** festen llama-server-Port (8089).
Zwei gleichzeitige Läufe stören sich gegenseitig (Messwerte, Abstürze, "port_in_use"). Niemand soll raten müssen, ob die GPU frei ist.

**Datei:** `workspace/GUPPI_OS/runtime_data/testlab/testlab.db` (SQLite, WAL). Code: `runtime/src/guppi_runtime/testlab.py`,
Kommandozeile: `runtime/benchmarks/testlab_cli.py`. 15 Tests in `tests/test_testlab.py`.

## Die Regel

**Wer ein Modell auf die GPU bringt (llama-server, LM Studio laden, hermes, manuelle Tests), holt vorher die GPU-Sperre.** Die Skripte
`token_quality.py`, `measure_recipe.py` und `workingset_real_run.py` tun das selbst. Alles andere läuft unter:

```bash
python benchmarks/testlab_cli.py hold --owner <chat-name> --purpose "<was>" --ttl 600 --wait 1800 -- <befehl ...>
```

`hold` wartet bis zu `--wait` Sekunden auf eine belegte GPU und gibt sonst den Exit-Code 75 zurück. Der Befehl läuft nur, solange er die Sperre
hat, die Sperre wird danach (auch bei Fehlern) freigegeben.

Eine Sperre ist **verwaist** und wird übernommen, wenn der Herzschlag älter als die `ttl` ist **oder** der haltende Prozess nicht mehr
existiert (geprüft; ein abgeschossener Lauf blockiert also nicht). Die Übernahme steht in `events`.

Wichtig: Die Sperre schützt nur gegen Prozesse, die sie benutzen. LM Studio selbst oder ein Spiel kennt sie nicht.

## Befehle

| Befehl | Wirkung |
|---|---|
| `status` | wer hält die GPU, was ist geplant, letzte Läufe, letzte Ereignisse |
| `plan --owner X --kind quality --what "…" --models a,b` | eine geplante Testrunde eintragen, damit andere Chats sie sehen und nicht doppelt machen |
| `queue [--all]` | geplante/laufende Runden (mit `--all` auch erledigte) |
| `setstatus ID planned\|running\|done\|cancelled [--note …]` | Status einer Runde ändern |
| `runs` / `summary RUN_ID` | letzte Läufe / pro Modell und Variante: Aufrufe, Anteil richtig, mittlere Tokens, Sekunden |

Tabellen: `lease` (eine Zeile `gpu`), `queue`, `runs`, `results` (Modell, Variante, Aufgabe, ok, Tokens, Sekunden, Zusatzfelder als JSON), `events`.
Ergebnisse bleiben erhalten, damit Runden später verglichen werden können.

## Eingetragene Runden (Stand 2026-10-02)

Die Läufe 1–12 (Arbeitsset-Messung mit Gemma) stehen in `runs`/`results`. Die beiden ersten Planeinträge (#1 Arbeitsset, #2 token_quality mit Gemma)
sind noch `planned`.

## Vorprüfung der GPU (2026-10-02)

Wer die Sperre über `lab.lease(..., preflight=clear_leftovers)` oder `testlab_cli.py hold` holt, bekommt vor dem Lauf eine bereinigte GPU: ein verwaister GUPPI-llama-server
(Reste eines abgestürzten oder abgebrochenen Laufs, Port 8089) wird beendet, damit weder `port_in_use` noch ein halb volles Gedächtnis die Messung verfälscht.
Es passiert nur etwas, wenn ein solcher Rest da ist. Fremde Prozesse (Spiel, LM Studio mit geladenem Modell, anderes auf dem Port) werden nie beendet; dann bricht der Lauf mit einer
Meldung ab, die den Verursacher nennt (Grenze: 2,5 GiB belegt, `GpuNotClean`). Von Hand: `python benchmarks/testlab_cli.py clean` (nur wenn niemand die Sperre hält).
Code: `runtime/src/guppi_runtime/gpu_preflight.py`, Tests: `tests/test_gpu_preflight.py`. Schlägt die Vorprüfung fehl, steht `preflight_failed` in `events` und die Sperre ist wieder frei.

