import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.guard import Guard
from guppi_runtime.feasibility import AdmissionUnavailable
from guppi_runtime.request_binding import path_state
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH=sorted((Path(__file__).resolve().parents[2]/'architecture').glob('GUPPI_Architecture_v*'))[-1]

class WorkflowCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.rt=GuppiRuntime(self.root,ARCH)
        self.m=self.rt.brain.create_mission('Create a report')
        self.mid=self.m['identity']['mission_id'];self.fs=self.rt.filesystem_tool
    def tearDown(self):self.tmp.cleanup()
    def pending_write(self):
        (self.fs.root/'a.txt').write_text('old')
        args={'path':'a.txt','content':'reviewed'}
        out=self.fs.execute(self.mid,'write_text',args)
        return args,self.rt.guard.approve(out['gate'])
    def test_changed_content_requires_new_gate(self):
        args,t=self.pending_write();args['content']='changed'
        out=self.fs.execute(self.mid,'write_text',args,t)
        self.assertEqual(out['status'],'captain_required')
        self.assertEqual((self.fs.root/'a.txt').read_text(),'old')
        self.assertEqual(t['status'],'active')
    def test_changed_source_requires_new_gate(self):
        args,t=self.pending_write();(self.fs.root/'a.txt').write_text('new source')
        self.assertEqual(self.fs.execute(self.mid,'write_text',args,t)['status'],'captain_required')
    def test_same_content_approved_once(self):
        args,t=self.pending_write()
        self.assertEqual(self.fs.execute(self.mid,'write_text',args,t)['status'],'completed')
        self.assertEqual(self.fs.execute(self.mid,'write_text',args,t)['status'],'captain_required')
    def test_legacy_token_cannot_grant_bound_write(self):
        args,_=self.pending_write()
        gate=self.rt.guard.create_gate(self.mid,'overwrite_existing',str(self.fs.root/'a.txt'))
        token=self.rt.guard.approve(gate)
        self.assertEqual(self.fs.execute(self.mid,'write_text',args,token)['status'],'captain_required')
    def test_scope_cannot_be_empty_or_expanded(self):
        g=self.rt.guard.create_gate(self.mid,'x','one')
        for scope in ([],['two'],['one','two']):
            with self.assertRaises(ValueError):self.rt.guard.approve(g,scope)
    def test_unscoped_gate_cannot_be_approved(self):
        with self.assertRaises(ValueError):self.rt.guard.approve(self.rt.guard.create_gate(self.mid,'x'))
    def test_token_consumption_across_instances(self):
        store=self.root/'tokens.json';rules=ARCH/'core/guard/guard_rules.yaml'
        first=Guard(rules,token_store_path=store);second=Guard(rules,token_store_path=store)
        token=first.approve(first.create_gate(self.mid,'x','one',request_binding={'version':1}))
        self.assertTrue(second.authorize(token,mission_id=self.mid,action='x',target='one',request_binding={'version':1})['authorized'])
        self.assertFalse(first.authorize(dict(token,status='active'),mission_id=self.mid,action='x',target='one',request_binding={'version':1})['authorized'])
    def test_two_threads_only_one_consumes(self):
        guard=self.rt.guard;g=guard.create_gate(self.mid,'x','one',request_binding={'v':1});t=guard.approve(g)
        results=[]
        def use():results.append(guard.authorize(dict(t),mission_id=self.mid,action='x',target='one',request_binding={'v':1})['authorized'])
        threads=[threading.Thread(target=use) for _ in range(2)]
        for th in threads:th.start()
        for th in threads:th.join()
        self.assertEqual(sum(results),1)
    def test_token_lock_fails_closed(self):
        from guppi_runtime.mission_lock import exclusive
        path=self.rt.guard.token_store_path.with_suffix('.lock')
        held=threading.Event();release=threading.Event()
        def holder():
            with exclusive(path):held.set();release.wait(10)
        th=threading.Thread(target=holder);th.start();held.wait(5)
        try:
            with self.assertRaises(RuntimeError):
                with self.rt.guard.token_transaction(wait_s=0.1):pass
        finally:release.set();th.join()
    def test_lock_file_left_by_a_crash_does_not_block_approvals(self):
        path=self.rt.guard.token_store_path.with_suffix('.lock');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('busy')
        token=self.rt.guard.approve(self.rt.guard.create_gate(self.mid,'x','one'))
        self.assertEqual(token['status'],'active')
    def test_copy_source_change_rejected(self):
        (self.fs.root/'source').write_text('a');(self.fs.root/'dest').write_text('b')
        args={'src':'source','dst':'dest'}
        token=self.rt.guard.approve(self.fs.execute(self.mid,'copy',args)['gate'])
        (self.fs.root/'source').write_text('c')
        self.assertEqual(self.fs.execute(self.mid,'copy',args,token)['status'],'captain_required')
    def test_delete_tree_change_rejected(self):
        d=self.fs.root/'tree';d.mkdir();(d/'one').write_text('a')
        args={'path':'tree','recursive':True}
        token=self.rt.guard.approve(self.fs.execute(self.mid,'delete',args)['gate'])
        (d/'two').write_text('b')
        self.assertEqual(self.fs.execute(self.mid,'delete',args,token)['status'],'captain_required')
    def test_artifact_content_change_rejected(self):
        req={'action':'create_text_artifact','content':'a'}
        self.rt.control.execute(self.m,req)
        req['content']='b';pending=self.rt.control.execute(self.m,req)
        token=self.rt.guard.approve(pending['gate']);req['content']='c'
        self.assertEqual(self.rt.control.execute(self.m,req,token)['status'],'captain_required')
    def test_objective_needs_bound_approval(self):
        with self.assertRaises(PermissionError):self.rt.missions.set_objective(self.m,'new')
        token=self.rt.guard.approve(self.rt.missions.objective_gate(self.m,'new'))
        with self.assertRaises(PermissionError):self.rt.missions.set_objective(self.m,'different',token)
        self.rt.missions.set_objective(self.m,'new',token)
        self.assertEqual(self.m['objective']['current'],'new')
    def test_objective_locked_after_planning(self):
        self.rt.brain.step(self.mid)
        with self.assertRaises(ValueError):self.rt.missions.objective_gate(self.rt.missions.load(self.mid),'new')
    def test_no_handler_is_unsupported(self):
        self.assertEqual(self.rt.control.check_execution(self.m,{'action':'merge'})['status'],'UNSUPPORTED')
    def test_cloud_only_is_unsupported(self):
        out=self.rt.control.check_execution(self.m,{'execution_requirements':{'allowed_execution_locations':['cloud']}})
        self.assertEqual(out['reason_code'],'CLOUD_NOT_IMPLEMENTED')
    def test_context_requirement_not_silently_reduced(self):
        out=self.rt.control.check_execution(self.m,{'execution_requirements':{'context_min_tokens':24000}})
        self.assertEqual(out['status'],'UNSUPPORTED')
    def test_unknown_requirements_fail_closed(self):
        for req in (None,{'cloud_allowed':True},{'data_class':'anything'}):
            self.assertNotEqual(self.rt.control.check_execution(self.m,{'execution_requirements':req})['status'],'EXECUTABLE')
    def test_feasibility_has_no_reservation_or_authorization(self):
        out=self.rt.control.check_execution(self.m,{'action':'create_text_artifact'})
        self.assertEqual(out['status'],'EXECUTABLE');self.assertFalse(out['reservation']);self.assertFalse(out['authorization'])
        self.assertIn('expires_at',out);self.assertEqual(len(out['request_digest']),64)
    def model_plan(self):
        m=self.rt.brain.run(self.mid,max_steps=4)
        m['plan']['steps']=[{'id':'STEP-1','action':'model_inference','messages':[{'role':'user','content':'hello'}]}]
        self.rt.missions.save(m)
    def test_resource_wait_does_not_fail(self):
        self.model_plan()
        with patch.object(self.rt.hardware_manager,'preflight',side_effect=AdmissionUnavailable('JOB_LIMIT')):
            out=self.rt.brain.run(self.mid)
        self.assertEqual(out['lifecycle']['phase'],'PAUSED');self.assertEqual(out['lifecycle']['status'],'waiting')
        self.assertEqual(out['execution']['results'],[])
        self.assertEqual(out['wait']['reason_code'],'JOB_LIMIT')
    def test_resume_rechecks_and_is_bounded(self):
        self.model_plan()
        with patch.object(self.rt.hardware_manager,'preflight',side_effect=AdmissionUnavailable('JOB_LIMIT')) as check:
            self.rt.brain.run(self.mid)
            for _ in range(3):self.rt.brain.resume(self.mid);self.rt.brain.run(self.mid)
            with self.assertRaises(ValueError):self.rt.brain.resume(self.mid)
        self.assertEqual(check.call_count,4)
    def test_resume_success_clears_wait(self):
        self.model_plan()
        with patch.object(self.rt.hardware_manager,'preflight',side_effect=AdmissionUnavailable('JOB_LIMIT')):self.rt.brain.run(self.mid)
        self.rt.brain.resume(self.mid)
        with patch.object(self.rt.control,'check_execution',return_value={'status':'EXECUTABLE','reason_code':'OK'}),patch.object(self.rt.control,'_model_inference',return_value={'status':'completed','artifacts':[]}):
            out=self.rt.brain.run(self.mid,max_steps=1)
        self.assertEqual(out['lifecycle']['phase'],'VERIFY');self.assertIsNone(out['wait'])
    def test_blocked_requirement_not_resumable_as_resource(self):
        m=self.rt.brain.run(self.mid,max_steps=4)
        m['plan']['execution_requirements']={'allowed_execution_locations':['cloud']};self.rt.missions.save(m)
        out=self.rt.brain.run(self.mid)
        self.assertEqual(out['lifecycle']['status'],'blocked')
        with self.assertRaises(ValueError):self.rt.brain.resume(self.mid)
    def test_artifact_result_explicitly_limited(self):
        out=self.rt.brain.run(self.mid)
        self.assertEqual(out['result']['qualification'],'ARTIFACT_ONLY');self.assertFalse(out['result']['accepted'])
    def test_provider_missing_no_chat(self):
        with patch.object(self.rt.model_router,'choose',side_effect=RuntimeError('missing')),patch.object(self.rt.hardware_manager,'preflight',return_value={}):
            out=self.rt.control.check_execution(self.m,{'action':'model_inference'})
        self.assertEqual(out['status'],'NOT_NOW');self.assertEqual(out['reason_code'],'PROVIDER_UNAVAILABLE')
    def test_binding_rejects_symlink(self):
        p=self.root/'link'
        try:p.symlink_to(self.fs.root)
        except OSError as exc:self.skipTest(f'symlink creation not permitted on this host: {exc}')
        with self.assertRaises(ValueError):path_state(p)

    def test_inspect_tools_respects_explicit_constraints(self):
        out=self.rt.control.execute(self.m,{'action':'inspect_tools','execution_requirements':{'allowed_execution_locations':['cloud']}})
        self.assertEqual(out['status'],'blocked')
    def test_plan_revision_change_requires_new_artifact_gate(self):
        req={'action':'create_text_artifact','content':'original'}
        self.rt.control.execute(self.m,req)
        req['content']='reviewed'
        pending=self.rt.control.execute(self.m,req);token=self.rt.guard.approve(pending['gate'])
        self.m['plan_revision']=1
        self.assertEqual(self.rt.control.execute(self.m,req,token)['status'],'captain_required')
    def test_race_after_check_pauses_without_replaying_completion(self):
        self.model_plan()
        with patch.object(self.rt.control,'check_execution',return_value={'status':'EXECUTABLE','reason_code':'OK'}),patch.object(self.rt.control,'_model_inference',return_value={'status':'waiting','reason_code':'JOB_LIMIT','artifacts':[]}):
            out=self.rt.brain.run(self.mid)
        self.assertEqual(out['lifecycle']['phase'],'PAUSED');self.assertEqual(out['wait']['status'],'NOT_NOW')
        self.assertEqual(out['wait']['reason_code'],'JOB_LIMIT')
