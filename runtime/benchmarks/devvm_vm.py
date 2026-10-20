"""The microVM environment of a build, in ONE place (Captain 2026-10-20, line L2): devvm_build runs the hidden tests with it, spec_check --vm runs the reference with it.

vm_env(project, tool_root) writes the build's own copy of the sandbox config into tool_root and returns (broker, vm_copy). vm_copy(ws, commands, extra) copies the files of ws
(anything with tree() and read(path): a DevWorkspace or a FolderTree) plus `extra` into a fresh workspace and runs `commands` there in the microVM: {"status", "output"},
status "completed" when every command ended with exit code 0. No model, no GPU."""
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME / "src") not in sys.path:
    sys.path.insert(0, str(RUNTIME / "src"))


def sandbox_text(bg_jobs):
    """The sandbox config of this build (a copy, the shipped runtime/config/sandbox.yaml stays as it is). With --bg-jobs a VM command may run 100 s instead of 30 and a whole VM run 150 s instead of 120, so a
    background job can be longer than a normal run_python (the broker's own limits are 120 s and 600 s)."""
    text = (RUNTIME / "config" / "sandbox.yaml").read_text(encoding="utf-8")
    if not bg_jobs: return text
    for old, new in (("command_timeout_seconds: 30", "command_timeout_seconds: 100"), ("job_timeout_seconds: 120", "job_timeout_seconds: 150")):
        if old not in text: raise SystemExit(f"sandbox.yaml has no line '{old}': --bg-jobs cannot raise the VM limit")
        text = text.replace(old, new, 1)
    return text


class FolderTree:
    """A folder on the host that looks like a workspace to vm_copy (tree, read). __pycache__, .git and files that are not UTF-8 text are left out, like a build seed."""
    def __init__(self, folder):
        self.folder = Path(folder)
        self.files = {}
        if self.folder.is_dir():
            for path in sorted(self.folder.rglob("*")):
                if not path.is_file() or "__pycache__" in path.parts or ".git" in path.parts: continue
                try: self.files[path.relative_to(self.folder).as_posix()] = path.read_text(encoding="utf-8")
                except UnicodeDecodeError: continue

    def tree(self):
        return list(self.files)

    def read(self, path):
        return self.files[path]


def vm_env(project, tool_root, bg_jobs=False, mission="M-BUILD", prefix="M-CHK"):
    from guppi_runtime.devenv.devvm import DevWorkspace
    from guppi_runtime.sandbox.broker import SandboxBroker
    from guppi_runtime.sandbox.provider import MicrosandboxProvider
    tool_root = Path(tool_root)
    cfg_path = tool_root / "sandbox-build.yaml"; cfg_path.write_text(sandbox_text(bg_jobs), encoding="utf-8")
    broker = SandboxBroker(tool_root, tool_root / "sandbox-data", cfg_path, MicrosandboxProvider(Path(project) / "runtime_data" / "sandboxes" / "backend_home", RUNTIME), None, None)
    counter = {"n": 0}

    def vm_copy(ws, commands, extra):
        counter["n"] += 1
        copy = DevWorkspace(tool_root, f"{prefix}{counter['n']:05d}", policy=broker.policy()); copy.create()
        for path in ws.tree(): copy.write(path, ws.read(path))
        for path, text in extra.items(): copy.write(path, text)
        try:
            out = broker._run(mission, copy.vm_preview(broker, commands))
        except Exception as exc:
            return {"status": "failed", "output": f"{type(exc).__name__}: {exc}"}
        rec = out.get("sandbox") or {}
        return {"status": out["status"], "output": "\n".join(c.get("output", "") for c in rec.get("commands", []))}

    return broker, vm_copy
