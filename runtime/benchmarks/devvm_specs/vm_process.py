"""Process starter for the background jobs of the coder (E-06 `bg_jobs` needs a `spawn` function; Captain 2026-10-13: GUPPI builds it). The microVM can only run one command to the end
and give back its output, so a "process" here is one such VM run in a thread: it exits when the run ends, its output arrives at the end, and a stop abandons the run (the result is
thrown away). The VM run itself is injected as `run(argv) -> {"status", "output"}`, so everything is pure logic that tests with fake runs. GUPPI builds it; Claude only wrote this file,
the hidden tests and the reference (benchmarks/devvm_refs/vm_process)."""

NOTES = '''# Notes for vm_process
Python 3 standard library only (threading), no file, process or network access of its own. The VM run is the injected function; never call anything else. Threads are daemon threads.
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code.
'''

HEAD = r'''
import threading, time
from vm_process import VmProcess, make_spawn


def fake(result, gate=None, boom=None):
    started = threading.Event(); seen = []
    def run(argv):
        seen.append(argv); started.set()
        if gate is not None:
            gate.wait(5)
        if boom is not None:
            raise boom
        return result
    return run, started, seen
'''

PROC = r'''
run, started, seen = fake({"status": "completed", "output": "hello\n"})
args = ["python3", "a.py"]
p = VmProcess(run, args)
assert p.wait(2) == 0 and p.poll() == 0
assert seen == [["python3", "a.py"]] and seen[0] is not args
assert p.read() == "hello\n" and p.read() == ""
assert p.wait() == 0

run, _, _ = fake({"status": "failed", "output": "Traceback\n"}); p = VmProcess(run, ["x"])
assert p.wait(2) == 1 and p.poll() == 1 and p.read() == "Traceback\n"
run, _, _ = fake({"status": "captain_required", "output": ""}); p = VmProcess(run, ["x"])
assert p.wait(2) == 1 and p.read() == "[captain_required]\n"
run, _, _ = fake({"status": "blocked", "output": "no\n"}); p = VmProcess(run, ["x"])
assert p.wait(2) == 1 and p.read() == "no\n"
run, _, _ = fake(None, boom=RuntimeError("vm down")); p = VmProcess(run, ["x"])
assert p.wait(2) == 1 and p.read() == "RuntimeError: vm down\n"
run, _, _ = fake({"status": "completed", "output": "x" * 30000}); p = VmProcess(run, ["x"])
p.wait(2); out = p.read(); assert len(out) == 20000 and set(out) == {"x"}
run, _, _ = fake({"status": "completed"}); p = VmProcess(run, ["x"])
assert p.wait(2) == 0 and p.read() == ""

gate = threading.Event(); run, started, _ = fake({"status": "completed", "output": "ok\n"}, gate)
p = VmProcess(run, ["x"]); assert started.wait(2)
assert p.poll() is None and p.read() == ""
try:
    p.wait(0.05); raise AssertionError("no timeout")
except TimeoutError:
    pass
assert p.poll() is None
gate.set(); assert p.wait(2) == 0 and p.read() == "ok\n"

gate = threading.Event(); run, started, _ = fake({"status": "completed", "output": "late\n"}, gate)
p = VmProcess(run, ["x"]); assert started.wait(2)
p.terminate()
assert p.poll() == -15 and p.wait(1) == -15
gate.set(); time.sleep(0.3)
assert p.poll() == -15 and p.read() == ""
p.kill(); assert p.poll() == -9 and p.wait() == -9
p.terminate(); assert p.poll() == -9 and p.wait() == -9

gate = threading.Event(); run, started, _ = fake({"status": "completed", "output": "w\n"}, gate)
p = VmProcess(run, ["x"]); started.wait(2)
got = []
waiter = threading.Thread(target=lambda: got.append(p.wait()), daemon=True); waiter.start(); time.sleep(0.1)
p.terminate(); waiter.join(1)
assert got == [-15], got
gate.set()

gate = threading.Event(); run, started, _ = fake({"status": "completed", "output": "z\n"}, gate)
p = VmProcess(run, ["x"]); started.wait(2); p.kill()
assert p.poll() == -9 and p.wait(1) == -9
gate.set()

run, _, _ = fake({"status": "completed", "output": "done\n"}); p = VmProcess(run, ["x"]); p.wait(2)
p.terminate(); p.kill()
assert p.poll() == 0 and p.read() == "done\n"
print("ok")
'''

