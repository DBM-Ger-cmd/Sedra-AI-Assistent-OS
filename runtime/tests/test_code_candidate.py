from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import yaml
from unittest.mock import patch
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.cli import main
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ROOT=Path(__file__).resolve().parents[2];ARCH=next((ROOT/'architecture').glob('GUPPI_Architecture_v*'))

class CandidateCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.rt=GuppiRuntime(Path(self.tmp.name),ARCH);self.project=self.rt.filesystem_tool.root/'demo';self.project.mkdir()
        # Own sandbox state: the runtime reads the PC's real config/sandbox.yaml (qualified once the Captain released the VM) and the
        # venv may carry the pinned SDK. Tests use the shipped unqualified default so the "VM unavailable" path holds on any machine.
        p=self.rt.sandbox.policy();p['target_qualified']=False
        self.rt.sandbox.config_path=Path(self.tmp.name)/'unqualified-sandbox.yaml'
        self.rt.sandbox.config_path.write_text(yaml.safe_dump({'sandbox':p}))
        self.old='def greet(name):\r\n    return name\r\n';self.new='def greet(name):\n    return "Hello " + name\n'
        (self.project/'app.py').write_bytes(self.old.encode())
        self.request={'project_path':'demo','files':['app.py'],'changes':[{'path':'app.py','expected_sha256':hashlib.sha256(self.old.encode()).hexdigest(),'content':self.new}]}
    def mission(self,request=None):return self.rt.brain.create_mission('Ändere Code als Kandidat',inputs=deepcopy(request or self.request))
    def ready(self,m):
        for _ in range(4):self.rt.brain.step(m['identity']['mission_id'])
        return self.rt.missions.load(m['identity']['mission_id'])
    def prepared(self,request=None):
        m=self.mission(request);return self.rt.brain.run(m['identity']['mission_id'])
    def report_path(self,m):return self.rt.control.workspace/m['identity']['mission_id']/'candidate-report.json'
    def report(self,m):return json.loads(self.report_path(m).read_text())
    def test_candidate_preparation_preserves_original(self):
        m=self.prepared();self.assertEqual(m['lifecycle']['phase'],'CANDIDATE_REVIEW');self.assertEqual(m['verification']['status'],'PASS')
        r=self.report(m);self.assertEqual((self.project/'app.py').read_bytes(),self.old.encode())
        self.assertEqual((self.rt.filesystem_tool.root/r['candidate']/'app.py').read_text(),self.new)
        self.assertEqual(r['qualification'],'PREPARED_NOT_TESTED');self.assertFalse(r['ready_for_merge']);self.assertFalse(r['tests_executed'])
    def test_diff_and_static_checks(self):
        r=self.report(self.prepared());self.assertIn('source/app.py',r['diff'][0]);self.assertIn('+    return "Hello "',r['diff'][0])
        self.assertEqual(r['static_checks'][0]['check'],'PYTHON_SYNTAX_PASS')
    def test_preview_never_runs_backend(self):
        req=deepcopy(self.request);req['test_commands']=[['python3','-m','unittest','discover']]
        with patch.object(self.rt.sandbox_provider,'execute',side_effect=AssertionError('must not execute')) as execute:
            m=self.prepared(req);execute.assert_not_called()
        self.assertEqual(m['lifecycle']['phase'],'CANDIDATE_REVIEW');r=self.report(m)
        self.assertEqual(r['sandbox_plan']['request']['commands'],req['test_commands']);self.assertFalse(r['sandbox_precheck']['execution_ready'])
    def test_missing_replacements_pauses(self):
        m=self.rt.brain.create_mission('Ändere Code als Kandidat');m=self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertEqual(m['context']['unresolved_questions'][0]['field'],'candidate_request')
    def test_pause_resume_with_request(self):
        m=self.rt.brain.create_mission('Ändere Code als Kandidat');mid=m['identity']['mission_id'];self.rt.brain.run(mid)
        self.rt.brain.set_inputs(mid,self.request);m=self.rt.brain.run(mid);self.assertEqual(m['lifecycle']['phase'],'CANDIDATE_REVIEW')
    def test_wrong_original_sha_pauses(self):
        req=deepcopy(self.request);req['changes'][0]['expected_sha256']='0'*64;m=self.prepared(req)
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertIn('sha256_mismatch',m['plan']['binding_error'])
    def test_invalid_python_not_executed(self):
        req=deepcopy(self.request);req['changes'][0]['content']='def broken(' ;m=self.prepared(req)
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertFalse(m['execution']['artifacts'])
    def test_python_side_effect_is_only_parsed(self):
        req=deepcopy(self.request);req['changes'][0]['content']='raise RuntimeError("must not execute")\n'
        self.assertEqual(self.prepared(req)['lifecycle']['phase'],'CANDIDATE_REVIEW')
    def test_unselected_new_file_rejected(self):
        req=deepcopy(self.request);req['changes'][0]['path']='new.py';m=self.prepared(req)
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertIn('existing_file',m['plan']['binding_error'])
    def test_paths_and_sensitive_names(self):
        for path in ['../app.py','.env','password.py','/tmp/out.py','CON.py']:
            req=deepcopy(self.request);req['changes'][0]['path']=path
            with self.subTest(path=path),self.assertRaises(ValueError):self.mission(req)
    def test_duplicate_portable_paths(self):
        req=deepcopy(self.request);second=deepcopy(req['changes'][0]);second['path']='APP.PY';req['changes'].append(second)
        with self.assertRaises(ValueError):self.mission(req)
    def test_source_changed_after_binding(self):
        m=self.ready(self.mission());(self.project/'app.py').write_text('changed')
        out=self.rt.brain.step(m['identity']['mission_id']);self.assertEqual(out['lifecycle']['phase'],'FAILED');self.assertFalse(out['execution']['artifacts'])
    def test_same_size_mtime_change_is_detected(self):
        m=self.ready(self.mission());path=self.project/'app.py';st=path.stat();blob=path.read_bytes().replace(b'name',b'xxxx')
        path.write_bytes(blob)
        import os
        os.utime(path,ns=(st.st_atime_ns,st.st_mtime_ns))
        out=self.rt.brain.step(m['identity']['mission_id']);self.assertEqual(out['lifecycle']['phase'],'FAILED')
    def test_binding_content_tamper_rejected(self):
        m=self.ready(self.mission());m['plan']['steps'][0]['binding']['inputs']['changes'][0]['content']='print(123)';self.rt.missions.save(m)
        self.assertEqual(self.rt.brain.step(m['identity']['mission_id'])['lifecycle']['phase'],'FAILED')
    def test_candidate_tamper_fails_verification(self):
        m=self.prepared();r=self.report(m);(self.rt.filesystem_tool.root/r['candidate']/'app.py').write_text('changed')
        self.assertEqual(self.rt.verifier.verify(m)['status'],'FAIL')
    def test_unexpected_candidate_file_fails(self):
        m=self.prepared();r=self.report(m);(self.rt.filesystem_tool.root/r['candidate']/'extra.py').write_text('pass')
        self.assertEqual(self.rt.verifier.verify(m)['status'],'FAIL')
    def test_unchanged_selected_files_copied_exactly(self):
        (self.project/'README.md').write_bytes(b'Unchanged\r\n');req=deepcopy(self.request);req['files'].append('README.md')
        m=self.prepared(req);r=self.report(m)
        self.assertEqual((self.rt.filesystem_tool.root/r['candidate']/'README.md').read_bytes(),b'Unchanged\r\n')
    def test_nested_source_file(self):
        (self.project/'src').mkdir();(self.project/'src'/'app.py').write_bytes(self.old.encode());req=deepcopy(self.request)
        req['files']=['src/app.py'];req['changes'][0]['path']='src/app.py';m=self.prepared(req)
        self.assertEqual(m['verification']['status'],'PASS')
    def test_source_symlink_rejected(self):
        try:(self.project/'alias.py').symlink_to(self.project/'app.py')
        except OSError:self.skipTest('symlink unavailable')
        req=deepcopy(self.request);req['files']=['alias.py'];req['changes'][0]['path']='alias.py';m=self.prepared(req)
        self.assertEqual(m['lifecycle']['phase'],'PAUSED')
    def test_budget_and_command_schema(self):
        req=deepcopy(self.request);req['changes'][0]['content']='x'*65537
        with self.assertRaises(ValueError):self.mission(req)
        req=deepcopy(self.request);req['test_commands']='python app.py'
        with self.assertRaises(ValueError):self.mission(req)
    def test_noop_rejected(self):
        req=deepcopy(self.request);req['changes'][0]['content']=self.old;m=self.prepared(req)
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertIn('noop',m['plan']['binding_error'])
    def test_read_guard_denial_pauses_before_staging(self):
        original=self.rt.guard.evaluate
        def deny(action,**kw):return {'decision':'BLOCK'} if action=='read_project_file' else original(action,**kw)
        with patch.object(self.rt.guard,'evaluate',side_effect=deny):m=self.prepared()
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertFalse((self.rt.filesystem_tool.root/'guppi-candidates').exists())
    def test_candidate_review_is_not_approved_merge(self):
        m=self.prepared();mid=m['identity']['mission_id'];again=self.rt.brain.run(mid,approval_token={'status':'active','token_id':'fake'})
        self.assertEqual(again['lifecycle']['phase'],'CANDIDATE_REVIEW');self.assertEqual((self.project/'app.py').read_bytes(),self.old.encode())
    def test_cli_request(self):
        request=Path(self.tmp.name)/'request.json';request.write_text(json.dumps(self.request))
        common=['--root',self.tmp.name,'--architecture',str(ARCH)]
        with patch('builtins.print') as output:
            self.assertEqual(main(common+['new-mission','--intent','Ändere Code als Kandidat','--candidate-request',str(request)]),0)
            mid=output.call_args.args[0];self.assertEqual(main(common+['run',mid]),0)
        self.assertEqual(self.rt.missions.load(mid)['lifecycle']['phase'],'CANDIDATE_REVIEW')
    def test_stage_namespace_cannot_be_source(self):
        req=deepcopy(self.request);req['project_path']='guppi-candidates/source'
        with self.assertRaises(ValueError):self.mission(req)
    def test_report_expansion_budget_stops_qualification(self):
        req={'project_path':'demo','files':[],'changes':[]}
        old='\x00'*65536;new='\x01'*65536
        for n in range(4):
            name=f'file{n}.txt';(self.project/name).write_bytes(old.encode());req['files'].append(name)
            req['changes'].append({'path':name,'expected_sha256':hashlib.sha256(old.encode()).hexdigest(),'content':new})
        m=self.prepared(req);self.assertEqual(m['lifecycle']['phase'],'FAILED')
        self.assertIn('report_byte_budget',m['execution']['errors'][0]);self.assertFalse(m['execution']['artifacts'])
