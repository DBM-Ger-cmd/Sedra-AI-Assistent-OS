"""Phase 3: Context Manager v1. Mechanics only: no model, fake provider usage, fake clock."""
import importlib
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from guppi_runtime.artifacts import ArtifactStore
from guppi_runtime.audit import AuditLog
from guppi_runtime.context_budget import ContextBudgetManager
from guppi_runtime.context_manager import (ContextConfig, ContextError, ContextManager, collect_pins, make_piece, redact_text, score_piece)
from guppi_runtime.development_evidence import DevelopmentEvidenceStore
from guppi_runtime.models.openai_local import normalize_usage
from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
CONFIG = RUNTIME / 'config' / 'job_supervisor.yaml'
ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
JOB = 'SDJ-0123456789AB'


def raw_config(**overrides):
    raw = yaml.safe_load(CONFIG.read_text(encoding='utf-8'))['context_manager']
    raw['enabled'] = True
    for key, value in overrides.items():
        raw[key] = {**raw[key], **value} if isinstance(value, dict) and isinstance(raw.get(key), dict) else value
    return raw


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        self.audit = AuditLog(self.root / 'audit.jsonl')
        self.artifacts = ArtifactStore(self.root / 'artifacts', self.audit)
        self.evidence = DevelopmentEvidenceStore(self.root / 'evidence.jsonl', self.audit)
        self.cm = self.make()

    def make(self, **overrides):
        return ContextManager(self.root, ContextConfig(raw_config(**overrides)), artifacts=self.artifacts, audit=self.audit,
                              evidence_store=self.evidence, clock=lambda: self.now)

    def events(self):
        path = self.root / 'audit.jsonl'      # the audit file only exists after the first event
        return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()] if path.exists() else []
    def types(self): return [e['event_type'] for e in self.events()]


class ConfigTests(unittest.TestCase):
    def test_shipped_config_is_valid_and_off_by_default(self):
        config = ContextConfig.load(CONFIG)
        self.assertFalse(config.enabled)
        self.assertEqual(config.watermarks, {'green': 0.55, 'yellow': 0.70, 'orange': 0.85})
        self.assertEqual(config.inline_max_tokens, 1500)

    def test_invalid_values_refuse_start(self):
        bad = [dict(watermarks={'green': 0.9, 'yellow': 0.7, 'orange': 0.85}), dict(estimator={'safety_factor': 0.9}),
               dict(estimator={'code_chars_per_token': 0}), dict(tool_output_inline_max_tokens=0), dict(checkpoint_max_tokens=5),
               dict(enabled='yes'), dict(default_context_window=100), dict(relevance_weights={'task': -1}),
               dict(artifact_read_max_bytes=True)]
        for overrides in bad:
            with self.assertRaises(ValueError, msg=str(overrides)):
                ContextConfig(raw_config(**overrides))

    def test_missing_file_is_reported(self):
        with self.assertRaises(ValueError):
            ContextConfig.load(Path(tempfile.gettempdir()) / 'nope_context.yaml')

    def test_runtime_wires_it_off_and_reports_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            self.assertIsNotNone(rt.context_manager)
            self.assertFalse(rt.context_manager.enabled)
            self.assertFalse(rt.boot()['context_manager']['enabled'])
            self.assertEqual(rt.context_status()['jobs'], [])


class EstimatorTests(Base):
    def test_estimate_is_pessimistic_and_counts_characters_not_bytes(self):
        text = 'a' * 350
        self.assertGreaterEqual(self.cm.estimate(text), 100 * 1.0)       # 350 / 3.5
        self.assertIn(self.cm.estimate(text), (115, 116))                 # ceil(100 * 1.15), float rounding either way
        self.assertEqual(self.cm.estimate('ä€😀' * 100, kind='prose'), self.cm.estimate('abc' * 100, kind='prose'))   # same character count, not bytes
        self.assertEqual(self.cm.estimator.detect_kind('ä€😀' * 100), 'code')              # symbols look like code: the denser, safer estimate

    def test_code_is_estimated_denser_than_prose(self):
        code = '{"a":[1,2,3],"b":{"c":"d"}}' * 50
        prose = 'the quick brown fox jumps over the lazy dog ' * 30
        self.assertEqual(self.cm.estimator.detect_kind(code), 'code')
        self.assertEqual(self.cm.estimator.detect_kind(prose), 'prose')
        self.assertGreater(self.cm.estimate(code[:1000]), self.cm.estimate(prose[:1000]))

    def test_messages_include_overhead(self):
        msgs = [{'role': 'user', 'content': 'x' * 35}, {'role': 'assistant', 'content': 'y' * 35}]
        detail = self.cm.estimator.estimate_messages(msgs)
        self.assertAlmostEqual(detail['raw_units'], self.cm.estimator.REQUEST_OVERHEAD + 2 * (10 + self.cm.estimator.MESSAGE_OVERHEAD))
        self.assertGreaterEqual(detail['estimate'], detail['raw_units'])
        with self.assertRaises(ContextError): self.cm.estimator.estimate_messages('not a list')

    def test_estimate_is_never_below_provider_usage_in_the_fake_cases(self):
        for chars, usage in ((350, 90), (3500, 1000), (35, 12)):
            self.assertGreaterEqual(self.cm.estimate('x' * chars), usage)

    def test_calibration_raises_at_once_and_relaxes_only_after_enough_samples_never_below_worst(self):
        est = self.cm.estimator
        self.assertEqual(est.factor('m'), 1.15)
        est.observe('m', 100.0, 140)                       # ratio 1.4 > safety factor
        self.assertEqual(est.factor('m'), 1.4)             # raised immediately
        for _ in range(25): est.observe('m', 100.0, 90)    # many easy samples
        self.assertGreaterEqual(est.factor('m'), 1.4)      # worst measurement still respected
        est2 = self.make().estimator
        for _ in range(25): est2.observe('easy', 100.0, 80)
        self.assertLess(est2.factor('easy'), 1.15)         # relaxed only after calibrate_after samples
        self.assertGreaterEqual(est2.factor('easy'), 1.0)

    def test_calibration_is_persisted_per_model(self):
        self.cm.estimator.observe('persist-me', 100.0, 130)
        again = self.make()
        self.assertEqual(again.estimator.factor('persist-me'), 1.3)
        self.assertEqual(again.estimator.factor('other'), 1.15)

    def test_calibration_ignores_unusable_measurements(self):
        est = self.cm.estimator
        for args in (('m', 0.0, 10), ('m', 10.0, -1), ('m', 10.0, 'x'), (None, 10.0, 10)):
            self.assertIsNone(est.observe(*args))
        self.assertEqual(est.factor('m'), 1.15)

    def test_unusable_calibration_file_falls_back_to_defaults(self):
        (self.root / 'context_metrics' / 'calibration.json').write_text('{broken', encoding='utf-8')
        self.assertEqual(self.make().estimator.factor('m'), 1.15)

    def test_non_text_input_is_refused(self):
        with self.assertRaises(ContextError): self.cm.estimate(123)


