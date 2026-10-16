from pathlib import Path
import hashlib
import json
import re
from .base import BaseModule
class VerificationModule(BaseModule):
    id='verification'
    def verify(self,mission):
        if mission['plan'].get('workflow')=='code-candidate-v1':
            from ..candidate_verification import verify_candidate
            return verify_candidate(self,mission)
        if mission['plan'].get('workflow')=='project-inspection-v1':
            return self.verify_inspection(mission)
        findings=[]; evidence=[]
        criteria=mission['plan'].get('acceptance_criteria',[])
        artifacts=mission['execution'].get('artifacts',[])
        for c in criteria:
            if c.get('type')=='artifact_exists':
                min_count=int(c.get('min_count',1))
                existing=[a for a in artifacts if Path(a['path']).exists()]
                evidence.append({'criterion':c,'existing':len(existing)})
                if len(existing)<min_count: findings.append('artifact_exists criterion failed')
        status='PASS' if not findings else 'FAIL'
        return {'status':status,'findings':findings,'evidence':evidence,'rework_request':None if status=='PASS' else {'reason':findings}}
    def verify_inspection(self,mission):
        findings=[];evidence=[]
        try:
            binder=self.inspection_binder
            binding=mission['plan']['steps'][0]['binding']
            binder.revalidate(mission,binding)
            criteria=mission['plan']['acceptance_criteria']
            if criteria!=[{'type':'project_inspection_report','binding_digest':binding['digest']}]:raise ValueError('inspection_criteria_changed')
            mid=mission['identity']['mission_id']
            path=self.workspace/mid/'inspection.json'
            path.resolve().relative_to(self.workspace.resolve())
            if path.is_symlink() or not path.is_file() or path.stat().st_size>2000000:raise ValueError('inspection_report_missing_or_invalid')
            record=next((a for a in mission['execution']['artifacts'] if Path(a['path'])==path),None)
            raw=path.read_bytes()
            if not record or hashlib.sha256(raw).hexdigest()!=record['integrity']['hash']:raise ValueError('inspection_report_integrity_failed')
            report=json.loads(raw)
            if report.get('kind')!='project_inspection' or report.get('schema')!=1 or report.get('mission_id')!=mid or report.get('binding_digest')!=binding['digest'] or report.get('project_path')!=binding['project_path']:
                raise ValueError('inspection_report_identity_mismatch')
            if report.get('entries')!=binding['snapshot']['entries']:raise ValueError('inspection_report_listing_mismatch')
            if any(report.get(k) is not False for k in ('project_modified','host_code_executed','tests_executed')):raise ValueError('inspection_scope_claim_invalid')
            files=report['files']
            if not isinstance(files,list) or [f['file'] for f in files]!=[f['file'] for f in binding['snapshot']['files']]:raise ValueError('inspection_report_file_selection_mismatch')
            allowed={t['id'] for t in mission['routing']['route']['tools']}
            if 'filesystem' not in allowed:raise ValueError('verification_filesystem_not_selected')
            calls=report['tool_evidence']
            expected=[('list_dir',{'path':binding['project_path'],'limit':binder.MAX_ENTRIES,'bounded':True})]
            for file in files:
                args={'path':binding['project_path']+'/'+file['file']}
                expected.extend([('sha256',dict(args,max_bytes=binder.MAX_FILE_BYTES)),('read_text',dict(args,encoding='utf-8',max_bytes=binder.MAX_FILE_BYTES)),('sha256',dict(args,max_bytes=binder.MAX_FILE_BYTES))])
            if [(c['operation'],c['args']) for c in calls]!=expected or any(c['tool']!='filesystem' or c['result']['status']!='completed' for c in calls):raise ValueError('inspection_tool_evidence_invalid')
            for file in files:
                if not isinstance(file.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',file['sha256']):raise ValueError('invalid_observed_sha256')
                out=self.tools.execute('filesystem',mid,'read_text',{'path':binding['project_path']+'/'+file['file'],'encoding':'utf-8','max_bytes':binder.MAX_FILE_BYTES})
                if out['status']!='completed':raise ValueError('verification_source_read_blocked')
                if hashlib.sha256(out['content'].encode('utf-8')).hexdigest()!=file['sha256'] or out['bytes']!=file['bytes'] or len(out['content'].splitlines())!=file['lines']:
                    raise ValueError('inspection_source_evidence_mismatch')
            binder.revalidate(mission,binding)
            evidence.append({'criterion':'project_inspection_report','artifact_id':record['artifact_id'],'verified_files':len(files),'verified_entries':len(report['entries']),'binding_digest':binding['digest']})
        except Exception as exc:findings.append(f'{type(exc).__name__}:{exc}')
        return {'status':'FAIL' if findings else 'PASS','findings':findings,'evidence':evidence,'rework_request':{'reason':findings} if findings else None}
    def handle(self,message): return self.verify(message.payload['mission'])
