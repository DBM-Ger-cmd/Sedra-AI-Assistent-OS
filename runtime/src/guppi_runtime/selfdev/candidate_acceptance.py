"""Guarded bounded file promotion; backup before effects, unknown outcomes never replay."""
import base64
import hashlib
import json
import os
import re
import tempfile
from ..candidate_tests import contract
from ..tuning import digest
from ..util import utcnow


def hash_bytes(raw):return hashlib.sha256(raw).hexdigest()


def test_qualification(rt, mission):
    plan,sha=contract(rt,mission);attempt=mission['execution'].get('candidate_test') or {}
    if attempt.get('status')!='FINISHED' or attempt.get('preparation_sha256')!=sha or attempt.get('plan_digest')!=plan['plan_digest']:
        raise ValueError('completed_bound_tests_required')
    verified=rt.sandbox.verify(mission['identity']['mission_id'],attempt['job_id'],attempt['report_sha256'],plan['plan_digest'])
    if verified.get('verification')!='PASS' or verified.get('qualification')!='MICROVM_RESULT':raise ValueError('real_verified_guest_tests_required')
    report=json.loads(rt.sandbox.receipt(attempt['job_id']));counts=[]
    if not report.get('commands'):raise ValueError('nonempty_successful_test_inventory_required')
    from ..code_generation import REPRO_HARNESS
    for command in report['commands']:
        if command['argv']==['python3',REPRO_HARNESS]:continue   # GUPPI's own reproduction step (prints REPRO lines, 2026-10-03); it never counts as a test, the unittest command below still must run and pass
        if command['argv']!=['python3','-m','unittest','discover','-s','tests','-v']:
            raise ValueError('qualified_unittest_command_required')
        output=command['output'];matches=re.findall(r'(?m)^Ran ([0-9]+) tests? in [^\r\n]+',output)
        if len(matches)!=1 or int(matches[0])<1 or not re.search(r'(?m)^OK\s*$',output):raise ValueError('nonempty_successful_test_inventory_required')
        counts.append(int(matches[0]))
    if not counts:raise ValueError('nonempty_successful_test_inventory_required')   # the reproduction step alone is no test run
    return {'job_id':attempt['job_id'],'report_sha256':attempt['report_sha256'],'test_counts':counts,'preparation_sha256':sha}
test_qualification.__test__=False   # a production check, not a pytest test (pytest collects it when a test module imports it)


def close_after_take_over(rt, mission, outcome, via):
    """Reflect a confirmed take-over in the mission (before 2026-10-02 it stayed on CANDIDATE_REVIEW for good).
    applied: CANDIDATE_REVIEW -> COMPLETE, result accepted. rolled_back: the result says so; a closed mission stays closed."""
    result=mission.setdefault('result',{})
    if outcome=='applied':
        result.update(accepted=True,accepted_via=via,accepted_at=utcnow())
        rt.missions.save(mission)
        if mission['lifecycle']['phase']=='CANDIDATE_REVIEW':rt.missions.transition(mission,'COMPLETE')
    else:
        result.update(accepted=False,rolled_back=True,rolled_back_via=via,rolled_back_at=utcnow())
        rt.missions.save(mission)


def linked_job(rt, mid):
    """The self-development job this mission's candidate is bound to, or None for a plain project mission.
    More than one job on the same candidate is ambiguous and refused."""
    sd=getattr(rt,'self_development',None)
    jobs=sd.jobs_for_mission(mid) if sd is not None else []
    if len(jobs)>1:raise ValueError('ambiguous_development_jobs:'+','.join(sorted(j['job_id'] for j in jobs)))
    return jobs[0] if jobs else None


def preview(rt, mission, resolution='accept'):
    mid=mission['identity']['mission_id'];previous=mission['execution'].get('candidate_acceptance')
    job=linked_job(rt,mid)
    if resolution=='accept':
        if previous:raise ValueError('acceptance_already_started')
        if job is not None:
            # Self-development: the job must hold a verified, independently reviewed PASS (2026-10-02: before, a candidate
            # could be taken over while its job stood on REWORK or BLOCKED).
            refusal=rt.self_development.acceptance_refusal(job)
            if refusal:raise ValueError(refusal)
        evidence=test_qualification(rt,mission)
        if job is not None:evidence=dict(evidence,development_job=job['job_id'])
        binding=mission['plan']['steps'][0]['binding'];inputs=binding['inputs'];files=[]
        for change in inputs['changes']:
            path=inputs['project_path']+'/'+change['path'];source=rt.filesystem_tool._resolve(path,must_exist=True)
            if rt.guard.evaluate('read_project_file',mission_id=mid,target=str(source))['decision']!='ALLOW':raise ValueError('source_read_not_allowed')
            with source.open('rb') as f:raw=f.read(65537)
            if len(raw)>65536 or hash_bytes(raw)!=change['expected_sha256']:raise ValueError('source_changed')
            content=change['content'];files.append({'path':path,'before_sha256':hash_bytes(raw),'after_sha256':hash_bytes(content.encode('utf-8')),'content':content,'backup_base64':base64.b64encode(raw).decode()})
        original=None
    elif resolution=='rollback':
        if not previous or previous.get('status')!='APPLIED':raise ValueError('confirmed_applied_acceptance_required')
        if previous.get('rollback'):raise ValueError('rollback_already_started')
        original=previous['plan'];unsigned=dict(original);unsigned.pop('plan_digest',None)
        if digest(unsigned)!=original['plan_digest'] or previous.get('plan_digest')!=original['plan_digest']:raise ValueError('backup_contract_changed')
        evidence={'acceptance_digest':original['plan_digest']};files=[]
        if job is not None:evidence['development_job']=job['job_id']
        for old in original['files']:
            raw=base64.b64decode(old['backup_base64'],validate=True)
            if hash_bytes(raw)!=old['before_sha256']:raise ValueError('backup_hash_mismatch')
            source=rt.filesystem_tool._resolve(old['path'],must_exist=True)
            if rt.guard.evaluate('read_project_file',mission_id=mid,target=str(source))['decision']!='ALLOW':raise ValueError('source_read_not_allowed')
            with source.open('rb') as f:current=f.read(65537)
            if hash_bytes(current)!=old['after_sha256']:raise ValueError('source_changed_after_acceptance')
            files.append({'path':old['path'],'before_sha256':old['after_sha256'],'after_sha256':old['before_sha256'],'content':raw.decode('utf-8'),'backup_base64':base64.b64encode(current).decode()})
    else:raise ValueError('unsupported_acceptance_resolution')
    for rec in files:
        path=rt.filesystem_tool._resolve(rec['path'],must_exist=True)
        if rt.guard.evaluate('read_project_file',mission_id=mid,target=str(path))['decision']!='ALLOW':raise ValueError('source_read_not_allowed')
        if rt.guard.evaluate('overwrite_existing',mission_id=mid,target=str(path))['decision']=='BLOCK':raise ValueError('source_write_blocked')
    plan={'schema':1,'mission_id':mid,'resolution':resolution,'tool_root':str(rt.filesystem_tool.root),'files':files,'evidence':evidence}
    plan['plan_digest']=digest(plan);return plan


