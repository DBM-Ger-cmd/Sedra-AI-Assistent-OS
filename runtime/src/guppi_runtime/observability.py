from __future__ import annotations
from .util import utcnow
class Observability:
    def __init__(self): self.checks={}
    def register(self, component_id, check): self.checks[component_id]=check
    def report(self):
        out=[]
        for cid,fn in self.checks.items():
            try:
                ok=bool(fn()); state='HEALTHY' if ok else 'UNHEALTHY'; finding=[] if ok else ['health check returned false']
            except Exception as e:
                state='UNHEALTHY'; finding=[repr(e)]
            out.append({'component_id':cid,'timestamp':utcnow(),'state':state,'blocking_findings':finding,'warnings':[]})
        return out
    def overall(self):
        reports=self.report(); return 'HEALTHY' if all(r['state']=='HEALTHY' for r in reports) else 'DEGRADED'
