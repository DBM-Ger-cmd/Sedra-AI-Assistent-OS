"""Technical prerequisites; never an authorization or resource reservation."""
from datetime import datetime,timezone,timedelta
from .core.request_binding import digest
from .core.util import utcnow


class AdmissionUnavailable(RuntimeError):
    def __init__(self,reason_code):
        self.reason_code=reason_code
        super().__init__(reason_code)


def assess(control,mission,request):
    now=datetime.now(timezone.utc)
    requirement=request.get('execution_requirements',{})
    identity={'mission_id':mission['identity']['mission_id'],'step_id':request.get('id','STEP-1'),
              'plan_revision':mission.get('plan_revision',0),
              'request_digest':digest(request)}
    out=dict(identity,schema=1,requirements_digest=digest(requirement),status='EXECUTABLE',reason_code='HANDLER_AVAILABLE',
             checked_at=now.isoformat(),expires_at=(now+timedelta(seconds=5)).isoformat(),
             reservation=False,authorization=False,evidence_refs=[],alternatives=[])
    def verdict(status,reason):
        out.update(status=status,reason_code=reason)
        return out
    allowed={'allowed_execution_locations','data_class','context_min_tokens'}
    if not isinstance(requirement,dict) or set(requirement)-allowed:
        return verdict('UNSUPPORTED','UNSUPPORTED_REQUIREMENT')
    locations=requirement.get('allowed_execution_locations',['local'])
    if not isinstance(locations,list) or not locations or any(not isinstance(x,str) or x not in {'local','cloud'} for x in locations):
        return verdict('BLOCKED','INVALID_EXECUTION_LOCATION')
    if 'local' not in locations: return verdict('UNSUPPORTED','CLOUD_NOT_IMPLEMENTED')
    if not isinstance(requirement.get('data_class','internal'),str) or requirement.get('data_class','internal') not in {'public','internal','confidential','restricted'}:
        return verdict('BLOCKED','INVALID_DATA_CLASS')
    context=requirement.get('context_min_tokens',0)
    if type(context) is not int or context<0: return verdict('BLOCKED','INVALID_CONTEXT_REQUIREMENT')
    if context: return verdict('UNSUPPORTED','CONTEXT_CAPACITY_UNQUALIFIED')
    action=request.get('action','create_text_artifact')
    handlers={'inspect_tools','model_inference','tool_call','tool_sequence','inspect_project','prepare_code_candidate','create_text_artifact'}
    if action not in handlers: return verdict('UNSUPPORTED','NO_HANDLER')
    if action=='inspect_project' and not getattr(control,'inspector',None): return verdict('UNSUPPORTED','NO_INSPECTOR')
    if action=='prepare_code_candidate' and not getattr(control,'candidate_preparer',None): return verdict('UNSUPPORTED','NO_CANDIDATE_HANDLER')
    if action=='tool_call':
        if control._route_tool_denial(mission,request.get('tool')): return verdict('BLOCKED','TOOL_NOT_SELECTED')
        live=control.tools.list() if control.tools else {}
        tool=live.get(request.get('tool'),{})
        if request.get('operation') not in tool.get('operations',[]): return verdict('UNSUPPORTED','NO_TOOL_OPERATION')
        if tool.get('healthy') is False: return verdict('NOT_NOW','TOOL_UNAVAILABLE')
    if action=='model_inference':
        router=control.model_router
        if not router: return verdict('UNSUPPORTED','NO_MODEL_ROUTER')
        provider=request.get('provider')
        if provider and provider not in router.adapters: return verdict('UNSUPPORTED','UNKNOWN_PROVIDER')
        hw=getattr(router,'hardware_manager',None)
        try:
            if hw:
                sample=hw.preflight()
                out['evidence_refs'].append({'kind':'hardware_sample','timestamp':sample.get('timestamp'),'thermal_state':sample.get('thermal_state')})
                with hw.lock:
                    cap=min(1,hw.active_profile()['max_jobs']) if hw._thermal=='WARM' else hw.active_profile()['max_jobs']
                    if hw.jobs>=cap: raise AdmissionUnavailable('JOB_LIMIT')
        except AdmissionUnavailable as exc:
            out['alternatives']=[{'kind':'wait_local','requires_fresh_check':True,'requirements_unchanged':True}]
            return verdict('NOT_NOW',exc.reason_code)
        except RuntimeError: return verdict('BLOCKED','HARDWARE_PROFILE_UNAVAILABLE')
        try: adapter=router.choose(provider)
        except Exception: return verdict('NOT_NOW','PROVIDER_UNAVAILABLE')
        out['evidence_refs'].append({'kind':'local_provider_health','provider':adapter.id,'checked_at':utcnow()})
        out['reason_code']='LOCAL_PROVIDER_AVAILABLE'
    return out