def apply(control,rt,mission,plan,token=None):
    mid=mission['identity']['mission_id'];resolution=plan.get('resolution') if isinstance(plan,dict) else None
    if preview(rt,mission,resolution)!=plan:raise ValueError('acceptance_plan_changed')
    action='candidate_accept' if resolution=='accept' else 'candidate_rollback';target=action+':'+plan['plan_digest']
    verdict=control.guard.evaluate(action,mission_id=mid,target=target)
    if verdict['decision']=='BLOCK':return {'status':'blocked','guard':verdict}
    if verdict['decision']=='CAPTAIN_REQUIRED' and not control.guard.authorize(token,mission_id=mid,action=action,target=target,request_binding=plan)['authorized']:
        gate=control.guard.create_gate(mid,action,target,risks=['Overwrite exactly reviewed existing files; inspect diff and backup; multi-file operation is not atomic'],rollback_available=True,request_binding=plan)
        return {'status':'captain_required','gate':gate}
    if resolution=='accept':
        record={'status':'RUNNING','plan':plan,'plan_digest':plan['plan_digest'],'completed':[],'started_at':utcnow()}
        mission['execution']['candidate_acceptance']=record
    else:
        record=mission['execution']['candidate_acceptance'];record['rollback']={'status':'RUNNING','plan':plan,'completed':[],'started_at':utcnow()};record=record['rollback']
    rt.missions.save(mission)  # Complete backup contract precedes all source writes.
    job_id=(plan.get('evidence') or {}).get('development_job')
    if job_id and resolution=='accept':rt.self_development.mark_activation(job_id,'started')
    try:
        for rec in plan['files']:
            path=rt.filesystem_tool._resolve(rec['path'],must_exist=True)
            verdict=control.guard.evaluate('overwrite_existing',mission_id=mid,target=str(path))
            if verdict['decision']=='BLOCK':raise ValueError('file_guard_blocked')
            with path.open('rb') as f:raw=f.read(65537)
            if hash_bytes(raw)!=rec['before_sha256']:raise ValueError('source_changed_before_write')
            fd,tmp=tempfile.mkstemp(prefix='guppi-change-',dir=path.parent)
            try:
                with os.fdopen(fd,'wb') as f:f.write(rec['content'].encode('utf-8'));f.flush();os.fsync(f.fileno())
                os.replace(tmp,path)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            with path.open('rb') as f:observed=f.read(65537)
            if hash_bytes(observed)!=rec['after_sha256']:raise ValueError('written_file_verification_failed')
            record['completed'].append(rec['path']);rt.missions.save(mission)
            control._audit_result(mid,action,{'status':'completed','path':str(path)})
        record['status']='APPLIED' if resolution=='accept' else 'ROLLED_BACK';record['finished_at']=utcnow();rt.missions.save(mission)
        if job_id:rt.self_development.mark_activation(job_id,'applied' if resolution=='accept' else 'rolled_back')
        close_after_take_over(rt,mission,'applied' if resolution=='accept' else 'rolled_back','candidate_acceptance')
        return {'status':'completed','acceptance':record,'ready_for_merge':False}
    except Exception as exc:
        record['status']='REVIEW_REQUIRED';record['error']=str(exc);rt.missions.save(mission)
        return {'status':'failed','acceptance':record,'reason':'partial_or_unknown_effect_requires_review'}


def command(rt,mid,operation,plan=None):
    with rt.missions.execution_lock(mid):
        mission=rt.missions.load(mid)
        if operation in {'accept-preview','rollback-preview'}:return {'status':'completed','plan':preview(rt,mission,'accept' if operation=='accept-preview' else 'rollback')}
        if operation=='rollback' and (mission['execution'].get('candidate_acceptance') or {}).get('rollback'):
            return {'status':'blocked','reason':'rollback_already_started'}
        token=mission['execution'].get('approval_token')
        out=rt.control.execute(mission,{'action':'candidate_acceptance','runtime':rt,'plan':plan},token)
        if out.get('gate'):
            gate=out['gate']
            if not any(g['request']==gate['request'] for g in mission['human_gates']['pending']):mission['human_gates']['pending'].append(gate)
        if token and token.get('status')=='used':mission['execution'].pop('approval_token',None)
        rt.missions.save(mission);return out
