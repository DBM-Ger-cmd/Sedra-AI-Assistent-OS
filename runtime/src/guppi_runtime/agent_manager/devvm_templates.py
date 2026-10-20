"""Agent templates for the DevVM roles (integration stage 5, first step).

The five roles of `devvm_tools` (coder, reviewer, tester, planner, explorer) become the first agent templates. Nothing is invented: the SOUL is the role's real system text,
the tool list is the role's real tool set, and every tool pin is the SHA-256 of that tool's real schema. The templates are written as files and come back through the same strict
import path as any other template (always UNVERIFIED); this module does not register or start anything.
"""
import hashlib
import json
import os

import yaml

from ..devenv.devvm_tools import ROLE_TOOLS, SCHEMAS, SYSTEM, TERMINAL

EFFECTS = {"coder": "reversible_write", "reviewer": "read_only", "tester": "preview", "planner": "proposal_only", "explorer": "read_only", "solo": "reversible_write", "step_planner": "proposal_only"}
WORKSPACE_MODE = {"coder": "mission_write", "reviewer": "read_only", "tester": "read_only", "planner": "read_only", "explorer": "read_only", "solo": "mission_write", "step_planner": "read_only"}


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def _pin(name):
    return hashlib.sha256(json.dumps(SCHEMAS[name], sort_keys=True).encode("utf-8")).hexdigest()


def role_template(role):
    soul = SYSTEM[role].encode("utf-8")
    tools = list(ROLE_TOOLS[role]) + [TERMINAL[role]]
    template = {
        "schema_version": "guppi.agent-template/v1", "id": f"guppi.devvm.{role}", "version": "1.0.0", "role": f"DevVM {role}",
        "soul": {"path": "SOUL.md", "version": "1.0.0", "sha256": hashlib.sha256(soul).hexdigest()},
        "capabilities": [{"id": f"guppi.devvm.{role}", "version": "1.0.0", "side_effect": EFFECTS[role]}],
        "tools": [{"id": name, "version": "1.0.0", "sha256": _pin(name)} for name in tools],
        "permissions": {"tools_allowed": tools, "workspace_mode": WORKSPACE_MODE[role], "network_mode": "deny", "external_write": False, "privileged": False},
        "runtime": {"adapter_id": "guppi.devvm.orchestrator", "isolation": "devvm_workspace", "model_role": role},
        "initial_qualification": "DRAFT", "tags": ["devvm"],
    }
    return template, soul


def export_role_templates(folder):
    """Write `<folder>/<role>/template.yaml` and `SOUL.md` for every DevVM role; returns the role names."""
    for role in ROLE_TOOLS:
        template, soul = role_template(role)
        target = os.path.join(folder, role)
        os.makedirs(target, exist_ok=True)
        with open(os.path.join(target, "template.yaml"), "w", encoding="utf-8", newline="\n") as handle:
            yaml.dump(template, handle, Dumper=_NoAliasDumper, sort_keys=False, allow_unicode=True)
        with open(os.path.join(target, "SOUL.md"), "wb") as handle:
            handle.write(soul)
    return list(ROLE_TOOLS)
