import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.candidate_lifecycle import discard
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH=sorted((Path(__file__).resolve().parents[2]/'architecture').glob('GUPPI_Architecture_v*'))[-1]


class JournalCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.rt=GuppiRuntime(self.root,ARCH)
    def ready(self,steps=None):
        m=self.rt.brain.create_mission('Create a report');mid=m['identity']['mission_id']
        self.rt.brain.run(mid,max_steps=4);m=self.rt.missions.load(mid)
        if steps is not None:m['plan']['steps']=steps
        m['plan']['acceptance_criteria']=[{'type':'artifact_exists','min_count':len(steps or [1])}]
        self.rt.missions.save(m);return m
    def two(self):
        return self.ready([{'id':'ONE','action':'create_text_artifact','content':'first'},
                           {'id':'TWO','action':'create_text_artifact','content':'second','depends_on':['ONE']}])
    def test_two_steps_complete_and_distinct_targets(self):
        m=self.two();out=self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(out['lifecycle']['phase'],'COMPLETE')
        self.assertEqual(out['execution']['step_journal']['cursor'],2)
        base=self.rt.control.workspace/m['identity']['mission_id']
        self.assertEqual((base/'ONE.txt').read_text(),'first');self.assertEqual((base/'TWO.txt').read_text(),'second')
    def test_restart_continues_second_step_without_rewrite(self):
        m=self.two();mid=m['identity']['mission_id'];self.rt.brain.step(mid)
        path=self.rt.control.workspace/mid/'ONE.txt';before=path.stat().st_mtime_ns
        restarted=GuppiRuntime(self.root,ARCH);out=restarted.brain.run(mid)
        self.assertEqual(out['lifecycle']['phase'],'COMPLETE');self.assertEqual(path.stat().st_mtime_ns,before)
        self.assertEqual(len(out['execution']['results']),2)
    def test_durable_completed_response_repairs_cursor(self):
        m=self.two();mid=m['identity']['mission_id'];out=self.rt.brain.step(mid)
        out['execution']['step_journal']['cursor']=0;self.rt.missions.save(out)
        out=self.rt.brain.run(mid);self.assertEqual(out['lifecycle']['phase'],'COMPLETE')
        self.assertEqual(len(out['execution']['results']),2)
    def test_cursor_cannot_skip_pending(self):
        m=self.two();mid=m['identity']['mission_id'];self.rt.brain.step(mid);m=self.rt.missions.load(mid)
        m['execution']['step_journal']['cursor']=2;self.rt.missions.save(m)
        out=self.rt.brain.run(mid);self.assertEqual(out['lifecycle']['phase'],'PAUSED')
        self.assertEqual(out['wait']['reason_code'],'cursor_skips_uncompleted_step')
    def test_changed_completed_artifact_blocks_next_step(self):
        m=self.two();mid=m['identity']['mission_id'];self.rt.brain.step(mid)
        (self.rt.control.workspace/mid/'ONE.txt').write_text('tampered')
        out=self.rt.brain.run(mid)
        self.assertEqual(out['wait']['reason_code'],'completed_artifact_changed')
        self.assertFalse((self.rt.control.workspace/mid/'TWO.txt').exists())
    def test_plan_change_after_checkpoint_stops(self):
        m=self.two();mid=m['identity']['mission_id'];self.rt.brain.step(mid);m=self.rt.missions.load(mid)
        m['plan']['steps'][1]['content']='tampered';self.rt.missions.save(m)
        out=self.rt.brain.run(mid);self.assertEqual(out['wait']['reason_code'],'plan_changed_after_checkpoint')
        self.assertFalse((self.rt.control.workspace/mid/'TWO.txt').exists())
    def test_invalid_dependencies_stopped(self):
        m=self.ready([{'id':'ONE','depends_on':['LATER']},{'id':'LATER'}])
        out=self.rt.brain.run(m['identity']['mission_id']);self.assertEqual(out['lifecycle']['phase'],'PAUSED')
        self.assertEqual(out['wait']['reason_code'],'dependencies_must_reference_earlier_steps')
    def test_duplicate_step_ids_stopped(self):
        m=self.ready([{'id':'ONE'},{'id':'ONE'}]);out=self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(out['wait']['reason_code'],'invalid_or_duplicate_step_id')
    def test_step_limit(self):
        m=self.ready([{'id':f'STEP-{i}'} for i in range(33)])
        self.assertEqual(self.rt.brain.run(m['identity']['mission_id'])['wait']['reason_code'],'plan_step_limit')
    def test_second_gate_does_not_repeat_first_step(self):
        m=self.two();mid=m['identity']['mission_id'];base=self.rt.control.workspace/mid;base.mkdir();(base/'TWO.txt').write_text('existing')
        out=self.rt.brain.run(mid);self.assertEqual(out['lifecycle']['phase'],'CAPTAIN_REVIEW')
        token=self.rt.guard.approve(out['human_gates']['pending'][-1]);before=(base/'ONE.txt').stat().st_mtime_ns
        out=self.rt.brain.run(mid,approval_token=token);self.assertEqual(out['lifecycle']['phase'],'COMPLETE')
        self.assertEqual((base/'ONE.txt').stat().st_mtime_ns,before)
    def test_saved_gate_restores_without_extra_dispatch(self):
        m=self.two();mid=m['identity']['mission_id'];base=self.rt.control.workspace/mid;base.mkdir();(base/'TWO.txt').write_text('existing')
        self.rt.brain.step(mid);transition=self.rt.missions.transition
        def interrupt(m,phase):
            if phase=='CAPTAIN_REVIEW':raise RuntimeError('before state transition')
            return transition(m,phase)
        with patch.object(self.rt.missions,'transition',side_effect=interrupt):
            with self.assertRaises(RuntimeError):self.rt.brain.step(mid)
        out=self.rt.brain.run(mid)
        self.assertEqual(out['lifecycle']['phase'],'CAPTAIN_REVIEW')
        self.assertEqual(out['execution']['step_journal']['steps'][1]['attempts'],1)
    def interrupted(self,action='create_text_artifact'):
        m=self.ready([{'id':'ONE','action':action}]);mid=m['identity']['mission_id']
        with patch.object(self.rt.bus,'send',side_effect=RuntimeError('simulated interruption')):
            with self.assertRaises(RuntimeError):self.rt.brain.step(mid)
        return self.rt.brain.run(mid)
    def test_unknown_outcome_never_replays(self):
        out=self.interrupted();self.assertEqual(out['lifecycle']['phase'],'PAUSED')
        self.assertEqual(out['wait']['reason_code'],'UNKNOWN_EXECUTION_OUTCOME')
        self.assertEqual(out['execution']['step_journal']['steps'][0]['status'],'RUNNING')
    def test_mutating_unknown_cannot_retry(self):
        out=self.interrupted()
        with self.assertRaises(ValueError):self.rt.brain.recover(out['identity']['mission_id'],'retry_readonly')
    def test_unknown_abort_requires_bound_captain(self):
        out=self.interrupted();mid=out['identity']['mission_id'];gate=self.rt.brain.recover(mid,'abort')['gate']
        token=self.rt.guard.approve(gate);out=self.rt.brain.recover(mid,'abort',token)
        self.assertEqual(out['mission']['lifecycle']['phase'],'FAILED')
        self.assertEqual(out['mission']['execution']['step_journal']['steps'][0]['status'],'ABORTED')
    def test_readonly_unknown_retry_requires_captain(self):
        out=self.interrupted('inspect_tools');mid=out['identity']['mission_id']
        gate=self.rt.brain.recover(mid,'retry_readonly')['gate'];token=self.rt.guard.approve(gate)
        self.rt.brain.recover(mid,'retry_readonly',token);out=self.rt.brain.run(mid,max_steps=1)
        self.assertEqual(out['lifecycle']['phase'],'VERIFY')
        self.assertEqual(out['execution']['step_journal']['steps'][0]['attempts'],2)
    def test_same_mission_concurrent_lock_rejects(self):
        m=self.ready();mid=m['identity']['mission_id']
        with self.rt.missions.execution_lock(mid):
            with self.assertRaises(RuntimeError):GuppiRuntime(self.root,ARCH).brain.step(mid)
    def test_actual_process_death_releases_lock_without_replay(self):
        m=self.ready();mid=m['identity']['mission_id']
        code='''
import os,sys
from pathlib import Path
from guppi_runtime.runtime import GuppiRuntime
rt=GuppiRuntime(Path(sys.argv[1]),Path(sys.argv[2]));send=rt.bus.send
def crash(msg):
 result=send(msg)
 if msg.type=='execution_request':os._exit(23)
 return result
rt.bus.send=crash
rt.brain.step(sys.argv[3])
'''
        p=subprocess.run([sys.executable,'-c',code,str(self.root),str(ARCH),mid],capture_output=True,text=True)
        self.assertEqual(p.returncode,23,p.stderr)
        path=self.rt.control.workspace/mid/'result.txt';before=path.stat().st_mtime_ns
        out=GuppiRuntime(self.root,ARCH).brain.run(mid)
        self.assertEqual(out['wait']['reason_code'],'UNKNOWN_EXECUTION_OUTCOME')
        self.assertEqual(path.stat().st_mtime_ns,before)
    def test_verifier_fail_does_not_replay_successful_step(self):
        m=self.ready();mid=m['identity']['mission_id'];self.rt.brain.step(mid)
        with patch.object(self.rt.verifier,'verify',return_value={'status':'FAIL','findings':['x'],'evidence':[]}):self.rt.brain.step(mid)
        out=self.rt.brain.run(mid)
        # Since 2026-10-02 the new execution is a Captain gate (the contract STEP_RECOVERY v1.15 asked for) instead of a dead end.
        # Without it nothing replays: same journal, one result, the gate is pending.
        self.assertEqual((out['lifecycle']['phase'],out['lifecycle']['status']),('REWORK','waiting_captain'))
        self.assertEqual([g['request']['exact_action'] for g in out['human_gates']['pending']],['execution_recovery'])
        self.assertEqual(len(out['execution']['results']),1);self.assertIsNotNone(out['execution']['step_journal'])
        self.assertEqual(self.rt.brain.run(mid)['execution']['results'],out['execution']['results'])   # asking again changes nothing
    def test_tool_sequence_gate_resumes_index(self):
        fs=self.rt.filesystem_tool.root;(fs/'existing').write_text('old')
        steps=[{'id':'A','tool':'filesystem','operation':'write_text','args':{'path':'new','content':'first'}},
               {'id':'B','tool':'filesystem','operation':'write_text','args':{'path':'existing','content':'second'}}]
        m=self.ready([{'id':'SEQ','action':'tool_sequence','steps':steps}]);mid=m['identity']['mission_id']
        m['routing']['route']['tools']=[{'id':'filesystem'}];self.rt.missions.save(m)
        out=self.rt.brain.run(mid);self.assertEqual(out['lifecycle']['phase'],'CAPTAIN_REVIEW')
        before=(fs/'new').stat().st_mtime_ns;token=self.rt.guard.approve(out['human_gates']['pending'][-1])
        out=self.rt.brain.run(mid,max_steps=1,approval_token=token)
        # One loop step resumes the review; the following step performs the sequence.
        out=self.rt.brain.run(mid,max_steps=1,approval_token=token)
        self.assertEqual(out['lifecycle']['phase'],'VERIFY');self.assertEqual((fs/'new').stat().st_mtime_ns,before)


