"""The microVM runner for acceptance suites: runs files and commands in the sandbox and returns {"status", "output"} like `acceptance_suite.host_runner`, so a CANDIDATE built by a model
never runs on the host. Same broker, image and limits as the DevVM judge (`benchmarks/devvm_build.py`); one VM per command list. A VM that does not start (about 2 of 8 starts failed in
the measurements of 2026-10-05) is tried again; a result that is not `completed` or `failed` after the tries stays `not_run`, never a guess."""
import os
import tempfile
from pathlib import Path

from ..devenv.devvm import DevWorkspace
from ..sandbox.broker import SandboxBroker
from ..sandbox.provider import MicrosandboxProvider


def vm_runner(project_dir, runtime_dir, attempts=3, mission="M-ACCEPT"):
    runtime, project = Path(runtime_dir), Path(project_dir)
    tool_root = Path(tempfile.mkdtemp(prefix="guppi_acceptance_"))
    config = tool_root / "sandbox-acceptance.yaml"
    config.write_text((runtime / "config" / "sandbox.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    broker = SandboxBroker(tool_root, tool_root / "sandbox-data", config, MicrosandboxProvider(project / "runtime_data" / "sandboxes" / "backend_home", runtime), None, None)
    counter = {"n": 0}

    def run(files, commands):
        result = {"status": "not_run", "output": ""}
        for _ in range(max(1, attempts)):
            counter["n"] += 1
            workspace = DevWorkspace(tool_root, f"M-ACC{counter['n']:05d}", policy=broker.policy())
            workspace.create()
            for name, text in files.items():
                workspace.write(name, text)
            try:
                out = broker._run(mission, workspace.vm_preview(broker, commands))
            except Exception as exc:
                result = {"status": "not_run", "output": f"{type(exc).__name__}: {exc}"}
                continue
            record = out.get("sandbox") or {}
            result = {"status": out.get("status", "not_run"), "output": "\n".join(c.get("output", "") for c in record.get("commands", []))}
            if result["status"] in ("completed", "failed"):
                return result
        return result
    return run
