"""Phase 5, part A, in stages (2026-10-06): the one-shot spec (phase5_view.py) failed 0 of 7 attempts, with the small and the strong model and in escalating as well as pipeline
mode: the task has about fifteen precise behaviours and the planner did not split it. The same module is therefore built in four small stages in the SAME workspace, each with
its own hidden test; the last stage is the complete hidden test of the one-shot spec. A stage that fails its hidden test is reported, and the next stage still runs on what exists."""
from devvm_specs.phase5_view import NOTES, HIDDEN as FULL

COMMON = r'''
import copy
from devvm_view import IMPORTS


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


EVENTS = [ev("DEVVM_AGENT_RUN", "2026-10-06T10:00:01Z", "M-A", role="coder", model="jan", label="coder (alone)", stopped_by="hand_in", calls=7, seconds=6.3),
          "junk", None, {"event_type": "OTHER", "payload": {}}, {"event_type": "DEVVM_PLAN", "timestamp": "2026-10-06T10:00:02Z", "payload": {}},
          ev("DEVVM_STEP", "2026-10-06T10:00:03Z", "M-A", title="task", accepted=True, rounds=1, mode="escalating"),
          ev("DEVVM_STEP", "2026-10-06T10:00:04Z", "M-A", title="t2", accepted=False, rounds=3, unjudged=True),
          ev("DEVVM_AGENT_RUN", "2026-10-06T10:00:05Z", "M-B", role="planner", stopped_by="turns", calls=3, depth=2),
          ev("DEVVM_RUN_DONE", "2026-10-06T10:00:06Z", "M-B", accepted=True, agent_runs=2, seconds=66.3, swaps=2, mode="escalating"),
          {"event_type": "DEVVM_AGENT_RUN", "timestamp": "2026-10-06T10:00:07Z", "source": {"component": "devvm", "mission_id": None}}]
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


S1 = r'''
wss = {"M-B": WS(["b.py", "a.py", "c/d.py"], [{"commit": "%040d" % i, "message": f"m{i}", "author": "a", "time": f"t{i}"} for i in range(15)], {"added": ["x"], "modified": ["y", "z"], "deleted": []}),
       "M-A": WS([f"f{i:03d}.py" for i in range(5)])}
snap = {k: list(v.files) for k, v in wss.items()}
m = missions_view(wss)
assert [x["mission_id"] for x in m] == ["M-A", "M-B"] and {k: list(v.files) for k, v in wss.items()} == snap
b = m[1]
assert b["files"] == ["a.py", "b.py", "c/d.py"] and b["file_count"] == 3 and b["truncated"] is False, b
assert len(b["log"]) == 10 and b["log"][0] == {"commit": "00000000", "message": "m0", "time": "t0"}
assert b["uncommitted"] == {"added": 1, "modified": 2, "deleted": 0} and b["usage"] == {"files": 3}
s = missions_view(wss, max_files=2)[1]
assert s["files"] == ["a.py", "b.py"] and s["file_count"] == 3 and s["truncated"] is True, s
bad = missions_view({"M-X": WS(["a"], boom="tree"), "M-Y": WS(["a"], boom="log"), "M-Z": WS(["z.py"])})
assert [x["mission_id"] for x in bad] == ["M-X", "M-Y", "M-Z"]
assert bad[0] == {"mission_id": "M-X", "error": "RuntimeError: tree broke"} and bad[1] == {"mission_id": "M-Y", "error": "ValueError: log broke"} and bad[2]["files"] == ["z.py"]
assert missions_view({}) == []
'''

S2 = r'''
snap = copy.deepcopy(EVENTS)
ag = agent_rows(EVENTS)
assert EVENTS == snap
assert [a["mission_id"] for a in ag] == [None, "M-B", "M-A"], ag
assert ag[2] == {"mission_id": "M-A", "time": "2026-10-06T10:00:01Z", "role": "coder", "label": "coder (alone)", "model": "jan", "stopped_by": "hand_in", "calls": 7, "seconds": 6.3, "depth": 1}, ag[2]
assert ag[1]["depth"] == 2 and ag[1]["model"] is None and ag[1]["label"] is None and ag[0]["role"] is None and ag[0]["depth"] == 1
st = step_rows(EVENTS)
assert [s["title"] for s in st] == ["t2", "task"], st
assert st[0] == {"mission_id": "M-A", "time": "2026-10-06T10:00:04Z", "title": "t2", "accepted": False, "rounds": 3, "unjudged": True, "mode": None}, st[0]
assert st[1]["unjudged"] is False and st[1]["mode"] == "escalating"
assert run_rows(EVENTS) == [{"mission_id": "M-B", "time": "2026-10-06T10:00:06Z", "accepted": True, "agent_runs": 2, "seconds": 66.3, "swaps": 2, "mode": "escalating"}]
assert len(agent_rows(EVENTS, max_events=2)) == 2 and agent_rows(EVENTS, max_events=2)[0]["mission_id"] is None
assert agent_rows([]) == [] and step_rows([]) == [] and run_rows([]) == []
'''

S3 = r'''
t = ticker_lines(EVENTS)
assert len(t) == 6, t
assert t[0] == "10:00:07 - ? ? ? calls", t[0]
assert t[1] == "10:00:06 M-B run done: ACCEPTED", t[1]
assert t[2] == "10:00:05 M-B planner turns 3 calls", t[2]
assert t[3] == "10:00:04 M-A step t2: REJECTED (unjudged)", t[3]
assert t[4] == "10:00:03 M-A step task: ACCEPTED", t[4]
assert t[5] == "10:00:01 M-A coder (alone) hand_in 7 calls", t[5]
assert len(ticker_lines(EVENTS, max_events=2)) == 2 and ticker_lines([]) == []
assert ticker_lines([ev("DEVVM_STEP", "bad", "M", title="x", accepted=True)]) == ["--:--:-- M step x: ACCEPTED"]
'''

EVENT_FORMAT = '''{"event_type": str, "timestamp": str, "source": {"component": str, "mission_id": str or None}, "payload": dict}'''

STAGES = [
    {"name": "missions_view",
     "task": '''In this workspace create `devvm_view.py` (pure Python 3 standard library, no file or network access, never modify the arguments).

