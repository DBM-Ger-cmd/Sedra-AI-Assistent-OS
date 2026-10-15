"""Phase 5, part A (Captain 2026-10-06: "GUPPI soll es selber bauen"): the read-only data view of the DevVM window and the live ticker.

GUPPI builds `devvm_view.py` (pure Python, no I/O) in a DevVM workspace; this spec holds the task text and the HIDDEN acceptance test, which the agents never see.
The candidate is exported, never integrated (Captain: the build is approved, the integration is not).
"""

TASK = '''Create the module `devvm_view.py` in this workspace (pure Python 3 standard library, no file or network access, never modify its inputs).

It provides one function:

    build_view(workspaces, events, max_files=200, max_events=100) -> dict

`workspaces` is a dict mapping a mission id (str) to a workspace object. A workspace object has these methods (see NOTES.md):
    tree()        -> list of relative file paths (str)
    log(limit)    -> list of dicts {"commit": str, "message": str, "author": str, "time": str}, newest first
    status()      -> dict {"added": [paths], "modified": [paths], "deleted": [paths]}
    usage()       -> dict (any content)
`events` is a list of audit events, oldest first. Each event is a dict:
    {"event_type": str, "timestamp": str, "source": {"component": str, "mission_id": str or None}, "payload": dict}
Ignore anything that is not such a dict, and events whose event_type does not start with "DEVVM_". Missing payload fields must never raise an error.

The result is a dict with exactly these keys:

"missions": a list sorted by mission id; one entry per workspace:
    {"mission_id", "files": the first `max_files` paths of tree() (sorted), "file_count": the full number of paths, "truncated": file_count > max_files,
     "log": the first 10 entries of log(10) reduced to {"commit": first 8 characters of the commit id, "message", "time"},
     "uncommitted": {"added": n, "modified": n, "deleted": n} (counts), "usage": usage() as returned}
    If any method of a workspace raises an exception, that entry is {"mission_id", "error": "<ExceptionClassName>: <message>"} and the other missions are still reported.

"agents": the DEVVM_AGENT_RUN events, NEWEST FIRST, at most `max_events`; each {"mission_id", "time", "role", "label", "model", "stopped_by", "calls", "seconds", "depth"}
    taken from source.mission_id, the payload and the timestamp, which is passed through UNCHANGED as "time" (the full string, e.g. "2026-10-06T10:00:01Z"; only the ticker uses the hh:mm:ss part); a missing payload field is None, except "depth" which is 1.

"steps": the DEVVM_STEP events, newest first, at most `max_events`; each {"mission_id", "time", "title", "accepted", "rounds", "unjudged", "mode"}; "unjudged" is False when missing.

"runs": the DEVVM_RUN_DONE events, newest first, at most `max_events`; each {"mission_id", "time", "accepted", "agent_runs", "seconds", "swaps", "mode"}.

"ticker": at most `max_events` short text lines for the live ticker, NEWEST FIRST, one per DEVVM_* event of any of the three kinds above (other DEVVM_ events such as DEVVM_PLAN are ignored):
    DEVVM_AGENT_RUN  -> "<hh:mm:ss> <mission_id> <label or role> <stopped_by> <calls> calls"
    DEVVM_STEP       -> "<hh:mm:ss> <mission_id> step <title>: ACCEPTED" or "...: REJECTED" (accepted true / not true), followed by " (unjudged)" when unjudged is true
    DEVVM_RUN_DONE   -> "<hh:mm:ss> <mission_id> run done: ACCEPTED" or "...: REJECTED"
    <hh:mm:ss> is the time part of an ISO timestamp like 2026-10-06T13:25:04Z (characters 11 to 19); use "--:--:--" when the timestamp is missing or too short.
    A missing mission id is shown as "-"; any other missing field of a ticker line (label and role both missing, stopped_by, calls, title) is shown as "?".

Add `tests/test_devvm_view.py` (unittest) with your own tests of this behaviour.'''

NOTES = '''# Notes for the DevVM view

The audit events are produced by the DevVM orchestrator. Example of one event:

    {"event_type": "DEVVM_AGENT_RUN", "timestamp": "2026-10-06T13:25:04Z", "source": {"component": "devvm", "mission_id": "M-ESCA00001"},
     "payload": {"role": "coder", "model": "jan-code-4b", "label": "coder (alone)", "task": "...", "stopped_by": "hand_in", "calls": 7, "turns": 5, "seconds": 6.3, "completion_tokens": 703, "depth": 1}}
    {"event_type": "DEVVM_STEP", ..., "payload": {"title": "task", "accepted": true, "rounds": 1, "mode": "escalating", "unjudged": false}}
    {"event_type": "DEVVM_RUN_DONE", ..., "payload": {"accepted": true, "steps": 1, "agent_runs": 2, "seconds": 66.3, "swaps": 2, "mode": "escalating"}}

The workspace objects are `DevWorkspace` instances of the runtime; in the tests use small fake classes with the four methods.
'''

