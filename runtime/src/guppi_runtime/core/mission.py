from __future__ import annotations
from pathlib import Path
from copy import deepcopy
import uuid, re
from .mission_lock import exclusive
from .errors import InvalidTransition
from .util import atomic_write_json, load_json, utcnow

ALLOWED = {
 'NEW': {'UNDERSTAND','PAUSED'},
 'UNDERSTAND': {'PLAN','READY','PAUSED','FAILED'},
 'PLAN': {'READY','PAUSED','FAILED'},
 'READY': {'EXECUTE','CAPTAIN_REVIEW','PAUSED'},
 'EXECUTE': {'VERIFY','REWORK','CAPTAIN_REVIEW','PAUSED','FAILED'},
 'VERIFY': {'COMPLETE','CAPTAIN_REVIEW','CANDIDATE_REVIEW','REWORK','FAILED'},
 'CANDIDATE_REVIEW': {'PAUSED','FAILED','COMPLETE'},   # COMPLETE only after a confirmed take-over (candidate_acceptance / self_integration)
 'REWORK': {'PLAN','EXECUTE','PAUSED','FAILED'},
 'CAPTAIN_REVIEW': {'EXECUTE','COMPLETE','PAUSED','FAILED'},
 'PAUSED': {'UNDERSTAND','PLAN','READY','EXECUTE','VERIFY','FAILED'},
 'COMPLETE': set(), 'FAILED': set(),
}

def new_mission(intent, objective=None, mission_class='S1', mission_id=None):
    mid=mission_id or f"M-{uuid.uuid4().hex[:8].upper()}"
    return {
      'schema':1,
      'identity':{'mission_id':mid,'created_at':utcnow(),'created_by':'captain','mission_class':mission_class},
      'captain_intent':{'original':intent,'immutable':True},
      'objective':{'current':objective or intent,'version':1},
      'lifecycle':{'phase':'NEW','status':'active'},
      'context':{'refs':[],'active_context_pack':None,'unresolved_questions':[]},
      'routing':{'status':'pending','route':None},
      'plan':{'version':None,'status':'missing','steps':[],'dependencies':[],'acceptance_criteria':[]},
      'modules':{'planning-context':{'state':'idle'},'control-master':{'state':'idle'},'verification':{'state':'idle'}},
      'execution':{'current_step':None,'requests':[],'results':[],'artifacts':[],'errors':[],'step_journal':None,'candidate_attempts':[]},
      'verification':{'status':'pending','findings':[],'evidence':[],'rework_request':None},
      'risk':{'level':'low','findings':[]},
      'human_gates':{'pending':[],'resolved':[]},
      'decisions':[], 'capability_gaps':[],
      'audit':{'last_event_id':None,'event_count':0},
      'rework_cycles':0,
      'plan_revision':0,
      'wait':None,
      'result':{'kind':None,'qualification':'PENDING','evidence_refs':[]},
    }

class MissionStore:
    def __init__(self, root: Path, audit=None):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.audit=audit
    def path(self, mission_id):
        if not isinstance(mission_id,str) or not re.fullmatch(r'M-[A-Za-z0-9_-]{1,64}',mission_id):raise ValueError('invalid_mission_id')
        return self.root/f'{mission_id}.json'
    def execution_lock(self,mission_id):
        self.path(mission_id)
        return exclusive(self.root/'.locks'/f'{mission_id}.lock')
    def create(self, intent, objective=None, mission_class='S1'):
        m=new_mission(intent,objective,mission_class)
        self.save(m)
        if self.audit: self.audit.append('MISSION_CREATED',mission_id=m['identity']['mission_id'],payload={'class':mission_class,'objective':m['objective']['current']})
        return m
    def load(self, mission_id):
        m=load_json(self.path(mission_id))
        if m is None: raise KeyError(mission_id)
        return m
    def save(self, mission): atomic_write_json(self.path(mission['identity']['mission_id']),mission)
    def transition(self, mission, new_phase):
        old=mission['lifecycle']['phase']
        if new_phase not in ALLOWED.get(old,set()):
            raise InvalidTransition(f'{old} -> {new_phase}')
        mission['lifecycle']['phase']=new_phase
        if new_phase in {'COMPLETE','FAILED'}: mission['lifecycle']['status']='closed'
        self.save(mission)
        if self.audit: self.audit.append('MISSION_STATE_CHANGED',mission_id=mission['identity']['mission_id'],payload={'from':old,'to':new_phase})
        return mission
    def _validate_objective_change(self,mission,objective):
        if not isinstance(objective,str) or not objective.strip() or len(objective)>4000:raise ValueError('invalid_objective')
        if mission['lifecycle']['phase']!='NEW' or mission['execution']['results']:
            raise ValueError('objective_change_only_before_planning')

    def objective_gate(self, mission, objective):
        self._validate_objective_change(mission,objective)
        guard=getattr(self,'guard',None)
        if not guard: raise PermissionError('objective_change_requires_guard')
        binding={'objective':objective,'current':mission['objective'],'plan_version':mission.get('plan_revision',0)}
        return guard.create_gate(mission['identity']['mission_id'],'change_objective','objective:'+mission['identity']['mission_id'],request_binding=binding)

    def set_objective(self, mission, objective, approval_token=None):
        self._validate_objective_change(mission,objective)
        guard=getattr(self,'guard',None)
        binding={'objective':objective,'current':mission['objective'],'plan_version':mission.get('plan_revision',0)}
        if not guard or not guard.authorize(approval_token,mission_id=mission['identity']['mission_id'],action='change_objective',target='objective:'+mission['identity']['mission_id'],request_binding=binding)['authorized']:
            raise PermissionError('objective_change_requires_bound_captain_approval')
        mission['objective']['current']=objective; mission['objective']['version']+=1; self.save(mission)
    def set_captain_intent(self, mission, _):
        raise PermissionError('captain_intent.original is immutable')
    def list(self):
        """All missions. A file is parsed again only when its mtime or size changed (the UIX polls this; before 2026-10-02 every
        call parsed every mission). Callers get copies, so changing a listed mission never changes the cache."""
        cache=self.__dict__.setdefault('_list_cache',{})
        out=[];seen=set()
        for p in sorted(self.root.glob('M-*.json')):
            try:st=p.stat()
            except FileNotFoundError:continue
            key=(st.st_mtime_ns,st.st_size);seen.add(p.name)
            hit=cache.get(p.name)
            if hit is None or hit[0]!=key:
                value=load_json(p)
                if value is None:continue
                hit=cache[p.name]=(key,value)
            out.append(deepcopy(hit[1]))
        for name in set(cache)-seen:cache.pop(name,None)
        return out
