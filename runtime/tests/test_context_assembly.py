"""Phase 4: child manifests, assembly, fresh context, repair, and the supervisor glue. Mechanics only; no model."""
import inspect
import json
import re
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from guppi_runtime.artifacts import ArtifactStore
from guppi_runtime.core.audit import AuditLog
from guppi_runtime.jobs.context_manager import ContextConfig, ContextError, ContextManager
from guppi_runtime.selfdev.development_contracts import canonical_digest, context_manifest, development_contract
from guppi_runtime.selfdev.development_evidence import DevelopmentEvidenceStore
from guppi_runtime.jobs.job_repair import repair_job, trigger_for
from guppi_runtime.jobs.job_supervisor import JobError, JobSupervisor, SupervisorConfig, SupervisorJobStore
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
CONFIG = RUNTIME / 'config' / 'job_supervisor.yaml'
JOB = 'SDJ-0123456789AB'
MARKER = 'MARKER-PARENT-CHAT-7731'


def contract(**kw):
    kw.setdefault('acceptance_criteria', [{'type': 'capability_smoke_test', 'id': 'smoke'}])
    kw.setdefault('verification_plan', [{'type': 'deterministic_tests'}])
    return development_contract(objective='probe objective', classification='E1', **kw)


class FakeRetriever:
    def __init__(self, items): self.items = items; self.calls = []
    def fetch(self, kind, ref):
        self.calls.append((kind, ref)); return self.items.get((kind, ref))


class Clock:
    def __init__(self): self.wall = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc); self.mono = 1000.0
    def now(self): return self.wall
    def monotonic(self): return self.mono
    def advance(self, s): self.wall += timedelta(seconds=s); self.mono += s


class Base(unittest.TestCase):
    repair_max = 2

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.clock = Clock()
        self.audit = AuditLog(self.root / 'audit.jsonl')
        self.artifacts = ArtifactStore(self.root / 'artifacts', self.audit)
        self.evidence = DevelopmentEvidenceStore(self.root / 'evidence.jsonl', self.audit)
        raw = yaml.safe_load(CONFIG.read_text(encoding='utf-8'))['context_manager']
        raw['enabled'] = True; raw['repair']['max_per_job'] = self.repair_max
        self.cm = ContextManager(self.root, ContextConfig(raw), artifacts=self.artifacts, audit=self.audit, evidence_store=self.evidence,
                                 clock=self.clock.now)
        self.job = self.make_job()

    def make_job(self, job_id=JOB, **extra):
        job = {'job_id': job_id, 'parent_job_id': None, 'contract': contract(), 'permission_level': 2, 'state': 'BUILDING', 'attempt_log': []}
        job.update(extra); return job

    def events(self):
        path = self.root / 'audit.jsonl'
        return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()] if path.exists() else []

    def types(self): return [e['event_type'] for e in self.events()]

    def checkpoint_source(self, **extra):
        def source():
            return {'goal': 'finish probe', 'next_steps': ['run the tests'], 'permission_state': {'level': 2}, **extra}
        return source

    def write_checkpoint(self, job=None, **kw):
        job = job or self.job
        return self.cm.checkpoint(job['job_id'], 'ATT-OLD', **{'goal': 'finish probe', 'permission_state': {'level': 2}, **kw})


