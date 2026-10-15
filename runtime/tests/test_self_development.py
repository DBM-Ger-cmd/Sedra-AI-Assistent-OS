import io
import json
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.context_budget import ContextBudgetManager
from guppi_runtime.development_evidence import DevelopmentEvidenceStore
from guppi_runtime.kev import KevVerificationProvider
from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'


class SelfDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.rt = GuppiRuntime(self.root, ARCH)

    def test_capability_admission_reuses_existing(self):
        out = self.rt.self_development.admission.evaluate(
            'code_editing', evidence=[{'source':'captain','claim':'need code editing'}],
            target_type='skill', checked={'skills':True,'tools':True,'modules':True})
        self.assertEqual(out['status'], 'REUSE_EXISTING')

    def test_capability_admission_requires_complete_checks(self):
        out = self.rt.self_development.admission.evaluate(
            'novel_local_capability', evidence=[{'source':'test'}], target_type='skill',
            checked={'skills':True,'tools':True,'modules':False})
        self.assertEqual(out['status'], 'BLOCK')
        self.assertEqual(out['reason'], 'existing_capability_checks_incomplete')

    def test_new_tool_requires_rationale(self):
        out = self.rt.self_development.admission.evaluate(
            'novel_local_capability', evidence=[{'source':'test'}], target_type='skill',
            checked={'skills':True,'tools':True,'modules':True}, requires_new_tool=True,
            new_tool_rationale='short')
        self.assertEqual(out['status'], 'BLOCK')

    def test_phase1_contract_and_context_budget(self):
        out = self.rt.self_development.start(
            'self_dev_example', evidence=[{'source':'test','failure':'missing'}], target_type='skill',
            acceptance_criteria=[{'type':'capability_smoke_test','id':'smoke'}],
            verification_plan=[{'type':'deterministic_tests'},{'type':'independent_review'}],
            context_window=8192)
        self.assertEqual(out['status'], 'ADMITTED')
        job = self.rt.self_development.jobs.load(out['job']['job_id'])
        self.assertEqual(job['state'], 'PLANNING')
        self.assertEqual(job['contract']['classification'], 'E1')
        self.assertLess(job['context_manifest']['budget']['max_input_tokens'], 8192)
        self.assertEqual(len(job['contract']['contract_digest']), 64)

    def test_context_watermarks(self):
        mgr = ContextBudgetManager(); budget = mgr.build_budget(8192)
        self.assertEqual(mgr.health(100, budget)['state'], 'GREEN')
        red = mgr.health(budget['max_input_tokens'], budget)
        self.assertEqual(red['state'], 'RED')
        self.assertIn('context_rebuild', red['actions'])

    def test_evidence_chain_detects_tamper(self):
        store = DevelopmentEvidenceStore(self.root/'evidence.jsonl')
        store.add('baseline_test', payload={'status':'FAIL'}, trust_level='deterministic')
        store.add('candidate_test', payload={'status':'PASS'}, trust_level='deterministic')
        self.assertTrue(store.verify_chain())
        lines=(self.root/'evidence.jsonl').read_text().splitlines(); value=json.loads(lines[0]); value['payload']['status']='PASS'; lines[0]=json.dumps(value)
        (self.root/'evidence.jsonl').write_text('\n'.join(lines)+'\n')
        self.assertFalse(store.verify_chain())

    def _ready_job(self, target_type='skill', capability='new_cap'):
        out=self.rt.self_development.start(capability,evidence=[{'source':'test'}],target_type=target_type)
        jid=out['job']['job_id']
        self.rt.self_development.prepare_development_environment(jid, {'execution_ready':True})
        self.rt.self_development.assign_roles(jid,['planner','coder','tester','reviewer','verifier'])
        self.rt.self_development.bind_candidate(jid,attempt_id='attempt-1',stage=f'guppi-candidates/{jid}/project',parent_version='1.19.0',candidate_hash='a'*64,builder='coder')
        return jid

    def _evidence(self, jid, status='PASS', trust='deterministic', candidate=True):
        """Record test evidence for the job's current candidate and return its id."""
        cid = self.rt.self_development.jobs.load(jid)['candidate']['candidate_id'] if candidate else None
        return self.rt.development_evidence.add('candidate_tests', job_id=jid, candidate_id=cid,
                                                payload={'status': status}, trust_level=trust)['evidence_id']

    def _keyed_job(self, builder_key):
        out=self.rt.self_development.start('keyed_cap',evidence=[{'source':'test'}])
        jid=out['job']['job_id']; sd=self.rt.self_development
        sd.prepare_development_environment(jid,{'execution_ready':True})
        sd.bind_candidate(jid,attempt_id='a1',stage=f'guppi-candidates/{jid}/p',parent_version='1',candidate_hash='a'*64,builder='coder',builder_key=builder_key)
        return jid

    def test_actual_identities_decide_independence_not_the_current_resolution(self):
        sd=self.rt.self_development
        sd.independence_check=lambda b,v:'UNVERIFIABLE'           # e.g. the coder cannot resolve right now (GPU still busy)
        jid=self._keyed_job('gpt-oss:sha256:x')
        rec=sd.attach_verification(jid,verifier='verifier',result='PASS',evidence_refs=[self._evidence(jid)],verifier_key='gemma4:sha256:y')
        self.assertEqual(rec['result'],'PASS'); self.assertEqual(sd.jobs.load(jid)['state'],'READY_FOR_ACCEPTANCE')
        self.assertEqual(sd.jobs.load(jid)['verification_identities'],{'builder_key':'gpt-oss:sha256:x','verifier_key':'gemma4:sha256:y'})

    def test_same_actual_model_is_downgraded(self):
        sd=self.rt.self_development; sd.independence_check=lambda b,v:'INDEPENDENT'
        jid=self._keyed_job('gpt-oss:sha256:x')
        rec=sd.attach_verification(jid,verifier='verifier',result='PASS',evidence_refs=[self._evidence(jid)],verifier_key='gpt-oss:sha256:x')
        self.assertEqual(rec['result'],'INCONCLUSIVE'); self.assertIn('pass_downgraded:independence_same',rec['findings'])

    def test_without_both_keys_the_role_check_still_applies(self):
        sd=self.rt.self_development; sd.independence_check=lambda b,v:'UNVERIFIABLE'
        jid=self._keyed_job(None)
        rec=sd.attach_verification(jid,verifier='verifier',result='PASS',evidence_refs=[self._evidence(jid)],verifier_key='gemma4:sha256:y')
        self.assertEqual(rec['result'],'INCONCLUSIVE')

    def _mission_job(self, mid, verdict='PASS', builder_key='gpt-oss:k1', verifier_key='gemma4:k2'):
        sd=self.rt.self_development; sd.independence_check=None
        out=sd.start('acc_cap_'+mid[-4:].lower(),evidence=[{'source':'test'}]); jid=out['job']['job_id']
        sd.prepare_development_environment(jid,{'execution_ready':True})
        sd.bind_candidate(jid,attempt_id='a1',stage=f'guppi-candidates/{mid}',parent_version='1',candidate_hash='a'*64,builder='coder',builder_key=builder_key)
        refs=[self._evidence(jid,status='PASS' if verdict=='PASS' else 'FAIL')]
        sd.attach_verification(jid,verifier='verifier',result=verdict,evidence_refs=refs,verifier_key=verifier_key)
        return jid

    def test_job_is_found_by_its_candidate_stage(self):
        jid=self._mission_job('M-AAAA1111')
        self.assertEqual([j['job_id'] for j in self.rt.self_development.jobs_for_mission('M-AAAA1111')],[jid])
        self.assertEqual(self.rt.self_development.jobs_for_mission('M-OTHER000'),[])

    def test_acceptance_needs_a_ready_independent_pass(self):
        sd=self.rt.self_development
        ok=sd.jobs.load(self._mission_job('M-AAAA2222'))
        self.assertIsNone(sd.acceptance_refusal(ok))
        failed=sd.jobs.load(self._mission_job('M-AAAA3333',verdict='FAIL'))
        self.assertEqual(sd.acceptance_refusal(failed),'development_job_not_ready:REWORK')
        same=sd.jobs.load(self._mission_job('M-AAAA4444',verifier_key='gpt-oss:k1'))      # downgraded to INCONCLUSIVE -> BLOCKED
        self.assertEqual(sd.acceptance_refusal(same),'development_job_not_ready:BLOCKED')

    def test_activation_marks_follow_the_take_over(self):
        sd=self.rt.self_development; jid=self._mission_job('M-AAAA5555')
        self.assertEqual(sd.mark_activation(jid,'started'),'ACTIVATION_PENDING')
        self.assertEqual(sd.mark_activation(jid,'applied'),'ACTIVATED')
        self.assertEqual(sd.mark_activation(jid,'rolled_back'),'ROLLED_BACK')
        self.assertEqual([e['phase'] for e in sd.jobs.load(jid)['activation_log']],['started','applied','rolled_back'])

    def test_acceptance_preview_refuses_a_job_that_is_not_ready(self):
        from guppi_runtime.candidate_acceptance import preview
        self._mission_job('M-AAAA6666',verdict='FAIL')
        mission={'identity':{'mission_id':'M-AAAA6666'},'execution':{}}
        with self.assertRaises(ValueError) as ctx: preview(self.rt,mission,'accept')
        self.assertIn('development_job_not_ready',str(ctx.exception))

    def test_two_jobs_on_one_candidate_are_ambiguous(self):
        from guppi_runtime.candidate_acceptance import linked_job
        self._mission_job('M-AAAA7777'); self._mission_job('M-AAAA7777')
        with self.assertRaises(ValueError) as ctx: linked_job(self.rt,'M-AAAA7777')
        self.assertIn('ambiguous_development_jobs',str(ctx.exception))

    def test_a_reworked_candidate_is_a_new_build_and_can_pass(self):
        sd=self.rt.self_development; sd.independence_check=None
        jid=self._mission_job('M-BBBB1111',verdict='FAIL')
        self.assertEqual(sd.jobs.load(jid)['state'],'REWORK')
        sd.bind_candidate(jid,attempt_id='a2',stage='guppi-candidates/M-BBBB2222',parent_version='1',candidate_hash='b'*64,builder='coder',builder_key='gpt-oss:k1')
        self.assertEqual(sd.jobs.load(jid)['state'],'BUILDING')
        rec=sd.attach_verification(jid,verifier='verifier',result='PASS',evidence_refs=[self._evidence(jid)],verifier_key='gemma4:k2')
        self.assertEqual((rec['result'],sd.jobs.load(jid)['state']),('PASS','READY_FOR_ACCEPTANCE'))

    def test_refused_bind_leaves_the_job_state(self):
        out=self.rt.self_development.start('bind_cap',evidence=[{'source':'test'}]); jid=out['job']['job_id']
        self.rt.self_development.prepare_development_environment(jid,{'execution_ready':True})
        with self.assertRaises(ValueError):
            self.rt.self_development.bind_candidate(jid,attempt_id='a1',stage='candidate',parent_version='1',candidate_hash='a'*64)
        self.assertEqual(self.rt.self_development.jobs.load(jid)['state'],'READY')

    def test_independent_verifier_required(self):
        jid=self._ready_job()
        with self.assertRaises(ValueError):
            self.rt.self_development.attach_verification(jid,verifier='coder',result='PASS')

    def test_baseline_candidate_improvement_and_e1_activation_default_off(self):
        jid=self._ready_job()
        cmp=self.rt.self_development.compare(jid,{'tests':{'red':'FAIL','regression':'PASS'}},{'tests':{'red':'PASS','regression':'PASS'}})
        self.assertEqual(cmp['status'],'IMPROVED')
        self.rt.self_development.attach_verification(jid,verifier='verifier',result='PASS',confidence=0.9,evidence_refs=[self._evidence(jid)])
        decision=self.rt.self_development.activation_decision(jid)
        self.assertEqual(decision['status'],'READY_FOR_CAPTAIN')

    def test_regression_blocks_activation(self):
        jid=self._ready_job()
        self.rt.self_development.compare(jid,{'tests':{'reg':'PASS'}},{'tests':{'reg':'FAIL'}})
        self.rt.self_development.attach_verification(jid,verifier='verifier',result='PASS',evidence_refs=[self._evidence(jid)])
        self.assertEqual(self.rt.self_development.activation_decision(jid)['reason'],'regression_detected')

    def test_e3_never_auto_activates(self):
        jid=self._ready_job(target_type='guard', capability='core_guard_improvement')
        self.rt.self_development.compare(jid,{'tests':{'red':'FAIL'}},{'tests':{'red':'PASS'}})
        self.rt.self_development.attach_verification(jid,verifier='security_reviewer',result='PASS',evidence_refs=[self._evidence(jid)])
        decision=self.rt.self_development.activation_decision(jid,captain_approved=True)
        self.assertEqual(decision['status'],'CAPTAIN_REQUIRED')
        self.assertEqual(decision['reason'],'e3_auto_activation_forbidden')

    def test_capability_learning_never_auto_known_good(self):
        jid=self._ready_job(capability='learned_example')
        self.rt.self_development.compare(jid,{'tests':{'red':'FAIL'}},{'tests':{'red':'PASS'}})
        self.rt.self_development.attach_verification(jid,verifier='verifier',result='PASS',evidence_refs=[self._evidence(jid)])
        record=self.rt.self_development.record_capability_learning(jid)
        self.assertEqual(record['trust_level'],'candidate')
        self.assertEqual(self.rt.self_development.promote_learned_capability('learned_example')['status'],'CAPTAIN_REQUIRED')
        promoted=self.rt.self_development.promote_learned_capability('learned_example',captain_approved=True)
        self.assertEqual(promoted['record']['trust_level'],'KNOWN_GOOD')

    def _verify_claim(self, jid, refs):
        record = self.rt.self_development.attach_verification(jid, verifier='verifier', result='PASS', evidence_refs=refs)
        return record, self.rt.self_development.jobs.load(jid)

    def test_pass_without_evidence_is_downgraded_and_blocks_the_job(self):
        jid = self._ready_job()
        record, job = self._verify_claim(jid, None)
        self.assertEqual(record['result'], 'INCONCLUSIVE')
        self.assertIn('pass_downgraded:deterministic_test_evidence_required', record['findings'])
        self.assertEqual(job['state'], 'BLOCKED')
        self.assertEqual(self.rt.self_development.activation_decision(jid)['status'], 'BLOCK')
        with self.assertRaises(ValueError):
            self.rt.self_development.record_capability_learning(jid)

    def test_pass_with_invented_evidence_id_is_downgraded(self):
        record, job = self._verify_claim(self._ready_job(), ['EVD-1'])
        self.assertEqual(record['result'], 'INCONCLUSIVE')
        self.assertTrue(any(f.startswith('pass_downgraded:evidence_not_found_for_job') for f in record['findings']))

    def test_model_assessment_alone_never_proves_pass(self):
        jid = self._ready_job()
        record, job = self._verify_claim(jid, [self._evidence(jid, trust='model_assessment')])
        self.assertEqual(record['result'], 'INCONCLUSIVE')
        self.assertTrue(any('evidence_not_deterministic' in f for f in record['findings']))

    def test_failing_deterministic_evidence_vetoes_pass(self):
        jid = self._ready_job()
        good, bad = self._evidence(jid), self._evidence(jid, status='FAIL')
        record, _ = self._verify_claim(jid, [good, bad])
        self.assertEqual(record['result'], 'INCONCLUSIVE')
        self.assertTrue(any('deterministic_evidence_not_passing' in f for f in record['findings']))

    def test_evidence_of_another_candidate_or_job_does_not_count(self):
        jid = self._ready_job(capability='cap_one')
        other = self._ready_job(capability='cap_two')
        unbound = self._evidence(jid, candidate=False)
        record, _ = self._verify_claim(jid, [unbound, self._evidence(other)])
        self.assertEqual(record['result'], 'INCONCLUSIVE')
        joined = ' '.join(record['findings'])
        self.assertIn('evidence_not_bound_to_candidate', joined)
        self.assertIn('evidence_not_found_for_job', joined)

    def test_tampered_evidence_chain_downgrades_pass(self):
        jid = self._ready_job()
        ref = self._evidence(jid)
        path = self.rt.development_evidence.path
        text = path.read_text(encoding='utf-8').replace('"status": "PASS"', '"status": "PASX"')
        path.write_text(text, encoding='utf-8')
        record, _ = self._verify_claim(jid, [ref])
        self.assertEqual(record['result'], 'INCONCLUSIVE')
        self.assertIn('pass_downgraded:evidence_chain_invalid', record['findings'])

    def test_pass_with_valid_deterministic_evidence_stands(self):
        jid = self._ready_job()
        record, job = self._verify_claim(jid, [self._evidence(jid)])
        self.assertEqual(record['result'], 'PASS')
        self.assertEqual(job['state'], 'READY_FOR_ACCEPTANCE')

    def test_unrelated_extra_reference_does_not_break_a_proven_pass(self):
        jid = self._ready_job()
        record, _ = self._verify_claim(jid, [self._evidence(jid), 'EVD-NOPE'])
        self.assertEqual(record['result'], 'PASS')

    def test_fail_and_inconclusive_need_no_evidence(self):
        jid = self._ready_job()
        record = self.rt.self_development.attach_verification(jid, verifier='verifier', result='FAIL', findings=['broken'])
        self.assertEqual(record['result'], 'FAIL')
        self.assertEqual(self.rt.self_development.jobs.load(jid)['state'], 'REWORK')

    def test_manager_without_evidence_store_cannot_pass(self):
        jid = self._ready_job()
        self.rt.self_development.evidence_store = None
        record, _ = self._verify_claim(jid, ['EVD-1'])
        self.assertEqual(record['result'], 'INCONCLUSIVE')
        self.assertIn('pass_downgraded:evidence_store_unavailable', record['findings'])

    def test_evolution_handoff_creates_controlled_job(self):
        gap=self.rt.evolution.record_gap('Need novel formatter',gap_type='captain_request',target_type='skill',target_id='novel_formatter')
        out=self.rt.evolution.handoff_to_self_development(gap,self.rt.self_development)
        self.assertEqual(out['status'],'ADMITTED')
        self.assertEqual(out['job']['contract']['classification'],'E1')

    def test_kev_is_loopback_only_and_can_parse_local_response(self):
        with self.assertRaises(ValueError): KevVerificationProvider('https://example.com/v1/systemone',enabled=True)
        class Response:
            # The shape the real Kev server returns: answers keyed by question id, noul answers carry p(true).
            def read(self): return json.dumps({'model':'kev-latest','answers':{'q1':{'type':'noul','noul':0.93}},'usage':{'input_tokens':12,'output_tokens':3}}).encode()
        provider=KevVerificationProvider('http://127.0.0.1:8008/v1/systemone',enabled=True,opener=lambda req,timeout:Response())
        out=provider.verify('Candidate satisfies contract',[{'type':'noul','question':'Pass?'}])
        self.assertEqual(out['status'],'ANSWERED'); self.assertEqual(out['provider'],'kev'); self.assertEqual(out['trust_level'],'model_assessment')

    def test_qwen35_kev_pair_profile_is_exposed(self):
        profile=self.rt.recommended_model_profile
        self.assertTrue(profile['model'].startswith('Qwen3.5-'))
        self.assertEqual(profile['verification']['provider'],'kev')
        result=self.rt.model_runtime.profile_for(model_size_gb=0.5,verifier_size_gb=0.2)
        self.assertIn(result['match_level'],{'OPTIMAL','COMPATIBLE','DEGRADED','INCOMPATIBLE'})
        self.assertIn(result['execution_mode'],{'DUAL_LOADED','SWAP_MODE','CPU_GPU_SPLIT'})

    def test_self_development_view_model(self):
        view=self.rt.self_development.view()
        self.assertIn('E3',view['policy']); self.assertFalse(view['policy']['E3']['may_activate'])
        self.assertEqual(view['kev']['provider'],'kev')


if __name__ == '__main__':
    unittest.main()
