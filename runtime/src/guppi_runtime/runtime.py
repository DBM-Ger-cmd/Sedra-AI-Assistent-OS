from __future__ import annotations
from pathlib import Path
import os
import re
import yaml
from .core.audit import AuditLog
from .core.util import load_json
from .core.mission import MissionStore
from .core.message_bus import MessageBus
from .core.registry import Registry
from .capability_router import CapabilityRouter
from .topics import TopicStore
from .selfdev.execution_binder import ExecutionParameterBinder
from .selfdev.project_inspection import ProjectInspector
from .selfdev.code_candidate import CandidateBinder, CandidatePreparer
from .core.guard import Guard
from .artifacts import ArtifactStore
from .observability import Observability
from .knowledge import KnowledgeStore
from .hardware import detect_hardware
from .hardware_manager import HardwareManager
from .tools.hardware_manager import HardwareManagerTool
from .models.model_profiles import ModelProfileStore
from .models.model_runtime import ModelRuntimeManager
from .models import ModelRouter, LMStudioAdapter, LlamaCppServerAdapter
from .models.cloud_api import build_cloud_adapters
from . import cloud_settings
from .cloud_settings import CloudKeyStore
from .tools import ToolManager, FilesystemTool, GitTool, ShellTool, ModelRuntimeTool
from .modules.planning import PlanningContextModule
from .modules.control import ControlMasterModule
from .modules.verification import VerificationModule
from .modules.knowledge_module import KnowledgeModule
from .modules.communications import CommunicationsModule
from .core.brain import GuppiBrain
from .sandbox import SandboxBroker, MicrosandboxProvider
from .jobs.context_budget import ContextBudgetManager
from .selfdev.development_evidence import DevelopmentEvidenceStore
from .selfdev.kev import KevVerificationProvider
from .selfdev.self_development import SelfDevelopmentManager
from .selfdev.evolution import EvolutionManager
from .jobs.job_supervisor import JobSupervisor, SupervisorConfig, SupervisorJobStore
from .jobs.context_manager import ContextManager, ContextConfig
from .models.role_routing import RoutingConfig, RoleRouter, ProviderHealth
from .models.routing_profiles import RoutingProfiles
from .core.permission_levels import PermissionConfig, PermissionGate
from .jobs.resource_scheduler import ResourceConfig, ResourceScheduler
from .models.model_loader import LoaderConfig, ModelLoader
from .jobs.token_policy import TokenPolicy, TokenPolicyConfig
from .local_switches import LocalSwitches
from .models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
from .jobs.verification_gate import VerificationGate
from .jobs.working_set import WorkingSet
from .models.runtime_control import LMStudioRuntimeController
from .orchestra import service as orchestra_service
from .orchestra.config import OrchestraConfig
from .orchestra.store import open_db as orchestra_open_db

def _architecture_version(path):
    """(1, 20) for GUPPI_Architecture_v1.20_SELF_DEVELOPMENT. Numbers, not text: v1.9 is older than v1.20."""
    match=re.match(r"GUPPI_Architecture_v(\d+(?:\.\d+)*)",Path(path).name)
    return (tuple(int(x) for x in match.group(1).split(".")) if match else (),Path(path).name)

