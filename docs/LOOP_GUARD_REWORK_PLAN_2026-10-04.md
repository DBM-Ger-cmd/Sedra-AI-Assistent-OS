# Plan: wire the loop guard into the rework loop (2026-10-04)

Status: **plan only, nothing built.** Needs the Captain's go for each phase.
Module: `runtime/src/guppi_runtime/loop_guard.py` (36 tests, see LOOP_GUARD_E1_ATTEMPT_2026-10-04.md). Nothing calls it yet.

## 1. What the rework loop is today

- **E1 harness** (`benchmarks/e1_golden_path.py`): `generate` -> `test` (VM, Captain gate) -> `review` (Gemma). A failed VM test goes through `rework` (feedback + previous candidate go to the next `generate`); a rejected review puts the job into REWORK. Failures of `generate` itself (`model_answer_truncated`, copied candidate, ...) are written to `discarded_generations`. The Captain's hint is the state key `captain_hint`.
- **Job supervisor** (`job_supervisor.py`): `reject_verification` sets `retry.awaiting_change = "candidate_hash"`: an identical candidate is never re-queued. `decide` has a retry limit (3) per failure class.
- **Brain** (`brain.py`, phase REWORK): bounded by `max_rework_cycles = 3` and a Captain gate for every new execution.

## 2. The gap

The supervisor stops an *identical candidate*. It does not stop a *different candidate that fails for the same cause*, and it does not see a failure class that keeps coming back. Evidence from the saved state of the `uix_window` run (`runtime_data/e1_golden_path/uix_window/state.json`, 24 discarded generations): the `parsed.port` ValueError survived many generations; 5 of the first 13 generations were `model_answer_truncated` or "thought until the token limit"; two copied the previous candidate. Each generation costs minutes of GPU. Existing rule (memory): "when a candidate fails twice on the same cause, offer the Captain a hint rather than burning more generations" - today that is a human judgement, not a check.

## 3. Design

### 3.1 Mapping rework onto `LoopGuard`

`LoopGuard` judges "the same call keeps returning the same outcome". For rework:

- **call** = tool `"rework"`, args `{"for": <signature of the failure being answered>, "hint": <sha of captain_hint or null>}`
- **outcome** = the failure signature of the new attempt (output), `is_error = True`; a success is not recorded (the loop ends).
- `generic_repeat`: the answer to failure A is again failure A (same cause, different candidate). Fires at the 3rd attempt (`repeat_threshold=3`): after two identical failures the next generation is not started.
- `ping_pong`: fixing A produces B and fixing B produces A (the calls `for=A` and `for=B` alternate with constant outcomes). `ping_pong_threshold=4`.
- A new Captain hint changes `args` (the `hint` field), so it is a new call and the guard lets the next generation run. No explicit reset needed.
- `guarded = {"rework"}`; the history is capped at the default 24.

### 3.2 Failure signature (new, small, deterministic)

`failure_signature(kind, text)` in a new module `rework_watch.py`. Stable across candidates, so it must drop what changes between attempts.
- VM test failure: sorted set of failing test ids (`FAIL:`/`ERROR:` lines) + exception types + the REPRO lines' *input* and exception (the harness already writes them: `REPRO input ..., exception, line`), with numbers, line numbers, paths, hashes and object addresses removed. Candidate line numbers are dropped on purpose (they move between candidates).
- Generation failure: the error class only (`model_answer_truncated`, `model_answer_empty`, `model_output_not_json`, `candidate_identical_to_previous`, ...). Review rejection: `review_fail` plus the first normalised finding words.
- Output is the first 16 hex of a SHA-256 over the normalised string, like the guard's own hashes.

### 3.3 Persistence