SPAWN = r'''
gate = threading.Event(); run, started, seen = fake({"status": "completed", "output": "a\n"}, gate)
spawn = make_spawn(run)
a, b = spawn(["x", "1"]), spawn(["x", "2"])
assert isinstance(a, VmProcess) and isinstance(b, VmProcess) and a is not b
try:
    spawn(["x", "3"]); raise AssertionError("limit")
except RuntimeError as exc:
    assert str(exc) == "too_many_processes"
gate.set(); assert a.wait(2) == 0 and b.wait(2) == 0
c = spawn(["x", "4"]); assert c.wait(2) == 0
for bad in ([], "x", ["x", 1], None):
    try:
        spawn(bad); raise AssertionError("argv")
    except ValueError as exc:
        assert str(exc) == "argv"

gate = threading.Event(); run, started, _ = fake({"status": "completed", "output": "a\n"}, gate)
quick = make_spawn(run, max_running=1)
q = quick(["x"]); q.terminate()
try:
    quick(["x"]); raise AssertionError("abandoned right after the spawn still occupies the VM")
except RuntimeError:
    pass
gate.set(); time.sleep(0.3)
assert quick(["x"]).wait(2) == 0

gate = threading.Event(); run, started, _ = fake({"status": "completed", "output": "a\n"}, gate)
one = make_spawn(run, max_running=1)
p = one(["x"]); started.wait(2); p.terminate(); time.sleep(0.3)
try:
    one(["x"]); raise AssertionError("an abandoned run still occupies the VM")
except RuntimeError:
    pass
gate.set(); time.sleep(0.3)
assert one(["x"]).wait(2) == 0

print("ok")
'''

STAGES = [
    {"name": "process",
     "task": """Create `vm_process.py` (Python 3 standard library only) with `class VmProcess`, the process object that `bg_jobs.Jobs` expects, backed by ONE blocking VM run.
- `VmProcess(run, argv)`: starts a daemon thread at once that calls `run(list(argv))` (a copy); `run` returns {"status": str, "output": str} and may raise.
- Result of the run: status "completed" -> exit code 0, any other status -> 1; output = the "output" value (missing or None counts as ""); if it is longer than 20000 characters only the LAST 20000 are kept. When the output is empty and the status is not "completed", the output is "[" + status + "]\\n". When `run` raises, the status is failed and the output is TypeName + ": " + message + "\\n" (for example "RuntimeError: vm down\\n").
- `read()`: "" while the run is going and after the run was abandoned; once finished, the output exactly once, then "" again.
- `poll()`: None while the run is going; after it ended 0 or 1 as above. After `terminate()` it is -15 at once, after `kill()` -9 at once, even while the thread still runs; a result that arrives later is thrown away.
- `terminate()` and `kill()` do nothing when the run has ended NORMALLY (its result was taken over: poll() is 0 or 1); otherwise they abandon the process. A process that was abandoned stays abandoned for good, also after its thread has ended later: `terminate()` then sets nothing new, `kill()` changes the code to -9 at any time (also when the thread has ended in the meantime), and `poll()` and `wait()` keep returning the abandon code. A `wait()` that is already blocked in another thread returns the abandon code as soon as the process is abandoned.
- `wait(timeout=None)`: waits for the thread at most timeout seconds (not at all when the process was abandoned or has ended) and returns poll(); when the run is still going afterwards it raises TimeoutError.""",
     "host_hidden": {},
     "hidden": {"hidden_vmp_1.py": HEAD + PROC}},
    {"name": "spawn",
     "task": """Add `make_spawn(run, max_running=2)` to `vm_process.py` (keep everything else): it returns a function `spawn(argv)` for `bg_jobs.Jobs`.
- `spawn(argv)`: argv must be a non-empty list of strings, else ValueError("argv"). It returns a new `VmProcess(run, argv)`.
- At most `max_running` processes of this spawner may occupy the VM at the same time; a process occupies it from its start until its thread has really ended (an abandoned process whose thread still runs counts). A further spawn raises RuntimeError("too_many_processes"), also when the process was abandoned right after the spawn. When a thread has ended, a new one may start.
- Keep what is needed to count the running processes inside the returned function's closure or an object; do not use module-level state.""",
     "hidden": {"hidden_vmp_1.py": HEAD + PROC, "hidden_vmp_2.py": HEAD + SPAWN}},
]
