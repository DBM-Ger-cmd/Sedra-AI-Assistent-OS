from copy import deepcopy
import hashlib
from unittest.mock import patch
import unittest
import test_sandbox
import test_code_candidate
from guppi_runtime.selfdev.candidate_tests import run_candidate_tests, verify_candidate_tests
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests


class EvidenceCase(unittest.TestCase):
    setUp = test_sandbox.SandboxCase.setUp
    tearDown = test_sandbox.SandboxCase.tearDown
    plan = test_sandbox.SandboxCase.plan
    approve_and_run = test_sandbox.SandboxCase.approve_and_run
    def test_invalid_pass_claims_are_rejected(self):
        valid={'status':'PASS','cleanup_confirmed':True,'commands':[{'argv':self.args['commands'][0], 'exit_code':0,'success':True,'output':''}],
               'exports':[{'path':'example.py','data_base64':'eA=='}]}
        changes=[{'commands':[]},{'commands':valid['commands']*2},{'error':'failed'},
                 {'commands':[dict(valid['commands'][0],argv=['different'])]},
                 {'commands':[dict(valid['commands'][0],exit_code=False)]},
                 {'commands':[dict(valid['commands'][0],exit_code=1)]},
                 {'commands':[dict(valid['commands'][0],success=False)]},
                 {'commands':[dict(valid['commands'][0],output=None)]},
                 {'commands':[dict(valid['commands'][0],output='x'*100000)]}]
        for change in changes:
            self.fake.response=dict(deepcopy(valid),**change)
            with self.subTest(change=str(change)[:100]):
                self.assertEqual(self.approve_and_run()['status'],'failed')
        self.assertFalse(list(self.broker.data_root.glob('jobs/*/candidate')))

    def test_false_cleanup_overrides_pass(self):
        self.fake.response={'status':'PASS','cleanup_confirmed':False,'commands':[],'exports':[]}
        out=self.approve_and_run();self.assertEqual(out['status'],'failed')
        self.assertEqual(out['sandbox']['status'],'CLEANUP_UNCONFIRMED')
        self.assertTrue((self.broker.data_root/'active.lock').exists())

    def receipt_args(self):
        record=self.approve_and_run()['sandbox']
        return {'job_id':record['job_id'],'report_sha256':hashlib.sha256(self.broker.receipt(record['job_id'])).hexdigest(),'plan_digest':record['plan']['plan_digest']}

    def test_independent_verification_and_qualification(self):
        args=self.receipt_args();count=len(self.fake.calls)
        out=self.broker.verify('M-SBX',**args)
        self.assertEqual(out['verification'],'PASS');self.assertEqual(out['qualification'],'SIMULATED_INTERFACE')
        self.assertFalse(out['ready_for_merge']);self.assertEqual(len(self.fake.calls),count)
        self.assertEqual(self.broker.verify('M-OTHER',**args)['verification'],'FAIL')

    def test_report_and_export_tamper_rejected(self):
        args=self.receipt_args();job=self.broker.data_root/'jobs'/args['job_id']
        f=job/'candidate/example.py';old=f.read_bytes();f.write_text('tampered')
        self.assertEqual(self.broker.verify('M-SBX',**args)['verification'],'FAIL');f.write_bytes(old)
        (job/'candidate/extra.py').write_text('unexpected')
        self.assertEqual(self.broker.verify('M-SBX',**args)['verification'],'FAIL');(job/'candidate/extra.py').unlink()
        p=job/'report.json';p.write_bytes(p.read_bytes()+b' ')
        self.assertEqual(self.broker.verify('M-SBX',**args)['verification'],'FAIL')

    def test_source_drift_invalidates_test(self):
        args=self.receipt_args();(self.source/'example.py').write_text('different')
        self.assertEqual(self.broker.verify('M-SBX',**args)['verification'],'FAIL')

    def test_bounded_directory_inventory(self):
        import yaml
        p=yaml.safe_load(self.cfg.read_text());p['sandbox']['max_files']=1;self.cfg.write_text(yaml.safe_dump(p))
        for i in range(9):(self.source/f'dir{i}').mkdir()
        from guppi_runtime.tools.base import ToolValidationError
        with self.assertRaises(ToolValidationError):self.plan()

    def test_bad_job_id_never_reads_outside(self):
        out=self.broker.verify('M-SBX','../../x','x','x');self.assertEqual(out['verification'],'FAIL')


