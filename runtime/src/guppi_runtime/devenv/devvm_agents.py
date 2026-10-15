"""DevVM Phase 3 (docs/DEVVM_AUFTRAG_2026-10-05.md, requirement C): sub-agents. GUPPI plans, a developer implements, a reviewer checks, an executed test decides.

    host = ModelHost(loader)                                   # one model on the GPU at a time; a crashed server is restarted once
    team = DevOrchestrator(workspace, host, {"planner": "qwen3coder", "coder": "jan", "reviewer": "swe"}, vm_runner=None, audit=rt.audit)
    result = team.run("the task, in words")                    # plan -> per step: developer, (test), reviewer, retry on FAIL -> commit

Only the orchestrator starts agents (`run_agent`); an agent's toolbox has no tool that starts one, and `run_agent` refuses a depth above 1: no agents that start agents.
Every agent run has a role, a task, a tool set (devvm_tools roles), a context (the task text it is given) and a budget; its hand-in is structured (`submit_plan`, `submit_result`,
`submit_review`). Budget per run (defaults, Captain 2026-10-05: 10 minutes, 40 tool calls): calls, seconds, turns, completion tokens, blocked repeats. Guards: the loop guard (inside
the toolbox: the same read again and again), the runaway guard (an answer that is one block repeated), a turn limit with a nudge (model_tools.run_tool_loop). Every run leaves its journal
(each tool call), an audit event `DEVVM_AGENT_RUN` and, when a run log is given, a line. Nothing here starts a VM: tests run only through a `vm_runner` from the caller (the broker, with the Guard).
"""
from __future__ import annotations

import ast
import re
import time
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from dataclasses import dataclass, replace

from ..devvm import DevWorkspace
from ..comment_archive import to_jsonl
from ..devvm_style import snapshot as ws_snapshot, tidy as ws_tidy
from ..devvm_evidence import ARBITER_RULES, DRIVER, format_evidence, parse as parse_evidence
from urllib.error import HTTPError

from ..model_tools import compact_history
from ..devvm_tools import SELF_CHECK, DevToolBox, unittest_command
from ..model_tools import run_tool_loop
from ..runaway_guard import RunawayGuard
from ..solo_steps import STEP_PROMPT, extract_for, number_task, numbered, syntax_problems, workspace_map

MAX_DEPTH = 1


@dataclass
class AgentBudget:
    max_calls: int = 40
    max_seconds: int = 600
    max_turns: int = 30
    max_completion_tokens: int = 40_000
    max_stuck_blocks: int = 3
    max_nudges: int = 1      # a loop or a runaway answer gets ONE correction message before the run ends (little-coder's quality monitor)
    max_tokens_per_answer: int = 8_000      # files of a few hundred lines were cut at 4000 (answer_cut, 2026-10-06)
    max_vm_runs: int = 2
    stub_at: int = 0         # prompt tokens above which the text of OLD write calls is replaced by a note (0 = never)
    compact_at: int = 0      # prompt tokens above which old tool results are shortened during the run (0 = never)


PLANNER_ANSWER_TOKENS = 10_000


class AgentStopped(Exception):
    """Raised inside the model call to end a run early; the reason is kept next to it."""


def _text_of(data):
    message = ((data.get("choices") or [{}])[0].get("message") or {})
    return (message.get("content") or "") + (message.get("reasoning_content") or "")


CODER_EXT_KEYS = ("think_limit", "family", "max_corrections", "prune_at", "window")


def make_coder_ext(config, box, reuse=None):
    """The CoderExtensions of ONE agent run from the config dict of --coder-ext ({"enabled": "all" | "e01,e08", "think_limit": ..., "family": ..., "window": ..., "record": bool}); None without a config or with nothing enabled.
    `reuse`: the instance of the run whose conversation this run continues (solo rework, 2026-10-11): it still knows which files the model read (measured: a new one refused an edit the model had read before, 2 wasted calls)."""
    if not config or not config.get("enabled"): return None
    if reuse is not None: return reuse
    from ..coder_ext import CoderExtensions      # loaded only when the extensions are used
    ext = CoderExtensions(config["enabled"], terminal=box.terminal, tool_names=box.names, **{k: config[k] for k in CODER_EXT_KEYS if k in config})
    return ext if ext.enabled else None


def make_skills(config):
    """The skill library of --skills (config["skills"] = library folder): read-only lookups for the coder, None without it. A missing or broken library stops the build before a model is loaded (see devvm_build.coder_ext_config)."""
    if not config or not config.get("skills"): return None
    from ..skill_library import SkillLibrary
    return SkillLibrary(config["skills"])


def make_jobs(config, vm_runner, clock=time.monotonic):
    """E-06 background jobs (--bg-jobs): the coder's `shell_start` runs a command as ONE VM run in a thread (vm_process), so it needs the VM runner of the run and is off without it.
    The VM is shared with the agent's own run_python: the broker lets one run at a time, a second one answers with its own status in the job output."""
    if not config or not config.get("bg_jobs") or vm_runner is None: return None
    from ..coder_ext.bg_jobs import Jobs
    from .vm_process import make_spawn
    return Jobs(make_spawn(lambda argv: vm_runner([argv])), clock)