class CandidateLifecycleCase(unittest.TestCase):
    def setUp(self):
        import hashlib
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.rt=GuppiRuntime(self.root,ARCH)
        self.source=self.rt.filesystem_tool.root/'demo';self.source.mkdir();(self.source/'app.py').write_bytes(b'x=1\n')  # bytes: write_text would store CRLF on Windows and break the expected hash
        req={'project_path':'demo','files':['app.py'],'changes':[{'path':'app.py','expected_sha256':hashlib.sha256(b'x=1\n').hexdigest(),'content':'x=2\n'}]}
        self.m=self.rt.brain.create_mission('Ändere Code als Kandidat',inputs=req);self.mid=self.m['identity']['mission_id']
    def test_candidate_known_file_gate_reuses_stage(self):
        evaluate=self.rt.guard.evaluate
        def policy(action,**kw):
            if action=='create_new_artifact' and kw.get('target','').replace('\\','/').endswith('/app.py'):return {'decision':'CAPTAIN_REQUIRED'}
            return evaluate(action,**kw)
        with patch.object(self.rt.guard,'evaluate',side_effect=policy):
            out=self.rt.brain.run(self.mid);stage=out['execution']['candidate_attempts'][0]['stage']
            token=self.rt.guard.approve(out['human_gates']['pending'][-1]);out=self.rt.brain.run(self.mid,approval_token=token)
        self.assertEqual(out['lifecycle']['phase'],'CANDIDATE_REVIEW')
        self.assertEqual(out['execution']['candidate_attempts'][0]['stage'],stage)
        self.assertEqual(len(out['execution']['candidate_attempts']),1)
    def test_candidate_report_gate_reuses_report(self):
        self.rt.brain.run(self.mid,max_steps=4);p=self.rt.control.workspace/self.mid/'candidate-report.json';p.parent.mkdir();p.write_text('existing')
        out=self.rt.brain.run(self.mid);token=self.rt.guard.approve(out['human_gates']['pending'][-1])
        stage=out['execution']['candidate_attempts'][0]['stage'];out=self.rt.brain.run(self.mid,approval_token=token)
        self.assertEqual(out['lifecycle']['phase'],'CANDIDATE_REVIEW');self.assertEqual(out['execution']['candidate_attempts'][0]['stage'],stage)
    def broken(self):
        call=self.rt.control._tool_call
        def stop(mid,request,*args,**kwargs):
            if request.get('operation')=='write_text':return {'status':'failed','error':'injected','artifacts':[]}
            return call(mid,request,*args,**kwargs)
        with patch.object(self.rt.control,'_tool_call',side_effect=stop):out=self.rt.brain.run(self.mid)
        self.assertEqual(out['lifecycle']['phase'],'FAILED');return out
    def test_partial_cleanup_requires_gate_and_preserves_source(self):
        m=self.broken();record=m['execution']['candidate_attempts'][0]
        out=discard(self.rt.control,m,record['attempt_id']);self.assertEqual(out['status'],'captain_required')
        token=self.rt.guard.approve(out['gate']);m=self.rt.missions.load(self.mid)
        out=discard(self.rt.control,m,record['attempt_id'],token);self.assertEqual(out['status'],'completed')
        self.assertFalse((self.rt.filesystem_tool.root/record['stage']).exists());self.assertEqual((self.source/'app.py').read_text(),'x=1\n')
    def test_cleanup_cannot_target_source(self):
        m=self.broken();r=m['execution']['candidate_attempts'][0];r['stage']='demo'
        with self.assertRaises(ValueError):discard(self.rt.control,m,r['attempt_id'])
    def test_completed_candidate_not_cleanup_target(self):
        m=self.rt.brain.run(self.mid);r=m['execution']['candidate_attempts'][0]
        with self.assertRaises(ValueError):discard(self.rt.control,m,r['attempt_id'])
    def test_changed_stage_after_cleanup_approval_requires_new_gate(self):
        m=self.broken();r=m['execution']['candidate_attempts'][0];out=discard(self.rt.control,m,r['attempt_id']);token=self.rt.guard.approve(out['gate'])
        (self.rt.filesystem_tool.root/r['stage']/'added').write_text('new')
        out=discard(self.rt.control,m,r['attempt_id'],token);self.assertEqual(out['status'],'captain_required')
    def test_tampered_staged_file_not_overwritten_on_resume(self):
        self.rt.brain.run(self.mid,max_steps=4);p=self.rt.control.workspace/self.mid/'candidate-report.json';p.parent.mkdir();p.write_text('existing')
        m=self.rt.brain.run(self.mid);token=self.rt.guard.approve(m['human_gates']['pending'][-1]);r=m['execution']['candidate_attempts'][0]
        path=self.rt.filesystem_tool.root/r['stage']/'app.py';path.write_text('tampered')
        out=self.rt.brain.run(self.mid,approval_token=token)
        self.assertEqual(out['lifecycle']['phase'],'FAILED');self.assertEqual(path.read_text(),'tampered')
        self.assertEqual((self.source/'app.py').read_text(),'x=1\n')
    def test_cleanup_foreign_mission_stage_rejected(self):
        m=self.broken();r=m['execution']['candidate_attempts'][0];r['stage']=r['stage'].replace(self.mid,'M-00000000')
        with self.assertRaises(ValueError):discard(self.rt.control,m,r['attempt_id'])


class ManualPlanCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.rt=GuppiRuntime(self.root,ARCH)
        self.plan={'steps':[{'id':'ONE','content':'one'},{'id':'TWO','content':'two','depends_on':['ONE']}]}
    def test_public_plan_interface_completes(self):
        m=self.rt.brain.create_mission('Create two documents',plan_request=self.plan)
        out=self.rt.brain.run(m['identity']['mission_id'])
        self.assertEqual(out['lifecycle']['phase'],'COMPLETE');self.assertEqual(out['result']['qualification'],'ARTIFACT_ONLY')
        self.assertEqual(out['execution']['step_journal']['cursor'],2)
    def test_public_plan_restart_keeps_completed_step(self):
        m=self.rt.brain.create_mission('Create two documents',plan_request=self.plan);mid=m['identity']['mission_id']
        self.rt.brain.run(mid,max_steps=5);p=self.rt.control.workspace/mid/'ONE.txt';before=p.stat().st_mtime_ns
        out=GuppiRuntime(self.root,ARCH).brain.run(mid)
        self.assertEqual(out['lifecycle']['phase'],'COMPLETE');self.assertEqual(p.stat().st_mtime_ns,before)
    def test_manual_plan_cannot_grant_tool_permissions(self):
        self.plan['steps'][0]['action']='tool_call'
        with self.assertRaises(ValueError):self.rt.brain.create_mission('x',plan_request=self.plan)
    def test_duplicate_targets_rejected(self):
        self.plan['steps'][0]['target']='same.txt';self.plan['steps'][1]['target']='SAME.txt'
        with self.assertRaises(ValueError):self.rt.brain.create_mission('x',plan_request=self.plan)
    def test_path_escape_rejected(self):
        self.plan['steps'][0]['target']='../source.txt'
        with self.assertRaises(ValueError):self.rt.brain.create_mission('x',plan_request=self.plan)
    def test_manual_plan_content_budget(self):
        self.plan['steps'][0]['content']='a'*65537
        with self.assertRaises(ValueError):self.rt.brain.create_mission('x',plan_request=self.plan)
