r"""Phase 1 acceptance of the DevVM mission on the REAL microVM (docs/DEVVM_AUFTRAG_2026-10-05.md): host workspace, git, VM run, directory export.

    .venv\Scripts\python.exe benchmarks/devvm_phase1_check.py <project_dir>

Everything happens in a temporary tool root with a COPY of config/sandbox.yaml in which `allow_export_dirs: true` is set for this check only; the real config is not touched
(the Captain's switch stays off). The run goes through the broker's own `_run` (plan validation, input snapshot, worker, candidate checks); the Guard step in front of it is the
only part skipped here, because the check has no mission to ask a gate for. Production use must go through `broker.execute('run', ...)` and the Captain's gate.

Steps: 1 workspace + code + tests + commit (host)   2 VM run of the tests with a directory export   3 change, run again, commit, diff, restore
       4 guest tries to export a symlink   5 guest writes a forbidden file type   6 the exported files must not have touched the host workspace
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
import time
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.devvm import DevWorkspace                                         # noqa: E402
from guppi_runtime.run_log import RunLog                                             # noqa: E402
from guppi_runtime.sandbox.broker import SandboxBroker                               # noqa: E402
from guppi_runtime.sandbox.provider import MicrosandboxProvider                      # noqa: E402

CODE = "def add(a, b):\n    return a + b\n"
TEST = "import unittest\nfrom calc import add\n\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n"
REPORT = ("import pathlib, sys\npathlib.Path('out/sub').mkdir(parents=True, exist_ok=True)\n"
          "pathlib.Path('out/report.txt').write_text('tests ran\\n')\npathlib.Path('out/sub/data.json').write_text('{\"ok\": true}\\n')\n")


def main():
    project = Path(sys.argv[1])
    log = RunLog(project / "runtime_data" / "measurements", "devvm_phase1_check")
    results = {}
    with log:
        tool_root = Path(tempfile.mkdtemp(prefix="guppi_devvm_check_"))
        cfg = yaml.safe_load((RUNTIME / "config" / "sandbox.yaml").read_text(encoding="utf-8"))
        cfg["sandbox"]["allow_export_dirs"] = True
        cfg_path = tool_root / "sandbox-check.yaml"; cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        provider = MicrosandboxProvider(project / "runtime_data" / "sandboxes" / "backend_home", RUNTIME)
        broker = SandboxBroker(tool_root, tool_root / "sandbox-data", cfg_path, provider, None)
        ws = DevWorkspace(tool_root, "M-PHASE1", policy=broker.policy()); ws.create()

        def run(commands, **kw):
            plan = ws.vm_preview(broker, commands, **kw)
            t0 = time.time(); out = broker._run("M-PHASE1", plan)
            return plan, out, round(time.time() - t0, 1)

        # 1 host side
        ws.write("calc.py", CODE); ws.write("test_calc.py", TEST); ws.write("make_report.py", REPORT)
        first = ws.commit("calculator with a test")
        log.say(f"1 host: {ws.tree()} committed {first[:10]}  usage {ws.usage()}")
        # 2 VM run with a directory export
        plan, out, seconds = run([["python3", "-m", "unittest", "discover", "-v"], ["python3", "make_report.py"]], export_dirs=["out"])
        rec = out["sandbox"]; cand = rec.get("candidate") or {}
        got = sorted(f["path"] for f in cand.get("files", []))
        tests_out = rec["commands"][0]["output"].strip().splitlines()[-1] if rec.get("commands") else ""
        ok2 = out["status"] == "completed" and got == ["out/report.txt", "out/sub/data.json"] and tests_out == "OK"
        results["run_and_export"] = {"ok": ok2, "status": out["status"], "seconds": seconds, "candidate_files": got, "unittest_last_line": tests_out, "promotion": cand.get("promotion")}
        log.say(f"2 VM run: {out['status']} in {seconds} s, unittest '{tests_out}', candidate {got}, promotion {cand.get('promotion')}")
        if out["status"] == "completed":
            job_id = Path(cand["path"]).parent.name
            report = broker.receipt(job_id)
            verdict = broker.verify("M-PHASE1", job_id, hashlib.sha256(report).hexdigest(), plan["plan_digest"])
            results["verify"] = verdict.get("verification"); log.say(f"   independent verify: {verdict.get('verification')} {verdict.get('error') or ''}")
        # 6 the host workspace must not contain the exported files (they wait in the candidate for the Captain)
        results["host_workspace_untouched"] = ws.tree() == ["calc.py", "make_report.py", "test_calc.py"]
        log.say(f"6 host workspace untouched by the export: {results['host_workspace_untouched']}")
        # 3 change, run again, commit, diff, restore
        ws.write("calc.py", "def add(a, b):\n    return a - b\n")
        plan, out, seconds = run([["python3", "-m", "unittest", "discover"]])
        failed_run = out["status"] == "failed"
        results["broken_change_detected"] = {"ok": failed_run, "status": out["status"], "seconds": seconds}
        log.say(f"3 broken change: VM run {out['status']} in {seconds} s (a failing test fails the job: {failed_run}); diff has {ws.diff().count(chr(10))} lines")
        restored = ws.restore(first); plan, out, seconds = run([["python3", "-m", "unittest", "discover"]])
        results["restore_runs_green"] = {"ok": out["status"] == "completed", "restored": restored, "seconds": seconds}
        log.say(f"   restore to {first[:10]}: VM run {out['status']} in {seconds} s, status {ws.status()}")
        # 4 the guest tries to hand back a symlink
        ws.write("evil.py", "import os\nos.makedirs('out', exist_ok=True)\nos.symlink('/etc/passwd', 'out/link.txt')\nopen('out/ok.txt', 'w').write('x')\n")
        plan, out, seconds = run([["python3", "evil.py"]], export_dirs=["out"])
        results["symlink_refused"] = {"ok": out["status"] in ("failed",) and "guest_export_symlink" in str(out["sandbox"].get("error")), "status": out["status"], "error": out["sandbox"].get("error")}
        log.say(f"4 symlink export: {out['status']} error {out['sandbox'].get('error')}")
        # 5 forbidden file type comes back from an approved directory
        ws.write("evil.py", "import os\nos.makedirs('out', exist_ok=True)\nopen('out/prog.exe', 'wb').write(b'MZ')\nopen('out/ok.txt', 'w').write('x')\n")
        before = len(list((tool_root / "sandbox-data" / "jobs").glob("*/candidate")))
        try:
            plan, out, seconds = run([["python3", "evil.py"]], export_dirs=["out"]); refused, why = out["status"] == "failed", out["status"]
        except Exception as exc:        # `_run` raises on untrusted answers; `execute('run')` turns that into status 'failed'
            refused, why = True, f"{type(exc).__name__}: {exc}"
        after = len(list((tool_root / "sandbox-data" / "jobs").glob("*/candidate")))
        results["forbidden_type_refused"] = {"ok": refused and after == before, "why": why, "candidate_folders_before": before, "after": after}
        log.say(f"5 forbidden file type: refused={refused} ({why}); candidate folders {before} -> {after}")
        results["all_ok"] = all(v.get("ok", True) if isinstance(v, dict) else v in (True, "PASS") for v in results.values())
        log.save(results)
        log.say(f"RESULT all ok: {results['all_ok']}")
    log.say(f"DONE -> {log.json_path.name}")


if __name__ == "__main__":
    main()
