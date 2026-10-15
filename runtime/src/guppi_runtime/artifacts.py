from __future__ import annotations
from pathlib import Path
import uuid
from .util import sha256_file, atomic_write_json, load_json, utcnow, append_lock

class ArtifactStore:
    def __init__(self, root: Path, audit=None):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.index=self.root/'index.json'; self.audit=audit
    def register(self, mission_id, path: Path, source_component='control-master', evolution_id=None, job_id=None):
        path=Path(path); digest=sha256_file(path)
        # The index is read, extended and rewritten: do that under a lock so concurrent writers cannot drop each other's records.
        with append_lock(self.index):
            records=load_json(self.index,[]) or []
            rec={'schema':1,'artifact_id':f"ART-{uuid.uuid4().hex[:8].upper()}",'mission_id':mission_id,'path':str(path),'type':'file','version':'1','provenance':{'created_by':'system','source_component':source_component,'evolution_id':evolution_id,'created_at':utcnow()},'integrity':{'algorithm':'sha256','hash':digest},'status':'active'}
            if job_id is not None: rec['job_id']=job_id   # optional; records written before Phase 3 simply lack it
            records.append(rec); atomic_write_json(self.index,records)
        if self.audit: self.audit.append('ARTIFACT_CREATED',component=source_component,mission_id=mission_id,payload={'artifact_id':rec['artifact_id'],'path':str(path),'hash':rec['integrity']['hash']})
        return rec
    def list(self, mission_id=None):
        records=load_json(self.index,[]) or []
        return [r for r in records if mission_id is None or r['mission_id']==mission_id]
    def get(self, artifact_id):
        for rec in load_json(self.index,[]) or []:
            if rec.get('artifact_id')==artifact_id: return rec
        return None
