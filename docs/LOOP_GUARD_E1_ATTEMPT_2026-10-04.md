# loop_guard E1 attempt, 2026-10-04 (stopped by the Captain)

Status: **stopped, no capability integrated.** The Captain ended the attempt on 2026-10-04 ("wir haben festgestellt dass es nicht funktioniert hier, wir machen eine Pause und dokumentieren alles").
Three E1 jobs ran; two produced a candidate that passed the VM test, none passed the independent review, one never produced a candidate.

## Origin

Review of the open-source agent OS Cognithor (`E:\cognithor-main\cognithor-main`, Apache 2.0, ~860 Python files). Point 1 of the lessons for GUPPI:
a **tool-loop detector** (`core/loop_detector.py`: SHA-256 over call and result, sliding window of 24, `generic_repeat` at the 4th identical call,
`ping_pong` at the 6th alternating call). GUPPI had no equivalent; evidence: gpt-oss at temperature 0.1 looped through 20000 tokens, and the
uix_window rework ran 12 generations with the same cause (2026-10-03). Plan: let GUPPI write it itself as an E1 capability
(`capabilities/loop_guard.py`), spec and tests written first by the assistant.

The other lessons of the review (not started) are listed at the end.

## What exists now

Scenario `runtime/examples/self_dev/loop_guard/` (kept):
- `scenario.json`: capability `tool_loop_guard`; generation budget now context 32768 / max_tokens 20000 (was 16384 / 12000).
- `loop_guard.py`: stub with constants and a precise docstring spec (`signature`, `outcome_hash`, `LoopGuard` with `record`, `check`, `reset`, `recorded_count`).
- `tests/test_loop_guard.py`: 36 tests.
- Verified before every run: the assistant's reference implementation (kept only in the scratchpad, not in the repo) passes 36/36; the stub passes 1/36 (the constant test).

Spec changes during the attempt (all because a reviewer or the assistant found something):
1. `history_size` was both the constructor maximum and the property "how many are remembered". Property renamed to `recorded_count`; docstring says the maximum is not exposed.
2. Added: tool names may contain ":" (`mcp:read`); the tool name must be stored per entry and never recovered by splitting a signature. Two tests (both orders plus an unguarded tool with the same prefix). The job-2 candidate fails this test (it parses `s.split(":", 1)[0]`).

## The three jobs

| Job | Project | Coder | Candidate | VM test | Gemma review | Job state |
|---|---|---|---|---|---|---|
| SDJ-0129D3B24C54 | PRJ-343410ce0f6a | gpt-oss-20b | M-E542AE1B / CAND-73409E514770 | PASS (SBX-aad1a342...) | FAIL: "history_size property wrong" (a confusion of constructor and property, spec change 1) | REWORK |
| SDJ-55E88D2A054C | PRJ-12d6da1f4a64 | gpt-oss-20b | M-2A73991C (1st try M-D7E4319F: answer truncated) | PASS (SBX-79e7426d...) | FAIL, vague: "ping_pong logic slightly flawed" | REWORK |
| SDJ-4664296CEFFC | PRJ-0bda68b62095 | gemma-4-12b-qat | none | not run | not run | PLANNING |

Notes:
- Both candidates were read line by line by the assistant against the spec. Job 1 followed the spec. Job 2 followed the spec except the colon issue (real but small); Gemma named neither concrete point correctly (the ping_pong message does contain the count).
- Job 3: three runs of Gemma ended with `model_answer_truncated` (M-E34CB788 at 12000 tokens, M-2E7E88DC at 12000, M-C61355F7 at 20000). `context_metrics/M-C61355F7.jsonl`: input 7081, output exactly 20000 tokens in about 395 s. A correct answer is about 1500 tokens, so Gemma ran away (repetition or garbage, compare `guppi-gemma-garbage-output`: `<unused49>`). A larger budget does not help. The raw answer is not stored, so the exact form is unknown.
- A job in REWORK cannot be reviewed again (`invalid_development_transition:REWORK->REWORK`), and the rework stage needs a failed VM test (`no_failed_test`), so jobs 1 and 2 cannot continue. They are left as they are; close or discard them when convenient.
- Old states were renamed, not deleted: `runtime_data/e1_golden_path/loop_guard/state.rejected-review-historysize.json`, `state.rejected-review-gemma-vague.json`; the current `state.json` is job 3.

## Findings