class ManifestTests(Base):
    def test_builder_has_no_way_to_carry_a_parent_conversation(self):
        params = set(inspect.signature(self.cm.assembly.build_manifest).parameters)
        for forbidden in ('history', 'messages', 'chat', 'conversation', 'transcript', 'parent_history'):
            self.assertNotIn(forbidden, params)

    def test_child_gets_the_manifest_not_the_parents_chat(self):
        parent_chat = [{'role': 'user', 'content': f'turn {i} {MARKER}'} for i in range(50)]
        self.assertEqual(len(parent_chat), 50)                     # exists in the "parent session", has no channel to the child
        art = self.cm.offloader.offload(JOB, 'A1', {'tool': 'shell'}, 'ARTIFACT-BODY-SHOULD-STAY-OUT\n' * 400)
        cp = self.write_checkpoint(decisions=[{'text': 'use the lock', 'decided_by': 'guppi', 'ref': 'D1'}],
                                   open_errors=[{'class': 'validation_failure', 'summary': 'sha mismatch on app.py'}],
                                   artifacts=[art['artifact_id']], next_steps=['rerun tests'])
        retriever = FakeRetriever({('file', 'src/app.py'): 'def run():\n    return 1\n', ('symbol', 'Worker.start'): 'class Worker:\n    def start(self): pass\n'})
        manifest = self.cm.build_manifest(self.job, task='fix the failing test', parent_checkpoint=cp, files=['src/app.py'], symbols=['Worker.start'])
        out = self.cm.assemble(manifest, retriever=retriever)
        blob = json.dumps(manifest) + out['text']
        self.assertNotIn(MARKER, blob)
        self.assertNotIn('ARTIFACT-BODY-SHOULD-STAY-OUT', blob)
        self.assertEqual(out['status'], 'READY')
        for needed in ('probe objective', 'forbidden: modify_stable_directly', 'max_permission_level: 2', 'capability_smoke_test', 'fix the failing test',
                       'def run()', 'class Worker', 'use the lock', 'validation_failure: sha mismatch on app.py', 'next: rerun tests', art['artifact_id']):
            self.assertIn(needed, out['text'], needed)
        self.assertEqual(manifest['artifact_refs'], [art['artifact_id']])
        self.assertEqual(out['allowed_artifacts'], {art['artifact_id']})

    def test_child_can_read_only_artifacts_named_in_its_manifest(self):
        mine = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'mine' * 4000)['artifact_id']
        other = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'other' * 4000)['artifact_id']
        out = self.cm.assemble(self.cm.build_manifest(self.job, task='t', artifact_refs=[mine]))
        self.assertEqual(self.cm.read_artifact_range(mine, 0, 4, allowed_artifacts=out['allowed_artifacts']), b'mine')
        with self.assertRaises(ContextError) as ctx: self.cm.read_artifact_range(other, 0, 4, allowed_artifacts=out['allowed_artifacts'])
        self.assertEqual(ctx.exception.code, 'policy_denied')

    def test_manifest_is_persisted_audited_and_verifiable(self):
        manifest = self.cm.build_manifest(self.job, task='t')
        self.assertEqual(self.cm.assembly.load_manifest(JOB, manifest['manifest_id']), manifest)
        built = [e for e in self.events() if e['event_type'] == 'CONTEXT_MANIFEST_BUILT'][0]['payload']
        self.assertEqual((built['manifest_id'], built['manifest_digest'], built['fresh']), (manifest['manifest_id'], manifest['manifest_digest'], False))
        path = self.root / 'context_manifests' / JOB / f"{manifest['manifest_id']}.json"
        data = json.loads(path.read_text(encoding='utf-8')); data['current_task'] = 'something else'
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ContextError) as ctx: self.cm.assembly.load_manifest(JOB, manifest['manifest_id'])
        self.assertEqual((ctx.exception.code, ctx.exception.detail), ('manifest_invalid', 'digest_mismatch'))

    def test_assembling_a_modified_manifest_is_refused(self):
        manifest = self.cm.build_manifest(self.job, task='t')
        manifest['permissions'] = {'max_level': 6}
        with self.assertRaises(ContextError) as ctx: self.cm.assemble(manifest)
        self.assertEqual(ctx.exception.code, 'manifest_invalid')
        with self.assertRaises(ContextError): self.cm.assemble({'no': 'digest'})

    def test_permissions_never_exceed_the_job_and_a_checkpoint_cannot_raise_them(self):
        job = self.make_job(permission_level=1)
        self.assertEqual(self.cm.build_manifest(job, task='t')['permissions'], {'max_level': 1})
        cp = self.write_checkpoint(job, permission_state={'level': 3})
        with self.assertRaises(ContextError) as ctx: self.cm.build_manifest(job, task='t', parent_checkpoint=cp)
        self.assertEqual((ctx.exception.code, ctx.exception.detail), ('policy_denied', 'checkpoint_permission_exceeds_job'))

    def test_checkpoint_of_an_unrelated_job_is_refused_but_the_parents_is_fine(self):
        stranger = self.make_job('SDJ-AAAAAAAAAAAA')
        cp = self.write_checkpoint(stranger)
        with self.assertRaises(ContextError) as ctx: self.cm.build_manifest(self.job, task='t', parent_checkpoint=cp)
        self.assertEqual(ctx.exception.detail, 'checkpoint_from_unrelated_job')
        child = self.make_job('SDJ-BBBBBBBBBBBB', parent_job_id=JOB)
        parent_cp = self.write_checkpoint(self.job)
        self.assertEqual(self.cm.build_manifest(child, task='t', parent_checkpoint=parent_cp)['parent_job_id'], JOB)

    def test_a_tampered_checkpoint_cannot_seed_a_context(self):
        cp = self.write_checkpoint(); cp['goal'] = 'changed'
        with self.assertRaises(ContextError) as ctx: self.cm.build_manifest(self.job, task='t', parent_checkpoint=cp)
        self.assertEqual(ctx.exception.code, 'checkpoint_digest_mismatch')
        with self.assertRaises(ContextError): self.cm.build_manifest(self.job, task='t', parent_checkpoint={'x': 1})

    def test_oversize_inputs_are_context_errors_not_crashes(self):
        with self.assertRaises(ContextError) as ctx: self.cm.build_manifest(self.job, task='t', open_questions=['q'] * 65)
        self.assertEqual(ctx.exception.code, 'manifest_invalid')
        with self.assertRaises(ContextError): self.cm.build_manifest(self.job, task='')
        with self.assertRaises(ContextError): self.cm.build_manifest({'job_id': JOB}, task='t')
        with self.assertRaises(ContextError): self.cm.build_manifest(self.make_job('../evil'), task='t')

    def test_snapshot_must_fit_its_budget(self):
        small = self.cm.resolve_budget(model_window=4096)
        with self.assertRaises(ContextError) as ctx: self.cm.build_manifest(self.job, task='t', budget=small, snapshot='x' * 50000)
        self.assertEqual(ctx.exception.detail, 'snapshot_missing_or_larger_than_project_context_budget')
        ok = self.cm.build_manifest(self.job, task='t', snapshot='compact project overview')
        self.assertIn('PROJECT SNAPSHOT', self.cm.assemble(ok)['text'])

    def test_minimum_context_larger_than_the_window_is_an_error(self):
        tiny = self.cm.resolve_budget(model_window=4096)
        with self.assertRaises(ContextError) as ctx: self.cm.build_manifest(self.job, task='t', budget=tiny, open_questions=['q ' * 240] * 30)
        self.assertEqual(ctx.exception.code, 'minimum_context_exceeds_window')
        self.assertIn('minimum_tokens', ctx.exception.detail)
        self.assertEqual(list((self.root / 'context_manifests').glob('**/*.json')), [])        # nothing half-built is left behind

    def test_pins_come_from_structured_sources(self):
        good = self.evidence.add('candidate_tests', job_id=JOB, candidate_id='CAND-1', payload={'status': 'PASS'}, trust_level='deterministic')
        self.evidence.add('opinion', job_id=JOB, candidate_id='CAND-1', payload={'status': 'PASS'}, trust_level='model_assessment')
        job = self.make_job(candidate={'candidate_hash': 'h' * 64, 'candidate_id': 'CAND-1'}, policy_hash='p' * 64)
        manifest = self.cm.build_manifest(job, task='t', approvals=[{'token_id': 'APR-1', 'action': 'candidate_accept'}])
        kinds = sorted(p['kind'] for p in manifest['pins'])
        self.assertEqual(kinds, ['approval', 'code_change', 'constraint', 'policy_hash', 'test_result'])
        self.assertEqual([p['ref'] for p in manifest['pins'] if p['kind'] == 'test_result'], [{'evidence_id': good['evidence_id']}])

    def test_every_pin_appears_in_the_assembled_context(self):
        rec = self.evidence.add('candidate_tests', job_id=JOB, candidate_id='CAND-1', payload={'status': 'PASS'}, trust_level='deterministic')
        job = self.make_job(candidate={'candidate_hash': 'h' * 64, 'candidate_id': 'CAND-1'}, policy_hash='p' * 64)
        manifest = self.cm.build_manifest(job, task='t')
        out = self.cm.assemble(manifest)
        self.assertEqual(out['pins'], manifest['pins'])
        for pin in manifest['pins']:
            self.assertIn(pin['pin_id'], out['text'])
        self.assertIn(rec['evidence_id'], out['text'])

    def test_old_style_manifests_are_unchanged(self):
        budget = self.cm.resolve_budget(model_window=8192)
        plain = context_manifest(goal='g', current_task='t', budget=budget)
        for key in ('layers', 'pins', 'snapshot', 'token_estimate', 'excluded', 'parent_manifest_id', 'budget_digest'):
            self.assertNotIn(key, plain)
        self.assertEqual(canonical_digest({k: v for k, v in plain.items() if k != 'manifest_digest'}), plain['manifest_digest'])
        rich = self.cm.build_manifest(self.job, task='t')
        for key in ('layers', 'pins', 'token_estimate', 'excluded', 'budget_digest'):
            self.assertIn(key, rich)
        self.assertEqual(rich['budget_digest'], canonical_digest(rich['budget']))


