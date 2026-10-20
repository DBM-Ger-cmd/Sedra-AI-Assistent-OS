"""MCP server for ONE DevVM workspace (Captain 2026-10-10: ready agents such as Qwen Code or little-coder may do the thinking, but the model may only see GUPPI's tools).

    python -m guppi_runtime.devvm_mcp --project <GUPPI project> [--seed <folder>] [--journal <file>] [--result-file <file>] [--max-vm-runs 8] [--self-check full|light|none] [--no-vm]

The server speaks MCP over stdio (JSON-RPC 2.0, one message per line, `initialize`, `tools/list`, `tools/call`, `ping`) and has no dependency outside the standard library. Every tool call goes through the DevToolBox of the solo developer, so the rules of the workspace hold
for any agent: paths only inside the workspace (no symlinks, depth and size limits), `write_file` does not replace a longer existing file, `edit_file` with `edits`, `read_file` in parts, `outline`, and `run_python` runs ONLY in the microVM (a copy of the workspace, never on the host).
`git_commit` is not offered; the caller commits and judges. What the server does NOT do: it does not show the hidden acceptance test, it does not start a model and it does not give out any file outside the workspace.

The agent side must remove its own file and shell tools (Qwen Code: `permissions.deny`), otherwise the model could bypass this server; see docs/MCP_SERVER_DEVVM.md.
Each call is appended to the journal file (tool, arguments without long texts, ok, milliseconds, error text): the data that the failure layers need.
"""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from .devenv.devvm import DevWorkspace
from .devenv.devvm_tools import READ_TOOLS, SELF_CHECK, DevToolBox

SERVER_NAME = "guppi-devvm"
SERVER_VERSION = "1.0.0"
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
POLICY = {"max_files": 60, "max_file_bytes": 60000, "max_input_bytes": 300000}
HANDED_IN = "The work is handed in and the task is over. Do not call any tool again; answer with one short sentence and stop."
INSTRUCTIONS = ("You work in one private workspace of GUPPI (a folder tree with git). All paths are relative to its root. Use these tools only. Read the task once, make small changes with edit_file (several changes at once with `edits`), "
                "write long new files in parts (write_file, then append_file), and hand in with submit_result. run_python runs a file in an isolated VM; there is no shell.")


def short_args(args):
    """The arguments for the journal: long texts are replaced by their length."""
    if not isinstance(args, dict): return {}
    return {k: (f"<{len(v)} chars>" if isinstance(v, str) and len(v) > 80 else v) for k, v in args.items() if k != "edits"} | ({"edits": f"<{len(args['edits'])} changes>"} if isinstance(args.get("edits"), list) else {})


class DevvmMcpServer:
    def __init__(self, ws, *, vm_runner=None, max_calls=120, max_seconds=3600, max_vm_runs=None, self_check="full", journal=None, result_file=None, clock=time.monotonic):
        self.ws, self.journal, self.result_file, self.clock = ws, journal, result_file, clock
        runs = SELF_CHECK[self_check]["vm_runs"] if max_vm_runs is None else max_vm_runs
        self.box = DevToolBox(ws, "solo", vm_runner=vm_runner, max_calls=max_calls, max_seconds=max_seconds, max_vm_runs=runs, exclude=("git_commit",), clock=clock, self_check=self_check)
        self.final = None
        self.calls = 0

    # ---- the tool list ---------------------------------------------------------------------------------------------------
    def tools(self):
        out = []
        for schema in self.box.schemas():
            fn = schema["function"]
            params = dict(fn["parameters"])
            params.setdefault("properties", {})
            out.append({"name": fn["name"], "description": fn["description"], "inputSchema": params,
                        "annotations": {"readOnlyHint": fn["name"] in READ_TOOLS, "destructiveHint": fn["name"] in ("delete_file", "move_file", "write_file", "edit_file"), "openWorldHint": False}})
        return out

    # ---- one message -------------------------------------------------------------------------------------------------------
    def handle(self, message):
        """The answer to one JSON-RPC message, or None for a notification."""
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None, "error": {"code": -32600, "message": "invalid request"}}
        method, ident, params = message["method"], message.get("id"), message.get("params") or {}
        if "id" not in message: return None                  # notifications (initialized, cancelled, ...) get no answer
        try:
            if method == "initialize":
                asked = params.get("protocolVersion") if isinstance(params, dict) else None
                return self._ok(ident, {"protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0], "capabilities": {"tools": {"listChanged": False}},
                                        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}, "instructions": INSTRUCTIONS})
            if method == "ping": return self._ok(ident, {})
            if method == "tools/list": return self._ok(ident, {"tools": self.tools()})
            if method == "tools/call": return self._call(ident, params)
        except Exception as exc:                              # a bug here must not end the server: the caller gets an error text
            return self._ok(ident, {"content": [{"type": "text", "text": f"error: {type(exc).__name__}: {str(exc)[:200]}"}], "isError": True})
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"method not found: {method}"}}

    @staticmethod
    def _ok(ident, result):
        return {"jsonrpc": "2.0", "id": ident, "result": result}

    def _call(self, ident, params):
        name, args = params.get("name"), params.get("arguments")
        if not isinstance(name, str) or name not in self.box.names:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": f"unknown tool: {name}"}}
        if args is not None and not isinstance(args, dict):
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": "arguments must be an object"}}
        started = self.clock()
        if self.final is not None:         # the work is handed in: no further tool does anything, and the answer says so
            self.calls += 1
            self._journal({"n": self.calls, "tool": name, "args": short_args(args), "ok": False, "ms": 0, "error": "after the hand-in"})
            return self._ok(ident, {"content": [{"type": "text", "text": "error: " + HANDED_IN}], "isError": True})
        text = self.box.call(name, args or {})
        ok = not text.startswith("error:")
        self.calls += 1
        if name == self.box.terminal and ok and self.box.final is not None:
            self._finish()
            text = HANDED_IN
        self._journal({"n": self.calls, "tool": name, "args": short_args(args), "ok": ok, "ms": round((self.clock() - started) * 1000), **({} if ok else {"error": text[:200]})})
        return self._ok(ident, {"content": [{"type": "text", "text": text}], "isError": not ok})

    def _finish(self):
        self.final = self.box.final
        if self.result_file:
            Path(self.result_file).write_text(json.dumps({"final": self.final, "calls": self.calls, "journal": self.box.journal[-1:]}, ensure_ascii=False), encoding="utf-8")

    def _journal(self, record):
        if not self.journal: return
        with open(self.journal, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"t": time.strftime("%H:%M:%S"), **record}, ensure_ascii=False) + "\n")

    # ---- the loop ---------------------------------------------------------------------------------------------------------
    def serve(self, stdin, stdout):
        for line in stdin:
            line = line.strip()
            if not line: continue
            try:
                message = json.loads(line)
            except ValueError:
                answer = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
            else:
                answer = [a for a in (self.handle(m) for m in message) if a is not None] if isinstance(message, list) else self.handle(message)
                if answer in (None, []): continue
            stdout.write(json.dumps(answer, ensure_ascii=False) + "\n")
            stdout.flush()


