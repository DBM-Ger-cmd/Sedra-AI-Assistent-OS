# JOB_SUPERVISOR_CONTRACTS

Stand: 2026-10-01 · Status: **Entwurf zur Freigabe (Phase 1). Kein Supervisor-Code existiert.**
Grundlage: `ARCHITECTURE_GAP_REPORT.md`, `INTEGRATION_PLAN.md`, `PHASE0_STATUS.md`, Code v1.20 + Phase-0-Änderungen.
Sprache der Verträge: Zustände, Feldnamen und Fehlercodes sind **Englisch** (wie im Bestand), Erläuterungen Deutsch.

Normative Wörter: **MUSS** = Pflicht, **SOLL** = Standard, Abweichung begründen, **DARF NICHT** = verboten.

---

## 1. Zuständigkeit

| Komponente | Verantwortet | DARF NICHT |
|---|---|---|
| **GUPPI** | Ziele, Planung, Entscheidungen, Eskalationsbewertung | Jobs selbst ausführen |
| **Job Supervisor** | Queue, Zustand, Lease, Heartbeat, Retry-Entscheidung, Cancel, Recovery, Audit der Übergänge | Provider/Modell wählen, Hardware steuern, Policy ändern, eigenes Projektgedächtnis führen |
| **Control Master** | Rolle → konkrete Runtime/Modell/Tool, Ausführung, Provider-Zustand, Cooldown | Jobzustand verändern |
| **Context Manager** | Budget, Manifest, Offloading, Checkpoint (siehe `CONTEXT_MANAGER_CONTRACTS.md`) | Jobzustand verändern |
| **Guard** | Entscheidung ALLOW/BLOCK/CAPTAIN_REQUIRED, Freigabe-Tokens | – |
| **Entwicklungsumgebung** | Änderungen, Tests, Kandidaten | – |

**Prüfregel (statisch testbar):** Der Quelltext des Supervisors enthält **keine** Provider-, Modell- oder Runtimenamen (`lm-studio`, `llama`, `qwen`, `kev` …). Der Supervisor kennt nur Rollen und Reason-Codes.

## 2. Grundprinzipien

1. **Erweitern, nicht ersetzen.** `DevelopmentJobStore` (v1.20, Phase 0) bleibt die Persistenz. `step_journal` bleibt für Mission-Schritte.
2. **Eine Wahrheit pro Zustand.** Der Supervisor-Zustand wird aus gespeicherten Feldern **berechnet**, nicht doppelt gespeichert (Abschnitt 4).
3. **Unbekannt ist nie Erfolg.** Ein Job, dessen Ausgang unbekannt ist, wird nie automatisch wiederholt, wenn er mutieren konnte (`UNKNOWN_EXECUTION_OUTCOME`, wie `step_journal`).
4. **Fallback umgeht keine Rechte.** Siehe 8.3.
5. **Append-only Enums.** Neue Zustände, Klassen, Events nur anhängen. Leser behandeln unbekannte Werte als `UNKNOWN` und stoppen den Job, statt zu raten.
6. **IDs werden nie wiederverwendet** (Job `SDJ-…`, Attempt `ATT-…`, Worker `WRK-…`).
7. **Heartbeats landen nicht im Audit.** Zustandswechsel, Lease-Ablauf, Retry, Fallback, Approval, Cancel, Recovery schon.

## 3. Datenmodell (Job Schema 2, rückwärtskompatibel)

Gespeichert im bestehenden Job-Datensatz `runtime_data/self_development/jobs/SDJ-*.json`. Felder, die v1.20 nicht kennt, sind **optional** beim Lesen (Default in Klammern). v1.20-Code ignoriert sie.

```text
Job (bestehend, unverändert):
  schema, job_id, parent_job_id, created_at, state, admission, contract, attempts,
  lease, last_heartbeat, last_progress, candidate, verification, comparison,
  activation, checkpoint, errors, rev, context_manifest, roles, development_environment

Job (neu, optional):
  kind                 "development"                        # später "mission_step" | "maintenance"
  depends_on           [job_id]                              # []
  requested_role       str | null                            # null
  selected_capability  str | null
  permission_level     int 0..6                              # aus contract.permission_level
  policy_hash          sha256 | null                         # Hash der wirksamen Policy beim Start
  queue                {enqueued_at, priority(0..9), not_before(ISO|null)} | null
  worker               {worker_id, claimed_at, lease_until, grace_until, state} | null   # ersetzt künftig `lease`
  heartbeat_seq        int                                   # 0, +1 je Heartbeat
  progress_seq         int                                   # 0, +1 je echtem Fortschritt
  progress_marker      str | null                            # Hash des aktuellen Schritts
  attempt_log          [Attempt]                             # []
  retry                {limit, count, next_not_before, last_class} # limit aus Config
  cancel               {requested_at, requested_by, reason} | null
  supervisor_flags     {escalated_to: null|"guppi"|"captain", dead: bool, rollback: null|"pending"|"done"}
  last_error           {class, reason_code, message(<=500), at} | null
  context_checkpoint_id str | null
```

