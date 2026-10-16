"""Layer summary (coder measurement, 2026-10-11): every build attempt and the comparison table should say in which LAYER the time went (1 server/model, 2 connection, 3 model
behaviour, 4 agent budget, 5 understanding, ok). Today benchmarks/failure_layers.py can only read whole log files by hand. `layer_summary.py` works on the agent run rows that
devvm_build already stores (agent_detail: stopped_by, seconds, completion_tokens), so the result file and model_compare can carry the layers. Pure functions. GUPPI builds it
(model comparison 2026-10-11), Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/layer_summary). Process: docs/PROZESS_GUPPY_VON_UNTEN_2026-10-10.md."""

NOTES = '''# Notes for layer_summary
Pure Python 3 standard library (re), no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
The six layers in this fixed order: "server", "connection", "behaviour", "budget", "understanding", "ok".
'''

COMMON = r'''
import copy
from layer_summary import IMPORTS
R = [
    {"stopped_by": "hand_in", "stage_passed": True, "seconds": 100, "completion_tokens": 1000},
    {"stopped_by": "hand_in", "stage_passed": False, "seconds": 50, "completion_tokens": 500},
    {"stopped_by": "hand_in", "seconds": 10, "completion_tokens": 100},
    {"stopped_by": "answer_cut", "seconds": 200, "completion_tokens": 4000},
    {"stopped_by": "turns", "seconds": 300, "completion_tokens": 3000},
    {"stopped_by": "error", "error": "HTTP Error 400: Bad Request", "seconds": 20, "completion_tokens": 0},
    {"stopped_by": "error", "error": "ConnectionResetError: [WinError 10054]", "seconds": 5, "completion_tokens": 0},
    {"stopped_by": "weird_end", "seconds": 15, "completion_tokens": 150},
    {"stopped_by": "no_tool_call", "completion_tokens": True},
]
ZERO = {"runs": 0, "seconds": 0, "tokens": 0}
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
assert [classify(r) for r in R] == ["ok", "understanding", "ok", "behaviour", "budget", "connection", "server", "behaviour", "connection"]
for end, layer in (("garbage", "server"), ("server_crash", "server"), ("runaway", "behaviour"), ("loop", "behaviour"), ("quality", "behaviour"),
                   ("time", "budget"), ("calls", "budget"), ("tokens", "budget"), ("error", "connection"), ("no_tool_call", "connection")):
    assert classify({"stopped_by": end}) == layer, end
assert classify({"stopped_by": "error", "error": "HTTP 503 Service Unavailable"}) == "server"
assert classify({"stopped_by": "error", "error": "RemoteDisconnected('closed')"}) == "server"
assert classify({"stopped_by": "error", "error": "ConnectionRefusedError"}) == "server"
assert classify({"stopped_by": "error", "error": None}) == "connection"
assert classify({"stopped_by": "error", "error": "HTTPError: HTTP Error 500: Internal Server Error"}) == "server"
assert classify({"stopped_by": "error", "error": "agent stopped: ConnectionAbortedError"}) == "server"
assert classify({"stopped_by": "hand_in", "stage_passed": None}) == "ok"
assert classify({}) == "behaviour"
s = summary(R)
assert list(s) == ["server", "connection", "behaviour", "budget", "understanding", "ok"]
assert s["server"] == {"runs": 1, "seconds": 5, "tokens": 0}
assert s["connection"] == {"runs": 2, "seconds": 20, "tokens": 0}
assert s["behaviour"] == {"runs": 2, "seconds": 215, "tokens": 4150}
assert s["budget"] == {"runs": 1, "seconds": 300, "tokens": 3000}
assert s["understanding"] == {"runs": 1, "seconds": 50, "tokens": 500}
assert s["ok"] == {"runs": 2, "seconds": 110, "tokens": 1100}
assert summary([]) == {k: ZERO for k in ["server", "connection", "behaviour", "budget", "understanding", "ok"]}
assert summary([{"stopped_by": "turns", "seconds": 1.5, "completion_tokens": "7"}])["budget"] == {"runs": 1, "seconds": 1.5, "tokens": 0}
before = copy.deepcopy(R); summary(R); assert R == before
"""

C2 = r"""
s = summary(R)
assert shares(s) == {"server": 1, "connection": 3, "behaviour": 31, "budget": 43, "understanding": 7, "ok": 16}
assert shares(s, "tokens") == {"server": 0, "connection": 0, "behaviour": 47, "budget": 34, "understanding": 6, "ok": 13}
assert shares(s, "runs") == {"server": 11, "connection": 22, "behaviour": 22, "budget": 11, "understanding": 11, "ok": 22}
assert list(shares(s)) == ["server", "connection", "behaviour", "budget", "understanding", "ok"]
assert shares(summary([])) == {k: 0 for k in ["server", "connection", "behaviour", "budget", "understanding", "ok"]}
assert cell(R) == "1:1 2:3 3:31 4:43 5:7 ok:16"
assert cell(R, "tokens") == "1:0 2:0 3:47 4:34 5:6 ok:13"
assert cell([]) == "1:0 2:0 3:0 4:0 5:0 ok:0"
assert cell([{"stopped_by": "hand_in", "seconds": 3}]) == "1:0 2:0 3:0 4:0 5:0 ok:100"
"""

STAGES = [
    {"name": "summary",
     "task": """Create `layer_summary.py` (Python 3 standard library only). A run is a dict (an agent run of a build) with "stopped_by" (how it ended), maybe "error" (text), "stage_passed" (True, False or None), "seconds" and "completion_tokens".
- `classify(run) -> str`, one of the layers "server", "connection", "behaviour", "budget", "understanding", "ok":
  * stopped_by "error" and re.search finds in str(error) (anywhere, not only at the start) the regular expression HTTP Error 5\\d\\d|HTTP 5\\d\\d|Connection(Reset|Aborted|Refused)|RemoteDisconnected -> "server"; any other "error" -> "connection";
  * "garbage", "server_crash" -> "server"; "no_tool_call" -> "connection"; "answer_cut", "runaway", "loop", "quality" -> "behaviour"; "turns", "time", "calls", "tokens" -> "budget";
  * "hand_in" -> "understanding" when stage_passed is False, else "ok";
  * anything else (also a missing stopped_by) -> "behaviour".
- `summary(runs) -> dict`: the six layers in the order above as keys, each {"runs": count, "seconds": sum, "tokens": sum of completion_tokens}. A missing value, or one that is not an int or float (a bool does not count as a number), adds 0. Layers without runs are still present with zeros.
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code. Add `tests/test_layer_summary.py` (unittest) with your own tests.""",
     "hidden": {"hidden_ls_1.py": hidden("classify, summary", C1)}},
    {"name": "shares",
     "task": """Add to `layer_summary.py`:
- `shares(table, key="seconds") -> dict`: for a summary table, the share of every layer in percent of the total of `key` ("runs", "seconds" or "tokens"), as round(100 * value / total) (Python's round), the six layers in the fixed order; all 0 when the total is 0.
- `cell(runs, key="seconds") -> str`: one short text for a table cell from the shares of summary(runs): for each layer in the fixed order "<short>:<percent>", joined by one space, where short is "1" server, "2" connection, "3" behaviour, "4" budget, "5" understanding and "ok" ok. Example: "1:0 2:5 3:30 4:35 5:14 ok:16".
Add tests to `tests/test_layer_summary.py`.""",
     "hidden": {"hidden_ls_2.py": hidden("classify, summary, shares, cell", C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_layer_summary.py` and read `layer_summary.py` once more. Make sure no mapping is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_ls_full.py": hidden("classify, summary, shares, cell", C1 + C2)}},
]
