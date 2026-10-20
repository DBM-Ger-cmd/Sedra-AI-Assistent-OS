from __future__ import annotations
from collections import Counter
from pathlib import Path
import uuid, yaml
from ..selfdev.evolution_targets import classify_target

class EvolutionManager:
    THRESHOLDS = {
        'repeated_failure': 3,
        'repeated_workaround': 3,
        'missing_capability': 1,
        'captain_request': 1,
        'verification_systemic_finding': 1,
        'safety_gap': 1,
    }
    def __init__(self):
        self.gaps=[]
        self._counts=Counter()
    def record_gap(self, description, gap_type='missing_capability', mission_id=None, target_type=None, target_id=None):
        key=(gap_type,description,target_type,target_id)
        self._counts[key]+=1
        g={'gap_id':f"GAP-{uuid.uuid4().hex[:8].upper()}",'type':gap_type,'description':description,'mission_id':mission_id,'target_type':target_type,'target_id':target_id,'occurrences':self._counts[key],'status':'open'}
        self.gaps.append(g); return g
    def should_propose(self,gap):
        return int(gap.get('occurrences',1)) >= self.THRESHOLDS.get(gap.get('type'),1)
    def classify(self,target_type):
        return classify_target(target_type)
    def propose(self,gap):
        if not self.should_propose(gap): return None
        level=self.classify(gap.get('target_type'))
        return {'proposal_id':f"EP-{uuid.uuid4().hex[:8].upper()}",'sources':{'capability_gaps':[gap['gap_id']],'missions':[gap['mission_id']] if gap.get('mission_id') else []},'problem':{'summary':gap['description'],'evidence':[{'occurrences':gap.get('occurrences',1)}]},'proposed_change':{'objective':f"Resolve: {gap['description']}",'target_type':gap.get('target_type') or 'skill','target_id':gap.get('target_id'),'classification':level},'development':{'recommended':True,'requires_captain_gate': level in {'E2','E3'},'suggested_tests':['compatibility'] if level=='E1' else ['unit','integration','regression']},'status':'proposed'}
    def generate_evolution_file(self, proposal, path: Path, base_version: str, core_contract: int=1):
        if not proposal: raise ValueError('proposal required')
        level=proposal['proposed_change']['classification']
        data={'evolution':{'schema':1,'id':f"EV-{uuid.uuid4().hex[:8].upper()}",'created_by':'guppi-evolution-manager','status':'proposed','base':{'guppi_version':str(base_version),'core_contract':core_contract},'source_proposals':[proposal['proposal_id']],'source_capability_gaps':proposal['sources']['capability_gaps'],'trigger':{'type':'capability_gap','source_missions':proposal['sources']['missions'],'observation':proposal['problem']['summary']},'objective':{'description':proposal['proposed_change']['objective']},'classification':{'level':level},'scope':{'affected':[],'forbidden_changes':['captain_authority','original_intent_immutability','guard_bypass','silent_stable_replacement']},'implementation':{'planned_changes':[]},'verification':{'required':['compatibility'] if level=='E1' else ['unit','integration','regression'],'rollback_test_required': level in {'E2','E3'}},'captain_gate':{'required':proposal['development']['requires_captain_gate']},'result':{'candidate_version':None,'build_path':None,'verification_status':'pending','package_path':None}}}
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True),encoding='utf-8'); return data
    def handoff_to_self_development(self, gap, manager, *, context_window=None):
        """Bridge an admitted proposal into the controlled self-development loop.

        The Evolution Manager still only observes/proposes. The SelfDevelopmentManager
        owns admission, contracts and development job state.
        """
        proposal=self.propose(gap)
        if not proposal:
            return {"status":"NOT_READY","reason":"proposal_threshold_not_met"}
        target_type=proposal["proposed_change"].get("target_type") or "skill"
        requested=proposal["proposed_change"].get("target_id") or proposal["proposed_change"]["objective"]
        evidence=[{"gap_id":gap["gap_id"],"occurrences":gap.get("occurrences",1),"type":gap.get("type")} ]
        return manager.start(requested,evidence=evidence,target_type=target_type,objective=proposal["proposed_change"]["objective"],
                             checked={"skills":True,"tools":True,"modules":True},context_window=context_window,source_gap_id=gap["gap_id"])

