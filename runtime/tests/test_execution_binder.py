import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.execution_binder import BindingError
from guppi_runtime.cli import main
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ROOT=Path(__file__).resolve().parents[2]
ARCH=next((ROOT/'architecture').glob('GUPPI_Architecture_v*'))

class BinderCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.rt=GuppiRuntime(self.root,ARCH)
        self.project=self.rt.filesystem_tool.root/'demo';self.project.mkdir()
        (self.project/'README.md').write_bytes(b'# Demo\r\nRead-only project\r\n')
        (self.project/'app.py').write_text('raise RuntimeError("must never import project code")\n')
    def mission(self,files=None):
        return self.rt.brain.create_mission('Analysiere dieses Projekt',inputs={'project_path':'demo','files':files})
    def ready(self,m):
        mid=m['identity']['mission_id']
        for _ in range(4):self.rt.brain.step(mid)
        return self.rt.missions.load(mid)
    def completed(self):
        m=self.mission();return self.rt.brain.run(m['identity']['mission_id'])
    def report(self,m):return self.rt.control.workspace/m['identity']['mission_id']/'inspection.json'
    def tamper_report(self,m,mutator,update_hash=False):
        p=self.report(m);value=json.loads(p.read_text());mutator(value);p.write_text(json.dumps(value))
        if update_hash:
            m['execution']['artifacts'][0]['integrity']['hash']=hashlib.sha256(p.read_bytes()).hexdigest()
        return m
    def test_end_to_end_inspection(self):
        before={p.name:p.read_bytes() for p in self.project.iterdir()}
        m=self.completed();self.assertEqual(m['lifecycle']['phase'],'COMPLETE');self.assertEqual(m['verification']['status'],'PASS')
        report=json.loads(self.report(m).read_text());self.assertEqual(report['files'][0]['sha256'],hashlib.sha256(before['README.md']).hexdigest())
        self.assertEqual(report['files'][0]['lines'],2);self.assertEqual(report['files'][0]['bytes'],len(before['README.md']))
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.project.iterdir()});self.assertFalse(report['host_code_executed'])
    def test_missing_input_pauses_before_execution(self):
        m=self.rt.brain.create_mission('Analysiere dieses Projekt');m=self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertEqual(m['plan']['status'],'needs_input')
        self.assertEqual(m['context']['unresolved_questions'][0]['field'],'project_path');self.assertFalse(m['execution']['results'])
    def test_resume_with_inputs_preserves_original_intent(self):
        intent='Analysiere dieses Projekt';m=self.rt.brain.create_mission(intent);mid=m['identity']['mission_id'];self.rt.brain.run(mid)
        self.rt.brain.set_inputs(mid,{'project_path':'demo'});m=self.rt.brain.run(mid)
        self.assertEqual(m['lifecycle']['phase'],'COMPLETE');self.assertEqual(m['captain_intent']['original'],intent)
    def test_invalid_paths(self):
        for path in ['../escape','/tmp','demo/../other','.','demo\\file','C:/project','demo/.git','CON','demo.']:
            with self.subTest(path=path),self.assertRaises(ValueError):self.rt.brain.create_mission('Analysiere dieses Projekt',inputs={'project_path':path})
    def test_missing_project_is_question(self):
        m=self.rt.brain.create_mission('Analysiere dieses Projekt',inputs={'project_path':'missing'});m=self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertIn('path_not_found',m['plan']['binding_error'])
    def test_symlink_project_rejected(self):
        link=self.rt.filesystem_tool.root/'alias'
        try:link.symlink_to(self.project,target_is_directory=True)
        except OSError:self.skipTest('symlink unavailable')
        m=self.rt.brain.create_mission('Analysiere dieses Projekt',inputs={'project_path':'alias'});m=self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertIn('symlink',m['plan']['binding_error'])
    def test_sensitive_selection_rejected(self):
        for file in ['.env','secret.json','passwords.txt','credentials.json','tokens.py','private/id_rsa','secret/config.py','app.exe']:
            with self.subTest(file=file),self.assertRaises(ValueError):self.mission([file])
    def test_auto_selection_skips_private_files(self):
        (self.project/'.env').write_text('never inspect')
        (self.project/'secret.txt').write_text('never inspect')
        m=self.completed();report=json.loads(self.report(m).read_text())
        self.assertEqual([x['file'] for x in report['files']],['README.md'])
        self.assertNotIn('never inspect',self.report(m).read_text())
    def test_explicit_code_read_does_not_execute_code(self):
        m=self.mission(['app.py']);m=self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(m['lifecycle']['phase'],'COMPLETE');self.assertFalse(json.loads(self.report(m).read_text())['host_code_executed'])
    def test_file_byte_budget(self):
        (self.project/'big.txt').write_bytes(b'x'*65537);m=self.mission(['big.txt']);m=self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertIn('file_byte_budget',m['plan']['binding_error'])
    def test_total_byte_budget(self):
        files=[]
        for n in range(5):
            name=f'file{n}.txt';(self.project/name).write_bytes(b'x'*65536);files.append(name)
        m=self.mission(files);m=self.rt.brain.run(m['identity']['mission_id']);self.assertEqual(m['lifecycle']['phase'],'PAUSED')
        self.assertIn('total_byte_budget',m['plan']['binding_error'])
    def test_file_count_and_duplicates(self):
        for files in [['a.txt']*2,[f'{n}.txt' for n in range(9)]]:
            with self.assertRaises(ValueError):self.mission(files)
    def test_directory_budget(self):
        for n in range(199):(self.project/f'{n}.txt').touch()
        m=self.mission([]);m=self.rt.brain.run(m['identity']['mission_id']);self.assertEqual(m['lifecycle']['phase'],'PAUSED')
    def test_empty_project_valid_inventory(self):
        (self.project/'README.md').unlink();(self.project/'app.py').unlink()
        m=self.completed();self.assertEqual(m['verification']['status'],'PASS');self.assertEqual(json.loads(self.report(m).read_text())['files'],[])
    def test_binding_digest_tampering_rejected(self):
        m=self.ready(self.mission());m['plan']['steps'][0]['binding']['project_path']='other';self.rt.missions.save(m)
        out=self.rt.brain.step(m['identity']['mission_id']);self.assertEqual(out['lifecycle']['phase'],'FAILED');self.assertFalse(out['execution']['artifacts'])
    def test_source_change_before_execution_requires_replan(self):
        m=self.ready(self.mission());(self.project/'README.md').write_text('changed')
        out=self.rt.brain.step(m['identity']['mission_id']);self.assertEqual(out['lifecycle']['phase'],'FAILED')
        self.assertIn('binding_changed',out['execution']['errors'][0])
    def test_no_silent_filesystem_allowlist_bypass(self):
        m=self.ready(self.mission());m['routing']['route']['tools']=[];self.rt.missions.save(m)
        out=self.rt.brain.step(m['identity']['mission_id']);self.assertEqual(out['lifecycle']['phase'],'FAILED')
    def test_verification_rejects_report_tampering(self):
        m=self.completed();self.tamper_report(m,lambda r:r.update(project_path='other'))
        self.assertEqual(self.rt.verifier.verify(m)['status'],'FAIL')
    def test_verification_checks_source_even_if_report_hash_updated(self):
        m=self.completed();self.tamper_report(m,lambda r:r['files'][0].update(sha256='a'*64),True)
        self.assertEqual(self.rt.verifier.verify(m)['status'],'FAIL')
    def test_source_change_after_execution_fails_verification(self):
        m=self.ready(self.mission());self.rt.brain.step(m['identity']['mission_id']);m=self.rt.missions.load(m['identity']['mission_id'])
        (self.project/'README.md').write_text('changed');self.assertEqual(self.rt.verifier.verify(m)['status'],'FAIL')
    def test_fake_artifact_exists_not_sufficient(self):
        m=self.ready(self.mission());fake=self.rt.control.workspace/m['identity']['mission_id']/'inspection.json';fake.parent.mkdir();fake.write_text('{}')
        m['execution']['artifacts']=[self.rt.artifacts.register(m['identity']['mission_id'],fake)]
        self.assertEqual(self.rt.verifier.verify(m)['status'],'FAIL')
    def test_inputs_locked_after_execution(self):
        m=self.completed()
        with self.assertRaises(ValueError):self.rt.brain.set_inputs(m['identity']['mission_id'],{'project_path':'other'})
    def test_unknown_control_action_fails_closed(self):
        m=self.mission();out=self.rt.control.execute(m,{'action':'execute_unsupported_workflow'})
        self.assertEqual(out['status'],'failed');self.assertFalse(out['artifacts'])
    def test_bounded_read_and_hash_limits(self):
        mid=self.mission()['identity']['mission_id']
        for operation in ['read_text','sha256']:
            with self.assertRaises(RuntimeError):self.rt.filesystem_tool.execute(mid,operation,{'path':'demo/README.md','max_bytes':2})
    def test_cli_inputs_and_run(self):
        common=['--root',self.tmp.name,'--architecture',str(ARCH)]
        with patch('builtins.print') as output:
            self.assertEqual(main(common+['new-mission','--intent','Analysiere dieses Projekt','--project-path','demo']),0)
            mid=output.call_args.args[0]
            self.assertEqual(main(common+['run',mid]),0)
        self.assertEqual(self.rt.missions.load(mid)['lifecycle']['phase'],'COMPLETE')
    def test_mixed_change_mission_does_not_complete_with_inventory(self):
        m=self.rt.brain.create_mission('Analysiere dieses Projekt und implementiere ein Feature',inputs={'project_path':'demo'})
        m=self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(m['lifecycle']['phase'],'PAUSED');self.assertIn('required',m['plan']['binding_error'])
    def test_unknown_input_keys_rejected(self):
        with self.assertRaises(ValueError):self.rt.brain.create_mission('Analysiere dieses Projekt',inputs={'project_path':'demo','command':['python','app.py']})
    def test_selected_file_symlink_rejected(self):
        try:(self.project/'link.py').symlink_to(self.project/'app.py')
        except OSError:self.skipTest('symlink unavailable')
        m=self.mission(['link.py']);m=self.rt.brain.run(m['identity']['mission_id']);self.assertEqual(m['lifecycle']['phase'],'PAUSED')
    def test_subdirectories_not_recursively_read(self):
        (self.project/'nested').mkdir();(self.project/'nested'/'private.txt').write_text('not automatically read')
        m=self.completed();report=json.loads(self.report(m).read_text())
        self.assertEqual([f['file'] for f in report['files']],['README.md'])
        self.assertTrue(any(e['name']=='nested' and e['type']=='dir' for e in report['entries']))
    def test_changed_during_read_is_rejected(self):
        m=self.ready(self.mission());original=self.rt.tools.execute
        def change(tool,mid,operation,args=None,approval_token=None):
            if operation=='read_text':(self.project/'README.md').write_text('changed during read')
            return original(tool,mid,operation,args,approval_token)
        with patch.object(self.rt.tools,'execute',side_effect=change):out=self.rt.brain.step(m['identity']['mission_id'])
        self.assertEqual(out['lifecycle']['phase'],'FAILED');self.assertFalse(out['execution']['artifacts'])
    def test_guard_denial_stops_inspection(self):
        m=self.ready(self.mission());original=self.rt.guard.evaluate
        def deny(action,**kw):return {'decision':'BLOCK'} if action=='read_project_file' else original(action,**kw)
        with patch.object(self.rt.guard,'evaluate',side_effect=deny):out=self.rt.brain.step(m['identity']['mission_id'])
        self.assertEqual(out['lifecycle']['phase'],'PAUSED');self.assertEqual(out['lifecycle']['status'],'blocked');self.assertFalse(out['execution']['artifacts'])
    def test_report_overwrite_requires_captain(self):
        m=self.ready(self.mission());p=self.report(m);p.parent.mkdir();p.write_text('existing')
        out=self.rt.brain.step(m['identity']['mission_id']);self.assertEqual(out['lifecycle']['phase'],'CAPTAIN_REVIEW')
        self.assertEqual(p.read_text(),'existing');token=self.rt.guard.approve(out['human_gates']['pending'][0])
        final=self.rt.brain.run(m['identity']['mission_id'],approval_token=token)
        self.assertEqual(final['verification']['status'],'PASS')
    def test_invalid_approval_does_not_loop_or_overwrite(self):
        m=self.ready(self.mission());p=self.report(m);p.parent.mkdir();p.write_text('existing')
        self.rt.brain.step(m['identity']['mission_id'])
        out=self.rt.brain.run(m['identity']['mission_id'],approval_token='invalid-token')
        self.assertEqual(out['lifecycle']['phase'],'CAPTAIN_REVIEW');self.assertEqual(p.read_text(),'existing')
