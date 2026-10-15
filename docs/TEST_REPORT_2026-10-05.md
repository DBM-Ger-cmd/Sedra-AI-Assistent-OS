# Testbericht 2026-10-05

## Ergebnis
| | |
|---|---|
| Befehl | `PYTHONPATH=src .venv\Scripts\python.exe -m unittest discover -s tests -v` (in `runtime/`) |
| Python | 3.14 (`.venv`), Windows 11 |
| Tests | **1297** |
| Ergebnis | **OK** (0 Fehler, 0 Fehlschläge), 8 übersprungen |
| Dauer | 222,6 s |
| Rohausgabe | `docs/TEST_LOG_2026-10-05.txt` |

Ablauf: Vor den Änderungen 1287 Tests. Erste volle Suite nach Runde 1 und 2 der Fixes: 1296 Tests, 1 Fehler (vorbestehend, siehe Abschnitt 3). Nach dem Fix dieses Fehlers und einem weiteren neuen Test: 1297 Tests, alles grün.

## Übersprungen (8, alle umgebungsbedingt, unverändert)
- 6 Symlink-Tests: auf diesem PC fehlt das Windows-Recht zum Anlegen von Symlinks (WinError 1314).
- 1 Test: `pydantic` ist hier nicht installiert.
- 1 Test: "no loader in this test project".

## 1. Gemachte Fixes und ihre Tests (10 neue Tests)
| # | Fix | Datei(en) | Neuer Test |
|---|---|---|---|
| 1 | Engine: Datei, die nicht im Manifest steht (z. B. untergeschobene DLL), macht die Engine unbenutzbar | `engine_provision.py` | `test_engine_provision...test_a_planted_file_next_to_the_server_is_detected_by_the_quick_check` |
| 2 | Sandbox: `active.lock` bleibt nicht liegen, wenn vor dem Provider-Start etwas fehlschlägt | `sandbox/broker.py` | `test_sandbox...test_failure_before_the_provider_starts_leaves_no_lock_behind` |
| 3 | `filesystem`: ungültige/Bytes-Codecs und nicht dekodierbare Dateien sind Validierungsfehler; `list_dir` liest einmal | `tools/filesystem.py`, `uix_server.py` (Binär-Erkennung angepasst) | `test_runtime...test_filesystem_bad_encoding_is_a_validation_error_not_a_crash`, `...test_filesystem_list_dir_truncation_flag` |
| 4 | Atomare Schreibzugriffe mit `fsync`; neues `atomic_write_bytes` | `util.py` | durch die ganze Suite abgedeckt |
| 5 | Guard-Token laufen nach 24 h ab, alte werden nach 30 Tagen entfernt | `guard.py` | `test_runtime...test_guard_token_expires_and_old_tokens_are_pruned` |
| 6 | Audit: `repair()` / CLI `audit-repair` für eine halbe letzte Zeile | `audit.py`, `cli.py` | `test_runtime...test_audit_repair_moves_a_torn_last_line_aside` |
| 7 | Audit: Anker `events.jsonl.head` gegen Abschneiden am Ende | `audit.py` | `test_runtime...test_audit_detects_events_cut_off_the_end` |
| 8 | Audit: Schwärzung nach Schlüssel-Endung (`approval_token` ja, `max_tokens` nein) | `audit.py` | `test_runtime...test_audit_redacts_keys_that_end_in_token_or_secret_but_not_usage_counters` |
| 9 | `stop_process` prüft die Startzeit vor dem Beenden (PID-Wiederverwendung) | `uix_server.py` | `test_uix_server...test_a_reused_pid_is_not_killed` |
| 10 | Rework-Watch zählt Kontext-Reparaturen nicht mehr als "derselbe Aufruf" | `job_supervisor.py` | `test_job_supervisor...test_a_context_overflow_repeated_is_not_a_rework_stall` |

Ohne neue Tests: 20 unbenutzte Importe und eine unbenutzte Variable entfernt (Prüfung: alle Module importierbar, pyflakes ohne Befund); 77 `.bak-*`-Dateien nach `archiv/bak_dateien/` verschoben (kein Test betroffen).

## 2. Korrektur eines eigenen Fehlers
Der Fix 3 (Runde 1) brach die Binärdatei-Erkennung der UIX-Dateiansicht (`project_file` verließ sich auf `UnicodeDecodeError`). Das fiel erst in Runde 2 auf (`test_uix_server...test_project_file_reads_text_flags_binary_and_needs_a_path`); behoben in `uix_server.py`. Lehre: bei Änderungen am Tool-Verhalten auch die Aufrufer-Module testen, nicht nur das Tool.

## 3. Der vorbestehende Fehler
`test_context_assembly.SupervisorGlueTests.test_repair_limit_escalates_instead_of_looping` war schon mit dem Code vor dem Review rot (3 von 3 Läufen mit dem Backup-Stand).
Ursache: `job_supervisor.fail` gab bei `AWAIT_CHANGE` jede Fehlersignatur an den `rework_watch` (2026-10-04). Der Kontext-Überlauf hat immer dieselbe Signatur, der Watch stoppte nach dreimal und eskalierte an den Captain, vor dem Reparatur-Limit (2, dann Eskalation an guppi). Fix siehe Tabelle Nr. 10. Der neue Test ist ohne den Fix rot, mit ihm grün.

## 4. Nicht Teil dieses Laufs
Keine Modelle geladen, kein GPU-Lease nötig (Tests sind per `host_isolation.py` von nvidia-smi, LM Studio und PowerShell getrennt). Die 6 Symlink-Sicherheitstests laufen auf diesem PC nicht; sie wurden nicht anderweitig geprüft.
