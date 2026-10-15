r"""How long does one VM run take, and what does a run keep? (Captain 2026-10-13: work on the VM and the shell.) No model, no GPU.

    .venv\Scripts\python.exe benchmarks/vm_latency.py <project_dir> [<runs>]

Builds the same VM environment as devvm_build.py (own copy of the sandbox config), then times N runs of a trivial command, one run with a few commands in ONE plan, a run that writes a file
(does it stay in the workspace?) and a run with a shell line (`sh -c`). Prints JSON lines; exit 0.
"""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.devvm import DevWorkspace                       # noqa: E402
from guppi_runtime.sandbox.broker import SandboxBroker              # noqa: E402
from guppi_runtime.sandbox.provider import MicrosandboxProvider    # noqa: E402


def main():
    project = Path(sys.argv[1]); runs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    work_root = project / "runtime_data" / "devvm_work"; work_root.mkdir(parents=True, exist_ok=True)
    tool_root = Path(tempfile.mkdtemp(prefix="build_latency_", dir=work_root))
    try:
        cfg = tool_root / "sandbox-build.yaml"; cfg.write_text((RUNTIME / "config" / "sandbox.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        broker = SandboxBroker(tool_root, tool_root / "sandbox-data", cfg, MicrosandboxProvider(project / "runtime_data" / "sandboxes" / "backend_home", RUNTIME), None, None)
        ws = DevWorkspace(tool_root, "M-LAT00001", policy=broker.policy()); ws.create(); ws.write("a.py", "print('hi')\n")
        counter = {"n": 0}

        def run(commands, label):
            counter["n"] += 1
            copy = DevWorkspace(tool_root, f"M-LATC{counter['n']:04d}", policy=broker.policy()); copy.create()
            for path in ws.tree(): copy.write(path, ws.read(path))
            t0 = time.monotonic()
            try: out = broker._run("M-LAT", copy.vm_preview(broker, commands)); status = out["status"]; rec = out.get("sandbox") or {}
            except Exception as exc: status, rec = f"{type(exc).__name__}: {exc}"[:200], {}
            seconds = round(time.monotonic() - t0, 2)
            output = "\n".join(c.get("output", "") for c in rec.get("commands", []))
            print(json.dumps({"run": label, "seconds": seconds, "status": status, "output": output[:200], "copy_files_after": copy.tree()}, ensure_ascii=False), flush=True)
            return seconds

        times = [run([["python3", "a.py"]], f"trivial {i + 1}") for i in range(runs)]
        three = run([["python3", "a.py"], ["python3", "a.py"], ["python3", "a.py"]], "three commands in one plan")
        run([["python3", "-c", "open('made.txt','w').write('x')"]], "writes a file")
        run([["sh", "-c", "echo one | tr a-z A-Z && echo two > t.txt && cat t.txt"]], "shell line via sh -c")
        print(json.dumps({"mean_trivial_s": round(sum(times) / len(times), 2), "three_commands_s": three}), flush=True)
    finally:
        shutil.rmtree(tool_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