def build(args):
    """The workspace (seeded), the VM runner (only when asked for) and the server for the command line."""
    tool_root = Path(args.workspace_root) if args.workspace_root else Path(tempfile.mkdtemp(prefix="guppi_devvm_mcp_"))
    ws = DevWorkspace(tool_root, args.mission, policy=dict(POLICY))
    if not args.attach: ws.create()           # --attach: the caller made the workspace (the harness judges the same folder afterwards)
    if args.seed and not args.attach:
        for path in sorted(Path(args.seed).rglob("*")):
            rel = path.relative_to(args.seed).as_posix()
            if path.is_file() and rel != "NOTES.md": ws.write(rel, path.read_text(encoding="utf-8"))
    vm = None
    if not args.no_vm:
        from .selfdev.acceptance_vm import vm_runner
        runner = vm_runner(args.project, Path(__file__).resolve().parents[2], mission=args.mission)
        vm = lambda commands: runner({p: ws.read(p) for p in ws.tree()}, commands)
    return ws, DevvmMcpServer(ws, vm_runner=vm, max_calls=args.max_calls, max_seconds=args.max_seconds, max_vm_runs=args.max_vm_runs, self_check=args.self_check, journal=args.journal, result_file=args.result_file)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="the GUPPI project folder (the microVM backend lives under runtime_data/sandboxes)")
    ap.add_argument("--workspace-root", help="where the workspace is created (default: a new temporary folder)")
    ap.add_argument("--mission", default="M-MCP00001")
    ap.add_argument("--seed", help="a folder whose files are put into the workspace first")
    ap.add_argument("--attach", action="store_true", help="the workspace (--workspace-root, --mission) exists already: use it as it is")
    ap.add_argument("--journal", help="a file that gets one JSON line per tool call")
    ap.add_argument("--result-file", help="a file that gets the hand-in (submit_result) as JSON")
    ap.add_argument("--max-calls", type=int, default=120)
    ap.add_argument("--max-seconds", type=int, default=3600)
    ap.add_argument("--max-vm-runs", type=int, default=None)
    ap.add_argument("--self-check", choices=sorted(SELF_CHECK), default="full")
    ap.add_argument("--no-vm", action="store_true", help="run_python is not available")
    args = ap.parse_args(argv)
    ws, server = build(args)
    print(f"{SERVER_NAME}: workspace {ws.work}", file=sys.stderr, flush=True)
    stdin = open(sys.stdin.fileno(), "r", encoding="utf-8", newline="\n", closefd=False)
    stdout = open(sys.stdout.fileno(), "w", encoding="utf-8", newline="\n", closefd=False)
    server.serve(stdin, stdout)


if __name__ == "__main__":
    main()