def run_agent(role, task, workspace: DevWorkspace, post, alias, *, sampling=None, budget=None, vm_runner=None, exclude=(), depth=1, audit=None, label="", clock=time.monotonic,
              delegator=None, delegate_roles=(), max_depth=MAX_DEPTH, history=None, self_check="full", coder_ext=None, coder_ext_state=None):
    """One agent run. Returns {role, model, label, task, final, stopped_by, calls, turns, seconds, completion_tokens, stuck_blocks, limit_hit, journal, error}.
    stopped_by: hand_in | no_tool_call | calls | time | tokens | loop | runaway | turns | answer_cut | error"""
    if depth > max_depth: raise ValueError("agent_depth_limit")
    budget = budget or AgentBudget()
    box = DevToolBox(workspace, role, vm_runner=vm_runner, max_calls=budget.max_calls, max_seconds=budget.max_seconds, max_vm_runs=SELF_CHECK[self_check]["vm_runs"] if role == "solo" else budget.max_vm_runs, self_check=self_check, exclude=exclude, clock=clock, delegator=delegator, delegate_roles=delegate_roles,
                     jobs=make_jobs(coder_ext, vm_runner), skills=make_skills(coder_ext), protected=(coder_ext or {}).get("protected", ()))
    started, tokens, stop, runaway = clock(), [0, 0], {"reason": None, "peak": 0, "nudges": 0}, RunawayGuard()      # tokens: [generated, read in (prompt)]; peak: the biggest prompt of ONE request (how full the window got)
    ext = make_coder_ext(coder_ext, box, coder_ext_state if history else None)      # E-21: one CoderExtensions per conversation (a continued conversation keeps it); None = as before
    box.ext = ext
    recorder = None
    if coder_ext and coder_ext.get("record"):      # the real server answers and what was sent, before any guard changes them; independent of the extensions (2026-10-12: on for every build)
        from ..coder_ext.replay_log import Recorder
        recorder = post = Recorder(post)

    def guarded(body):
        nonlocal runaway
        if clock() - started > budget.max_seconds: stop["reason"] = "time"; raise AgentStopped("time")
        if tokens[0] >= budget.max_completion_tokens: stop["reason"] = "tokens"; raise AgentStopped("tokens")
        if box.stuck_blocks >= budget.max_stuck_blocks:
            if stop["nudges"] >= budget.max_nudges: stop["reason"] = "loop"; raise AgentStopped("loop")
            stop["nudges"] += 1; box.stuck_blocks = 0
            reset = getattr(box.guard, "reset", None)
            if reset: reset()
            body["messages"].append({"role": "user", "content": LOOP_NOTE})       # the same list the tool loop keeps: the correction stays in the conversation
        data = post(body)
        tokens[0] += int((data.get("usage") or {}).get("completion_tokens") or 0)
        tokens[1] += int((data.get("usage") or {}).get("prompt_tokens") or 0)
        stop["peak"] = max(stop["peak"], int((data.get("usage") or {}).get("prompt_tokens") or 0))
        if runaway.feed(_text_of(data)):
            if stop["nudges"] >= budget.max_nudges: stop["reason"] = "runaway"; raise AgentStopped("runaway")
            stop["nudges"] += 1; runaway = RunawayGuard()       # the guard keeps its verdict: a new one judges the next answer
            data = {**data, "choices": [{**data["choices"][0], "message": {"role": "assistant", "content": ""}, "finish_reason": "length"}]}       # the answer is dropped and the tool loop asks again in smaller steps (the cut-answer path)
        return data

    start = (list(history) if history else [{"role": "system", "content": box.system}]) + [{"role": "user", "content": task}]      # history: the earlier conversation of the same agent (solo mode continues it after a failed acceptance test)
    out = run_tool_loop(guarded, alias, start, box, sampling or {}, max_turns=budget.max_turns, max_tokens=budget.max_tokens_per_answer, compact_at=budget.compact_at, stub_at=budget.stub_at, ext=ext)
    if stop["reason"]: reason = stop["reason"]
    elif box.final is not None: reason = "hand_in"
    elif box.limit_hit: reason = "time" if "minutes" in box.limit_hit else "calls"
    elif out.get("finish") == "length": reason = "answer_cut"
    elif out.get("error"): reason = "error"
    elif out.get("turns", 0) >= budget.max_turns: reason = "turns"
    else: reason = "no_tool_call"
    result = {"role": role, "model": alias, "label": label, "task": " ".join(task.split())[:160], "final": box.final, "stopped_by": reason, "calls": len(box.calls), "turns": out.get("turns"),
              "seconds": round(clock() - started, 1), "completion_tokens": tokens[0], "prompt_tokens": tokens[1], "prompt_peak": stop["peak"], "nudges": stop["nudges"], "tool_counts": dict(Counter(box.calls)), "stuck_blocks": box.stuck_blocks, "limit_hit": box.limit_hit, "journal": box.journal,
              "delegations": box.delegations, "depth": depth, "answer_cuts": out.get("cuts", 0), "_messages": out.get("messages"), "error": out.get("error") if reason == "error" else None,
              "coder_ext": {"enabled": sorted(ext.enabled) if ext is not None else [], **box.ext_stats, "think_less": bool(ext.request_patch()) if ext is not None else False, "corrections": out.get("ext_corrections", 0), "prunes": out.get("ext_prunes", 0)}}
    if recorder is not None: result["replay_records"] = recorder.records
    if ext is not None: result["_coder_ext"] = ext      # for a continuation of this conversation; the orchestrator takes it out before logging
    if audit:
        audit.append("DEVVM_AGENT_RUN", component="devvm", mission_id=workspace.mission_id,
                     payload={k: result[k] for k in ("role", "model", "label", "task", "stopped_by", "calls", "turns", "seconds", "completion_tokens", "stuck_blocks", "delegations", "depth")} | {"final": str(box.final)[:200]})
    return result


