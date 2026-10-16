"""Closed argument binder for a read-only project inventory workflow."""
import hashlib
import json
import os
from pathlib import PurePosixPath


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class BindingError(ValueError): pass


class ExecutionParameterBinder:
    WORKFLOW = 'project-inspection-v1'
    MAX_ENTRIES = 200
    MAX_FILES = 8
    MAX_FILE_BYTES = 65536
    MAX_TOTAL_BYTES = 262144
    DEFAULT_FILES = ('README.md', 'README.txt', 'pyproject.toml', 'package.json', 'requirements.txt')
    SUFFIXES = {'.md', '.txt', '.toml', '.json', '.yaml', '.yml', '.py', '.js', '.ts', '.csv'}

    def __init__(self, filesystem): self.filesystem = filesystem

    @staticmethod
    def relative(value):
        if not isinstance(value, str) or not value or len(value) > 240 or '\\' in value or ':' in value:
            raise BindingError('relative_project_path_required')
        parts=value.split('/')
        if any(not p or p in {'.','..'} or p.startswith('.') or any(ord(c)<32 for c in p) for p in parts):
            raise BindingError('protected_or_traversing_path')
        reserved={'con','prn','aux','nul'}|{p+str(n) for p in ('com','lpt') for n in range(1,10)}
        if any(p.endswith((' ','.')) or p.split('.')[0].casefold() in reserved for p in parts):
            raise BindingError('unsafe_portable_filename')
        if PurePosixPath(value).is_absolute(): raise BindingError('relative_project_path_required')
        return value

    @staticmethod
    def allowed_name(name):
        lower=name.casefold()
        return not name.startswith('.') and not any(x in lower for x in ('secret','credential','password','passwd','token','api_key','id_rsa'))

    def validate_inputs(self, inputs):
        if not isinstance(inputs,dict) or set(inputs)-{'project_path','files'}:
            raise BindingError('unsupported_inspection_inputs')
        path=inputs.get('project_path')
        if path is not None:self.relative(path)
        files=inputs.get('files')
        if files is not None:
            if not isinstance(files,list) or len(files)>self.MAX_FILES: raise BindingError('invalid_inspection_files')
            for file in files:
                self.relative(file)
                if not all(self.allowed_name(part) for part in PurePosixPath(file).parts) or PurePosixPath(file).suffix.lower() not in self.SUFFIXES:
                    raise BindingError('protected_or_unsupported_inspection_file')
            if len(set(files))!=len(files):raise BindingError('duplicate_inspection_file')
        return inputs

    def snapshot(self, path, files):
        root=self.filesystem._resolve(path,must_exist=True)
        if not root.is_dir() or root==self.filesystem.root:raise BindingError('explicit_project_directory_required')
        # Metadata only; no code imports, recursive scans, config interpretation or file reads.
        children=[]
        with os.scandir(root) as scanner:
            for child in scanner:
                if len(children)>=self.MAX_ENTRIES:raise BindingError('project_directory_entry_budget_exceeded')
                if child.is_symlink():kind='symlink';size=None
                elif child.is_dir(follow_symlinks=False):kind='dir';size=None
                elif child.is_file(follow_symlinks=False):kind='file';size=child.stat(follow_symlinks=False).st_size
                else:kind='special';size=None
                children.append({'name':child.name,'type':kind,'size':size})
        chosen=list(files) if files is not None else [f for f in self.DEFAULT_FILES if (root/f).is_file()]
        selected=[];total=0
        for file in chosen:
            full=self.filesystem._resolve(path+'/'+file,must_exist=True)
            if not full.is_file():raise BindingError('inspection_target_not_file')
            st=full.stat()
            if st.st_size>self.MAX_FILE_BYTES:raise BindingError('inspection_file_byte_budget_exceeded')
            total+=st.st_size
            if total>self.MAX_TOTAL_BYTES:raise BindingError('inspection_total_byte_budget_exceeded')
            selected.append({'file':file,'size':st.st_size,'mtime_ns':st.st_mtime_ns,'inode':st.st_ino,'device':st.st_dev})
        st=root.stat()
        return {'root_identity':{'inode':st.st_ino,'device':st.st_dev},
                'entries':sorted(children,key=lambda x:x['name']), 'files':selected}

    def bind(self, mission):
        route=(mission.get('routing') or {}).get('route') or {}
        if route.get('primary_intent')!='project_analysis':
            if mission.get('inputs',{}).get('project_path'):
                return {'status':'needs_input','workflow':self.WORKFLOW,'binding_error':'requested_workflow_not_supported_by_inspection_binder',
                        'questions':[{'field':'workflow','question':'v1.12 kann diesen Projektpfad nur als reine Bestandsaufnahme untersuchen. Bitte eine getrennte Untersuchungsmission anlegen.'}],
                        'steps':[],'acceptance_criteria':[],'execution_status':'unsupported_workflow'}
            return None
        questions=[]
        inputs=mission.get('inputs') or {}
        try:
            self.validate_inputs(inputs)
            if not inputs.get('project_path'):
                questions.append({'field':'project_path','question':'Welchen Projekt-Unterordner im GUPPI tool_workspace soll ich untersuchen?','example':'demo-project'})
                raise BindingError('project_path_missing')
            if {x['id'] for x in route.get('intent_families',[])}-{'project_analysis'}:
                raise BindingError('mixed_workflow_not_supported_by_inspection_binder')
            if 'project-inspection' not in {x['id'] for x in route.get('skills',[])}:
                raise BindingError('project_inspection_skill_not_selected')
            if 'filesystem' not in {x['id'] for x in route.get('tools',[])}:
                raise BindingError('filesystem_not_selected')
            snapshot=self.snapshot(inputs['project_path'],inputs.get('files'))
            binding={'schema':1,'workflow':self.WORKFLOW,'mission_id':mission['identity']['mission_id'],
                     'tool_root':str(self.filesystem.root),'project_path':inputs['project_path'],
                     'requested_files':inputs.get('files'),'snapshot':snapshot}
            binding['digest']=digest(binding)
            return {'status':'ready','workflow':self.WORKFLOW,'questions':[],
                    'steps':[{'id':'INSPECT-1','action':'inspect_project','binding':binding}],
                    'acceptance_criteria':[{'type':'project_inspection_report','binding_digest':binding['digest']}],
                    'execution_status':'bound_read_only_workflow'}
        except (ValueError,OSError,RuntimeError) as exc:
            if not questions:
                questions=[{'field':'inputs','question':'Bitte Projektpfad und Dateiauswahl prüfen und die Mission erneut planen.','reason':str(exc)}]
            return {'status':'needs_input','workflow':self.WORKFLOW,'questions':questions,
                    'binding_error':str(exc),'steps':[],'acceptance_criteria':[],
                    'execution_status':'blocked_until_valid_binding'}

    def revalidate(self, mission, binding):
        expected=self.bind(mission)
        if not expected or expected['status']!='ready' or expected['steps'][0]['binding']!=binding:
            raise BindingError('inspection_binding_changed_replan_required')
        return binding
