"""Real runtime port for the bridge (integration stage 5): a run is one DevVM build of a named spec, started as a detached worker process.

Same contract as the fake runtime: `start(run_id, assignment)` and `inspect(run_id)`. Nothing free-form gets in: the only input is the NAME of a spec in `benchmarks/devvm_specs`
(letters, digits, underscore), the seed folder is looked up by that name under `runtime_data/agent_manager/seeds/`, and the worker runs the existing `benchmarks/devvm_build.py`
(GPU lease, microVM judge, candidate export, run log), so no model code ever runs on the host. A run id is used once: starting it again is refused.

Outcomes: a start that is refused before anything exists raises `RefusedStart` (certainly not started). The worker writes `done.json` when it ends; a running worker is `running`;
a worker that vanished without `done.json` is `unknown`, never `failed`.
"""
import ctypes
import json
import os
import re
import subprocess
import sys

SPEC_NAME = re.compile(r"[a-z][a-z0-9_]{2,40}")
RUN_ID = re.compile(r"run-[0-9a-f]{12}")
STILL_ACTIVE = 259


class RefusedStart(ConnectionRefusedError):
    pass


def process_alive(pid):
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    code = ctypes.c_ulong()
    kernel.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel.CloseHandle(handle)
    return code.value == STILL_ACTIVE


def process_command_line(pid):
    """The command line of a process (PowerShell on Windows, /proc elsewhere), or None when it cannot be read."""
    pid = int(pid)
    if os.name != "nt":
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as handle:
                return handle.read().replace(b"\x00", b" ").decode("utf-8", "replace")
        except OSError:
            return None
    try:
        done = subprocess.run(["powershell.exe", "-NoProfile", "-Command", f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None


def process_belongs_to(pid, run_id):
    """True only when the process with this PID is the worker of this run (its command line names the run). A PID that was reused by another program, or a changed pid file, never counts."""
    line = process_command_line(pid)
    return bool(line) and "run_worker" in line and run_id in line


def kill_process_tree(pid):
    """Ends this process and everything it started (the worker, its build and the model server), by PID only; never by name."""
    if os.name == "nt":
        return subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True).returncode == 0
    os.kill(int(pid), 15)
    return True


class DevVmRuntime:
    demo = False

    def __init__(self, runtime_dir, project_dir, python=None, popen=subprocess.Popen, alive=process_alive, kill_tree=None, owns=process_belongs_to):
        self.runtime_dir, self.project_dir = str(runtime_dir), str(project_dir)
        self.python, self.popen, self.alive = python or sys.executable, popen, alive
        self.kill_tree = kill_tree or kill_process_tree
        self.owns = owns      # (pid, run_id) -> is that process really the worker of this run? checked before anything is called running or killed (hardening 2026-10-09)
        self.runs = os.path.join(self.project_dir, "runtime_data", "agent_manager", "runs")

    def start(self, run_id, assignment):
        spec = assignment.get("input_ref")
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise RefusedStart("bad run id")
        known = isinstance(spec, str) and SPEC_NAME.fullmatch(spec) and (os.path.isfile(os.path.join(self.runtime_dir, "benchmarks", "devvm_specs", spec + ".py"))
                                                                     or (spec.startswith("probe_") and os.path.isfile(os.path.join(self.runtime_dir, "benchmarks", "probes", spec[len("probe_"):] + "_probe.py"))))
        if not known:
            raise RefusedStart("input_ref must be the name of a spec in benchmarks/devvm_specs or a probe_<name> in benchmarks/probes")
        run_dir = os.path.join(self.runs, run_id)
        try:
            os.makedirs(run_dir)
        except FileExistsError:
            raise RefusedStart("this run id was already used") from None
        request = {"run_id": run_id, "spec": spec, "agent_ref": assignment.get("agent_ref"), "mission_id": assignment.get("mission_id")}
        with open(os.path.join(run_dir, "request.json"), "w", encoding="utf-8") as handle:
            json.dump(request, handle)
        env = {**os.environ, "PYTHONPATH": os.path.join(self.runtime_dir, "src"), "TESTLAB_OWNER": f"agent_manager:{run_id}"}
        flags = (0x00000008 | 0x00000200) if os.name == "nt" else 0
        with open(os.path.join(run_dir, "worker.log"), "wb") as log:
            process = self.popen([self.python, "-m", "guppi_runtime.agent_manager.run_worker", run_dir, self.runtime_dir, self.project_dir], cwd=self.runtime_dir, env=env,
                                 stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
        with open(os.path.join(run_dir, "pid"), "w", encoding="ascii") as handle:
            handle.write(str(process.pid))

    def inspect(self, run_id):
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            return "unknown"
        run_dir = os.path.join(self.runs, run_id)
        done = self._read(os.path.join(run_dir, "done.json"))
        if done is not None:
            return "succeeded" if done.get("state") == "succeeded" else "failed"
        pid = self._read(os.path.join(run_dir, "pid"), raw=True)
        if pid and pid.isdigit() and self.alive(int(pid)) and self.owns(int(pid), run_id):
            return "running"
        return "unknown"

    def stop(self, run_id, reason):
        """Stops a run on request: ends the recorded worker tree by PID and writes the known outcome (state failed, stopped true, with the reason). Returns True when something was running."""
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise RefusedStart("bad run id")
        run_dir = os.path.join(self.runs, run_id)
        if self._read(os.path.join(run_dir, "done.json")) is not None:
            return False
        pid = self._read(os.path.join(run_dir, "pid"), raw=True)
        if pid is None:
            return False
        running = bool(pid.isdigit() and self.alive(int(pid)))
        foreign = running and not self.owns(int(pid), run_id)
        if running and not foreign:
            self.kill_tree(int(pid))
        elif foreign:
            reason = f"{reason} (the recorded PID {pid} belongs to another program: nothing was ended)"
            running = False
        done = {"state": "failed", "stopped": True, "reason": str(reason)[:300], "exit_code": None, "hidden_passed": False, "candidate": None}
        temporary = os.path.join(run_dir, "done.json.tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(done, handle)
        os.replace(temporary, os.path.join(run_dir, "done.json"))
        return running

    def result(self, run_id):
        return self._read(os.path.join(self.runs, run_id, "done.json")) if RUN_ID.fullmatch(run_id or "") else None

    @staticmethod
    def _read(path, raw=False):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            return None
        if raw:
            return text.strip()
        try:
            return json.loads(text)
        except ValueError:
            return None
