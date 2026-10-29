# Bau-Spec N2: Deckung einer Aufgaben-Freigabe (SEDRA-Bau, 29.10.2026)

Gehört zu `SPEC_HARNESS_SHELL_v1_G3_STUFE3.md` (N2) und `SPEC_HARNESS_SHELL_v1_G2_STUFE3.md` §4.2. Die Aufgabe selbst steht in `runtime/benchmarks/devvm_specs/harness_aufgabe_deckung.py`
(`TASK`, `NOTES`); die versteckten Prüfungen (15, L3 ≤ 20) stehen im selben Modul unter `HIDDEN`/`CHECKS` und sind für die bauenden Agenten nicht sichtbar.

| | |
|---|---|
| Was SEDRA baut | `aufgabe_deckung.py` mit `zustand(aufgabe, jetzt)` und `deckt(aufgaben, sitzung_id, werkzeug, ziel, jetzt, passt)` – reine Logik, nur `datetime` |
| Referenz (Claude) | `runtime/benchmarks/devvm_refs/harness_aufgabe_deckung/aufgabe_deckung.py` = `harness/aufgabe_deckung.py` im Paket (der Test `test_harness_bau_pruefungen` hält beides gleich) |
| Stempel | `spec_check.py harness_aufgabe_deckung --vm --project <A1>/workspace/GUPPI_OS`: lint ok, Referenz ok, microVM ok (Python 3.12.15), **Stempel geschrieben 29.10.2026** (ohne Modell) |
| Bau | **nicht gestartet** – P-11, nur auf Ansage des Captains: `devvm_build.py <projekt> --spec harness_aufgabe_deckung --profile standard` (lädt Qwen3.6-35B-A3B, exklusive GPU, etwa 6 Minuten) |
| Danach | Vergleich Kandidat gegen Referenz (Zufallsfälle, 0 Abweichungen verlangt), Review, Übernahme durch den Captain; scheitert der Bau → V4, die Referenz bleibt, die Quote steht im Logbuch |
| Warum SEDRA | reine Logik mit klarer Schnittstelle (L4); die Sicherheit liegt nicht hier, sondern in `freigabe.py`, `vorbehalte.py` und der Herkunftsprüfung, die nur Claude ändert |
| Grenze | Der Bau schreibt nur in den Kandidatenordner (`runtime_data/devvm_candidates/`); nichts im Repo, nichts in `local_config/`, kein Push |
