import json
import sys
import unittest
import urllib.request
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))

from agent_tool_probe import DENY, DISABLED, OUR_TOOLS, judge, make_server, qwen_settings, tool_names, tool_results  # noqa: E402


def post(port, body):
    request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode("utf-8")


class ProbeTests(unittest.TestCase):
    def test_tool_names_and_the_judgement(self):
        body = {"tools": [{"type": "function", "function": {"name": "mcp__devvm__read_file"}}, {"type": "function", "function": {"name": "outline"}}]}
        self.assertEqual(tool_names(body), ["mcp__devvm__read_file", "outline"])
        self.assertEqual(judge(tool_names(body)), (True, []))
        ours, foreign = judge(["mcp__devvm__read_file", "run_shell_command", "tool_call"])
        self.assertFalse(ours)
        self.assertEqual(foreign, ["run_shell_command", "tool_call"])
        self.assertEqual(tool_names({}), [])

    def test_the_confined_settings_deny_the_built_in_tools_and_allow_only_ours(self):
        plain = qwen_settings(False, "python", "proj", "ws")
        self.assertNotIn("permissions", plain)
        confined = qwen_settings(True, "python", "proj", "ws")
        self.assertEqual(set(DENY) & {"Bash", "Read", "Edit", "Glob", "Grep", "WebFetch"}, {"Bash", "Read", "Edit", "Glob", "Grep", "WebFetch"})
        self.assertEqual(confined["permissions"]["deny"], DENY)
        self.assertEqual(sorted(confined["permissions"]["allow"]), sorted(f"mcp__devvm__{n}" for n in OUR_TOOLS))
        self.assertEqual(sorted(confined["tools"]["visible"]), sorted(f"mcp__devvm__{n}" for n in OUR_TOOLS))
        self.assertFalse(confined["tools"]["toolSearch"]["enabled"])
        for name in ("tool_search", "tool_call", "run_shell_command", "write_file", "edit", "web_fetch"):
            self.assertIn(name, DISABLED)
        server = confined["mcpServers"]["devvm"]
        self.assertIn("--no-vm", server["args"])
        self.assertIn("guppi_runtime.devvm_mcp", server["args"])

    def test_the_fake_model_answers_with_text_and_with_scripted_tool_calls_and_records_everything(self):
        records = []
        server = make_server(records, [("mcp__devvm__write_file", {"path": "a.py", "content": "x = 1\n"})])
        port = server.server_address[1]
        try:
            first = post(port, {"model": "m", "stream": True, "tools": [{"type": "function", "function": {"name": "t"}}], "messages": []})
            self.assertIn('"tool_calls"', first)
            self.assertIn("mcp__devvm__write_file", first)
            self.assertTrue(first.rstrip().endswith("data: [DONE]"))
            second = post(port, {"model": "m", "stream": False, "tools": [{"type": "function", "function": {"name": "t"}}], "messages": []})
            self.assertEqual(json.loads(second)["choices"][0]["message"]["content"], "ok")
            third = post(port, {"model": "m", "stream": True, "messages": [{"role": "user", "content": "title please"}]})
            self.assertIn('"content": "ok"', third)
        finally:
            server.shutdown()
        self.assertEqual(len(records), 3)

    def test_the_tool_results_of_a_request_are_listed_with_the_calls(self):
        body = {"messages": [{"role": "user", "content": "go"}, {"role": "assistant", "content": None, "tool_calls": [{"function": {"name": "run_shell_command"}}]},
                             {"role": "tool", "content": "declined"}]}
        self.assertEqual(tool_results(body), ["(call) run_shell_command", "declined"])


if __name__ == "__main__":
    unittest.main()