1. **Coder choice was gpt-oss, not qwen3-coder, although profile `standard` prefers qwen3-coder.** Cause: the router rejects `coder.local_primary` with `ram_measured` (`resource_scheduler.py:147`). Measured 2026-10-04: 31.1 GB total, 18.4 to 19.0 GB available, reserve 3.0 GB, recipe needs at least 18 GB, so about 2 to 2.6 GB were missing. Closing small programs (Steam, LM Studio, WhatsApp, Phone Experience: about 2 GB together) did not suffice. Windows has page files (C: 25 GB, G: 80 GB), but the scheduler measures physical available RAM, so they do not count.
2. **`require_coder_model` in `e1_golden_path.py` was read but never used.** Fixed: `generate_stage` now stops with `coder_not_available` before loading a model when the routed coder differs (backup `e1_golden_path.py.bak-2026-10-04-require-coder`, CRLF kept). Verified: pin on qwen3-coder gave `coder_not_available` without loading anything.
3. **RAM reserve is now fixed at 3 GB:** `runtime/config/resource_scheduler.yaml` `ram_reserve_gb: 3.0` (before: `null`, taken from the active hardware profile, which happened to be 3). Backup `resource_scheduler.yaml.bak-2026-10-04-ram-reserve`. This did not change the qwen3-coder decision.
4. **The one-line Gemma review is a poor judge for long prose specs.** The verifier runs at temperature 0, `reasoning_effort: none`, answer "PASS or FAIL, then a short reason". Two FAILs, one wrong, one vague. Not changed (loosening the reviewer until it passes would weaken the gate).
5. **Gemma as coder ran away on this task** (job 3), see above.
6. **Routing profile `stabil` was active during the attempt and has been switched back to `standard` (2026-10-04, Captain).** Resolution after the switch: coder and rework `coder.llama_gptoss` (qwen3-coder still rejected for RAM, see 1), verifier `verifier.llama_gemma`. Open risk of `stabil`, never exercised: gpt-oss as verifier would get `reasoning_effort: none`, which gpt-oss does not know (low/medium/high).
7. **Operating notes for the Captain's gates:** the CLI approve needs `--architecture`: `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m guppi_runtime --root ..\workspace\GUPPI_OS --architecture ..\architecture\GUPPI_Architecture_v1.20_SELF_DEVELOPMENT approve <mission> --gate-id <gate>`. The mission and gate id must be those of the current job (a new job has new ones; one approval went to the old mission by mistake). In PowerShell `PYTHONPATH=src` as a prefix does not work.

## Open items / ideas

- Testlab #31 (this run) set to cancelled. Testlab #32 `moe_mmap` stays planned: qwen3-coder with mmap on NVMe instead of the RAM copy (speed, free RAM, stability; the recipe `min_ram_gb` would have to be lowered for the test). Note: `mmap: false` was set on purpose on 2026-10-03 (with mmap the server held 22.7 GB and left 0.6 GB free).
- Running jobs of other chats in the lab: #18 and #21 (`chat-moe-modelltest`) still show `running` although the GPU is free; probably stale, not touched.
- Gemma runaway: related to the planned `garbage_hunt` rounds (#3, #4 of `chat-guppi-dev`).
- Decision for later (Captain): run again with gpt-oss writing (profile `standard` or `gptoss`) against the sharpened spec; accept that Gemma's review may fail vaguely again; or give the review a more structured form (a decision for the Captain, not for the assistant).

## Cognithor lessons (review of 2026-10-04)

Already in GUPPI: deterministic gatekeeper (guard.py), failure classes with retry rules (stricter), hash-chained audit, working set with offload/recall, hash-bound integration with rollback, coding lessons in the knowledge base.
Candidates to take over (priority order as proposed): 1 loop detector (this attempt), 2 three-tier context guard (truncate head/tail, replace old tool results, overflow flag; relevant for gpt-oss q8 KV above 40k), 3 hashline guard for safe edits of existing files (relevant for E2, which stays closed), 4 causal failure analysis over run traces (GEPA), 5 deterministic response validator before the Gemma review, 6 fail-open observer, 7 idle learning with a resource check, 8 manifest hash on resume, 9 separate model choice and context profile, 10 LLM retry with stream-to-sync fallback.
Not worth taking over: the sheer scope (14 stale modules in its own audit), ten ledgers, keyword heuristics for failure categories.

## Follow-up: implemented by the assistant (2026-10-04, Captain's request)

After the stop the Captain asked the assistant to implement the loop guard itself. Result: `runtime/src/guppi_runtime/loop_guard.py` (spec docstrings kept, reference logic, tool name stored per entry) and `runtime/tests/test_loop_guard.py` (the 36 scenario tests with the import `guppi_runtime.loop_guard`); run with `cd runtime/tests; PYTHONPATH=../src python -m unittest test_loop_guard`: 36 OK.
It is deliberately **not** in `capabilities/` (that package states that every module there was written by the coder model, VM-tested, independently reviewed and gated) and did not go through the self-integration path, so it is **not** a GUPPI self-development result. Nothing calls it yet; wiring it into the job supervisor / rework loop is a separate decision.
