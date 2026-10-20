from __future__ import annotations
from pathlib import Path
import json, uuid
from .core.util import utcnow
class KnowledgeStore:
    def __init__(self,path: Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    def add(self,title,summary,*,record_type='note',mission_id=None,tags=None,source_ref=''):
        rec={'schema':1,'id':f"KN-{uuid.uuid4().hex[:8].upper()}",'type':record_type,'title':title,'content':{'summary':summary,'data':{}},'provenance':{'source_type':'runtime','source_ref':source_ref,'mission_id':mission_id,'created_at':utcnow()},'scope':{'project':'GUPPI','tags':tags or [],'validity':'current'},'confidence':{'level':'unknown'},'status':'active'}
        with self.path.open('a',encoding='utf-8') as f: f.write(json.dumps(rec,ensure_ascii=False)+'\n')
        return rec
    def search(self,query):
        q=query.lower(); out=[]
        if not self.path.exists(): return out
        for line in self.path.read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            r=json.loads(line); blob=(r['title']+' '+r['content']['summary']+' '+' '.join(r['scope']['tags'])).lower()
            if q in blob: out.append(r)
        return out

    # Coding lessons (2026-10-03, Captain: "hinterlege in der Wissensdatenbank wie man es richtig baut"). A lesson carries trigger words in
    # its tags; code generation attaches every active lesson whose trigger occurs in the task, the selected source or the rework feedback.
    LESSON_TYPE='coding_lesson'

    def add_lesson(self,title,lesson,*,triggers,source_ref=''):
        if not isinstance(triggers,list) or not triggers or any(not isinstance(t,str) or not t.strip() for t in triggers):
            raise ValueError('lesson_triggers_required')
        return self.add(title,lesson,record_type=self.LESSON_TYPE,tags=[t.strip().lower() for t in triggers],source_ref=source_ref)

    def lessons_for(self,text,limit=5,rank=False,min_specificity=0):
        """Active coding lessons whose trigger words occur in `text` (case-insensitive), oldest first, at most `limit`.
        rank=True (DevVM, small models, 2026-10-06): the lessons that fit best come first instead of the oldest: more trigger words that occur, then more characters in them
        (a trigger like `re.match(` says more than `port`). min_specificity=N drops a lesson whose longest matching trigger has fewer than N characters: a generic word such as
        `port` or `digits` must not attach a lesson that has nothing to do with the code (measured: a regex lesson on a dict lookup). Without both, the result is as before."""
        if not self.path.exists() or not isinstance(text,str): return []
        low=text.lower(); out=[]
        for line in self.path.read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            r=json.loads(line)
            if r.get('type')!=self.LESSON_TYPE or r.get('status')!='active': continue
            hits=[t for t in r['scope']['tags'] if t in low]
            if not hits or max(len(t) for t in hits)<min_specificity: continue
            out.append((len(hits),sum(len(t) for t in hits),r))
        if rank: out.sort(key=lambda x:(-x[0],-x[1]))       # stable: equal scores keep their age order
        return [r for _,_,r in out][:limit]
