# Plan: extending loop_guard and rework_watch with lessons from StarNet (2026-10-04)

Status: **plan only, nothing built.** Source of the ideas: the review of StarNet (`<projekte>\starnet-feat-harness-backend`, MIT code; memory note `starnet-review-2026-10-04`). Each item below was checked against GUPPI's code and data first; two of the originally proposed items are deliberately cut down or deferred.

Modules concerned: `runtime/src/guppi_runtime/loop_guard.py`, `rework_watch.py`, `job_supervisor.py`, `benchmarks/e1_golden_path.py`, `models/openai_local.py`.

## 0. What was checked

- `loop_guard.py` has **no consumer** that feeds it tool-call outcomes. GUPPI's coder is a single-shot JSON call (`code_generation.generate`, `"stream": False`), there is no multi-turn tool loop. Only `rework_watch.py` uses `LoopGuard`, with failure signatures, not raw tool output.
- A "warn at N, block at N+1" level (StarNet's `warnAfter 3`, `exactBlockAfter 4`) does not map onto the rework watch: with threshold 3 a warning would fire after every first failure, which says nothing. It only makes sense where a model can be told "you are repeating yourself" in the same run, i.e. a future tool loop. **Deferred, not planned now** (design when a consumer exists: a `level()` method next to `check`, warn at threshold minus 1).
- Real data: the saved states of earlier runs contain the candidates. Normalising whitespace and hashing them finds, in `uix_window` (15 candidates with content), **exactly the two cases the Captain's notes called out by hand**: generation 3 = generation 2 ("identical to the previous candidate, same `^...$`") and generation 6 = generation 5 ("qwen3-coder copied the previous version unchanged"). No identical pair in `self_diagnosis` (2) and `loop_guard` (1). Detection matches the manual judgement with zero false positives on this data.

## 1. Item C: "candidate unchanged" as a rework signal (the main item)

Why: StarNet's `stallSignal` asks what the ledger can prove (no file changed, no commit). For GUPPI the ledger fact is the candidate itself. An identical candidate is a certain no-progress, it costs a VM run and a Captain gate for nothing, and today only a human notices.

Design:
- `rework_watch.candidate_key(changes)`: SHA-256 (16 hex) over, per changed file, `path` + the content with CRLF -> LF and whitespace runs collapsed. Comments and code are kept, so a one-character change is a different candidate. Only **exact identity after whitespace normalisation** counts; near-identical candidates (StarNet's similarity "echo" is for prose summaries) are not skipped, because a one-line edit can fix a failing test.
- Harness, `generate_stage`, after a completed generation: compare the new key with the keys of `previous_candidate` and of every `discarded_generations[].candidate`. If equal: do **not** bind the candidate and do not offer it for a test; record `generation = "refused"` with reason `candidate_unchanged (same as attempt N)`, record `failure_signature("gen", "candidate_unchanged")` in the watch, return `generation_failed`. No VM run, no gate. With the existing thresholds two such attempts in a row stall the job to the Captain.
- Supervisor, `supply_change` (`candidate_hash == last_candidate_hash`): today it raises `change_not_different`. New: the same event is recorded in `retry.watch` as `gen:candidate_unchanged` (persisted before the exception leaves the `mutate` block, so the exception is raised after the block), then raised as before. Two identical candidates in a row stall the job like any other repeat.
- Evidence it is needed: the identical candidates above; the harness now keeps their content in `discarded_generations`.

Validation before switching on: replay the saved states (the check above, extended into a test fixture) must find exactly generations 3 and 6 of `uix_window` and nothing in the other two states.
Tests (new, only these are run): `candidate_key` (CRLF/whitespace invariant, one-character change differs, other file name differs), harness gate with a stub (identical candidate refused and recorded, different candidate passes through), supervisor (`change_not_different` still raised AND the watch has the entry; two in a row stall; a different hash does not), plus the replay fixture.
Touches: `rework_watch.py` (+ ~25 lines), `e1_golden_path.py` (one block in `generate_stage`), `job_supervisor.py` (`supply_change`, CRLF file). Backups with `.bak-2026-10-04-*`.

## 2. Item A: normalise volatile text before hashing (small, shared)

Why: StarNet's guard strips ids, durations and call refs before hashing, so "the same result" is not hidden behind a timestamp. GUPPI's `outcome_hash` hashes raw text; one timestamp in a tool output makes every repeat look new. `rework_watch._clean` already does this for failure text (file names, line numbers, hex addresses) but has its own small copy.

Design: `loop_guard.normalize_output(text)` replacing only **host-generated volatility**: ISO-8601 timestamps, durations (`1.2s`, `350ms`, `after 3 min`), UUIDs, `0x` addresses, hex strings of 12 or more digits, GUPPI ids (`SDJ-`, `M-`, `SBX-`, `HG-`, `CAND-`, `PRJ-`, `EVT-` plus their digits), `pid N`. Everything else, including ordinary numbers, stays, so different results stay different. Applied **before** the 2000-character cut in `outcome_hash`. `rework_watch._clean` reuses the same function and keeps its own file/line rules on top.
Contract change: `outcome_hash` docstring and tests (the current 36 tests do not contain these patterns and must still pass unchanged; the spec test "differ only after 2000 characters" stays). New tests: each pattern normalised, ordinary numbers and words not, the same output with two different timestamps/ids gives one hash, and the old tests.
Note: this changes the module that GUPPI's own self-development attempt targeted (`loop_guard`); the assistant wrote it (documented), so no integrity statement is affected.
Value today: low (no tool-output consumer yet); cost: ~30 lines plus tests. Do it only together with C, because it removes the duplicated normaliser.

## 3. Item D: record real model replies (prerequisite, medium)

Why: StarNet gets byte-identical runs from a replay provider with fixtures. GUPPI cannot replay a real run: the raw reply of a failed generation is not stored (for the Gemma runaway we know only `output_tokens: 20000`), and the review keeps 500 characters. This blocks three things: regression tests of stalls with real model behaviour, the review bench (docs/REVIEW_STRUCTURED_PROPOSAL_2026-10-04.md, part C) and Item E.

Design: an opt-in recorder around `Control.model_call` / `_model_inference` (env `GUPPI_RECORD_REPLIES=1` or a local switch): append one JSONL line per call to `runtime_data/model_recordings/<job_or_mission>.jsonl` with request digest, model, sampling, the full reply content (capped at, say, 200 KB), usage, truncated flag, timing. Off by default; the file is data, not evidence (no gate). Then a `ReplayAdapter` (same interface as `OpenAICompatibleLocalAdapter.chat`) that answers a request from a recording by digest, for tests and for dry-running the harness stages without the GPU.
Touches: `modules/control.py` (small hook), a new `models/replay.py`; tests with a hand-made recording. Needs a decision about disk use and privacy (replies contain code and objectives; local only).

## 4. Item E: runaway guard on the model stream (larger, needs the Captain's decision)

Why: this is the failure that really cost time: Gemma generated exactly 20000 tokens in 395 s three times; gpt-oss looped 20000 tokens at temperature 0.1. A repetition check on the stream could abort such a generation after a few thousand tokens and hand `gen:runaway` to the watch, instead of waiting for the token limit.
Obstacle: `OpenAICompatibleLocalAdapter.chat` is non-streaming (`"stream": False`, one `urlopen`). A guard needs SSE streaming, an incremental repetition detector (for instance: the last N characters recur K times without new content), and a clean abort (closing the connection; llama.cpp stops on disconnect, to be verified). Legitimate output also repeats (tests with similar lines), so thresholds must be tuned on real recordings, which is why D comes first.
Scope risk: the adapter is shared by every model call (chat, review, benchmarks). Plan it as an opt-in flag per call (`stream_guard`), used first by `code_generation.generate`, default off.
Not planned for implementation until D has produced real runaway recordings.

## 5. Order, effort, checks

1. **C + A together**: about one session. Checks: new tests plus the affected modules (`test_rework_watch`, `test_job_supervisor`, `test_verification_gate`, `test_job_worker`), the replay fixture on saved states; no GPU needed.
2. **D**: about one session; check with a hand-made recording and one real recorded `generate` call (needs the GPU lease; one real run, no gate).
3. **E**: only after D and a Captain decision; a spike on the adapter first, measured on recordings.
4. **B (warn level)**: not scheduled.

Process rules as before: run only the tests of changed or new code, keep backups with `.bak-2026-10-04-<name>`, keep CRLF in CRLF files, document each step in this folder and in the memory note, no change to the review gate.

## 6. Decisions for the Captain

(a) Build C + A as described, including "an identical candidate is refused without a test run"? (b) Is D (recording real replies to disk, off by default) acceptable? (c) Leave E until D has data, or drop it? (d) Confirm that B stays deferred.

## Built (2026-10-04, Captain: "can we not work through all points", so A to E and B were all done)

Order built: A + B (loop_guard), C (candidate unchanged), D (recording and replay), E (stream guard). Backups carry `.bak-2026-10-04-<step>`; CRLF files kept CRLF.

**A, normalised outcomes** (`loop_guard.py`): `normalize_output` replaces ISO timestamps, UUIDs, GUPPI ids (`SDJ-`/`SBX-`/`HG-`/`CAND-`/`PRJ-`/`KN-`/`M-` + 8 hex, `EVT-` + digits), `0x` addresses, hex or digit strings of 12+ with at least 6 distinct characters, durations (`1.2s`, `350ms`, `3 min`) and `pid N`; whitespace is collapsed; ordinary numbers and words stay. `outcome_hash` normalises before the 2000-character cut. A guard can opt out (`normalize=False`): the rework watch does, because its outcomes are already canonical failure signatures (found on the first run: a signature's own hex part was being normalised away and every outcome looked equal). `rework_watch._clean` now shares the normaliser.
**B, warn level**: `LoopGuard.level(tool, args, warn_margin=1)` returns `{"level": "ok" | "warn" | "stuck", ...check fields}`; warn means "stuck if the thresholds were one lower". It is not used by the rework watch (see section 0) and waits for a consumer such as a tool loop. Tests: 78 in `test_loop_guard` + `test_rework_watch` after A and B.
**C, candidate unchanged**: `rework_watch.candidate_key` / `same_as_earlier`; harness `refuse_repeated_candidate` (no bind, no VM run, no gate; recorded as `gen:candidate_unchanged`; the generation is discarded) and `discard_generation` (any unusable generation is now archived and its mission fields cleared, so `generate` is no longer answered `exists` after a failure, which used to need a hand edit of the state); `job_supervisor.supply_change` records the old candidate in the watch before it raises `change_not_different` (raised after the block, because a raise inside drops the record). Checked on the saved states: finds exactly generations 3 and 6 of `uix_window`, nothing in `self_diagnosis` or `loop_guard`. With the supervisor and verification tests: 233 OK.
**D, recording and replay** (`models/recording.py`, hooks in `models/router.py` and `runtime.py`): with the environment variable `GUPPI_RECORD_REPLIES=1` every model call is appended to `runtime_data/model_recordings/<mission or job>.jsonl` (request digest, capped request, the full reply up to 200 KB with finish reason, usage, runaway verdict, seconds, or the error). Off by default, never breaks an inference. `ReplayAdapter` answers from recordings by digest (`replay_miss` for an unknown request, recorded errors raised again, recordings of one request in order, the last one reused). 18 tests; the six modules that touch the router or runtime: 271 OK.
**E, runaway guard** (`runaway_guard.py`, `models/openai_local.py`, `code_generation.py`, `modules/control.py`, harness): opt-in `stream_guard` per call (True or a settings dict). The adapter streams the answer (SSE) and one `RunawayGuard` per channel (answer, thinking) watches it: a repeating tail of at least 3000 characters (8 repeats for blocks up to 200 characters, 4 up to 1000, 3 beyond; whitespace-only counts) or 20 `<unusedNNN>` tokens in 6000 characters. On a runaway the connection is closed (the server stops generating) and the call returns `finish_reason: "runaway"`, `truncated: true`, the text so far and the verdict. `code_generation.unusable_answer` names it `model_answer_runaway`; the harness retries it like any bad answer, counts it in the rework watch and switches the guard ON by default for `generate` (scenario `generation.stream_guard: false` turns it off). 27 tests including a local streaming server that sees the client leave; with the neighbouring modules 392 OK.

Not covered by unit tests: the real llama-server's behaviour on a closed connection and a false-positive rate on real outputs. The real-model check (queued behind another chat's GPU lease, run through `testlab_cli hold`) covers both; its result is added below.

### Real-model check of D and E (2026-10-04, gpt-oss-20b on the real llama-server, under the testlab lease, testlab #34)

First attempt failed to start (relative interpreter path in the `hold` command, nothing ran); second attempt ran after another chat's lease was released. Five calls through `ModelRouter.chat` with `GUPPI_RECORD_REPLIES=1`:

| Call | Result |
|---|---|
| hello, guard on | 1.3 s, `stop`, answer "Hello!", streamed, usage parsed (13 in / 47 out) |
| 60 unit tests, guard on, 4000 tokens | `length`, no answer: gpt-oss spent all 4000 tokens thinking (11361 characters of reasoning). The guard did not trip on that thinking. **This call did not test a long legitimate answer** (the model never got to it) |
| induced runaway ("repeat this sentence forever"), guard on | **runaway after 14.8 s**: repetition, period 29, span 3130 characters, channel answer; 3130 characters of answer kept |
| same request, guard off | ran to the limit: 56.9 s, 4000 tokens, 13631 characters of the sentence |
| `/slots` right after the abort and 1.5 s later | `is_processing: false` both times: **closing the connection really stops the server's generation** |

So the guard cut the induced runaway to about a quarter of the time (14.8 s against 56.9 s) and the server was free at once. The aborted call reports no token usage (the stream ends before the usage chunk), the characters seen are in the verdict.

Recording (D): 4 lines in `runtime_data/model_recordings/REALCHECK-E.jsonl` with the full replies, finish reasons and the verdict. Replaying the recorded runaway request through `ReplayAdapter` returned `runaway / repetition / 3130 characters`. Finding: the guarded and the unguarded request had the same digest and replayed in recording order; fixed by making `stream_guard` part of the digest (test added, 46 tests in the two modules OK).

False-alarm check that replaces the missing long-answer call: all 214 `.py` and `.md` files of the runtime, tests, examples, benchmarks and docs (2.2 million characters) streamed through the guard in 200-character chunks: **0 false alarms**, 1.6 s in total.

Still not measured: the guard on the Gemma runaway that started this (no recording exists of it, and Gemma was not run), and a long legitimate gpt-oss answer in its own right (needs a prompt that gets past the thinking; gpt-oss has no "none" effort). Both are cheap to add now that recordings exist.