**Attempt** (Element von `attempt_log`):
```text
attempt_id        "ATT-<uuid hex 12>"
started_at, ended_at (ISO UTC | null)
worker_id, role, capability
provider_ref      opaque (vom Control Master geliefert, vom Supervisor nur durchgereicht)
outcome           "RUNNING" | "SUCCEEDED" | "FAILED" | "ABANDONED" | "UNKNOWN"
failure_class     eine von FAILURE_CLASSES | null
reason_code       str | null
retry_decision    {action, retry_same_request, fallback_allowed, not_before} | null
context_manifest_id, context_checkpoint_id
usage             {input_tokens, output_tokens, peak_fill} | null     # nur Verweis, Details im Metrik-Log
```

**Invarianten (MÜSSEN gelten, per Test geprüft):**
- I1 `attempt_log` enthält höchstens einen Eintrag mit `outcome=="RUNNING"`.
- I2 `retry.count == Anzahl Attempts mit outcome in {FAILED, ABANDONED, UNKNOWN}` und `retry.count <= retry.limit`, außer bei Eskalation.
- I3 `heartbeat_seq` und `progress_seq` sind monoton steigend. Ein Rückgang ist `corrupt_job_record`.
- I4 `worker != null` ⇒ Zustand ∈ {CLAIMED, RUNNING, VERIFYING}.
- I5 `permission_level` darf nach `READY` **nicht** steigen (nur sinken).
- I6 `cancel != null` ⇒ Zustand führt nie wieder nach `RUNNING`.
- I7 `rev` steigt bei jedem Schreiben um genau 1 (Phase 0).

## 4. Zustandsmaschine

### 4.1 Berechneter Zustand

`supervisor_state(job)` ist eine **reine Funktion** des Datensatzes. Gespeichert bleibt das bestehende Feld `state` (v1.20-Zustände) plus `supervisor_flags`/`worker`/`queue`/`cancel`.

| Bedingung (in dieser Reihenfolge prüfen) | supervisor_state |
|---|---|
| `supervisor_flags.dead` | DEAD |
| `cancel != null` und `state` nicht final | CANCELLED (nach Abschluss des Abbruchs) / bis dahin Zustand wie gespeichert |
| `supervisor_flags.escalated_to == "captain"` | ESCALATED_TO_CAPTAIN |
| `supervisor_flags.escalated_to == "guppi"` | ESCALATED_TO_GUPPI |
| `supervisor_flags.rollback == "pending"` | ROLLBACK_PENDING |
| `state == ROLLED_BACK` | ROLLED_BACK |
| `worker != null` und `worker.state == "claimed"` | CLAIMED |
| `queue != null` und `worker == null` und `state == READY` | QUEUED |
| `state` laut Tabelle 4.2 | siehe Tabelle |

### 4.2 Abbildung der v1.20-Zustände

| gespeichert (`state`) | supervisor_state |
|---|---|
| CREATED | CREATED |
| PLANNING | PLANNING |
| READY | READY |
| BUILDING, TESTING | RUNNING |
| VERIFYING | VERIFYING |
| REWORK | RETRY_PENDING |
| READY_FOR_ACCEPTANCE | PASSED |
| ACTIVATION_PENDING | WAITING_APPROVAL |
| ACTIVATED | COMPLETED |
| BLOCKED | BLOCKED |
| REJECTED | FAILED |
| ROLLED_BACK | ROLLED_BACK |
| *unbekannter Wert* | UNKNOWN (Job wird nicht angefasst, Eskalation an GUPPI) |

### 4.3 Neue gespeicherte Zustände

Der Dev-Pfad kann diese nicht ausdrücken, sie werden **zusätzlich** in `ALLOWED` aufgenommen (bestehende Übergänge bleiben):

