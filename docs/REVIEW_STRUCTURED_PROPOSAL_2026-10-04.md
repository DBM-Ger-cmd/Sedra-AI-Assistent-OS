# Proposal: a structured independent review (2026-10-04)

Status: **proposal only, nothing changed.** The review step is a gate; changing it is the Captain's decision.
Origin: three Gemma FAILs on three different loop_guard candidates (docs/LOOP_GUARD_E1_ATTEMPT_2026-10-04.md, docs/LOOP_GUARD_REWORK_PLAN_2026-10-04.md), none with a reproducible counter-example, while the VM tests and a differential test (81072 checks, 0 differences) agreed with the code.

## 1. What the review does today

`review_stage` (benchmarks/e1_golden_path.py): the verifier (a different model family than the coder, Gemma) gets the objective and the full changed files and must answer "exactly one line: PASS or FAIL, then a short reason" (temperature 0, `reasoning_effort: none`, 1500 tokens). The reply (first 500 characters) becomes `independent_review` evidence (trust level `model_assessment`) next to the deterministic VM test; a FAIL sends the job to REWORK, which cannot be reviewed again.

Weaknesses seen:
1. A one-line verdict on a 150-line file against 50 lines of prose rules. No reasoning, no evidence required.
2. A FAIL needs no proof, yet it is final: one unsupported sentence ends the job (REWORK -> REWORK is refused, rework needs a failed VM test).
3. Nobody measured how reliable the verifier is for this kind of task. Three of three FAILs on code that was right (as far as tests and the differential test can tell) is a false-FAIL rate of at least 3/3 on this scenario; the opposite error (a PASS on bad code) is unmeasured, and that is the dangerous one.
4. Only 500 characters of the reply are kept; the prompt is not recorded.

## 2. Principle

The gate must not get weaker. Concretely: a PASS needs at least as much as today; a FAIL becomes expensive to give (it needs evidence), and a FAIL without evidence no longer kills the job but goes to the Captain. Nothing is activated without a PASS and the Captain's gate.

## 3. The proposal (three parts, each separable)

### A. Adversarial test instead of prose verdict (the main change)

