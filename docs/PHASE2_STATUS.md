# PHASE2_STATUS – Minimal-Supervisor

Stand: 2026-10-01 · Testumgebung: Windows 11, Python 3.14.7. **Kein Zielgerät, keine Modelle, keine Hardware-Qualifizierung.**

**Ergebnis:** `python -m unittest discover -s tests` → **483 Tests, 0 Fehler, 5 übersprungen** (alle 5 sind Symlink-Tests, siehe PHASE0_STATUS). `validate_package.py` und `compileall` sind OK.
Der Supervisor ist **standardmäßig AUS** (`enabled: false`). Mit dem Flag aus verhält sich GUPPI wie v1.20.

## Umgesetzte Entscheidungen (vom Captain übernommen)

| Entscheidung | Umsetzung |
|---|---|
| E-1 `DEAD` gespeichert | Endzustand `DEAD`. v1.20-Leser kennen ihn nicht und fassen den Job nicht an (Test) |
| E-2 eigener Ordner | `runtime_data/jobs/` (`SupervisorJobStore`). Dev-Jobs bleiben in `self_development/jobs/` |
| E-3 pull | Worker holt per `claim` |
| E-5 FIFO + Priorität | Priorität 0–9, dann Alter, dann Job-ID |
| E-6 mutierende Rollen | `coder, tool_operator, hardware_engineer, documentation` in `config/job_supervisor.yaml` |
| E-7 E1-Positivliste | `E1_TARGETS = {skill, topic, documentation}`. Fehlendes Ziel = `skill`. Alles andere Unbekannte (Tippfehler, neue Art, Nicht-String) = **E2**, also Captain-Gate |
| E-C1 Tokenschätzung | betrifft Phase 3, hier nicht berührt |
| E-4 Reaper als Thread | **noch nicht umgesetzt**, siehe „Nicht umgesetzt" |

## Neue und geänderte Dateien

| Datei | Inhalt |
|---|---|
| `src/guppi_runtime/job_supervisor.py` (neu) | `SupervisorConfig`, `SupervisorJobStore`, `supervisor_state()`, `JobSupervisor`, `WorkerContext` |
| `config/job_supervisor.yaml` (neu) | alle Schwellen, Flag, 11 Rollen |
| `tests/test_job_supervisor.py` (neu) | 78 Tests |
| `src/guppi_runtime/runtime.py` | Supervisor wird verdrahtet, `boot()` meldet Status, bei ungültiger Config bleibt er aus und nennt den Grund |
| `src/guppi_runtime/uix_server.py` | `/api/supervisor` (nur lesend) |
| `src/guppi_runtime/self_development.py` | `mutate()` schreibt nur bei tatsächlicher Änderung (idempotente Wiederholung ändert `rev` nicht) |
| `src/guppi_runtime/evolution_targets.py`, `tests/test_evolution_targets.py` | E1-Positivliste |

## Was der Supervisor kann

- **Lebenszyklus:** `create_job → enqueue → claim → confirm_start → complete_step → mark_passed`. Der berechnete Zustand folgt Vertrag 4.2.
- **Übergabe bestätigt:** `claim` ohne `confirm_start` verfällt nach `claim_timeout_s` (Reaper) bzw. wird von `confirm_start` abgelehnt (`claim_expired`).
- **Heartbeat ≠ Progress:** `heartbeat_seq` und `progress_seq` getrennt, Fortschritt zählt nur bei geändertem Marker. Heartbeats werden **nicht** auditiert (Test).
- **Reaper:** Ablauf der Lease zählt nur zusammen mit einem **unveränderten `heartbeat_seq`** über `suspect_after_s` (monotone Zeit). Danach Verdacht → Healthcheck-Hook → Grace → Abandon. Ein Wanduhr-Sprung (vor/zurück) tötet keinen lebenden Worker (Tests).
- **Abandon-Regeln:** lesende Rolle → zurück in die Queue; **mutierende Rolle mit unbekanntem Ausgang → `DEAD` + Eskalation, nie automatisch wiederholt**; kritischer lesender Job → `BLOCKED` + Eskalation.
- **Stagnation:** Heartbeats ohne Progress → `JOB_STALLED`, Klasse `context_quality_degraded`, Job wartet auf **neuen Kontext** (`REWORK`, `awaiting_change`), kein stures Retry.
- **Retry/Fallback:** Entscheidung aus `failure_classes.retry_rule`. Alle 12 Klassen sind getestet. Backoff mit Jitter und Deckel. Retry-Limit endet in Eskalation. **Dieselbe Anfrage wird bei `retry_same_request=false` nie erneut eingereiht**: ohne `supply_change` (anderer Kandidat, Kontext oder Input) bleibt der Job in `REWORK` (`change_required`).
- **Policy:** `policy_denied` → nie Fallback, Eskalation an den **Captain**, `enqueue` und `resume` werden abgelehnt. Text, der „policy" erwähnt, wird nie wiederholbar klassifiziert (Test).
- **Cancel:** sofort vor dem Start, kooperativ während der Arbeit (Heartbeat meldet `cancel_requested`, `acknowledge_cancel`), bei verschwundenem Worker ohne Retry. Idempotent.
- **Wiederanlauf:** `startup_recovery` löst Claims, beendet offene Abbrüche, behandelt laufende Jobs nach den Abandon-Regeln. Beschädigte Job-Dateien werden nach `_corrupt/` **gesichert und nie überschrieben**, höchstens 3 Kopien je Datei, keine Duplikate.
- **`recover`:** Guard-Aktion `execution_recovery` mit Gate und Token, der an `job_id`, `rev`, Auflösung und Versuchszahl gebunden ist. Verändert sich der Job nach der Freigabe, gilt der Token nicht mehr. Wiederholen von mutierender Arbeit wird abgelehnt.
- **Parallelität:** Genau **ein** Worker. Atomares Claiming über Threads (6 Threads, 1 Gewinner) und **Prozesse** (4 Prozesse, 1 Gewinner).
- **Überprüfung der Grenzen:** Der Quelltext enthält **keinen** Provider-, Modell- oder Runtimenamen (statischer Test). Keine Secrets und keine Prompt-Inhalte im Audit (Test).

