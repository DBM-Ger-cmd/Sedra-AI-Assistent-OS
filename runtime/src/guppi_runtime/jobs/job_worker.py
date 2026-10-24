"""The worker loop on the job supervisor (Phase 8b).

One worker, no parallelism (`workers: 1`). It claims the next job it is allowed to take, starts the attempt (role resolution,
reservation and model load happen inside `confirm_start`), runs a handler, and keeps the lease alive while the handler works.
It never decides what a job means: the handler does the work, the supervisor decides what a failure leads to.

  - A heartbeat runs on its own thread while the handler works, so a long model call cannot lose the lease.
  - The reaper runs between jobs, at the configured interval; `startup_recovery` runs once when the loop starts.
  - A handler that raises is reported with the exception, and with what it said it changed (`ctx.mutate()`): a mutating
    attempt whose outcome is unknown is never replayed (the supervisor's rule, not this module's).
  - Nothing here promotes a job to PASSED. That needs verification evidence and stays with the acceptance gate.
"""
from __future__ import annotations

import re
import threading
import time

from ..jobs.job_supervisor import JobError, WorkerContext
from ..jobs.token_policy import TokenBudgetError

ADVANCE_STATES = ("TESTING", "VERIFYING")

# A server that has gone bad answers with special-token runs (Gemma: `<unused49><unused49>...`) and stays bad for every later
# request in the same process (PHASE9_STATUS.md). Such text is not empty, so it must be caught explicitly.
_TOKEN_RUN = re.compile(r"(?:<unused\d+>|<pad>|<\|[a-z_]+\|>){3,}")


def degenerate_reason(text):
    """Why `text` is garbage from a broken server, or None. Kept narrow on purpose: a false hit throws away a good answer."""
    if _TOKEN_RUN.search(text):
        return "special_token_run"
    stripped = re.sub(r"\s+", "", text)
    if len(stripped) >= 200 and len(set(stripped)) <= 2:
        return "single_character_run"
    return None


class HandlerError(Exception):
    """A handler's own refusal. `code` is a failure reason the supervisor already classifies."""
    def __init__(self, code, message=None):
        super().__init__(message or code)
        self.code = code


class _Heartbeat:
    def __init__(self, ctx, interval):
        self.ctx, self.interval = ctx, interval
        self.stop_event = threading.Event()
        self.lost = False
        self.thread = threading.Thread(target=self._run, name=f"heartbeat-{ctx.job_id}", daemon=True)

    def _run(self):
        while not self.stop_event.wait(self.interval):
            try:
                self.ctx.heartbeat()
            except JobError:
                self.lost = True                    # the job was taken away (reaped, cancelled to final): stop beating
                return
            except Exception:
                continue                            # a failed beat is retried on the next tick; the lease has room for a few

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop_event.set()
        self.thread.join(timeout=5)


