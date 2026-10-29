# Bau-Spec N2: Deckung einer Aufgaben-Freigabe (SEDRA-Bau, 29.10.2026)

Gehört zu `SPEC_HARNESS_SHELL_v1_G3_STUFE3.md` (N2) und `SPEC_HARNESS_SHELL_v1_G2_STUFE3.md` §4.2. Die Aufgabe selbst steht in `runtime/benchmarks/devvm_specs/harness_aufgabe_deckung.py`
(`TASK`, `NOTES`); die versteckten Prüfungen (15, L3 ≤ 20) stehen im selben Modul unter `HIDDEN`/`CHECKS` und sind für die bauenden Agenten nicht sichtbar.

| | |
|---|---|
| Was SEDRA baut | `aufgabe_deckung.py` mit `zustand(aufgabe, jetzt)` und `deckt(aufgaben, sitzung_id, werkzeug, ziel, jetzt, passt)` – reine Logik, nur `datetime` |
| Referenz (Claude) | `runtime/benchmarks/devvm_refs/harness_aufgabe_deckung/aufgabe_deckung.py` = `harness/aufgabe_deckung.py` im Paket (der Test `test_harness_bau_pruefungen` hält beides gleich) |
| Stempel | `spec_check.py harness_aufgabe_deckung --vm --project <A1>/workspace/GUPPI_OS`: lint ok, Referenz ok, microVM ok (Python 3.12.15), **Stempel geschrieben 29.10.2026** (ohne Modell) |
| Bau | **29.10.2026 gelaufen** (Captain-Ja): Qwen3.6-35B-A3B, Profil `standard`, 544 s, 20 Modellaufrufe, 1 Nacharbeit, 0 Eskalationen, **versteckt 15/15 bestanden**, Kandidat 106 Zeilen, Quote Claude/SEDRA 1,3. Vorher scheiterten zwei Versuche ohne Modellaufruf (Worktree ohne `engines`/`local_paths.yaml`; Gewichte nach `I:/KI-Daten/modelle` umgezogen, Modellpfade vom Captain freigegeben umgestellt) |
| Danach | **Review und Übernahme (Captain 29.10.2026: „Mit Korrektur übernehmen“).** Kandidat gegen Referenz: 5233 saubere Fälle ohne Abweichung; mit kaputten Eingaben wich er in unsicherer Richtung ab (ein `bis`, das kein Text ist, und ein `max_aufrufe`, das keine ganze Zahl ist, galten als unbegrenzt; eine Aufgabe ohne `id` warf `KeyError`). Drei Korrekturen von Claude (Eingriff im Logbuch), in `harness/aufgabe_deckung.py` im Kopf benannt. Beim Vergleich zeigten sich zwei Schwächen der Referenz, die der Kandidat richtig hatte (`sitzungen` als Text traf per Teilstring, `aufrufe=True` zählte als Zahl); die Referenz ist angepasst. Die versteckten Prüfungen wurden danach auf 18 geschärft (der rohe Kandidat besteht sie nicht, das Paket und die Referenz schon), Stempel erneuert. `test_harness_aufgabe_deckung_vergleich` hält Paket und Referenz gleich (saubere und kaputte Eingaben) |
| Warum SEDRA | reine Logik mit klarer Schnittstelle (L4); die Sicherheit liegt nicht hier, sondern in `freigabe.py`, `vorbehalte.py` und der Herkunftsprüfung, die nur Claude ändert |
| Grenze | Der Bau schreibt nur in den Kandidatenordner (`runtime_data/devvm_candidates/`); nichts im Repo, nichts in `local_config/`, kein Push |
