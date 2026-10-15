"""Read-only agent manager service (integration stage 2).

It reads agent templates from a folder (host side, with the strict YAML loader), checks every one with the import preview of AM-004 and registers it in the registry as a
template entry with trust UNVERIFIED. Nothing is executed and nothing gets a permission: a template that fails the preview is registered too, with its problems, so that the
Captain can see why it was refused. The database is the manager's own SQLite file (never the mission files).
"""
import os

from .agent_contracts import ContractError, canonical_digest
from .agent_import import preview_template
from .crews import validate_crew
from .instances import promotion_gaps
from .agent_matcher import match
from .agent_registry import Registry
from .yaml_loader import load_strict

TEMPLATE_FILE = "template.yaml"
MAX_FILE_BYTES = 1048576


class AgentManager:
    def __init__(self, db_path):
        self.registry = Registry(str(db_path))

    def close(self):
        self.registry.close()

    def import_templates(self, folder):
        """Import every `<folder>/<name>/template.yaml`. Returns a list of {"folder", "key", "status", "problems"}; status is created, unchanged, changed, or refused."""
        results = []
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.isdir(path) and os.path.isfile(os.path.join(path, TEMPLATE_FILE)):
                results.append(self._import_one(name, path))
        return results

    def _import_one(self, name, path):
        try:
            template = load_strict(self._read(os.path.join(path, TEMPLATE_FILE)))
            files = self._files_of(template, path)
        except (ContractError, OSError) as exc:
            return {"folder": name, "key": None, "status": "refused", "problems": [getattr(exc, "code", "unreadable")]}
        preview = preview_template(template, files)
        if preview["ref"] is None:
            return {"folder": name, "key": None, "status": "refused", "problems": preview["problems"]}
        data = {"template": template, "preview": preview, "trust": "UNVERIFIED", "digest": canonical_digest(template)}
        return {"folder": name, "key": preview["ref"], "status": self._register(preview["ref"], data), "problems": preview["problems"]}

    def _register(self, key, data):
        stored = self.registry.get("template", key)
        if stored is None:
            self.registry.create("template", key, data)
            return "created"
        if stored["data"]["digest"] == data["digest"] and stored["data"]["preview"] == data["preview"]:
            return "unchanged"
        return "changed"

    @staticmethod
    def _read(path):
        if os.path.getsize(path) > MAX_FILE_BYTES:
            raise ContractError("file_too_large", os.path.basename(path))
        with open(path, "rb") as handle:
            return handle.read()

    def _files_of(self, template, folder):
        soul = template.get("soul") if isinstance(template, dict) else None
        rel = soul.get("path") if isinstance(soul, dict) else None
        if not isinstance(rel, str) or not rel or os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
            return {}
        target = os.path.join(folder, rel)
        if os.path.isfile(target) and os.path.realpath(target).startswith(os.path.realpath(folder) + os.sep):
            return {rel: self._read(target)}
        return {}

    def list_templates(self):
        return [self._summary(entry) for entry in self.registry.list("template")]

    def import_crews(self, folder):
        """Import every `<folder>/<name>/crew.yaml`: strict YAML, the crew validation, and the pins checked against the registered templates (a missing or changed template is a problem, not a
        silent substitute). A crew with problems is registered too (so they can be seen) but cannot be assembled. Returns a list of {"folder", "key", "status", "problems"}."""
        results = []
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name, "crew.yaml")
            if not os.path.isfile(path):
                continue
            try:
                crew = load_strict(self._read(path))
            except (ContractError, OSError) as exc:
                results.append({"folder": name, "key": None, "status": "refused", "problems": [getattr(exc, "code", "unreadable")]})
                continue
            problems = validate_crew(crew)
            if "bad_id" in problems or "bad_version" in problems or not isinstance(crew, dict):
                results.append({"folder": name, "key": None, "status": "refused", "problems": problems})
                continue
            for slot in crew.get("slots") if isinstance(crew.get("slots"), list) else []:
                if not isinstance(slot, dict):
                    continue
                entry = self.registry.get("template", f"{slot.get('template_id')}@{slot.get('template_version')}") if isinstance(slot.get("template_id"), str) and isinstance(slot.get("template_version"), str) else None
                if entry is None:
                    problems.append(f"template_not_imported:{slot.get('id')}")
                elif entry["data"]["digest"].removeprefix("sha256:") != slot.get("template_sha256"):
                    problems.append(f"pin_mismatch:{slot.get('id')}")
            data = {"crew": crew, "problems": sorted(set(problems)), "digest": canonical_digest(crew)}
            key = f"{crew['id']}@{crew['version']}"
            stored = self.registry.get("crew", key)
            if stored is None:
                self.registry.create("crew", key, data)
                status = "created"
            else:
                status = "unchanged" if stored["data"]["digest"] == data["digest"] and stored["data"]["problems"] == data["problems"] else "changed"
            results.append({"folder": name, "key": key, "status": status, "problems": data["problems"]})
        return results

    def list_crews(self):
        return [{"ref": e["key"], "purpose": e["data"]["crew"].get("purpose"), "slots": len(e["data"]["crew"].get("slots") or []), "steps": len(e["data"]["crew"].get("workflow") or []),
                 "problems": e["data"]["problems"]} for e in self.registry.list("crew")]

    def get_template(self, ref):
        entry = self.registry.get("template", ref)
        return None if entry is None else entry["data"]

    @staticmethod
    def _summary(entry):
        data = entry["data"]
        return {"ref": entry["key"], "role": data["template"].get("role"), "trust": data["trust"], "ok": data["preview"]["ok"], "problems": data["preview"]["problems"]}

    def promotion_gaps(self, ref, run, independent_review=False, guppi_decision=False):
        """What still stands between a template and VERIFIED, by the shared rule of `instances.promotion_gaps` (the suite the template declares, every required case PASS, an independent review, a
        GUPPI decision). `independent_review` may be a bool or the stored review dict. Changes nothing."""
        entry = self.registry.get("template", ref)
        if entry is None:
            return ["template_unknown"]
        review = independent_review if isinstance(independent_review, dict) else ({"verdict": "PASS", "reviewer": "reviewer", "builder": "builder"} if independent_review else None)
        return promotion_gaps(entry["data"]["template"].get("verification"), run, review, guppi_decision)

    def match_templates(self, requirement, snapshot):
        """Run the matcher over the registered templates. A template is not an agent yet: it is unverified and not admitted, so the hard filter excludes it with its reasons
        until a real instance with a valid admission exists. The result only recommends; it starts nothing."""
        candidates = []
        for entry in self.registry.list("template"):
            template = entry["data"]["template"]
            candidates.append({"agent_id": entry["key"], "lifecycle": "ACTIVE", "qualification": "UNVERIFIED", "admission": {"valid": False, "revoked": False},
                               "capabilities": template.get("capabilities") if isinstance(template.get("capabilities"), list) else [], "stats": {"successes": 0, "runs": 0},
                               "available": "now", "resources": {}})
        return match(requirement, candidates, snapshot)