`LoopGuard` is in memory and each E1 stage is a new process. Store the recorded entries (tool, args, output, is_error; at most 24) in the job state and replay them with `record` at the start of each stage:
- E1 harness: `state["rework_watch"]` in `state.json`.
- Supervisor (phase 2): `job["retry"]["progress"]` next to `awaiting_change`.
No change to `loop_guard.py` is needed; replaying 24 entries is trivial.

### 3.4 What happens when it says "stuck"

Never silently: the stage returns `{"status": "rework_stalled", "detector", "count", "repeated_failure": <short text>, "options": [...]}` before loading any model (like `coder_not_available` today), and writes an audit event `REWORK_STALLED` (job, detector, count, signature). Options offered to the Captain: give a hint (`captain_hint`), change the coder/profile, change the spec, or stop. The guard only recommends; it never cancels the job or changes state beyond the record.

## 4. Phases

**Phase 1 - E1 harness only (small, reversible).**
1. `rework_watch.py`: `failure_signature`, `ReworkWatch` (load/save list, `check(for_sig, hint)`, `record(for_sig, outcome_sig)`), thresholds 3 and 4.
2. `e1_golden_path.py`: at the start of `generate_stage` call `check`; in `rework_after_failed_test`, in the `generation_failed` branch, in `review_stage` on FAIL and when the candidate equals the previous one call `record`. New status `rework_stalled`. Backup first (`.bak-2026-10-04-rework-watch`), keep CRLF.
3. Tests in `runtime/tests/test_rework_watch.py` (run only these): signature stability (same cause, different line numbers and paths -> same signature; different test -> different), persistence round trip, the three scenarios (same cause x2 -> stalled on the 3rd; A/B alternation -> stalled; hint changes -> allowed again), a generation-failure streak.

**Validation before trusting it (no model needed):** replay the 24 discarded generations of `uix_window` and the 6 of `self_diagnosis`/others through `ReworkWatch` and print where it would have stopped, and whether it would ever have stopped a run that later succeeded (false stop). Acceptance: no false stop on a run that ended in success; it fires on the `parsed.port` streak and on repeated truncation. If it would have fired too early, raise the thresholds, not the matching.

**Phase 2 - job supervisor (only after phase 1 proved itself).**
`reject_verification` and the failure path of `decide` call the same watch; the stall becomes a supervisor flag `awaiting_captain` plus the audit event, instead of another queue entry. Touches a 1330-line shared module and its tests (run `test_job_supervisor` only).

**Phase 3 - UIX (optional).** Show "rework stalled" with the repeated failure and a field for the hint (the UIX has gate and rejection endpoints; the hint endpoint is new). Separate decision.

Not planned: the brain's rework phase (already bounded by `max_rework_cycles` and a gate per cycle).

## 5. Risks and open decisions

