# coder_ext — Erweiterungen des GUPPI-Coders (E-21, 2026-10-10)

`__init__.py` (`CoderExtensions`, E-20) ist die einzige Stelle, mit der der Kern spricht. Angeschlossen ist sie in `devvm_tools.DevToolBox`, `model_tools.run_tool_loop` und `devvm_agents.run_agent`. Eingeschaltet wird sie mit `devvm_build.py --coder-ext all|e01,e08,...`. Standardmäßig ist sie aus.

Plan: `<projekte>\Guppy\ERWEITERUNGSPLAN_CODER_2026-10-10.md`. Specs: `runtime/benchmarks/devvm_specs/eNN_*.py`. Reviews: `runtime/benchmarks/devvm_reviews/`.

Die Module hat GUPPI im Solo-Modus gebaut, mit Qwen3.6-35B-A3B. Abgenommen sind sie durch die versteckten Tests der Spec, aufgeräumt nach Claudes Reviews. Ihr Code ist unverändert übernommen. Kommentare stehen bewusst nur hier.

| Datei | Paket | Idee aus | Kandidat (runtime_data/devvm_candidates/...) |
|---|---|---|---|
| read_tracker.py | E-01 erst lesen, dann ändern | little-coder (edit refuses on unread), Hermes (file_tools_read_tracking) | e01_read_tracker/attempt_01_20261011_004759 |
| fuzzy_edit.py | E-08 tolerantes edit_file | Hermes (tools/fuzzy_match.py, MIT) | e08_fuzzy_edit/attempt_01_20261010_223920 |
| replay_log.py | E-04 aufzeichnen und abspielen | deepseek-harness (llm-replay), StarNet (replay provider) | e04_replay_log/attempt_01_20261011_112628 |
| think_guard.py | E-02 Thinking-Budget | little-coder (thinking-budget) | e02_think_guard/attempt_01_20261010_224042 |
| no_call_monitor.py | E-03 Antworten ohne Tool-Call | little-coder (quality-monitor, output-parser), Hermes (empty_response_guard) | e03_no_call_monitor/attempt_01_20261010_224307 |
| syntax_note.py | E-09 Syntax-Notiz nach dem Schreiben | Hermes (file_operations_lint) | e09_syntax_note/attempt_01_20261010_222727 |
| result_pruner.py | E-05 alte Tool-Ergebnisse kürzen | deepseek-harness (compaction-tool-result-pruner), Hermes (read dedup) | e05_result_pruner/attempt_01_20261010_222948 |
| tool_cards.py | E-07 Tool-Karte nach Fehler | little-coder (tool skill cards) | e07_tool_cards/attempt_01_20261010_223244 |
| coder_cards.py | Regeln und Kartentexte für E-07 | von Claude geschrieben | benchmarks/devvm_seeds/coder_ext_extra |