It provides `missions_view(workspaces, max_files=200) -> list`. `workspaces` maps a mission id (str) to a workspace object with the methods
    tree() -> list of relative file paths, log(limit) -> list of dicts {"commit": str, "message": str, "author": str, "time": str} (newest first),
    status() -> dict {"added": [paths], "modified": [paths], "deleted": [paths]}, usage() -> dict.
The result is a list sorted by mission id with one entry per workspace:
    {"mission_id", "files": the first `max_files` paths of tree() (sorted), "file_count": the full number of paths, "truncated": file_count > max_files,
     "log": the first 10 entries of log(10) reduced to {"commit": first 8 characters of the commit id, "message", "time"},
     "uncommitted": {"added": n, "modified": n, "deleted": n} (the counts of the lists of status()), "usage": usage() as returned}
If any method of a workspace raises an exception, that entry is {"mission_id", "error": "<ExceptionClassName>: <message>"} and the other missions are still reported.
Add `tests/test_devvm_view.py` (unittest) with your own tests.''',
     "hidden": {"hidden_s1.py": hidden("missions_view", S1)}},
    {"name": "event_rows",
     "task": '''In the existing `devvm_view.py` (keep `missions_view`) add three functions. Each takes `events`, a list of audit events (oldest first) and `max_events=100`. An event is a dict
    ''' + EVENT_FORMAT + '''
Ignore anything that is not such a dict. Missing payload fields must never raise an error. Each function returns the matching events NEWEST FIRST, at most `max_events`.

`agent_rows(events, max_events=100)`: for the events with event_type "DEVVM_AGENT_RUN"; each row is
    {"mission_id", "time", "role", "label", "model", "stopped_by", "calls", "seconds", "depth"}
    mission_id from source.mission_id, "time" is the timestamp string UNCHANGED, the others from the payload; a missing payload field is None, except "depth" which is 1.
`step_rows(events, max_events=100)`: for "DEVVM_STEP"; each row {"mission_id", "time", "title", "accepted", "rounds", "unjudged", "mode"}; "unjudged" is False when missing, the others None when missing.
`run_rows(events, max_events=100)`: for "DEVVM_RUN_DONE"; each row {"mission_id", "time", "accepted", "agent_runs", "seconds", "swaps", "mode"}; missing values are None.
Add tests to `tests/test_devvm_view.py`.''',
     "hidden": {"hidden_s2.py": hidden("agent_rows, step_rows, run_rows", S2)}},
    {"name": "ticker_lines",
     "task": '''In the existing `devvm_view.py` (keep the other functions) add `ticker_lines(events, max_events=100) -> list of str`: short text lines for a live ticker, NEWEST FIRST, at most `max_events`.
`events` are audit events as before (oldest first, dicts ''' + EVENT_FORMAT + '''); ignore everything that is not such a dict.
One line per event of these three kinds (other events, such as DEVVM_PLAN, are ignored). `<hh:mm:ss>` is characters 11 to 19 of the ISO timestamp (e.g. "2026-10-06T13:25:04Z" gives "13:25:04"), or "--:--:--" when the timestamp is missing or too short. A missing mission id is shown as "-". Any other missing field is shown as "?".
    DEVVM_AGENT_RUN -> "<hh:mm:ss> <mission_id> <label, or role when there is no label> <stopped_by> <calls> calls"
    DEVVM_STEP      -> "<hh:mm:ss> <mission_id> step <title>: ACCEPTED" when payload accepted is true, otherwise "...: REJECTED"; add " (unjudged)" at the end when payload unjudged is true
    DEVVM_RUN_DONE  -> "<hh:mm:ss> <mission_id> run done: ACCEPTED" or "...: REJECTED" in the same way
Add tests to `tests/test_devvm_view.py`.''',
     "hidden": {"hidden_s3.py": hidden("ticker_lines", S3)}},
    {"name": "build_view",
     "task": '''In the existing `devvm_view.py` add `build_view(workspaces, events, max_files=200, max_events=100) -> dict` that combines the functions you already wrote. The result has exactly the keys
    "missions": missions_view(workspaces, max_files), "agents": agent_rows(events, max_events), "steps": step_rows(events, max_events), "runs": run_rows(events, max_events), "ticker": ticker_lines(events, max_events).
Neither argument may be modified. Add a test to `tests/test_devvm_view.py`.''',
     "hidden": FULL},
]
