"""Managed project registry; never mount arbitrary host directories."""
import uuid
from .util import load_json,atomic_write_json,utcnow

class ProjectRegistry:
    def __init__(self,rt):self.rt=rt;self.path=rt.project_root/'runtime_data/projects.json'
    def list(self):return load_json(self.path,[])
    def get(self,pid):
        item=next((p for p in self.list() if p['project_id']==pid),None)
        if not item:raise ValueError('unknown_project_id')
        self.rt.filesystem_tool._resolve(item['workspace_path'],must_exist=True);return item
    def create(self,name):
        if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('project_name_required')
        records=self.list()
        if len(records)>=64:raise ValueError('project_limit')
        pid='PRJ-'+uuid.uuid4().hex[:12];path='projects/'+pid
        out=self.rt.filesystem_tool.execute('M-PROJECT','mkdir',{'path':path})
        if out['status']!='completed':raise ValueError('project_creation_blocked')
        rec={'project_id':pid,'display_name':name.strip(),'workspace_path':path,'created_at':utcnow(),'status':'ACTIVE','qualification':'MANAGED_WORKSPACE_NOT_VM'}
        records.append(rec);atomic_write_json(self.path,records);return rec
