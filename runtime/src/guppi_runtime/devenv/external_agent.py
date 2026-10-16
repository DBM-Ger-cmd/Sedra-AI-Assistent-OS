"""An external coding agent in the stage loop of the DevVM build (Captain 2026-10-10: before more modules are built, measure whether a ready agent does better with the same model, the same workspace and the same judge).

`LittleCoderTeam` has the small interface of `DevOrchestrator` that `benchmarks/devvm_build.py` uses (`run`, `continue_solo`, `tidy_files`) and runs little-coder (the `pi` runtime with its extensions, Apache-2.0, installed in its own folder) headless in the folder of
the DevWorkspace. What stays ours: the workspace (git, size limits), the model server (llama.cpp through GUPPI's runtime, the GPU lease), the hidden acceptance test in the microVM, the measurement files.

Safety: the agent gets FILE tools only (`--tools read,write,edit,grep,find,glob`: no `bash`), runs with its working folder inside the workspace, its own home and session folder under `home_dir`, no update check, no network start-up (`--offline`).
Its file tools are not confined to the workspace by little-coder itself: the run is short, local and the task names only workspace files, but it is NOT the microVM. Files the broker would refuse (other types, caches) are removed after every run.
The process is stopped by its own PID (tree) on a timeout, never by name.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

ALLOWED_SUFFIXES = (".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv", ".js", ".css", ".html")
TOOLS = "read,write,edit,grep,find,glob"
MODEL_ID_RE = re.compile(r"[A-Za-z0-9_.\-]{1,80}")


def models_file(endpoint, alias, context, max_tokens=4096):
    """The `models.json` that points little-coder at GUPPI's llama-server."""
    return {"default": f"llamacpp/{alias}", "providers": {"llamacpp": {"api": "openai-completions", "baseUrl": endpoint.rstrip("/") + "/v1", "apiKey": "LLAMACPP_API_KEY",
            "models": [{"id": alias, "name": alias, "reasoning": True, "input": ["text"], "contextWindow": int(context), "maxTokens": int(max_tokens),
                        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}}]}}}


def child_env(home_dir, models_path, max_turns, thinking_budget=None, base=None):
    """The environment of the child: its own home and cache, the models file, no update check."""
    home = Path(home_dir)
    env = dict(base if base is not None else os.environ)
    env.update({"PI_CODING_AGENT_DIR": str(home / "agent"), "PI_SKIP_VERSION_CHECK": "1", "PI_OFFLINE": "1", "LITTLE_CODER_MODELS_FILE": str(models_path), "LLAMACPP_API_KEY": "noop",
                "LITTLE_CODER_MAX_TURNS": str(int(max_turns)), "XDG_CACHE_HOME": str(home / "cache"), "XDG_CONFIG_HOME": str(home / "config"), "HOME": str(home), "USERPROFILE": str(home)})
    if thinking_budget: env["LITTLE_CODER_THINKING_BUDGET"] = str(int(thinking_budget))
    return env


def command_line(node, launcher, prompt, alias, session_dir, tools=TOOLS, continue_session=False):
    if not MODEL_ID_RE.fullmatch(alias): raise ValueError("bad_model_alias")
    cmd = [node, str(launcher), "-p", prompt, "--mode", "json", "--tools", tools, "--provider", "llamacpp", "--model", alias, "--session-dir", str(session_dir), "--offline", "--no-context-files"]
    if continue_session: cmd.append("--continue")
    return cmd


def parse_events(text):
    """Best-effort counts from the JSON lines of `--mode json`: {"events", "tool_calls": {name: n}, "completion_tokens", "prompt_tokens", "errors"}. Unknown shapes count as events only."""
    out = {"events": 0, "tool_calls": {}, "completion_tokens": 0, "prompt_tokens": 0, "errors": 0}
    for line in str(text).splitlines():
        line = line.strip()
        if not line.startswith("{"): continue
        try: event = json.loads(line)
        except ValueError: continue
        out["events"] += 1
        kind = str(event.get("type") or "")
        if kind in ("tool_execution_start", "tool_call", "toolcall_start") or (kind == "tool_execution_start"):
            name = str(event.get("toolName") or event.get("name") or (event.get("toolCall") or {}).get("name") or "?")
            out["tool_calls"][name] = out["tool_calls"].get(name, 0) + 1
        usage = event.get("usage") or (event.get("message") or {}).get("usage") or {}
        if isinstance(usage, dict) and kind in ("message_end", "turn_end", "agent_end", "message"):
            out["completion_tokens"] += int(usage.get("output") or usage.get("completion_tokens") or 0)
            out["prompt_tokens"] += int(usage.get("input") or usage.get("prompt_tokens") or 0)
        if "error" in kind or event.get("isError") is True: out["errors"] += 1
    return out


