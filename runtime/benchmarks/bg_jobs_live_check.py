r"""Live check of the coder's background job tools (E-06/E-10 with vm_process) against the REAL microVM, without a model and without the GPU (Captain 2026-10-13).

    .venv\Scripts\python.exe benchmarks/bg_jobs_live_check.py <project_dir>

It builds the same VM environment as devvm_build.py (broker, MicrosandboxProvider, a throw-away workspace under runtime_data/devvm_work) and lets a DevToolBox call shell_start, shell_log and
shell_stop the way the coder would. The VM runs only inside the throw-away workspace copy. Needs the TestLab GPU lease? No: the VM does not use the GPU. Result: JSON lines on stdout, exit 0
when every step behaved, 1 otherwise.
"""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.devenv.devvm import DevWorkspace                       # noqa: E402
from guppi_runtime.devenv.devvm_agents import make_jobs                    # noqa: E402
from guppi_runtime.devenv.devvm_tools import DevToolBox                    # noqa: E402
from guppi_runtime.sandbox.broker import SandboxBroker              # noqa: E402
from guppi_runtime.sandbox.provider import MicrosandboxProvider    # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from devvm_build import sandbox_text                                # noqa: E402

LONG = "import time\nprint('long start', flush=True)\ntime.sleep(40)\nprint('LONG DONE', flush=True)\n"
SCRIPT = "import time\nfor i in range(3):\n    print('step', i, flush=True)\n    time.sleep(0.5)\nprint('ready', flush=True)\n"


def main():
    project = Path(sys.argv[1])
    work_root = project / "runtime_data" / "devvm_work"; work_root.mkdir(parents=True, exist_ok=True)
    tool_root = Path(tempfile.mkdtemp(prefix="build_livecheck_", dir=work_root))
    steps, ok = [], True

    def step(name, passed, detail=""):
        nonlocal ok
        ok = ok and passed
        steps.append({"step": name, "ok": bool(passed), "detail": str(detail)[:300]}); print(json.dumps(steps[-1], ensure_ascii=False), flush=True)

    try:
        cfg = tool_root / "sandbox-build.yaml"; cfg.write_text(sandbox_text(True), encoding="utf-8")      # the same raised limits as devvm_build --bg-jobs
        broker = SandboxBroker(tool_root, tool_root / "sandbox-data", cfg, MicrosandboxProvider(project / "runtime_data" / "sandboxes" / "backend_home", RUNTIME), None, None)
        ws = DevWorkspace(tool_root, "M-LIVE0001", policy=broker.policy()); ws.create()
        ws.write("slow.py", SCRIPT)
        counter = {"n": 0}

        def runner(commands):
            counter["n"] += 1
            copy = DevWorkspace(tool_root, f"M-LIVC{counter['n']:04d}", policy=broker.policy()); copy.create()
            for path in ws.tree(): copy.write(path, ws.read(path))
            try: out = broker._run("M-LIVE", copy.vm_preview(broker, commands))
            except Exception as exc: return {"status": "failed", "output": f"{type(exc).__name__}: {exc}"}
            rec = out.get("sandbox") or {}
            return {"status": out["status"], "output": "\n".join(c.get("output", "") for c in rec.get("commands", []))}

        box = DevToolBox(ws, "solo", vm_runner=runner, jobs=make_jobs({"bg_jobs": True}, runner), max_calls=400)
        step("tools offered", all(n in box.names for n in ("shell_start", "shell_log", "shell_stop")), box.names)
        started = box.call("shell_start", {"command": "python3 slow.py", "wake_match": "ready"})
        step("shell_start", started.startswith("started J1"), started)
        woke, deadline = started, time.time() + 150
        while "woke you" not in woke and time.time() < deadline:
            time.sleep(1.0); woke = box.call("list_dir", {})
        step("woken by the job", "match: ready" in woke or "exit: 0" in woke, woke.replace("\n", " | "))
        log = box.call("shell_log", {"job": "J1", "tail": 10})
        step("log has the output", "step 0" in log and "ready" in log, log.replace("\n", " | "))
        step("stop after the end is harmless", box.call("shell_stop", {"job": "J1"}).startswith("stopped J1"))
        bad = box.call("shell_start", {"command": "python3 nothere.py"})
        again = ""
        for _ in range(60):
            time.sleep(1.0); again = bad + box.call("list_dir", {})
            if "woke you" in again: break
        step("a failing command wakes with exit 1", "exit: 1" in again, again.replace("\n", " | "))
        piped = box.call("shell_start", {"command": "cat slow.py | head -n 2 > out.txt && cat out.txt && echo files: $(ls | wc -l)"})
        waited = box.call("shell_log", {"job": "J3", "wait": 20})
        step("a shell line with pipe, redirect and && runs with sh -c", piped.startswith("started J3") and "import time" in waited and "files:" in waited, waited.replace(chr(10), " | "))
        step("what the command wrote is not in the workspace", "out.txt" not in ws.tree(), ws.tree())
        ws.write("long.py", LONG)
        began = time.time()
        started = box.call("shell_start", {"command": "python3 long.py", "wake_match": "LONG DONE"})
        woke, deadline = started, time.time() + 170
        while "woke you" not in woke and time.time() < deadline:
            time.sleep(2.0); woke = box.call("search_text", {"text": f"poll {time.time()}"})
        step("a job longer than 30 s survives", "LONG DONE" in woke and time.time() - began > 35, f"{round(time.time() - began)} s: " + woke.replace(chr(10), " | "))
    except Exception as exc:
        step("unexpected error", False, f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(tool_root, ignore_errors=True)
    print(json.dumps({"all_ok": ok, "steps": len(steps)}), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
