import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.devenv.devvm import DevWorkspace  # noqa: E402
from guppi_runtime.devvm_mcp import POLICY, DevvmMcpServer, short_args  # noqa: E402


def rpc(method, params=None, ident=1):
    return {"jsonrpc": "2.0", "id": ident, "method": method, **({"params": params} if params is not None else {})}


class McpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = DevWorkspace(Path(self.tmp.name), "M-MCP0001", policy=dict(POLICY)); self.ws.create()
        self.journal = Path(self.tmp.name) / "journal.jsonl"
        self.result = Path(self.tmp.name) / "result.json"
        self.vm_calls = []

        def vm(commands):
            self.vm_calls.append(commands)
            return {"status": "completed", "output": "ran in the vm"}
        self.server = DevvmMcpServer(self.ws, vm_runner=vm, journal=self.journal, result_file=self.result, max_vm_runs=2)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, name, arguments=None, ident=2):
        return self.server.handle(rpc("tools/call", {"name": name, "arguments": arguments or {}}, ident))

    def text(self, response):
        return response["result"]["content"][0]["text"], response["result"]["isError"]

    def test_the_handshake_and_the_tool_list(self):
        init = self.server.handle(rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}))
        self.assertEqual((init["result"]["protocolVersion"], init["result"]["serverInfo"]["name"]), ("2025-03-26", "guppi-devvm"))
        self.assertIn("tools", init["result"]["capabilities"])
        self.assertEqual(self.server.handle(rpc("initialize", {"protocolVersion": "1999-01-01"}))["result"]["protocolVersion"], "2025-06-18")
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertEqual(self.server.handle(rpc("ping"))["result"], {})
        tools = {t["name"]: t for t in self.server.handle(rpc("tools/list"))["result"]["tools"]}
        for name in ("read_file", "outline", "write_file", "append_file", "edit_file", "delete_file", "search_text", "run_python", "submit_result", "git_status"):
            self.assertIn(name, tools)
        for name in ("git_commit", "run_tests", "delegate", "shell", "bash"):
            self.assertNotIn(name, tools)
        self.assertEqual(tools["edit_file"]["inputSchema"]["type"], "object")
        self.assertIn("edits", tools["edit_file"]["inputSchema"]["properties"])
        self.assertTrue(tools["read_file"]["annotations"]["readOnlyHint"])
        self.assertIn("properties", tools["git_status"]["inputSchema"])

    def test_the_rules_of_the_workspace_hold_for_every_agent(self):
        self.assertFalse(self.text(self.call("write_file", {"path": "a.py", "content": "".join(f"x{i} = {i}\n" for i in range(20))}))[1])
        text, is_error = self.text(self.call("write_file", {"path": "a.py", "content": "y = 1\n"}))
        self.assertTrue(is_error)
        self.assertIn("write_file refused", text)
        out, is_error = self.text(self.call("edit_file", {"path": "a.py", "edits": [{"old": "x0 = 0", "new": "x0 = 10"}, {"old": "x19 = 19", "new": "x19 = 190"}]}))
        self.assertFalse(is_error)
        self.assertIn("2 changes", out)
        self.call("write_file", {"path": "m.py", "content": "def f(a):\n    return a\n"})
        self.assertIn("def f(a)", self.text(self.call("outline", {"path": "m.py"}))[0])
        for bad in ("../outside.py", "/etc/passwd", "a/../../b.py"):
            self.assertTrue(self.text(self.call("read_file", {"path": bad}))[1], bad)
        self.assertTrue(self.text(self.call("write_file", {"path": "evil.exe", "content": "x"}))[1])

    def test_run_python_goes_to_the_vm_and_is_limited(self):
        self.ws.write("check_a.py", "print(1)\n")
        out, is_error = self.text(self.call("run_python", {"path": "check_a.py"}))
        self.assertFalse(is_error)
        self.assertIn("ran in the vm", out)
        self.assertEqual(self.vm_calls[0], [["python3", "check_a.py"]])
        self.call("run_python", {"path": "check_a.py"})
        out, is_error = self.text(self.call("run_python", {"path": "check_a.py"}))
        self.assertTrue(is_error)
        self.assertIn("at most 2 VM runs", out)

    def test_without_a_vm_there_is_no_run_python(self):
        server = DevvmMcpServer(self.ws, vm_runner=None)
        names = [t["name"] for t in server.handle(rpc("tools/list"))["result"]["tools"]]
        self.assertNotIn("run_python", names)

    def test_errors_notifications_and_the_journal(self):
        self.assertEqual(self.server.handle(rpc("nothing/here"))["error"]["code"], -32601)
        self.assertEqual(self.call("unknown_tool")["error"]["code"], -32602)
        self.assertEqual(self.server.handle({"jsonrpc": "1.0", "id": 3, "method": "ping"})["error"]["code"], -32600)
        self.assertEqual(self.server.handle(rpc("tools/call", {"name": "list_dir", "arguments": "no"}))["error"]["code"], -32602)
        self.call("write_file", {"path": "a.py", "content": "x = 1\n" * 40})
        self.call("read_file", {"path": "missing.py"})
        rows = [json.loads(line) for line in self.journal.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["tool"], r["ok"]) for r in rows], [("write_file", True), ("read_file", False)])
        self.assertIn("<240 chars>", json.dumps(rows[0]["args"]))
        self.assertNotIn("x = 1", json.dumps(rows[0]))

    def test_the_hand_in_is_written_down(self):
        out, is_error = self.text(self.call("submit_result", {"summary": "done"}))
        self.assertFalse(is_error)
        self.assertEqual(json.loads(self.result.read_text(encoding="utf-8"))["final"], {"summary": "done"})
        self.assertEqual(self.server.final, {"summary": "done"})

    def test_the_stdio_loop_answers_line_by_line_and_survives_garbage(self):
        lines = [json.dumps(rpc("initialize", {"protocolVersion": "2024-11-05"}, 1)), "not json", json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}), "", json.dumps(rpc("tools/list", None, 2))]
        out = io.StringIO()
        self.server.serve(io.StringIO("\n".join(lines) + "\n"), out)
        answers = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual([a.get("id") for a in answers], [1, None, 2])
        self.assertEqual(answers[1]["error"]["code"], -32700)

    def test_arguments_in_the_journal_are_short(self):
        self.assertEqual(short_args({"path": "a.py", "content": "x" * 500, "edits": [1, 2]}), {"path": "a.py", "content": "<500 chars>", "edits": "<2 changes>"})


