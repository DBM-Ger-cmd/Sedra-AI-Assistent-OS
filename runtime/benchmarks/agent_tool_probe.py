r"""Which tools does an agent really offer to the model? (Captain 2026-10-10: before a foreign agent works with a model, the list of tools that reaches the model must be known.)

    .venv\Scripts\python.exe benchmarks/agent_tool_probe.py qwen-code [--variant baseline|confined|both] [--install-dir <folder>]

No model and no GPU: a tiny fake OpenAI-compatible server on 127.0.0.1 answers every request with a short text ("ok", no tool call) and RECORDS the request. The agent is started headless with its own empty home folder, in an empty
working folder, with the fake server as its model. The `tools` array of the recorded request is what the model would be shown. Variants:
  baseline  the agent as it is (shows its built-in tools)
  confined  the agent with our configuration: its built-in file and shell tools denied, GUPPI's MCP server (`guppi_runtime.devvm_mcp --no-vm`) as the only tool source
The probe prints the tool names of each variant and whether the confined list contains only our tools. The agent process runs on this PC (Node); it gets no secrets, no project path and no real model, and it is stopped by its own PID.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
from guppi_runtime.local_paths import expand                                     # noqa: E402

DEFAULT_INSTALL = Path(expand(r"<projekte>\qwen-code-main\qwen-code-installed"))      # folders of this PC: runtime/config/local_paths.yaml
OUR_TOOLS = ("list_dir", "read_file", "outline", "write_file", "append_file", "edit_file", "make_dir", "move_file", "delete_file", "search_text", "diff_files", "check_syntax", "git_status", "git_log", "submit_result")
DISABLED = ["manage_memory", "search_memory", "cron_create", "cron_delete", "cron_list", "enter_worktree", "exit_worktree", "loop_wakeup", "read_mcp_resource", "record_artifact", "report_findings", "send_message", "task_stop", "get_goal", "update_goal", "list_agents",
            "propose_goal", "agent", "task", "skill", "tool_search", "tool_call", "enter_plan_mode", "exit_plan_mode", "ask_user_question", "todo_write", "web_fetch", "web_search", "run_shell_command", "read_file", "write_file", "edit", "glob",
            "grep_search", "list_directory", "notebook_edit"]
DENY = ["Bash", "Shell", "Read", "Edit", "Glob", "Grep", "ListFiles", "WebFetch", "WebSearch", "Agent", "Skill", "NotebookEdit"]


def tool_names(body):
    """The tool names of one recorded chat-completions request (OpenAI shape: tools[].function.name)."""
    return [((t.get("function") or {}).get("name") or t.get("name") or "?") for t in (body.get("tools") or [])]


def completion(model, stream):
    """The answer of the fake model: the text 'ok', no tool call."""
    if not stream:
        return {"id": "fake-1", "object": "chat.completion", "created": 0, "model": model, "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
    return None


def make_server(records, script=None):
    """The fake model server. With `script` (a list of (tool name, arguments)) it answers the first requests that carry tools with those tool calls, one per request, then with plain text."""
    state = {"step": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def do_GET(self):
            body = json.dumps({"object": "list", "data": [{"id": "fake-model", "object": "model"}]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try: body = json.loads(raw or b"{}")
            except ValueError: body = {}
            records.append({"path": self.path, "body": body})
            model, stream = body.get("model", "fake-model"), bool(body.get("stream"))
            if script and body.get("tools") and state["step"] < len(script):
                name, arguments = script[state["step"]]
                state["step"] += 1
                call = {"index": 0, "id": f"call_{state['step']}", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}
                if not stream:
                    data = json.dumps({"id": "fake-1", "object": "chat.completion", "created": 0, "model": model, "choices": [{"index": 0, "message": {"role": "assistant", "content": None, "tool_calls": [{k: v for k, v in call.items() if k != "index"}]}, "finish_reason": "tool_calls"}],
                                       "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache"); self.end_headers()
                first = {"id": "fake-1", "object": "chat.completion.chunk", "created": 0, "model": model, "choices": [{"index": 0, "delta": {"role": "assistant", "content": None, "tool_calls": [call]}, "finish_reason": None}]}
                last = {"id": "fake-1", "object": "chat.completion.chunk", "created": 0, "model": model, "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
                for chunk in (first, last): self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
                return
            if not stream:
                data = json.dumps(completion(model, False)).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache"); self.end_headers()
            chunks = [{"id": "fake-1", "object": "chat.completion.chunk", "created": 0, "model": model, "choices": [{"index": 0, "delta": {"role": "assistant", "content": "ok"}, "finish_reason": None}]},
                      {"id": "fake-1", "object": "chat.completion.chunk", "created": 0, "model": model, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}]
            for chunk in chunks: self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def qwen_settings(confined, python, project, work_root, *, vm=False, mission="M-MCP00001", attach=False, journal=None, result_file=None, self_check="full", max_vm_runs=None, model=None):
    """The `~/.qwen/settings.json` of the agent. `confined`: its built-in tools are denied and removed, the bridge to withheld tools is off and GUPPI's MCP server is the only tool source. `vm`: the server also offers run_python (in the microVM).
    `attach`: the workspace of `mission` under `work_root` exists already (the harness judges the same folder). `model`: settings for a REAL model server: {"alias", "context", "temperature", "max_turns", "max_tokens"} (None: the fake model of the probe)."""
    settings = {"security": {"auth": {"selectedType": "openai"}}, "model": {"name": "fake-model"}, "general": {"enableAutoUpdate": False}}
    if model:
        settings["model"] = {"name": model["alias"], "maxSessionTurns": int(model.get("max_turns", 40)),
                             "generationConfig": {"contextWindowSize": int(model["context"]), "timeout": 600000, "streamIdleTimeoutMs": 600000,
                                                  "samplingParams": {"temperature": float(model.get("temperature", 0.1)), "max_tokens": int(model.get("max_tokens", 8000))}}}
    if confined:
        names = list(OUR_TOOLS) + (["run_python"] if vm else [])
        settings["permissions"] = {"deny": DENY, "allow": [f"mcp__devvm__{name}" for name in names]}      # only OUR tools run without a question (non-interactive mode cannot ask)
        settings["tools"] = {"disabled": DISABLED, "visible": [f"mcp__devvm__{name}" for name in names], "toolSearch": {"enabled": False}}      # no bridge to withheld tools: ours are declared up front, the rest is not registered
        settings["goals"] = {"modelProposed": "disabled"}
        args = ["-m", "guppi_runtime.devvm_mcp", "--project", str(project), "--workspace-root", str(work_root), "--mission", mission, "--self-check", self_check]
        if attach: args.append("--attach")
        if not vm: args.append("--no-vm")
        if max_vm_runs is not None: args += ["--max-vm-runs", str(int(max_vm_runs))]
        if journal: args += ["--journal", str(journal)]
        if result_file: args += ["--result-file", str(result_file)]
        settings["mcpServers"] = {"devvm": {"command": python, "args": args, "env": {"PYTHONPATH": str(RUNTIME / "src")}, "timeout": 300000}}
    return settings


def run_qwen(install_dir, confined, project, timeout=150, script=None, prompt="Say ok.", settings=None, extra_args=()):
    """Starts Qwen Code headless against the fake server; returns {"tools": [[names of request 1], ...], "requests": n, "exit": code, "output": tail}."""
    records = []
    server = make_server(records, script)
    port = server.server_address[1]
    base = Path(tempfile.mkdtemp(prefix="agent_tool_probe_"))
    home, work, mcp_root = base / "home", base / "work", base / "mcp_workspace"
    (home / ".qwen").mkdir(parents=True); work.mkdir(); mcp_root.mkdir()
    (home / ".qwen" / "settings.json").write_text(json.dumps(settings if settings is not None else qwen_settings(confined, sys.executable, project, mcp_root), indent=1), encoding="utf-8")
    entry = Path(install_dir) / "node_modules" / "@qwen-code" / "qwen-code" / "cli-entry.js"
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "OPENAI_API_KEY": "noop", "OPENAI_BASE_URL": f"http://127.0.0.1:{port}/v1", "OPENAI_MODEL": "fake-model",
           "QWEN_CODE_NO_RELAUNCH": "1", "NO_COLOR": "1", "CI": "1"}
    proc = subprocess.Popen(["node", str(entry), "-p", prompt, "--output-format", "json", *extra_args], cwd=str(work), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)       # this child only
        out = "(timeout)"
    time.sleep(0.5)
    server.shutdown()
    chat = [r for r in records if r["path"].rstrip("/").endswith("/chat/completions")]
    return {"tools": [tool_names(r["body"]) for r in chat], "init_tools": init_tools(out or ""), "requests": len(chat), "exit": proc.returncode, "output": (out or "")[-600:], "folder": str(base), "work": str(work), "mcp_workspace": str(mcp_root),
            "tool_results": tool_results(chat[-1]["body"]) if chat else [], "first_body": chat[0]["body"] if chat else {}}


def init_tools(output):
    """The tools that the agent REGISTERED for the session, from the `system` / `init` event at the start of its JSON output (a tool can be registered without being declared in the first request, for example the memory tools)."""
    try:
        data = json.loads(output)
    except ValueError:
        start = str(output).find("[")
        try: data = json.loads(str(output)[start:]) if start >= 0 else []
        except ValueError: return []
    for item in data if isinstance(data, list) else [data]:
        if isinstance(item, dict) and item.get("type") == "system" and item.get("subtype") == "init":
            return [str(t) for t in (item.get("tools") or [])]
    return []


def all_tool_names(result):
    """Every tool the agent registered or declared in any request of the run (the union)."""
    names = set(result.get("init_tools") or [])
    for request in result.get("tools") or []:
        names |= set(request)
    return sorted(names)


def tool_results(body):
    """The texts of the tool results (role tool, or function responses) in a recorded request: what the agent told the model about each call."""
    out = []
    for m in body.get("messages") or []:
        if m.get("role") == "tool":
            c = m.get("content")
            out.append((" ".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else str(c))[:300])
        elif m.get("role") == "assistant" and m.get("tool_calls"):
            out.append("(call) " + ", ".join(str((c.get("function") or {}).get("name")) for c in m["tool_calls"]))
    return out


def judge(names):
    names = list(names)
    """(ours_only, foreign): the tool names a confined agent shows must all be ours (the MCP name may carry a prefix such as mcp__devvm__)."""
    foreign = [n for n in names if not any(n == o or n.endswith("__" + o) or n.endswith("_" + o) for o in OUR_TOOLS + ("run_python",))]
    return (not foreign), foreign


def attack(args):
    """The scripted fake model calls: (1) our write tool, (2) the shell, (3) the built-in write tool, (4) the built-in read tool, (5) our read tool with a path outside the workspace. Harmless marker files in a temp folder show what ran."""
    marker = Path(tempfile.mkdtemp(prefix="agent_attack_marker_"))
    shell_marker, write_marker = marker / "shell_ran.txt", marker / "builtin_write_ran.txt"
    script = [("mcp__devvm__write_file", {"path": "a.py", "content": "x = 1\n"}),
              ("run_shell_command", {"command": f'echo x > "{shell_marker}"', "is_background": False}),
              ("write_file", {"file_path": str(write_marker), "content": "x"}),
              ("read_file", {"absolute_path": str(Path(args.install_dir) / "package.json")}),
              ("mcp__devvm__read_file", {"path": "../../../../../../Windows/win.ini"})]
    result = run_qwen(args.install_dir, True, args.project, script=script, prompt="Please do the steps.")
    print(f"exit {result['exit']}, {result['requests']} request(s)")
    for i, text in enumerate(result["tool_results"], 1): print(f"  result {i}: {text[:160]!r}")
    a_py = Path(result["mcp_workspace"]).rglob("a.py")
    print("  our write_file created a.py in the MCP workspace:", any(True for _ in a_py))
    print("  shell marker exists (BAD if True):", shell_marker.exists())
    print("  built-in write marker exists (BAD if True):", write_marker.exists())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("agent", choices=["qwen-code"])
    ap.add_argument("--variant", choices=["baseline", "confined", "both", "attack"], default="both", help="attack: the fake model calls our tool and then tries denied tools (shell, built-in write and read); a marker file shows whether any of them ran")
    ap.add_argument("--install-dir", default=str(DEFAULT_INSTALL))
    ap.add_argument("--project", default=str(RUNTIME.parent / "workspace" / "GUPPI_OS"))
    args = ap.parse_args()
    if args.variant == "attack":
        attack(args)
        return
    for variant in (["baseline", "confined"] if args.variant == "both" else [args.variant]):
        result = run_qwen(args.install_dir, variant == "confined", args.project)
        first = all_tool_names(result)
        print(f"== {variant}: exit {result['exit']}, {result['requests']} request(s) to the fake model")
        print("   tools registered or offered to the model (union over the session start and all requests):", ", ".join(first) or "(none recorded)")
        if variant == "confined" and first:
            ours, foreign = judge(first)
            print("   ONLY OUR TOOLS" if ours else "   NOT CONFINED, foreign tools: " + ", ".join(foreign))
        if not first: print("   output:", result["output"].replace("\n", " | ")[-400:])


if __name__ == "__main__":
    main()