class MetricsTests(Base):
    def test_provider_usage_is_recorded_exactly(self):
        record = self.cm.record_usage(JOB, 'ATT-1', messages=[{'role': 'user', 'content': 'x' * 3500}], usage={'input_tokens': 1200, 'output_tokens': 300},
                                      model_ref='p:m', role='coder', context_window=8192)
        self.assertEqual((record['input_tokens'], record['output_tokens'], record['usage_source']), (1200, 300, 'provider'))
        self.assertAlmostEqual(record['peak_fill'], 1500 / 8192)
        self.assertGreater(record['estimator_error_ratio'], 0)

    def test_without_usage_the_estimate_is_stored_and_labelled(self):
        record = self.cm.record_usage(JOB, 'ATT-1', messages=[{'role': 'user', 'content': 'x' * 350}], model_ref='p:m')
        self.assertEqual(record['usage_source'], 'estimate')
        self.assertIsNone(record['output_tokens'])            # unknown, not zero
        self.assertGreater(record['input_tokens'], 0)
        self.assertIsNone(record['estimator_error_ratio'])

    def test_peak_fill_is_the_maximum_over_attempts(self):
        for n, tokens in enumerate((1000, 4000, 2000), 1):
            self.cm.record_usage(JOB, f'ATT-{n}', usage={'input_tokens': tokens, 'output_tokens': 0}, model_ref='p:m', context_window=8000)
        self.assertAlmostEqual(self.cm.metrics.summary(JOB)['peak_fill'], 0.5)

    def test_usage_calibrates_the_estimator(self):
        self.cm.record_usage(JOB, 'ATT-1', messages=[{'role': 'user', 'content': 'x' * 350}], usage={'input_tokens': 500, 'output_tokens': 1}, model_ref='p:m')
        self.assertGreater(self.cm.estimator.factor('p:m'), 1.15)

    def test_exactly_one_audit_event_per_job_however_often_it_finishes(self):
        for n in range(3): self.cm.record_usage(JOB, f'ATT-{n}', usage={'input_tokens': 10, 'output_tokens': 5}, model_ref='p:m')
        self.assertIsNotNone(self.cm.metrics.finish_job(JOB))
        self.assertIsNone(self.cm.metrics.finish_job(JOB))
        self.assertEqual(self.types().count('CONTEXT_METRICS_SUMMARY'), 1)
        payload = [e for e in self.events() if e['event_type'] == 'CONTEXT_METRICS_SUMMARY'][0]['payload']
        self.assertEqual((payload['input_tokens'], payload['output_tokens'], payload['attempts']), (30, 15, 3))

    def test_metrics_stay_out_of_the_audit_chain(self):
        count = len(self.events())
        for n in range(20): self.cm.record_usage(JOB, f'ATT-{n}', usage={'input_tokens': 1, 'output_tokens': 1}, model_ref='p:m')
        self.assertEqual(len(self.events()), count)
        self.assertTrue(self.audit.verify_chain())

    def test_unknown_counter_and_unsafe_ids_are_refused(self):
        with self.assertRaises(ContextError): self.cm.metrics.bump(JOB, 'A', bogus=1)
        for bad in ('../x', 'a b', '', 'x' * 65, 'a/b'):
            with self.assertRaises(ContextError): self.cm.metrics.path(bad)

    def test_concurrent_writers_lose_no_lines(self):
        def run(n):
            for i in range(20): self.cm.record_usage(JOB, f'ATT-{n}-{i}', usage={'input_tokens': 1, 'output_tokens': 1}, model_ref='p:m')
        threads = [threading.Thread(target=run, args=(n,)) for n in range(6)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(self.cm.metrics.summary(JOB)['attempts'], 120)

    def test_damaged_metric_line_does_not_break_the_summary(self):
        self.cm.record_usage(JOB, 'ATT-1', usage={'input_tokens': 5, 'output_tokens': 5}, model_ref='p:m')
        with self.cm.metrics.path(JOB).open('a', encoding='utf-8') as f: f.write('{not json\n')
        self.assertEqual(self.cm.metrics.summary(JOB)['attempts'], 1)

    def test_normalize_usage_never_guesses(self):
        self.assertEqual(normalize_usage({'prompt_tokens': 7, 'completion_tokens': 3}), {'input_tokens': 7, 'output_tokens': 3})
        self.assertEqual(normalize_usage({'prompt_tokens': 7, 'completion_tokens': 3, 'prompt_tokens_details': {'cached_tokens': 2}})['cached_tokens'], 2)
        for bad in (None, {}, {'prompt_tokens': '7', 'completion_tokens': 3}, {'prompt_tokens': -1, 'completion_tokens': 3}, {'prompt_tokens': True, 'completion_tokens': 1}, 'x'):
            self.assertIsNone(normalize_usage(bad))


class BudgetTests(Base):
    def test_window_is_the_smallest_known_limit(self):
        b = self.cm.resolve_budget(model_window=32768, hardware_effective_max=8192, runtime_loaded=16384)
        self.assertEqual((b['context_window'], b['budget_source']), (8192, 'model_pass'))
        b = self.cm.resolve_budget(model_window=4096, hardware_effective_max=8192)
        self.assertEqual((b['context_window'], b['budget_source']), (4096, 'model'))
        b = self.cm.resolve_budget(model_window=32768, runtime_loaded=4096)
        self.assertEqual(b['budget_source'], 'runtime')
        self.assertEqual(b['window_inputs'], {'model': 32768, 'runtime': 4096})

    def test_unknown_window_falls_back_visibly_or_fails_when_strict(self):
        b = self.cm.resolve_budget()
        self.assertEqual((b['context_window'], b['budget_source']), (8192, 'default'))
        with self.assertRaises(ContextError) as ctx: self.cm.resolve_budget(strict=True)
        self.assertEqual(ctx.exception.code, 'context_window_unknown')

    def test_budget_is_the_existing_formula(self):
        ours = self.cm.resolve_budget(model_window=8192)
        reference = ContextBudgetManager().build_budget(8192)
        for key, value in reference.items():
            self.assertEqual(ours[key], value, key)

    def test_sub_budgets_sum_within_the_window(self):
        b = self.cm.resolve_budget(model_window=8192)
        subs = sum(b[k] for k in ('system_budget', 'project_context_budget', 'task_context_budget', 'tool_result_budget', 'recent_history_budget'))
        self.assertLessEqual(subs + b['reserved_output_tokens'] + b['safety_margin'], b['context_window'])

    def test_invalid_inputs_are_refused(self):
        for kwargs in (dict(model_window=0), dict(model_window='8192'), dict(hardware_effective_max=-5), dict(model_window=100)):
            with self.assertRaises(ContextError, msg=str(kwargs)): self.cm.resolve_budget(**kwargs)

    def test_hardware_pass_result_is_used(self):
        pass_result = {'context_limits': {'model_maximum': 32768, 'safe_maximum': 4096, 'recommended': 4096, 'effective_maximum': 4096}}
        b = self.cm.resolver.from_pass(pass_result, model_window=32768)
        self.assertEqual((b['context_window'], b['budget_source']), (4096, 'model_pass'))
        self.assertEqual(self.cm.resolver.from_pass({}, model_window=16384)['budget_source'], 'model')

    def test_self_development_marks_a_guessed_window_and_accepts_a_resolved_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            guessed = rt.self_development.start('budget_probe_a', evidence=[{'source': 't'}])['job']['context_manifest']['budget']
            self.assertEqual(guessed['budget_source'], 'default')
            explicit = rt.self_development.start('budget_probe_b', evidence=[{'source': 't'}], context_window=4096)['job']['context_manifest']['budget']
            self.assertEqual((explicit['budget_source'], explicit['context_window']), ('caller', 4096))
            resolved = rt.context_manager.resolve_budget(model_window=16384, hardware_effective_max=8192)
            job = rt.self_development.start('budget_probe_c', evidence=[{'source': 't'}], budget=resolved)['job']
            self.assertEqual(job['context_manifest']['budget']['budget_source'], 'model_pass')
            with self.assertRaises(ValueError): rt.self_development.start('budget_probe_d', evidence=[{'source': 't'}], budget={'max_input_tokens': 0})


class OffloadTests(Base):
    def big_log(self, lines=5000, errors=(40, 4000)):
        out = []
        for i in range(lines):
            out.append(f'line {i}: build step ok')
        for e in errors:
            out[e] = f'line {e}: ERROR module X failed token=SECRET123'
        return '\n'.join(out) + '\n'

    def test_small_output_stays_inline_and_is_redacted(self):
        out = self.cm.process_tool_output(JOB, 'A1', {'tool': 'shell'}, 'ok\npassword = hunter2\n')
        self.assertTrue(out['inline'])
        self.assertNotIn('hunter2', out['text'])
        self.assertIn('***REDACTED***', out['text'])
        self.assertEqual(self.artifacts.list(), [])

    def test_large_output_is_stored_in_full_and_replaced_by_a_summary(self):
        log = self.big_log()
        out = self.cm.process_tool_output(JOB, 'A1', {'tool': 'shell', 'operation': 'run'}, log)
        self.assertFalse(out['inline'])
        record = out['record']
        self.assertEqual(record['bytes'], len(log.encode()))
        stored = Path(self.artifacts.get(record['artifact_id'])['path']).read_bytes()
        self.assertEqual(stored, log.encode())                        # the original is untouched, secret included
        self.assertEqual(record['sha256'], __import__('hashlib').sha256(log.encode()).hexdigest())
        self.assertEqual(record['summary']['counts']['errors'], 2)
        self.assertEqual(record['summary']['first_error']['line'], 41)
        self.assertEqual(record['summary_method'], 'deterministic')
        self.assertLess(out['tokens'], self.cm.config.inline_max_tokens)
        self.assertNotIn('SECRET123', out['text'])                    # nothing secret goes toward a model
        self.assertTrue(record['redacted'])
        self.assertGreater(record['tokens_saved_estimate'], 1000)

    def test_relevant_ranges_are_exact_byte_ranges_that_read_back(self):
        log = self.big_log()
        record = self.cm.process_tool_output(JOB, 'A1', {'tool': 'shell'}, log)['record']
        rng = record['summary']['relevant_ranges'][0]
        chunk = self.cm.read_artifact_range(record['artifact_id'], rng['start'], rng['end'] - rng['start']).decode()
        self.assertIn('ERROR module X failed', chunk)
        self.assertEqual(chunk, log.encode()[rng['start']:rng['end']].decode())

    def test_summary_flags_truncation_when_more_errors_than_ranges(self):
        log = '\n'.join(f'ERROR {i}' for i in range(30)) + '\n' + 'filler ' * 20000
        record = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, log)
        self.assertTrue(record['summary']['truncated'])
        self.assertIn('summary_covers_only_first_errors=true', self.cm.offloader.render_summary(record))
        self.assertLessEqual(len(record['summary']['relevant_ranges']), 5)

    def test_clean_output_summary_does_not_invent_findings(self):
        record = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'all good\n' * 10000)
        self.assertEqual((record['summary']['status'], record['summary']['first_error'], record['summary']['relevant_ranges']), ('ok', None, []))

    def test_threshold_shrinks_with_the_watermark(self):
        t = [self.cm.offloader.threshold(s) for s in ('GREEN', 'YELLOW', 'ORANGE', 'RED')]
        self.assertEqual(t, [1500, 750, 375, 187])
        text = 'word ' * 1200                     # ~1,700 estimated tokens... inline in no state above GREEN limit? compute below
        green = self.cm.process_tool_output(JOB, 'A1', {'tool': 't'}, 'x' * 3000, state='GREEN')
        red = self.cm.process_tool_output(JOB, 'A1', {'tool': 't'}, 'x' * 3000, state='RED')
        self.assertTrue(green['inline']); self.assertFalse(red['inline'])
        with self.assertRaises(ContextError): self.cm.offloader.threshold('PURPLE')

    def test_oversize_output_is_refused_not_truncated(self):
        small = self.make()
        small.config.max_offload_bytes = 2048
        with self.assertRaises(ContextError) as ctx: small.offloader.offload(JOB, 'A1', {'tool': 't'}, 'x' * 5000)
        self.assertEqual((ctx.exception.code, ctx.exception.detail), ('offload_failed', 'output_exceeds_max_offload_bytes'))

    def test_binary_and_non_utf8_payloads_are_stored_exactly(self):
        raw = b'\xff\xfe\x00binary\nERROR here\n' + bytes(range(256)) * 50
        record = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, raw)
        self.assertEqual(Path(self.artifacts.get(record['artifact_id'])['path']).read_bytes(), raw)
        with self.assertRaises(ContextError): self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 12345)

    def test_read_range_is_bounded_and_validated(self):
        record = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'abcdefghij' * 20000)
        aid = record['artifact_id']
        self.assertEqual(self.cm.read_artifact_range(aid, 3, 4), b'defg')
        self.assertEqual(self.cm.read_artifact_range(aid, 199998, 100), b'ij')          # clipped at the end
        for args in ((aid, 0, self.cm.config.artifact_read_max_bytes + 1), (aid, -1, 5), (aid, 0, 0), (aid, '0', 5)):
            with self.assertRaises(ContextError, msg=str(args)): self.cm.read_artifact_range(*args)
        with self.assertRaises(ContextError) as ctx: self.cm.read_artifact_range('ART-NOPE0000', 0, 5)
        self.assertEqual(ctx.exception.code, 'piece_not_found')

    def test_tampered_artifact_is_detected(self):
        record = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'abc' * 5000)
        Path(self.artifacts.get(record['artifact_id'])['path']).write_bytes(b'tampered')
        with self.assertRaises(ContextError) as ctx: self.cm.read_artifact_range(record['artifact_id'], 0, 5)
        self.assertEqual(ctx.exception.code, 'artifact_integrity_failed')

    def test_artifact_outside_the_store_is_not_readable(self):
        outside = self.root / 'secret.txt'; outside.write_text('top secret', encoding='utf-8')
        rec = self.artifacts.register('M-1', outside)
        with self.assertRaises(ContextError) as ctx: self.cm.read_artifact_range(rec['artifact_id'], 0, 5)
        self.assertEqual(ctx.exception.code, 'policy_denied')

    def test_manifest_allow_list_is_enforced(self):
        a = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'one' * 5000)['artifact_id']
        b = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'two' * 5000)['artifact_id']
        self.assertEqual(self.cm.read_artifact_range(a, 0, 3, allowed_artifacts={a}), b'one')
        with self.assertRaises(ContextError) as ctx: self.cm.read_artifact_range(b, 0, 3, allowed_artifacts={a})
        self.assertEqual(ctx.exception.code, 'policy_denied')

    def test_prompt_reads_are_redacted_but_raw_reads_are_exact(self):
        aid = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'api_key: ABC123\n' + 'x' * 8000)['artifact_id']
        self.assertIn(b'ABC123', self.cm.read_artifact_range(aid, 0, 40))
        self.assertNotIn('ABC123', self.cm.read_artifact_range(aid, 0, 40, for_prompt=True))

    def test_offload_bumps_the_counters(self):
        self.cm.process_tool_output(JOB, 'A1', {'tool': 't'}, self.big_log())
        s = self.cm.metrics.summary(JOB)
        self.assertGreater(s['tool_output_offloaded_bytes'], 0)
        self.assertGreater(s['estimated_tokens_saved'], 0)

    def test_artifact_index_survives_concurrent_registration(self):
        paths = []
        for n in range(8):
            p = self.root / f'f{n}.txt'; p.write_text(str(n), encoding='utf-8'); paths.append(p)
        threads = [threading.Thread(target=lambda p=p: [self.artifacts.register('M-1', p, job_id=JOB) for _ in range(5)]) for p in paths]
        for t in threads: t.start()
        for t in threads: t.join()
        records = self.artifacts.list('M-1')
        self.assertEqual(len(records), 40)
        self.assertEqual(len({r['artifact_id'] for r in records}), 40)
        self.assertTrue(all(r['job_id'] == JOB for r in records))

    def test_old_artifact_records_without_job_id_still_work(self):
        p = self.root / 'old.txt'; p.write_text('x', encoding='utf-8')
        self.assertNotIn('job_id', self.artifacts.register('M-2', p))