class ProcessTests(unittest.TestCase):
    def test_the_real_process_speaks_mcp_over_stdio_without_a_vm(self):
        with tempfile.TemporaryDirectory() as tmp:
            messages = "\n".join(json.dumps(m) for m in (rpc("initialize", {"protocolVersion": "2025-06-18"}, 1), {"jsonrpc": "2.0", "method": "notifications/initialized"},
                                                         rpc("tools/call", {"name": "write_file", "arguments": {"path": "a.py", "content": "x = 1\n"}}, 2),
                                                         rpc("tools/call", {"name": "read_file", "arguments": {"path": "a.py"}}, 3))) + "\n"
            done = subprocess.run([sys.executable, "-m", "guppi_runtime.devvm_mcp", "--project", tmp, "--no-vm", "--workspace-root", tmp], input=messages, capture_output=True, text=True,
                                  timeout=60, cwd=str(RUNTIME), env={**os.environ, "PYTHONPATH": str(RUNTIME / "src")})
            answers = [json.loads(x) for x in done.stdout.splitlines()]
            self.assertEqual([a["id"] for a in answers], [1, 2, 3], done.stderr)
            self.assertEqual(answers[2]["result"]["content"][0]["text"], "x = 1\n")


if __name__ == "__main__":
    unittest.main()


class AttachTests(unittest.TestCase):
    def test_a_server_can_attach_to_a_workspace_that_the_caller_made(self):
        from guppi_runtime.devvm_mcp import build, main
        import argparse
        with tempfile.TemporaryDirectory() as tmp:
            ws = DevWorkspace(Path(tmp), "M-ATT00001", policy=dict(POLICY)); ws.create()
            ws.write("seed.py", "x = 1\n")
            args = argparse.Namespace(workspace_root=tmp, mission="M-ATT00001", attach=True, seed=None, no_vm=True, project=tmp, max_calls=10, max_seconds=60, max_vm_runs=None, self_check="full", journal=None, result_file=None)
            attached, server = build(args)
            self.assertEqual(attached.read("seed.py"), "x = 1\n")                                                 # the file of the caller is there, no second create
            server.box.call("write_file", {"path": "b.py", "content": "y = 2\n"})
            self.assertEqual(ws.read("b.py"), "y = 2\n")                                                          # and what the agent writes is seen by the caller
            args.attach = False
            with self.assertRaises(Exception): build(args)                                                        # without --attach an existing workspace is refused


class HandInTests(McpTests):
    def test_after_the_hand_in_every_call_says_that_the_task_is_over(self):
        out, is_error = self.text(self.call("submit_result", {"summary": "done"}))
        self.assertFalse(is_error)
        self.assertIn("task is over", out)
        for name, args in (("submit_result", {"summary": "again"}), ("read_file", {"path": "a.py"}), ("write_file", {"path": "x.py", "content": "y"})):
            text, is_error = self.text(self.call(name, args))
            self.assertTrue(is_error); self.assertIn("task is over", text)
        self.assertFalse((Path(self.tmp.name) / "devvm" / "M-MCP0001" / "repo" / "work" / "x.py").exists())          # nothing is written after the hand-in
        rows = [json.loads(line) for line in self.journal.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["ok"] for r in rows], [True, False, False, False])
