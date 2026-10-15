"""E-06 (coder extension "background jobs with wake_on", 2026-10-11): the coder can start a long-running command (a server, a watcher, a slow test), keep working and is
woken when the job exits, prints a matching line or stays silent too long; plus job log and stop. The stop waits until the process is really gone and kills it when terminate is
ignored (pattern from deepseek-harness). Idea from little-coder. The process is injected (spawn function), so the table is pure logic and the tool wiring in the sandbox comes
after acceptance. GUPPI builds it (model comparison 2026-10-11), Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/e06_bg_jobs).
Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for bg_jobs
Pure Python 3 standard library (re), no file, process or network access of its own: processes come from the injected `spawn` function, time from the injected `clock`.
A process object has: read() -> str (new output since the last read, maybe several lines, maybe a partial line), poll() -> None while running else the exit code,
terminate(), kill(), wait(timeout) -> exit code (may raise an exception when the process does not end in time).
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code.
'''

COMMON = r'''
from bg_jobs import Jobs

class Proc:
    def __init__(self, argv):
        self.argv, self.out, self.code = argv, [], None
        self.terminated = self.killed = 0
        self.hang, self.waits = False, []
    def read(self):
        return self.out.pop(0) if self.out else ""
    def poll(self):
        return self.code
    def terminate(self):
        self.terminated += 1
        if not self.hang:
            self.code = -15
    def kill(self):
        self.killed += 1
        self.code = -9
    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self.code is None:
            raise TimeoutError("still running")
        return self.code

T = [0.0]
def clock():
    return T[0]
procs = []
def spawn(argv):
    p = Proc(argv)
    procs.append(p)
    return p

def raises(kind, text, fn, *args):
    try:
        fn(*args)
    except kind as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no {kind.__name__}({text!r})")
BODY
print("ok")
'''


def hidden(body):
    return COMMON.replace("BODY", body)


C1 = r"""
j = Jobs(spawn, clock)
argv = ["python3", "srv.py"]
a = j.start(argv)
assert a == "J1"
assert procs[0].argv == ["python3", "srv.py"]
argv.append("--x")
assert j.status(a) == {"job": "J1", "argv": ["python3", "srv.py"], "state": "running", "code": None, "lines": 0}
raises(ValueError, "argv", j.start, [])
raises(ValueError, "argv", j.start, "ls")
raises(ValueError, "argv", j.start, ["a", 1])
raises(ValueError, "wake_on", j.start, ["a"], {"bad": 1})
raises(ValueError, "wake_on", j.start, ["a"], ["exit"])
raises(ValueError, "wake_on", j.start, ["a"], {"exit": "yes"})
raises(ValueError, "match", j.start, ["a"], {"match": "("})
raises(ValueError, "match", j.start, ["a"], {"match": 5})
raises(ValueError, "silence", j.start, ["a"], {"silence": 0})
raises(ValueError, "silence", j.start, ["a"], {"silence": -1})
raises(ValueError, "silence", j.start, ["a"], {"silence": True})
raises(ValueError, "silence", j.start, ["a"], {"silence": "5"})
assert len(procs) == 1
b = j.start(["b"], {"exit": False, "match": "x", "silence": 2.5})
assert b == "J2" and len(procs) == 2
assert j.stop(a) == -15
assert procs[0].terminated == 1 and procs[0].waits == [5] and procs[0].killed == 0
assert j.status(a)["state"] == "stopped" and j.status(a)["code"] == -15
assert j.stop(a) == -15 and procs[0].terminated == 1
procs[1].hang = True
assert j.stop(b) == -9
assert procs[1].terminated == 1 and procs[1].killed == 1 and procs[1].waits == [5, 5]
assert j.status(b) == {"job": "J2", "argv": ["b"], "state": "stopped", "code": -9, "lines": 0}
for fn in (j.stop, j.status, j.log):
    raises(ValueError, "unknown_job", fn, "J9")