class ModelHost:
    """One model on the GPU at a time (12 GB). `loader.load(key)` returns (alias, plain_post, sampling) and starts that model; `loader.unload()` stops it. A swap costs the load time of the
    new model (a few seconds for the small ones). A server that dies mid-answer (connection reset) is restarted ONCE and the call repeated; the crash is kept in `crashes`."""

    def __init__(self, loader):
        self.loader, self.current, self.alias, self.sampling, self.plain = loader, None, None, {}, None
        self.swaps, self.crashes, self.load_seconds = 0, [], 0.0

    def use(self, key):
        if key != self.current:
            if self.current is not None: self.loader.unload()
            t0 = time.monotonic()
            self.alias, self.plain, self.sampling = self.loader.load(key)
            self.load_seconds += time.monotonic() - t0
            self.current = key; self.swaps += 1
        return self.alias, self._post, self.sampling

    def call(self, key, body):
        """A model call that first makes sure `key` is the model on the GPU: an agent whose helpers ran on other models finds its own model again."""
        self.use(key)
        return self._post(body)

    def _post(self, body):
        try:
            return self.plain(body)
        except HTTPError as exc:      # a 4xx answer is the server REFUSING this request (e.g. window full), not a crash: no reload, no second try with the same body, and the reason of the server is kept (am007, 2026-10-10: 8 runs ended in "HTTP Error 400" with a model restart each)
            if exc.code >= 500: return self._after_crash(exc, body)
            try: reason = exc.read().decode("utf-8", "replace")[:300]
            except Exception: reason = ""
            raise RuntimeError(f"HTTP {exc.code}: {reason}" if reason else f"HTTP {exc.code}") from exc
        except (ConnectionError, OSError) as exc:
            return self._after_crash(exc, body)

    def _after_crash(self, exc, body):
        self.crashes.append({"model": self.current, "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
        key = self.current
        try: self.loader.unload()
        except Exception: pass
        self.alias, self.plain, self.sampling = self.loader.load(key)
        return self.plain(body)

    def close(self):
        if self.current is not None:
            try: self.loader.unload()
            finally: self.current = None


CODER_TASK = ("Overall task (for context):\n{task}\n\nYour step {i} of {n}: {title}\nInstruction: {instruction}\nAcceptance: {acceptance}{check}{lessons}\n\n"
              "Do only this step. Make the changes with the tools, check the syntax of Python files you wrote and look at your diff. Do NOT commit: a reviewer checks your changes first. "
              "Hand in with submit_result.{feedback}")
CHECK_TEXT = "\n\nThis check script will be run against your work and must pass (do not edit it):\n{code}"
LESSON_TEXT = "\n\nA lesson from the team's knowledge base that matches this code:\n- {text}"
MAX_LESSONS = 1      # small models get at most ONE lesson (docs/MESSUNGEN.md 3g: two lessons together broke a task that each alone solved; cap probe 46/48 with one against 39 with two)
REVIEW_TASK = ("Overall task:\n{task}\n\nStep {i} of {n}: {title}\nInstruction: {instruction}\nAcceptance: {acceptance}\n\nChanged files since the last commit: {status}\n\n"
               "Diff of the uncommitted changes of this step:\n{diff}\n\nCheck EVERY requirement and every concrete example of the instruction against these changes, one by one (read a file with "
               "read_file only if the diff does not show enough; moved or deleted files no longer exist at their old path). PASS only if all are met; otherwise FAIL and name the missing or wrong requirement.")
_BROKEN_CHECK = ("NameError", "SyntaxError", "IndentationError", "UnboundLocalError")
_WRITERS = frozenset({"write", "write_text", "write_bytes", "mkdir", "makedirs", "rmtree", "remove", "unlink", "rename", "replace", "touch", "copy", "copyfile", "move"})


def expected_modules(task):
    """Module names the task asks for in backticks (`style_check.py`): a check written before the code exists may import them although the workspace does not have them yet."""
    return set(re.findall(r"`([a-z_][a-z0-9_]*)\.py`", str(task)))


def check_problem(code, ws, expected=()):
    """Why a planner-written check script cannot serve as judge, or None. Seen on 2026-10-06: checks that CREATE the files they should check, checks that define the function under test
    themselves and then test their own copy, checks with a syntax error. Static only; nothing is run."""
    try: tree = ast.parse(code)
    except SyntaxError: return "it does not parse"
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == "open":
                mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else next((k.value.value for k in node.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)), "r")
                if isinstance(mode, str) and any(c in mode for c in "wax+"): return "it writes files"
            if isinstance(f, ast.Attribute) and f.attr in _WRITERS: return "it creates or changes files"
    defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    asserted = {c.func.id for n in tree.body if isinstance(n, ast.Assert) for c in ast.walk(n) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    workspace = {p.split("/")[0].removesuffix(".py") for p in ws.tree()} | set(expected)
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    if defined & asserted and not imported & workspace: return "it defines the code it tests instead of importing it"
    return None


def check_is_broken(output, name):
    """True when the check script itself is wrong (undefined name, bad syntax raised in the script's own frame), not the work it checks."""
    lines = [l for l in str(output).strip().splitlines() if l.strip()]
    files = re.findall(r'File "([^"]+)"', str(output))
    return bool(lines) and any(lines[-1].startswith(e) for e in _BROKEN_CHECK) and bool(files) and files[-1].replace(chr(92), "/").endswith(name)
PLAN_DELEGATE_HINT = (" If the workspace has more than a few files, you SHOULD first hand the reading of it to a helper: delegate(role='explorer', instruction='report which files exist, "
                      "which functions they define and what they do'). Plan from its report.")
DELEGATE_HINT = ("\n\nYou work in a team and you SHOULD use helper agents with the delegate tool: when your change is done, call delegate(role='reviewer', instruction=...) and write every "
                 "requirement and every concrete example of your step into the instruction so the reviewer can check each one; fix what it reports. If you cannot fix a reported defect yourself, "
                 "call delegate(role='strong_coder', instruction=...) naming the file and the exact defect. Then hand in with submit_result.")
SOLO_PROMPT = "{task}{lessons}\n\nWork on your own. {check} Do NOT commit."
SOLO_STEP_PROMPT = ("You build ONE step of a larger task; the earlier steps are already in the workspace (look at the files you need, do not rewrite them).\nPlan: {plan}\n\nYour step {i} of {n}:\n{instruction}\n\nDone when: {acceptance}{lessons}\n\n"
                    "Work on your own. Check your work with a small check_*.py script and run_python before you hand in with submit_result. Do NOT commit.")
CONTINUE_PROMPT = ("The independent acceptance test of the Captain does NOT pass yet (you do not see the test, only this report of its first failing checks):\n{report}\n\n"
                   "Find the cause in your code, fix it with small edits (edit_file) and {again}; keep everything that already works. Do NOT commit. Hand in again with submit_result.")
SOLO_TASK = ("{task}{lessons}\n\nMake the changes with the tools, check the syntax of the Python files you wrote and look at your diff. Before you hand in, read the task again clause by clause (every sentence and every part of a sentence) "
             "and compare each clause with your code and your tests, above all the unusual inputs it names: None, missing, empty, invalid, ties, limits and what a function returns in those cases. Add ONE short test (a few lines) for every clause that has none, but at most 20 tests in all, and write the test file in pieces of at most 100 lines per call (create it, then add more with edit_file). "
             "Do NOT commit. Hand in with submit_result.")
STRONG_TASK = ("{task}{lessons}\n\nA teammate already made a first attempt; it is in the workspace and does NOT meet the requirement: {feedback}\n\n"
               "This check script will be run against your work and must pass (do not edit it):\n{code}\n\nFix the work (read the files first). Do NOT commit. Hand in with submit_result.")
CHECKER_NOTE = ("\n\nA developer has already made a first attempt at this task; it is in the workspace. You are NOT planning work now: your job is the acceptance check. Use exactly ONE step "
                "(title: 'task', the instruction can repeat the task) and put the check script in its `check`: it imports the workspace code, calls it and asserts the result of EVERY concrete example of "
                "the task (it only reads, never writes a file). Hand it in with submit_plan. Rules for a check that is right: (1) build every input from ONE complete valid example and change exactly ONE "
                "thing per assertion; never use partial inputs, because a missing part changes the result of the task itself. (2) No two assertions may contradict each other: whatever the task says about "
                "a missing or empty part holds in every assertion. (3) Compare results exactly as the task defines them (order, sorting, type); do not add expectations the task does not state. "
                "(4) Go through the task clause by clause: every sentence or part of a sentence that names a limit, an error code, a default or a missing, None, empty or invalid input needs its own assertion, also when it stands in a subordinate clause.")
CHECK_RULES = CHECKER_NOTE[CHECKER_NOTE.index(" Rules for a check that is right"):]
CHECKER_FIRST_NOTE = ("\n\nNo code exists yet for this task: a developer is writing it right now. You are NOT planning work: your job is the acceptance check. Write it from the task text ONLY, as for a module you have "
                      "never seen: it imports the module by the exact names the task gives, calls the functions as the task defines them and asserts the result of EVERY concrete example of the task. "
                      "Use exactly ONE step (title: 'task', the instruction can repeat the task) and put the check script in its `check` (it only reads, never writes a file). Hand it in with submit_plan." + CHECK_RULES)
STEP_PLAN_TASK = "The task, in numbered lines:\n{task}\n\nLook at the workspace (outline gives the classes and functions of a file), then cut the task into steps. Use ONE step unless the task clearly has separate parts.{split}"
STEP_PLAN_SPLIT = " This task is long: cut it into at least TWO steps at natural seams (for example validation and result shape, then the matching, then the gaps), so that no step needs the whole task."
SYNTAX_PROMPT = "The Python file(s) do not parse after your step: {problems}\nFix this with small edits (edit_file), then hand in again with submit_result. Do NOT commit."
LOOP_NOTE = ("You are repeating the same calls and getting the same results. Stop and change your approach: read a DIFFERENT part of the code, change the file with edit_file, or, if the work is done, hand it in with submit_result.")
PLAN_TASK = "Task:\n{task}\n\nLook at the workspace, then plan. Use ONE step unless the task clearly has separate parts."


class DevOrchestrator:
    def __init__(self, workspace: DevWorkspace, host: ModelHost, models, *, vm_runner=None, audit=None, say=None, budget=None, max_rounds=2, clock=time.monotonic,
                 mode="escalating", max_depth=MAX_DEPTH, max_subagents=4, same_model=False, check_first=False, parallel_check=False, tidy=False, comment_log=None, comment_meta=None, plan_steps=False, step_syntax_check=False, fresh_rework=False, context=32768, self_check="full", coder_ext=None):
        self.coder_ext = coder_ext      # E-21: config dict of the coder extensions for every agent run (None = off)
        self.context = context      # the window of the model: the limits for the history follow it (compact at 60 %, old written code at 20 %, at most a quarter of it for one answer, a task over 5.5 % in characters is cut in two steps)
        self.solo_budget = replace(self.SOLO_BUDGET, compact_at=int(context * 0.6), stub_at=int(context * 0.2), max_tokens_per_answer=min(self.SOLO_BUDGET.max_tokens_per_answer, max(512, context // 4)))
        self.split_at = max(900, int(context * 0.055))
        if self_check not in SELF_CHECK: raise ValueError("unknown_self_check")
        self.self_check = self_check      # how much the solo developer checks his own work: full | light | none (see devvm_tools.SELF_CHECK)
        self.rescued = []      # files put back to the last commit because a run ended without a hand-in and left them unparsable
        self.step_syntax_check, self.fresh_rework = step_syntax_check, fresh_rework      # options of the step plan: a syntax check after every step; a rework with a fresh conversation instead of the old one
        self.plan_steps = plan_steps      # solo mode: the planner splits the task and the developer gets ONE step per fresh conversation (a short history)
        if mode not in ("pipeline", "delegating", "escalating", "solo"): raise ValueError("unknown_mode")
        if mode == "delegating" and max_depth < 2: raise ValueError("delegation_needs_depth_2")      # helpers starting from agents are opt-in: the default ceiling stays at depth 1
        self.mode, self.max_depth, self.max_subagents, self.subagents = mode, max_depth, max_subagents, 0
        self.same_model = same_model        # Captain 2026-10-06: helpers use the model that is loaded anyway when possible; a stronger model comes in only when something failed
        self.ws, self.host, self.models, self.vm_runner, self.audit = workspace, host, models, vm_runner, audit
        self.say, self.budget, self.max_rounds, self.clock = say or (lambda text: None), budget or AgentBudget(), max_rounds, clock
        self.runs, self.broken_checks, self.escalations, self.dropped_checks, self.replans = [], 0, 0, 0, 0
        self.rejected_checks = []           # unusable checks (problem + text), for diagnosis
        self.comment_log, self.comment_meta = comment_log, dict(comment_meta or {})      # Captain 2026-10-09: the comments that tidy strips are saved to this JSON-lines file first (the judge and the failure search can read them)
        self.tidy, self.tidied = tidy, []       # Captain 2026-10-08: comments and docstrings are stripped by code, new helper files deleted, after every coder turn (devvm_style)
        self.check_first, self.parallel_check = check_first, parallel_check      # Captain 2026-10-07: the check is written from the task alone, optionally at the same time as the code
        self.lessons = []
        self.convo = None       # solo mode: the messages of the developer's conversation (continued after a failed acceptance test)

    def _agent(self, role, task, label, model_role=None, parent=None, depth=1, budget=None, **kw):
        key = self.models[model_role or role]
        if self.same_model and role in ("reviewer", "explorer") and self.host.current is not None: key = self.host.current      # no swap for a reviewer or explorer
        alias, _, sampling = self.host.use(key)
        post = lambda body, key=key: self.host.call(key, body)       # every call re-checks that this agent's own model is the one loaded
        if role == "solo" and kw.get("history"): kw["coder_ext_state"] = getattr(self, "convo_ext", None)      # the continued conversation keeps its extensions (what the model read)
        result = run_agent(role, task, self.ws, post, alias, sampling=sampling, budget=budget or self.budget, audit=self.audit, label=label, clock=self.clock, depth=depth, max_depth=self.max_depth, coder_ext=self.coder_ext, **kw)
        ext = result.pop("_coder_ext", None)
        if role == "solo" and ext is not None: self.convo_ext = ext
        result["parent"] = parent
        if role == "solo": self._rescue(result)
        if role == "solo" and result.get("_messages"): self.convo = result["_messages"]       # a failed run (HTTP error) keeps the earlier conversation
        result.pop("_messages", None)       # the conversation stays on the orchestrator, not in the results that are logged
        self.runs.append(result)
        self.say(f"   {'  ' * (depth - 1)}agent {label:{22 - 2 * (depth - 1)}s} {alias:22s} {result['stopped_by']:11s} {result['calls']:2d} calls {result['seconds']:6.1f} s {result['completion_tokens']} tokens, {result.get('prompt_tokens', 0)} prompt, peak {result.get('prompt_peak', 0)}"
                 + (f"  delegated {result['delegations']}x" if result.get("delegations") else "")
                 + (f"  error: {str(result['error'])[:200]}" if result.get("error") else ""))
        return result

    SUB_BUDGET = AgentBudget(max_calls=25, max_seconds=300, max_turns=20, max_completion_tokens=20_000)

    def _delegator(self, parent_label, task, instruction_of_parent=""):
        """The `delegate` tool of an agent (delegating mode only). Helpers are leaves (depth 2 = max_depth); the team has a total of `max_subagents` helpers per run."""
        def delegate(role, instruction):
            if self.subagents >= self.max_subagents: return f"error: the team already used its {self.max_subagents} helpers for this run"
            self.subagents += 1
            label = f"sub:{role} of {parent_label}"
            if role == "reviewer":
                status = {k: [p for p in v if not p.startswith("acceptance_step")] for k, v in self.ws.status().items()}
                diff = "".join(self.ws.diff(p) for k in status.values() for p in k)
                res = self._agent("reviewer", f"A teammate asks you to check their work.\n\nThe overall task:\n{task}\n\nWhat to check (from the teammate):\n{instruction}\n\n"
                                              f"Changed files since the last commit: {'; '.join(f'{k}: {chr(44).join(v)}' for k, v in status.items() if v) or '(none)'}\n\nDiff:\n{diff[:8000] or '(no changes)'}\n\n"
                                              "Check every requirement and every concrete example, one by one. PASS only if all are met; otherwise FAIL and name what is missing or wrong.",
                                  label, parent=parent_label, depth=2, budget=self.SUB_BUDGET)
                final = res["final"] or {}
                return f"{final['verdict']}: {final.get('cause') or 'no defect found'}" if final.get("verdict") else "the reviewer gave no verdict"
            if role == "strong_coder":
                res = self._agent("coder", f"A teammate asks you to do this in the workspace:\n{instruction}\n\nOverall task, for context:\n{task}\n\nDo not commit. Hand in with submit_result.",
                                  label, model_role="coder_strong", parent=parent_label, depth=2, budget=self.SUB_BUDGET, exclude=("git_commit",))
                changed = "; ".join(f"{k}: {', '.join(v)}" for k, v in self.ws.status().items() if v) or "nothing changed"
                return f"{(res['final'] or {}).get('summary') or 'the helper handed in nothing'} (workspace now: {changed})"
            res = self._agent("explorer", instruction, label, model_role="planner", parent=parent_label, depth=2, budget=self.SUB_BUDGET)
            return (res["final"] or {}).get("summary") or "the explorer handed in nothing"
        return delegate

    def _delegate_roles(self, parent_role):
        if self.mode != "delegating": return ()
        if parent_role == "planner": return ("explorer",)
        return tuple(r for r, key in (("reviewer", "reviewer"), ("strong_coder", "coder_strong")) if self.models.get(key))

    def _audit(self, event, payload):
        if self.audit: self.audit.append(event, component="devvm", mission_id=self.ws.mission_id, payload=payload)

    def plan(self, task, retry_note="", label="planner"):
        roles = self._delegate_roles("planner")
        result = self._agent("planner", PLAN_TASK.format(task=task) + retry_note + (PLAN_DELEGATE_HINT if roles else ""), label,
                             budget=replace(self.budget, max_tokens_per_answer=PLANNER_ANSWER_TOKENS),       # a check script for a larger task did not fit into 4000 tokens (answer_cut, 2026-10-06)
                             delegator=self._delegator(label, task) if roles else None, delegate_roles=roles)
        steps = (result["final"] or {}).get("steps")
        if not steps:
            self.say("   plan: the planner handed in nothing usable, the whole task is one step")
            steps = [{"title": "whole task", "instruction": task, "acceptance": "", "check": ""}]
            fallback = True
        else: fallback = False
        self._audit("DEVVM_PLAN", {"steps": [s["title"] for s in steps], "fallback": fallback})
        return steps, fallback

    def _judge(self, commands):
        result = self.vm_runner(commands)
        if result.get("status") not in ("completed", "failed"): return False, None, f"not run: {result.get('status')}"
        return True, result.get("status") == "completed", str(result.get("output") or "")[-1500:]

    def _tests(self, step, i, n):
        """The executed test as judge, only with a vm_runner (the broker and its gate): 1) the check script the planner wrote for this step, 2) after the LAST step also the workspace's own
        unit tests (earlier steps may legitimately leave them failing). Returns (ran, passed, output)."""
        if self.vm_runner is None: return False, None, ""
        ran_any = False
        if step.get("check") and step["check"] != step.get("_usable"):
            problem = check_problem(step["check"], self.ws)
            if problem:
                self.say(f"   step {i}: the planner's check is not usable ({problem}); it is dropped, the reviewer decides"); self.dropped_checks += 1; step["check"] = ""
            else: step["_usable"] = step["check"]
        if step.get("check"):
            name = f"acceptance_step{i}.py"
            self.ws.write(name, step["check"] if step["check"].endswith(chr(10)) else step["check"] + chr(10))
            ran, passed, output = self._judge([["python3", name]])
            if ran and not passed and check_is_broken(output, name):
                self.say(f"   step {i}: the planner's check script is itself broken ({output.strip().splitlines()[-1][:80]}); it is dropped, the reviewer decides")
                self.ws.delete(name); self.broken_checks += 1; ran = False
            ran_any = ran_any or ran
            if ran and not passed: return True, False, "the check script of this step fails:" + chr(10) + output
        if i == n and any(p.split("/")[-1].startswith("test_") for p in self.ws.tree()):
            ran, passed, output = self._judge([unittest_command(self.ws)])
            if ran and not passed and "NO TESTS RAN" in output: self.say(f"   step {i}: the unit tests found no test to run; not counted"); ran = False
            ran_any = ran_any or ran
            if ran and not passed: return True, False, "the unit tests fail:" + chr(10) + output
        return ran_any, (True if ran_any else None), ""

    def _step_delegating(self, task, step, i, n):
        """Delegating mode: the developer is the actor; reviewer and strong coder are helpers it calls itself. The executed check judges, nothing else is run by the pipeline."""
        record, feedback, accepted = {"title": step["title"], "rounds": []}, "", False
        if step.get("check") and self.vm_runner is not None:
            problem = check_problem(step["check"], self.ws)
            if problem:
                self.say(f"   step {i}: the planner's check is not usable ({problem}); it is dropped"); self.dropped_checks += 1; step["check"] = ""
            else: step["_usable"] = step["check"]
        roles = self._delegate_roles("coder")
        for rnd in range(1, self.max_rounds + 1):
            fb = f"\n\nYour previous attempt was rejected: {feedback}\nFix exactly that." if feedback else ""
            label = f"coder s{i} r{rnd}"
            coder = self._agent("coder", CODER_TASK.format(task=task, i=i, n=n, title=step["title"], instruction=step["instruction"], acceptance=step["acceptance"] or "(none given)", feedback=fb,
                                                         check=CHECK_TEXT.format(code=step["check"]) if step.get("check") and self.vm_runner is not None else "",
                                                         lessons="".join(LESSON_TEXT.format(text=l) for l in self.lessons)) + (DELEGATE_HINT if roles else ""),
                                label, exclude=("git_commit",), delegator=self._delegator(label, task) if roles else None, delegate_roles=roles)
            row = {"round": rnd, "coder": {"stopped_by": coder["stopped_by"], "summary": (coder["final"] or {}).get("summary"), "delegations": coder.get("delegations", 0)}}
            ran, passed, output = self._tests(step, i, n)
            row["test"] = {"ran": ran, "passed": passed}
            if ran and not passed:
                feedback = output; row["verdict"] = "FAIL(test)"; record["rounds"].append(row); self.say(f"   step {i} round {rnd}: test failed"); continue
            row["verdict"] = "PASS(test)" if ran else "accepted"; record["rounds"].append(row); accepted = True; break
        record["accepted"] = accepted
        if any(self.ws.status().values()):
            record["commit"] = self.ws.commit(step["title"] if accepted else "UNREVIEWED: " + step["title"])
        self._audit("DEVVM_STEP", {"title": step["title"], "accepted": accepted, "rounds": len(record["rounds"]), "mode": self.mode})
        return record

    def step(self, task, step, i, n):
        if self.mode == "delegating": return self._step_delegating(task, step, i, n)
        record, feedback, accepted = {"title": step["title"], "rounds": []}, "", False
        if step.get("check") and self.vm_runner is not None:
            problem = check_problem(step["check"], self.ws)
            if problem:
                self.say(f"   step {i}: the planner's check is not usable ({problem}); it is dropped, the reviewer decides"); self.dropped_checks += 1; step["check"] = ""
            else: step["_usable"] = step["check"]
        for rnd in range(1, self.max_rounds + 1):
            fb = f"\n\nYour previous attempt was rejected: {feedback}\nFix exactly that." if feedback else ""
            strong = bool(feedback) and bool(self.models.get("coder_strong"))      # the small developer failed once: the strong model takes over for the retry
            self.escalations += strong
            coder = self._agent("coder", CODER_TASK.format(task=task, i=i, n=n, title=step["title"], instruction=step["instruction"], acceptance=step["acceptance"] or "(none given)", feedback=fb,
                                                         check=CHECK_TEXT.format(code=step["check"]) if step.get("check") and self.vm_runner is not None else "",
                                                         lessons="".join(LESSON_TEXT.format(text=l) for l in self.lessons)),
                                f"coder s{i} r{rnd}" + (" (strong)" if strong else ""), model_role="coder_strong" if strong else None, exclude=("git_commit",))
            row = {"round": rnd, "coder": {"stopped_by": coder["stopped_by"], "summary": (coder["final"] or {}).get("summary")}}
            ran, passed, output = self._tests(step, i, n)
            row["test"] = {"ran": ran, "passed": passed}
            arbitration = ""
            if ran and not passed:
                feedback = output
                if rnd < self.max_rounds:
                    row["verdict"] = "FAIL(test)"; record["rounds"].append(row); self.say(f"   step {i} round {rnd}: test failed"); continue
                # the last round: the check may be the wrong one (a planner's check can be). The reviewer decides, and only an explicit PASS accepts.
                self.say(f"   step {i} round {rnd}: test failed again, the reviewer arbitrates")
                row["test_failed"] = True
                arbitration = f"\n\nAn automatic check of this step failed with:\n{output[-800:]}\nThe check itself may be wrong. Decide from the diff and the instruction whether the work meets the requirements."
            status = {k: [p for p in v if not p.startswith("acceptance_step")] for k, v in self.ws.status().items()}        # the planner's check scripts are not part of the work to review
            diff = "".join(self.ws.diff(p) for k in status.values() for p in k)
            review = self._agent("reviewer", REVIEW_TASK.format(task=task, i=i, n=n, title=step["title"], instruction=step["instruction"], acceptance=step["acceptance"] or "(none given)",
                                                                  status="; ".join(f"{k}: {', '.join(v)}" for k, v in status.items() if v) or "(none)", diff=diff[:8000] or "(no changes)") + arbitration, f"reviewer s{i} r{rnd}")
            final = review["final"] or {}
            verdict = final.get("verdict")
            row["verdict"] = verdict or "no_verdict"; row["cause"] = final.get("cause")
            record["rounds"].append(row)
            self.say(f"   step {i} round {rnd}: reviewer {row['verdict']}" + (f" ({(final.get('cause') or '')[:90]})" if verdict == "FAIL" else ""))
            if (verdict == "PASS") if arbitration else (verdict != "FAIL"):
                accepted = True
                if arbitration: row["overruled_check"] = True
                break
            feedback = final.get("cause") or "the reviewer found a defect"
        record["accepted"] = accepted
        if any(self.ws.status().values()):
            record["commit"] = self.ws.commit(step["title"] if accepted else "UNREVIEWED: " + step["title"])
        self._audit("DEVVM_STEP", {"title": step["title"], "accepted": accepted, "rounds": len(record["rounds"])})
        return record

    def _evidence(self, step):
        """What the check really says: each of its assertions run separately, to the end, in the microVM (devvm_evidence). Empty without a check or a vm_runner, or when the driver reports nothing."""
        if self.vm_runner is None or not step.get("check"): return ""
        check_name, driver_name = "acceptance_evidence_check.py", "acceptance_evidence.py"
        result = None
        try:
            self.ws.write(check_name, step["check"] if step["check"].endswith(chr(10)) else step["check"] + chr(10)); self.ws.write(driver_name, DRIVER)
            result = self.vm_runner([["python3", driver_name, check_name]])
        except Exception as exc:
            self.say(f"   arbiter: no evidence table ({type(exc).__name__})")
        finally:
            for name in (check_name, driver_name):
                try: self.ws.delete(name)
                except Exception: pass
        table = parse_evidence((result or {}).get("output", "")) if result else None
        return "\n\n" + format_evidence(step["check"], table) + ARBITER_RULES if table else ""

    def _arbitrate(self, task, step, output, label):
        """The check may be the wrong one (the planner's check can be). The model that is loaded anyway (the strong one) judges from the diff and the task; only an explicit PASS overrules the check."""
        status = {k: [p for p in v if not p.startswith("acceptance_")] for k, v in self.ws.status().items()}
        diff = "".join(self.ws.diff(p) for k in status.values() for p in k)
        note = ("\n\nAn automatic check of this task failed with:\n" + output[-800:] + self._evidence(step)
                + "\nThe check itself may be wrong. Decide from the diff and the instruction whether the work meets the requirements.")
        review = self._agent("reviewer", REVIEW_TASK.format(task=task, i=1, n=1, title=step["title"], instruction=step["instruction"], acceptance="(none given)",
                                                              status="; ".join(f"{k}: {', '.join(v)}" for k, v in status.items() if v) or "(none)", diff=diff[:8000] or "(no changes)") + note,
                             label, model_role="arbiter" if "arbiter" in self.models else "planner")
        return (review["final"] or {}).get("verdict")

    def _lesson_text(self):
        return "".join(LESSON_TEXT.format(text=l) for l in self.lessons)

    def archive_comments(self, comments):
        """Appends the comments and docstrings that tidy stripped to the comment log (one JSON line each, with path, turn and the meta of the stage). Never raises: a full disk must not stop a build."""
        if not self.comment_log or not comments: return
        try:
            self.comment_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self.comment_log, "a", encoding="utf-8") as handle:
                for path, entries in sorted(comments.items()):
                    handle.write(to_jsonl(entries, {**self.comment_meta, "path": path, "turn": len(self.tidied)}))
        except OSError as exc:
            self.say(f"   tidy: comment log not written ({type(exc).__name__})")

    def tidy_files(self, before, task):
        """After a coder turn (`before` = snapshot taken before it): strip comments and docstrings, delete new helper files, record what needs thought. Does nothing unless tidy is on."""
        if not self.tidy or before is None: return
        out = ws_tidy(self.ws, before, expected_modules(task))
        self.tidied.append({k: v for k, v in out.items() if k != "comments"})
        self.archive_comments(out.get("comments"))
        if out["stripped"] or out["deleted"]:
            self.say(f"   tidy: stripped {', '.join(out['stripped']) or '-'}; deleted {', '.join(out['deleted']) or '-'}")

    def _solo_coder(self, task):
        before = ws_snapshot(self.ws) if self.tidy else None
        result = self._agent("coder", SOLO_TASK.format(task=task, lessons=self._lesson_text()), "coder (alone)", exclude=("git_commit",))
        self.tidy_files(before, task)
        return result

    def _write_check(self, task, step, first_note):
        """Asks for an acceptance check (twice at most) and keeps the first usable one in step["check"]; an unusable one is kept in rejected_checks."""
        note, expected = first_note, expected_modules(task)
        for attempt in (1, 2):
            steps, fallback = self.plan(task, note, "checker" if attempt == 1 else "checker (retry)")
            check = "\n".join(s["check"] for s in steps if s.get("check")) if not fallback else ""
            problem = check_problem(check, self.ws, expected) if check else "it has no check"
            if not problem: step["check"], step["_usable"] = check, check; return
            self.rejected_checks.append({"problem": problem, "check": check[:3000]})
            self.say(f"   checker: the check is not usable ({problem})" + ("; asking once more" if attempt == 1 else "; the first attempt stays unjudged"))
            note = first_note + f"\n\nYour previous check was unusable: {problem}. Every check must import the workspace code, only read, and assert the concrete examples of the task."
            if attempt == 1: self.replans += 1

    def _code_and_check_first(self, task, step):
        """The check is written from the task alone. With `parallel_check` and the SAME model for coder and checker both run at the same time (the model server needs two slots; with one slot
        its queue serialises them); with different models they run one after the other, because a swap in the middle of the other agent's work would cost more than it saves."""
        if self.parallel_check and self.models["coder"] == self.models["planner"]:
            self.host.use(self.models["coder"])
            with ThreadPoolExecutor(max_workers=2) as pool:
                coder, checker = pool.submit(self._solo_coder, task), pool.submit(self._write_check, task, step, CHECKER_FIRST_NOTE)
                checker.result()
                return coder.result()
        self._write_check(task, step, CHECKER_FIRST_NOTE)
        return self._solo_coder(task)

    def _run_escalating(self, task, t0):
        """`escalating` mode: the small developer works ALONE first. Only then does the strong model write the acceptance check (it is loaded anyway for the next step), an executed
        test judges, and only a FAILING check brings the strong model in as developer (no swap: the checker already loaded it). No planner steps, no reviewer, no helpers.
        Without a vm_runner nothing can be judged: the first attempt is returned as `unjudged`."""
        record = {"title": "task", "rounds": []}
        step, accepted, unjudged, disputed = {"title": "task", "instruction": task, "acceptance": "", "check": ""}, False, False, False
        prepared = False
        if self.check_first and self.vm_runner is not None:
            first, prepared = self._code_and_check_first(task, step), True
        else:
            first = self._solo_coder(task)
        row = {"round": 1, "coder": {"stopped_by": first["stopped_by"], "summary": (first["final"] or {}).get("summary")}}
        if self.vm_runner is None:
            row["verdict"], unjudged = "unjudged", True; record["rounds"].append(row); accepted = True
        else:
            if not prepared: self._write_check(task, step, CHECKER_NOTE)
            if not step["check"]:
                self.dropped_checks += 1; row["verdict"], unjudged = "unjudged", True; record["rounds"].append(row); accepted = True
            else:
                ran, passed, output = self._tests(step, 1, 1)
                row["test"] = {"ran": ran, "passed": passed}
                if not ran or passed is None: row["verdict"], unjudged = "unjudged", True; record["rounds"].append(row); accepted = True
                elif passed: row["verdict"] = "PASS(test)"; record["rounds"].append(row); accepted = True
                else:
                    row["verdict"] = "FAIL(test)"; record["rounds"].append(row); feedback = output
                    for rnd in range(2, self.max_rounds + 2):          # the strong model gets up to `max_rounds` attempts
                        self.escalations += 1
                        before = ws_snapshot(self.ws) if self.tidy else None
                        strong = self._agent("coder", STRONG_TASK.format(task=task, lessons=self._lesson_text(), feedback=feedback, code=step["check"]), f"coder (strong) r{rnd - 1}",
                                             model_role="coder_strong", exclude=("git_commit",))
                        self.tidy_files(before, task)
                        row = {"round": rnd, "coder": {"stopped_by": strong["stopped_by"], "summary": (strong["final"] or {}).get("summary")}}
                        ran, passed, output = self._tests(step, 1, 1)
                        row["test"] = {"ran": ran, "passed": passed}
                        if ran and not passed:
                            row["verdict"] = "FAIL(test)"; record["rounds"].append(row)
                            stuck = output.strip()[-400:] == feedback.strip()[-400:]       # the same failure twice: more rounds will not help, the check is suspect
                            feedback = output; self.say(f"   strong coder round {rnd - 1}: check failed again")
                            if stuck or rnd == self.max_rounds + 1:
                                self.say("   the check is suspect, the strong model arbitrates")
                                if self._arbitrate(task, step, output, f"arbiter r{rnd - 1}") == "PASS": row["overruled_check"] = True; disputed = accepted = True; break
                                break
                            continue
                        row["verdict"] = "PASS(test)" if ran else "unjudged"; record["rounds"].append(row); accepted = True; break
        record["accepted"], record["unjudged"] = accepted, unjudged
        if any(self.ws.status().values()):
            record["commit"] = self.ws.commit(("task (check disputed)" if disputed else "task") if accepted else "UNREVIEWED: task")
        self._audit("DEVVM_STEP", {"title": "task", "accepted": accepted, "rounds": len(record["rounds"]), "mode": self.mode, "unjudged": unjudged})
        return self._result([record], ["task"], False, t0)

    SOLO_BUDGET = AgentBudget(max_calls=80, max_seconds=1200, max_turns=45, max_completion_tokens=60_000, max_vm_runs=8, compact_at=20_000, stub_at=6_000)

    def _run_solo(self, task, t0):
        """`solo` mode (Captain 2026-10-09: one model for every role, so no hand-offs between copies of the same model): ONE developer who also checks his own work with a small script in the VM, in ONE conversation.
        There is no checker, no arbiter and no strong coder: the independent judge is the acceptance test of the caller (`continue_solo` continues the same conversation with its report)."""
        self.solo_task = task
        if self.plan_steps: return self._run_solo_steps(task, t0)
        before = ws_snapshot(self.ws) if self.tidy else None
        first = self._agent("solo", SOLO_PROMPT.format(task=task, lessons=self._lesson_text(), check=SELF_CHECK[self.self_check]["prompt"]), "solo developer", model_role="coder", budget=self.solo_budget, exclude=("git_commit",), vm_runner=self.vm_runner, self_check=self.self_check)
        self.tidy_files(before, task)
        record = {"title": "task", "rounds": [{"round": 1, "coder": {"stopped_by": first["stopped_by"], "summary": (first["final"] or {}).get("summary")}, "verdict": "unjudged"}], "accepted": True, "unjudged": True}
        if any(self.ws.status().values()): record["commit"] = self.ws.commit("task")
        self._audit("DEVVM_STEP", {"title": "task", "accepted": True, "rounds": 1, "mode": self.mode, "unjudged": True})
        return self._result([record], ["task"], False, t0)

    def plan_solo(self, task, units):
        """The step plan for the solo developer: the task in numbered lines in, 1-4 steps out (title, instruction, lines, interface, acceptance). A task over self.split_at characters (5.5 % of the window) must be cut into at least two steps."""
        split = STEP_PLAN_SPLIT if len(task) > self.split_at else ""
        result = self._agent("step_planner", STEP_PLAN_TASK.format(task=numbered(units), split=split), "planner", model_role="planner",
                             budget=replace(self.budget, max_tokens_per_answer=PLANNER_ANSWER_TOKENS))
        steps = (result["final"] or {}).get("steps")
        fallback = not steps
        if fallback:
            self.say("   plan: the planner handed in nothing usable, the whole task is one step")
            steps = [{"title": "whole task", "instruction": task, "acceptance": "", "lines": [], "interface": ""}]
        self._audit("DEVVM_PLAN", {"steps": [s["title"] for s in steps], "fallback": fallback, "mode": "solo_steps"})
        return steps, fallback

    def _run_solo_steps(self, task, t0):
        """Captain 2026-10-10: the planner makes the plan so that the developer needs only the step in front of him. Every step is a NEW conversation (system message, plan with interfaces, one line from each earlier step, a map of the workspace,
        the units of the task that belong to the step WORD FOR WORD), so the history that is sent with every request stays short. A task the planner keeps as ONE step is built like plain solo mode. The checks of the planner are not used
        (only the hidden acceptance test judges). Option step_syntax_check: a file that does not parse after a step goes back to the developer (at most twice)."""
        units = number_task(task)
        steps, fallback = self.plan_solo(task, units)
        plan = "\n".join(f"{i}. {s['title']}" + (f" - {s['interface']}" if s.get("interface") else "") for i, s in enumerate(steps, 1))
        records, notes = [], []
        for i, s in enumerate(steps, 1):
            before = ws_snapshot(self.ws) if self.tidy else None
            if len(steps) > 1:
                prompt = STEP_PROMPT.format(plan=plan, notes=("Notes from the earlier steps:\n" + "\n".join(notes) + "\n") if notes else "", map=self._map_text(), i=i, n=len(steps), title=s["title"], instruction=s["instruction"],
                                            extract=extract_for(s, steps, units), acceptance=s.get("acceptance") or "everything the step asks for works", lessons=self._lesson_text(), check=SELF_CHECK[self.self_check]["prompt"])
            else: prompt = SOLO_PROMPT.format(task=task, lessons=self._lesson_text(), check=SELF_CHECK[self.self_check]["prompt"])
            label = f"solo developer (step {i}/{len(steps)})" if len(steps) > 1 else "solo developer"
            run = self._agent("solo", prompt, label, model_role="coder", budget=self.solo_budget, exclude=("git_commit",), vm_runner=self.vm_runner, self_check=self.self_check)
            for attempt in range(2 if self.step_syntax_check else 0):
                problems = syntax_problems(self.ws)
                if not problems: break
                self.say(f"   step {i}: syntax problem {problems[0][0]} line {problems[0][1]}, back to the developer")
                run = self._agent("solo", SYNTAX_PROMPT.format(problems="; ".join(f"{f} line {n}: {m}" for f, n, m in problems)), f"{label} (syntax {attempt + 1})", model_role="coder",
                                  budget=self.solo_budget, exclude=("git_commit",), vm_runner=self.vm_runner, self_check=self.self_check, history=compact_history(self.convo) if self.convo else None)
            self.tidy_files(before, s["instruction"])
            summary = (run["final"] or {}).get("summary")
            if summary: notes.append(f"- step {i} ({s['title']}): {str(summary)[:200]}")
            record = {"title": s["title"], "rounds": [{"round": 1, "coder": {"stopped_by": run["stopped_by"], "summary": summary}, "verdict": "unjudged"}], "accepted": True, "unjudged": True}
            if any(self.ws.status().values()): record["commit"] = self.ws.commit(s["title"][:60])
            self._audit("DEVVM_STEP", {"title": s["title"], "accepted": True, "rounds": 1, "mode": self.mode, "unjudged": True})
            records.append(record)
        return self._result(records, [s["title"] for s in steps], fallback, t0)

    def _rescue(self, run):
        """A solo run that ended WITHOUT a hand-in (round limit, cut answer, server error) may have stopped in the middle of a change: a Python file that does not parse is put back to the state of the last commit (or deleted if it is new),
        so that the next run, the rework and the acceptance test do not start on a broken file (am007 2026-10-10: a half-done change). Parsable files are never touched."""
        if run.get("stopped_by") == "hand_in": return
        for name, line, message in syntax_problems(self.ws):
            outcome = self.ws.restore_file(name)
            self.rescued.append({"file": name, "line": line, "message": message, "outcome": outcome, "after": run.get("stopped_by")})
            self.say(f"   rescue: {name} did not parse (line {line}: {message}) after a run that ended by {run.get('stopped_by')}: {outcome}")

    def _map_text(self):
        text = workspace_map(self.ws)
        return ("Map of the workspace (file, line, class or function):\n" + text + "\n") if text else ""

    def continue_solo(self, report, label="solo developer (continued)"):
        """After a failed acceptance test: the SAME developer continues his conversation (he remembers what he did) with the report of the failure. Long histories are shortened first. Without a conversation (the last run failed) or with the option
        fresh_rework a NEW conversation starts from the complete task, a map of the workspace and the report."""
        if not self.convo and not getattr(self, "solo_task", None): raise ValueError("no_solo_conversation")
        before = ws_snapshot(self.ws) if self.tidy else None
        keep = bool(self.convo) and not self.fresh_rework
        if keep: prompt = CONTINUE_PROMPT.format(report=report, again=SELF_CHECK[self.self_check]["again"]) + (f"\n\nThe complete task was:\n{self.solo_task}" if self.plan_steps else "")
        else: prompt = SOLO_PROMPT.format(task=self.solo_task, lessons=self._lesson_text(), check=SELF_CHECK[self.self_check]["prompt"]) + "\n\nYour earlier work is in the workspace.\n" + self._map_text() + "\n" + CONTINUE_PROMPT.format(report=report, again=SELF_CHECK[self.self_check]["again"])
        result = self._agent("solo", prompt, label, model_role="coder", budget=self.solo_budget, exclude=("git_commit",), vm_runner=self.vm_runner, self_check=self.self_check, history=compact_history(self.convo) if keep else None)
        self.tidy_files(before, "")
        if any(self.ws.status().values()): self.ws.commit("solo: continued after a failed acceptance test")
        return result

    def _result(self, records, plan_titles, fallback, t0):
        result = {"steps": records, "plan": plan_titles, "plan_fallback": fallback, "accepted": all(r["accepted"] for r in records), "seconds": round(self.clock() - t0, 1),
                  "mode": self.mode, "same_model": self.same_model, "subagents": self.subagents, "delegations": sum(r.get("delegations", 0) for r in self.runs), "lessons_used": len(self.lessons), "escalations": self.escalations,
                  "broken_checks": self.broken_checks, "dropped_checks": self.dropped_checks, "replans": self.replans, "rejected_checks": self.rejected_checks, "tidy": self.tidied, "rescued": self.rescued, "model_swaps": self.host.swaps,
                  "model_load_seconds": round(self.host.load_seconds, 1), "server_crashes": list(self.host.crashes), "agent_runs": self.runs}
        self._audit("DEVVM_RUN_DONE", {"accepted": result["accepted"], "steps": len(records), "agent_runs": len(self.runs), "seconds": result["seconds"], "swaps": result["model_swaps"], "mode": self.mode})
        return result

    def run(self, task, lessons=None):
        """`lessons`: texts of matching lessons from the knowledge base; only the first one is ever given to the developer (MAX_LESSONS)."""
        t0 = self.clock()
        self.lessons = [str(l) for l in (lessons or [])][:MAX_LESSONS]
        if self.mode == "escalating": return self._run_escalating(task, t0)
        if self.mode == "solo": return self._run_solo(task, t0)
        steps, fallback = self.plan(task)
        problems = [(i, check_problem(s["check"], self.ws)) for i, s in enumerate(steps, 1) if s.get("check") and self.vm_runner is not None]
        problems = [(i, p) for i, p in problems if p]
        if problems and not fallback:
            # a dropped check leaves only the reviewer as judge, and the small reviewer misses details: ask the planner ONCE for a corrected plan while its model is still loaded
            self.say("   plan: unusable checks (" + "; ".join(f"step {i}: {p}" for i, p in problems) + "), the planner is asked once more")
            note = ("\n\nYour previous plan had unusable checks: " + "; ".join(f"step {i}: {p}" for i, p in problems)
                    + ". Hand in the whole plan again. Every check must import the workspace code, only read, and assert the concrete examples of the task.")
            again, again_fallback = self.plan(task, note, "planner (retry)")
            if not again_fallback: steps, self.replans = again, self.replans + 1
        records = [self.step(task, s, i, len(steps)) for i, s in enumerate(steps, 1)]
        return self._result(records, [s["title"] for s in steps], fallback, t0)
