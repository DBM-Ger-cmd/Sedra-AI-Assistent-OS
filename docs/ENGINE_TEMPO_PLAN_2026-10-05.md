# Engine-Tempo-Messung (geplant 2026-10-05)

Ausgangslage: Flash-Attention an stürzt im Standard-Build b11371 (CUDA 12.4, Clang) auf dieser Karte ab (`MESSUNGEN.md` 3b). Stabile Wege: Flash-Attention aus
oder der lokale Build b11160 (CUDA 13, MSVC, Unsloth). Die Engine wurde bisher nicht auf Tempo-Optionen geprüft. Der Vergleich der Hilfetexte beider Builds:
207 gegen 206 Optionen, nur `--spec-draft-sampling` fehlt in b11160.

Reihenfolge (jede Runde in der Test-Warteschlange, Besitzer `chat-guppi-cudahunt`; GPU-Lease nötig):

| # | Frage | Varianten | Maß | Vorarbeit |
|---|---|---|---|---|
| 1 | Bringen mehr CPU-Threads Tempo bei MoE im RAM? | `-t`/`-tb`: Standard, echte Kerne, Kerne-2 | Prompt- und Gen-tok/s (Median aus 3), fester Prompt | `threads` in `build_command` |
| 2 | Hilft spekulatives Dekodieren ohne Zweitmodell? | `--spec-type none`, `ngram-mod`, `ngram-cache` | Gen-tok/s und Sekunden pro Reparatur, statische Note unverändert | `spec_type` erweitern (bisher nur none/draft-mtp) |
| 3 | Hilft `--cache-reuse`? | 0, 256 | Sekunden pro Werkzeug-Schleife | `cache_reuse` in `build_command` |

Regeln: nur auf dem stabilen Build messen (sonst Absturz statt Tempo); jede Variante frisch gestartet, Absturz zählt; Ergebnis über `run_log.py` nach
`measurements/logs/`; eine Option kommt erst nach der Messung ins Rezept. Stand der Absturzjagd: `cuda_crash_hunt_*` in `measurements/logs/`.
Die Runde #33 von `chat-claude-smallmodels` (Kleinmodell-Test) überschneidet sich mit `small_team.py`; sie ist nicht gestrichen, nur abzugleichen.

**Ergebnis (2026-10-05):** alle drei Runden gemessen, keine Option brachte etwas für Qwen3-Coder; die Optionen wurden wieder ausgebaut. Siehe `MESSUNGEN.md` 3d.
