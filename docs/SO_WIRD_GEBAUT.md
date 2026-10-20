# So wird gebaut

Kompakte Seite (PIPE-04, geändert 20.10.2026, Linie L1–L4 und V1–V4). Ausführlich: [ENTWICKLUNG.md](ENTWICKLUNG.md). Alle Befehle laufen im Ordner `runtime` mit `.venv\Scripts\python.exe`.

## Die Schritte

| # | Schritt | Befehl | Wer |
|---|---|---|---|
| 0 | Lohnt sich ein Bau? Spec + Tests + Referenz kleiner als der Code, sonst baut Claude direkt (Regel V4) | Schätzung | Claude |
| 1 | Spec, versteckte Tests, Referenz schreiben (`benchmarks/devvm_specs/<name>.py`, `devvm_refs/<name>/`) | Datei-Werkzeuge | Claude |
| 2 | Spec prüfen und Stempel schreiben | `benchmarks/spec_check.py <name> --vm --project <projekt>` | Claude |
| 3 | Bauen | `benchmarks/devvm_build.py <projekt> --spec <name> --profile standard` | SEDRA (Modelle), gestartet von Claude |
| 4 | Logbuch: BAU-Zeile mit Stufen, Dauer, GPU-Zeit, Aufrufen, Nacharbeiten und Quote | automatisch am Ende des Baus | `devvm_build.py` |
| 5 | Kandidat lesen (`runtime_data/devvm_candidates/<name>/attempt_…/`) mit der Review-Vorlage `benchmarks/REVIEW_VORLAGE.md`; Empfehlung G4 ja/nein | Review | Claude |
| 6 | Übernahme ja/nein (Gate G4) | Entscheidung | Captain |
| 7 | Übernehmen: `adopt_plan` oder Handkopie, Tests in `tests/`, Logbuch (INTEGRATION) | siehe ENTWICKLUNG.md | Claude |

## Der Standardbefehl

```
cd runtime
.venv\Scripts\python.exe benchmarks/spec_check.py <name> --vm --project <projekt>
.venv\Scripts\python.exe benchmarks/devvm_build.py <projekt> --spec <name> --profile standard
```

`--profile standard` heißt: `--attempts 1`, `--coder` und `--all-models coder.local_primary`, `--context 32768`, `--tidy`, `--reasoning off`, `--coder-ext all`,
`--server-set flash_attn=on`, `kv_cache_type=q8_0`, `ubatch=512`. Der Stempel liegt in `<projekt>/runtime_data/spec_stamps/<name>.json`. Der Agent Manager (`run_worker`) baut denselben Weg.

## Abbruchgrenzen

- **Kein Stempel:** `spec_not_checked`. Spec oder Referenz nach der Prüfung geändert: `spec_changed_since_check`. Stempel nur vom Host (`spec_check --host-only`): `spec_stamp_host_only`.
  Ausnahmen, jeweils mit Warnung im Log: `--skip-spec-stamp` (jeder Stempel fehlt), `--allow-host-stamp` (Host-Stempel).
- **Stufengröße:** über 20 neue Prüfungen je Stufe Warnung, über 30 Fehler (`spec_check`).
- **Gescheiterte Stufe:** nach den Nacharbeiten (`--rework`, im Agent Manager 2) hält der Bau an und nennt den Fortsetzungsbefehl; `--keep-going` baut trotzdem weiter.
- **Experimentelle Optionen** (`--plan-steps`, `--fresh-rework`, `--step-syntax-check`, `--parallel-check`, `--checker`, `--arbiter`) nur mit `--experimental`.
- **GPU:** der Bau hält die Lease des Testlabors; ohne sie startet kein Modell.
- Die Ketten- und Einmal-Skripte liegen im Archiv `benchmarks/archiv/` und werden nicht mehr benutzt.

## Logbuch

Die BAU-Zeile schreibt `devvm_build.py` selbst (`--no-logbook` nur für Tests). Alles andere trägt der Vorarbeiter mit `benchmarks/logbook.py add <ART> "Text" --ref "Datei"` ein;
erlaubte Arten: ENTSCHEIDUNG, SPEC, BAU, INTEGRATION, MESSUNG, FEHLER, AENDERUNG, DOKU, RECHERCHE, HINWEIS. Die Uhrzeit setzt das Werkzeug.
