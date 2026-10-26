"""Before a test run: nothing from an earlier run may still sit on the GPU or on GUPPI's llama-server port.

Why: a run that crashed (or was stopped) leaves its llama-server behind. The next run then fails with `port_in_use:8089`, or - worse - measures
against a card that is already half full (seen on 2026-10-02: 8 GB used by a leftover, so prompt processing dropped from 250 to 20 tokens/s).

What it does, in this order, only while the caller holds the GPU lease (so nobody else's cooperating run can be hit):
  1. a process listening on GUPPI's port that is a GUPPI-started llama-server is stopped. Anything else on that port is NOT touched: the run is
     refused with the name of the process.
  2. other llama-server processes that carry GUPPI's start signature (`--no-webui` and `--spec-type`, which LM Studio's own engine does not use)
     are orphans of earlier runs and are stopped too.
  3. the used VRAM is read. If it does not fall below `baseline_max_gb` within `settle_s`, the run is refused and the processes that use the
     GPU are listed (a game, LM Studio with a model loaded, a forgotten run). Nothing outside GUPPI's own llama-server is ever stopped.

A llama-server that the model scheduler owns is never a leftover (Spec 2, D2.7, B-6): its pid stands in `slot_server.pid` of the test lab while the
server is starting, ready or draining. Such a pid is spared; if it sits on the port, the run is refused with the owner named.

Use as a hook: `lab.lease(owner, purpose, preflight=clear_leftovers)`, or from the shell: `python benchmarks/testlab_cli.py clean`.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

GUPPI_SIGNATURE = ("--no-webui", "--spec-type")      # always present in llama_server_runtime.build_command, never in LM Studio's own launches
BACKEND_MARKER = "\\.lmstudio\\extensions\\backends\\"
OWN_ENGINE_MARKER = "\\engines\\llama.cpp\\"          # GUPPI's own engine (engine_provision.py, since 2026-10-03)


class GpuNotClean(Exception):
    """The GPU or the port is in a state this module must not fix by itself. The message names the cause."""


def _powershell(script, run=subprocess.run):
    """The PowerShell inventory of this PC. Off Windows there is none: an empty answer, so callers see "no processes" (start for Mac users, 2026-10-14).
    A `run` passed in by a test is always used (the tests fake PowerShell on every platform)."""
    if run is subprocess.run and sys.platform != "win32":
        return ""
    out = run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    return (out.stdout or "").strip()


def listener_pid(port, run=subprocess.run):
    text = _powershell(f"(Get-NetTCPConnection -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess", run)
    return int(text) if text.isdigit() else None


def process_info(pid, run=subprocess.run):
    text = _powershell(f"Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}' | Select-Object Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress", run)
    try:
        data = json.loads(text) if text else None
    except ValueError:
        return None
    return {"name": data.get("Name") or "", "path": data.get("ExecutablePath") or "", "cmd": data.get("CommandLine") or ""} if data else None


def guppi_llama_servers(run=subprocess.run):
    """pid -> info of every llama-server.exe that GUPPI started (backend folder of LM Studio plus GUPPI's start signature)."""
    text = _powershell("Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | Select-Object ProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress", run)
    if not text:
        return {}
    data = json.loads(text)
    data = data if isinstance(data, list) else [data]
    found = {}
    for item in data:
        info = {"name": item.get("Name") or "", "path": item.get("ExecutablePath") or "", "cmd": item.get("CommandLine") or ""}
        if is_guppi_server(info):
            found[int(item["ProcessId"])] = info
    return found


def is_guppi_server(info):
    path = info["path"].lower().replace("/", "\\") if info else ""
    return bool(info) and info["name"].lower() == "llama-server.exe" and (BACKEND_MARKER in path or OWN_ENGINE_MARKER in path) \
        and all(flag in info["cmd"] for flag in GUPPI_SIGNATURE)


def vram_used_gb(run=subprocess.run):
    out = run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30)
    return round(int(out.stdout.split()[0]) / 1024, 2)


def gpu_users(run=subprocess.run):
    out = run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"], capture_output=True, text=True, timeout=30)
    return [line.strip() for line in (out.stdout or "").splitlines() if line.strip()][:8]


def _stop(pid, run=subprocess.run):
    if sys.platform == "win32":
        run(["taskkill", "/F", "/PID", str(int(pid))], capture_output=True, text=True, timeout=30)
    else:
        run(["kill", "-TERM", str(int(pid))], capture_output=True, text=True, timeout=30)


def scheduler_server_pids(lab):
    """The pids of the llama-server that the model scheduler runs now (`slot_server.pid` while its state is startet/bereit/drain). Empty when
    the lab has no schema 2 or nothing runs. Reads only."""
    if lab is None or getattr(lab, "schema", 1) < 2:
        return set()
    try:
        conn = lab.connect()
        try:
            row = conn.execute("SELECT pid, state FROM slot_server WHERE name = 'main'").fetchone()
        finally:
            conn.close()
    except Exception:
        return set()
    if row is None or row["pid"] is None or row["state"] not in ("startet", "bereit", "drain"):
        return set()
    return {int(row["pid"])}


def clear_leftovers(owner="", *, port=8089, baseline_max_gb=3.0, settle_s=20, say=print, run=subprocess.run, sleep=time.sleep, monotonic=time.monotonic,
                    lab=None, protected=()):
    """Stops what earlier runs left behind and refuses the run when the card is still busy. Returns the VRAM in GiB that is in use afterwards.
    `protected`: pids that are never stopped; with `lab` (given by `TestLab.lease`) the scheduler's server pid is added (B-6)."""
    stopped = []
    spared = {int(p) for p in protected} | scheduler_server_pids(lab)
    pid = listener_pid(port, run)
    if pid in spared:
        raise GpuNotClean(f"port {port} is used by the model scheduler's llama-server (pid {pid}); it holds a live slot lease and is not stopped")
    if pid:
        info = process_info(pid, run)
        if not is_guppi_server(info):
            raise GpuNotClean(f"port {port} is used by {(info or {}).get('name', 'pid ' + str(pid))} (pid {pid}), which is not a GUPPI llama-server; not touching it")
    targets = {t: i for t, i in guppi_llama_servers(run).items() if t not in spared}
    if pid and pid not in targets:
        targets[pid] = process_info(pid, run)
    for target, info in targets.items():
        say(f"preflight: stopping leftover llama-server pid {target} ({_alias(info)})")
        _stop(target, run)
        stopped.append(target)
    deadline = monotonic() + settle_s
    while True:
        used = vram_used_gb(run)
        if used <= baseline_max_gb:
            if stopped:
                say(f"preflight: {len(stopped)} leftover server(s) stopped, GPU at {used} GiB")
            return used
        if monotonic() >= deadline:
            raise GpuNotClean(f"GPU holds {used} GiB (limit {baseline_max_gb}) and it is not a GUPPI llama-server; in use by: {'; '.join(gpu_users(run)) or 'unknown'}")
        sleep(1)


clear_leftovers.wants_lab = True        # TestLab.lease then passes itself as `lab`


def _alias(info):
    parts = (info or {}).get("cmd", "").split()
    return parts[parts.index("--alias") + 1] if "--alias" in parts else "?"
