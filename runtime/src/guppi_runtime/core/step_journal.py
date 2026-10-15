"""Sequential checkpoints; interrupted effects are never silently replayed."""
import re
import hashlib
from pathlib import Path
from .request_binding import digest
from .util import utcnow


class JournalError(ValueError):
    pass


def plan_steps(mission):
    steps=mission['plan'].get('steps') or [{'id':'STEP-1','action':'create_text_artifact'}]
    if not isinstance(steps,list) or not 1<=len(steps)<=32:raise JournalError('plan_step_limit')
    if mission['plan'].get('dependencies'):raise JournalError('global_dependencies_not_supported_use_depends_on')
    if mission['plan'].get('workflow') in {'code-candidate-v1','project-inspection-v1'} and len(steps)!=1:
        raise JournalError('bound_workflow_requires_single_step')
    seen=set(); normalized=[]
    for index,raw in enumerate(steps):
        if not isinstance(raw,dict):raise JournalError('invalid_plan_step')
        step=dict(raw);sid=step.setdefault('id',f'STEP-{index+1}')
        if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',sid) or sid in seen:
            raise JournalError('invalid_or_duplicate_step_id')
        dependencies=step.get('depends_on',[])
        if not isinstance(dependencies,list) or any(not isinstance(x,str) or x not in seen for x in dependencies):
            raise JournalError('dependencies_must_reference_earlier_steps')
        if step.get('action')=='tool_sequence' and (step.get('start_at',0)!=0 or step.get('approval_tokens')):
            raise JournalError('sequence_resume_must_come_from_checkpoint')
        seen.add(sid);normalized.append(step)
    return normalized


def checkpoint(mission,control=None):
    steps=plan_steps(mission);execution=mission['execution']
    seal=digest({'plan':mission['plan'],'plan_revision':mission.get('plan_revision',0),'objective':mission['objective'],'routing':mission.get('routing')})
    journal=execution.get('step_journal')
    if journal is None:
        if execution.get('results'):raise JournalError('legacy_execution_has_results_requires_review')
        journal={'schema':1,'plan_digest':seal,'cursor':0,'steps':[
            {'id':s['id'],'status':'PENDING','attempts':0,'attempt_id':None,'request_digest':None,'result':None} for s in steps]}
        execution['step_journal']=journal
    if journal.get('schema')!=1 or journal.get('plan_digest')!=seal or [x.get('id') for x in journal.get('steps',[])]!=[s['id'] for s in steps]:
        raise JournalError('plan_changed_after_checkpoint')
    cursor=journal.get('cursor')
    if type(cursor) is not int or not 0<=cursor<=len(steps):raise JournalError('invalid_step_cursor')
    if any(x['status']!='COMPLETED' for x in journal['steps'][:cursor]):raise JournalError('cursor_skips_uncompleted_step')
    # A response checkpoint may have survived a crash before cursor advancement.
    while cursor<len(steps) and journal['steps'][cursor]['status']=='COMPLETED':
        entry=journal['steps'][cursor]
        if not isinstance(entry.get('result'),dict) or entry['result'].get('status')!='completed':raise JournalError('completed_step_missing_result')
        cursor+=1
    if control:
        roots=[control.workspace.resolve()]
        fs=control.tools.tools.get('filesystem') if control.tools else None
        if fs:roots.append(fs.root.resolve())
        for entry in journal['steps'][:cursor]:
            for artifact in (entry.get('result') or {}).get('artifacts',[]):
                try:
                    path=Path(artifact['path'])
                    resolved=path.resolve()
                    if path.is_symlink() or not any(resolved.is_relative_to(root) for root in roots):raise JournalError('completed_artifact_outside_workspace')
                    if control.guard.evaluate('read_project_file',mission_id=mission['identity']['mission_id'],target=str(path))['decision']!='ALLOW':raise JournalError('completed_artifact_read_blocked')
                    h=hashlib.sha256();size=0
                    with path.open('rb') as stream:
                        while True:
                            blob=stream.read(min(65536,4_000_001-size))
                            if not blob:break
                            size+=len(blob)
                            if size>4_000_000:raise JournalError('completed_artifact_byte_budget')
                            h.update(blob)
                    if h.hexdigest()!=artifact['integrity']['hash']:raise JournalError('completed_artifact_changed')
                except (OSError,KeyError,TypeError) as exc:raise JournalError('completed_artifact_missing_or_invalid') from exc
    journal['cursor']=cursor
    execution['current_step']=steps[cursor]['id'] if cursor<len(steps) else None
    return steps,journal


def start(entry,request):
    import uuid
    if entry['status']=='RUNNING':raise JournalError('UNKNOWN_EXECUTION_OUTCOME')
    if entry['status'] not in {'PENDING','WAITING','GATE'}:raise JournalError('step_not_retryable')
    if entry['attempts']>=3:raise JournalError('step_attempt_budget_exhausted')
    entry.update(status='RUNNING',attempts=entry['attempts']+1,attempt_id='ATT-'+uuid.uuid4().hex,
                 request_digest=digest(request),started_at=utcnow(),result=None)


def finish(entry,result):
    entry['result']=result;entry['finished_at']=utcnow()
    entry['status']={'completed':'COMPLETED','captain_required':'GATE','waiting':'WAITING','blocked':'BLOCKED'}.get(result.get('status'),'FAILED')


def readonly_step(step):
    return step.get('action')=='inspect_tools' or (step.get('action')=='tool_call' and step.get('tool')=='filesystem' and step.get('operation') in {'read_text','list_dir','stat','sha256'})
