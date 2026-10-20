r"""Qwen Code in the stage loop of the DevVM build (Captain 2026-10-10: a ready agent against our solo developer, same model, same server, same workspace, same hidden test).

    .venv\Scripts\python.exe benchmarks/qwen_build.py <project_dir> --spec bench_std [--only <stage>] [--seed <folder>] [--rework 3] [--self-check none|light|full] [--context 32768] [--coder coder.local_primary]
    .venv\Scripts\python.exe benchmarks/qwen_build.py <project_dir> --spec bench_std --fake-model        # rehearsal without GPU: the model is a scripted fake, everything else is real

What runs where:
  - the model: GUPPI's llama-server (GPU lease held) - or, with --fake-model, a scripted fake on 127.0.0.1;
  - the agent: Qwen Code (Node, installed in its own folder) headless, in an EMPTY working folder, with its own empty home, no secrets; its built-in tools are denied and removed and the bridge to withheld tools is off: the model sees ONLY the
    tools of GUPPI's MCP server (`guppi_runtime.devvm_mcp`, attached to the workspace of this run); `run_python` (only with --self-check light|full) runs in the microVM;
  - the judge: the hidden acceptance test of the stage in the microVM, as in devvm_build.py; a failed stage gets the readable bug report in a rework that CONTINUES the session (`--continue`).
BEFORE every run the tool list that the agent shows to the model is recorded with a fake model and compared with ours (agent_tool_probe); any other tool stops the whole run (exit 3). Results go to the same files as devvm_build.py
(`devvm_build_<spec>_*.json/.log`, mode column "qwen-code"), the candidate to runtime_data/devvm_candidates, a snapshot after every passed stage to runtime_data/devvm_snapshots.
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(RUNTIME / "benchmarks"))

import agent_tool_probe as probe                                                      # noqa: E402

EXIT_NOT_CONFINED = 3


def qwen_command(node, entry, prompt, continue_session=False, system_mode="asis", system_text=""):
    """The headless call of Qwen Code (JSON output); a rework continues the session of the stage. system_mode: asis (its own system prompt), append (ours added to it), lean (ours instead of its own: it is about 5,000 tokens)."""
    cmd = [node, str(entry), "-p", prompt, "--output-format", "json"]
    if system_mode == "append": cmd += ["--append-system-prompt", system_text]
    elif system_mode == "lean": cmd += ["--system-prompt", system_text]
    if continue_session: cmd.append("--continue")
    return cmd


def our_system_text(self_check):
    """The system text of our solo developer (the same words, the check clause of the chosen way)."""
    from guppi_runtime.devenv.devvm_tools import SELF_CHECK, SYSTEM
    text = SYSTEM["solo"]
    if self_check != "full": text = text.replace(SELF_CHECK["full"]["system"], SELF_CHECK[self_check]["system"])
    return text


def qwen_env(home, base_url, alias, base=None):
    """The environment of the agent: its own home (settings, sessions, caches), the model server, no other secret. The key is a dummy."""
    env = dict(base if base is not None else os.environ)
    for key in [k for k in env if "KEY" in k.upper() or "TOKEN" in k.upper() or "SECRET" in k.upper() or k.upper().startswith(("OPENAI", "ANTHROPIC", "DASHSCOPE", "GEMINI", "GOOGLE"))]:
        env.pop(key)                                       # nothing of the PC's own credentials reaches the agent
    env.update({"HOME": str(home), "USERPROFILE": str(home), "OPENAI_API_KEY": "noop", "OPENAI_BASE_URL": base_url, "OPENAI_MODEL": alias, "NO_COLOR": "1", "CI": "1"})
    return env


def read_journal(path):
    """({tool: calls}, number of calls, number of failed calls) from the journal of the MCP server of one run."""
    counts, failed = {}, 0
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            counts[row["tool"]] = counts.get(row["tool"], 0) + 1
            failed += 0 if row.get("ok", True) else 1
    except (OSError, ValueError):
        pass
    return counts, sum(counts.values()), failed


def parse_qwen_output(text):
    """Numbers from the JSON output of `qwen -p ... --output-format json`: {"completion_tokens", "prompt_tokens", "cached_tokens", "turns", "result"}. The final `result` event carries the usage of the WHOLE run; the usage of the single
    `assistant` events is only used when there is no result event (adding both counted every token twice in the runs of 2026-10-10 until 17:40). Unknown shapes give zeros."""
    out = {"completion_tokens": 0, "prompt_tokens": 0, "cached_tokens": 0, "turns": 0, "result": ""}
    try:
        data = json.loads(text)
    except ValueError:
        start = str(text).find("[")
        try: data = json.loads(str(text)[start:]) if start >= 0 else []
        except ValueError: return out
    items = [i for i in (data if isinstance(data, list) else [data]) if isinstance(i, dict)]
    per_event = {"completion_tokens": 0, "prompt_tokens": 0, "cached_tokens": 0}
    whole = None
    for item in items:
        usage = item.get("usage") or (item.get("message") or {}).get("usage") or {}
        got = {"completion_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0) if isinstance(usage, dict) else 0,
               "prompt_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0) if isinstance(usage, dict) else 0,
               "cached_tokens": int(usage.get("cache_read_input_tokens") or 0) if isinstance(usage, dict) else 0}
        if item.get("type") == "result" and any(got.values()): whole = got
        elif item.get("type") != "result":
            for key in per_event: per_event[key] += got[key]
        if item.get("type") == "assistant": out["turns"] += 1
        if item.get("type") == "result": out["result"] = str(item.get("result") or "")[:300]
    out.update(whole or per_event)
    return out


def stop_reason(returncode, timed_out, handed_in):
    """Why the run ended, in the words of the failure layers: hand_in (the agent called submit_result), time, error (non-zero exit), no_tool_call (it ended without handing in)."""
    if handed_in: return "hand_in"
    if timed_out: return "time"
    if returncode not in (0, None): return "error"
    return "no_tool_call"


def expected_names(vm):
    return sorted(list(probe.OUR_TOOLS) + (["run_python"] if vm else []))


def tools_are_confined(names, vm):
    """True when the tools shown to the model are exactly ours (MCP prefix allowed) and nothing else."""
    ours, foreign = probe.judge(names)
    shown = sorted(n.split("__")[-1] if n.startswith("mcp__") else n for n in names)
    return ours and shown == expected_names(vm), foreign


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--spec", default="bench_std")
    ap.add_argument("--only")
    ap.add_argument("--seed")
    ap.add_argument("--rework", type=int, default=3)
    ap.add_argument("--self-check", choices=["none", "light", "full"], default="none")
    ap.add_argument("--context", default="32768")
    ap.add_argument("--coder", default=None, help="model key (default: the standard coder)")
    ap.add_argument("--reasoning", default="off")
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--max-turns", type=int, default=40, help="Qwen Code: maximum model/tool turns per session")
    ap.add_argument("--max-seconds", type=int, default=1200, help="per run of the agent")
    ap.add_argument("--install-dir", default=str(probe.DEFAULT_INSTALL))
    ap.add_argument("--system", choices=["asis", "append", "lean"], default="asis", help="asis: Qwen Code's own system prompt; append: ours added; lean: ours instead of its own (saves about 5,000 tokens of the window)")
    ap.add_argument("--fake-model", action="store_true", help="rehearsal: a scripted fake model instead of the GPU")
    ap.add_argument("--skip-preflight", action="store_true", help="NOT for real runs")
    args = ap.parse_args()

    import devvm_agents_bench as bench
    from devvm_build import DEFAULT_MODEL, acceptance, export_snapshot, hidden_report, without_test_duty
    from guppi_runtime.devenv.devvm import DevWorkspace
    from guppi_runtime.devenv.devvm_agents import CONTINUE_PROMPT, SOLO_PROMPT
    from guppi_runtime.devenv.devvm_tools import SELF_CHECK
    from guppi_runtime.jobs.run_log import RunLog
    from guppi_runtime.sandbox.broker import SandboxBroker
    from guppi_runtime.sandbox.provider import MicrosandboxProvider

    project = Path(args.project)
    if args.spec == "bench_std" and not args.seed: args.seed = str(RUNTIME / "benchmarks" / "bench_std_seed")      # the standard test needs its seed files (util.py, main.py, ledger.py); the first Qwen Code runs of 2026-10-10 had none (see docs/QWEN_ANSCHLUSS)
    vm = args.self_check != "none"
    spec = importlib.import_module(f"devvm_specs.{args.spec}")
    log = RunLog(project / "runtime_data" / "measurements", f"devvm_build_{args.spec}", config={"spec": args.spec, "attempts": 1, "agent": "qwen-code"})
    log_stamp = time.strftime("%Y%m%d_%H%M%S")
    tool_root = Path(tempfile.mkdtemp(prefix="guppi_qwen_build_"))
    entry = Path(args.install_dir) / "node_modules" / "@qwen-code" / "qwen-code" / "cli-entry.js"
    if not entry.is_file():
        print(f"Qwen Code is not installed at {entry}", file=sys.stderr)
        sys.exit(2)

    with log:
        # ---- 1. the tool list that reaches the model must be exactly ours -------------------------------------------------------------
        if not args.skip_preflight:
            settings = probe.qwen_settings(True, sys.executable, project, tool_root / "preflight_ws", vm=vm, mission="M-PREFLT01", self_check=args.self_check)
            shown = probe.run_qwen(args.install_dir, True, project, settings=settings)
            names = probe.all_tool_names(shown)           # registered at the start of the session AND declared in any request
            confined, foreign = tools_are_confined(names, vm)
            log.say(f"   preflight: tools shown to the model: {', '.join(names) or '(none)'}")
            if not confined:
                log.say(f"   PREFLIGHT FAILED: the agent is NOT confined (foreign: {', '.join(foreign) or 'tool list differs'}). Nothing was started.")
                sys.exit(EXIT_NOT_CONFINED)
            log.say("   preflight: ONLY OUR TOOLS")

        # ---- 2. the judge: microVM copy of the workspace -------------------------------------------------------------------------------
        cfg_path = tool_root / "sandbox-build.yaml"
        cfg_path.write_text((RUNTIME / "config" / "sandbox.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        broker = SandboxBroker(tool_root, tool_root / "sandbox-data", cfg_path, MicrosandboxProvider(project / "runtime_data" / "sandboxes" / "backend_home", RUNTIME), None, None)
        counter = {"n": 0}

        def vm_copy(ws, commands, extra):
            counter["n"] += 1
            copy = DevWorkspace(tool_root, f"M-CHK{counter['n']:05d}", policy=broker.policy()); copy.create()
            for path in ws.tree(): copy.write(path, ws.read(path))
            for path, text in extra.items(): copy.write(path, text)
            try:
                out = broker._run("M-BUILD", copy.vm_preview(broker, commands))
            except Exception as exc:
                return {"status": "failed", "output": f"{type(exc).__name__}: {exc}"}
            rec = out.get("sandbox") or {}
            return {"status": out["status"], "output": "\n".join(c.get("output", "") for c in rec.get("commands", []))}

        # ---- 3. the model server ---------------------------------------------------------------------------------------------------------
        server_handle, loader, runtime, lease = None, None, None, None
        if args.fake_model:
            records = []
            script = [("mcp__devvm__write_file", {"path": "rehearsal.py", "content": "x = 1\n"}), ("mcp__devvm__submit_result", {"summary": "rehearsal"})] * 6
            server_handle = probe.make_server(records, script)
            endpoint, alias, context = f"http://127.0.0.1:{server_handle.server_address[1]}", "fake-model", int(args.context)
        else:
            from guppi_runtime.models.gpu_preflight import clear_leftovers
            from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
            from guppi_runtime.jobs.testlab import TestLab, default_path
            config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
            runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_qwen_build_rt_")))
            key = args.coder or DEFAULT_MODEL
            loader = bench.BenchLoader(runtime, project, {"coder": key}, log, context=int(args.context), server_extra={"reasoning": args.reasoning})
            lease = TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "qwen_build"), f"qwen build {args.spec}", ttl_s=1800, wait_s=36000, preflight=clear_leftovers)
            lease.__enter__()
            alias, _, _ = loader.load(key)
            endpoint, context = runtime.endpoint, loader.window(loader.specs[key])
        try:
            ws = DevWorkspace(tool_root, "M-QWEN001", policy=broker.policy()); ws.create()
            ws.write("NOTES.md", spec.NOTES)
            if args.seed:
                for f in sorted(Path(args.seed).rglob("*")):
                    rel = f.relative_to(args.seed).as_posix()
                    if f.is_file() and rel != "NOTES.md": ws.write(rel, f.read_text(encoding="utf-8"))
            home = tool_root / "qwen_home"; (home / ".qwen").mkdir(parents=True)
            work = tool_root / "qwen_cwd"; work.mkdir()
            runs, stage_rows, run_no = [], [], {"n": 0}
            t0 = time.monotonic()

            def run_agent(prompt, label, continue_session):
                run_no["n"] += 1
                journal, result_file = tool_root / f"journal_{run_no['n']}.jsonl", tool_root / f"result_{run_no['n']}.json"
                settings = probe.qwen_settings(True, sys.executable, project, tool_root, vm=vm, mission="M-QWEN001", attach=True, journal=journal, result_file=result_file, self_check=args.self_check,
                                               model={"alias": alias, "context": context, "temperature": args.temperature, "max_turns": args.max_turns})
                (home / ".qwen" / "settings.json").write_text(json.dumps(settings, indent=1), encoding="utf-8")
                started, timed_out = time.monotonic(), False
                proc = subprocess.Popen(qwen_command("node", entry, prompt, continue_session, args.system, our_system_text(args.self_check)), cwd=str(work), env=qwen_env(home, endpoint.rstrip("/") + "/v1", alias), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace")
                try:
                    text, _ = proc.communicate(timeout=args.max_seconds)
                except subprocess.TimeoutExpired:
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)       # this child only, by its PID
                    timed_out = True
                    try: text, _ = proc.communicate(timeout=20)
                    except Exception: text = ""
                seconds = round(time.monotonic() - started, 1)
                counts, calls, failed = read_journal(journal)
                info = parse_qwen_output(text or "")
                stopped = stop_reason(proc.returncode, timed_out, result_file.exists())
                (tool_root / f"qwen_output_{run_no['n']}.txt").write_text(text or "", encoding="utf-8")
                run = {"label": label, "model": alias, "stopped_by": stopped, "calls": calls, "seconds": seconds, "completion_tokens": info["completion_tokens"], "prompt_tokens": info["prompt_tokens"], "prompt_peak": 0,
                       "tool_counts": counts, "nudges": 0, "failed_calls": failed}
                runs.append(run)
                log.say(f"   agent {label:22s} {alias:22s} {stopped:11s} {calls:2d} calls {seconds:6.1f} s {info['completion_tokens']} tokens, {info['prompt_tokens']} prompt, peak 0"
                        + (f"  error: {(text or '')[-200:]}" if stopped == "error" else ""))
                if any(ws.status().values()): ws.commit(label)

            stages = getattr(spec, "STAGES", None) or [{"name": "all", "task": spec.TASK, "hidden": spec.HIDDEN}]
            if args.only: stages = [s for s in stages if s["name"] == args.only]
            check_clause = SELF_CHECK[args.self_check]
            for stage in stages:
                task = without_test_duty(stage["task"])
                s0 = time.monotonic()
                run_agent(SOLO_PROMPT.format(task=task, lessons="", check=check_clause["prompt"]) + " Your tools come from the devvm server; hand in with its submit_result tool.", "qwen-code", False)
                check = acceptance(vm_copy, ws, stage)
                reworks = 0
                while check["status"] != "completed" and reworks < args.rework:
                    reworks += 1
                    report = hidden_report(vm_copy, ws, stage) or check["output"][-1500:]
                    run_agent(CONTINUE_PROMPT.format(report=report, again=check_clause["again"]), f"qwen-code (rework {reworks})", True)
                    check = acceptance(vm_copy, ws, stage)
                passed = check["status"] == "completed"
                if passed:
                    try: export_snapshot(ws, project, args.spec, log_stamp, stage["name"])
                    except Exception as exc: log.say(f"   snapshot of {stage['name']} failed: {type(exc).__name__}")
                seconds = round(time.monotonic() - s0, 1)
                stage_rows.append({"stage": stage["name"], "hidden_passed": passed, "own_check_accepted": None, "unjudged": [True], "escalations": 0, "reworks": reworks, "seconds": seconds, "hidden_output": check["output"][-600:],
                                   "own_tests": {"present": False, "passed": None, "output": ""}})
                log.say(f"   stage {stage['name']}: hidden {'PASSED' if passed else 'FAILED'} (own check accepted=UNJUDGED, own tests none, {seconds} s)")
            seconds = round(time.monotonic() - t0, 1)
            ok = bool(stage_rows) and all(r["hidden_passed"] for r in stage_rows)
            files = {p: ws.read(p) for p in ws.tree()}
            target = project / "runtime_data" / "devvm_candidates" / args.spec / f"attempt_01_{time.strftime('%Y%m%d_%H%M%S')}"
            for path, text in files.items():
                (target / path).parent.mkdir(parents=True, exist_ok=True); (target / path).write_text(text, encoding="utf-8")
            row = {"attempt": 1, "hidden_passed": ok, "stages": stage_rows, "hidden_output": stage_rows[-1]["hidden_output"][-1500:] if stage_rows else "", "own_check_accepted": None, "rejected_checks": [], "unjudged": [True] * len(stage_rows),
                   "coder": args.coder or "fake", "models": {"coder": alias}, "mode": "solo", "agent": "qwen-code", "self_check": args.self_check, "system_prompt": args.system, "plan_steps": False, "fresh_rework": False, "step_syntax_check": False, "rescued": [], "seconds": seconds,
                   "escalations": 0, "agent_runs": len(runs), "agent_detail": runs, "calls": sum(r["calls"] for r in runs), "swaps": 0, "files": sorted(files), "exported_to": str(target), "server_crashes": [], "agent_errors": [], "context": args.context}
            log.save({"spec": args.spec, "attempts": [row]})
            log.say(f"attempt 1: hidden test {'PASSED' if ok else 'FAILED'} | own check accepted=UNJUDGED | {seconds} s, {len(runs)} agent runs, {row['calls']} calls -> {target}")
        finally:
            if server_handle is not None: server_handle.shutdown()
            if loader is not None:
                try: loader.unload()
                except Exception: pass
            if lease is not None: lease.__exit__(None, None, None)
        log.say(f"DONE -> {log.json_path.name}")


if __name__ == "__main__":
    main()