| Neu | Bedeutung | erlaubt von | erlaubt nach |
|---|---|---|---|
| `QUEUED` | eingereiht, wartet auf Claim | READY, REWORK | BUILDING (über Claim), CANCELLED |
| `CANCELLED` | abgebrochen, endgültig | alle nichtfinalen | – |
| `DEAD` | nicht wiederherstellbar (z. B. Lease-Ablauf + Unknown + mutierend, Retry-Limit ohne Eskalation möglich) | BUILDING, TESTING, VERIFYING, REWORK, BLOCKED | ESCALATED_* (nur als Flag, Zustand bleibt DEAD) |

`CLAIMED`, `ROLLBACK_PENDING`, `ESCALATED_*` sind **Flags/Felder**, keine gespeicherten Zustände (vermeidet doppelte Wahrheit). Das Feld `state` bleibt damit eine Obermenge von v1.20.

**Entscheidung offen (§15, E-1):** Ob `DEAD` ein gespeicherter Zustand oder nur das Flag ist. Entwurf: gespeicherter Endzustand `DEAD`, damit v1.20-Leser ihn als unbekannt erkennen und nicht weiterarbeiten.

### 4.4 Übergänge

Jeder Übergang MUSS: (1) unter der Store-Sperre geschehen (`mutate`), (2) gegen `ALLOWED` geprüft werden, (3) `rev` erhöhen, (4) ein Audit-Event schreiben, (5) idempotent sein (gleicher Aufruf mit gleicher `operation_id` ändert nichts und liefert dasselbe Ergebnis).

Zusätzliche Übergänge (zu den bestehenden aus `DevelopmentJobStore.ALLOWED`):

```text
READY      -> QUEUED        enqueue
REWORK     -> QUEUED        enqueue nach Retry-Entscheidung
QUEUED     -> BUILDING      claim + confirm_start
QUEUED     -> CANCELLED     cancel
BUILDING   -> REWORK        fail mit Retry-Entscheidung "retry"
BUILDING   -> QUEUED        abandon (Lease-Ablauf, Grace vorbei, Unknown-Regel erlaubt Wiederholung)
BUILDING   -> DEAD          abandon (mutierend + Ausgang unbekannt)
TESTING    -> REWORK|QUEUED|DEAD   analog
VERIFYING  -> REWORK|QUEUED|DEAD   analog
BLOCKED    -> QUEUED        resume nach Behebung
* (nichtfinal) -> CANCELLED cancel
```
Finale Zustände: `REJECTED`, `ROLLED_BACK`, `ACTIVATED`, `CANCELLED`, `DEAD`. Aus ihnen führt **kein** Übergang heraus.

## 5. Operationen (Schnittstelle des Supervisors)

Python-Signaturen sind Zielbild. Alle Operationen nehmen `operation_id` (str, vom Aufrufer) für Idempotenz. Alle liefern ein Dict mit `status` und dem aktualisierten Job. Fehler sind `JobError(code, detail)`.

