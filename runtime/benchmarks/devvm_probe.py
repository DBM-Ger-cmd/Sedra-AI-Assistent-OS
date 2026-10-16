r"""Phase 0 of the DevVM mission (docs/DEVVM_AUFTRAG_2026-10-05.md): what is GUPPI's microVM as a developer environment? A measurement, nothing is changed.

    .venv\Scripts\python.exe benchmarks/devvm_probe.py <project_dir> [--starts 8]

Runs through the same code as the sandbox worker (`MicrosandboxProvider._execute_worker`, policy from config/sandbox.yaml: no network, RESTRICTED, tmpfs root, guest user 65534).
  starts      N minimal jobs: wall time and failures (VM starts failed about 2 in 8 on 2026-10-02)
  capability  one job, several commands in ONE VM: tools and modules in the image, pip, disk, memory, limits, file operations (nested folders, move, copy, delete,
              how many files), python start time and CPU speed, unittest, offline pip install of a local wheel into /workspace/lib, state kept between commands
  export      files written in the guest come back (what size works, what the policy refuses)
  source      time to copy 1, 50 and 200 files into the VM
Never touches the host outside the job folders. Output: runtime_data/measurements/logs/devvm_probe_*.{log,json}
"""
from __future__ import annotations

import argparse
import base64
import json
import statistics
import sys
import tempfile
import time
import zipfile
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.run_log import RunLog                                             # noqa: E402