- **False stops** are the main risk: a normaliser that is too coarse treats different failures as the same. Mitigation: replay validation, conservative thresholds, the guard only advises.
- **Hash of the hint** as part of the call means any hint text, even a useless one, re-opens the loop. Acceptable: the Captain decides.
- **Not a GUPPI self-development result:** `loop_guard.py` was written by the assistant. The wiring would also be written by the assistant, or can be offered to GUPPI as a new E1 scenario later (a good test: the scenario would be `rework_watch.py` with a stub and tests, but note GUPPI's review step failed twice on the guard itself, see the attempt log).
- `e1_golden_path.py` is a guided harness, not the runtime; phase 1 therefore changes the tool the Captain uses, not GUPPI's core behaviour.

Decisions for the Captain: (a) go for phase 1 as described; (b) thresholds 3 / 4 as proposed or other; (c) whether phase 2 and 3 are wanted at all after the replay results.

## Phase 1 built (2026-10-04, Captain: go, thresholds 3 and 4)

Files: `runtime/src/guppi_runtime/rework_watch.py` (new), `runtime/tests/test_rework_watch.py` (27 tests, new), `runtime/benchmarks/e1_golden_path.py` (backup `.bak-2026-10-04-rework-watch`, CRLF kept).

Differences from the plan above:
- **Two guards instead of one** (the plan's single mapping could not give both results): the `repeat` guard uses a constant call (only the Captain's hint changes it) and the outcome is the failure signature, so the third generation is stalled after two identical failures (threshold 3); the `ping_pong` guard uses the call "answering failure A" and stalls the fifth generation after A, B, A, B (threshold 4). Both are `LoopGuard` instances replayed from `state["rework_watch"]` (at most 24 entries).
- Failure signatures: `test:` (REPRO lines without their " at ..." tail, failing test ids, exception lines; file names, line numbers, hex addresses removed), `gen:` (error class only, the detail after it ignored), `review:` (every rejected review counts the same).
- Hooks in the harness: `generate` checks first and returns `rework_stalled` (plus audit event `REWORK_STALLED`) before loading any model; failed generations (each try), failed VM tests (`rework`) and review FAILs are recorded. New stages `watch` (show) and `watch_reset` (forget, audit `REWORK_WATCH_RESET`, old list kept in the state). A new `captain_hint` in `state.json` lets the next generation run.
- Run only these tests: `cd runtime/tests; PYTHONPATH=../src python -m unittest test_rework_watch` -> 27 OK. They include the harness gate with a stub runtime (nothing is loaded).

Replay against the saved states (no model; test failures re-read from the sandbox receipts, other discarded reasons counted as unknown, i.e. never equal):
- `uix_window` (25 generations): stops before generation 3 (same `^...$` failure twice, which is what happened: generation 3 was "identical to the previous candidate"), before 11 and 14 (repeated token-limit/truncation), before 15. It does not fire in between where the failures differ.
- `loop_guard` job 3: stops before generation 3 (two truncations), which would have saved the 395-second third Gemma run.
- `self_diagnosis` (successful run): never stops.
Limits of the replay: the "other" reasons are free-text notes of earlier sessions and were counted as unknown, so the real stops can differ; the thresholds were not changed.

Not done (decisions pending): phase 2 (job supervisor), phase 3 (UIX hint field).

## Phase 2 built: job supervisor (2026-10-04)

`job_supervisor.py` (backup `.bak-2026-10-04-rework-watch`, CRLF kept):
- New jobs carry `retry.watch` (the persisted history) and `retry.captain_hint`; older jobs get the fields on first use.
- `_stall_if_repeating(job, signature)`: called where a job goes to REWORK with a change awaited, i.e. in `_apply_failure` for the AWAIT_CHANGE decision and in `reject_verification`. It records the failure signature (a failed test: `test:`, other classes: `gen:` + reason code, a rejected review: `review:`) and asks the watch. If stuck, the job goes to BLOCKED with `escalated_to = captain`, `last_error.reason_code = rework_stalled`; audit `JOB_REWORK_STALLED` (detector, count, failure) and `JOB_ESCALATED`. Transient/infrastructure failures (retry, fallback) are not rework and are not recorded.
- `give_hint(job_id, text, resolved_by)`: only for a stalled job; text 1 to 2000 characters and different from the last hint (`hint_not_new`); sets `retry.captain_hint`, clears the escalation, BLOCKED -> REWORK (new transition), audit `JOB_HINT_GIVEN`. The job still needs a different candidate (`supply_change`) before it is queued.
- `reject_verification` now returns the real state (`REWORK`, or `BLOCKED` when stalled).
- Tests: `StalledReworkTests` in `tests/test_job_supervisor.py` (8). Run: `test_job_supervisor`, `test_verification_gate`, `test_job_worker` -> 139 OK.

## Phase 3 built: UIX (2026-10-04)

- `uix_server.py` (backup `.bak-2026-10-04-rework`): read-only `GET /api/rework` (`rework_view`: stalled supervisor jobs and stalled E1 runs found in `runtime_data/e1_golden_path/**/state.json`) and `POST /api/rework/hint` (`rework_hint`: supervisor job -> `give_hint`; E1 run -> `captain_hint` in its state; anything not stalled is refused; audit `UIX_REWORK_HINT_GIVEN`).
- `uix/js/rework.js` (new) wraps `renderRunning` of models.js, so a card "Rework steckt fest" with a text field and the button "Hinweis geben" appears under "Läuft gerade" in the models window; models.js itself is untouched. One script tag added to `retro_desktop.html` (backup `.bak-2026-10-04-rework`).
- Tests: 6 in `tests/test_uix_server.py` (backup `.bak-2026-10-04-rework`), whole module + `test_rework_watch`: 82 OK (1 skipped, not ours).
- Harness fix found while planning the real check: `captain_hint` only reached the model together with failed-test feedback; it now also reaches it when there is none (e.g. after truncated answers).

## Real-model check (2026-10-04, Captain: check with a real model once everything stands)

Subject: job SDJ-4664296CEFFC (loop_guard, state `runtime_data/e1_golden_path/loop_guard/state.json`, copy before the check: `state.before-real-check.json`), real runtime, profile `standard` (coder falls back to gpt-oss, qwen3-coder still rejected for RAM).

1. Backfill: the 4 real `model_answer_truncated` attempts (M-E34CB788, M-2E7E88DC, M-F0F7E699, M-C61355F7; they happened before the watch existed) were written into `rework_watch`; mission/generation fields cleared as in every earlier retry. `watch` showed `stuck: true, generic_repeat, count 5`.
2. `generate` stopped with `rework_stalled` at once: no llama-server was started, audit event `REWORK_STALLED` written (EVT-006274).
3. `UIXHub.rework_view()` listed the job; `rework_hint()` stored a hint in the state (audit `UIX_REWORK_HINT_GIVEN`); the view was empty afterwards. (Hub logic on the real project; the browser card itself was not clicked.)
4. `generate` with the hint ran with the real model (gpt-oss-20b): first try truncated again (M-83289798, recorded under the hint's key), second try completed: mission M-BE2CAA0A, candidate CAND-2FE3E1B54730, phase CANDIDATE_REVIEW, 6513 tokens in, 12076 out. Run on the host against the 36 scenario tests (not in the VM): 36 OK.

Not shown by this check: that the hint text changed the model's behaviour (a different model than the earlier failures wrote this candidate, so the effect cannot be isolated); that the hint reached the prompt is established by the code path only. The VM test (Captain gate) and Gemma's review of this candidate were not run.

### Result of the real check, continued: VM test and review of CAND-2FE3E1B54730

- VM test (Captain gate HG-0CC22A18, mission M-BE2CAA0A): PASS in GUPPI's microVM, job SBX-04db267f4d8c46919e05dc2ff1b9ffe7, 36/36 tests (report sha256 de8d3e0c...).
- Gemma review: **FAIL** again, third time on this scenario, with a general claim ("the ping_pong logic incorrectly handles the alt count and the expected sequence ... will not correctly identify the sequence length or the no-progress condition") and no concrete input. The job SDJ-4664296CEFFC is in REWORK (activation BLOCK, candidate_not_ready); a second review is not possible in that state.
- Differential test (assistant's reference vs the candidate, 4000 random runs, 81072 `check` calls, random thresholds 2 to 6, window 3 to 24, five tool names including a colon name and an unguarded one, random outcomes and errors): **0 differences** in `stuck`, `detector` and `count`, and equal `recorded_count`. Caveat: the reference is the assistant's own reading of the spec, so this shows the candidate equals that reading, not that the spec is without ambiguity.
- Reading: three Gemma FAILs on three different candidates, none with a reproducible counter-example, while the VM tests and the differential test agree. The one-line verdict at temperature 0 without thinking is not a reliable judge for this spec; the weak step is the review, not the generated code. Nothing was changed in the review. Whether to give the review a more structured form is a Captain decision.
