"""Track and explicitly discard staged candidates; never touch original sources."""
import re
import uuid
from ..core.util import utcnow


def checked_stage(mission,record):
    mid=mission['identity']['mission_id'];stage=record.get('stage')
    if not isinstance(stage,str) or not re.fullmatch(r'guppi-candidates/'+re.escape(mid)+r'-[0-9a-f]{32}/project',stage):
        raise ValueError('invalid_recorded_candidate_stage')
    if record.get('attempt_id')!=stage.split('/')[-2].split('-')[-1]:raise ValueError('candidate_attempt_identity_mismatch')
    return stage


def persist(control,mission):
    store=getattr(control,'missions',None)
    if not store:raise RuntimeError('candidate_lifecycle_store_required')
    store.save(mission)


def preparation(control,mission,binding):
    records=mission['execution'].setdefault('candidate_attempts',[])
    if not isinstance(records,list) or len(records)>3:raise ValueError('candidate_attempt_budget')
    record=records[-1] if records and records[-1].get('status') not in {'DISCARDED','FAILED'} else None
    if record:
        checked_stage(mission,record)
        if record['binding_digest']!=binding['digest']:raise ValueError('candidate_attempt_binding_changed')
    else:
        if len(records)>=3:raise ValueError('candidate_attempt_budget')
        aid=uuid.uuid4().hex
        record={'attempt_id':aid,'stage':f"guppi-candidates/{mission['identity']['mission_id']}-{aid}/project",
                'binding_digest':binding['digest'],'created_at':utcnow(),'status':'PREPARING','calls':[],'reason':None}
        records.append(record)
    persist(control,mission)
    return record


def discard(control,mission,attempt_id,approval_token=None):
    if mission['lifecycle']['phase'] not in {'FAILED','PAUSED','CAPTAIN_REVIEW'}:
        raise ValueError('candidate_cleanup_requires_stopped_mission')
    record=next((r for r in mission['execution'].get('candidate_attempts',[]) if r.get('attempt_id')==attempt_id),None)
    if not record:raise ValueError('candidate_attempt_not_found')
    stage=checked_stage(mission,record)
    if record['status']=='DISCARDED':return {'status':'completed','already_discarded':True,'artifacts':[]}
    if record['status'] not in {'PREPARING','GATE','BLOCKED','FAILED','REPORT_PENDING','READY_UNVERIFIED'}:
        raise ValueError('candidate_not_discardable')
    parent=stage.rsplit('/',1)[0]
    fs=control.candidate_preparer.binder.filesystem
    target=fs._resolve(parent)
    if not target.exists():raise ValueError('candidate_stage_missing_requires_manual_review')
    out=control._tool_call(mission['identity']['mission_id'],{'tool':'filesystem','operation':'delete',
                         'args':{'path':parent,'recursive':True}},approval_token,mission=mission)
    if out['status']=='completed':
        record.update(status='DISCARDED',discarded_at=utcnow())
        mission['execution'].pop('approval_token',None)
    elif out['status']=='captain_required':
        mission['human_gates']['pending'].append(out['gate'])
    persist(control,mission)
    return out
