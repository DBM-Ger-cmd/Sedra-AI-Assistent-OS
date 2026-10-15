"""Phase 8d: the verification gate, candidate pinning, parking and the independent review job."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.audit import AuditLog
from guppi_runtime.development_contracts import canonical_digest, development_contract, verification_contract
from guppi_runtime.development_evidence import DevelopmentEvidenceStore
from guppi_runtime.job_supervisor import JobError, JobSupervisor, SupervisorConfig, SupervisorJobStore, supervisor_state
from guppi_runtime.verification_gate import VerificationGate, document_check, record_check, record_review
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
TEXT = 'A hash-chained log links every entry to the one before it, so removing or editing an entry breaks the chain.'
CHASH = hashlib.sha256(TEXT.encode()).hexdigest()
KEYS = {'documentation': 'family-a|weights-a', 'coder': 'family-a|weights-a', 'verifier': 'family-b|weights-b', 'security_reviewer': 'family-b|weights-b'}


class Base(unittest.TestCase):
    keys = dict(KEYS)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.audit = AuditLog(root / 'audit.jsonl')
        self.evidence = DevelopmentEvidenceStore(root / 'evidence.jsonl', self.audit)
        store = SupervisorJobStore(root / 'jobs', self.audit)
        self.gate = VerificationGate(self.evidence, store.load)
        config = SupervisorConfig.load(RUNTIME / 'config' / 'job_supervisor.yaml'); config.enabled = True
        self.sup = JobSupervisor(store, config, audit=self.audit, pass_gate=self.gate.gaps)
        self.asked = []
        def resolver(role, req, exclude, independent_of):
            self.asked.append((role, list(independent_of)))
            return {'role': role, 'provider_ref': 'lm-studio', 'capability_id': 'c-' + role, 'independence_key': self.keys.get(role), 'context_window': 8192,
                    'estimated_resources': {}, 'model': 'm-' + role}
        self.sup.resolver = resolver
        self.n = 0

    # ---- helpers
    def contract(self, criteria=None, plan=None):
        return development_contract(objective='write the note', classification='E1',
                                    acceptance_criteria=criteria if criteria is not None else [{'type': 'document_check', 'id': 'doc_ok'}],
                                    verification_plan=plan if plan is not None else [{'type': 'deterministic_tests'}, {'type': 'independent_review'}])

    def start(self, role, kind='development', parent=None, contract=None, worker=None):
        self.n += 1; worker = worker or f'w{self.n}'
        job = self.sup.create_job(contract or self.contract(), requested_role=role, kind=kind, parent_job_id=parent, permission_level=1)
        self.sup.enqueue(job['job_id']); self.sup.claim(worker, [role])
        res = self.sup.confirm_start(job['job_id'], worker); assert res['status'] == 'running', res
        return job['job_id'], worker

    def built(self, role='documentation', candidate_hash=CHASH, contract=None, checks=('doc_ok',), park=True):
        job_id, worker = self.start(role, contract=contract)
        self.sup.bind_candidate(job_id, worker, stage='guppi-candidates/note', parent_version='v0', candidate_hash=candidate_hash, changed_files=['note.md'])
        self.sup.complete_step(job_id, worker, 'TESTING')
        refs = []
        for cid in checks:
            refs.append(record_check(self.evidence, self.sup.store.load(job_id), criterion_id=cid, status='PASS', check='document_check')['evidence_id'])
        self.sup.complete_step(job_id, worker, 'VERIFYING')
        if park: self.sup.park_for_verification(job_id, worker)
        return job_id, worker, refs

    def reviewed(self, parent_id, role='verifier', verdict='PASS', kind='review'):
        review_id, worker = self.start(role, kind=kind, parent=parent_id)
        self.sup.complete_review(review_id, worker)
        review = self.sup.store.load(review_id)
        record = record_review(self.evidence, self.sup.store.load(parent_id), review, review['attempt_log'][-1], verdict=verdict, summary='looks right')
        return review_id, record['evidence_id']

    def verification(self, job_id, refs, result='PASS', verifier='verifier'):
        return verification_contract(candidate_contract_record=self.sup.store.load(job_id)['candidate'], verifier=verifier, evidence_refs=refs, result=result)

    def gaps(self, job_id, verification): return self.gate.gaps(self.sup.store.load(job_id), verification)


class HappyPathTest(Base):
    def test_build_check_park_review_accept(self):
        job_id, _, refs = self.built()
        job = self.sup.store.load(job_id)
        self.assertEqual((job['state'], supervisor_state(job)), ('VERIFYING', 'WAITING_VERIFICATION'))
        self.assertIsNone(job['worker']); self.assertEqual(job['attempt_log'][-1]['outcome'], 'SUCCEEDED')
        review_id, review_ref = self.reviewed(job_id)
        verification = self.verification(job_id, refs + [review_ref])
        self.assertEqual(self.gaps(job_id, verification), [])
        out = self.sup.accept_verification(job_id, verification)
        self.assertEqual(out['status'], 'PASSED')
        job = self.sup.store.load(job_id)
        self.assertEqual((job['state'], supervisor_state(job), job['verification']['verification_digest']), ('READY_FOR_ACCEPTANCE', 'PASSED', verification['verification_digest']))
        self.assertTrue(self.evidence.verify_chain())

    def test_the_review_job_resolves_with_the_builders_key_as_the_one_to_avoid(self):
        job_id, _, _ = self.built()
        self.reviewed(job_id)
        self.assertEqual(self.asked[-1], ('verifier', [KEYS['documentation']]))

    def test_parking_frees_the_worker_so_the_review_can_run_on_the_single_worker(self):
        job_id, _, _ = self.built(park=False)
        review = self.sup.create_job(self.contract(), requested_role='verifier', kind='review', parent_job_id=job_id, permission_level=1)
        self.sup.enqueue(review['job_id'])
        with self.assertRaises(JobError) as ctx: self.sup.claim('w9', ['verifier'])
        self.assertEqual(ctx.exception.code, 'worker_busy')
        self.sup.park_for_verification(job_id, self.sup.store.load(job_id)['worker']['worker_id'])
        self.assertEqual(self.sup.claim('w9', ['verifier'])['job']['job_id'], review['job_id'])


class GapTest(Base):
    def setUp(self):
        super().setUp()
        self.job_id, _, self.refs = self.built()
        self.review_id, self.review_ref = self.reviewed(self.job_id)

    def refused(self, verification, expect):
        gaps = self.gaps(self.job_id, verification)
        self.assertTrue(any(g.startswith(expect) for g in gaps), (expect, gaps))
        with self.assertRaises(JobError) as ctx: self.sup.accept_verification(self.job_id, verification)
        self.assertEqual(ctx.exception.code, 'verification_gate_failed')
        self.assertEqual(supervisor_state(self.sup.store.load(self.job_id)), 'WAITING_VERIFICATION')        # still parked, nothing promoted

    def test_no_evidence_no_pass(self):
        self.refused(self.verification(self.job_id, []), 'deterministic_test_evidence_required')
        self.refused(self.verification(self.job_id, []), 'independent_review_required')

    def test_a_model_opinion_is_not_deterministic_evidence(self):
        self.refused(self.verification(self.job_id, [self.review_ref]), 'deterministic_test_evidence_required')

    def test_every_acceptance_criterion_needs_its_own_pass(self):
        contract = self.contract(criteria=[{'type': 'document_check', 'id': 'doc_ok'}, {'type': 'tone', 'id': 'tone_ok'}])
        job_id, _, refs = self.built(contract=contract, checks=('doc_ok',))
        _, review_ref = self.reviewed(job_id)
        gaps = self.gaps(job_id, self.verification(job_id, refs + [review_ref]))
        self.assertEqual([g for g in gaps if g.startswith('acceptance')], ['acceptance_criterion_not_covered:tone_ok'])

    def test_criteria_without_an_id_cannot_be_checked(self):
        job_id, _, refs = self.built(contract=self.contract(criteria=[{'type': 'document_check'}]), checks=('x',))
        _, review_ref = self.reviewed(job_id)
        self.assertIn('acceptance_criterion_without_id', self.gaps(job_id, self.verification(job_id, refs + [review_ref])))

    def test_one_failing_deterministic_record_vetoes_the_rest(self):
        job = self.sup.store.load(self.job_id)
        bad = record_check(self.evidence, job, criterion_id='doc_ok', status='FAIL', check='document_check')['evidence_id']
        self.refused(self.verification(self.job_id, self.refs + [self.review_ref, bad]), 'deterministic_evidence_not_passing')

    def test_evidence_made_for_other_content_does_not_count(self):
        job = self.sup.store.load(self.job_id)
        other = self.evidence.add('deterministic_check', job_id=self.job_id, candidate_id=job['candidate']['candidate_id'], artifact_sha256='f' * 64,
                                  trust_level='deterministic', payload={'status': 'PASS', 'criterion_id': 'doc_ok'})['evidence_id']
        self.refused(self.verification(self.job_id, [other, self.review_ref]), 'evidence_for_other_candidate_hash')

    def test_evidence_of_another_job_or_candidate_is_ignored(self):
        other_job, _, other_refs = self.built()
        self.refused(self.verification(self.job_id, other_refs + [self.review_ref]), 'evidence_not_found_for_job')
        stray = self.evidence.add('deterministic_check', job_id=self.job_id, candidate_id='CAND-OTHER', artifact_sha256=CHASH, trust_level='deterministic',
                                  payload={'status': 'PASS', 'criterion_id': 'doc_ok'})['evidence_id']
        self.refused(self.verification(self.job_id, [stray, self.review_ref]), 'evidence_not_bound_to_candidate')

    def test_an_edited_evidence_chain_is_refused(self):
        path = self.evidence.path
        lines = path.read_text(encoding='utf-8').splitlines()
        record = json.loads(lines[0]); record['payload']['status'] = 'PASS'; record['payload']['detail'] = {'edited': True}
        lines[0] = json.dumps(record, ensure_ascii=False, sort_keys=True); path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.refused(self.verification(self.job_id, self.refs + [self.review_ref]), 'evidence_chain_invalid')

    def test_a_tampered_verification_record(self):
        verification = self.verification(self.job_id, self.refs + [self.review_ref])
        verification['evidence_refs'] = self.refs                               # changed after it was digested
        self.refused(verification, 'verification_digest_mismatch')

    def test_verification_of_another_candidate_and_non_pass_results(self):
        job = self.sup.store.load(self.job_id)
        verification = self.verification(self.job_id, self.refs + [self.review_ref])
        stranger = dict(verification, candidate_id='CAND-OTHER'); stranger['verification_digest'] = canonical_digest({k: v for k, v in stranger.items() if k != 'verification_digest'})
        self.refused(stranger, 'verification_not_for_this_candidate')
        self.refused(self.verification(self.job_id, self.refs + [self.review_ref], result='INCONCLUSIVE'), 'passing_verification_required')
        self.refused(self.verification(self.job_id, self.refs + [self.review_ref], verifier='documentation'), 'verifier_is_builder')
        self.assertEqual(self.gate.gaps(job, 'PASS'), ['verification_record_required'])

    def test_a_candidate_without_a_content_hash_cannot_pass(self):
        job_id, worker = self.start('documentation')
        self.sup.bind_candidate(job_id, worker, stage='guppi-candidates/x', parent_version='v0', candidate_hash=None)
        self.sup.complete_step(job_id, worker, 'TESTING'); self.sup.complete_step(job_id, worker, 'VERIFYING')
        self.assertIn('candidate_hash_required', self.gaps(job_id, self.verification(job_id, [])))
        with self.assertRaises(ValueError): record_check(self.evidence, self.sup.store.load(job_id), criterion_id='doc_ok', status='PASS', check='c')


class IndependenceTest(Base):
    def run_case(self, builder_key, reviewer_key, verdict='PASS', role='verifier', kind='review'):
        self.keys = {'documentation': builder_key, role: reviewer_key}
        self.sup.resolver.__defaults__  # resolver reads self.keys at call time
        job_id, _, refs = self.built()
        review_id, ref = self.reviewed(job_id, role=role, verdict=verdict, kind=kind)
        return job_id, review_id, self.gaps(job_id, self.verification(job_id, refs + [ref]))

    def test_same_model_is_not_independent(self):
        self.assertIn('review_not_independent:same', ' '.join(self.run_case('k1', 'k1')[2]))

    def test_unknown_identity_is_not_independent_on_either_side(self):
        self.assertIn('review_not_independent:unverifiable', ' '.join(self.run_case('k1', None)[2]))
        self.assertIn('review_not_independent:unverifiable', ' '.join(self.run_case(None, 'k2')[2]))

    def test_different_models_pass(self):
        self.assertEqual(self.run_case('k1', 'k2')[2], [])

    def test_a_failing_review_never_supports_a_pass(self):
        self.assertIn('independent_review_not_passing', ' '.join(self.run_case('k1', 'k2', verdict='FAIL')[2]))

    def test_the_review_must_be_a_finished_child_review_job_of_a_review_role(self):
        job_id, _, refs = self.built(); stranger_parent, _, _ = self.built()
        review_id, ref = self.reviewed(stranger_parent)                       # a review of ANOTHER job, cited here
        record = self.evidence.add('independent_review', job_id=job_id, candidate_id=self.sup.store.load(job_id)['candidate']['candidate_id'],
                                   artifact_sha256=CHASH, trust_level='model_assessment',
                                   payload={'verdict': 'PASS', 'verifier_job_id': review_id, 'attempt_id': 'x', 'independence_key': None})
        gaps = ' '.join(self.gaps(job_id, self.verification(job_id, refs + [record['evidence_id']])))
        self.assertIn('review_job_not_a_child_of_this_job', gaps); self.assertIn('review_attempt_not_successful', gaps)
        ghost = self.evidence.add('independent_review', job_id=job_id, candidate_id=self.sup.store.load(job_id)['candidate']['candidate_id'], artifact_sha256=CHASH,
                                  trust_level='model_assessment', payload={'verdict': 'PASS', 'verifier_job_id': 'SDJ-NOPE'})
        self.assertIn('review_job_not_found', ' '.join(self.gaps(job_id, self.verification(job_id, refs + [ghost['evidence_id']]))))

    def test_a_review_that_claims_trust_it_does_not_have(self):
        job_id, _, refs = self.built()
        review_id, _ = self.reviewed(job_id)
        review = self.sup.store.load(review_id)
        forged = self.evidence.add('independent_review', job_id=job_id, candidate_id=self.sup.store.load(job_id)['candidate']['candidate_id'], artifact_sha256=CHASH,
                                   trust_level='deterministic', payload={'verdict': 'PASS', 'verifier_job_id': review_id, 'attempt_id': review['attempt_log'][-1]['attempt_id']})
        self.assertIn('review_evidence_trust_level_invalid', ' '.join(self.gaps(job_id, self.verification(job_id, refs + [forged['evidence_id']]))))


class MechanicsTest(Base):
    def test_candidate_is_bound_only_by_the_owner_while_building(self):
        job_id, worker = self.start('documentation')
        with self.assertRaises(JobError): self.sup.bind_candidate(job_id, 'someone-else', stage='guppi-candidates/x', parent_version='v0', candidate_hash=CHASH)
        with self.assertRaises(ValueError): self.sup.bind_candidate(job_id, worker, stage='elsewhere/x', parent_version='v0', candidate_hash=CHASH)
        self.sup.bind_candidate(job_id, worker, stage='guppi-candidates/x', parent_version='v0', candidate_hash=CHASH)
        self.sup.complete_step(job_id, worker, 'TESTING')
        with self.assertRaises(JobError): self.sup.bind_candidate(job_id, worker, stage='guppi-candidates/x', parent_version='v0', candidate_hash=CHASH)

    def test_parking_needs_a_candidate_and_the_verifying_state(self):
        job_id, worker = self.start('documentation')
        with self.assertRaises(JobError): self.sup.park_for_verification(job_id, worker)

    def test_complete_review_is_for_review_jobs_only(self):
        job_id, worker = self.start('documentation')
        with self.assertRaises(JobError) as ctx: self.sup.complete_review(job_id, worker)
        self.assertEqual(ctx.exception.code, 'not_a_review_job')

    def test_accept_needs_a_parked_job_and_a_gate(self):
        done, _, refs = self.built()
        job_id, worker = self.start('documentation')
        with self.assertRaises(JobError): self.sup.accept_verification(job_id, {})
        self.sup.pass_gate = None
        with self.assertRaises(JobError) as ctx: self.sup.accept_verification(done, {})
        self.assertEqual(ctx.exception.code, 'verification_gate_unavailable')

    def test_a_rejected_review_sends_the_job_to_rework_and_demands_a_different_candidate(self):
        job_id, _, _ = self.built()
        self.sup.reject_verification(job_id, findings=['claims something false'])
        job = self.sup.store.load(job_id)
        self.assertEqual((job['state'], job['retry']['awaiting_change'], job['retry']['last_candidate_hash']), ('REWORK', 'candidate_hash', CHASH))
        with self.assertRaises(JobError): self.sup.supply_change(job_id, candidate_hash=CHASH)             # the identical candidate is not a change
        self.sup.supply_change(job_id, candidate_hash='b' * 64)

    def test_in_place_mark_passed_asks_the_same_gate(self):
        job_id, worker = self.start('documentation')
        self.sup.bind_candidate(job_id, worker, stage='guppi-candidates/x', parent_version='v0', candidate_hash=CHASH)
        self.sup.complete_step(job_id, worker, 'TESTING'); self.sup.complete_step(job_id, worker, 'VERIFYING')
        with self.assertRaises(JobError) as ctx: self.sup.mark_passed(job_id, worker, self.verification(job_id, []))
        self.assertEqual(ctx.exception.code, 'verification_gate_failed')


class DocumentCheckTest(unittest.TestCase):
    def test_a_clean_document_passes_and_is_hashed(self):
        out = document_check(TEXT)
        self.assertEqual((out['status'], out['sha256']), ('PASS', CHASH))

    def test_each_check_can_fail(self):
        for text, name in (('', 'size_within_limit'), ('short', 'has_substance'), (TEXT + ' api_key = sk-12345', 'no_secret_shaped_values'),
                           (TEXT + ' ```python', 'code_fences_balanced'), (None, 'is_text')):
            out = document_check(text)
            self.assertEqual(out['status'], 'FAIL', name)
            self.assertIn(name, [c['check'] for c in out['checks'] if not c['ok']])
        self.assertEqual(document_check(TEXT + ' internal only', forbidden=['internal only'])['status'], 'FAIL')
        self.assertEqual(document_check(TEXT, max_bytes=10)['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