The verifier gets the spec and the candidate and must return JSON:
```
{"verdict": "PASS" | "FAIL",
 "checks": [{"rule": "<short quote of one rule of the spec>", "ok": true|false, "lines": "<the lines of the candidate that implement it>"}, ...],
 "counterexample": null | {"test": "<a stdlib unittest TestCase method body that must pass if the rule holds>", "rule": "<which rule>"}}
```
Rules for the harness (deterministic, no model):
- PASS: every spec rule appears in `checks` with `ok: true` and a non-empty `lines`. Missing rules, empty citations or a malformed JSON = `review_malformed` (no verdict, ask again once, then Captain).
- FAIL: must carry a `counterexample`. The harness runs the reviewer's test against the candidate in GUPPI's VM (the usual Captain gate `sandbox_execute`, one more run):
  - the test **fails** -> reproducible counter-example: the job goes to REWORK with the failing test output as feedback, exactly like a failed project test (the existing rework path, the rework watch and the hints apply unchanged);
  - the test **passes** -> the claim is refuted: the FAIL does not count; the review is recorded as `review_refuted` (and the reviewer model's reply is kept as evidence);
  - the test **errors** (syntax, import, wrong API) -> `review_malformed`.
- A FAIL without a counter-example = `review_unsubstantiated`: job state stays reviewable (no REWORK), activation stays BLOCKED, the Captain sees the claim and decides: ask again (different prompt or model), accept the candidate on his own authority through the existing gate, or reject.
Cost: one extra VM run per FAIL; the reviewer's test is short and readable, so the Captain can judge a disputed test in seconds, which he cannot do with a vague sentence.

Caveat: a reviewer test can itself be wrong (asserting something the spec does not say). Then it fails against a correct candidate and the job goes to REWORK for nothing. Mitigation: the harness also shows the test to the Captain before the rework starts when the same test fails on a candidate that passed all project tests ("disputed counter-example"); this is a Captain click, not a loop.

### B. One rule per call

Split the spec into its rules (the docstring paragraphs: signature, outcome hash, generic_repeat, ping_pong, window, guarded tools) and ask one narrow question per call with only that rule and the candidate. Smaller prose per answer for a 12B model, no thinking needed, and the `checks` list is complete by construction. The scenario would carry the list (`review_rules` in scenario.json: id, the rule text, the tests that cover it); the harness builds the calls. A rule covered by tests that pass is shown to the reviewer as covered, which removes the "tests prove it" half of the work.

### C. Record everything

Keep the full reply, the prompt digest and the model/engine identity of every review in the evidence (today 500 characters). Needed for measuring (below) and for the Captain's audit.

## 4. Measure first (before changing the gate)

The project has done this before ("rework bench: qwen3-coder 10/10, gpt-oss 7/10, gemma 2/10"). Do the same for the review:
- **Known-good set:** the assistant's reference `loop_guard.py`, the three gpt-oss/Gemma-checked candidates that passed the tests (CAND-73409E514770, M-2A73991C's candidate, CAND-2FE3E1B54730; the first two against the then-current spec versions).
- **Known-bad set:** the job-2 candidate that fails the colon test (real flaw, small), and about 12 mutants generated from the reference by a script (off-by-one threshold, ping-pong without the no-progress check, window not capped, `is_error` ignored in the outcome, key order changes the signature, generic_repeat counting only consecutive entries, `other` taken from the wrong entry, ...). Each mutant must fail at least one test, otherwise it is an equivalent mutant and is dropped.
- **Formats compared on the same set:** today's one-line verdict; A (JSON with counter-example); A + B (per rule). Gemma and gpt-oss as verifier (independence rule: the coder of the candidate may not review it, so for a reference with no coder the pairing is free).
- **Numbers to report:** false-FAIL rate on the good set, miss rate on the bad set (PASS on a mutant), refuted-claim rate (format A), tokens and seconds per review. A format is only worth adopting if the miss rate is not worse than today's and the false-FAIL rate drops.
- Runs are testlab rounds (GPU lease, planned in the queue); the VM executions of format A need a gate each, so the bench runs the counter-example tests on the host only (a bench, not a verdict).

## 5. Where it would go

1. Bench (no gate change): new `benchmarks/review_bench.py` plus the mutant generator; results in the testlab DB and a short report in docs. ~1 session.
2. Harness: `review_stage` gets A (and B if the bench says so) behind a switch, default off; new outcomes `review_unsubstantiated`, `review_refuted`, `review_malformed`; the rework watch records `review` signatures as today and the refuted/unsubstantiated outcomes as their own kinds. Tests for the pure parts (JSON validation, rule coverage, outcome mapping) without a model.
3. Runtime: the same outcomes in `verification_gate` / `job_supervisor.reject_verification` (a rejected verification needs evidence of kind "reproduced failure", an unsubstantiated one parks the job for the Captain).
4. UIX card: a review that needs the Captain (unsubstantiated or disputed counter-example) shown next to the stalled-rework card, with the claim, the reviewer's test and three buttons.

## 6. Risks

- The reviewer writes bad tests (see caveat) or ignores the format; the bench measures both before anything is switched on.
- Format A is more work for a small model; per-rule calls (B) mitigate it at the price of more calls.
- A weaker reviewer that now has to produce evidence may say PASS more often. That is why the bench measures the miss rate first and why PASS keeps the full checklist requirement.

## 7. Decisions for the Captain

(a) Do the measurement first (step 1) as proposed? (b) Which verifier models to include (Gemma only, or gpt-oss too for the cross-family check)? (c) After the numbers: switch format A on by default, keep it opt-in, or drop it.