class AssemblyTests(Base):
    def test_layers_are_ordered_and_critical_pieces_always_stay(self):
        retriever = FakeRetriever({('file', 'a.py'): 'x = 1\n' * 200})
        manifest = self.cm.build_manifest(self.job, task='t', files=['a.py'], artifact_refs=['ART-00000000'], snapshot='overview')
        out = self.cm.assemble(manifest, retriever=retriever)
        layers = [p['layer'] for p in out['pieces']]
        self.assertEqual(layers, sorted(layers))
        self.assertEqual(layers[0], 'L0')
        kinds = [p['kind'] for p in out['pieces']]
        for kind in ('policy', 'contract', 'snapshot', 'pin', 'file_excerpt', 'artifact_ref'):
            self.assertIn(kind, kinds)
        self.assertEqual(retriever.calls, [('file', 'a.py')])       # detail is fetched on demand, once

    def test_pressure_drops_detail_never_policy_contract_or_pins(self):
        files = {('file', f'f{i}.py'): ('line of code\n' * 300) for i in range(12)}
        budget = self.cm.resolve_budget(model_window=4096)
        manifest = self.cm.build_manifest(self.job, task='t', budget=budget, files=[ref for _, ref in files])
        out = self.cm.assemble(manifest, retriever=FakeRetriever(files))
        kinds = [p['kind'] for p in out['pieces']]
        for kind in ('policy', 'contract', 'pin'):
            self.assertIn(kind, kinds)
        self.assertTrue(out['excluded'])
        self.assertTrue(all(e['reason'] == 'low_relevance' for e in out['excluded']))
        self.assertLessEqual(out['tokens'], int(0.55 * budget['max_input_tokens']) + max(p['tokens_est'] for p in out['pieces'] if p['critical']))
        self.assertLess(len([k for k in kinds if k == 'file_excerpt']), 12)

    def test_missing_detail_makes_the_result_incomplete_not_silently_smaller(self):
        manifest = self.cm.build_manifest(self.job, task='t', files=['a.py', 'gone.py'], symbols=['Nope'])
        out = self.cm.assemble(manifest, retriever=FakeRetriever({('file', 'a.py'): 'ok\n'}))
        self.assertEqual(out['status'], 'INCOMPLETE')
        self.assertEqual(out['missing'], [{'kind': 'file', 'ref': 'gone.py'}, {'kind': 'symbol', 'ref': 'Nope'}])
        self.assertEqual(self.cm.assemble(manifest)['status'], 'INCOMPLETE')                 # no retriever at all
        self.assertEqual(len(self.cm.assemble(manifest)['missing']), 3)

    def test_large_excerpts_are_cut_and_say_so(self):
        manifest = self.cm.build_manifest(self.job, task='t', files=['big.py'])
        out = self.cm.assemble(manifest, retriever=FakeRetriever({('file', 'big.py'): 'y' * 60000}))
        self.assertEqual(out['truncated'], [{'kind': 'file', 'ref': 'big.py'}])
        self.assertIn('truncated to about', out['text'])
        self.assertLess(out['tokens'], 4000)

    def test_artifact_bodies_are_only_referenced(self):
        art = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'BODY-NEVER-INLINE ' * 3000)['artifact_id']
        out = self.cm.assemble(self.cm.build_manifest(self.job, task='t', artifact_refs=[art]))
        self.assertIn(art, out['text']); self.assertNotIn('BODY-NEVER-INLINE', out['text'])

    def test_state_reports_the_fill_level(self):
        out = self.cm.assemble(self.cm.build_manifest(self.job, task='t'))
        self.assertEqual(out['state'], 'GREEN')