## Messwerte (dieser PC, Windows, nur Orientierung)

| | 50 Jobs | 200 Jobs |
|---|---|---|
| `create_job` | 25 ms | 27 ms |
| `enqueue` | 7 ms | 8 ms |
| `claim` + `confirm_start` | 26 ms | 57 ms |
| `heartbeat` | 7 ms | 8 ms |

Die erste Fassung brauchte bei `enqueue` 48 ms bei 200 Jobs, weil sie alle Dateien las. Sie liest jetzt nur noch die Abhängigkeiten.
`claim` und `reap` lesen **alle** Job-Dateien. Bei vielen tausend Jobs wird das langsam. Grenze nicht gemessen.

## Nicht umgesetzt oder nicht verdrahtet (ehrlich)

1. **Kein Reaper-Thread, kein Worker-Loop.** `reap()` muss von außen aufgerufen werden. Nichts im Runtime ruft `reap()` oder `run_next()` auf. Das Flag ist aus, also läuft nichts von allein. Ein Treiber folgt, sobald Control Master und Context Manager angebunden sind (Phase 3 bis 5).
2. **Keine Rollenauflösung / kein Control Master:** `provider_ref` bleibt leer, solange kein Control Master ihn setzt (Phase 5). Fallback ist darum bisher nur eine **Eintragung** (`retry.exclude`, Audit `JOB_FALLBACK_DECIDED`), nicht eine echte Wahl.
3. **`mark_passed` ist nicht an den Evidence-Store angeschlossen:** Der Runtime übergibt kein `pass_gate`, also **lehnt `mark_passed` ab** (`verification_gate_unavailable`). Das ist Absicht (sicherer Default). Die Anbindung an die Beleg-Prüfung aus Phase 0.6 folgt mit dem Verifier.
4. **Keine Permission-Level-Durchsetzung, keine `request_approval`/`resolve_approval`** (Phase 6). `permission_level` wird gespeichert und darf nur sinken, aber nichts prüft Aktionen dagegen.
5. **`independence_key` fehlt** (Phase 5), damit bleibt F-4 im Dev-Pfad offen.
6. **`policy_hash`, `context_checkpoint_id`, `context_manifest_id` bleiben leer** (Phase 3).
7. **Keine Migration für den Rückbau** (Vertrag 13): Jobs in `QUEUED`/`CANCELLED`/`DEAD` müssten vor einem Rückbau auf v1.20-Zustände gebracht werden. Das Skript fehlt.
8. **Claim-Timeout** vergleicht Wanduhrzeit. Ein Uhrsprung kann einen Claim zu früh oder spät freigeben. Folge ist harmlos (Job zurück in die Queue bzw. `claim_expired`), aber nicht wie die Lease mit monotoner Zeit abgesichert.
9. **Eine Sperre für den ganzen Store**, Sperrdatei `store.lock` bleibt liegen. Bei einem Worker unkritisch.
10. **Windows-Verhalten unter Antivirus/Dateisystem-Last** nicht gemessen. Die Tests liefen auf einem Entwickler-PC.
11. **Fehlerklassen** sind nicht gegen echte Provider-Fehler geprüft. Mit echten Fehlertexten kann ein Fall als `unknown_failure` landen und eskaliert dann (das ist die sichere Seite, aber nicht bequem).
12. Die zweite Job-Welt (Dev-Jobs in `self_development/jobs/`) und die Supervisor-Jobs sind **getrennt**. Die Zusammenführung ist Phase 8.

## Abweichungen vom Vertrag

| Vertrag | Umsetzung |
|---|---|
| Abschnitt 5 `resolve_approval`, `request_approval` | zurückgestellt (Phase 6) |
| `recover … abort` bei `BLOCKED` | schließt den Job als `CANCELLED` (Vertrag sagte nur „Eskalation schließen"). Bei `DEAD` bleibt er final |
| Abschnitt 3: Feld `worker` ersetzt künftig `lease` | v1.20-Feld `lease` bleibt im Datensatz (`null`), `worker` trägt die Lease |
| Abschnitt 5: Idempotenz | nur für `enqueue` und `cancel` über `operation_id`, `complete_step` nutzt sie ebenfalls. Andere Operationen sind über ihren Zustand idempotent genug, nicht über IDs |

## Was als Nächstes ansteht

Phase 3 (Context v1): Tokenschätzer und Metriken zuerst (reine Erfassung), dann Budget-Auflösung, Offloading, Checkpoint, Watermark-Aktionen. Der Supervisor liefert dafür bereits `progress_seq`, `retry`, `attempt_log` und die Stagnations-Meldung.
