from pathlib import Path
from ..core.request_binding import file_request
from ..core.util import atomic_write_text
from .base import BaseModule


class ControlMasterModule(BaseModule):
    id="control-master"
    def __init__(self,workspace: Path,guard,artifacts,audit=None,tools=None,model_router=None):
        self.workspace=Path(workspace); self.workspace.mkdir(parents=True,exist_ok=True)
        self.guard=guard; self.artifacts=artifacts; self.audit=audit; self.tools=tools; self.model_router=model_router

    def check_execution(self,mission,request):
        from ..feasibility import assess
        return assess(self,mission,request)

    def execute(self,mission,request,approval_token=None):
        mid=mission["identity"]["mission_id"]
        action=request.get("action","create_text_artifact")
        if self.audit: self.audit.append("EXECUTION_REQUESTED",component=self.id,mission_id=mid,payload={"action":action})
        if action == "model_inference" or 'execution_requirements' in request:
            check=self.check_execution(mission,request)
            if check['status']!='EXECUTABLE':
                return {'status':'waiting' if check['status']=='NOT_NOW' else 'blocked','feasibility':check,'reason_code':check['reason_code'],'artifacts':[]}
        if action == "candidate_acceptance":
            from ..selfdev.candidate_acceptance import apply
            return apply(self,request["runtime"],mission,request.get("plan"),approval_token)
        if action == "inspect_tools":
            return {"status":"completed","tools":self.tools.list() if self.tools else {},"artifacts":[]}
        if action == "model_inference":
            return self._model_inference(mid,request)
        if action == "tool_call":
            return self._tool_call(mid,request,approval_token,mission=mission)
        if action == "tool_sequence":
            return self._tool_sequence(mid,request,mission=mission)
        if action == 'inspect_project':
            if not getattr(self,'inspector',None):return {'status':'failed','error':'inspection_handler_unavailable','artifacts':[]}
            out=self.inspector.execute(self,mission,request.get('binding'),approval_token)
            self._audit_result(mid,'inspect_project',out)
            return out
        if action == 'prepare_code_candidate':
            if not getattr(self,'candidate_preparer',None):return {'status':'failed','error':'candidate_handler_unavailable','artifacts':[]}
            out=self.candidate_preparer.execute(self,mission,request.get('binding'),approval_token)
            self._audit_result(mid,'prepare_code_candidate',out)
            return out
        if action != 'create_text_artifact':
            return {'status':'failed','error':'unsupported_control_action','artifacts':[]}
        return self._create_text_artifact(mission,request,approval_token)

    def _model_inference(self,mid,request):
        if not self.model_router:
            return {"status":"failed","error":"model_router_unavailable","artifacts":[]}
        try:
            result=self.model_router.chat(mid,request.get("messages") or [],provider=request.get("provider"),model=request.get("model"),temperature=request.get("temperature"),max_tokens=request.get("max_tokens"),top_p=request.get("top_p"),reasoning_effort=request.get("reasoning_effort"),thinking_budget_tokens=request.get("thinking_budget_tokens"),stream_guard=request.get("stream_guard"),tools=request.get("tools"),tool_choice=request.get("tool_choice"))
            out={"status":"completed","model_result":result,"artifacts":[]}
            self._record_context_usage(mid,request,result)
        except Exception as exc:
            from ..feasibility import AdmissionUnavailable
            if isinstance(exc,AdmissionUnavailable):
                out={'status':'waiting','reason_code':exc.reason_code,'artifacts':[]}
            else:
                out={"status":"failed","error":f"{type(exc).__name__}:{exc}","artifacts":[]}
        self._audit_result(mid,"model_inference",out)
        return out

    def model_call(self,job_id,request):
        """The job worker's way to a model: same path, audit and usage metrics as a mission's inference, addressed by job id."""
        return self._model_inference(job_id,request)

    def resolve_role(self,role,requirements=None,**kw):
        """The one place that turns a role into a concrete provider. Raises role_routing.ResolutionError."""
        from ..models.role_routing import ResolutionError
        router=getattr(self,"role_router",None)
        if router is None or not router.enabled:
            raise ResolutionError("no_capability",{"reason":"role_routing_disabled"})
        return router.resolve_role(role,requirements,**kw)

    def resolve_fallback(self,previous,failure_class,requirements=None,**kw):
        from ..models.role_routing import ResolutionError
        router=getattr(self,"role_router",None)
        if router is None or not router.enabled:
            raise ResolutionError("no_capability",{"reason":"role_routing_disabled"})
        return router.resolve_fallback(previous,failure_class,requirements,**kw)

    def _record_context_usage(self,mid,request,result):
        """Measure only. A failure to measure is audited and never breaks the inference."""
        manager=getattr(self,"context_manager",None)
        if manager is None or not manager.enabled: return
        try:
            manager.record_usage(request.get("job_id") or mid,request.get("attempt_id") or "ATT-NONE",messages=request.get("messages") or [],
                                 usage=result.get("usage"),model_ref=f"{result.get('provider')}:{result.get('model')}",role=request.get("role"))
        except Exception as exc:
            if self.audit: self.audit.append("CONTEXT_METRICS_FAILED",component=self.id,mission_id=mid,payload={"error":type(exc).__name__})

    def _tool_call(self,mid,request,approval_token=None,mission=None):
        if not self.tools:
            return {"status":"failed","error":"tool_manager_unavailable","artifacts":[]}
        denied=self._route_tool_denial(mission,request.get("tool"))
        if denied: return denied
        try:
            result=self.tools.execute(request.get("tool"),mid,request.get("operation"),request.get("args") or {},approval_token)
        except Exception as exc:
            result={"status":"failed","error":f"{type(exc).__name__}:{exc}"}
        artifacts=self._register_result_artifact(mid,request,result)
        out={"status":result.get("status","failed"),"tool_result":result,"artifacts":artifacts}
        for key in ("gate","guard","error"):
            if key in result: out[key]=result[key]
        self._audit_result(mid,"tool_call",out)
        return out

    def _tool_sequence(self,mid,request,mission=None):
        if not self.tools:
            return {"status":"failed","error":"tool_manager_unavailable","artifacts":[]}
        steps=request.get("steps")
        if not isinstance(steps,list) or not steps:
            return {"status":"failed","error":"tool_sequence_requires_steps","artifacts":[]}
        if len(steps)>50:
            return {"status":"failed","error":"tool_sequence_too_long","artifacts":[]}
        start_at=max(0,int(request.get("start_at",0)))
        tokens=request.get("approval_tokens") or {}
        results=[]; artifacts=[]
        for index in range(start_at,len(steps)):
            step=steps[index]
            sid=str(step.get("id",f"step-{index}"))
            token=tokens.get(sid)
            denied=self._route_tool_denial(mission,step.get("tool"))
            if denied:
                result=denied
            else:
                try:
                    result=self.tools.execute(step.get("tool"),mid,step.get("operation"),step.get("args") or {},token)
                except Exception as exc:
                    result={"status":"failed","error":f"{type(exc).__name__}:{exc}"}
            step_out={"index":index,"id":sid,"tool":step.get("tool"),"operation":step.get("operation"),"result":result}
            results.append(step_out)
            artifacts.extend(self._register_result_artifact(mid,step,result))
            if result.get("status") != "completed":
                out={"status":result.get("status","failed"),"steps":results,"artifacts":artifacts,"resume_from":index}
                for key in ("gate","guard","error"):
                    if key in result: out[key]=result[key]
                self._audit_result(mid,"tool_sequence",out)
                return out
        out={"status":"completed","steps":results,"artifacts":artifacts,"resume_from":len(steps)}
        self._audit_result(mid,"tool_sequence",out)
        return out

    def _route_tool_denial(self,mission,tool_id):
        if not mission:
            return None
        route=(mission.get("routing") or {}).get("route") or {}
        if not route or not route.get("enforce_tool_allowlist",False):
            return None
        allowed={x.get("id") for x in route.get("tools",[]) if x.get("id")}
        if tool_id not in allowed:
            return {"status":"failed","error":f"tool_not_selected_by_capability_router:{tool_id}","artifacts":[]}
        return None

    def _register_result_artifact(self,mid,request,result):
        artifacts=[]
        if result.get("status") == "completed" and request.get("register_artifact") and result.get("path"):
            p=Path(result["path"])
            if p.exists() and p.is_file():
                artifacts.append(self.artifacts.register(mid,p,source_component=f"tool:{request.get('tool')}"))
        return artifacts

    def _create_text_artifact(self,mission,request,approval_token=None):
        mid=mission["identity"]["mission_id"]
        mdir=self.workspace/mid; mdir.mkdir(parents=True,exist_ok=True)
        target=Path(request.get("target") or (mdir/"result.txt"))
        if not target.is_absolute(): target=mdir/target
        target=target.resolve()
        try: target.relative_to(mdir.resolve())
        except ValueError: return {"status":"failed","error":"target_outside_mission_workspace","artifacts":[]}
        guard_action="overwrite_existing" if target.exists() else "create_new_artifact"
        content=request.get("content") or f"GUPPI mission {mid}\nObjective: {mission['objective']['current']}\n"
        binding=file_request('create_text_artifact',{'content':content,'plan_revision':mission.get('plan_revision',0),'objective_version':mission['objective']['version']},target)
        verdict=self.guard.evaluate(guard_action,mission_id=mid,target=str(target))
        if verdict["decision"]=="BLOCK": return {"status":"blocked","guard":verdict,"artifacts":[]}
        if verdict["decision"]=="CAPTAIN_REQUIRED":
            auth=self.guard.authorize(approval_token,mission_id=mid,action=guard_action,target=str(target),request_binding=binding)
            if not auth["authorized"]:
                gate=self.guard.create_gate(mid,guard_action,str(target),rollback_available=True,request_binding=binding)
                return {"status":"captain_required","guard":verdict,"gate":gate,"artifacts":[]}
        target.parent.mkdir(parents=True,exist_ok=True)
        if guard_action=="create_new_artifact":
            # The Guard allowed a NEW file; one that appeared since the check must not be overwritten without the overwrite gate.
            try:
                with target.open("x",encoding="utf-8") as stream: stream.write(content)
            except FileExistsError:
                return {"status":"failed","error":"target_appeared_after_guard_check","artifacts":[]}
        else:
            atomic_write_text(target,content)      # an approved overwrite never leaves a half-written file behind
        rec=self.artifacts.register(mid,target,source_component=self.id)
        out={"status":"completed","artifacts":[rec],"result":{"path":str(target)}}
        self._audit_result(mid,"create_text_artifact",out)
        return out

    def _audit_result(self,mid,action,out):
        if not self.audit: return
        status=out.get("status")
        event={"completed":"EXECUTION_COMPLETED","waiting":"EXECUTION_WAITING","blocked":"EXECUTION_BLOCKED","captain_required":"EXECUTION_GATE_PENDING"}.get(status,"EXECUTION_FAILED")
        self.audit.append(event,component=self.id,mission_id=mid,payload={"action":action,"status":status,"error":out.get("error")})

    def handle(self,message): return self.execute(message.payload["mission"],message.payload["request"],message.payload.get("approval_token"))
