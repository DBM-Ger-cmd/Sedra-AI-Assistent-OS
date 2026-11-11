# So wird gebaut

Kompakte Seite (PIPE-04, geändert 20.10.2026, Linie L1–L4 und V1–V4). Ausführlich: [ENTWICKLUNG.md](ENTWICKLUNG.md). Alle Befehle laufen im Ordner `runtime` mit `.venv\Scripts\python.exe`.

**Ein Bau-Ort (PIPE-09, 20.10.2026)** (geändert 20.10.2026, PIPE-09) Gebaut wird immer aus dem Arbeitsstand (Git). Projektordner ist `<sedra>/workspace/SEDRA_OS`, **nicht** `<sedra>` selbst (das legt einen leeren VM-Cache an). Das Python mit allen Paketen kommt aus `<sedra>/runtime/.venv`. Engine (`engines/llama.cpp/<engine_build>`) und `runtime/config/llama_server.yaml` sind im Arbeitsstand und in der Laufzeit-Installation gleich; `runtime/tests/test_bau_ort.py` prüft das (und dass `engine_build` freigegeben ist, derzeit b11160). Engine-Wechsel nur mit Captain-Gate.

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
`--self-check none` (geändert 21.10.2026, PROFIL-01: Messung skill_rank3 21.10.: self_check full 1850 s, none 170 s, gleiches Ergebnis), `--server-set flash_attn=on`, `kv_cache_type=q8_0`, `ubatch=512`. Der Stempel liegt in `<projekt>/runtime_data/spec_stamps/<name>.json`. Der Agent Manager (`run_worker`) baut denselben Weg.

**Profil `schnell-klein`** (geändert 21.10.2026, PROFIL-02): wie `standard`, aber `--coder` und `--all-models coder.llama_qwen35` (Qwen3.5-9B mit MTP, 282 s auf skill_rank3). **Reserve, nicht Standard**; Aufruf mit `--profile schnell-klein`.

**Feld `SEED`** (geändert 21.10.2026, PIPE-10): Baut eine Spec auf einer Saat auf, trägt sie `SEED = "benchmarks/<ordner>"` (Pfad relativ zu `runtime/`). `devvm_build.py` nimmt den Ordner als `--seed`, wenn keiner angegeben ist (ein angegebenes `--seed` gewinnt, mit Zeile im Log); fehlt der Ordner: Abbruch `seed_missing`. Der Stempel bindet den Hash des Saat-Ordners (`seed_sha256`); `spec_check` meldet die Zeile `seed <ordner> (<n> Dateien)`. Stempel von vor dem 21.10.2026 sind damit ungültig (`spec_changed_since_check`): einmal neu prüfen.

## Vergleichslauf (A/B) und Arbeitsanweisung

**Arbeitsanweisung** (dritte Ebene, `config/manager/arbeitsanweisungen/<typ>.md`, 11.11.2026): `devvm_build.py --arbeitsanweisung <typ> [--anweisung-sprache auto|de|en]` hängt ihren Text an jede Aufgabe des Entwicklers und an die Nacharbeit. In der Bau-Schleife ist sie **standardmäßig aus** (`bau_schleife.py ... --arbeitsanweisung bau_coder` schaltet sie ein), weil der erste A/B-Lauf (am3_rechte_diff, 3 Paare) keinen messbaren Nutzen und rund 21 % mehr Prompt-Token zeigte. Zweiter Vergleich (am3_berechtigung, 1044 Differenzfälle, je 5 Läufe, 11.11.2026): Dauer im Median ohne 167 s, deutsch 129 und 134 s, englisch 146 s; bei der Qualität (Läufe ohne Abweichung 3/5, 3/5 und 1/5, 3/5) kein Signal, Englisch nicht besser als Deutsch. Dritter Vergleich (`am0_herkunft`, 4 Stufen, größere Aufgabe, 554 Differenzfälle, je 5 Läufe, 11.11.2026): **mit Anweisung schlechter**. Abweichungen von der Referenz im Mittel 38,6 gegen 3,0 (jeder Lauf mit Anweisung hat 13 bis 69, jeder ohne höchstens 7), Nacharbeiten 2,2 gegen 1,0, Prompt-Token +21 %, Dauer nur 194 gegen 198 s im Mittel (Median 190 gegen 204 s). Der Tempogewinn der kleinen Specs hält bei der größeren Aufgabe nicht, die Qualität fällt. Die Anweisung bleibt in der Schleife aus. `:en` bricht ab, wenn die englische Fassung nicht gilt (kein stiller Rückfall auf Deutsch).