class RedactionTests(unittest.TestCase):
    def test_shapes(self):
        for text in ('password=abc', 'PASSWORD: abc', '"api_key": "abc"', "token = 'abc'", 'credentials=abc,next', 'secret:abc'):
            self.assertNotIn('abc', redact_text(text), text)
        self.assertEqual(redact_text('nothing sensitive here'), 'nothing sensitive here')
        self.assertEqual(redact_text('tokenizer = bpe'), 'tokenizer = bpe')


class CheckpointTests(Base):
    def evidence_record(self, status='PASS', candidate='CAND-1'):
        return self.evidence.add('candidate_tests', job_id=JOB, candidate_id=candidate, payload={'status': status}, trust_level='deterministic')

    def sources(self):
        rec = self.evidence_record()
        art = self.cm.offloader.offload(JOB, 'A1', {'tool': 't'}, 'log\n' * 4000)
        return rec, art

    def test_checkpoint_roundtrip_and_digest(self):
        rec, art = self.sources()
        pins = [{'kind': 'test_result', 'ref': {'evidence_id': rec['evidence_id']}, 'digest': rec['evidence_hash'], 'value': 'PASS'},
                {'kind': 'path', 'ref': {'path': 'src/app.py'}, 'digest': 'a' * 64, 'value': 'src/app.py'}]
        cp = self.cm.checkpoint(JOB, 'A1', goal='make tests pass', changed=[{'path': 'src/app.py', 'sha256': 'a' * 64}],
                                artifacts=[art['artifact_id']], tests=[{'id': 't1', 'result': 'PASS', 'evidence_id': rec['evidence_id']}],
                                open_errors=[{'class': 'validation_failure', 'summary': 'x'}], decisions=[{'text': 'use lock', 'decided_by': 'guppi', 'ref': 'D1'}],
                                next_steps=['review'], permission_state={'level': 2, 'tokens_used': ['APR-1'], 'gates_pending': []}, pins=pins)
        loaded = self.cm.checkpoints.load(JOB, cp['checkpoint_id'])
        self.assertEqual(loaded, cp)
        self.assertEqual(len(loaded['pins']), 2)
        self.assertEqual(self.cm.checkpoints.latest(JOB)['checkpoint_id'], cp['checkpoint_id'])
        self.assertIn('CONTEXT_CHECKPOINT_WRITTEN', self.types())
        self.assertEqual(self.cm.metrics.summary(JOB)['checkpoint_count'], 1)

    def test_tampered_checkpoint_is_detected(self):
        cp = self.cm.checkpoint(JOB, 'A1', goal='g')
        path = self.root / 'context_checkpoints' / JOB / f"{cp['checkpoint_id']}.json"
        data = json.loads(path.read_text(encoding='utf-8')); data['goal'] = 'something else'
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ContextError) as ctx: self.cm.checkpoints.load(JOB, cp['checkpoint_id'])
        self.assertEqual(ctx.exception.code, 'checkpoint_digest_mismatch')
        self.assertIsNone(self.cm.checkpoints.latest(JOB))                  # a damaged checkpoint is not offered as "latest"

    def test_pin_without_a_checkable_source_is_refused(self):
        bad_pins = [{'kind': 'test_result', 'ref': {}, 'digest': 'x'}, {'kind': 'nonsense', 'ref': {'path': 'p'}, 'digest': 'x'},
                    {'kind': 'path', 'ref': {'path': 'p'}, 'digest': ''}, {'kind': 'path', 'ref': {'evidence_id': 'EVD-NOPE'}, 'digest': 'x'},
                    {'kind': 'hash', 'ref': {'artifact_id': 'ART-NOPE0000'}, 'digest': 'x'}, 'not a dict']
        for pin in bad_pins:
            with self.assertRaises(ContextError, msg=str(pin)) as ctx: self.cm.checkpoint(JOB, 'A1', goal='g', pins=[pin])
            self.assertEqual(ctx.exception.code, 'pin_missing_source')

    def test_oversize_checkpoint_shortens_free_text_but_never_pins_or_tests(self):
        rec = self.evidence_record()
        pins = [{'kind': 'test_result', 'ref': {'evidence_id': rec['evidence_id']}, 'digest': rec['evidence_hash'], 'value': 'PASS'}]
        tests = [{'id': f't{i}', 'result': 'PASS', 'evidence_id': rec['evidence_id']} for i in range(5)]
        cp = self.cm.checkpoint(JOB, 'A1', goal='g' * 500, pins=pins, tests=tests, next_steps=['step ' * 30] * 30,
                                decisions=[{'text': 'd' * 300, 'decided_by': 'x', 'ref': 'r'}] * 3, permission_state={'level': 2})
        self.assertLessEqual(self.cm.checkpoints._tokens(cp), self.cm.config.checkpoint_max_tokens + 200)
        self.assertEqual(len(cp['pins']), 1)
        self.assertEqual(len(cp['tests']), 5)
        self.assertEqual(cp['permission_state'], {'level': 2})

    def test_checkpoint_that_cannot_fit_without_cutting_facts_is_an_error(self):
        small = self.make(checkpoint_max_tokens=200)
        rec = self.evidence_record()
        tests = [{'id': f't{i}', 'result': 'PASS', 'evidence_id': rec['evidence_id'], 'note': 'n' * 100} for i in range(40)]
        with self.assertRaises(ContextError) as ctx: small.checkpoint(JOB, 'A1', goal='g', tests=tests)
        self.assertEqual(ctx.exception.code, 'checkpoint_too_large')
        self.assertEqual(small.checkpoints.list_ids(JOB), [])               # nothing half-written

    def test_invalid_checkpoint_input(self):
        for kwargs in (dict(goal=''), dict(goal=None), dict(goal='g', tests='no'), dict(goal='g', pins='no'), dict(goal='g', next_steps=[1, 2][:0] + [object()])):
            with self.assertRaises(ContextError, msg=str(kwargs)): self.cm.checkpoint(JOB, 'A1', **kwargs)
        with self.assertRaises(ContextError): self.cm.checkpoint('../evil', 'A1', goal='g')

    def test_collect_pins_uses_structured_sources_only(self):
        rec = self.evidence_record()
        self.evidence.add('model_view', job_id=JOB, candidate_id='CAND-1', payload={'status': 'PASS'}, trust_level='model_assessment')
        job = {'job_id': JOB, 'contract': {'contract_digest': 'c' * 64, 'contract_id': 'DEV-1', 'permission_level': 2},
               'policy_hash': 'p' * 64, 'candidate': {'candidate_hash': 'h' * 64, 'candidate_id': 'CAND-1'}}
        pins = collect_pins(job, evidence_records=self.evidence.list(JOB), approvals=[{'token_id': 'APR-1', 'action': 'candidate_accept'}, {}])
        kinds = sorted(p['kind'] for p in pins)
        self.assertEqual(kinds, ['approval', 'code_change', 'constraint', 'policy_hash', 'test_result'])
        self.assertEqual(len([p for p in pins if p['kind'] == 'test_result']), 1)   # the model assessment is no test result
        cp = self.cm.checkpoint(JOB, 'A1', goal='g', pins=pins)                    # and all of them pass validation
        self.assertEqual(len(cp['pins']), 5)