class Worker:
    def __init__(self, supervisor, worker_id, roles, handler, *, heartbeat_every=None, reap_every=None, idle_sleep_s=1.0,
                 monotonic=time.monotonic, sleep=None):
        self.supervisor, self.worker_id, self.roles, self.handler = supervisor, worker_id, list(roles), handler
        cfg = supervisor.config
        self.heartbeat_every = heartbeat_every if heartbeat_every is not None else cfg.heartbeat_interval_s
        self.reap_every = reap_every if reap_every is not None else cfg.reap_interval_s
        self.idle_sleep_s = idle_sleep_s
        self._mono = monotonic
        self.stopped = threading.Event()
        self._sleep = sleep or (lambda seconds: self.stopped.wait(seconds))
        self._last_reap = None

    def stop(self):
        self.stopped.set()

    def _reap_if_due(self):
        now = self._mono()
        if self._last_reap is not None and now - self._last_reap < self.reap_every:
            return []
        self._last_reap = now
        return self.supervisor.reap()

    def run_once(self):
        sup = self.supervisor
        self._reap_if_due()
        try:
            claimed = sup.claim(self.worker_id, self.roles)
        except JobError as exc:
            if exc.code in {"no_job", "worker_busy", "no_slot"}:
                # no_slot: jobs are queued but every slot is taken (or the server is starting); the job loses nothing by waiting
                return {"status": {"no_job": "idle", "worker_busy": "busy", "no_slot": "waiting"}[exc.code]}
            raise
        job_id = claimed["job"]["job_id"]
        started = sup.confirm_start(job_id, self.worker_id)
        if started["status"] != "running":
            return {"status": started["status"], "job_id": job_id, "code": started.get("code"), "decision": started.get("decision")}
        attempt = started["job"]["attempt_log"][-1]
        ctx = WorkerContext(sup, job_id, self.worker_id)
        beat = _Heartbeat(ctx, self.heartbeat_every)
        try:
            with beat:
                result = self.handler(started["job"], attempt, ctx)
        except Exception as exc:
            if beat.lost:
                return {"status": "lease_lost", "job_id": job_id}
            code = exc.code if isinstance(exc, HandlerError) else None
            failed = sup.fail(job_id, self.worker_id, reason_code=code, exception=None if code else exc,
                              mutated=ctx.mutated or None, outcome_known=not ctx.mutated)
            return {"status": "failed", "job_id": job_id, "result": failed}
        if isinstance(result, dict) and result.get("job_finished"):
            # The handler ended the attempt itself (parked it for review, completed a review): the lease is gone on purpose.
            return {"status": "handled", "job_id": job_id, "attempt_id": attempt["attempt_id"], "result": result}
        if beat.lost:
            return {"status": "lease_lost", "job_id": job_id}
        try:
            ctx.heartbeat()                                       # one last look: a cancel may have arrived at the very end
        except JobError:
            return {"status": "lease_lost", "job_id": job_id}
        if ctx.cancel_seen:
            return sup.acknowledge_cancel(job_id, self.worker_id)
        advance = (result or {}).get("advance", []) if isinstance(result, dict) else []
        for state in advance:
            if state not in ADVANCE_STATES:
                raise JobError("invalid_transition", state)
            sup.complete_step(job_id, self.worker_id, state)
        released = self._release_finished(job_id)
        return {"status": "handled", "job_id": job_id, "attempt_id": attempt["attempt_id"], "result": result, "released": released}

    def _release_finished(self, job_id):
        """A job the handler finished (VERIFYING) but did not park itself is released here. Before 2026-10-02 it kept the worker
        until the lease ran out; the reaper then took the successful attempt for a lost worker: a read-only job ran again, a
        mutating one ended DEAD (`unknown_outcome_of_mutating_attempt`). Nothing is promoted: the evidence gate still decides."""
        job = self.supervisor.store.load(job_id)
        if job["state"] != "VERIFYING" or (job.get("worker") or {}).get("worker_id") != self.worker_id:
            return None
        if job.get("kind") == "review":
            self.supervisor.complete_review(job_id, self.worker_id)
            return "review_completed"
        self.supervisor.park_for_verification(job_id, self.worker_id, allow_without_candidate=True)
        return "parked_for_verification"

    def run_forever(self, *, max_iterations=None):
        """Run until `stop()` (or `max_iterations` passes). Returns the statuses seen, for the log."""
        self.supervisor.startup_recovery()
        seen = []
        while not self.stopped.is_set() and (max_iterations is None or len(seen) < max_iterations):
            out = self.run_once()
            seen.append(out["status"])
            if out["status"] in {"idle", "busy", "waiting"}:
                self._sleep(self.idle_sleep_s)
        return seen


# How a request reads when the server process went away under it (Windows: WinError 10054 / 10053; http.client: RemoteDisconnected).
SERVER_GONE = re.compile(r"ConnectionReset|ConnectionAborted|RemoteDisconnected|Remote end closed|WinError 1005[34]|server_exited", re.I)