GUEST_PARTS = {
    "tools": r'''
import json, shutil, importlib, sys, platform, os
out = {"python": sys.version.split()[0], "platform": platform.platform(), "uid": os.getuid(), "cwd": os.getcwd(), "home": os.environ.get("HOME")}
out["commands"] = {c: shutil.which(c) for c in ("git", "pytest", "pip", "pip3", "python3", "sh", "bash", "grep", "diff", "patch", "find", "sed", "awk", "tar", "unzip", "make", "gcc", "curl", "wget", "ls", "cp", "mv", "rm", "mkdir", "timeout")}
mods = {}
for m in ("unittest", "doctest", "venv", "ensurepip", "pip", "setuptools", "wheel", "pytest", "sqlite3", "json", "zipfile", "tarfile", "difflib", "ast", "py_compile", "compileall", "subprocess", "threading", "multiprocessing", "ctypes", "ssl", "tkinter", "readline", "zoneinfo", "venv"):
    try: importlib.import_module(m); mods[m] = True
    except Exception as e: mods[m] = type(e).__name__
out["modules"] = mods
out["env"] = sorted(os.environ)
print("PART_tools=" + json.dumps(out))
''',
    "resources": r'''
import json, shutil, os, resource, time
out = {}
for p in ("/workspace", "/tmp", "/"):
    try: u = shutil.disk_usage(p); out["disk " + p] = {"total_mib": u.total // 2**20, "free_mib": u.free // 2**20}
    except Exception as e: out["disk " + p] = type(e).__name__
try: out["mem_total_mib"] = int([l for l in open("/proc/meminfo") if l.startswith("MemTotal")][0].split()[1]) // 1024; out["mem_available_mib"] = int([l for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0].split()[1]) // 1024
except Exception as e: out["mem"] = repr(e)
out["cpus"] = os.cpu_count()
out["rlimits"] = {n: resource.getrlimit(getattr(resource, n)) for n in ("RLIMIT_NPROC", "RLIMIT_NOFILE", "RLIMIT_FSIZE", "RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_STACK")}
out["clock"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
print("PART_resources=" + json.dumps(out))
''',
    "files": r'''
import json, os, shutil, subprocess, sys
base = "/workspace/dev"; out = {}
os.makedirs(base + "/pkg/sub/deeper", exist_ok=True)
open(base + "/pkg/__init__.py", "w").write("x = 1\n")
shutil.copy(base + "/pkg/__init__.py", base + "/pkg/sub/copy.py")
shutil.move(base + "/pkg/sub/copy.py", base + "/pkg/sub/deeper/moved.py")
out["tree"] = sorted(os.path.relpath(os.path.join(r, f), base) for r, _, fs in os.walk(base) for f in fs)
shutil.rmtree(base + "/pkg/sub"); out["after_rmtree"] = sorted(os.path.relpath(os.path.join(r, f), base) for r, _, fs in os.walk(base) for f in fs)
n = 0
try:
    for i in range(2000): open(f"/workspace/dev/f{i}.txt", "w").write("x"); n += 1
except Exception as e: out["many_files_stopped_by"] = type(e).__name__
out["many_files_created"] = n
for size_mib in (0.9, 3):
    r = subprocess.run([sys.executable, "-c", f"open('/workspace/dev/big{size_mib}.bin','wb').write(b'0' * int({size_mib} * 1048576))"], capture_output=True, text=True)
    out[f"write_{size_mib}_MiB_exit"] = r.returncode
out["write_in_tmp"] = (lambda: (open("/tmp/x", "w").write("y"), "ok")[1])()
out["write_in_etc"] = "refused" if not os.access("/etc", os.W_OK) else "allowed"
out["symlink_in_workspace"] = "ok"
try: os.symlink("/etc/passwd", "/workspace/dev/link")
except Exception as e: out["symlink_in_workspace"] = type(e).__name__
print("PART_files=" + json.dumps(out))
''',
    "state": r'''
import json, os
out = {"file_from_previous_command": os.path.exists("/workspace/dev/pkg/__init__.py"), "env_marker_from_previous_command": os.environ.get("DEVVM_MARK")}
print("PART_state=" + json.dumps(out))
''',
    "timing": r'''
import json, subprocess, sys, time, os, statistics
out = {}
starts = []
for _ in range(5):
    t = time.time(); subprocess.run([sys.executable, "-c", "pass"], check=True); starts.append(time.time() - t)
out["python_start_ms"] = round(statistics.median(starts) * 1000, 1)
t = time.time(); s = 0
for i in range(5_000_000): s += i
out["cpu_loop_5M_s"] = round(time.time() - t, 2)
os.makedirs("/workspace/ut", exist_ok=True)
open("/workspace/ut/test_demo.py", "w").write("import unittest\nclass T(unittest.TestCase):\n    def test_a(self): self.assertEqual(1 + 1, 2)\n    def test_b(self): self.assertTrue('a' in 'abc')\n")
t = time.time(); r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "/workspace/ut", "-v"], capture_output=True, text=True)
out["unittest_discover"] = {"exit": r.returncode, "seconds": round(time.time() - t, 2), "last_line": (r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else ""}
t = time.time(); r = subprocess.run([sys.executable, "-m", "py_compile", "/workspace/ut/test_demo.py"], capture_output=True, text=True); out["py_compile"] = {"exit": r.returncode, "seconds": round(time.time() - t, 2)}
print("PART_timing=" + json.dumps(out))
''',
    "pip": r'''
import json, subprocess, sys, time, os
out = {}
def run(argv, timeout=20):
    t = time.time()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd="/workspace", env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PYTHONDONTWRITEBYTECODE": "1"})
        return {"exit": r.returncode, "seconds": round(time.time() - t, 1), "stdout": r.stdout[-400:], "stderr": r.stderr[-400:]}
    except Exception as e: return {"error": type(e).__name__, "seconds": round(time.time() - t, 1)}
out["pip_version"] = run([sys.executable, "-m", "pip", "--version"])
out["pip_list"] = run([sys.executable, "-m", "pip", "list", "--format=freeze"])
out["offline_install"] = run([sys.executable, "-m", "pip", "install", "--no-index", "--find-links", "/workspace/wheels", "--target", "/workspace/lib", "--no-deps", "gp_demo"])
r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, '/workspace/lib'); import gp_demo; print(gp_demo.hello())"], capture_output=True, text=True)
out["import_installed"] = {"exit": r.returncode, "output": (r.stdout or r.stderr).strip()[-200:]}
out["online_install_attempt"] = run([sys.executable, "-m", "pip", "install", "--target", "/workspace/lib2", "six"], timeout=25)
print("PART_pip=" + json.dumps(out))
''',
    "export_files": r'''
import os
os.makedirs("/workspace/out", exist_ok=True)
open("/workspace/out/small.txt", "w").write("hello")
open("/workspace/out/medium.bin", "wb").write(b"0" * 900_000)
print("PART_export_files=done")
''',
}