class WatermarkTests(Base):
    def budget(self): return self.cm.resolve_budget(model_window=8192)

    def pieces(self):
        out = [self.cm.piece('policy', 'never bypass the guard ' * 5, layer='L0', critical=True, safety=1),
               self.cm.piece('contract', 'goal and acceptance criteria ' * 10, layer='L1', critical=True),
               self.cm.piece('decision', 'open question ' * 10, layer='L3', decision=1),
               self.cm.piece('history_summary', 'old chatter ' * 200, layer='L4'),
               self.cm.piece('history_summary', 'older chatter ' * 200, layer='L4', created_at=(self.now - timedelta(hours=5)).isoformat()),
               self.cm.piece('step', 'finished work ' * 100, layer='L3', done=True),
               self.cm.piece('tool_output', 'ERROR line\n' + 'noise ' * 3000, layer='L5', task=1)]
        return out

    def test_states_and_actions_follow_the_budget_manager(self):
        b = self.budget(); mx = b['max_input_tokens']
        seen = {}
        for ratio in (0.50, 0.56, 0.71, 0.86):
            h = self.cm.health(int(mx * ratio), b)
            seen[h['state']] = h['actions']
        self.assertEqual(list(seen), ['GREEN', 'YELLOW', 'ORANGE', 'RED'])
        self.assertEqual(seen['GREEN'], [])
        self.assertIn('checkpoint', seen['ORANGE']); self.assertIn('context_rebuild', seen['RED'])

    def test_green_does_nothing(self):
        b = self.budget(); h = self.cm.health(10, b)
        out = self.cm.on_watermark(JOB, 'A1', h, pieces=self.pieces(), budget=b)
        self.assertEqual((out['protocol'], out['excluded']), ([], []))
        self.assertFalse(out['flags']['rebuild_required'])

    def test_orange_writes_a_checkpoint_compacts_and_offloads_for_real(self):
        b = self.budget(); pcs = self.pieces(); used = sum(p['tokens_est'] for p in pcs)
        h = self.cm.health(int(b['max_input_tokens'] * 0.75), b)
        self.assertEqual(h['state'], 'ORANGE')
        out = self.cm.on_watermark(JOB, 'A1', h, pieces=pcs, budget=b,
                                   checkpoint_source=lambda: {'goal': 'finish the task', 'next_steps': ['continue']})
        by = {e['action']: e for e in out['protocol']}
        self.assertEqual(by['checkpoint']['status'], 'written')
        self.assertTrue(Path(self.root / 'context_checkpoints' / JOB / f"{by['checkpoint']['detail']}.json").exists())   # a file exists, not just a promise
        self.assertEqual(by['compact_completed_work']['status'], 'applied')
        self.assertNotIn('step', [p['kind'] for p in out['pieces']])
        self.assertEqual(by['artifact_offload']['detail'], 'offloaded 1')
        self.assertNotIn('tool_output', [p['kind'] for p in out['pieces']])
        summary = [p for p in out['pieces'] if p['kind'] == 'tool_summary'][0]
        self.assertIn('first_error line 1', summary['text'])
        self.assertEqual(len(self.artifacts.list(JOB)), 1)
        metrics = self.cm.metrics.summary(JOB)
        self.assertEqual((metrics['checkpoint_count'], metrics['compaction_count']), (1, 1))
        self.assertIn('CONTEXT_WATERMARK_ACTIONS', self.types())
        self.assertLess(sum(p['tokens_est'] for p in out['pieces']), used)

    def test_critical_pieces_survive_every_reaction(self):
        b = self.budget(); pcs = self.pieces()
        h = {'state': 'RED', 'actions': ['avoid_irrelevant_history', 'compact_completed_work', 'artifact_offload'], 'max_input_tokens': 200}
        out = self.cm.on_watermark(JOB, 'A1', h, pieces=pcs, budget={'max_input_tokens': 200})
        kinds = [p['kind'] for p in out['pieces']]
        self.assertIn('policy', kinds); self.assertIn('contract', kinds)
        self.assertTrue(all(e['reason'] in {'low_relevance', 'completed_work'} for e in out['excluded']))

    def test_least_relevant_pieces_go_first(self):
        fresh = self.cm.piece('history_summary', 'chatter ' * 100, layer='L4')
        old = self.cm.piece('history_summary', 'chatter ' * 100, layer='L4', created_at=(self.now - timedelta(hours=5)).isoformat())
        used = self.cm.piece('file_excerpt', 'code ' * 100, layer='L3', file=1, task=1)
        pcs = [fresh, old, used]
        kept, dropped = self.cm.trim_to_target(pcs, sum(p['tokens_est'] for p in pcs) - 10)
        self.assertEqual([d['piece_id'] for d in dropped], [old['piece_id']])      # old and unreferenced goes first
        self.assertEqual([p['piece_id'] for p in kept], [fresh['piece_id'], used['piece_id']])
        # a finished step is penalised and goes before an unfinished one of the same age
        done = self.cm.piece('step', 'finished ' * 100, done=True)
        open_ = self.cm.piece('step', 'finished ' * 100)
        _, dropped = self.cm.trim_to_target([open_, done], done['tokens_est'] + 1)
        self.assertEqual([d['piece_id'] for d in dropped], [done['piece_id']])

    def test_red_signals_rebuild_and_blocks_big_dumps(self):
        b = self.budget(); h = self.cm.health(b['max_input_tokens'], b)
        out = self.cm.on_watermark(JOB, 'A1', h, pieces=self.pieces(), budget=b, checkpoint_source=lambda: {'goal': 'g'})
        self.assertEqual(h['state'], 'RED')
        self.assertTrue(out['flags']['rebuild_required'])
        self.assertTrue(out['flags']['block_large_tool_dump'])
        self.assertTrue(out['flags']['fresh_context_requested'])
        self.assertEqual({e['action']: e['status'] for e in out['protocol']}['context_rebuild'], 'signalled')

    def test_missing_checkpoint_source_is_reported_not_faked(self):
        b = self.budget(); h = self.cm.health(int(b['max_input_tokens'] * 0.75), b)
        out = self.cm.on_watermark(JOB, 'A1', h, pieces=self.pieces(), budget=b)
        entry = [e for e in out['protocol'] if e['action'] == 'checkpoint'][0]
        self.assertEqual((entry['status'], entry['detail']), ('skipped', 'no_checkpoint_source'))
        self.assertEqual(self.cm.checkpoints.list_ids(JOB), [])

    def test_unknown_action_and_state_are_visible(self):
        out = self.cm.on_watermark(JOB, 'A1', {'state': 'YELLOW', 'actions': ['teleport'], 'max_input_tokens': 1000})
        self.assertEqual(out['protocol'][0]['status'], 'unknown_action')
        with self.assertRaises(ContextError): self.cm.on_watermark(JOB, 'A1', {'state': 'PURPLE', 'actions': []})

    def test_input_pieces_are_not_modified(self):
        pcs = self.pieces(); before = [dict(p) for p in pcs]
        h = {'state': 'ORANGE', 'actions': ['compact_completed_work', 'artifact_offload', 'avoid_irrelevant_history'], 'max_input_tokens': 500}
        self.cm.on_watermark(JOB, 'A1', h, pieces=pcs, budget={'max_input_tokens': 500})
        self.assertEqual(pcs, before)

    def test_health_reports_heuristic_ratios(self):
        b = self.budget(); pcs = self.pieces(); pcs.append(dict(pcs[0], piece_id='CPC-DUPLICATE0001'))
        h = self.cm.health(sum(p['tokens_est'] for p in pcs), b, pcs, last_checkpoint_at=(self.now - timedelta(seconds=90)).isoformat())
        self.assertEqual(h['method'], 'heuristic')
        self.assertGreater(h['tool_output_ratio'], 0.2)
        self.assertGreater(h['duplicate_ratio'], 0)
        self.assertEqual(h['unresolved_decision_count'], 1)
        self.assertEqual(h['last_checkpoint_age_s'], 90)
        self.assertTrue(h['stale_candidates'])
        self.assertNotIn(pcs[0]['piece_id'], h['stale_candidates'])        # critical pieces are never "stale"

    def test_score_parts_are_reported(self):
        s = score_piece(self.pieces()[2], self.cm.config.weights, self.now)
        self.assertEqual(set(s['parts']), {'task', 'file', 'decision', 'safety', 'pinned', 'recency', 'done_penalty'})
        self.assertEqual(s['parts']['decision'], 2)

    def test_pinned_pieces_are_critical(self):
        self.assertTrue(make_piece('note', 'x', pinned=True)['critical'])
        self.assertTrue(make_piece('pin', 'x')['critical'])
        self.assertFalse(make_piece('note', 'x')['critical'])
        with self.assertRaises(ContextError): make_piece('note', 'x', layer='L9')