def clean_workspace(ws):
    """Removes what the broker refuses for the VM (caches, hidden folders, other file types, half-written temp files) after the agent ran; returns the removed paths."""
    root = Path(ws.work)
    removed = []
    for path in sorted(root.rglob("*"), key=lambda p: (-len(p.parts), str(p))):
        rel = path.relative_to(root).as_posix()
        hidden = any(part.startswith(".") or part in ("__pycache__", "node_modules") for part in rel.split("/"))
        if path.is_file():
            if hidden or not rel.lower().endswith(ALLOWED_SUFFIXES):
                path.unlink(missing_ok=True); removed.append(rel)
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return removed


def kill_tree(pid):
    """Stops ONE process tree by its own PID (the child this module started), never anything else."""
    subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True)


class LittleCoderTeam:
    def __init__(self, ws, host, *, endpoint, alias, context, repo, home_dir, say=print, node="node", max_seconds=1200, max_turns=40, thinking_budget=None, tools=TOOLS, popen=subprocess.Popen, kill=kill_tree, clock=time.monotonic):
        self.ws, self.host, self.say, self.node = ws, host, say, node
        self.endpoint, self.alias, self.context = endpoint, alias, context
        self.launcher = Path(repo) / "bin" / "little-coder.mjs"
        self.home = Path(home_dir); self.home.mkdir(parents=True, exist_ok=True)
        self.max_seconds, self.max_turns, self.thinking_budget, self.tools = max_seconds, max_turns, thinking_budget, tools
        self.popen, self.kill, self.clock = popen, kill, clock
        self.runs, self.rejected_checks = [], []
        self.mode, self.session_dir = "little-coder", self.home / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.models_path = self.home / "models.json"

    def _run(self, prompt, label, continue_session=False, model_key=None):
        if model_key and self.host is not None: self.host.use(model_key)       # the model server of the run is loaded and holds the GPU
        self.models_path.write_text(json.dumps(models_file(self.endpoint, self.alias, self.context), indent=1), encoding="utf-8")
        cmd = command_line(self.node, self.launcher, prompt, self.alias, self.session_dir, self.tools, continue_session)
        started = self.clock()
        proc = self.popen(cmd, cwd=str(self.ws.work), env=child_env(self.home, self.models_path, self.max_turns, self.thinking_budget), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        stopped = "hand_in"
        try:
            text, _ = proc.communicate(timeout=self.max_seconds)
        except subprocess.TimeoutExpired:
            self.kill(proc.pid)
            try: text, _ = proc.communicate(timeout=20)
            except Exception: text = ""
            stopped = "time"
        seconds = round(self.clock() - started, 1)
        if stopped == "hand_in" and proc.returncode not in (0, None): stopped = "error"
        info = parse_events(text or "")
        if stopped == "hand_in" and info["events"] == 0: stopped = "error"
        log_dir = self.home / "logs"; log_dir.mkdir(exist_ok=True)
        (log_dir / f"{len(self.runs) + 1:03d}_{re.sub(r'[^A-Za-z0-9]+', '_', label)}.jsonl").write_text(text or "", encoding="utf-8")
        removed = clean_workspace(self.ws)
        run = {"role": "external", "model": self.alias, "label": label, "stopped_by": stopped, "calls": sum(info["tool_calls"].values()), "turns": info["events"], "seconds": seconds,
               "completion_tokens": info["completion_tokens"], "prompt_tokens": info["prompt_tokens"], "prompt_peak": 0, "tool_counts": info["tool_calls"], "nudges": 0, "final": {"summary": "little-coder"} if stopped == "hand_in" else None,
               "error": (text or "")[-300:] if stopped == "error" else None, "removed_files": removed}
        self.runs.append(run)
        self.say(f"   agent {label:22s} {self.alias:22s} {stopped:11s} {run['calls']:2d} calls {seconds:6.1f} s {run['completion_tokens']} tokens, {run['prompt_tokens']} prompt, peak 0" + (f"  error: {run['error'][:200]}" if run["error"] else ""))
        return run

    def run(self, task, lessons=None, model_key=None):
        t0 = self.clock()
        prompt = task + (("\n\n" + str(lessons[0])) if lessons else "")
        run = self._run(prompt, "little-coder", model_key=model_key)
        if any(self.ws.status().values()): self.ws.commit("task")
        return self._result([run], t0)

    def continue_solo(self, report, label="little-coder (rework)"):
        run = self._run("The independent acceptance test does NOT pass yet (you do not see the test, only this report of its first failing checks):\n" + report
                        + "\n\nFind the cause in your code, fix it with small edits and keep everything that already works.", label, continue_session=True)
        if any(self.ws.status().values()): self.ws.commit("little-coder: continued after a failed acceptance test")
        return run

    def tidy_files(self, before, task):
        return None

    def _result(self, runs, t0):
        return {"steps": [{"title": "task", "unjudged": True}], "plan": ["task"], "plan_fallback": False, "accepted": True, "seconds": round(self.clock() - t0, 1), "mode": self.mode, "same_model": True, "subagents": 0, "delegations": 0,
                "lessons_used": 0, "escalations": 0, "broken_checks": 0, "dropped_checks": 0, "replans": 0, "rejected_checks": [], "tidy": 0, "rescued": [], "model_swaps": 0, "agent_runs": list(runs)}
