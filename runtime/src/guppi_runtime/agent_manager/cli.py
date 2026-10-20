"""Command line of the agent manager: put an assignment through the bridge and the Guard, then watch it.

    python -m guppi_runtime.agent_manager.cli propose --agent REF --mission ID --input SPEC     # writes a Captain gate and shows exactly what it would allow
    python -m guppi_runtime.agent_manager.cli approve GATE_ID                                    # the Captain's approval (run only on his explicit instruction)
    python -m guppi_runtime.agent_manager.cli reject GATE_ID
    python -m guppi_runtime.agent_manager.cli submit GATE_ID                                     # hands the approved assignment to the bridge: starts the run
    python -m guppi_runtime.agent_manager.cli stop ASSIGNMENT --reason TEXT                      # stops a run (worker tree by PID) and records the known outcome
    python -m guppi_runtime.agent_manager.cli hire --template REF --purpose TEXT --mission ID [--model KEY]    # gate for a new crew instance (then approve GATE, then create GATE)
    python -m guppi_runtime.agent_manager.cli create GATE_ID                                      # the approved gate creates the instance (UNVERIFIED, no admission)
    python -m guppi_runtime.agent_manager.cli suite INSTANCE --suite NAME --candidate DIR --builder MODEL   # run the acceptance suite in the microVM and store the result
    python -m guppi_runtime.agent_manager.cli review INSTANCE --reviewer MODEL --verdict PASS|FAIL           # an independent review of the latest suite run's candidate
    python -m guppi_runtime.agent_manager.cli gaps INSTANCE                                       # what stands between the instance and VERIFIED
    python -m guppi_runtime.agent_manager.cli promote-propose INSTANCE --mission ID               # gate for VERIFIED (refused while gaps remain; then approve GATE, then promote GATE)
    python -m guppi_runtime.agent_manager.cli promote GATE_ID
    python -m guppi_runtime.agent_manager.cli revoke INSTANCE --reason TEXT                       # takes the admission away at once (no gate needed)
    python -m guppi_runtime.agent_manager.cli crews                                                # the crew templates
    python -m guppi_runtime.agent_manager.cli plan CREW_REF [--snapshot JSON]                     # plans a crew from the instances (only recommends)
    python -m guppi_runtime.agent_manager.cli crew                                                # the instances
    python -m guppi_runtime.agent_manager.cli status                                             # reconciles with the runtime and lists the assignments

`propose` never approves and `submit` refuses without a token the Guard issued for exactly this agent, mission and input. Every step is written to the audit log.
"""
import argparse
import json
import sys
from pathlib import Path

from ..core.audit import AuditLog
from ..core.guard import Guard
from .agent_contracts import ContractError, make_id
from .agent_registry import Registry
from .bridge import ACTION, AgentBridge
from .devvm_runtime import DevVmRuntime
from .instances import InstanceService