| Operation | Vorbedingung | Wirkung | Audit-Event | Fehlercodes |
|---|---|---|---|---|
| `create_job(contract, role_requests, parent_job_id=None, depends_on=())` | gültiger Contract-Digest; Parent existiert | Job `CREATED` | `JOB_CREATED` | `invalid_contract`, `unknown_parent`, `dependency_cycle` |
| `enqueue(job_id, priority=5, not_before=None)` | Zustand READY/REWORK, `depends_on` alle COMPLETED/PASSED laut Config, Permission-Gate erfüllt | `queue` setzen → QUEUED | `JOB_ENQUEUED` | `not_ready`, `dependency_unmet`, `approval_required` |
| `claim(worker_id, roles, now)` | Worker hat Lease-Kapazität | wählt ältesten höchstpriorisierten QUEUED-Job mit passender Rolle, `not_before <= now`, setzt `worker{claimed}` | `JOB_CLAIMED` | `no_job`, `worker_busy` |
| `confirm_start(job_id, worker_id, attempt_id)` | Job CLAIMED durch diesen Worker | Attempt `RUNNING`, Zustand BUILDING, Lease gesetzt, `progress_seq`+1 | `JOB_STARTED` | `not_claimed`, `claim_expired` |
| `heartbeat(job_id, worker_id, lease_extend_s)` | Lease gehört diesem Worker | `heartbeat_seq`+1, `lease_until` verlängert (nie über `max_lease_s`) | **keins** | `lease_lost` |
| `report_progress(job_id, worker_id, marker, step=None)` | wie heartbeat | wenn `marker != progress_marker`: `progress_seq`+1, `progress_marker`=marker | **keins** (nur Zustandswechsel auditiert) | `lease_lost` |
| `complete_step(job_id, worker_id, next_state, result_ref)` | passender Zustand | Übergang gemäß 4.4, Attempt `SUCCEEDED` beim letzten Schritt | `JOB_STATE_CHANGED` | `invalid_transition`, `lease_lost` |
| `fail(job_id, worker_id, reason_code=None, exception=None, message=None, mutated=False)` | Attempt RUNNING | Klasse über `failure_classes.classify`, Retry-Entscheidung (6), Attempt `FAILED` | `JOB_FAILED`, ggf. `JOB_RETRY_SCHEDULED` / `JOB_ESCALATED` | `lease_lost` |
| `cancel(job_id, requested_by, reason)` | Zustand nicht final | `cancel` gesetzt; laufender Worker erhält beim nächsten Heartbeat `cancel_requested`; nach Stopp → CANCELLED | `JOB_CANCEL_REQUESTED`, `JOB_CANCELLED` | `already_final` |
| `reap(now)` | – | Lease-Prüfung (5.1) für alle aktiven Jobs | `JOB_LEASE_SUSPECT`, `JOB_LEASE_EXPIRED`, `JOB_ABANDONED` | – |
| `recover(job_id, resolution, approval_token)` | Job `DEAD`/Unknown | `resolution ∈ {abort, retry_readonly}` wie `brain.recover`; **Guard-Aktion `execution_recovery`** | `JOB_RECOVERED` | `mutating_job_cannot_be_replayed`, `approval_required` |
| `request_approval(job_id, action, target)` | Zustand erreicht Gate | Guard-Gate `HG-…` erzeugen, Job → WAITING_APPROVAL (4.2) | `JOB_APPROVAL_REQUESTED` | – |
| `resolve_approval(job_id, token)` | gültiger Guard-Token | Fortsetzung | `JOB_APPROVAL_RESOLVED` | `token_invalid` (Detail aus Guard) |
| `startup_recovery()` | beim Start | Jobs mit Worker/RUNNING ohne lebenden Prozess: gemäß 5.3 behandeln | `JOB_RECOVERY_STARTED/FINISHED` | – |

**Idempotenz:** `operation_id` wird im Job unter `ops` (letzte 64) abgelegt. Wiederholung → gleiches Ergebnis, kein neuer Audit-Eintrag, kein neuer `rev`.

## 6. Lease, Heartbeat, Fortschritt, Stuck-Erkennung

### 6.1 Begriffe
- **Heartbeat:** „Worker lebt". Erhöht `heartbeat_seq`. Sagt nichts über Arbeit.
- **Progress:** „Worker kommt voran". Erhöht `progress_seq`, nur wenn sich `progress_marker` (Hash des aktuellen Schritts) ändert. Gleichbleibender Marker bei Heartbeat = **Stagnation**.
- **Handover bestätigt:** `confirm_start` ist der Beleg, dass die Arbeit begonnen hat. Zwischen `claim` und `confirm_start` gilt `claim_timeout_s` (Config). Ablauf → Claim verfällt, Job zurück in QUEUED, Audit `JOB_CLAIM_EXPIRED` (Idee aus herdr: Übergabe ≠ Arbeitsbeginn).

### 6.2 Reaper (`reap`)
Läuft periodisch (Intervall Config) und beim Start. Uhrensprünge dürfen keine falschen Abbrüche auslösen. Deshalb:

1. `lease_until` ist **Wanduhr-UTC** (für Persistenz).
2. Der Reaper entscheidet **nicht** allein über `now > lease_until`, sondern beobachtet `heartbeat_seq`: Er speichert im Speicher je Job `(seen_seq, monotonic_t0)`.
3. **Verdacht** (`suspect`): `now > lease_until` **und** `heartbeat_seq` unverändert seit mindestens `suspect_after_s` (monotone Zeit im Reaper-Prozess).
4. Nach Verdacht: Healthcheck-Hook (vom Control Master bereitgestellt: „lebt der Worker/Provider?"). Antwort `alive` ⇒ Lease um `grace_s` verlängern, Audit `JOB_LEASE_GRACE`. Sonst Grace-Frist (`grace_until`).
5. Ablauf der Grace-Frist ⇒ **Abandon**:
   - Attempt `ABANDONED` (oder `UNKNOWN`, wenn `mutated` unklar).
   - Provider-Health-Signal an Control Master (Cooldown liegt dort, nicht hier).
   - Entscheidung nach Abschnitt 7. Kritischer Job (`priority>=8` oder `permission_level>=4`) ⇒ **immer Eskalation**.
6. **Stagnation:** `heartbeat_seq` steigt, `progress_seq` nicht seit `stall_after_s` ⇒ Audit `JOB_STALLED`, Fehlerklasse `context_quality_degraded` (Verdacht auf festhängendes Modell) ⇒ Context-Repair anfordern (siehe Context-Vertrag 8), **nicht** stumpfes Retry.

### 6.3 Neustart des Supervisors (`startup_recovery`)
| Fund im Job | Aktion |
|---|---|
| CLAIMED, kein confirm_start | Claim verwerfen → QUEUED |
| RUNNING, Attempt `RUNNING`, Prozess unbekannt, **nichtmutierende** Rolle (reiner Lesejob) | Attempt `ABANDONED`, → QUEUED |
| RUNNING, **mutierend oder unklar** | Attempt `UNKNOWN`, Job → DEAD, Eskalation an GUPPI; Wiederaufnahme nur über `recover` + Guard |
| `cancel != null`, Zustand nicht final | Abbruch abschließen |
| `supervisor_flags.rollback == "pending"` | Rollback fortsetzen (über `candidate_acceptance`, nicht hier) |
| unlesbare Datei | **Original sichern** (`jobs/_corrupt/<name>.<rev>.bak`, max. 3 Kopien), Job als `corrupt` melden, **nicht überschreiben** (Idee aus herdr) |

Ob eine Rolle „mutierend" ist, steht in der **Rollenkonfiguration** (`mutates: true/false`), nicht im Code (`coder`, `tool_operator` = true; `reviewer`, `planner` = false).

## 7. Retry- und Fallback-Entscheidung

Eingabe: `failure_class` (aus `failure_classes.classify`), Zähler, Config. Ausgabe: `retry_decision`.

```text
decide(job, failure_class, mutated):
  rule = failure_classes.retry_rule(failure_class)
  if rule.escalate:                            -> ESCALATE (Captain bei policy_denied, sonst GUPPI)
  if job.retry.count >= job.retry.limit:       -> ESCALATE (GUPPI)
  if mutated and attempt_outcome unknown:      -> DEAD + ESCALATE (nie automatisch wiederholen)
  if rule.next_action == "retry_with_backoff": -> RETRY, not_before = now + backoff(count)
  if "retry_limited_then_fallback":            -> RETRY bis `timeout_retry_limit`, danach FALLBACK_REQUEST
  if rule.fallback_allowed:                    -> FALLBACK_REQUEST (Control Master wählt, siehe 8.3)
  else:                                        -> REWORK (Änderung nötig) oder BLOCKED
```
- `retry_same_request == false` ⇒ der Supervisor DARF NICHT dieselbe Anfrage mit demselben Kontext erneut einreihen. Er verlangt eine Änderung (anderer Kontext, geänderter Code, anderer Provider, andere Queue-Position) und trägt sie in `retry.last_change` ein. Ohne Änderung ⇒ `BLOCKED`.
- `deterministic_test_failure`: Wiederholung nur, wenn sich `candidate_hash` geändert hat.
- Backoff: `min(base * 2**count, max_backoff)` mit Jitter ±20 %. Werte in Config.

## 8. Schnittstelle zum Control Master

### 8.1 Rollenauflösung
```text
resolve_role(role, requirements, *, exclude=(), policy) -> Resolution | ResolutionError

requirements:   offline_preferred, max_vram_gb, max_ram_gb, filesystem_scope,
                network ("denied"|"local"|"allowed"), test_required, data_class,
                context_min_tokens, exclusive
Resolution:     provider_ref (opak), capability_id, runtime_profile_id,
                context_window (effektiv, aus HardwareModelPass), estimated_resources {ram_gb, vram_gb, kv_cache_gb?},
                independence_key (siehe 8.4), reason
ResolutionError.code ∈ {no_capability, requirements_unmet, policy_denied, hardware_pressure, provider_unavailable}
```
`exclude` enthält `independence_key`s, die für diesen Job nicht erlaubt sind (Verifier-Unabhängigkeit).

### 8.2 Ausführung
`ControlMaster.execute(...)` bleibt der einzige Weg. Das Ergebnis enthält `usage` (falls Provider liefert), `status`, `reason_code`. Der Supervisor reicht den **Kontext** nicht selbst durch, sondern übergibt `context_manifest_id`.

### 8.3 Fallback
Der Supervisor erzeugt nur eine **Fallback-Anfrage** (`exclude` + Grund). Der Control Master entscheidet **innerhalb der Policy**. Harte Regeln (MÜSSEN getestet werden):
- `policy_denied` ⇒ **nie** Fallback.
- Fallback darf `permission_level`, `network`, `data_class` **nicht** lockern.
- Cloud/extern nur, wenn Policy `cloud_allowed: true` **und** Captain-Gate erteilt. Aktuell: kein Cloud-Adapter (`CLOUD_NOT_IMPLEMENTED`).
- Jede Fallback-Entscheidung wird auditiert (`JOB_FALLBACK_DECIDED`, mit Grund, ohne Secrets).

### 8.4 Unabhängiger Verifier (schließt F-4)
Heute prüft der Bestand nur `verifier != builder` als **String**. Der Vertrag fordert: `independence_key(builder) != independence_key(verifier)`. Der Schlüssel wird vom Control Master gebildet (z. B. Modellfamilie + Gewichts-ID) und ist für den Supervisor opak. Ist kein Schlüssel verfügbar, bleibt das Ergebnis `INCONCLUSIVE`, **nicht** `PASS`.

## 9. Berechtigungsstufen und Guard

Level 0–6 werden **keine** zweite Rechteschicht. `permission_levels.py` enthält nur eine Abbildung **Level → erlaubte Guard-Aktionen**. Jede Aktion läuft weiter durch `Guard.evaluate`.

| Level | Name | Guard-Aktionen (Entwurf, anhand `guard_rules.yaml` v1.20) |
|---|---|---|
| 0 | READ_ONLY | – (nur Lesen im Job-Kontext) |
| 1 | PROJECT_READ | `read_project_file`, `git_read` |
| 2 | DEV_ENV_WRITE | `create_new_artifact` (nur Entwicklungsumgebung) |
| 3 | TEST_EXECUTION | `sandbox_execute`, `shell_execute` (nur Sandbox) |
| 4 | PROJECT_WRITE | `overwrite_existing`, `candidate_accept`, `candidate_rollback`, `filesystem_move`, `git_init`, `execution_recovery` |
| 5 | SYSTEM_CHANGE | `model_runtime_control`, `model_profile_promote`, `hardware_profile_control`, `sandbox_image_import`, `core_update_install`, `file_delete` |
| 6 | EXTERNAL_ACTION | `external_write`, `deployment`, `credential_access`, `paid_action` |
| – | **nie automatisch** | `modify_core_invariants`, `bypass_guard`, `silent_stable_replacement` |

Regeln:
- Ein Job darf nur Aktionen bis zu seinem `permission_level` anfordern. Mehr ⇒ `policy_denied`. Das **Heraufsetzen** des Levels ist nur durch Captain möglich, nicht durch den Job (I5).
- Level 0–2: automatisch, wenn Guard `ALLOW`. Level 3: policy-abhängig, isoliert. Level 4: Review + Verifikation + Guard. Level 5/6: **immer** Captain-Gate (Guard-Standard `CAPTAIN_REQUIRED`).
- Unbekannte Guard-Aktion ⇒ weiter `CAPTAIN_REQUIRED` (Bestand).
- **Vor Phase 6 zu prüfen:** Die Zuordnung der 24 Aktionen ist ein Entwurf (jede Aktion steht genau einmal in der Tabelle, `execution_recovery` und `git_init` sind Einordnungen nach Namen). Sie wurde aus den Namen abgeleitet, nicht aus den Regeln selbst gelesen (`guard_rules.yaml` wurde nur als Aktionsliste ausgewertet).

## 10. Persistenz und Dateien

```text
runtime_data/self_development/jobs/SDJ-*.json        # bestehend
runtime_data/self_development/jobs/store.lock        # Sperre (Phase 0)
runtime_data/self_development/jobs/_corrupt/         # gesicherte defekte Dateien (neu)
runtime_data/self_development/evidence.jsonl         # bestehend
runtime_data/audit/events.jsonl                      # bestehend
```
- Schreiben ausschließlich über `mutate` (Sperre + `rev`).
- Eine Operation, die mehrere Felder ändert, MUSS in **einem** `mutate` laufen.
- Entscheidung offen (E-2): eigener Ordner `runtime_data/jobs/` mit `kind` oder Verbleib im Dev-Ordner.

## 11. Audit-Ereignisse (anhängen, nie umbenennen)

`JOB_CREATED, JOB_ENQUEUED, JOB_CLAIMED, JOB_CLAIM_EXPIRED, JOB_STARTED, JOB_STATE_CHANGED, JOB_FAILED, JOB_RETRY_SCHEDULED, JOB_FALLBACK_DECIDED, JOB_LEASE_SUSPECT, JOB_LEASE_GRACE, JOB_LEASE_EXPIRED, JOB_ABANDONED, JOB_STALLED, JOB_ESCALATED, JOB_CANCEL_REQUESTED, JOB_CANCELLED, JOB_APPROVAL_REQUESTED, JOB_APPROVAL_RESOLVED, JOB_RECOVERED, JOB_RECOVERY_STARTED, JOB_RECOVERY_FINISHED, JOB_CORRUPT_RECORD`

Pflichtfelder je Event (`payload`): `job_id`, `parent_job_id`, `rev`, `from`/`to` (bei Wechsel), `attempt_id`, `requested_role`, `selected_capability`, `permission_level`, `policy_hash`, `context_manifest_id`, `failure_class`, `reason_code`. **Keine Secrets**, keine Prompt-Inhalte, keine Tool-Ausgaben (nur Artefakt-Referenzen). Das bestehende `_redact` greift zusätzlich.

Bestehende Events (`SELF_DEVELOPMENT_STATE_CHANGED` usw.) bleiben unverändert und werden **weiter** geschrieben, solange Dev-Jobs sie nutzen. Neue Events sind additiv.

## 12. Konfiguration `config/job_supervisor.yaml` (Entwurf)

```yaml
job_supervisor:
  schema: 1
  enabled: false                 # Feature Flag, Default AUS
  workers: 1                     # Phase 2: genau ein Worker
  claim_timeout_s: 30
  lease_s: 120
  max_lease_s: 900
  heartbeat_interval_s: 20
  suspect_after_s: 60
  grace_s: 60
  stall_after_s: 300
  reap_interval_s: 30
  retry: {limit: 3, timeout_retry_limit: 2, backoff_base_s: 2, backoff_max_s: 120}
  critical: {min_priority: 8, min_permission_level: 4}
  roles:                         # Rollen sind Konfiguration, nicht Code
    coder:    {mutates: true,  capability: python_local_coding}
    planner:  {mutates: false, capability: planning}
    reviewer: {mutates: false, capability: code_review}
    verifier: {mutates: false, capability: verification, independent_of: [coder]}
    # …weitere Rollen aus Handoff §5
```
Fehlende oder ungültige Datei ⇒ Supervisor bleibt **aus**, `boot()` meldet den Grund. Werte außerhalb Grenzen ⇒ Start verweigert (kein stilles Clamping bei Sicherheitswerten).

## 13. Kompatibilität

- Flag aus ⇒ alle v1.20-Pfade und Tests unverändert.
- Dev-Jobs funktionieren ohne Supervisor wie bisher.
- Neue Zustände `QUEUED`, `CANCELLED`, `DEAD` sind für v1.20-Leser **unbekannt**: Sie müssen sie als „nicht weiterbearbeiten" behandeln. Das ist in `DevelopmentJobStore.transition` (`invalid_development_transition`) bereits der Fall.
- Rollback: Flag aus und Modul entfernen. Jobs in neuen Zuständen werden vorher per `startup_recovery` auf einen v1.20-kompatiblen Zustand gebracht (CANCELLED/DEAD → `REJECTED` mit `last_error`). Das ist als Migrationsskript in Phase 2 zu liefern und zu testen.

## 14. Testmatrix (Handoff §17 A–J → konkrete Tests)

| Gruppe | Testfälle (Auszug, alle ohne echtes Modell, mit FakeClock und FakeControlMaster) |
|---|---|
| **A Lifecycle** | Gültiger Pfad CREATED→…→COMPLETED. Jeder ungültige Übergang → `invalid_transition`. Finale Zustände bleiben final. Idempotente Wiederholung ändert `rev` nicht. |
| **B Crash Recovery** | Prozess stirbt in CLAIMED / RUNNING (lesend) / RUNNING (mutierend) / während `mutate`. Erwartung laut 6.3. Defekte Datei wird gesichert, nicht überschrieben. |
| **C Retry** | Jede der 12 Klassen führt zur Aktion aus `retry_rule`. Limit erreicht → Eskalation. `retry_same_request=false` ohne Änderung → BLOCKED. Backoff-Grenzen. Test-Fehler nur nach geändertem `candidate_hash` wiederholbar. |
| **D Provider-Fallback** | `policy_denied` → nie Fallback. Fallback lockert nie Level/Netz/Datenklasse. Kein Provider im Supervisor-Quelltext (statische Prüfung). |
| **E Permission** | Aktion über Level → `policy_denied`. Level nicht steigerbar (I5). Level 5/6 → Gate. Unbekannte Aktion → `CAPTAIN_REQUIRED`. Token einmalig. |
| **F Policy** | E3 nie auto-aktiviert. `may_activate=False` unveränderlich. Config kann Kernschutz nicht lockern. |
| **G Concurrency** | Zwei Worker, ein Job: genau ein Claim. Heartbeat gegen Statuswechsel (Phase 0). Mehr Prozesse als Slots → warten. |
| **H Unabhängige Verifikation** | gleicher `independence_key` → INCONCLUSIVE. Fehlender Schlüssel → INCONCLUSIVE. PASS nur mit Beleg (Phase 0.6). |
| **I Rollback** | Rollback läuft über `candidate_acceptance`. Flag `rollback=pending` übersteht Neustart. |
| **J Restart-Persistenz** | Queue, Retry-Zähler, Lease, Cancel überstehen Neustart. `heartbeat_seq`/`progress_seq` bleiben monoton. |
| **Uhr** | Uhr springt vor/zurück: kein falscher Abbruch, kein ewiger Lease (Abschnitt 6.2). |
| **Stall** | Heartbeat ohne Progress → `JOB_STALLED`, Context-Repair statt Retry. |
| **Handover** | claim ohne confirm_start → nach `claim_timeout_s` zurück in Queue. |

Alle Tests laufen auf **diesem PC (Windows)** und in der Sandbox-losen Variante. Sie sind **keine** reale Abnahme (Hardware, Modelle).

## 15. Offene Entscheidungen

| # | Frage | Empfehlung |
|---|---|---|
| E-1 | `DEAD` als gespeicherter Zustand oder nur Flag? | gespeicherter Endzustand |
| E-2 | Eigener Job-Ordner oder Dev-Ordner? | eigener Ordner `runtime_data/jobs/`, Dev-Jobs bleiben bis Phase 8 |
| E-3 | `claim` pull (Worker holt) oder push (Supervisor weist zu)? | pull; einfacher zu recovern |
| E-4 | Reaper als Thread im Runtime-Prozess oder eigener Prozess? | Thread, Phase 2 mit einem Worker; Prozess erst bei Parallelität |
| E-5 | Priorität 0–9 ausreichend, oder FIFO-only in v1? | FIFO + Priorität, Fairness später |
| E-6 | Welche Rollen sind `mutates: true`? | coder, tool_operator, hardware_engineer, documentation (Schreiben); Rest false. Vom Captain zu bestätigen |
| E-7 | Positivliste für E1-Ziele (aus Phase 0, noch offen) | ja, unbekannte Ziele → E2 |
| E-8 | `independence_key`-Bildung | Control Master: Modellfamilie + Gewichts-Hash; ohne Hash → INCONCLUSIVE |

## 16. Abnahme dieses Vertrags (Phase 1)

- [ ] Captain hat Abschnitte 3, 4, 7, 9 und die Entscheidungen E-1 bis E-8 geprüft.
- [ ] Context-Vertrag (`CONTEXT_MANAGER_CONTRACTS.md`) schließt die Lücken zu 6.2 (Stall) und 8.2 (Manifest).
- [ ] Kein Widerspruch zu Guard, `step_journal` und `DevelopmentJobStore` (Abschnitt 4.2 und 13).
