from __future__ import annotations
from pathlib import Path
import yaml
from .errors import RegistryError, CompatibilityError

class Registry:
    def __init__(self, architecture_root: Path, core_contract=1):
        self.root=Path(architecture_root); self.core_contract=core_contract
        self.modules={}; self.services={}; self.skills={}; self.tools={}
    def _load_yaml(self,path): return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    def _validate_contract(self, component_id, data):
        compat=data.get("compatibility",{})
        contract=data.get("core_contract",compat.get("core_contract",self.core_contract))
        if int(contract) != self.core_contract: raise CompatibilityError(component_id)
    def load(self):
        reg=self.root/"core"/"registry"
        mod_data=self._load_yaml(reg/"module_registry.yaml").get("module_registry",{}).get("modules",{})
        for mid,meta in mod_data.items():
            manifest=self.root/meta["manifest"]
            data=self._load_yaml(manifest)["module"]
            if data["id"] != mid: raise RegistryError(f"Module id mismatch: {mid}")
            self._validate_contract(mid,data)
            self.modules[mid]={**meta,"data":data}
        sr=reg/"service_registry.yaml"
        if sr.exists():
            svc_data=self._load_yaml(sr).get("service_registry",{}).get("services",{})
            for sid,meta in svc_data.items():
                data=self._load_yaml(self.root/meta["manifest"])["service"]
                if data["id"] != sid: raise RegistryError(f"Service id mismatch: {sid}")
                self._validate_contract(sid,data)
                self.services[sid]={**meta,"data":data}
        skr=reg/"skill_registry.yaml"
        if skr.exists():
            for sid,meta in self._load_yaml(skr).get("skill_registry",{}).get("skills",{}).items():
                data=self._load_yaml(self.root/meta["manifest"])["skill"]
                if data["id"] != sid: raise RegistryError(f"Skill id mismatch: {sid}")
                self._validate_contract(sid,data)
                self.skills[sid]={**meta,"data":data}
        tr=reg/"tool_registry.yaml"
        if tr.exists():
            for tid,meta in self._load_yaml(tr).get("tool_registry",{}).get("tools",{}).items():
                data=self._load_yaml(self.root/meta["manifest"])["tool"]
                if data["id"] != tid: raise RegistryError(f"Tool id mismatch: {tid}")
                self._validate_contract(tid,data)
                self.tools[tid]={**meta,"data":data}
        return self
    def capabilities(self):
        out={}
        for mid,meta in self.modules.items(): out[mid]=meta["data"].get("capabilities",[])
        for sid,meta in self.skills.items(): out[f"skill:{sid}"]=meta["data"].get("capabilities",[])
        for tid,meta in self.tools.items(): out[f"tool:{tid}"]=meta["data"].get("capabilities",[])
        return out
    def health(self):
        return {"modules":len(self.modules),"services":len(self.services),"skills":len(self.skills),"tools":len(self.tools),"ok":True}