class Manager:
    def __init__(self, project_dir, runtime_dir, architecture_root, runtime=None, python=None):
        self.project, self.runtime_dir = Path(project_dir), Path(runtime_dir)
        data = self.project / "runtime_data"
        self.base = data / "agent_manager"
        self.gates = self.base / "gates"
        self.gates.mkdir(parents=True, exist_ok=True)
        self.audit = AuditLog(data / "audit" / "events.jsonl")
        self.guard = Guard(Path(architecture_root) / "core" / "guard" / "guard_rules.yaml", self.audit, data / "guard" / "approval_tokens.json")
        self.registry = Registry(str(self.base / "registry.sqlite"))
        self.runtime = runtime or DevVmRuntime(self.runtime_dir, self.project, python=python)
        self.bridge = AgentBridge(self.base / "registry.sqlite", self.guard, self.runtime, self.registry)
        self.instances = InstanceService(self.registry, self.guard, self.audit)

    def close(self):
        self.bridge.close()
        self.registry.close()

    def _binding(self, agent, mission, input_ref):
        return {"agent_ref": agent, "mission_id": mission, "input_ref": input_ref}

    def propose(self, agent, mission, input_ref):
        entry = self.registry.get("template", agent)
        if entry is None or not entry["data"]["preview"]["ok"]:
            raise ContractError("agent_unknown", "no clean template with this reference")
        risks = ["starts a DevVM build on this PC: uses the GPU (lease) for about one to two hours", "writes only a candidate under runtime_data/devvm_candidates and a run folder under runtime_data/agent_manager/runs",
                 "no integration into src, no network, no change to control.py, guard.py or the guest image"]
        gate = self.guard.create_gate(mission, ACTION, agent, risks=risks, rollback_available=True, request_binding=self._binding(agent, mission, input_ref))
        gate["agent_manager"] = {"input_ref": input_ref, "command_id": make_id("cmd", {"gate": gate["gate_id"]})}
        self._save(gate)
        self.audit.append("AGENT_ASSIGNMENT_PROPOSED", component="agent_manager", mission_id=mission, actor="claude", payload={"gate_id": gate["gate_id"], "agent": agent, "input_ref": input_ref})
        return gate

    def approve(self, gate_id):
        gate = self._load(gate_id)
        if gate["status"] != "pending":
            raise ContractError("gate_resolved", "this gate is already resolved")
        token = self.guard.approve(gate)
        self._save(gate)
        (self.gates / f"{gate_id}.token.json").write_text(json.dumps(token), encoding="utf-8")
        return token

    def reject(self, gate_id):
        gate = self.guard.reject(self._load(gate_id), "rejected with the agent manager command line")
        self._save(gate)
        return gate

    def submit(self, gate_id):
        gate = self._load(gate_id)
        if gate["status"] != "resolved" or (gate.get("resolution") or {}).get("decision") != "APPROVE_ONCE":
            raise ContractError("not_approved", "the gate is not approved")
        token = json.loads((self.gates / f"{gate_id}.token.json").read_text(encoding="utf-8"))
        meta = gate["agent_manager"]
        agent = gate["request"]["targets"][0]
        record = self.bridge.submit(meta["command_id"], agent, gate["mission_id"], meta["input_ref"], token)
        self.audit.append("AGENT_ASSIGNMENT_SUBMITTED", component="agent_manager", mission_id=gate["mission_id"], actor="claude", payload={"gate_id": gate_id, "assignment": record["assignment_id"], "run_id": record["run_id"], "state": record["state"]})
        return record

    def hire(self, template_ref, purpose, mission, model_key=None):
        gate = self.instances.instantiation_gate(template_ref, purpose, mission, model_key)
        self._save(gate)
        return gate

    def create(self, gate_id):
        gate = self._load(gate_id)
        if gate["status"] != "resolved" or (gate.get("resolution") or {}).get("decision") != "APPROVE_ONCE":
            raise ContractError("not_approved", "the gate is not approved")
        return self.instances.instantiate(gate, self._token(gate_id))

    def _token(self, gate_id):
        return json.loads((self.gates / f"{gate_id}.token.json").read_text(encoding="utf-8"))

    def suite(self, instance_id, suite_name, candidate_dir, builder, runner=None):
        from ..selfdev.acceptance_suite import load_suite, run_suite
        from ..selfdev.acceptance_vm import vm_runner
        suite = load_suite(str(self.project / "acceptance" / "suites" / suite_name))
        files = {name: (Path(candidate_dir) / name).read_text(encoding="utf-8") for name in suite.reference if (Path(candidate_dir) / name).is_file()}
        if set(files) != set(suite.reference):
            raise ContractError("candidate_incomplete", "missing: " + ", ".join(sorted(set(suite.reference) - set(files))))
        run = run_suite(suite, files, runner or vm_runner(self.project, self.runtime_dir))
        self.instances.record_suite_run(instance_id, run, builder)
        self.audit.append("AGENT_SUITE_RUN", component="agent_manager", actor="claude", payload={"instance": instance_id, "suite": run["suite"], "passed": run["passed"], "candidate_hash": run["candidate_hash"]})
        return run

    def review(self, instance_id, reviewer, verdict):
        run = self.registry.get("agent", instance_id)["data"]["suite_runs"][-1]
        updated = self.instances.record_review(instance_id, reviewer, verdict, run["candidate_hash"])
        self.audit.append("AGENT_REVIEW_RECORDED", component="agent_manager", actor="claude", payload={"instance": instance_id, "reviewer": reviewer, "verdict": verdict})
        return updated

    def propose_promotion(self, instance_id, mission):
        gate = self.instances.promotion_gate(instance_id, mission)
        self._save(gate)
        return gate

    def promote(self, gate_id):
        gate = self._load(gate_id)
        if gate["status"] != "resolved" or (gate.get("resolution") or {}).get("decision") != "APPROVE_ONCE":
            raise ContractError("not_approved", "the gate is not approved")
        return self.instances.promote(gate, self._token(gate_id))

    def crew_rows(self):
        return [{"ref": e["key"], "purpose": e["data"]["crew"].get("purpose"), "slots": len(e["data"]["crew"].get("slots") or []), "steps": len(e["data"]["crew"].get("workflow") or []), "problems": e["data"]["problems"]} for e in self.registry.list("crew")]

    def stop(self, assignment_id, reason):
        record = self.bridge.stop(assignment_id, reason)
        self.audit.append("AGENT_RUN_STOPPED", component="agent_manager", mission_id=record["mission_id"], actor="claude",
                          payload={"assignment": assignment_id, "run_id": record["run_id"], "reason": reason, "was_running": record["was_running"]})
        return record

    def status(self):
        changed = self.bridge.reconcile()
        rows = self.bridge.list()
        for row in rows:
            row["result"] = self.runtime.result(row["run_id"]) if hasattr(self.runtime, "result") else None
        return {"reconciled": changed, "assignments": rows}

    def _path(self, gate_id):
        if not gate_id.startswith("HG-") or not gate_id[3:].isalnum():
            raise ContractError("bad_gate", "not a gate id")
        return self.gates / f"{gate_id}.json"

    def _save(self, gate):
        self._path(gate["gate_id"]).write_text(json.dumps(gate, indent=1), encoding="utf-8")

    def _load(self, gate_id):
        try:
            return json.loads(self._path(gate_id).read_text(encoding="utf-8"))
        except OSError:
            raise ContractError("gate_unknown", "no such gate") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    proposal = sub.add_parser("propose")
    proposal.add_argument("--agent", required=True)
    proposal.add_argument("--mission", required=True)
    proposal.add_argument("--input", required=True)
    for name in ("approve", "reject", "submit"):
        sub.add_parser(name).add_argument("gate")
    hirer = sub.add_parser("hire")
    hirer.add_argument("--template", required=True)
    hirer.add_argument("--purpose", required=True)
    hirer.add_argument("--mission", required=True)
    hirer.add_argument("--model", help="the model key this instance runs on (needed for the independence rules of crews)")
    suiter = sub.add_parser("suite")
    suiter.add_argument("instance")
    suiter.add_argument("--suite", required=True)
    suiter.add_argument("--candidate", required=True)
    suiter.add_argument("--builder", required=True)
    reviewer = sub.add_parser("review")
    reviewer.add_argument("instance")
    reviewer.add_argument("--reviewer", required=True)
    reviewer.add_argument("--verdict", required=True, choices=["PASS", "FAIL"])
    sub.add_parser("gaps").add_argument("instance")
    promoter = sub.add_parser("promote-propose")
    promoter.add_argument("instance")
    promoter.add_argument("--mission", required=True)
    revoker = sub.add_parser("revoke")
    revoker.add_argument("instance")
    revoker.add_argument("--reason", required=True)
    sub.add_parser("create").add_argument("gate")
    sub.add_parser("promote").add_argument("gate")
    sub.add_parser("crew")
    sub.add_parser("crews")
    planner = sub.add_parser("plan")
    planner.add_argument("crew_ref")
    planner.add_argument("--snapshot", default="{}")
    stopper = sub.add_parser("stop")
    stopper.add_argument("assignment")
    stopper.add_argument("--reason", required=True)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    runtime_dir = Path(__file__).resolve().parents[3]
    project = Path(args.project) if args.project else runtime_dir.parent / "workspace" / "GUPPI_OS"
    architecture = sorted((project.parent.parent / "architecture").glob("GUPPI_Architecture_v*"))[-1]
    manager = Manager(project, runtime_dir, architecture)
    try:
        if args.cmd == "propose":
            gate = manager.propose(args.agent, args.mission, args.input)
            print(json.dumps({"gate_id": gate["gate_id"], "action": gate["request"]["exact_action"], "target": gate["request"]["targets"], "risks": gate["request"]["risks"],
                              "input": args.input, "command_id": gate["agent_manager"]["command_id"], "status": gate["status"]}, indent=1))
        elif args.cmd == "approve":
            print("approved, token", manager.approve(args.gate)["token_id"])
        elif args.cmd == "reject":
            print("rejected", manager.reject(args.gate)["gate_id"])
        elif args.cmd == "submit":
            print(json.dumps(manager.submit(args.gate), indent=1))
        elif args.cmd == "hire":
            gate = manager.hire(args.template, args.purpose, args.mission, args.model)
            print(json.dumps({"gate_id": gate["gate_id"], "action": gate["request"]["exact_action"], "target": gate["request"]["targets"], "risks": gate["request"]["risks"], "status": gate["status"]}, indent=1))
        elif args.cmd == "create":
            print(json.dumps(manager.create(args.gate), indent=1))
        elif args.cmd == "suite":
            run = manager.suite(args.instance, args.suite, args.candidate, args.builder)
            print(run["suite"], "PASSED all" if run["passed"] else "FAILED", {r["criterion_id"]: r["status"] for r in run["results"]})
        elif args.cmd == "review":
            print(json.dumps(manager.review(args.instance, args.reviewer, args.verdict)["data"]["review"], indent=1))
        elif args.cmd == "gaps":
            print(json.dumps({"gaps": manager.instances.gaps(args.instance), "gaps_if_decided": manager.instances.gaps(args.instance, decision=True)}, indent=1))
        elif args.cmd == "promote-propose":
            gate = manager.propose_promotion(args.instance, args.mission)
            print(json.dumps({"gate_id": gate["gate_id"], "action": gate["request"]["exact_action"], "target": gate["request"]["targets"], "risks": gate["request"]["risks"], "status": gate["status"]}, indent=1))
        elif args.cmd == "promote":
            data = manager.promote(args.gate)["data"]
            print(json.dumps({"qualification": data["qualification"], "admission": data["admission"]}, indent=1))
        elif args.cmd == "revoke":
            data = manager.instances.revoke(args.instance, args.reason)["data"]
            print(json.dumps({"lifecycle": data["lifecycle"], "admission": data["admission"]}, indent=1))
        elif args.cmd == "crews":
            for row in manager.crew_rows():
                print(f"{row['ref']}  slots={row['slots']} steps={row['steps']}  problems={row['problems'] or '-'}  {row['purpose']}")
        elif args.cmd == "plan":
            print(json.dumps(manager.instances.assemble(args.crew_ref, json.loads(args.snapshot)), indent=1))
        elif args.cmd == "crew":
            for entry in manager.registry.list("agent"):
                d = entry["data"]
                last = d["suite_runs"][-1] if d["suite_runs"] else None
                passed = f"{sum(r['status'] == 'PASS' for r in last['results'])}/{len(last['results'])}" if last else "-"
                print(f"{entry['key']}  {d['template_ref']}  {d['qualification']}  {d['lifecycle']}  admission={'valid' if d['admission']['valid'] else 'none'}  suite={passed}  review={(d['review'] or {}).get('verdict', '-')}")
        elif args.cmd == "stop":
            print(json.dumps(manager.stop(args.assignment, args.reason), indent=1))
        else:
            print(json.dumps(manager.status(), indent=1))
    except ContractError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    finally:
        manager.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
