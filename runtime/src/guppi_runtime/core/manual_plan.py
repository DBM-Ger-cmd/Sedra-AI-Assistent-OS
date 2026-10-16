"""Captain-supplied bounded local artifact plans; no executable tool permissions."""
from copy import deepcopy
import re


def artifact_plan(value):
    if not isinstance(value,dict) or set(value)!={'steps'}:raise ValueError('artifact_plan_requires_only_steps')
    steps=value['steps']
    if not isinstance(steps,list) or not 1<=len(steps)<=32:raise ValueError('artifact_plan_step_limit')
    ids=set();targets=set();total=0;out=[]
    for raw in steps:
        if not isinstance(raw,dict) or set(raw)-{'id','action','content','target','depends_on'}:raise ValueError('unsupported_artifact_step_fields')
        step=deepcopy(raw);sid=step.get('id');content=step.get('content')
        if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',sid) or sid in ids:raise ValueError('invalid_artifact_step_id')
        if step.get('action','create_text_artifact')!='create_text_artifact':raise ValueError('manual_plan_supports_local_artifacts_only')
        if not isinstance(content,str) or not content:raise ValueError('artifact_content_required')
        size=len(content.encode('utf-8'));total+=size
        if size>65536 or total>262144:raise ValueError('artifact_plan_content_budget')
        target=step.get('target',sid+'.txt')
        if not isinstance(target,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}\.(txt|md)',target) or target.casefold() in targets:
            raise ValueError('artifact_targets_must_be_unique_safe_text_names')
        depends=step.get('depends_on',[])
        if not isinstance(depends,list) or any(not isinstance(x,str) or x not in ids for x in depends):raise ValueError('artifact_dependencies_must_precede_step')
        ids.add(sid);targets.add(target.casefold());step.update(action='create_text_artifact',target=target)
        out.append(step)
    return {'version':4,'status':'ready','workflow':'local-artifact-plan-v1','steps':out,
            'dependencies':[],'acceptance_criteria':[{'type':'artifact_exists','min_count':len(out)}],
            'execution_requirements':{'allowed_execution_locations':['local'],'data_class':'internal','context_min_tokens':0},
            'execution_status':'captain_supplied_local_artifacts_only'}
