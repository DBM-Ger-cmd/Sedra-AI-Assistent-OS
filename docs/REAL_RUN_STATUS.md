# Real run on the Captain's PC – status (2026-10-01)

Machine: RTX 4070 Ti 12 GB, 31 GB RAM, Windows 11, LM Studio on 127.0.0.1:1234. Game closed (confirmed by the Captain; GPU
baseline 0.89 GiB). Both models were loaded for the tests and unloaded afterwards (GPU back to 0.89 GiB).

## What was done

| Stage | What | Result |
|---|---|---|
| A | read-only: hardware collector, scheduler headroom, model pass, routing dry run | works; see findings 4, 5 |
| B | real model calls through `ModelRouter` + `HardwareManager` | works; usage, audit chain and job counter correct |
| C | real `JobSupervisor`: job → claim → resolution → reservation → model call → metric | works for the coder path (below) |
| – | thermal profile `custom-gpu-careful` saved and activated (68 / 74 / 80 °C, hysteresis 5) | sensor recognised, state NORMAL at 41 °C |

Stage C ran on a throw-away project copy; the four feature switches were enabled **in memory for that process only**. The
Captain's real configs and `runtime_data` were not changed; routing, scheduler, supervisor and context manager are still
`enabled: false`.

Stage C observed: resolution `coder.local_primary` → `lm-studio`; reservation of 4.0 GiB RAM / 8.26 GiB VRAM on the GPU;
real call answered `pong`; provider usage 17 in / 121 out (117 reasoning) recorded as a metric with source `provider`;
unloaded afterwards.

## Measurements (context 8192, `--gpu max`)

| Model | VRAM delta | old estimate | answer | tokens in/out (reasoning) |
|---|---|---|---|---|
| qwen3.5-9b-mtp | 8.26 GiB | 6.0 | pong | 17 / 159 (155) |
| google/gemma-4-12b-qat | 7.74 GiB | 6.83 | pong | 23 / 57 (51) |

qwen with LM Studio's default context: 9.82 GiB. The two models do not fit in VRAM together; they run one after another.

## Findings

1. **VRAM was underestimated** (weights × 1.05 ignores KV cache, compute buffers, mmproj). Overlay now carries
   `measured_vram_gb` (can only raise an estimate, never lower it).
2. **Reasoning models can return an empty answer without any error** when `max_tokens` is spent on thinking. The adapter now
   reports `finish_reason`, `truncated`, `empty_answer`, `reasoning_chars`, `reasoning_tokens`. Callers must give reasoning
   models a generous `max_tokens` (600 was enough here, 60 was not) and check `empty_answer`.
3. **Token estimate was too low** for the second model (21 vs 23). Overhead raised to 12 per message + 8 per request. This
   rests on two data points; per-model calibration should replace it.
4. **The model pass uses total VRAM, not free VRAM.** Not changed yet.
5. **Resolved window was 32768 while 8192 was actually loaded.** GUPPI does not tell LM Studio which context to load; the
   recipe's `maximum` was therefore too optimistic. Overlay `maximum` is now 8192 (the value the VRAM was measured at).
   GUPPI did not set the loaded context itself at that point. **Update:** Phase 8a (`model_loader`, see PHASE8_STATUS.md) now does,
   behind its own flag (off by default); the VRAM of an already loaded model is no longer counted twice.
6. **Thermal protection is admission only** (`admission_only; no_fan_writes; no_inflight_cancellation`): WARM → one job at a
   time, HOT/CRITICAL → no new jobs. Running jobs are never stopped.
7. The model-to-file mapping (LM Studio name → GGUF → SHA-256) was inferred from file sizes and then confirmed by
   `lms ps` paths.

## Not done / limits

- The verifier path (gemma) was **not** run through the supervisor. A second job while the first holds its room could not be
  tested because `workers: 1` (the claim fails with `worker_busy` first); refusal for lack of room is covered only by unit tests.
- No gemma resolution with a real reservation, no retry/fallback with a real provider failure, no stall/reaper on real load.
- KV cache rates are still unknown (`estimate_complete: false`).
- `measured_vram_gb` has no dedicated unit test yet; the adapter fields and estimator constants do.
- Kev was not installed or run.
- Results from one run and one prompt are an existence proof, not an acceptance test.

## Next decisions (Captain)

- Enable routing/scheduler/supervisor/context manager in the real config, or keep them off until Phase 8.
- Whether GUPPI should pass the context length to LM Studio itself (finding 5).
- Remaining open items from earlier phases (stage mapping, Kev environment and lineage, tool chain through the gate, reaper
  thread, Phase 8 worker loop).