def model_text_handler(infer, build_messages, *, max_tokens=800, advance=("TESTING", "VERIFYING"), temperature=None,
                       policy=None, estimate_tokens=None, on_result=None, on_degenerate=None):
    """A handler that asks the resolved model one question and returns its text.

    `infer(job_id, request)` is `ControlMasterModule.model_call`. The request names the instance the loader prepared
    (`attempt["model_identifier"]`), so the call cannot land on a stale instance with another context. A reasoning model that
    spends its whole budget on thinking returns an empty answer without any error; that is a failure here, not a result.

    With an enabled `policy` (token_policy.py) the call is planned: reasoning effort and output budget come from the role, the
    input is estimated against the window that was really loaded (`estimate_tokens(messages) -> int`), and an answer that was
    cut off by the output limit gets one bounded retry with a bigger budget. Without a policy nothing changes.

    `on_result(job, attempt, result)` is called with the finished answer (`{"text", "usage", "token_report"}`); a working set uses it to
    record the reply as a turn, so that the next step composes its prompt from the stored history instead of resending it.

    An answer that is garbage from a broken server (`degenerate_reason`) is never a result and never reaches `on_result`. The
    attempt fails as `provider_unavailable`, and `on_degenerate(attempt, reason)` is called first so the caller can stop that
    server process; the next attempt then loads a fresh one."""
    def handler(job, attempt, ctx):
        messages = build_messages(job)
        role = job.get("requested_role")
        plan = None
        if policy is not None and policy.enabled:
            window = attempt.get("loaded_context") or attempt.get("resolved_context_window")
            if estimate_tokens is None or not window:
                raise HandlerError("validation_failure", "token_policy_needs_an_estimator_and_a_window")
            try:
                plan = policy.plan(role, int(estimate_tokens(messages)), int(window))
            except TokenBudgetError as exc:
                raise HandlerError(exc.code, f"{exc.code}:{exc.detail}") from exc
        calls, thought_chars = [], 0
        while True:
            request = {"provider": attempt["provider_ref"], "model": attempt.get("model_identifier") or attempt.get("model"),
                       "messages": messages, "max_tokens": plan["max_tokens"] if plan else max_tokens, "job_id": job["job_id"],
                       "attempt_id": attempt["attempt_id"], "role": role}
            if plan and plan["reasoning_effort"]:
                request["reasoning_effort"] = plan["reasoning_effort"]
            if plan and plan.get("thinking_budget_tokens"):
                request["thinking_budget_tokens"] = plan["thinking_budget_tokens"]
            if temperature is not None:
                request["temperature"] = temperature
            out = infer(job["job_id"], request)
            if out.get("status") == "waiting":
                raise HandlerError(out.get("reason_code") or "hardware_pressure")
            if out.get("status") != "completed":
                error = str(out.get("error"))[:200]
                # The local server process died under the request (2026-10-03: qwen3-coder "CUDA error: an illegal memory access", the
                # client saw the connection reset). That is a runtime crash: cool down, then one trial with a freshly started server.
                # As `provider_unavailable` it marked the WHOLE llama-cpp-server provider UNAVAILABLE, and nothing ever lifts that state.
                raise HandlerError("runtime_crash" if SERVER_GONE.search(error) else "provider_unavailable", error)
            result = out.get("model_result") or {}
            calls.append(result.get("usage") or {})
            thought_chars += int(result.get("reasoning_chars") or 0)
            text = (result.get("content") or "").strip()
            cut_off = bool(result.get("truncated"))
            broken = degenerate_reason(text) if text else None
            if broken:
                if on_degenerate is not None:
                    try:
                        on_degenerate(attempt, broken)
                    except Exception:
                        pass                          # the failure below is what counts; a failed stop shows up on the next load
                # The broken server was just stopped (on_degenerate); a restart is the remedy, so this is a runtime crash too.
                raise HandlerError("runtime_crash", f"degenerate_output:{broken}")
            if text and not (cut_off and plan):
                break
            bigger = policy.escalate(plan, len(calls) - 1) if plan else None
            if bigger is None:
                raise HandlerError("validation_failure", "empty_answer" + (":truncated_by_max_tokens" if cut_off else ""))
            plan = bigger                     # one bounded retry with room for the answer; the first call's tokens are counted as waste
        total = lambda key: sum(u.get(key) or 0 for u in calls)
        report = {"calls": len(calls), "input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"),
                  "reasoning_tokens": total("reasoning_tokens"),
                  # Some servers (llama-server) do not report thinking tokens in `usage`; the size of the thinking text is always known.
                  "reasoning_chars": thought_chars,
                  "wasted_output_tokens": sum(u.get("output_tokens") or 0 for u in calls[:-1]),
                  "reasoning_effort": request.get("reasoning_effort"), "thinking_budget_tokens": request.get("thinking_budget_tokens"),
                  "max_tokens": request["max_tokens"]}
        final = {"text": result["content"], "usage": result.get("usage"), "truncated": cut_off, "model": result.get("model"),
                 "advance": list(advance), "token_report": report}
        if on_result is not None:
            on_result(job, attempt, final)
        return final
    return handler
