"""Read-only bounded inspection through routed FilesystemTool calls."""
import hashlib
import json
from ..execution_binder import BindingError


class ProjectInspector:
    def __init__(self, binder):self.binder=binder

    def execute(self, control, mission, binding, approval_token=None):
        mid=mission['identity']['mission_id'];calls=[]
        try:
            self.binder.revalidate(mission,binding)
            def call(operation,args):
                out=control._tool_call(mid,{'tool':'filesystem','operation':operation,'args':args},mission=mission)
                if out['status']!='completed':raise InspectionStopped(out)
                result=out['tool_result']
                calls.append({'tool':'filesystem','operation':operation,'args':args,
                              'result':{k:v for k,v in result.items() if k!='content'}})
                return result
            path=binding['project_path']
            listing=call('list_dir',{'path':path,'limit':self.binder.MAX_ENTRIES,'bounded':True})
            if listing['truncated'] or listing['entries']!=binding['snapshot']['entries']:
                raise BindingError('inspection_listing_changed')
            files=[]
            for selected in binding['snapshot']['files']:
                file=selected['file'];args={'path':path+'/'+file}
                hash_args=dict(args,max_bytes=self.binder.MAX_FILE_BYTES)
                before=call('sha256',hash_args)['sha256']
                reading=call('read_text',dict(args,encoding='utf-8',max_bytes=self.binder.MAX_FILE_BYTES))
                after=call('sha256',hash_args)['sha256']
                observed=hashlib.sha256(reading['content'].encode('utf-8')).hexdigest()
                if before!=after or observed!=before or reading['bytes']!=selected['size']:
                    raise BindingError('inspection_file_changed_during_read')
                files.append({'file':file,'bytes':reading['bytes'],'sha256':before,
                              'lines':len(reading['content'].splitlines()),'encoding':'utf-8'})
            self.binder.revalidate(mission,binding)
            report={'schema':1,'kind':'project_inspection','mission_id':mid,'created_at':mission['execution'].get('report_created_at',mission['identity']['created_at']),
                    'binding_digest':binding['digest'],'project_path':path,'scope':'root inventory and selected UTF-8 files; no recursive or semantic code review',
                    'entries':listing['entries'],'files':files,'tool_evidence':calls,
                    'project_modified':False,'host_code_executed':False,'tests_executed':False,
                    'git_inspection':'NOT_EXECUTED; untrusted Git configuration hardening remains separate',
                    'limits':{'entries':self.binder.MAX_ENTRIES,'files':self.binder.MAX_FILES,
                              'file_bytes':self.binder.MAX_FILE_BYTES,'total_bytes':self.binder.MAX_TOTAL_BYTES},
                    'limitations':['No nested-directory discovery','Hidden/sensitive names excluded from file selection, not necessarily from directory inventory',
                                   'No semantic code quality or test outcome asserted','Live filesystem reads are not an atomic snapshot']}
            out=control._create_text_artifact(mission,{'target':'inspection.json','content':json.dumps(report,indent=2,ensure_ascii=False)+'\n'},approval_token)
            if out['status']=='completed':out['inspection']={'binding_digest':binding['digest'],'files':len(files),'entries':len(listing['entries'])}
            return out
        except InspectionStopped as exc:return exc.result
        except Exception as exc:
            return {'status':'failed','error':f'{type(exc).__name__}:{exc}','artifacts':[]}


class InspectionStopped(Exception):
    def __init__(self,result):self.result=result
