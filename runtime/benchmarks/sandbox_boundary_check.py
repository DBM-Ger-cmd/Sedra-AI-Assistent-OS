"""Collect evidence for the sandbox boundary acceptance (PC-03 isolation, PC-07 cleanup) on THIS PC. A measurement, not a test.

    .venv\\Scripts\\python.exe benchmarks/sandbox_boundary_check.py <project_dir>

It starts GUPPI's own microVM through the same code the worker uses (`worker.run_job`, same policy from config/sandbox.yaml:
no network, RESTRICTED profile, tmpfs root, pull policy NEVER, guest user 65534) with a small probe as the only source. The probe
looks for a host sentinel, tries the network and host services, reads the environment, mounts, limits and the hypervisor identity.
A second command sleeps past the command timeout. Afterwards the sandbox list is read to confirm the VM is gone.

It never changes `target_qualified`: the report is evidence for the Captain, who decides. Results go to
<project>/runtime_data/acceptance/sandbox_boundary_<UTC time>.json.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

PROBE = r'''
import json, os, socket, time, resource
out = {}
token = os.environ.get("NO_TOKEN_HERE")  # the sentinel token is never passed in; it is only searched for
SENTINEL = "__SENTINEL__"
out["uname"] = " ".join(os.uname())
out["uid"] = os.getuid()
try: out["hypervisor_flag"] = "hypervisor" in open("/proc/cpuinfo").read()
except Exception as e: out["hypervisor_flag"] = repr(e)
try: out["mounts"] = open("/proc/mounts").read().splitlines()
except Exception as e: out["mounts"] = repr(e)
try: out["mem_total_kb"] = int([l for l in open("/proc/meminfo") if l.startswith("MemTotal")][0].split()[1])
except Exception as e: out["mem_total_kb"] = repr(e)
out["cpu_count"] = os.cpu_count()
out["env"] = sorted(os.environ)
try: out["net_dev"] = [l.split(":")[0].strip() for l in open("/proc/net/dev").read().splitlines()[2:]]
except Exception as e: out["net_dev"] = repr(e)
try: out["routes"] = open("/proc/net/route").read().splitlines()[1:]
except Exception as e: out["routes"] = repr(e)
def tcp(host, port):
    s = socket.socket(); s.settimeout(3)
    try: s.connect((host, port)); return "CONNECTED"
    except Exception as e: return type(e).__name__ + ":" + str(e)[:60]
    finally: s.close()
out["tcp"] = {f"{h}:{p}": tcp(h, p) for h, p in [("1.1.1.1", 53), ("8.8.8.8", 443), ("10.0.2.2", 8089), ("10.0.2.2", 445),
                                                 ("192.168.65.1", 445), ("172.17.0.1", 8089), ("127.0.0.1", 8089), ("127.0.0.1", 1234)]}
DNS_NAME = "__DNSNAME__"   # unique per run, so a host-side capture can prove whether any query left the machine
try: out["dns"] = str(socket.getaddrinfo(DNS_NAME, 443)[:1])
except Exception as e: out["dns"] = type(e).__name__ + ":" + str(e)[:60]
import struct
qname = b"".join(bytes([len(l)]) + l.encode() for l in DNS_NAME.split(".")) + b"\x00"
query = b"\x47\x50\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + qname + b"\x00\x01\x00\x01"
raw = {}
for srv in ("1.1.1.1", "8.8.8.8", "9.9.9.9"):
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.settimeout(3)
    try: u.sendto(query, (srv, 53)); raw["udp " + srv] = "ANSWER %d bytes" % len(u.recv(512))
    except Exception as e: raw["udp " + srv] = type(e).__name__
    finally: u.close()
    t = socket.socket(); t.settimeout(3)
    try: t.connect((srv, 53)); t.sendall(struct.pack(">H", len(query)) + query); raw["tcp " + srv] = "ANSWER %d bytes" % len(t.recv(512))
    except Exception as e: raw["tcp " + srv] = type(e).__name__
    finally: t.close()
out["dns_raw_queries"] = raw
hits, scanned, started = [], 0, time.time()
for root, dirs, files in os.walk("/", onerror=lambda e: None):
    if root.startswith(("/proc", "/sys", "/dev")): dirs[:] = []; continue
    for f in files:
        p = os.path.join(root, f)
        try:
            if os.path.islink(p) or os.path.getsize(p) > 262144: continue
            with open(p, "rb") as fh:
                if SENTINEL.encode() in fh.read(): hits.append(p)
            scanned += 1
        except Exception: pass
    if time.time() - started > 20: out["sentinel_scan_truncated"] = True; break
out["sentinel_hits"] = [h for h in hits if not h.startswith("/workspace")]
out["sentinel_scanned_files"] = scanned
def write(path):
    try:
        with open(path, "w") as fh: fh.write("x")
        return "WRITTEN"
    except Exception as e: return type(e).__name__
out["write"] = {p: write(p) for p in ("/etc/guppi_probe", "/usr/guppi_probe", "/tmp/guppi_probe", "/workspace/guppi_probe",
                                     "/.msb/guppi_probe", "/.msb/rootfs/upperfs/guppi_probe", "/.msb/scripts/guppi_probe")}
out["rlimit_nproc"] = resource.getrlimit(resource.RLIMIT_NPROC)
children, err = 0, None
pids = []
try:
    for _ in range(200):
        pid = os.fork()
        if pid == 0: time.sleep(5); os._exit(0)
        pids.append(pid); children += 1
except Exception as e: err = type(e).__name__
out["fork"] = {"started": children, "stopped_by": err}
for pid in pids:
    try: os.kill(pid, 9); os.waitpid(pid, 0)
    except Exception: pass
print("PROBE_JSON=" + json.dumps(out))
'''


def run(project: Path):
    from guppi_runtime.sandbox.provider import MicrosandboxProvider
    from guppi_runtime.sandbox.broker import SandboxBroker
    import yaml

    policy = yaml.safe_load((RUNTIME / "config" / "sandbox.yaml").read_text(encoding="utf-8"))["sandbox"]
    data = project / "runtime_data"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work = Path(tempfile.mkdtemp(prefix="guppi_boundary_"))
    sentinel_token = "GUPPI-SENTINEL-" + secrets.token_hex(12)
    # The sentinel lives on the host only: next to the source, in the job root and in the project. The guest must not find it.
    sentinel_files = [work / "host_sentinel.txt", project / "runtime_data" / "acceptance" / f"sentinel_{stamp}.txt"]
    for f in sentinel_files:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(sentinel_token, encoding="utf-8")
    source = work / "source"; source.mkdir()
    dns_name = f"gp{secrets.token_hex(8)}.guppi-boundary.example.com"
    (source / "probe.py").write_text(PROBE.replace("__SENTINEL__", sentinel_token).replace("__DNSNAME__", dns_name), encoding="utf-8")
    job_root = work / "job"; job_root.mkdir()
    request = {"job_id": "boundary-" + stamp.lower(), "policy": policy, "source": str(source), "job_root": str(job_root),
               "commands": [["python3", "/workspace/probe.py"], ["/bin/sleep", str(int(policy["command_timeout_seconds"]) + 15)]],
               "exports": []}
    provider = MicrosandboxProvider(data / "sandboxes" / "backend_home", RUNTIME)
    started = time.time()
    result = provider._execute_worker("run", request, job_root)
    seconds = round(time.time() - started, 1)
    # Independent inventory: list sandboxes with the same home after the worker has returned.
    inventory = subprocess.run([sys.executable, "-I", "-B", "-c", LIST_SANDBOXES], env=provider.environment(job_root),
                               capture_output=True, text=True, timeout=60)
    probe = None
    for cmd in result.get("commands", []):
        for line in (cmd.get("output") or "").splitlines():
            if line.startswith("PROBE_JSON="):
                probe = json.loads(line[len("PROBE_JSON="):])
    report = {"schema": 1, "kind": "sandbox_boundary_evidence", "created_at": stamp, "seconds": seconds, "dns_probe_name": dns_name,
              "policy": policy, "worker_status": result.get("status"), "worker_error": result.get("error"),
              "cleanup_confirmed": result.get("cleanup_confirmed"),
              "commands": [{"argv": c.get("argv"), "exit_code": c.get("exit_code"), "success": c.get("success")} for c in result.get("commands", [])],
              "probe": probe, "sandbox_inventory_after": (inventory.stdout or inventory.stderr).strip()[-2000:],
              "checks": checks(probe, result, inventory.stdout, policy),
              "target_qualified_changed": False}
    out = data / "acceptance" / f"sandbox_boundary_{stamp}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for f in sentinel_files:
        f.unlink(missing_ok=True)
    return out, report


LIST_SANDBOXES = r'''
import asyncio, microsandbox as sdk
from microsandbox._runtime import msb_path
sdk.set_default_backend(sdk.BackendKind.LOCAL)
sdk._microsandbox.set_runtime_msb_path(str(msb_path()))
sdk.set_libkrunfw_path(str([p for p in (msb_path().parent.parent/"lib").iterdir() if "krunfw" in p.name][0]))
async def m():
    page = await sdk.Sandbox.list()
    items = getattr(page, "items", None) or getattr(page, "sandboxes", None) or page
    print("SANDBOXES=" + repr(items))
asyncio.run(m())
'''


def checks(probe, result, inventory, policy):
    """Each check is PASS / FAIL / NO_EVIDENCE. NO_EVIDENCE is never a pass."""
    c = {}
    if not probe:
        return {"probe_ran": "FAIL"}
    c["guest_runs_unprivileged"] = "PASS" if probe.get("uid") == 65534 else "FAIL"
    c["host_sentinel_not_visible"] = "PASS" if probe.get("sentinel_hits") == [] and probe.get("sentinel_scanned_files", 0) > 100 else "FAIL"
    mounts = probe.get("mounts") or []
    shares = [m for m in mounts if any(k in m.lower() for k in ("9p", "virtiofs", "drvfs", "smb", "cifs"))] if isinstance(mounts, list) else ["unreadable"]
    # microsandbox always shares the sandbox's own runtime folder (`msb_runtime` at /.msb, rw). Any other host share is a failure.
    c["no_host_share_except_sandbox_runtime"] = "PASS" if all(m.startswith("msb_runtime /.msb ") for m in shares) else f"FAIL:{shares}"
    # The share itself stays rw (the VM's own overlay lives there); what counts is whether the guest user can write into it.
    w0 = probe.get("write") or {}
    msb_writes = {k: v for k, v in w0.items() if k.startswith("/.msb/")}
    c["runtime_share_not_writable_by_guest"] = "PASS" if msb_writes and all(v != "WRITTEN" for v in msb_writes.values()) else f"FAIL:{msb_writes}"
    tcp = probe.get("tcp") or {}
    other = {k: v for k, v in tcp.items() if not k.endswith(":53")}
    c["no_tcp_to_internet_or_host_services"] = "PASS" if other and not any(v == "CONNECTED" for v in other.values()) else f"FAIL:{other}"
    c["no_name_resolution"] = "PASS" if str(probe.get("dns", "")).startswith(("gaierror", "OSError")) else "FAIL"
    # Port 53 is answered by the SDK's own network stack even with Network.none(); whether queries leave the host needs a
    # host-side capture (PC-03 evidence "network capture"), so this stays a finding, never a pass.
    c["FINDING_port_53_reachable"] = "FINDING" if any(v == "CONNECTED" for k, v in tcp.items() if k.endswith(":53")) else "PASS"
    # The image's own variables are public (GPG_KEY is the CPython release key fingerprint), not host secrets.
    image_env = {"GPG_KEY", "PYTHON_SHA256", "PYTHON_VERSION"}
    leaked = [k for k in probe.get("env", []) if k not in image_env and any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD", "PROXY", "USERPROFILE", "APPDATA"))]
    c["no_host_secrets_in_env"] = "PASS" if not leaked else f"FAIL:{leaked}"
    w = probe.get("write") or {}
    c["system_dirs_read_only"] = "PASS" if w.get("/etc/guppi_probe") != "WRITTEN" and w.get("/usr/guppi_probe") != "WRITTEN" else "FAIL"
    c["workspace_writable"] = "PASS" if w.get("/workspace/guppi_probe") == "WRITTEN" else "FAIL"
    mem = probe.get("mem_total_kb")
    c["memory_limited"] = "PASS" if isinstance(mem, int) and mem <= policy["memory_mib"] * 1024 * 1.1 else f"FAIL:{mem}"
    c["cpu_limited"] = "PASS" if isinstance(probe.get("cpu_count"), int) and probe["cpu_count"] <= policy["cpus"] else f"FAIL:{probe.get('cpu_count')}"
    fork = probe.get("fork") or {}
    c["process_limit_enforced"] = "PASS" if fork.get("started", 999) <= policy["max_processes"] else f"FAIL:{fork}"
    c["runs_in_a_vm"] = "PASS" if probe.get("hypervisor_flag") is True else "NO_EVIDENCE"
    cmds = result.get("commands", [])
    c["command_timeout_enforced"] = "PASS" if len(cmds) >= 2 and not cmds[1].get("success") else "FAIL"
    c["cleanup_confirmed_by_worker"] = "PASS" if result.get("cleanup_confirmed") is True else "FAIL"
    c["no_sandbox_left_behind"] = "PASS" if "guppi-boundary" not in (inventory or "") and "SANDBOXES=" in (inventory or "") else "NO_EVIDENCE"
    return c


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    path, rep = run(Path(sys.argv[1]).resolve())
    print(json.dumps({"report": str(path), "dns_probe_name": rep["dns_probe_name"], "worker_status": rep["worker_status"], "worker_error": rep["worker_error"],
                      "seconds": rep["seconds"], "checks": rep["checks"]}, indent=2, ensure_ascii=False))