class ControlMasterIntegrationTests(unittest.TestCase):
    def test_inference_is_measured_only_when_enabled_and_never_breaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)

            class FakeRouter:
                adapters = {}
                def choose(self, provider=None):
                    from types import SimpleNamespace
                    return SimpleNamespace(id='fake')
                def chat(self, mission_id, messages, **kw):
                    return {'provider': 'fake', 'model': 'tiny', 'content': 'hi', 'usage': {'input_tokens': 77, 'output_tokens': 5}}

            rt.control.model_router = FakeRouter()
            mission = {'identity': {'mission_id': 'M-ABCDEF12'}}
            request = {'action': 'model_inference', 'messages': [{'role': 'user', 'content': 'hello ' * 40}]}
            out = rt.control.execute(mission, request)
            self.assertEqual(out['status'], 'completed')
            self.assertEqual(rt.context_manager.metrics.lines('M-ABCDEF12'), [])           # flag off: nothing recorded
            rt.context_manager.config.enabled = True
            rt.control.execute(mission, request)
            lines = rt.context_manager.metrics.lines('M-ABCDEF12')
            self.assertEqual((lines[0]['input_tokens'], lines[0]['usage_source'], lines[0]['model_ref']), (77, 'provider', 'fake:tiny'))
            rt.context_manager.record_usage = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('disk full'))
            self.assertEqual(rt.control.execute(mission, request)['status'], 'completed')   # measuring failed, inference did not
            self.assertIn('CONTEXT_METRICS_FAILED', [json.loads(x)['event_type'] for x in rt.audit.path.read_text(encoding='utf-8').splitlines()])


