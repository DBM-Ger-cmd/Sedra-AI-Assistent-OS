"""Closed candidate preparation: supplied replacements, no source writes or execution."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re

from ..selfdev.execution_binder import ExecutionParameterBinder, BindingError, digest


class CandidateBinder(ExecutionParameterBinder):
    CANDIDATE_WORKFLOW='code-candidate-v1'
    STAGING='guppi-candidates'
    CANDIDATE_SUFFIXES={'.py','.md','.txt','.json','.yaml','.yml','.toml','.csv'}

    def __init__(self,filesystem,tools):
        super().__init__(filesystem)
        self.tools=tools

    def validate_inputs(self,inputs):
        if isinstance(inputs,dict) and ('changes' in inputs or 'test_commands' in inputs):
            if set(inputs)-{'project_path','files','changes','test_commands'}:raise BindingError('unsupported_candidate_inputs')
            base={k:v for k,v in inputs.items() if k in {'project_path','files'}}
            super().validate_inputs(base)
            if (inputs.get('project_path') or '').split('/')[0]==self.STAGING:raise BindingError('candidate_namespace_not_source')
            changes=inputs.get('changes')
            if changes is not None:
                if not isinstance(changes,list) or not 1<=len(changes)<=self.MAX_FILES:raise BindingError('invalid_candidate_changes')
                seen=set();total=0
                for change in changes:
                    if not isinstance(change,dict) or set(change)!={'path','expected_sha256','content'}:raise BindingError('invalid_change_schema')
                    path=self.relative(change['path'])
                    if not all(self.allowed_name(p) for p in path.split('/')) or Path(path).suffix.lower() not in self.CANDIDATE_SUFFIXES:raise BindingError('unsupported_candidate_file')
                    if path.casefold() in seen:raise BindingError('duplicate_portable_change_path')
                    seen.add(path.casefold())
                    if not isinstance(change['expected_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',change['expected_sha256']):raise BindingError('expected_source_sha256_required')
                    if not isinstance(change['content'],str):raise BindingError('replacement_text_required')
                    size=len(change['content'].encode('utf-8'));total+=size
                    if size>self.MAX_FILE_BYTES or total>self.MAX_TOTAL_BYTES:raise BindingError('candidate_replacement_budget_exceeded')
            commands=inputs.get('test_commands')
            if commands is not None:
                if not isinstance(commands,list) or not 1<=len(commands)<=3:raise BindingError('invalid_test_commands')
                for argv in commands:
                    if not isinstance(argv,list) or not 1<=len(argv)<=32 or any(not isinstance(x,str) or not x or len(x)>512 or '\x00' in x for x in argv):raise BindingError('invalid_guest_test_argv')
            return inputs
        return super().validate_inputs(inputs)

    def source(self,mission,inputs):
        data={};records=[];total=0
        for file in inputs['files']:
            args={'path':inputs['project_path']+'/'+file,'encoding':'utf-8','max_bytes':self.MAX_FILE_BYTES}
            out=self.tools.execute('filesystem',mission['identity']['mission_id'],'read_text',args)
            if out.get('status')!='completed':raise BindingError('candidate_source_read_blocked')
            raw=out['content'].encode('utf-8');total+=len(raw)
            if total>self.MAX_TOTAL_BYTES:raise BindingError('candidate_source_budget_exceeded')
            data[file]=out['content'];records.append({'path':file,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        return records,data

    @staticmethod
    def static_check(path,content):
        if path.endswith('.py'):
            ast.parse(content,filename=path);return 'PYTHON_SYNTAX_PASS'
        if path.endswith('.json'):
            json.loads(content);return 'JSON_SYNTAX_PASS'
        return 'TEXT_ONLY_NO_LANGUAGE_VALIDATION'

    def bind(self,mission):
        route=(mission.get('routing') or {}).get('route') or {};inputs=mission.get('inputs') or {}
        if route.get('primary_intent')!='code_change' and 'changes' not in inputs:return super().bind(mission)
        try:
            self.validate_inputs(inputs)
            if route.get('primary_intent')!='code_change':raise BindingError('candidate_requires_code_change_intent')
            if not inputs.get('project_path') or not inputs.get('files') or not inputs.get('changes'):
                raise BindingError('project_path_files_and_changes_required')
            if not re.fullmatch('M-[0-9A-F]{8}',mission['identity']['mission_id']):raise BindingError('invalid_candidate_mission_id')
            if inputs['project_path'].split('/')[0]==self.STAGING:raise BindingError('candidate_namespace_not_source')
            if {x['id'] for x in route['intent_families']}-{'code_change','project_analysis','test_validation','debugging','sandbox_execution'}:raise BindingError('unsupported_mixed_candidate_workflow')
            if 'safe-code-change' not in {s['id'] for s in route['skills']}:raise BindingError('safe_code_skill_not_selected')
            if 'filesystem' not in {t['id'] for t in route['tools']}:raise BindingError('filesystem_not_selected')
            if inputs.get('test_commands') and 'sandbox' not in {t['id'] for t in route['tools']}:raise BindingError('sandbox_not_selected_for_test_preview')
            if len({f.casefold() for f in inputs['files']})!=len(inputs['files']):raise BindingError('portable_file_collision')
            for f in inputs['files']:
                if Path(f).suffix.lower() not in self.CANDIDATE_SUFFIXES:raise BindingError('unsupported_candidate_source_file')
            for f in inputs['files']:
                if any(g!=f and g.casefold().startswith(f.casefold()+'/') for g in inputs['files']):raise BindingError('file_directory_collision')
            snapshot=self.snapshot(inputs['project_path'],inputs['files'])
            records,data=self.source(mission,inputs);hashes={r['path']:r['sha256'] for r in records};checks=[]
            changed=set()
            for change in inputs['changes']:
                file=change['path']
                if file not in data:raise BindingError('change_must_target_selected_existing_file')
                if hashes[file]!=change['expected_sha256']:raise BindingError('expected_source_sha256_mismatch')
                if data[file]==change['content']:raise BindingError('candidate_change_is_noop')
                changed.add(file);checks.append({'path':file,'check':self.static_check(file,change['content'])})
            outputs=dict(data);outputs.update({c['path']:c['content'] for c in inputs['changes']})
            if sum(len(c.encode('utf-8')) for c in outputs.values())>self.MAX_TOTAL_BYTES:raise BindingError('candidate_output_budget_exceeded')
            if self.snapshot(inputs['project_path'],inputs['files'])!=snapshot:raise BindingError('source_changed_during_binding')
            binding={'schema':1,'workflow':self.CANDIDATE_WORKFLOW,'mission_id':mission['identity']['mission_id'],
                     'tool_root':str(self.filesystem.root),'inputs':inputs,'snapshot':snapshot,'source_files':records,'static_checks':checks}
            binding['digest']=digest(binding)
            return {'status':'ready','workflow':self.CANDIDATE_WORKFLOW,'questions':[],
                    'steps':[{'id':'CANDIDATE-1','action':'prepare_code_candidate','binding':binding}],
                    'acceptance_criteria':[{'type':'code_candidate_preparation','binding_digest':binding['digest']}],
                    'execution_status':'bound_candidate_preparation; no_test_execution'}
        except (ValueError,OSError,RuntimeError,SyntaxError,RecursionError) as exc:
            return {'status':'needs_input','workflow':self.CANDIDATE_WORKFLOW,'binding_error':str(exc),
                    'questions':[{'field':'candidate_request','question':'Bitte Projektpfad, explizite Quelldateien und Änderungen mit Original-SHA256 bereitstellen oder korrigieren.','reason':str(exc)}],
                    'steps':[],'acceptance_criteria':[],'execution_status':'blocked_until_valid_candidate_request'}

    def revalidate_candidate(self,mission,binding):
        current=self.bind(mission)
        if not current or current['status']!='ready' or current['steps'][0]['binding']!=binding:raise BindingError('candidate_binding_changed_replan_required')


class CandidatePreparer:
    def __init__(self,binder):self.binder=binder

    def execute(self,control,mission,binding,approval_token=None):
        stage=None;record=None
        from ..selfdev.candidate_lifecycle import preparation,persist
        try:
            self.binder.revalidate_candidate(mission,binding)
            inputs=binding['inputs'];records,data=self.binder.source(mission,inputs)
            if records!=binding['source_files']:raise BindingError('source_changed_before_staging')
            base=dict(data);data.update({c['path']:c['content'] for c in inputs['changes']})
            mid=mission['identity']['mission_id']
            record=preparation(control,mission,binding)
            stage=record['stage']
            target=self.binder.filesystem._resolve(stage)
            if target.exists() and not target.is_dir():raise BindingError('candidate_stage_not_directory')
            calls=record['calls']
            def call(tool,operation,args):
                out=control._tool_call(mid,{'tool':tool,'operation':operation,'args':args},approval_token,mission=mission)
                if out['status']!='completed':raise CandidateStopped(out)
                evidence={'tool':tool,'operation':operation,'path':out['tool_result'].get('path')}
                if evidence not in calls:calls.append(evidence)
                persist(control,mission)
                return out['tool_result']
            if not target.exists():call('filesystem','mkdir',{'path':stage})
            staged=[]
            for file,content in data.items():
                # Paths come exclusively from the validated selection, never from generated code.
                existing=self.binder.filesystem._resolve(stage+'/'+file)
                if existing.exists():
                    out=control._tool_call(mid,{'tool':'filesystem','operation':'read_text','args':{'path':stage+'/'+file,'max_bytes':self.binder.MAX_FILE_BYTES,'encoding':'utf-8'}},mission=mission)
                    if out['status']!='completed':raise CandidateStopped(out)
                    if out['tool_result']['content']!=content:raise BindingError('staged_candidate_changed_requires_review')
                    out={'bytes':len(content.encode('utf-8')),'sha256':hashlib.sha256(content.encode('utf-8')).hexdigest()}
                else:
                    out=call('filesystem','write_text',{'path':stage+'/'+file,'content':content,'encoding':'utf-8'})
                staged.append({'path':file,'bytes':out['bytes'],'sha256':out['sha256']})
            self.binder.revalidate_candidate(mission,binding)
            commands=inputs.get('test_commands');test_plan=None;health=None
            if commands:
                test_plan=call('sandbox','preview',{'source':stage,'commands':commands,'exports':[]})['plan']
                health=call('sandbox','doctor',{})['sandbox']
            diffs=[]
            for change in inputs['changes']:
                file=change['path']
                diffs.append(''.join(difflib.unified_diff(base[file].splitlines(keepends=True),data[file].splitlines(keepends=True),fromfile='source/'+file,tofile='candidate/'+file)))
            report={'schema':1,'kind':'code_candidate_preparation','mission_id':mid,'created_at':record['created_at'],
                    'binding_digest':binding['digest'],'source':inputs['project_path'],'candidate':stage,
                    'source_files':records,'candidate_files':staged,'static_checks':binding['static_checks'],
                    'diff':diffs,'tool_evidence':calls,'sandbox_plan':test_plan,'sandbox_precheck':health,
                    'qualification':'PREPARED_NOT_TESTED','tests_executed':False,'host_code_executed':False,
                    'source_modified':False,'ready_for_merge':False,'captain_review':'PENDING',
                    'scope':'explicit selected-file subset; supplied replacements; no model-generated code',
                    'immutability':'hash-sealed manifest; workspace is not physically read-only'}
            encoded=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
            if len(encoded.encode('utf-8'))>2000000:raise BindingError('candidate_report_byte_budget_exceeded')
            record['status']='REPORT_PENDING';persist(control,mission)
            out=control._create_text_artifact(mission,{'target':'candidate-report.json','content':encoded},approval_token)
            record['status']='READY_UNVERIFIED' if out['status']=='completed' else 'REPORT_PENDING';persist(control,mission)
            if out['status']=='completed':out['candidate']={'path':stage,'qualification':'PREPARED_NOT_TESTED'}
            return out
        except CandidateStopped as exc:
            if record:
                record['status']='GATE' if exc.result['status']=='captain_required' else 'BLOCKED';record['reason']=exc.result.get('error') or exc.result['status'];persist(control,mission)
            return dict(exc.result,candidate_stage=stage)
        except Exception as exc:
            if record:record.update(status='FAILED',reason=str(exc));persist(control,mission)
            return {'status':'failed','error':f'{type(exc).__name__}:{exc}','artifacts':[],'candidate_stage':stage}


class CandidateStopped(Exception):
    def __init__(self,result):self.result=result
