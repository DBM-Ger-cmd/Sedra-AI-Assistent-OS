"""First real E1 self-development run, step by step (P2-009 / P3-002). A guided run, not a test.

    .venv\\Scripts\\python.exe benchmarks/e1_golden_path.py <project_dir> prepare|generate|test|rework|diagnose|review|rebind|status|watch|watch_reset [--scenario <folder>]

A scenario folder holds the project files (code with the gap + its tests) and scenario.json {capability, objective, files, evidence}.
Without --scenario the demo (examples/demo-project) is used. State lives in <project>/runtime_data/e1_golden_path/[<scenario>/]state.json,
so each stage can be repeated and the Captain's gates fit in between.

  prepare   copies the demo project (examples/demo-project) into a managed GUPPI project and records the baseline: its test fails
            ("Hello David" vs "Hello, David!"), which is the capability gap. A self-development job (E1) is admitted for it.
  generate  holds the GPU lease, loads the coder the role router picks (qwen3-coder-30b-a3b on this PC since 2026-10-03), asks it for the fix through
            code_generation.generate (tests may not be touched), unloads it, and lets the mission prepare the candidate
            (CANDIDATE_REVIEW). The job gets the candidate bound to it.
  test      runs the bound test command in GUPPI's own VM (candidate_tests). The first call raises a Captain gate
            (sandbox_execute); approve it with `guppi approve <mission> --gate-id <id>` and call `test` again.
  review    the verifier model (gemma, a different family) reviews the change under the GPU lease; the deterministic VM test and
            the review become evidence; the job's verification is attached. Activation stays with the Captain.
  watch     shows the rework watch (rework_watch.py): the remembered failures and its verdict for the next generation. `generate` stops with
            `rework_stalled` when the last attempts ended in the same failure (3 times) or in two alternating failures (4); a new
            `captain_hint` in the state lets it continue, `watch_reset` forgets the list. It only advises.
Nothing here writes to the original demo files or activates anything.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
ARCH = RUNTIME.parent / "architecture" / "GUPPI_Architecture_v1.20_SELF_DEVELOPMENT"
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.runtime import GuppiRuntime          # noqa: E402
from guppi_runtime.projects import ProjectRegistry      # noqa: E402
from guppi_runtime.core.util import atomic_write_json, load_json  # noqa: E402
from guppi_runtime.jobs.rework_watch import ReworkWatch, failure_signature, same_as_earlier  # noqa: E402

DEMO = {"name": "demo", "capability": "demo_greeting_format", "target_type": "skill", "source": RUNTIME / "examples" / "demo-project",
        "files": ["app.py", "tests/test_app.py"], "evidence": [],
        "objective": ("Fix greet() in app.py so that the existing test passes: greet('David') must return 'Hello, David!'. "
                      "Change only app.py. Do not touch the tests.")}
SC = dict(DEMO)          # the active scenario; main() replaces it from --scenario <folder with scenario.json>
CODER_MODEL = None   # since 2026-10-03 the active routing profile picks the coder; set a model here to pin new runs to it


def load_scenario(folder):
    folder = Path(folder).resolve()
    raw = json.loads((folder / "scenario.json").read_text(encoding="utf-8"))
    return {"name": folder.name, "capability": raw["capability"], "target_type": raw.get("target_type", "skill"), "source": folder,
            "files": list(raw["files"]), "evidence": list(raw.get("evidence", [])), "objective": raw["objective"],
            "generation": dict(raw.get("generation", {}))}      # optional {"context_min_tokens", "max_tokens"} for bigger tasks


def state_path(project):
    base = project / "runtime_data" / "e1_golden_path"
    return base / "state.json" if SC["name"] == "demo" else base / SC["name"] / "state.json"


def save(project, state):
    atomic_write_json(state_path(project), state)


def baseline_tests(folder):
    """Red baseline on the host is only a read of the fixture's own verdict; it runs the demo's unittest in a throw-away copy."""
    # Same command as the bound VM test (code_generation: python3 -m unittest discover -s tests -v); `-m` puts the cwd on sys.path.
    env = {k: v for k, v in __import__("os").environ.items() if k.upper() in {"SYSTEMROOT", "PATH", "TEMP", "TMP"}}
    out = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=folder,
                         capture_output=True, text=True, timeout=60, env=env)
    text = out.stdout + out.stderr
    return {"returncode": out.returncode, "assertion_failure": "AssertionError" in text,
            "tail": text.strip().splitlines()[-4:]}


def prepare(rt, project, state):
    if state.get("project_id"):
        return {"status": "exists", **state}
    reg = ProjectRegistry(rt)
    rec = reg.create("E1 " + SC["name"])
    target = rt.filesystem_tool.root / rec["workspace_path"]
    for src in SC["source"].rglob("*"):
        if src.is_file() and src.name not in {"README.md", "scenario.json"} and "__pycache__" not in src.parts:
            dst = target / src.relative_to(SC["source"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    scratch = state_path(project).parent / "baseline"
    if scratch.exists(): shutil.rmtree(scratch)
    shutil.copytree(target, scratch)
    base = baseline_tests(scratch)
    if base["returncode"] == 0:
        return {"status": "no_gap", "detail": "the baseline tests already pass; nothing to develop", "baseline": base}
    evidence = SC["evidence"] + [{"source": "baseline_unittest", "returncode": base["returncode"], "tail": base["tail"]}]
    sd = rt.self_development.start(SC["capability"], evidence=evidence, target_type=SC["target_type"], objective=SC["objective"],
                                   acceptance_criteria=[{"type": "deterministic_tests", "command": "python3 -m unittest discover -s tests -v", "expect": "pass"}])
    state.update(project_id=rec["project_id"], workspace_path=rec["workspace_path"], baseline=base, scenario=SC["name"],
                 require_coder_model=CODER_MODEL,
                 job_id=(sd.get("job") or {}).get("job_id"), admission=sd["status"])
    save(project, state)
    return state


def resolve(rt, role, **kw):
    res = rt.control.resolve_role(role, **kw)
    return res


def with_model(rt, resolution, fn):
    loaded = rt.model_loader.ensure(resolution)
    try:
        return fn(loaded)
    finally:
        rt.model_loader.unload(resolution)


REPRO_HARNESS_SOURCE = RUNTIME / "examples" / "self_dev" / "_shared" / "_guppi_repro.py"


def with_repro_harness(rt, proj, files):
    """Put GUPPI's reproduction harness into the project's tests/ (read-only for the coder) and select it, so every VM test also
    reports which input failed where (Captain 2026-10-03, "Reproduktionsschritt bauen"). The project copy is refreshed if it differs."""
    target = rt.filesystem_tool.root / proj["workspace_path"] / "tests" / "_guppi_repro.py"
    source = REPRO_HARNESS_SOURCE.read_bytes()
    if not target.is_file() or target.read_bytes() != source:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source)
    return list(files) + (["tests/_guppi_repro.py"] if "tests/_guppi_repro.py" not in files else [])


def discard_generation(state, reason):
    """An unusable generation is archived and its mission fields cleared, so `generate` can run again (before, the state kept the mission and
    `generate` answered `exists` until someone edited the file by hand)."""
    old = {k: state.pop(k) for k in ("mission_id", "coder", "generation", "candidate", "mission_phase", "candidate_id") if k in state}
    old["generation"] = "refused"
    old["reason"] = reason
    state.setdefault("discarded_generations", []).append(old)


def refuse_repeated_candidate(state, watch):
    """Rework watch, plan 2026-10-04 item C: a candidate identical to an earlier one (after whitespace normalisation) is no progress. It is
    not bound and not tested (no VM run, no Captain gate); the repeat is recorded in the watch. Returns the `generate` answer, or None."""
    repeated = same_as_earlier(state.get("candidate"), state)
    if repeated is None:
        return None
    watch.record(failure_signature("gen", "candidate_unchanged"), state.get("captain_hint"))
    watch.save(state)
    discard_generation(state, f"candidate_unchanged (same as {repeated}); not tested")
    return {"status": "generation_failed", "out": {"status": "refused", "error": f"candidate_unchanged: same as {repeated}; no test was run"}}


def generate_stage(rt, project, state):
    from guppi_runtime.selfdev.code_generation import generate
    if state.get("mission_id"):
        return {"status": "exists", "mission_id": state["mission_id"]}
    watch = ReworkWatch.load(state)
    verdict = watch.check(state.get("captain_hint"))
    if verdict["stuck"]:
        # Nothing is loaded yet. The watch only advises: it records the stall and hands the decision to the Captain (plan 2026-10-04).
        rt.audit.append("REWORK_STALLED", component="e1-golden-path", payload={"job_id": state.get("job_id"), "detector": verdict["detector"],
                                                                              "count": verdict["count"], "failure": verdict["repeated_failure"]})
        return {"status": "rework_stalled", "detector": verdict["detector"], "count": verdict["count"], "failure": verdict["repeated_failure"],
                "detail": verdict["message"], "options": ["set captain_hint in state.json (a new hint lets the next generation run)",
                                                           "change coder, routing profile or the spec, then run `watch_reset`", "stop"]}
    proj = ProjectRegistry(rt).get(state["project_id"])
    budget = SC.get("generation", {})
    need = budget.get("context_min_tokens")
    # A Captain's per-run choice (2026-10-03: gpt-oss with deep thinking for one rework): `coder_exclude` removes models by their
    # independence key from this run's coder choice, `coder_reasoning_effort` sets its thinking. The default coder stays as it is.
    exclude = list(state.get("coder_exclude") or ())
    # Which model writes comes from the ACTIVE ROUTING PROFILE (local_config/routing_profiles.yaml, `guppi routing-profile use <name>`):
    # purpose "coder" for the first draft, "rework" for a repair after a failed VM test (recognised by the stored test feedback), each
    # with the profile's sampling. Standard profile 2026-10-03: qwen3-coder drafts, gpt-oss repairs (effort medium, temperature 1.0).
    # `require_coder_model` in the state pins a model for one run (the Captain's choice); a fallback is then refused, not silent.
    rework = bool(state.get("feedback"))
    coder = resolve(rt, "coder", requirements={"context_min_tokens": need} if need else None, exclude=exclude,
                    purpose="rework" if rework else "coder")
    sampling = coder.get("sampling") or {}
    effort = state.get("coder_reasoning_effort") or sampling.get("reasoning_effort") or "low"
    temperature = sampling.get("temperature")
    wanted = state.get("require_coder_model")
    if wanted and wanted not in (coder.get("model"), coder.get("capability_id")):
        # Nothing is loaded yet: a pinned model that the router did not choose (e.g. ram_measured: too little free RAM) stops the run.
        return {"status": "coder_not_available", "wanted": wanted, "routed": coder.get("capability_id"), "model": coder.get("model"),
                "detail": "the router chose another coder than require_coder_model; free memory or unset the pin"}
    objective = SC["objective"]          # the mission's task; rework material goes to the model only (code_generation feedback=)
    feedback = ""
    if state.get("feedback"):
        # Rework: the coder sees why its previous candidate failed in GUPPI's VM (the deterministic test output), not only the task.
        feedback += ("\n\nYour previous attempt failed these tests in the sandbox. Fix the cause; the tests are correct and stay "
                      "unchanged:\n" + state["feedback"])
        # ... and the code it wrote then. Without it the coder only saw the untouched stub again and rewrote it from scratch with the
        # same idiom (2026-10-03, qwen3-coder: `^...$` twice, so "url\n" kept passing). It is told where to look, not what to write.
        previous = state.get("previous_candidate") or []
        if previous:
            feedback += "\n\nYour previous version (it produced the failure above; find the line that causes it):\n" + "\n".join(
                f"--- {c['path']}\n{c['content'][:12000]}" for c in previous)
        if state.get("captain_hint"):
            # The Captain's own hint, after the coders failed the same cause several times (2026-10-03). It says where, not the code.
            feedback += "\n\nThe Captain's hint for this failure:\n" + state["captain_hint"]
        if (state.get("diagnosis") or {}).get("text") and state.get("use_diagnosis", True):
            # It can be wrong (2026-10-03: gemma said the regex "does not account for trailing whitespace"; qwen3-coder then ALLOWED it).
            feedback += ("\n\nAn independent reviewer's diagnosis of that failure (it may be wrong; check it against the test output "
                          "before you rely on it):\n" + state["diagnosis"]["text"])
    elif state.get("captain_hint"):
        # A stalled rework without a failed test (e.g. the model's answers were cut off) has no feedback; the hint still has to reach the model.
        feedback += "\n\nThe Captain's hint for this task:\n" + state["captain_hint"]
    target = {"provider": coder["provider_ref"], "model": coder["model"], "reasoning_effort": effort,
              "max_tokens": budget.get("max_tokens", 6000), "temperature": temperature,
              "stream_guard": budget.get("stream_guard", True) or None,       # runaway guard (plan 2026-10-04 item E); a scenario can switch it off
              "context_window": need}       # sizes how much selected source may go in (code_generation.source_limit); None = 64 KB as before
    # An unusable answer (empty, not JSON, wrong shape) gets one more try with the model already loaded; each try is its own mission.
    # Anything else generate refuses (out of scope, tests touched, source changed) is not retried.
    RETRYABLE = ("model_answer_empty", "model_answer_truncated", "model_answer_runaway", "model_output_not_json", "model_output_schema_invalid")

    files = with_repro_harness(rt, proj, SC["files"])

    def attempts(loaded):
        tries = []
        for _ in range(2):
            m = rt.brain.create_mission("Ändere Code als Kandidat: " + objective)
            m["context"]["refs"] = [{"project_id": proj["project_id"], "workspace_path": proj["workspace_path"]}]
            rt.missions.save(m)
            try:
                out = generate(rt, m, proj, files, target=dict(target, model=loaded["identifier"]), feedback=feedback.strip() or None)
            except ValueError as exc:      # generate refuses a bad answer; keep the reason in the state
                out = {"status": "refused", "error": str(exc)}
            tries.append((m, out))
            if out.get("status") == "completed" or not str(out.get("error", "")).startswith(RETRYABLE):
                break
        return tries

    tries = with_model(rt, coder, attempts)
    for m_failed, out_failed in tries[:-1]:
        state.setdefault("discarded_generations", []).append({"mission_id": m_failed["identity"]["mission_id"], "generation": "refused",
                                                              "reason": "unusable model answer: " + str(out_failed.get("error"))})
        watch.record(failure_signature("gen", out_failed.get("error")), state.get("captain_hint"))
    m, out = tries[-1]
    if out.get("status") != "completed":
        watch.record(failure_signature("gen", out.get("error")), state.get("captain_hint"))
    watch.save(state)
    state.update(mission_id=m["identity"]["mission_id"], coder={k: coder.get(k) for k in ("capability_id", "provider_ref", "model", "independence_key")},
                 generation=out.get("status"), candidate=out.get("candidate_request", {}).get("changes"))
    save(project, state)
    if out.get("status") != "completed":
        discard_generation(state, "unusable model answer: " + str(out.get("error")))
        save(project, state)
        return {"status": "generation_failed", "out": out}
    refused = refuse_repeated_candidate(state, watch)
    if refused:
        save(project, state)
        return refused
    m = rt.brain.run(state["mission_id"], max_steps=12)
    state["mission_phase"] = m["lifecycle"]["phase"]
    if state.get("job_id"):
        sd = rt.self_development
        job = sd.jobs.load(state["job_id"])
        if job["state"] == "PLANNING":
            sd.prepare_development_environment(state["job_id"], rt.sandbox.doctor())
        changes = state["candidate"] or []
        rec = sd.bind_candidate(state["job_id"], attempt_id=f"E1-ATT-{len(state.get('discarded_generations', [])) + 1}", stage="guppi-candidates/" + state["mission_id"], parent_version="demo-baseline",
                                changed_files=[c["path"] for c in changes], builder="coder",   # role name
                                builder_key=state["coder"]["independence_key"])                # the model that really wrote it
        state["candidate_id"] = rec.get("candidate_id")
    save(project, state)
    return state


def test_stage(rt, project, state):
    from guppi_runtime.selfdev.candidate_tests import run_candidate_tests, verify_candidate_tests
    out = run_candidate_tests(rt, state["mission_id"])
    m = rt.missions.load(state["mission_id"])
    state["test"] = {"status": out.get("status"), "attempt": out.get("attempt"),
                     "pending_gates": [g["gate_id"] for g in m["human_gates"]["pending"]]}
    if (out.get("attempt") or {}).get("status") == "FINISHED":
        state["test_verify"] = verify_candidate_tests(rt, state["mission_id"])
    save(project, state)
    return state


def rework_after_failed_test(rt, project, state):
    """The VM test of the candidate failed (a known outcome). Record it as deterministic FAIL evidence, let the job go to REWORK,
    keep the failing test output as feedback for the next generation, and clear the attempt so `generate` starts a new candidate."""
    attempt = (state.get("test") or {}).get("attempt") or {}
    if attempt.get("status") != "FAILED" or not attempt.get("job_id"):
        return {"status": "no_failed_test", "attempt": attempt.get("status")}
    receipt = json.loads(rt.sandbox.receipt(attempt["job_id"]))
    output = "\n".join((c.get("output") or "") for c in receipt.get("commands", []))
    lines = [l for l in output.splitlines() if l.strip()]
    # REPRO lines come from GUPPI's reproduction harness: which input raised what at which line of the candidate. They go first.
    repro = [l for l in lines if l.startswith("REPRO")][:40]
    keep = repro + [l for l in lines if l.startswith(("FAIL:", "ERROR:", "AssertionError", "Traceback", "  File", "    ", "-", "+", "?"))][:60]
    feedback = "\n".join(keep or lines[-40:])[:3000]
    watch = ReworkWatch.load(state)
    watch.record(failure_signature("test", feedback), state.get("captain_hint"))
    watch.save(state)
    sd = rt.self_development
    ev = sd.evidence_store.add("vm_unittest", job_id=state["job_id"], candidate_id=state["candidate_id"], trust_level="deterministic",
                               source_ref=attempt["job_id"], artifact_sha256=attempt.get("report_sha256"),
                               payload={"status": "FAIL", "plan_digest": attempt.get("plan_digest")})
    record = sd.attach_verification(state["job_id"], verifier="verifier", result="FAIL", evidence_refs=[ev["evidence_id"]],
                                    findings=["vm tests failed"] + keep[:5])
    old = {k: state.pop(k) for k in ("mission_id", "coder", "generation", "candidate", "mission_phase", "candidate_id", "test", "test_verify") if k in state}
    old["reason"] = "VM tests failed; reworked with the test output as feedback"
    state.setdefault("discarded_generations", []).append(old)
    state["feedback"] = feedback
    state["previous_candidate"] = [{"path": c["path"], "content": c["content"]} for c in (old.get("candidate") or [])]
    save(project, state)
    return {"status": "rework", "job_state": sd.jobs.load(state["job_id"])["state"], "verification": record.get("result"), "feedback": feedback}


def rebind_after_block(rt, project, state):
    """A BLOCKED job (e.g. independence could not be proven) goes back through PLANNING -> READY and binds the same candidate
    again, now with the builder's actual identity. The candidate gets a new id, so the review stage records its evidence anew;
    the VM test it points to is the same verified sandbox job."""
    sd = rt.self_development
    job = sd.jobs.load(state["job_id"])
    if job["state"] != "BLOCKED":
        return {"status": "not_blocked", "job_state": job["state"]}
    sd.jobs.transition(job, "PLANNING")
    sd.prepare_development_environment(state["job_id"], rt.sandbox.doctor())
    rec = sd.bind_candidate(state["job_id"], attempt_id="E1-ATT-2", stage="guppi-candidates/" + state["mission_id"], parent_version="demo-baseline",
                            changed_files=[c["path"] for c in state["candidate"]], builder="coder", builder_key=state["coder"]["independence_key"])
    state.setdefault("superseded_candidates", []).append({"candidate_id": state.get("candidate_id"), "review": state.pop("review", None)})
    state["candidate_id"] = rec["candidate_id"]
    save(project, state)
    return review_stage(rt, project, state)


def review_stage(rt, project, state):
    sd = rt.self_development
    attempt = (state.get("test") or {}).get("attempt") or {}
    verified = state.get("test_verify") or {}
    passed = attempt.get("status") == "FINISHED" and verified.get("status") == "completed"
    ev = sd.evidence_store
    test_ev = ev.add("vm_unittest", job_id=state["job_id"], candidate_id=state["candidate_id"], trust_level="deterministic",
                     source_ref=attempt.get("job_id"), artifact_sha256=attempt.get("report_sha256"),
                     payload={"status": "PASS" if passed else "FAIL", "plan_digest": attempt.get("plan_digest")})
    # The reviewer must be a different model than the one that wrote the change.
    # 16k: room for the change plus the verifier's thinking (8k with 600/3000 tokens ended without an answer, 2026-10-02).
    verifier = resolve(rt, "verifier", requirements={"context_min_tokens": 16384}, independent_of=[state["coder"]["independence_key"]])
    # The reviewer sees every changed file in full. Before 2026-10-02 this was cut at 8000 characters and gemma rightly failed a
    # 13 000-character module as "ends abruptly". Too much for the review window is refused, never shortened silently.
    diff = "\n\n".join(f"=== {c['path']} ===\n{c['content']}" for c in (state.get("candidate") or []))
    if len(diff) > 48000:
        return {"status": "review_refused", "reason": "candidate_too_large_for_review", "characters": len(diff)}
    prompt = [{"role": "system", "content": "You review a code change. Reply with exactly one line: PASS or FAIL, then a short reason."},
              {"role": "user", "content": f"Objective: {SC['objective']}\nThe change (full new file content):\n{diff}"}]
    def ask(loaded):
        return rt.control.model_call(state["job_id"], {"provider": verifier["provider_ref"], "model": loaded["identifier"],
                                                       "messages": prompt, "max_tokens": 1500, "temperature": 0,
                                                       # thinking off: with thinking, gemma spent 600 / 3000 / 6000 tokens without an
                                                       # answer on the path_health review (2026-10-02); a one-line verdict needs none
                                                       "reasoning_effort": "none"})
    reply = with_model(rt, verifier, ask)
    text = ((reply.get("model_result") or {}).get("content") or "").strip()
    if not text:
        # An empty review (e.g. the verifier thought until its token limit; seen 2026-10-02 with 600 tokens) is no verdict.
        state["review_attempts"] = state.get("review_attempts", 0) + 1
        save(project, state)
        return {"status": "review_empty", "truncated": (reply.get("model_result") or {}).get("truncated"), "attempts": state["review_attempts"]}
    review_ev = ev.add("independent_review", job_id=state["job_id"], candidate_id=state["candidate_id"], trust_level="model_assessment",
                       payload={"verifier": verifier["capability_id"], "model": verifier["model"], "reply": text[:2000]})
    verdict = "PASS" if passed and text.upper().startswith("PASS") else ("FAIL" if not passed or text.upper().startswith("FAIL") else "INCONCLUSIVE")
    record = sd.attach_verification(state["job_id"], verifier="verifier", result=verdict, verifier_key=verifier["independence_key"],
                                    evidence_refs=[test_ev["evidence_id"], review_ev["evidence_id"]], findings=[text[:500]])
    if verdict == "FAIL":
        watch = ReworkWatch.load(state)
        watch.record(failure_signature("review"), state.get("captain_hint"))
        watch.save(state)
    state["review"] = {"verifier": verifier["capability_id"], "reply": text[:500], "verdict": verdict,
                       "recorded_result": record.get("result"), "job_state": sd.jobs.load(state["job_id"])["state"],
                       "activation": sd.activation_decision(state["job_id"])}
    save(project, state)
    return state


def diagnose_stage(rt, project, state):
    """After a failed VM test: the verifier (another model family) names the CAUSE of the failure, without writing the fix.

    Captain 2026-10-03 ("Prüfer-Hinweis"): qwen3-coder got the failing test output and its own previous code and still wrote the same
    `^...$` twice; a second pair of eyes is cheaper than more blind attempts. The diagnosis goes into the next `generate` together
    with the test output. Code blocks are removed from it, so the reviewer can point at the line but not hand over the solution."""
    previous = state.get("previous_candidate") or []
    if not state.get("feedback") or not previous:
        return {"status": "nothing_to_diagnose", "hint": "run `rework` after a failed `test` first"}
    builder = next((g.get("coder") for g in reversed(state.get("discarded_generations") or []) if g.get("coder")), None) or state.get("coder")
    if not builder or not builder.get("independence_key"):
        return {"status": "builder_unknown"}
    verifier = resolve(rt, "verifier", requirements={"context_min_tokens": 16384}, independent_of=[builder["independence_key"]])
    code = "\n\n".join(f"=== {c['path']} ===\n{c['content']}" for c in previous)
    prompt = [{"role": "system", "content": ("You diagnose why a code change fails its tests. Name the exact line and explain the cause in at most "
                                             "three sentences. Do NOT write corrected code or a code block.")},
              {"role": "user", "content": f"Task: {SC['objective']}\n\nFailing test output:\n{state['feedback']}\n\nThe code that fails:\n{code}"}]
    def ask(loaded):
        return rt.control.model_call(state["job_id"], {"provider": verifier["provider_ref"], "model": loaded["identifier"], "messages": prompt,
                                                       "max_tokens": 800, "temperature": 0, "reasoning_effort": "none"})
    reply = with_model(rt, verifier, ask)
    text = ((reply.get("model_result") or {}).get("content") or "").strip()
    text = re.sub(r"```.*?(```|\Z)", "[code removed]", text, flags=re.S).strip()
    if not text:
        return {"status": "diagnosis_empty"}
    state["diagnosis"] = {"verifier": verifier["capability_id"], "model": verifier["model"], "text": text[:1500]}
    save(project, state)
    return {"status": "diagnosed", **state["diagnosis"]}


def watch_stage(rt, project, state):
    """Show the rework watch: the remembered failures and what it would say about the next generation."""
    watch = ReworkWatch.load(state)
    return {"status": "watch", "entries": watch.entries, "next_generation": watch.check(state.get("captain_hint"))}


def watch_reset_stage(rt, project, state):
    """Forget the remembered failures (after a change of coder, profile or spec); the old list is kept in the state."""
    old = state.pop("rework_watch", None)
    state.setdefault("rework_watch_resets", []).append({"entries": old})
    save(project, state)
    rt.audit.append("REWORK_WATCH_RESET", component="e1-golden-path", payload={"job_id": state.get("job_id"), "forgotten": len(old or [])})
    return {"status": "watch_reset", "forgotten": len(old or [])}


def main():
    global SC
    stages = {"watch": watch_stage, "watch_reset": watch_reset_stage, "prepare": prepare, "generate": generate_stage, "test": test_stage, "review": review_stage, "rebind": rebind_after_block,
              "rework": rework_after_failed_test, "diagnose": diagnose_stage}
    args = sys.argv[1:]
    if len(args) == 4 and args[2] == "--scenario":
        SC = load_scenario(args[3]); args = args[:2]
    if len(args) != 2 or args[1] not in set(stages) | {"status"}:
        raise SystemExit(__doc__)
    sys.argv[1:] = args
    project = Path(sys.argv[1]).resolve()
    rt = GuppiRuntime(project, ARCH)
    state = load_json(state_path(project), {}) or {}
    out = stages.get(sys.argv[2], lambda *a: state)(rt, project, state)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