class FreshContextTests(Base):
    def test_fresh_context_keeps_pins_failures_decisions_and_limits(self):
        rec = self.evidence.add('candidate_tests', job_id=JOB, candidate_id='CAND-1', payload={'status': 'FAIL'}, trust_level='deterministic')
        pin = {'kind': 'test_result', 'ref': {'evidence_id': rec['evidence_id']}, 'digest': rec['evidence_hash'], 'value': 'FAIL'}
        path_pin = {'kind': 'path', 'ref': {'path': 'src/app.py'}, 'digest': 'a' * 64, 'value': 'src/app.py'}
        cp = self.write_checkpoint(pins=[pin, path_pin], open_errors=[{'class': 'deterministic_test_failure', 'summary': '3 tests failed'}],
                                   decisions=[{'text': 'keep the public API', 'decided_by': 'captain', 'ref': 'D9'}], next_steps=['fix test_x'])
        first = self.cm.build_manifest(self.job, task='first')
        fresh = self.cm.fresh_context(self.job, cp, task='second', attempt_id='ATT-NEW')
        have = {(p['kind'], json.dumps(p['ref'], sort_keys=True), p['digest']) for p in fresh['pins']}
        for p in cp['pins']:
            self.assertIn((p['kind'], json.dumps(p['ref'], sort_keys=True), p['digest']), have)
        self.assertIn('deterministic_test_failure: 3 tests failed', fresh['known_failures'])        # unresolved errors are not forgotten
        self.assertIn('keep the public API', fresh['relevant_decisions'])
        self.assertIn('forbidden: bypass_guard', fresh['constraints'])                              # limits come from the contract, not memory
        self.assertEqual((fresh['checkpoint_id'], fresh['current_task']), (cp['checkpoint_id'], 'second'))
        self.assertNotEqual(fresh['manifest_id'], first['manifest_id'])
        self.assertEqual(self.cm.metrics.summary(JOB)['fresh_context_count'], 1)
        self.assertTrue([e for e in self.events() if e['event_type'] == 'CONTEXT_MANIFEST_BUILT'][-1]['payload']['fresh'])

    def test_fresh_context_chain_records_its_parent_manifest(self):
        first = self.cm.build_manifest(self.job, task='one')
        cp = self.write_checkpoint(manifest=first)
        self.assertEqual(self.cm.fresh_context(self.job, cp, task='two')['parent_manifest_id'], first['manifest_id'])

    def test_a_pin_whose_source_vanished_blocks_the_new_context(self):
        art = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'x' * 5000)
        pin = {'kind': 'hash', 'ref': {'artifact_id': art['artifact_id']}, 'digest': art['sha256'], 'value': 'log'}
        cp = self.write_checkpoint(pins=[pin])
        (self.root / 'artifacts' / 'index.json').write_text('[]', encoding='utf-8')
        with self.assertRaises(ContextError) as ctx: self.cm.fresh_context(self.job, cp, task='t')
        self.assertEqual(ctx.exception.code, 'pin_missing_source')

    def test_next_job_starts_from_checkpoint_and_artifacts_not_from_history(self):
        art = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'result\n' * 3000)['artifact_id']
        cp = self.write_checkpoint(artifacts=[art], decisions=[{'text': 'done with step one', 'decided_by': 'guppi', 'ref': 'R1'}])
        history = [f'turn {i} {MARKER}' for i in range(40)]
        self.assertTrue(history)
        out = self.cm.assemble(self.cm.fresh_context(self.job, cp, task='step two'))
        self.assertNotIn(MARKER, out['text'])
        self.assertIn(art, out['text']); self.assertIn('done with step one', out['text'])


