r"""Phase 2 acceptance of the DevVM mission: a model's `run_tests` goes through the broker, the Guard and the Captain's gate, and runs in the REAL microVM only with an approved gate.

    .venv\Scripts\python.exe benchmarks/devvm_phase2_check.py <project_dir>

A temporary GuppiRuntime (own folder, own audit chain) gives a real Guard and a real SandboxBroker with the real provider and the real sandbox config. The check plays the Captain
for ITS OWN temporary gates only (like the unit tests do): it approves a gate it created itself and nothing else. Steps:
  1 coder box with a `broker_runner` and NO approval token: `run_tests` answers "NOT STARTED ... gate", the VM was not started (no job folder)
  2 the gate is approved for exactly this plan: the same run now executes in the VM and the model sees the unittest output
  3 the code changes: the old token does not fit the new plan, so the run is not started again (a new gate is needed)
  4 the audit chain records the DevVM workspace events with the mission
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.devenv.devvm import DevWorkspace                                         # noqa: E402
from guppi_runtime.devenv.devvm_tools import DevToolBox, broker_runner                      # noqa: E402
from guppi_runtime.jobs.run_log import RunLog                                             # noqa: E402
from guppi_runtime.runtime import GuppiRuntime                                       # noqa: E402
from guppi_runtime.sandbox.broker import SandboxBroker                               # noqa: E402
from guppi_runtime.sandbox.provider import MicrosandboxProvider                      # noqa: E402

CODE = "def add(a, b):\n    return a + b\n"
TEST = "import unittest\nfrom calc import add\n\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n"


def main():
    project = Path(sys.argv[1])
    arch = sorted((RUNTIME.parent / "architecture").glob("GUPPI_Architecture_v*"))[-1]
    log = RunLog(project / "runtime_data" / "measurements", "devvm_phase2_check")
    results = {}
    with log:
        root = Path(tempfile.mkdtemp(prefix="guppi_devvm_p2_"))
        rt = GuppiRuntime(root, arch)
        provider = MicrosandboxProvider(project / "runtime_data" / "sandboxes" / "backend_home", RUNTIME)
        broker = SandboxBroker(rt.filesystem_tool.root, root / "sandbox-data", RUNTIME / "config" / "sandbox.yaml", provider, rt.guard, rt.audit)
        mission = "M-GATE0001"
        ws = DevWorkspace(rt.filesystem_tool.root, mission, policy=broker.policy(), audit=rt.audit); ws.create()
        ws.write("calc.py", CODE); ws.write("test_calc.py", TEST); ws.commit("calc with a test")
        jobs = lambda: len(list((root / "sandbox-data" / "jobs").glob("SBX-*"))) if (root / "sandbox-data" / "jobs").is_dir() else 0

        # 1 no token: not started
        runner = broker_runner(ws, broker, mission)
        box = DevToolBox(ws, "coder", vm_runner=runner)
        answer = box.call("run_tests", {})
        results["step1_not_started_without_gate"] = {"ok": answer.startswith("NOT STARTED") and jobs() == 0, "answer": answer[:140], "vm_jobs": jobs()}
        log.say(f"1 without a gate: '{answer[:110]}' VM jobs started: {jobs()}")
        # 2 approve the gate for exactly this plan, run for real
        first = runner([["python3", "-m", "unittest", "discover", "-v"]])
        token = rt.guard.approve(first["gate"])
        approved = DevToolBox(ws, "coder", vm_runner=broker_runner(ws, broker, mission, token))
        out = approved.call("run_tests", {})
        results["step2_runs_with_approved_gate"] = {"ok": out.startswith("VM run completed") and "OK" in out, "answer": out[-160:], "vm_jobs": jobs()}
        log.say(f"2 with the approved gate: {out[:60].strip()} ... {out.strip().splitlines()[-1] if out.strip() else ''}  (VM jobs: {jobs()})")
        # 3 changed code: the old token does not cover the new plan
        ws.write("calc.py", "def add(a, b):\n    return a - b\n")
        again = DevToolBox(ws, "coder", vm_runner=broker_runner(ws, broker, mission, token)).call("run_tests", {})
        results["step3_old_token_does_not_cover_a_changed_plan"] = {"ok": again.startswith("NOT STARTED"), "answer": again[:140], "vm_jobs": jobs()}
        log.say(f"3 changed code, old token: '{again[:100]}' (VM jobs: {jobs()})")
        # 4 audit
        import json
        events = [json.loads(line) for line in Path(rt.audit.path).read_text(encoding="utf-8").splitlines() if line.strip()]
        mine = [e for e in events if (e.get("source") or {}).get("component") == "devvm"]
        results["step4_audit"] = {"ok": bool(mine) and all((e.get("source") or {}).get("mission_id") == mission for e in mine) and rt.audit.verify_chain() is not False,
                                  "events": sorted({e.get("event_type") for e in mine}), "count": len(mine)}
        log.say(f"4 audit events of the workspace: {results['step4_audit']['events']}")
        results["all_ok"] = all(v.get("ok") for v in results.values() if isinstance(v, dict))
        log.save(results)
        log.say(f"RESULT all ok: {results['all_ok']}")
    log.say(f"DONE -> {log.json_path.name}")


if __name__ == "__main__":
    main()
