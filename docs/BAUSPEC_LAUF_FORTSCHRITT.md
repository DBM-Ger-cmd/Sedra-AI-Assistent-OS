# Bau-Spec N8: Fortschritt eines Laufs (SEDRA-Pilot über die Harness, 29.10.2026)

Gehört zu `SPEC_HARNESS_SHELL_v1_G3_STUFE3.md` (N8, S3-F). Aufgabe und versteckte Prüfungen (12, L3 ≤ 20) stehen in `runtime/benchmarks/devvm_specs/harness_lauf_fortschritt.py`.

| | |
|---|---|
| Was SEDRA baut | `lauf_fortschritt.py` mit `fortschritt_aus(zeilen, regel) -> {prozent, text} \| None` – Regeln `zeilen` (n/m), `prozent`, `text`; wirft nie |
| Referenz (Claude) | `runtime/benchmarks/devvm_refs/harness_lauf_fortschritt/lauf_fortschritt.py` = `harness/lauf_fortschritt.py` im Paket; `lauf.fortschritt_aus` benutzt es |
| Stempel | `spec_check.py harness_lauf_fortschritt --vm --project <A1>/workspace/GUPPI_OS`: lint ok, Referenz ok, microVM ok, **Stempel geschrieben 29.10.2026** (ohne Modell) |
| Besonderheit | Der Bau läuft **nicht von Hand**, sondern als erster Bau eines SEDRA-Agenten unter einem Vorarbeiter: der Captain nennt der Vorarbeiter-Sitzung den Wunsch, sie schlägt die Aufgaben-Freigabe vor, der Captain gibt sie frei (Muster: `docs/spec_entwuerfe/**` schreiben, `spec_check`-Befehl, Lauf `devvm_build` mit `spec=harness_lauf_fortschritt`, Modell `coder.local_primary`, ≤ 3 Stunden, ≤ 60 Aufrufe), der Vorarbeiter startet den Lauf, die Taskleiste zeigt ihn |
| Prüfer | Gemma-4-12B (`pruefer`, nur lesend), nach dem Bau mit Modellwechsel (nie gleichzeitig mit Qwen) |
| Bau | **nicht gestartet** – P-12/P-13, nur auf Ansage des Captains |
| Danach | Kandidat gegen Referenz, Review, Übernahme durch den Captain; Misserfolg wird ehrlich als Befund und V4-Entscheidung im Bericht festgehalten |