class RepetitionTests(Base):
    def test_detection(self):
        d = self.cm.detect_repetition
        same = [{'request_digest': 'a'}] * 3
        self.assertEqual(d(same), {'trigger': 'repetition', 'kind': 'request', 'count': 3, 'value': 'a'})
        self.assertEqual(d([{'error_signature': 'e'}] * 3)['kind'], 'error')
        self.assertIsNone(d([{'request_digest': 'a'}] * 2))
        self.assertIsNone(d([{'request_digest': 'a'}, {'request_digest': 'b'}, {'request_digest': 'a'}, {'request_digest': 'b'}]))
        self.assertIsNone(d([])); self.assertIsNone(d([{}, {}, {}]))
        self.assertEqual(d([{'request_digest': 'x'}] * 5, threshold=5)['count'], 5)
        self.assertIsNone(d([{'request_digest': 'x'}] * 4, threshold=5))
        self.assertIsNone(d([{'request_digest': 'x'}, {'request_digest': 'x'}, {'request_digest': None}, {'request_digest': 'x'}]))


class RepairTests(Base):
    def test_plan_rules(self):
        plan = self.cm.plan_repair(self.job, trigger='stagnation', mutating=False)
        self.assertTrue(plan['possible']); self.assertTrue(plan['worker_change_requested'])
        self.assertFalse(self.cm.plan_repair(self.job, trigger='context_overflow', mutating=False)['worker_change_requested'])
        final = self.make_job(state='DEAD')
        self.assertEqual(self.cm.plan_repair(final, trigger='manual', mutating=False)['reason'], 'job_is_final')
        unknown = self.make_job(attempt_log=[{'attempt_id': 'ATT-1', 'outcome': 'UNKNOWN'}])
        self.assertEqual(self.cm.plan_repair(unknown, trigger='manual', mutating=True)['reason'], 'unknown_outcome_of_mutating_attempt')
        self.assertTrue(self.cm.plan_repair(unknown, trigger='manual', mutating=False)['possible'])      # a read-only attempt is safe to redo
        with self.assertRaises(ContextError): self.cm.plan_repair(self.job, trigger='because', mutating=False)

    def test_repair_keeps_the_job_changes_the_attempt_and_writes_a_checkpoint(self):
        job = self.make_job(attempt_log=[{'attempt_id': 'ATT-OLD', 'outcome': 'RUNNING'}])
        plan = self.cm.repair(job, trigger='stagnation', task='continue', checkpoint_source=self.checkpoint_source(), mutating=False)
        self.assertEqual(plan['preserves']['job_id'], JOB)
        self.assertNotEqual(plan['attempt_id_new'], 'ATT-OLD')
        self.assertTrue(plan['attempt_id_new'].startswith('ATT-'))
        cp_file = self.root / 'context_checkpoints' / JOB / f"{plan['checkpoint']['checkpoint_id']}.json"
        self.assertTrue(cp_file.exists())
        self.assertEqual(plan['new_manifest']['checkpoint_id'], plan['checkpoint']['checkpoint_id'])
        self.assertEqual(plan['checkpoint']['permission_state'], plan['preserves']['permission_state'])
        event = [e for e in self.events() if e['event_type'] == 'CONTEXT_REPAIR'][0]['payload']
        self.assertEqual((event['job_id'], event['attempt_id_previous'], event['attempt_id_new']), (JOB, 'ATT-OLD', plan['attempt_id_new']))
        self.assertTrue(event['worker_change_requested'])
        self.assertEqual(self.cm.metrics.summary(JOB)['fresh_context_count'], 1)

    def test_repair_limit_then_refusal_is_audited(self):
        for _ in range(2):
            self.cm.repair(self.job, trigger='manual', task='t', checkpoint_source=self.checkpoint_source(), mutating=False)
        with self.assertRaises(ContextError) as ctx:
            self.cm.repair(self.job, trigger='manual', task='t', checkpoint_source=self.checkpoint_source(), mutating=False)
        self.assertEqual((ctx.exception.code, ctx.exception.detail), ('repair_not_possible', 'repair_limit_reached'))
        refused = [e for e in self.events() if e['event_type'] == 'CONTEXT_REPAIR_REFUSED']
        self.assertEqual(refused[-1]['payload']['reason'], 'repair_limit_reached')
        self.assertEqual(len(self.cm.checkpoints.list_ids(JOB)), 2)                 # the refused repair wrote nothing

    def test_mutating_unknown_outcome_is_never_repaired(self):
        job = self.make_job(attempt_log=[{'attempt_id': 'ATT-1', 'outcome': 'UNKNOWN'}])
        with self.assertRaises(ContextError) as ctx: self.cm.repair(job, trigger='stagnation', task='t', checkpoint_source=self.checkpoint_source(), mutating=True)
        self.assertEqual(ctx.exception.detail, 'unknown_outcome_of_mutating_attempt')
        self.assertEqual(self.cm.checkpoints.list_ids(JOB), [])
        self.assertIn('CONTEXT_REPAIR_REFUSED', self.types())

    def test_repair_needs_a_checkpoint_source(self):
        with self.assertRaises(ContextError) as ctx: self.cm.repair(self.job, trigger='manual', task='t', checkpoint_source=None, mutating=False)
        self.assertEqual(ctx.exception.detail, 'no_checkpoint_source')

    def test_concurrent_repairs_cannot_exceed_the_limit(self):
        results = []

        def go():
            try:
                self.cm.repair(self.job, trigger='manual', task='t', checkpoint_source=self.checkpoint_source(), mutating=False); results.append('ok')
            except ContextError as exc:
                results.append(exc.detail)

        threads = [threading.Thread(target=go) for _ in range(6)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(results.count('ok'), 2)
        self.assertEqual(results.count('repair_limit_reached'), 4)


class SupervisorGlueTests(Base):
    def setUp(self):
        super().setUp()
        raw = yaml.safe_load(CONFIG.read_text(encoding='utf-8'))['job_supervisor']; raw['enabled'] = True
        self.sup = JobSupervisor(SupervisorJobStore(self.root / 'jobs', self.audit), SupervisorConfig(raw), audit=self.audit,
                                 clock=self.clock.now, monotonic=self.clock.monotonic, pass_gate=lambda job, v: [])

    def start(self, role='reviewer', worker='w1'):
        job = self.sup.create_job(contract(), requested_role=role)
        self.sup.enqueue(job['job_id']); self.sup.claim(worker, [role]); self.sup.confirm_start(job['job_id'], worker)
        return job['job_id']

    def stall(self, job_id, worker='w1'):
        self.sup.reap()
        for _ in range(int(self.sup.config.stall_after_s / self.sup.config.heartbeat_interval_s) + 2):
            self.clock.advance(self.sup.config.heartbeat_interval_s); self.sup.heartbeat(job_id, worker)
        self.sup.reap()

    def fix(self, job_id):
        return repair_job(self.sup, self.cm, job_id, task='continue the work', checkpoint_source=self.checkpoint_source())

    def test_stalled_job_gets_new_context_and_resumes_as_a_new_attempt_of_the_same_job(self):
        job_id = self.start(); self.stall(job_id)
        stalled = self.sup.store.load(job_id)
        self.assertEqual((stalled['state'], stalled['retry']['awaiting_change']), ('REWORK', 'context_manifest'))
        self.assertEqual(trigger_for(stalled), 'stagnation')
        plan = self.fix(job_id)
        fixed = self.sup.store.load(job_id)
        self.assertEqual(fixed['state'], 'REWORK')                                 # queueing stays an explicit step
        self.assertIsNone(fixed['retry']['awaiting_change'])
        self.assertEqual(fixed['retry']['last_manifest_id'], plan['new_manifest']['manifest_id'])
        self.assertEqual(fixed['pending_attempt_id'], plan['attempt_id_new'])
        self.sup.enqueue(job_id); self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        resumed = self.sup.store.load(job_id)
        attempt = resumed['attempt_log'][-1]
        self.assertEqual(resumed['job_id'], job_id)
        self.assertEqual((attempt['attempt_id'], attempt['context_manifest_id'], attempt['context_checkpoint_id']),
                         (plan['attempt_id_new'], plan['new_manifest']['manifest_id'], plan['checkpoint']['checkpoint_id']))
        self.assertEqual(len(resumed['attempt_log']), 2)
        self.assertNotIn('pending_attempt_id', resumed)
        self.assertEqual(resumed['attempt_log'][0]['outcome'], 'UNKNOWN')

    def test_context_overflow_is_repaired_too(self):
        job_id = self.start()
        self.sup.fail(job_id, 'w1', reason_code='CONTEXT_CAPACITY_UNQUALIFIED')
        self.assertEqual(trigger_for(self.sup.store.load(job_id)), 'context_overflow')
        plan = self.fix(job_id)
        self.assertFalse(plan['worker_change_requested'])
        self.assertEqual(self.sup.enqueue(job_id)['status'], 'queued')

    def test_a_stalled_mutating_job_is_dead_and_is_not_repaired_or_replayed(self):
        job_id = self.start('coder'); self.stall(job_id)
        self.assertEqual(self.sup.store.load(job_id)['state'], 'DEAD')
        with self.assertRaises(JobError) as ctx: self.fix(job_id)
        self.assertEqual(ctx.exception.code, 'no_change_awaited')
        self.assertEqual(self.cm.checkpoints.list_ids(job_id), [])

    def test_a_mutating_job_with_a_known_overflow_failure_can_be_repaired(self):
        job_id = self.start('coder')
        self.sup.fail(job_id, 'w1', reason_code='CONTEXT_CAPACITY_UNQUALIFIED')       # outcome known: nothing is in doubt
        self.assertTrue(self.fix(job_id)['possible'])

    def test_repair_limit_escalates_instead_of_looping(self):
        job_id = self.start()
        for round_ in range(3):
            if round_:
                self.sup.enqueue(job_id); self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
                self.sup.fail(job_id, 'w1', reason_code='CONTEXT_CAPACITY_UNQUALIFIED')
            else:
                self.sup.fail(job_id, 'w1', reason_code='CONTEXT_CAPACITY_UNQUALIFIED')
            if round_ < 2:
                self.fix(job_id)
            else:
                with self.assertRaises(ContextError) as ctx: self.fix(job_id)
                self.assertEqual(ctx.exception.detail, 'repair_limit_reached')
        stored = self.sup.store.load(job_id)
        self.assertEqual((stored['state'], stored['supervisor_flags']['escalated_to']), ('BLOCKED', 'guppi'))
        self.assertIn('context_repair_failed:repair_not_possible', stored['last_error']['reason_code'])

    def test_repair_without_awaiting_change_is_refused(self):
        job_id = self.start()
        with self.assertRaises(JobError) as ctx: self.fix(job_id)
        self.assertEqual(ctx.exception.code, 'no_change_awaited')

    def test_unusable_checkpoint_pin_escalates(self):
        job_id = self.start(); self.sup.fail(job_id, 'w1', reason_code='CONTEXT_CAPACITY_UNQUALIFIED')
        bad = self.checkpoint_source(pins=[{'kind': 'hash', 'ref': {'artifact_id': 'ART-NOPE0000'}, 'digest': 'x'}])
        with self.assertRaises(ContextError): repair_job(self.sup, self.cm, job_id, task='t', checkpoint_source=bad)
        self.assertEqual(self.sup.store.load(job_id)['supervisor_flags']['escalated_to'], 'guppi')

    def test_golden_path_work_stalls_gets_repaired_and_finishes(self):
        job_id = self.start(); self.stall(job_id)
        self.fix(job_id)
        self.sup.enqueue(job_id); self.sup.claim('w1', ['reviewer']); self.sup.confirm_start(job_id, 'w1')
        self.sup.complete_step(job_id, 'w1', 'TESTING'); self.sup.complete_step(job_id, 'w1', 'VERIFYING')
        done = self.sup.mark_passed(job_id, 'w1', {'result': 'PASS', 'verification_digest': 'd' * 64})
        self.assertEqual(done['job']['state'], 'READY_FOR_ACCEPTANCE')
        self.assertEqual([a['outcome'] for a in done['job']['attempt_log']], ['UNKNOWN', 'SUCCEEDED'])
        self.assertTrue(self.audit.verify_chain())

    def test_escalate_helper(self):
        job_id = self.start(); self.sup.fail(job_id, 'w1', reason_code='CONTEXT_CAPACITY_UNQUALIFIED')
        with self.assertRaises(JobError) as ctx: self.sup.escalate(job_id, to='nobody', reason='x')
        self.assertEqual(ctx.exception.code, 'invalid_escalation_target')
        job = self.sup.escalate(job_id, to='captain', reason='needs a human')
        self.assertEqual((job['state'], job['supervisor_flags']['escalated_to']), ('BLOCKED', 'captain'))
        done = self.sup.create_job(contract(), requested_role='reviewer'); self.sup.cancel(done['job_id'], requested_by='t', reason='r')
        with self.assertRaises(JobError) as ctx: self.sup.escalate(done['job_id'], to='guppi', reason='x')
        self.assertEqual(ctx.exception.code, 'already_final')

    def test_explicit_attempt_id_still_wins_over_a_prepared_one(self):
        job_id = self.start(); self.sup.fail(job_id, 'w1', reason_code='CONTEXT_CAPACITY_UNQUALIFIED'); self.fix(job_id)
        self.sup.enqueue(job_id); self.sup.claim('w1', ['reviewer'])
        self.sup.confirm_start(job_id, 'w1', attempt_id='ATT-EXPLICIT')
        self.assertEqual(self.sup.store.load(job_id)['attempt_log'][-1]['attempt_id'], 'ATT-EXPLICIT')


class BoundaryTests(unittest.TestCase):
    SRC = RUNTIME / 'src' / 'guppi_runtime'

    def test_modules_name_no_provider_or_model(self):
        for name in ('jobs/context_assembly.py', 'jobs/job_repair.py'):
            source = (self.SRC / name).read_text(encoding='utf-8').lower()
            for word in ('lm-studio', 'lmstudio', 'llama', 'qwen', 'kev', 'openai', 'anthropic'):
                self.assertNotRegex(source, rf'\b{re.escape(word)}\b', f'{name}:{word}')

    def test_context_assembly_does_not_touch_job_state_or_rights(self):
        source = (self.SRC / 'jobs' / 'context_assembly.py').read_text(encoding='utf-8')
        for forbidden in ('.transition(', 'JobSupervisor', 'DevelopmentJobStore', 'guard.approve', 'supply_change', 'enqueue('):
            self.assertNotIn(forbidden, source)

    def test_job_repair_never_queues_or_cancels_by_itself(self):
        source = (self.SRC / 'jobs' / 'job_repair.py').read_text(encoding='utf-8')
        for forbidden in ('.enqueue(', '.cancel(', '.claim(', '.fail(', 'guard'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