def make_wheel(folder: Path):
    """A pure-python wheel written by hand (a zip with dist-info), so the guest can show whether `pip install --no-index` works from a local folder."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "gp_demo-0.1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("gp_demo/__init__.py", "def hello():\n    return 'hello from an offline wheel'\n")
        z.writestr("gp_demo-0.1.dist-info/METADATA", "Metadata-Version: 2.1\nName: gp-demo\nVersion: 0.1\n")
        z.writestr("gp_demo-0.1.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: devvm_probe\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        z.writestr("gp_demo-0.1.dist-info/RECORD", "gp_demo/__init__.py,,\ngp_demo-0.1.dist-info/METADATA,,\ngp_demo-0.1.dist-info/WHEEL,,\ngp_demo-0.1.dist-info/RECORD,,\n")
    return path


def run_job(provider, policy, source, commands, exports=(), label="job"):
    job_root = Path(tempfile.mkdtemp(prefix="guppi_devvm_job_"))
    request = {"job_id": f"devvm-{label}-{int(time.time() * 1000)}", "policy": policy, "source": str(source), "job_root": str(job_root),
               "commands": commands, "exports": list(exports)}
    t0 = time.time()
    result = provider._execute_worker("run", request, job_root)
    result["wall_seconds"] = round(time.time() - t0, 1)
    return result


def parts(result):
    found = {}
    for cmd in result.get("commands", []):
        for line in (cmd.get("output") or "").splitlines():
            if line.startswith("PART_") and "=" in line:
                key, _, value = line.partition("=")
                try: found[key[5:]] = json.loads(value)
                except ValueError: found[key[5:]] = value
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--starts", type=int, default=8)
    args = ap.parse_args()
    import yaml
    from guppi_runtime.sandbox.provider import MicrosandboxProvider
    project = Path(args.project)
    policy = yaml.safe_load((RUNTIME / "config" / "sandbox.yaml").read_text(encoding="utf-8"))["sandbox"]
    provider = MicrosandboxProvider(project / "runtime_data" / "sandboxes" / "backend_home", RUNTIME)
    log = RunLog(project / "runtime_data" / "measurements", "devvm_probe", config={"starts": args.starts, "policy": {k: policy[k] for k in ("cpus", "memory_mib", "root_disk_mib", "command_timeout_seconds", "job_timeout_seconds", "max_files", "max_file_bytes", "max_export_bytes", "max_input_bytes")}})
    report = {}
    with log:
        # ---- starts
        src = Path(tempfile.mkdtemp(prefix="guppi_devvm_src_")); (src / "hello.py").write_text("print('ok')\n", encoding="utf-8")
        rows = []
        for i in range(args.starts):
            res = run_job(provider, policy, src, [["python3", "/workspace/hello.py"]], label=f"start{i}")
            ok = res.get("status") == "PASS"
            rows.append({"n": i + 1, "ok": ok, "wall_seconds": res["wall_seconds"], "status": res.get("status"), "error": res.get("error"), "cleanup_confirmed": res.get("cleanup_confirmed")})
            log.say(f"   start {i + 1}: {'ok' if ok else 'FAILED ' + str(res.get('error'))}  {res['wall_seconds']} s  cleanup {res.get('cleanup_confirmed')}")
        okt = [r["wall_seconds"] for r in rows if r["ok"]]
        report["starts"] = {"rows": rows, "ok": f"{len(okt)}/{len(rows)}", "median_seconds": round(statistics.median(okt), 1) if okt else None, "max_seconds": max(okt) if okt else None}
        log.say(f"== starts: {report['starts']['ok']} ok, median {report['starts']['median_seconds']} s")
        log.save(report)
        # ---- capability (one VM, several commands: the files written by one are read by the next)
        src = Path(tempfile.mkdtemp(prefix="guppi_devvm_src_")); make_wheel(src / "wheels")
        for name, code in GUEST_PARTS.items():
            if name != "export_files": (src / f"p_{name}.py").write_text(code, encoding="utf-8")
        order = ["tools", "resources", "files", "state", "timing", "pip"]
        commands = [["python3", f"/workspace/p_{n}.py"] for n in order]
        res = run_job(provider, policy, src, commands, label="capability")
        got = parts(res)
        report["capability"] = {"status": res.get("status"), "error": res.get("error"), "wall_seconds": res["wall_seconds"], "cleanup_confirmed": res.get("cleanup_confirmed"),
                                "command_seconds_note": "wall time of the whole job incl. VM start", "parts": got,
                                "command_exit": [c.get("exit_code") for c in res.get("commands", [])]}
        log.say(f"== capability: {res.get('status')} {res.get('error') or ''} {res['wall_seconds']} s, parts {sorted(got)}")
        log.save(report)
        # ---- export
        src2 = Path(tempfile.mkdtemp(prefix="guppi_devvm_src_")); (src2 / "p_export_files.py").write_text(GUEST_PARTS["export_files"], encoding="utf-8")
        res = run_job(provider, policy, src2, [["python3", "/workspace/p_export_files.py"]], exports=["out/small.txt", "out/medium.bin"], label="export")
        exported = {e["path"]: len(base64.b64decode(e["data_base64"])) for e in res.get("exports", [])}
        report["export"] = {"status": res.get("status"), "error": res.get("error"), "bytes_back": exported}
        log.say(f"== export: {res.get('status')} {res.get('error') or ''} back {exported}")
        # ---- source size / count
        rows = []
        for count in (1, 50, 200):
            srcn = Path(tempfile.mkdtemp(prefix="guppi_devvm_src_"))
            for i in range(count): (srcn / f"f{i}.py").write_text(f"x = {i}\n" * 40, encoding="utf-8")
            r = run_job(provider, policy, srcn, [["python3", "-c", "import os; print(len(os.listdir('/workspace')))"]], label=f"src{count}")
            rows.append({"files": count, "status": r.get("status"), "error": r.get("error"), "wall_seconds": r["wall_seconds"]})
            log.say(f"   source {count} files: {r.get('status')} {r.get('error') or ''} {r['wall_seconds']} s")
        report["source"] = rows
        log.save(report)
    log.say(f"DONE -> {log.json_path.name}")


if __name__ == "__main__":
    main()
