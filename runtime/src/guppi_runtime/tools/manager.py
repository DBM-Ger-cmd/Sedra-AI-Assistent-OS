from __future__ import annotations
from .base import ToolValidationError


class ToolManager:
    def __init__(self, audit=None, registry_tools=None):
        self.audit = audit
        self.tools = {}
        self.required = {}
        self.registry_tools = registry_tools if registry_tools is not None else None

    def register(self, tool, *, required=None):
        if tool.id in self.tools:
            raise ToolValidationError(f"duplicate_tool:{tool.id}")
        if self.registry_tools is not None:
            meta=self.registry_tools.get(tool.id)
            if meta is None:
                raise ToolValidationError(f"tool_not_in_registry:{tool.id}")
            if not meta.get("enabled",True):
                raise ToolValidationError(f"tool_disabled_in_registry:{tool.id}")
            manifest=meta.get("data",{})
            manifest_version=str(manifest.get("version",""))
            if manifest_version and getattr(tool,"version",manifest_version) != manifest_version:
                raise ToolValidationError(f"tool_version_mismatch:{tool.id}:{getattr(tool,'version',None)}!={manifest_version}")
            required=meta.get("required",False) if required is None else required
        if required is None: required=True
        self.tools[tool.id] = tool
        self.required[tool.id] = bool(required)

    def list(self):
        out={}
        all_ids=set(self.tools)
        if self.registry_tools is not None: all_ids |= set(self.registry_tools)
        for tid in sorted(all_ids):
            tool=self.tools.get(tid); meta=(self.registry_tools or {}).get(tid,{})
            out[tid]={
                "registered":tool is not None,
                "healthy":bool(tool.health()) if tool else False,
                "required":self.required.get(tid,meta.get("required",False)),
                "enabled":meta.get("enabled",True),
                "version":getattr(tool,"version",None) if tool else meta.get("version"),
                "operations":sorted(getattr(tool,"supported_operations",set())) if tool else [],
            }
        return out

    def execute(self, tool_id, mission_id, operation, args=None, approval_token=None):
        tool = self.tools.get(tool_id)
        if tool is None:
            raise ToolValidationError(f"unknown_or_unavailable_tool:{tool_id}")
        supported=getattr(tool,"supported_operations",set())
        if supported and operation not in supported:
            raise ToolValidationError(f"unsupported_operation:{tool_id}:{operation}")
        if self.audit:
            self.audit.append("EXECUTION_REQUESTED",component="tool-manager",mission_id=mission_id,payload={"tool":tool_id,"operation":operation})
        return tool.execute(mission_id, operation, args or {}, approval_token)

    def health(self):
        if self.registry_tools is not None:
            for tid,meta in self.registry_tools.items():
                if meta.get("enabled",True) and meta.get("required",False):
                    tool=self.tools.get(tid)
                    if tool is None or not bool(tool.health()): return False
        return all(bool(tool.health()) for tid,tool in self.tools.items() if self.required.get(tid,True))
