from __future__ import annotations
from .message_bus import Message
from copy import deepcopy
from .util import utcnow
from .step_journal import checkpoint, start, finish, JournalError, readonly_step


class GuppiBrain:
    def __init__(self, missions, bus, planner, control, verifier, guard, audit=None, max_rework_cycles=3, capability_router=None):
        self.missions = missions
        self.bus = bus
        self.planner = planner
        self.control = control
        self.verifier = verifier
        self.guard = guard
        self.audit = audit
        self.max_rework = max_rework_cycles
        self.capability_router = capability_router

    def create_mission(self, intent, objective=None, mission_class='S1', inputs=None, plan_request=None):
        if inputs is not None and getattr(self.planner,'binder',None):self.planner.binder.validate_inputs(inputs)
        if plan_request is not None:
            from .manual_plan import artifact_plan
            if inputs is not None:raise ValueError('manual_plan_cannot_mix_with_bound_inputs')
            artifact_plan(plan_request)
        m=self.missions.create(intent, objective, mission_class)
        if plan_request is not None:m['manual_plan']=deepcopy(plan_request);self.missions.save(m)
        if inputs is not None:
            m['inputs']=deepcopy(inputs);self.missions.save(m)
        return m

    def set_inputs(self, mission_id, inputs):
        with self.missions.execution_lock(mission_id):return self._set_inputs(mission_id,inputs)

    def _set_inputs(self, mission_id, inputs):
        m=self.missions.load(mission_id)
        if m['lifecycle']['phase'] not in {'NEW','UNDERSTAND','PLAN','PAUSED'} or m['execution']['results'] or m['execution'].get('step_journal'):
            raise ValueError('mission_inputs_locked_after_execution')
        if getattr(self.planner,'binder',None):self.planner.binder.validate_inputs(inputs)
        m['inputs']=deepcopy(inputs);m['context']['unresolved_questions']=[]
        self.missions.save(m)
        if m['lifecycle']['phase']=='PAUSED':self.missions.transition(m,'PLAN')
        return self.missions.load(mission_id)

    def resume(self,mission_id):
        with self.missions.execution_lock(mission_id):return self._resume(mission_id)

    def _resume(self,mission_id):
        m=self.missions.load(mission_id)
        wait=m.get('wait')
        if m['lifecycle']['phase']!='PAUSED' or not wait or wait.get('status')!='NOT_NOW':
            raise ValueError('only_resource_wait_can_resume')
        if wait.get('resume_checks',0)>=3: raise ValueError('resource_resume_budget_exhausted')
        wait['resume_checks']=wait.get('resume_checks',0)+1
        m['lifecycle']['status']='active'
        self.missions.save(m)
        self.missions.transition(m,'EXECUTE')
        return m

    def recover(self,mission_id,resolution,approval_token=None):
        with self.missions.execution_lock(mission_id):
            m=self.missions.load(mission_id)
            if m['lifecycle']['phase']!='PAUSED' or (m.get('wait') or {}).get('reason_code')!='UNKNOWN_EXECUTION_OUTCOME':
                raise ValueError('no_unknown_execution_to_recover')
            steps,journal=checkpoint(m,self.control);entry=journal['steps'][journal['cursor']]
            if entry['status']!='RUNNING':raise ValueError('no_running_checkpoint')
            if resolution not in {'abort','retry_readonly'}:raise ValueError('unsupported_recovery_resolution')
            if resolution=='retry_readonly' and not readonly_step(steps[journal['cursor']]):raise ValueError('mutating_step_cannot_be_replayed')
            target='recovery:'+mission_id
            binding={'plan_digest':journal['plan_digest'],'entry':entry,'resolution':resolution}
            verdict=self.guard.evaluate('execution_recovery',mission_id=mission_id,target=target)
            if verdict['decision']=='BLOCK':return {'status':'blocked','guard':verdict}
            token=approval_token or m['execution'].get('approval_token')
            if not self.guard.authorize(token,mission_id=mission_id,action='execution_recovery',target=target,request_binding=binding)['authorized']:
                gate=self.guard.create_gate(mission_id,'execution_recovery',target,request_binding=binding)
                m['human_gates']['pending'].append(gate);self.missions.save(m)
                return {'status':'captain_required','gate':gate}
            if self.audit:self.audit.append('EXECUTION_RECOVERY_RESOLVED',component=self.id,mission_id=mission_id,payload={'resolution':resolution,'attempt_id':entry['attempt_id'],'plan_revision':m.get('plan_revision',0)})
            m['decisions'].append({'type':'execution_recovery','resolution':resolution,'attempt_id':entry['attempt_id'],'at':utcnow()})
            m['execution'].pop('approval_token',None);m['wait']=None;m['lifecycle']['status']='active'
            if resolution=='abort':
                entry['status']='ABORTED';self.missions.save(m);self.missions.transition(m,'FAILED')
            else:
                entry['status']='PENDING';self.missions.save(m);self.missions.transition(m,'EXECUTE')
            return {'status':'completed','mission':self.missions.load(mission_id)}

    def _pause_execution(self,m,check):
        old=m.get('wait') or {}
        m['wait']={'status':check['status'],'reason_code':check['reason_code'],
                   'since':old.get('since',utcnow()),'resume_checks':old.get('resume_checks',0),
                   'blocked_step_id':check.get('step_id'),'resume_condition':'explicit_resume_and_fresh_check',
                   'feasibility':check}
        m['lifecycle']['status']='waiting' if check['status']=='NOT_NOW' else 'blocked'
        self.missions.save(m);self.missions.transition(m,'PAUSED')
        if self.audit:self.audit.append('MISSION_EXECUTION_PAUSED',mission_id=m['identity']['mission_id'],payload={'status':check['status'],'reason_code':check['reason_code']})
        return self.missions.load(m['identity']['mission_id'])

    def step(self, mission_id, approval_token=None):
        with self.missions.execution_lock(mission_id):
            return self._step(mission_id,approval_token)

    def _step(self, mission_id, approval_token=None):
        m = self.missions.load(mission_id)
        phase = m['lifecycle']['phase']
        if phase == 'NEW':
            self.missions.transition(m, 'UNDERSTAND')
            return self.missions.load(mission_id)
        if phase == 'UNDERSTAND':
            if self.capability_router:
                route = self.capability_router.route_mission(m)
                m['routing'] = {'status': route.get('status', 'resolved'), 'route': route}
                self.missions.save(m)
            self.missions.transition(m, 'PLAN')
            return self.missions.load(mission_id)
        if phase == 'PLAN':
            if m['execution'].get('step_journal'):
                return self._pause_execution(m,{'status':'BLOCKED','reason_code':'replan_requires_explicit_new_execution_contract'})
            result = self.bus.send(Message(mission_id, self.id, 'planning-context', 'create_plan', {'mission': m}))
            m['plan_revision']=m.get('plan_revision',0)+1
            m['plan']=result['plan']
            m['plan']['revision']=m['plan_revision']
            if m['plan'].get('status')=='needs_input':
                m['context']['unresolved_questions']=m['plan'].get('questions',[])
                self.missions.save(m)
                self.missions.transition(m,'PAUSED')
                return self.missions.load(mission_id)
            self.missions.save(m)
            self.missions.transition(m, 'READY')
            return self.missions.load(mission_id)
        if phase == 'READY':
            self.missions.transition(m, 'EXECUTE')
            return self.missions.load(mission_id)
        if phase == 'CAPTAIN_REVIEW':
            token = approval_token or m['execution'].get('approval_token')
            if not token:
                return m
            self.missions.transition(m, 'EXECUTE')
            return self.missions.load(mission_id)
        if phase == 'EXECUTE':
            try:
                steps,journal=checkpoint(m,self.control)
                if journal['cursor']==len(steps):
                    self.missions.save(m);self.missions.transition(m,'VERIFY')
                    return self.missions.load(mission_id)
                step=steps[journal['cursor']];entry=journal['steps'][journal['cursor']]
                if entry['status']=='RUNNING':raise JournalError('UNKNOWN_EXECUTION_OUTCOME')
                if entry['status']=='GATE' and not (approval_token or m['execution'].get('approval_token')):
                    gate=entry['result'].get('gate')
                    if not gate:raise JournalError('gate_checkpoint_missing_gate')
                    if not any(g['gate_id']==gate['gate_id'] for g in m['human_gates']['pending']):m['human_gates']['pending'].append(gate)
                    self.missions.save(m);self.missions.transition(m,'CAPTAIN_REVIEW')
                    return self.missions.load(mission_id)
                if entry['attempts']>=3:raise JournalError('step_attempt_budget_exhausted')
            except JournalError as exc:
                return self._pause_execution(m,{'status':'BLOCKED','reason_code':str(exc)})
            request = dict(step)
            request.setdefault('action','create_text_artifact')
            if request['action']=='create_text_artifact' and len(steps)>1:request.setdefault('target',step['id']+'.txt')
            request.setdefault('content',f"GUPPI planning artifact: {m['objective']['current']}\nThis artifact does not assert execution of unbound skill workflows.\n")
            if request['action']=='tool_sequence' and entry.get('result') and entry['result'].get('status') in {'captain_required','waiting'}:
                previous=entry['result'];index=previous.get('resume_from')
                sequence=request.get('steps',[])
                if type(index) is not int or not 0<=index<len(sequence):return self._pause_execution(m,{'status':'BLOCKED','reason_code':'invalid_sequence_resume_checkpoint'})
                request['start_at']=index
                if previous['status']=='captain_required':
                    sid=str(sequence[index].get('id',f'step-{index}'))
                    request['approval_tokens']={sid:approval_token or m['execution'].get('approval_token')}
            request['plan_revision']=m.get('plan_revision',0)
            request['routing']=(m.get('routing') or {}).get('route')
            request.setdefault('execution_requirements',m['plan'].get('execution_requirements',{}))
            check=self.control.check_execution(m,request)
            m['execution']['feasibility']=check
            if check['status']!='EXECUTABLE':return self._pause_execution(m,check)
            m['execution'].setdefault('report_created_at',utcnow())
            try:start(entry,request)
            except JournalError as exc:return self._pause_execution(m,{'status':'BLOCKED','reason_code':str(exc)})
            self.missions.save(m)
            if self.audit:self.audit.append('STEP_STARTED',component=self.id,mission_id=mission_id,payload={'step_id':entry['id'],'attempt_id':entry['attempt_id'],'request_digest':entry['request_digest']})
            token = approval_token or m['execution'].get('approval_token')
            result = self.bus.send(Message(mission_id, self.id, 'control-master', 'execution_request', {'mission': m, 'request': request, 'approval_token': token}))
            prior=entry.get('partial_artifacts',[])
            combined={a['artifact_id']:a for a in prior+result.get('artifacts',[])}
            result['artifacts']=list(combined.values())
            if result.get('status')!='completed':entry['partial_artifacts']=result['artifacts']
            finish(entry,result)
            m['execution']['results'].append(result)
            if result['status']=='completed':
                m['wait']=None
                m['execution']['artifacts'].extend(result['artifacts'])
                m['execution'].pop('approval_token',None)
            self.missions.save(m)
            if self.audit:self.audit.append('STEP_CHECKPOINTED',component=self.id,mission_id=mission_id,payload={'step_id':entry['id'],'attempt_id':entry['attempt_id'],'status':entry['status']})
            if result['status'] == 'captain_required':
                gate=result['gate']   # same request already pending (repeated run without approval): keep one gate, not a pile
                if not any(g['request']==gate['request'] for g in m['human_gates']['pending']):m['human_gates']['pending'].append(gate)
                self.missions.save(m)
                self.missions.transition(m, 'CAPTAIN_REVIEW')
                return self.missions.load(mission_id)
            if result['status'] in {'waiting','blocked'}:
                pause=result.get('feasibility') or dict(check,status='NOT_NOW' if result['status']=='waiting' else 'BLOCKED',reason_code=result.get('reason_code') or result.get('reason') or 'EXECUTION_BLOCKED')
                return self._pause_execution(m,pause)
            if result['status'] != 'completed':
                m['execution']['errors'].append(result.get('error') or result['status'])
                self.missions.save(m)
                self.missions.transition(m, 'FAILED')
                return self.missions.load(mission_id)
            journal['cursor']+=1
            m['execution']['current_step']=steps[journal['cursor']]['id'] if journal['cursor']<len(steps) else None
            self.missions.save(m)
            if journal['cursor']==len(steps):self.missions.transition(m, 'VERIFY')
            return self.missions.load(mission_id)
        if phase == 'VERIFY':
            try:
                steps,journal=checkpoint(m,self.control)
                if journal['cursor']!=len(steps):raise JournalError('verification_before_all_steps_completed')
            except JournalError as exc:return self._pause_execution(m,{'status':'BLOCKED','reason_code':str(exc)})
            result = self.bus.send(Message(mission_id, self.id, 'verification', 'verification_request', {'mission': m}))
            m['verification'].update(result)
            self.missions.save(m)
            if result['status'] == 'PASS':
                workflow=m['plan'].get('workflow')
                qualification={'code-candidate-v1':'PREPARED_NOT_TESTED','project-inspection-v1':'VERIFIED_INVENTORY'}.get(workflow,'ARTIFACT_ONLY')
                m['result']={'kind':workflow or 'planning_artifact','qualification':qualification,'evidence_refs':result.get('evidence',[]),'tests_executed':False,'accepted':False}
                if workflow=='code-candidate-v1':
                    for record in m['execution'].get('candidate_attempts',[]):
                        if record['status']=='READY_UNVERIFIED':record['status']='VERIFIED_PREPARATION'
                self.missions.save(m)
                self.missions.transition(m, 'CANDIDATE_REVIEW' if m['plan'].get('workflow')=='code-candidate-v1' else 'COMPLETE')
            elif result['status'] == 'FAIL':
                self.missions.transition(m, 'REWORK')
            else:
                self.missions.transition(m, 'PAUSED')
            return self.missions.load(mission_id)
        if phase == 'REWORK':
            journal=m['execution'].get('step_journal')
            if journal and m['rework_cycles'] < self.max_rework:
                # STEP_RECOVERY v1.15: a verifier FAIL after execution must not trigger an automatic replan with replay; it needs an
                # approved contract for a new execution. This is that contract (2026-10-02; before, the mission paused forever):
                # a Captain gate bound to the failed attempt, and only when every step's outcome is known (done or never started).
                open_steps=[s['id'] for s in journal['steps'] if s['status'] not in {'COMPLETED','PENDING'}]
                if open_steps:
                    return self._pause_execution(m,{'status':'BLOCKED','reason_code':'rework_blocked_by_unfinished_steps','step_id':open_steps[0]})
                target=f"replan:{mission_id}:{m.get('plan_revision',0)}"
                binding={'kind':'rework_new_execution','plan_digest':journal['plan_digest'],'plan_revision':m.get('plan_revision',0),
                         'findings':[str(x)[:200] for x in (m['verification'].get('findings') or [])][:20]}
                verdict=self.guard.evaluate('execution_recovery',mission_id=mission_id,target=target)
                if verdict['decision']=='BLOCK':
                    return self._pause_execution(m,{'status':'BLOCKED','reason_code':'rework_replan_blocked_by_guard'})
                token=approval_token or m['execution'].get('approval_token')
                if verdict['decision']!='ALLOW' and not self.guard.authorize(token,mission_id=mission_id,action='execution_recovery',target=target,request_binding=binding)['authorized']:
                    if not any(g['request']['exact_action']=='execution_recovery' and g['request']['targets']==[target] for g in m['human_gates']['pending']):
                        m['human_gates']['pending'].append(self.guard.create_gate(mission_id,'execution_recovery',target,
                            risks=['Starts a new execution of a reworked plan; steps that already ran may run again'],rollback_available=False,request_binding=binding))
                    m['lifecycle']['status']='waiting_captain'
                    self.missions.save(m)
                    return self.missions.load(mission_id)
                m['execution'].setdefault('previous_executions',[]).append({
                    'plan_revision':m.get('plan_revision',0),'journal':journal,'results':m['execution']['results'],
                    'verification':deepcopy(m['verification']),'archived_at':utcnow()})
                m['execution'].update(step_journal=None,results=[],current_step=None)
                m['execution'].pop('approval_token',None)
                m['verification']=dict(m['verification'],status='pending')
                m['lifecycle']['status']='active'
                if self.audit:self.audit.append('EXECUTION_ARCHIVED_FOR_REWORK',component=self.id,mission_id=mission_id,
                                                payload={'plan_revision':m.get('plan_revision',0),'rework_cycle':m['rework_cycles']+1})
            m['rework_cycles'] += 1
            self.missions.save(m)
            self.missions.transition(m, 'FAILED' if m['rework_cycles'] > self.max_rework else 'PLAN')
            return self.missions.load(mission_id)
        return m

    @property
    def id(self):
        return 'guppi-core'

    def run(self, mission_id, max_steps=20, approval_token=None):
        resumed_review=False
        for _ in range(max_steps):
            m = self.missions.load(mission_id)
            if m['lifecycle']['phase']=='CAPTAIN_REVIEW':
                token=approval_token or m['execution'].get('approval_token')
                if token and not resumed_review:
                    resumed_review=True
                    self.step(mission_id,approval_token=token)
                    continue
                return m
            if m['lifecycle']['phase'] in {'COMPLETE', 'FAILED', 'PAUSED', 'CAPTAIN_REVIEW','CANDIDATE_REVIEW'}:
                return m
            if m['lifecycle']['phase']=='REWORK' and m['lifecycle'].get('status')=='waiting_captain' and not (approval_token or m['execution'].get('approval_token')):
                return m                                              # the new-execution gate is pending; nothing to do until approved
            self.step(mission_id, approval_token=approval_token)
        return self.missions.load(mission_id)