class AtomicReplaceTests(unittest.TestCase):
    def test_transient_permission_error_is_retried_on_windows_only(self):
        from unittest.mock import patch
        from guppi_runtime import util
        calls = {'n': 0}

        def flaky(src, dst):
            calls['n'] += 1
            if calls['n'] < 3: raise PermissionError('held by scanner')

        with patch.object(util.os, 'replace', side_effect=flaky), patch.object(util.os, 'name', 'nt'), patch.object(util.time, 'sleep'):
            util._replace_with_retry('a', 'b')
        self.assertEqual(calls['n'], 3)
        with patch.object(util.os, 'replace', side_effect=PermissionError('x')), patch.object(util.os, 'name', 'posix'):
            with self.assertRaises(PermissionError): util._replace_with_retry('a', 'b')     # not retried elsewhere
        with patch.object(util.os, 'replace', side_effect=PermissionError('x')), patch.object(util.os, 'name', 'nt'), patch.object(util.time, 'sleep'):
            with self.assertRaises(PermissionError): util._replace_with_retry('a', 'b', attempts=3)   # gives up
        with patch.object(util.os, 'replace', side_effect=FileNotFoundError('x')):
            with self.assertRaises(FileNotFoundError): util._replace_with_retry('a', 'b')           # other errors are immediate


class BoundaryTests(unittest.TestCase):
    def test_module_names_no_provider_or_model(self):
        import re
        source = Path(importlib.import_module('guppi_runtime.context_manager').__file__).read_text(encoding='utf-8').lower()
        for word in ('lm-studio', 'lmstudio', 'llama', 'qwen', 'kev', 'openai', 'anthropic'):
            self.assertNotRegex(source, rf'\b{re.escape(word)}\b', word)

    def test_module_does_not_touch_job_state(self):
        source = Path(importlib.import_module('guppi_runtime.context_manager').__file__).read_text(encoding='utf-8')
        for forbidden in ('.transition(', 'JobSupervisor', 'DevelopmentJobStore', 'guard.approve'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
