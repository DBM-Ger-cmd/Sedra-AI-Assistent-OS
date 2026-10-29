# Bau-Spec N8: Fortschritt eines Laufs (SEDRA-Pilot über die Harness, 29.10.2026)

Gehört zu `SPEC_HARNESS_SHELL_v1_G3_STUFE3.md` (N8, S3-F). Aufgabe und versteckte Prüfungen (12, L3 ≤ 20) stehen in `runtime/benchmarks/devvm_specs/harness_lauf_fortschritt.py`.

| | |
|---|---|
| Was SEDRA baut | `lauf_fortschritt.py` mit `fortschritt_aus(zeilen, regel) -> {prozent, text} \| None` – Regeln `zeilen` (n/m), `prozent`, `text`; wirft nie |
| Referenz (Claude) | `runtime/benchmarks/devvm_refs/harness_lauf_fortschritt/lauf_fortschritt.py` = `harness/lauf_fortschritt.py` im Paket; `lauf.fortschritt_aus` benutzt es |
| Stempel | `spec_check.py harness_lauf_fortschritt --vm --project <A1>/workspace/GUPPI_OS`: lint ok, Referenz ok, microVM ok, **Stempel geschrieben 29.10.2026** (ohne Modell) |
| Besonderheit | Der Bau läuft **nicht von Hand**, sondern als erster Bau eines SEDRA-Agenten unter einem Vorarbeiter: der Captain nennt der Vorarbeiter-Sitzung den Wunsch, sie schlägt die Aufgaben-Freigabe vor, der Captain gibt sie frei (Muster: `docs/spec_entwuerfe/**` schreiben, `spec_check`-Befehl, Lauf `devvm_build` mit `spec=harness_lauf_fortschritt`, Modell `coder.local_primary`, ≤ 3 Stunden, ≤ 60 Aufrufe), der Vorarbeiter startet den Lauf, die Taskleiste zeigt ihn |
| Prüfer | Gemma-4-12B (`pruefer`, nur lesend), nach dem Bau mit Modellwechsel (nie gleichzeitig mit Qwen) |
| Bau | **29.10.2026 gelaufen (Pilot)**: Vorarbeiter-Sitzung (Qwen3.5-9B) startete `spec_check` und `devvm_build` unter der Aufgaben-Freigabe T-E0A4F78E; Qwen3.6-35B-A3B baute: **versteckt 12/12 bestanden**, 732 s, 16 Modellaufrufe, 1 Nacharbeit, Kandidat 108 Zeilen, Quote Claude/SEDRA 0,9. Prüfer Gemma-4-12B: „übernehmen“ (oberflächlich) |
| Danach | **Übernommen (Captain 29.10.2026: „Ohne toten Code“)**: der Kandidat steht im Paket, die ungenutzte Funktion `_gültige_regel` ist entfernt (Eingriff im Logbuch). Vergleich gegen die Referenz: 4000 saubere Fälle ohne Abweichung; bei kaputten Eingaben war der Kandidat strenger (genaue Gruppenzahl der Regex, nur Listen, ganze Zahlen bei „zeilen“) – das entspricht der Spec, die Referenz und der Spec-Text sind angeglichen, Stempel erneuert. `test_harness_lauf_fortschritt_vergleich` hält Paket und Referenz gleich |