HIDDEN = {"hidden_view_check.py": r'''
import copy
from devvm_view import build_view


class WS:
    def __init__(self, files, log=(), status=None, usage=None, boom=None):
        self.files, self._log, self._status, self._usage, self.boom = list(files), list(log), status or {"added": [], "modified": [], "deleted": []}, usage or {"files": len(files)}, boom
    def tree(self):
        if self.boom == "tree": raise RuntimeError("tree broke")
        return list(self.files)
    def log(self, limit=20):
        if self.boom == "log": raise ValueError("log broke")
        return list(self._log)[:limit]
    def status(self): return copy.deepcopy(self._status)
    def usage(self): return dict(self._usage)


def ev(kind, ts, mission, **payload): return {"event_type": kind, "timestamp": ts, "source": {"component": "devvm", "mission_id": mission}, "payload": payload}


commits = [{"commit": "%040d" % i, "message": f"m{i}", "author": "a", "time": f"t{i}"} for i in range(15)]
wss = {"M-B": WS(["b.py", "a.py", "c/d.py"], commits, {"added": ["x"], "modified": ["y", "z"], "deleted": []}),
       "M-A": WS([f"f{i:03d}.py" for i in range(5)])}
events = [ev("DEVVM_AGENT_RUN", "2026-10-06T10:00:01Z", "M-A", role="coder", model="jan", label="coder (alone)", stopped_by="hand_in", calls=7, seconds=6.3),
          "junk", None, {"event_type": "OTHER", "payload": {}}, {"event_type": "DEVVM_PLAN", "timestamp": "2026-10-06T10:00:02Z", "payload": {}},
          ev("DEVVM_STEP", "2026-10-06T10:00:03Z", "M-A", title="task", accepted=True, rounds=1, mode="escalating"),
          ev("DEVVM_STEP", "2026-10-06T10:00:04Z", "M-A", title="t2", accepted=False, rounds=3, unjudged=True),
          ev("DEVVM_AGENT_RUN", "2026-10-06T10:00:05Z", "M-B", role="planner", stopped_by="turns", calls=3, depth=2),
          ev("DEVVM_RUN_DONE", "2026-10-06T10:00:06Z", "M-B", accepted=True, agent_runs=2, seconds=66.3, swaps=2, mode="escalating"),
          {"event_type": "DEVVM_AGENT_RUN", "timestamp": "2026-10-06T10:00:07Z", "source": {"component": "devvm", "mission_id": None}}]
snapshot_events, snapshot_files = copy.deepcopy(events), {k: list(v.files) for k, v in wss.items()}

v = build_view(wss, events)
assert set(v) == {"missions", "agents", "steps", "runs", "ticker"}, set(v)
assert events == snapshot_events and {k: list(w.files) for k, w in wss.items()} == snapshot_files, "inputs were changed"
assert [m["mission_id"] for m in v["missions"]] == ["M-A", "M-B"]
b = v["missions"][1]
assert b["files"] == ["a.py", "b.py", "c/d.py"] and b["file_count"] == 3 and b["truncated"] is False, b
assert len(b["log"]) == 10 and b["log"][0] == {"commit": "00000000", "message": "m0", "time": "t0"}, b["log"][0]
assert b["uncommitted"] == {"added": 1, "modified": 2, "deleted": 0} and b["usage"] == {"files": 3}
small = build_view(wss, events, max_files=2)["missions"][1]
assert small["files"] == ["a.py", "b.py"] and small["file_count"] == 3 and small["truncated"] is True, small
bad = build_view({"M-X": WS(["a"], boom="tree"), "M-Y": WS(["a"], boom="log"), "M-Z": WS(["z.py"])}, [])["missions"]
assert [m["mission_id"] for m in bad] == ["M-X", "M-Y", "M-Z"]
assert bad[0] == {"mission_id": "M-X", "error": "RuntimeError: tree broke"}, bad[0]
assert bad[1] == {"mission_id": "M-Y", "error": "ValueError: log broke"}, bad[1]
assert bad[2]["files"] == ["z.py"]
ag = v["agents"]
assert [a["mission_id"] for a in ag] == [None, "M-B", "M-A"], ag
assert ag[2] == {"mission_id": "M-A", "time": "2026-10-06T10:00:01Z", "role": "coder", "label": "coder (alone)", "model": "jan", "stopped_by": "hand_in", "calls": 7, "seconds": 6.3, "depth": 1}, ag[2]
assert ag[1]["depth"] == 2 and ag[1]["model"] is None and ag[1]["label"] is None
assert ag[0]["role"] is None and ag[0]["depth"] == 1
st = v["steps"]
assert [s["title"] for s in st] == ["t2", "task"] and st[0]["unjudged"] is True and st[1]["unjudged"] is False and st[1]["mode"] == "escalating" and st[0]["mode"] is None, st
assert st[0] == {"mission_id": "M-A", "time": "2026-10-06T10:00:04Z", "title": "t2", "accepted": False, "rounds": 3, "unjudged": True, "mode": None}, st[0]
rn = v["runs"]
assert rn == [{"mission_id": "M-B", "time": "2026-10-06T10:00:06Z", "accepted": True, "agent_runs": 2, "seconds": 66.3, "swaps": 2, "mode": "escalating"}], rn
t = v["ticker"]
assert len(t) == 6, t
assert t[0] == "10:00:07 - ? ? ? calls", t[0]
assert t[1] == "10:00:06 M-B run done: ACCEPTED", t[1]
assert t[2] == "10:00:05 M-B planner turns 3 calls", t[2]
assert t[3] == "10:00:04 M-A step t2: REJECTED (unjudged)", t[3]
assert t[4] == "10:00:03 M-A step task: ACCEPTED", t[4]
assert t[5] == "10:00:01 M-A coder (alone) hand_in 7 calls", t[5]
few = build_view({}, events, max_events=2)
assert len(few["agents"]) == 2 and len(few["ticker"]) == 2 and few["ticker"][0].startswith("10:00:07"), few
assert build_view({}, []) == {"missions": [], "agents": [], "steps": [], "runs": [], "ticker": []}
nots = build_view({}, [ev("DEVVM_STEP", "bad", "M", title="x", accepted=True)])["ticker"]
assert nots == ["--:--:-- M step x: ACCEPTED"], nots
print("ok")
'''}