class CandidateTestCase(unittest.TestCase):
    setUp = test_code_candidate.CandidateCase.setUp
    mission = test_code_candidate.CandidateCase.mission
    prepared = test_code_candidate.CandidateCase.prepared
    def prepare_tests(self):
        req=deepcopy(self.request);req['test_commands']=[['python3','-m','unittest','discover']]
        return self.prepared(req)

    def install_fake(self):
        from test_sandbox import FakeProvider
        import yaml
        self.fake=FakeProvider();self.rt.sandbox.provider=self.fake
        p=self.rt.sandbox.policy();p['target_qualified']=True;p['image']='test/image@sha256:'+'a'*64
        self.rt.sandbox.config_path=self.project.parent/'test-sandbox.yaml'
        self.rt.sandbox.config_path.write_text(yaml.safe_dump({'sandbox':p}))
        # This fake is test evidence only, never VM boundary qualification.
        def execute(request,job):
            self.fake.calls.append(request)
            return {'status':'PASS','cleanup_confirmed':True,'commands':[{'argv':x,'exit_code':0,'success':True,'output':''} for x in request['commands']], 'exports':[]}
        self.fake.execute=execute

    def approved_run(self,mid):
        gate=run_candidate_tests(self.rt,mid)['gate'];token=self.rt.guard.approve(gate)
        m=self.rt.missions.load(mid);m['execution']['approval_token']=token;self.rt.missions.save(m)
        return run_candidate_tests(self.rt,mid)

    def test_unavailable_vm_blocks_without_execution(self):
        m=self.prepare_tests();mid=m['identity']['mission_id']
        with patch.object(self.rt.sandbox_provider,'execute') as execute:
            out=run_candidate_tests(self.rt,mid);execute.assert_not_called()
        self.assertEqual(out['status'],'blocked');self.assertEqual(out['attempt']['status'],'WAITING')

    def test_candidate_without_tests_has_no_execution(self):
        mid=self.prepared()['identity']['mission_id']
        self.assertEqual(run_candidate_tests(self.rt,mid)['reason'],'bound_test_commands_required')

    def test_success_is_bound_and_never_repeated(self):
        self.install_fake();mid=self.prepare_tests()['identity']['mission_id']
        out=self.approved_run(mid);self.assertEqual(out['attempt']['status'],'FINISHED')
        self.assertEqual(verify_candidate_tests(self.rt,mid)['qualification'],'SIMULATED_INTERFACE')
        self.assertTrue(run_candidate_tests(self.rt,mid)['reused']);self.assertEqual(len(self.fake.calls),1)
        self.assertEqual((self.project/'app.py').read_bytes(),self.old.encode())
        self.assertEqual(self.rt.missions.load(mid)['lifecycle']['phase'],'CANDIDATE_REVIEW')
        self.assertFalse(out['ready_for_merge'])

    def test_interrupted_dispatch_stays_unknown_without_retry(self):
        self.install_fake();mid=self.prepare_tests()['identity']['mission_id']
        original=self.rt.sandbox.execute
        def interrupt(mid,operation,*args,**kwargs):
            if operation=='run': raise KeyboardInterrupt
            return original(mid,operation,*args,**kwargs)
        with patch.object(self.rt.sandbox,'execute',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):run_candidate_tests(self.rt,mid)
        out=run_candidate_tests(self.rt,mid);self.assertEqual(out['reason'],'UNKNOWN_TEST_OUTCOME');self.assertFalse(self.fake.calls)

    def test_candidate_drift_blocks_reverification(self):
        self.install_fake();mid=self.prepare_tests()['identity']['mission_id'];self.approved_run(mid)
        m=self.rt.missions.load(mid);stage=m['execution']['candidate_attempts'][0]['stage']
        (self.rt.filesystem_tool.root/stage/'app.py').write_text('changed')
        self.assertEqual(verify_candidate_tests(self.rt,mid)['status'],'failed')

    def test_changed_receipt_reuse_fails_without_rerun(self):
        self.install_fake();mid=self.prepare_tests()['identity']['mission_id'];out=self.approved_run(mid)
        p=self.rt.sandbox.report_path(out['attempt']['job_id']);p.write_bytes(p.read_bytes()+b' ')
        out=run_candidate_tests(self.rt,mid);self.assertEqual(out['status'],'failed');self.assertTrue(out['reused'])
        self.assertEqual(len(self.fake.calls),1)

    def test_repeated_gate_preserves_pending_binding(self):
        self.install_fake();mid=self.prepare_tests()['identity']['mission_id']
        self.assertEqual(run_candidate_tests(self.rt,mid)['status'],'captain_required')
        self.assertEqual(run_candidate_tests(self.rt,mid)['status'],'captain_required')
        mission=self.rt.missions.load(mid)
        self.assertEqual(len(mission['human_gates']['pending']),1);self.assertFalse(self.fake.calls)