k = Jobs(spawn, clock, max_jobs=2)
assert k.start(["1"]) == "J1" and k.start(["2"]) == "J2"
raises(RuntimeError, "too_many_jobs", k.start, ["3"])
k.stop("J1")
assert k.start(["3"]) == "J3"
assert k.stop_all() == ["J2", "J3"]
assert k.status("J2")["state"] == "stopped" and k.status("J3")["state"] == "stopped"
assert k.stop_all() == []
"""

C2 = r"""
T[0] = 0.0
j = Jobs(spawn, clock)
a = j.start(["srv"], {"match": "ready|listening", "silence": 10, "exit": True})
p = procs[-1]
T[0] = 1.0; p.out = ["boot\nlist"]
assert j.poll() == []
assert j.log(a) == "boot" and j.status(a)["lines"] == 1
T[0] = 2.0; p.out = ["ening on 80\nok\n"]
assert j.poll() == [{"job": a, "reason": "match", "detail": "listening on 80"}]
assert j.log(a) == "boot\nlistening on 80\nok" and j.status(a)["lines"] == 3
T[0] = 11.9
assert j.poll() == []
T[0] = 12.0
assert j.poll() == [{"job": a, "reason": "silence", "detail": 10}]
T[0] = 30.0
assert j.poll() == []
T[0] = 31.0; p.out = ["ready again\nready 2\n"]
assert j.poll() == [{"job": a, "reason": "match", "detail": "ready again"}]
T[0] = 41.0
assert j.poll() == [{"job": a, "reason": "silence", "detail": 10}]
T[0] = 42.0; p.out = ["bye\n", "listening late"]; p.code = 0
assert j.poll() == [{"job": a, "reason": "match", "detail": "listening late"}, {"job": a, "reason": "exit", "detail": 0}]
assert j.log(a, 2) == "bye\nlistening late"
assert j.status(a)["state"] == "exited" and j.status(a)["code"] == 0
assert j.poll() == []
assert j.stop(a) == 0 and p.terminated == 0
b = j.start(["x"]); pb = procs[-1]
c = j.start(["y"], {"match": "err"}); pc = procs[-1]
pb.code = 3; pc.out = ["err1\nerr2\n"]; pc.code = 1
assert j.poll() == [{"job": b, "reason": "exit", "detail": 3}, {"job": c, "reason": "match", "detail": "err1"}]
assert j.status(c)["state"] == "exited" and j.status(c)["code"] == 1
T[0] = 100.0
d = j.start(["z"], {"silence": 5})
T[0] = 104.0
assert j.poll() == []
T[0] = 105.0
assert j.poll() == [{"job": d, "reason": "silence", "detail": 5}]
small = Jobs(spawn, clock, keep_lines=3)
e = small.start(["n"]); procs[-1].out = ["1\n2\n3\n4\n5\n"]
assert small.poll() == []
assert small.log(e) == "3\n4\n5" and small.log(e, 1) == "5" and small.status(e)["lines"] == 3
raises(ValueError, "tail", small.log, e, 0)
raises(ValueError, "tail", small.log, e, True)
raises(ValueError, "tail", small.log, e, "2")
"""

STAGES = [
    {"name": "table",
     "task": """Create `bg_jobs.py` (Python 3 standard library only) with a class `Jobs(spawn, clock, max_jobs=4, keep_lines=200)`: a table of background jobs. `spawn(argv)` returns a process object (see NOTES.md), `clock()` returns the time in seconds.
- `start(argv, wake_on=None) -> str`: argv must be a non-empty list of str, else ValueError("argv"). wake_on None means {"exit": True}. Otherwise wake_on must be a dict whose keys are among "exit", "match", "silence", else ValueError("wake_on"); "exit" (default False) must be a bool, else ValueError("wake_on"); "match" (default None) must be a str that compiles as a regular expression, else ValueError("match"); "silence" (default None) must be an int or float > 0 and not a bool, else ValueError("silence"). When max_jobs jobs are running: RuntimeError("too_many_jobs"). Only then spawn(a copy of argv) is called and the job gets the id "J1", "J2", ... (one more for every successful start; a refused start uses no id and spawns nothing). Return the id.
- `status(job_id) -> dict`: {"job": id, "argv": copy of the argv given at start, "state": "running" / "exited" / "stopped", "code": exit code or None, "lines": number of kept output lines}.
- `stop(job_id) -> code`: a job that is not running: return its code, do nothing else. Otherwise terminate(), then code = wait(timeout=5); when wait raises any exception: kill(), then code = wait(timeout=5). The state becomes "stopped" with that code; return it.
- `stop_all() -> list`: stop every running job in start order and return their ids.
- An unknown id in status, stop (and log, next stage): ValueError("unknown_job").
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code. Add `tests/test_bg_jobs.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e06_1.py": hidden(C1)}},
    {"name": "poll",
     "task": """Add output handling and wake events to `Jobs` in `bg_jobs.py`:
- `poll() -> list`: for every RUNNING job in start order: now = clock(); text = read(); code = poll() of the process; when code is not None, text += read() once more. Output is split into lines at "\\n": a last piece without "\\n" waits (pending) for the next read and is joined to it; when the process has exited, a non-empty pending piece becomes a line too. New complete lines are added to the job's lines; keep only the last keep_lines lines. When there were new lines, the job's last-output time becomes now and its silence event may fire again. Events for this job, in this order:
  * "match": when wake_on has a match pattern, the FIRST new line where re.search finds it: {"job": id, "reason": "match", "detail": line} (at most one per job per poll);
  * "exit": when code is not None the job becomes "exited" with that code; if wake_on exit is true: {"job": id, "reason": "exit", "detail": code};
  * "silence": only while still running, when wake_on has silence, the event has not fired since the last output, and now - last output time >= silence: {"job": id, "reason": "silence", "detail": now - last output time}. The last output time starts at the start of the job.
  Return all events of all jobs.
- `log(job_id, tail=20) -> str`: the last `tail` kept lines joined by "\\n"; tail must be an int >= 1 (not a bool), else ValueError("tail").
Add tests to `tests/test_bg_jobs.py`.""",
     "hidden": {"hidden_e06_2.py": hidden(C1 + C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_bg_jobs.py` and read `bg_jobs.py` once more. Make sure no check is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e06_full.py": hidden(C1 + C2)}},
]