**Standardvergleich:** `python benchmarks/ab_bau.py <spec> [--paare 3] [--arme ohne,bau_coder:de]` zeigt ohne `--start` nur den Plan und prüft Stempel, GPU (höchstens 3 GiB), Prozesse, Sperrdatei und RAM. Mit `--start` (Ja des Captains) laufen die Läufe abwechselnd nacheinander; Ergebnis unter `<projekt>/runtime_data/ab_bau/<spec>_<zeit>/` (`bericht.md`, `ergebnis.json`, Logs). Gemessen werden Stufen, Dauer, Aufrufe, Nacharbeiten, Token und der **Differenztest** gegen die Referenz (`benchmarks/ab_diff/<spec>.py` mit `MODUL` und `faelle(ref)`): Bestanden beweist wenig, Abweichungen bei Randfällen zeigen die Qualität. Unter 5 Läufen je Arm warnt der Bericht. Eine Spec ohne Differenzfälle wird nur nach Stufen und Aufwand verglichen. Braucht eine Spec Dateien, Uhrzeit oder eine Klasse mit Zustand, legt `ab_diff/<spec>.py` Hilfsfunktionen in `HILFEN` an (Signatur `h(modul, *args)`; Beispiel `am0_herkunft`): sie bauen eigene Ordner, geben nur Vergleichbares zurück (keine Pfade, keine Uhrzeit) und räumen auf. `benchmarks/konsens.py` vergleicht mehrere Kandidaten mit denselben Fällen untereinander (Konzept: `docs/KONZEPT_KONSENS_BAU_2026-11-11.md`).

## Abbruchgrenzen

- **Kein Stempel:** `spec_not_checked`. Spec, Referenz oder Saat nach der Prüfung geändert: `spec_changed_since_check`. Stempel nur vom Host (`spec_check --host-only`): `spec_stamp_host_only`.
  Ausnahmen, jeweils mit Warnung im Log: `--skip-spec-stamp` (jeder Stempel fehlt), `--allow-host-stamp` (Host-Stempel).
- **Stufengröße:** über 20 neue Prüfungen je Stufe Warnung, über 30 Fehler (`spec_check`).
- **Gescheiterte Stufe:** nach den Nacharbeiten (`--rework`, im Agent Manager 2) hält der Bau an und nennt den Fortsetzungsbefehl; `--keep-going` baut trotzdem weiter.
- **Experimentelle Optionen** (`--plan-steps`, `--fresh-rework`, `--step-syntax-check`, `--parallel-check`, `--checker`, `--arbiter`) nur mit `--experimental`.
- **GPU:** der Bau hält die Lease des Testlabors; ohne sie startet kein Modell.
- Die Ketten- und Einmal-Skripte liegen im Archiv `benchmarks/archiv/` und werden nicht mehr benutzt.

## Logbuch

Die BAU-Zeile schreibt `devvm_build.py` selbst (`--no-logbook` nur für Tests). Alles andere trägt der Vorarbeiter mit `benchmarks/logbook.py add <ART> "Text" --ref "Datei"` ein;
erlaubte Arten: ENTSCHEIDUNG, SPEC, BAU, INTEGRATION, MESSUNG, FEHLER, AENDERUNG, DOKU, RECHERCHE, HINWEIS. Die Uhrzeit setzt das Werkzeug.