class GuppiRuntime:
    ORCHESTRA_CONFIG="orchestra.yaml"      # unter config_root; die Paket-Vorgabe (Spec 0, D3.4)

    def __init__(self,project_root: Path, architecture_root: Path|None=None):
        self.project_root=Path(project_root).resolve(); self.project_root.mkdir(parents=True,exist_ok=True)
        if architecture_root is None:
            candidates=sorted((self.project_root.parent/"architecture").glob("GUPPI_Architecture_v*"),key=_architecture_version)
            if not candidates: raise FileNotFoundError("architecture root required")
            architecture_root=candidates[-1]
        self.architecture_root=Path(architecture_root).resolve()
        self.config_root=Path(__file__).resolve().parents[2]/"config"
        data=self.project_root/"runtime_data"; data.mkdir(parents=True,exist_ok=True)
        self.audit=AuditLog(data/"audit"/"events.jsonl")
        self.missions=MissionStore(data/"missions",self.audit)
        self.registry=Registry(self.architecture_root).load()
        self.guard=Guard(self.architecture_root/"core"/"guard"/"guard_rules.yaml",self.audit,data/"guard"/"approval_tokens.json")
        self.missions.guard=self.guard
        self.artifacts=ArtifactStore(data/"artifacts",self.audit)
        self.knowledge=KnowledgeStore(data/"knowledge"/"records.jsonl")
        self.context_budget=ContextBudgetManager()
        self.development_evidence=DevelopmentEvidenceStore(data/"self_development"/"evidence.jsonl", self.audit)
        kev_cfg=(yaml.safe_load((self.config_root/"kev.yaml").read_text(encoding="utf-8")) or {}).get("kev",{}) if (self.config_root/"kev.yaml").exists() else {}
        # The API key is read from the environment variable the config names; it is never written to a file here.
        kev_key=os.environ.get(kev_cfg.get("api_key_env","KEV_API_KEY")) if kev_cfg.get("api_key_env","KEV_API_KEY") else None
        self.kev=KevVerificationProvider(kev_cfg.get("endpoint","http://127.0.0.1:8008/v1/systemone"), enabled=bool(kev_cfg.get("enabled",False)),
                                         model=kev_cfg.get("model","kev-latest"), api_key=kev_key)
        self.evolution=EvolutionManager()
        self.bus=MessageBus(self.audit)
        self.observability=Observability()

        self.tools=ToolManager(self.audit,self.registry.tools)
        tool_root=data/"tool_workspace"
        self.filesystem_tool=FilesystemTool(tool_root,self.guard,self.audit)
        self.git_tool=GitTool(tool_root,self.guard,self.audit)
        self.shell_tool=ShellTool(tool_root,self.guard,self.audit)
        self.tools.register(self.filesystem_tool,required=True)
        self.tools.register(self.git_tool,required=False)
        self.tools.register(self.shell_tool,required=True)
        from .tools.web import WebTool, WebAccessConfig      # read-only web access, domain list (2026-10-03)
        self.web_tool=WebTool(tool_root,self.guard,self.audit,config=WebAccessConfig.load(self.config_root/"web_access.yaml"),store_dir=data/"external")
        # Only where the architecture lists the tool (tools/web/tool.yaml); older architectures simply run without it.
        if getattr(self.registry,"tools",None) is None or "web" in self.registry.tools: self.tools.register(self.web_tool,required=False)

        self.sandbox_provider=MicrosandboxProvider(data/"sandboxes"/"backend_home", self.config_root.parent)
        self.sandbox=SandboxBroker(tool_root,data/"sandboxes",self.config_root/"sandbox.yaml",self.sandbox_provider,self.guard,self.audit)
        self.sandbox.path_health_source=self._open_candidate_bindings
        self.tools.register(self.sandbox,required=False)

        self.hardware=detect_hardware()
        self.hardware_manager=HardwareManager(data/"hardware", self.audit)
        self.hardware_manager_tool=HardwareManagerTool(tool_root,self.hardware_manager,self.guard,self.audit)
        self.tools.register(self.hardware_manager_tool,required=False)
        self.model_profiles=ModelProfileStore(self.config_root/"model_profiles.yaml",data/"profiles"/"custom_profiles.yaml",data/"profiles"/"known_good_profiles.yaml")
        self.recommended_model_profile=self.model_profiles.select_for_hardware(self.hardware.hardware_class)
        self.model_runtime=ModelRuntimeManager(self.config_root/"model_runtimes.yaml",data,self.config_root.parent/"portable",self.hardware,self.model_profiles,self.audit)
        self.model_runtime.hardware_manager=self.hardware_manager
        self.model_runtime_tool=ModelRuntimeTool(tool_root,self.model_runtime,self.guard,self.audit)
        self.tools.register(self.model_runtime_tool,required=False)
        self.model_router=ModelRouter(self.audit)
        self.model_router.hardware_manager=self.hardware_manager
        # Build 16 (SPEC_EIN_SICHERER_WEG S1/S2): jeder Modellaufruf geht durch den Inhaltsschutz; der Modus kommt vom Desk (S5).
        from .core.content_guard import ContentGuard
        self.content_guard=ContentGuard(audit=self.audit,mode='sandbox')      # G-04 (Ticket B6-G-01, 15.10.2026): Standard ist scharf
        self.model_router.content_guard=self.content_guard
        if os.environ.get("GUPPI_RECORD_REPLIES","").strip().lower() in {"1","true","yes"}:   # off by default; local files only (models/recording.py)
            from .models.recording import Recorder
            self.model_router.recorder=Recorder(data/"model_recordings")
        self._configure_model_runtimes()
        self._configure_cloud_providers()
        self._load_switches()
        self._configure_role_routing(data)

        self.topic_store=TopicStore(data/'topics', self.audit)
        self.capability_router=CapabilityRouter(self.registry,self.config_root/"capability_router.yaml",self.audit,self.tools,self.topic_store)
        self.self_development=SelfDevelopmentManager(self.registry,data,audit=self.audit,knowledge=self.knowledge,context_budget=self.context_budget,kev=self.kev,config_path=self.config_root/"self_development.yaml",evidence_store=self.development_evidence)
        self._configure_llama_server(data)
        self._configure_job_supervisor(data)
        self._configure_orchestra(data)
        self._configure_wissen(data)
        self._configure_context_manager(data)
        self._configure_token_policy()
        self.planner=PlanningContextModule(self.knowledge)
        self.execution_binder=CandidateBinder(self.filesystem_tool,self.tools)
        self.planner.binder=self.execution_binder
        self.control=ControlMasterModule(data/"workspace",self.guard,self.artifacts,self.audit,self.tools,self.model_router)
        self.control.context_manager=self.context_manager   # measurement only, and only when context_manager.enabled
        self.control.role_router=self.role_router           # the only place a role becomes a provider; inert unless role_routing.enabled
        self.control.missions=self.missions
        self.control.inspector=ProjectInspector(self.execution_binder)
        self.control.candidate_preparer=CandidatePreparer(self.execution_binder)
        self.verifier=VerificationModule()
        self.verifier.inspection_binder=self.execution_binder
        self.verifier.tools=self.tools
        self.verifier.workspace=self.control.workspace
        self.knowledge_module=KnowledgeModule(self.knowledge)
        self.communications=CommunicationsModule()
        for mod in (self.planner,self.control,self.verifier,self.knowledge_module,self.communications): self.bus.register(mod.id,mod.handle)
        self.brain=GuppiBrain(self.missions,self.bus,self.planner,self.control,self.verifier,self.guard,self.audit,capability_router=self.capability_router)
        self.observability.register("registry",lambda:self.registry.health()["ok"])
        self.observability.register("audit",self.audit.verify_chain)
        self.observability.register("tool-manager",self.tools.health)
        self.observability.register("capability-router",self.capability_router.health)
        self.observability.register("development-evidence",self.development_evidence.verify_chain)
        for mod in (self.planner,self.control,self.verifier,self.knowledge_module,self.communications): self.observability.register(mod.id,mod.health)

    def _optional(self,name,build,*,error=None):
        """One switchable part: `build()` makes it. A missing or invalid config (ValueError) leaves the part None and keeps the
        reason in `<name>_error` (or `error`), so the status views say why instead of the runtime failing to start."""
        error=error or name+"_error"
        setattr(self,name,None); setattr(self,error,None)
        try:
            setattr(self,name,build())
        except ValueError as exc:
            setattr(self,error,str(exc))
        return getattr(self,name)

    def _configure_orchestra(self,data):
        """Spec 0 (D3.5): die Orchestrierung nur bei eingeschaltetem Schalter `orchestra` (OP-14: `enabled` in der Datei schaltet allein
        nicht ein). Fehlt die Konfiguration, ist sie ungültig oder öffnet die Datenbank nicht, bleibt sie aus und sagt warum
        (`orchestra_error`, einmal Audit ORCHESTRA_OFF). READY hängt davon nicht ab."""
        def build():
            orchestra,error=orchestra_service.build(self.switches.apply("orchestra","enabled",False),OrchestraConfig.load,orchestra_open_db,
                                                    self.config_root/self.ORCHESTRA_CONFIG,data,
                                                    audit=lambda event,payload: self.audit.append(event,component="orchestra",payload=payload),
                                                    guard=self.guard,supervisor=self.job_supervisor)
            if error: raise ValueError(error)
            return orchestra
        self._optional("orchestra",build)

    def _configure_wissen(self,data):
        """Spec 7 (D7.1, G2-S7-q): der Wissensspeicher nur bei eingeschaltetem Schalter `wissen`. Fehlt die Konfiguration, ist sie
        ungültig oder öffnet die Datei nicht, bleibt er aus und sagt warum (`wissen_error`, einmal Audit WISSEN_OFF). READY hängt
        davon nicht ab. Das Einbetten läuft nur auf der CPU; die Lage der GPU liest er aus dem Testlabor (D7.4)."""
        def build():
            if self.switches.apply("wissen","enabled",False) is not True: return None
            from .wissen import konfig as wissen_konfig
            from .wissen.speicher import WissenSpeicher
            from .wissen.embed import TestLabZugang
            from .jobs.testlab import TestLab, default_path
            cfg=wissen_konfig.load(self.config_root/"wissen.yaml",self.project_root/"local_config"/"wissen.yaml")
            try:                                                  # ein Fehler beim Öffnen schaltet nur `wissen` aus, nie den Start
                lab=TestLab(default_path(self.project_root))
            except Exception as exc:
                raise ValueError("wis_testlab_nicht_lesbar:"+(str(exc) or type(exc).__name__)[:80]) from None
            return WissenSpeicher.oeffnen(cfg,projekt_root=self.project_root,repo_root=self.config_root.parents[1],
                                          audit=lambda event,payload: self.audit.append(event,component="wissen",payload=payload),
                                          gpu=TestLabZugang(lab))
        self._optional("wissen",build)
        if self.wissen_error: self.audit.append("WISSEN_OFF",component="runtime",payload={"reason":self.wissen_error})

    def wissen_status(self):
        if self.wissen is None: return {"enabled":False,"error":self.wissen_error}
        try: stand=self.wissen.stand()
        except Exception as exc: return {"enabled":True,"error":str(exc) or type(exc).__name__}
        return {"enabled":True,"error":None,"modus":stand["modus"],"abschnitte":stand["abschnitte"],"abdeckung":stand["abdeckung"],"quellen":stand["quellen"]}

    def _configure_job_supervisor(self,data):
        """The supervisor stays off (and says why) when its config is missing or invalid."""
        self.job_supervisor=None; self.job_supervisor_error=None
        # Set before the first early return: boot() and the status views read these even when the supervisor stays off.
        self.resource_scheduler=None; self.resource_error=None
        self.permission_gate=None; self.permission_error=None
        self.model_loader=None; self.model_loader_error=None
        try:
            config=SupervisorConfig.load(self.config_root/"job_supervisor.yaml")
            config.enabled=self.switches.apply("job_supervisor","enabled",config.enabled)
        except ValueError as exc:
            self.job_supervisor_error=str(exc); return
        def resources():   # reservations only matter when enabled; a broken file leaves no scheduler and says why
            resource_config=ResourceConfig.load(self.config_root/"resource_scheduler.yaml")
            resource_config.enabled=self.switches.apply("resource_scheduler","enabled",resource_config.enabled)
            return ResourceScheduler(resource_config,self.hardware_manager,data/"resource_reservations.json",audit=self.audit)
        self._optional("resource_scheduler",resources,error="resource_error")
        if self.resource_scheduler is not None and self.resource_scheduler.enabled and self.role_router is not None:
            # Advisory only. A model that is already loaded holds its own room (reused as it is, or unloaded and reloaded by the
            # model loader); the binding reservation checks again afterwards.
            self.role_router.load_check=lambda recipe,estimated,req: self.resource_scheduler.explain(
                estimated,exclusive=req["exclusive"],
                resident_vram_gb=(estimated.get("vram_gb") or 0.0) if getattr(self,"model_loader",None) is not None and self.model_loader.enabled and self.model_loader.loaded(recipe["model"]) else 0.0)
        # No gate (missing or invalid config) means the supervisor can check no action, so it allows none.
        self._optional("permission_gate",lambda: PermissionGate(PermissionConfig.load(self.config_root/"permission_levels.yaml"),self.guard,audit=self.audit),
                       error="permission_error")
        jobs_store=SupervisorJobStore(data/"jobs",self.audit)
        self.verification_gate=VerificationGate(self.development_evidence,jobs_store.load)
        self.job_supervisor=JobSupervisor(jobs_store,config,audit=self.audit,guard=self.guard,permissions=self.permission_gate,scheduler=self.resource_scheduler,
                                          pass_gate=self.verification_gate.gaps)
        try:   # the loader needs the `lms` CLI; without it the supervisor simply leaves context to the provider and says why
            loader_config=LoaderConfig.load(self.config_root/"model_loader.yaml")
            loader_config.enabled=self.switches.apply("model_loader","enabled",loader_config.enabled)
            loader_config.evict_idle_models=self.switches.apply("model_loader","evict_idle_models",loader_config.evict_idle_models)
            lm_cfg=(yaml.safe_load((self.config_root/"model_runtimes.yaml").read_text(encoding="utf-8")) or {}).get("model_runtimes",{}).get("lm-studio",{})
            controller=LMStudioRuntimeController(lm_cfg.get("executable"),endpoint=lm_cfg.get("endpoint","http://127.0.0.1:1234"),enabled=lm_cfg.get("enabled",True))
            managed=self.llama_server
            if loader_config.enabled and not controller.available() and not (managed and managed.available()): self.model_loader_error="no_model_runtime_controller_available"
            else:
                self.model_loader=ModelLoader(loader_config,controller,audit=self.audit,controllers={"llama-cpp-server":managed} if managed else None)
                self.job_supervisor.loader=self.model_loader
        except (ValueError,OSError) as exc:
            self.model_loader_error=str(exc)
        if self.role_router is not None and self.role_router.enabled:
            self.job_supervisor.resolver=lambda role,req,exclude,independent_of: self.control.resolve_role(role,req,exclude=exclude,independent_of=independent_of)
            self.job_supervisor.provider_report=self._report_provider
            from .models.role_routing import check_independence
            self.self_development.independence_check=lambda builder,verifier: check_independence(
                self.role_router.key_for_role(builder),self.role_router.key_for_role(verifier))

    def reload_role_routing(self):
        """Das Routing-Overlay ohne Neustart neu lesen: eine im Menü freigegebene Änderung (z. B. der Kontext eines Modells) wirkt beim
        nächsten Laden. Der Router liest seine Rezepte bei jedem Aufruf aus `config`; die Gesundheit der Anbieter bleibt erhalten.
        Ein ungültiges Overlay wirft, und die bisherige Konfiguration bleibt (fail-closed)."""
        if self.role_router is None: raise ValueError("role_routing_unavailable")
        config=RoutingConfig.load(self.config_root/"role_routing.yaml",self.project_root/"local_config"/"role_routing.yaml")
        self.role_router.config=config
        self.audit.append("ROUTING_RELOADED",component="runtime",payload={"recipes":[r["id"] for r in config.recipes]})
        return config

    def _configure_role_routing(self,data):
        """Role routing stays off (and says why) when its config is missing or invalid. Provider health only
        reaches the model router when routing is enabled, so v1.20 behaviour is unchanged otherwise."""
        self.role_router=None; self.provider_health=None; self.role_routing_error=None
        try:
            config=RoutingConfig.load(self.config_root/"role_routing.yaml",self.project_root/"local_config"/"role_routing.yaml")
        except ValueError as exc:
            self.role_routing_error=str(exc); return
        self.provider_health=ProviderHealth(config,data/"provider_health.json",audit=self.audit)
        # The Captain's switchable model combination (routing_profiles.py). A broken profile file never stops routing: the router
        # then keeps its recipe order and routing_status says why.
        self._optional("routing_profiles",lambda: RoutingProfiles.load(self.project_root/"local_config"/"routing_profiles.yaml",
                                                                       known_ids={r["id"] for r in config.recipes}))
        self.role_router=RoleRouter(config,snapshot=self.hardware,health=self.provider_health,audit=self.audit,profiles=self.routing_profiles)
        if config.enabled: self.model_router.provider_health=self.provider_health

    def resource_status(self):
        if self.resource_scheduler is None: return {"enabled":False,"error":self.resource_error}
        return self.resource_scheduler.view()

    def permission_status(self):
        if self.permission_gate is None: return {"available":False,"error":self.permission_error}
        cfg=self.permission_gate.config
        return {"available":True,"levels":cfg.names,"actions":{a:s["level"] for a,s in sorted(cfg.actions.items())},
                "never_automatic":sorted(cfg.never),"policy_hash":self.permission_gate.policy_hash()}

    def routing_status(self):
        if self.role_router is None: return {"enabled":False,"error":self.role_routing_error}
        return {**self.role_router.view(),"profiles":self.routing_profiles.view() if self.routing_profiles else None,
                "profiles_error":getattr(self,"routing_profiles_error",None)}

    def _report_provider(self,provider_ref,outcome,failure_class=None):
        if self.provider_health is None: return
        if outcome=="success": self.provider_health.report_success(provider_ref)
        else: self.provider_health.report_failure(provider_ref,failure_class)

    def _configure_llama_server(self,data):
        """GUPPI's own llama-server (llama_server_runtime.py). Off by default. When on, the model router's `llama-cpp-server` provider
        points at the endpoint GUPPI manages instead of the generic 8080 one."""
        self.llama_server=None; self.llama_server_error=None; self.llama_canary_warning=None
        try:
            config=LlamaServerConfig.load(self.config_root/"llama_server.yaml")
            config.enabled=self.switches.apply("llama_server","enabled",config.enabled)
            config.mtp=self.switches.apply("llama_server","mtp",config.mtp)
            if not config.enabled: return
            self.llama_server=LlamaServerRuntime(config,data/config.log_dir,audit=self.audit)
            if config.canary.config_error:      # Entscheidung 2026-10-19: der Server läuft ohne Canary; die Ursache steht im Audit und im Status
                self.llama_canary_warning=config.canary.config_error
                self.audit.append("LLAMA_CANARY_OFF",component="runtime",payload={"grund":config.canary.config_error})
            if not self.llama_server.available(): self.llama_server_error="llama_server_executable_not_found"
            self.model_router.adapters["llama-cpp-server"]=LlamaCppServerAdapter(self.llama_server.endpoint,timeout=600)
        except ValueError as exc:
            self.llama_server_error=str(exc)

    def _load_switches(self):
        """Machine-local on/off switches (local_config/switches.yaml). A broken file applies none of them and says why."""
        self.switches_error=None
        try:
            self.switches=LocalSwitches.load(self.project_root/"local_config"/"switches.yaml")
        except ValueError as exc:
            self.switches=LocalSwitches(); self.switches_error=str(exc)
        if self.switches.problems:      # ungültige Abschnitte werden übersprungen, aber nicht still
            self.audit.append("LOCAL_SWITCHES_PARTLY_IGNORED",component="runtime",payload={"problems":self.switches.problems})
        if self.switches.values:
            self.audit.append("LOCAL_SWITCHES_APPLIED",component="runtime",payload=self.switches.summary())
        elif self.switches_error:
            self.audit.append("LOCAL_SWITCHES_REFUSED",component="runtime",payload={"error":self.switches_error})

    def _configure_token_policy(self):
        """Per-role reasoning effort and output budgets. Off by default; a broken file leaves no policy and says why."""
        def policy():
            token_config=TokenPolicyConfig.load(self.config_root/"token_policy.yaml")
            token_config.enabled=self.switches.apply("token_policy","enabled",token_config.enabled)
            return TokenPolicy(token_config)
        self._optional("token_policy",policy)

    def working_set(self,job,*,task,window,**kw):
        """The history of one job, kept outside the prompt (working_set.py). `window` is the context the provider really loaded
        (the attempt's `loaded_context`), so the working set compacts against the real limit, not a configured one."""
        manager=self.context_manager
        if manager is None or not manager.enabled: raise ValueError("context_manager_disabled")
        manifest=manager.assembly.build_manifest(job,task=task,budget=manager.budget_manager.build_budget(int(window)))
        return WorkingSet(manager,self.project_root/"runtime_data"/"working_sets",job,manifest=manifest,**kw)

    def worker_handler(self,build_messages,**kw):
        """A model handler for the job worker wired to this runtime: same inference path, the token policy, and the context
        manager's pessimistic estimate of the input."""
        from .jobs.job_worker import model_text_handler
        estimate=None
        if self.context_manager is not None:
            estimate=lambda messages: self.context_manager.estimator.estimate_messages(messages)["estimate"]
        if "on_degenerate" not in kw:
            kw["on_degenerate"]=self._stop_degenerate_server
        return model_text_handler(self.control.model_call,build_messages,policy=self.token_policy,estimate_tokens=estimate,**kw)

    def _stop_degenerate_server(self,attempt,reason):
        """A llama-server that emits garbage stays broken; stop it so the next attempt starts a fresh process. LM Studio is
        left alone: it may hold a model the Captain loaded by hand."""
        self.audit.append("MODEL_OUTPUT_DEGENERATE",component="job-worker",payload={"provider":attempt.get("provider_ref"),"model":attempt.get("model"),"reason":reason})
        if attempt.get("provider_ref")=="llama-cpp-server" and self.llama_server is not None:
            self.llama_server.unload_model(all_models=True)

    def _configure_context_manager(self,data):
        """Measurement, offloading and checkpoints stay off (and say why) when config is missing or invalid."""
        def manager():
            config=ContextConfig.load(self.config_root/"job_supervisor.yaml")
            config.enabled=self.switches.apply("context_manager","enabled",config.enabled)
            return ContextManager(data,config,artifacts=self.artifacts,audit=self.audit,
                                  evidence_store=self.development_evidence,budget_manager=self.context_budget)
        self._optional("context_manager",manager)

    def context_status(self):
        if self.context_manager is None: return {"enabled":False,"error":self.context_manager_error}
        return self.context_manager.status()

    def job_supervisor_status(self):
        if self.job_supervisor is None: return {"enabled":False,"error":self.job_supervisor_error}
        return self.job_supervisor.view()

    def _configure_model_runtimes(self):
        path=self.config_root/"model_runtimes.yaml"
        if not path.exists(): return
        cfg=(yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("model_runtimes",{})
        lm=cfg.get("lm-studio",{})
        if lm.get("enabled",False): self.model_router.register(LMStudioAdapter(lm.get("endpoint","http://127.0.0.1:1234")))
        lc=cfg.get("llama-cpp-server",{})
        if lc.get("enabled",False): self.model_router.register(LlamaCppServerAdapter(lc.get("endpoint","http://127.0.0.1:8080")))

    def _configure_cloud_providers(self):
        """Cloud-APIs mit Schlüssel (models/cloud_api.py). Standard AUS: ohne eingeschalteten Hauptschalter und Anbieter wird nichts
        gebaut und der Cloudweg bleibt gesperrt. Eingeschaltet: die Adapter kommen in den Router, der Inhaltsschutz erlaubt den Cloudweg,
        und jeder Aufruf prüft das Regelwerk. Der Router wählt Cloud nie von selbst (models/router.py choose)."""
        self.cloud_providers_error=None
        self.cloud_key_store=CloudKeyStore(cloud_settings.key_store_path(self.project_root))
        try:
            cfg=cloud_settings.load_config(self.project_root)          # local_config (Einstellungen-Fenster) vor config/
            adapters=build_cloud_adapters(cfg,key_store=self.cloud_key_store)
        except (ValueError,OSError,yaml.YAMLError) as exc:
            self.cloud_providers_error=str(exc); adapters=[]           # fail-closed: ein kaputter Eintrag schaltet nichts ein
        self.cloud_boot_signature=cloud_settings.signature(self.project_root,self.cloud_key_store)
        for adapter in adapters: self.model_router.register(adapter)
        self.content_guard.cloud_enabled=bool(adapters)
        if self.audit and adapters:
            self.audit.append("CLOUD_PROVIDERS_ENABLED",component="runtime",payload={"providers":[a.id for a in adapters]})

    def _open_candidate_bindings(self):
        """(project root, [{"mission_id", "host_root"}]) for path_health: the folder each open candidate (CANDIDATE_REVIEW) was
        prepared in. A closed mission is history and cannot block anything, so it is not listed."""
        reports=[]
        for m in self.missions.list():
            if m['lifecycle']['phase']!='CANDIDATE_REVIEW':continue
            mid=m['identity']['mission_id']
            report=load_json(self.control.workspace/mid/'candidate-report.json',{}) or {}
            host_root=(report.get('sandbox_plan') or {}).get('host_root')
            if isinstance(host_root,str) and host_root:reports.append({'mission_id':mid,'host_root':host_root})
        return str(self.project_root.resolve()),reports

    def boot(self):
        self.audit.append("BOOT_STARTED")
        status=self.observability.overall()
        if status=="HEALTHY": self.audit.append("SYSTEM_READY")
        else: self.audit.append("SAFE_MODE_ENTERED",payload={"health":status})
        # The three slow probes each wait on an external program (PowerShell inventory, LM Studio's CLI, nvidia-smi) and do not
        # depend on each other; in sequence they took ~1.6 of 1.8 s (measured 2026-10-02). Same results, run side by side.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3,thread_name_prefix="boot-probe") as pool:
            capabilities=pool.submit(self.hardware_manager.capabilities)
            portable=pool.submit(self.model_runtime.status)
            resources=pool.submit(self.resource_status)
            capabilities,portable,resources=capabilities.result(),portable.result(),resources.result()
        return {
            "state":"READY" if status=="HEALTHY" else "SAFE_MODE",
            "health":self.observability.report(),
            "registry":self.registry.health(),
            "tools":self.tools.list(),
            "capability_router":{"healthy":self.capability_router.health(),"skills":len(self.registry.skills)},
            "sandbox":self.sandbox.doctor(),
            "hardware":self.hardware.to_dict(),
            "hardware_manager":{"capabilities":capabilities, "profile_state":self.hardware_manager.state_record()},
            "recommended_model_profile":self.recommended_model_profile,
            "model_runtimes":self.model_router.status(check_health=False),
            "portable_model_runtime":portable,
            "self_development":self.self_development.view(),
            "job_supervisor":self.job_supervisor_status(),
            "context_manager":self.context_status(),
            "role_routing":self.routing_status(),
            "permissions":self.permission_status(),
            "resources":resources,
            "local_switches":{**self.switches.summary(),"error":self.switches_error,"ignored":list(self.switches.problems)},
            "model_loader":{"enabled":bool(self.model_loader and self.model_loader.enabled),
                            "evict_idle_models":bool(self.model_loader and self.model_loader.config.evict_idle_models),"error":self.model_loader_error},
            "token_policy":{"enabled":bool(self.token_policy and self.token_policy.enabled),"error":self.token_policy_error},
            "llama_server":{**(self.llama_server.status() if self.llama_server else {"enabled":False}),"error":self.llama_server_error},
            "orchestra":orchestra_service.boot_entry(self.orchestra,self.orchestra_error),
            "wissen":self.wissen_status(),
        }
