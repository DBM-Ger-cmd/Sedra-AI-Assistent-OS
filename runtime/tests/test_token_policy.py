"""Phase 8c: what a model call should cost, and what it really cost."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.artifacts import ArtifactStore
from guppi_runtime.audit import AuditLog
from guppi_runtime.context_manager import ContextConfig, ContextManager
from guppi_runtime.job_worker import HandlerError, Worker, model_text_handler
from guppi_runtime.models.base import ModelAdapterError
from guppi_runtime.models.openai_local import OpenAICompatibleLocalAdapter
from guppi_runtime.token_policy import TokenBudgetError, TokenPolicy, TokenPolicyConfig
from test_job_worker import Base as WorkerBase
from test_model_loader import KEY
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]


def policy(**overrides):
    raw = {'enabled': True, 'min_output_tokens': 128, 'default': {'max_output_tokens': 1000, 'output_cap': 4000},
           'escalation': {'max_retries': 1, 'factor': 2},
           'roles': {'reviewer': {'reasoning_effort': 'none', 'max_output_tokens': 500, 'output_cap': 2000}, 'coder': {'max_output_tokens': 3000, 'output_cap': 9000}}}
    raw.update(overrides)
    return TokenPolicy(TokenPolicyConfig(raw))


class ConfigTest(unittest.TestCase):
    def test_shipped_file_is_valid_off_and_matches_the_measurement(self):
        config = TokenPolicyConfig.load(RUNTIME / 'config' / 'token_policy.yaml')
        self.assertFalse(config.enabled)
        self.assertEqual(config.roles['reviewer']['reasoning_effort'], 'none')
        self.assertIsNone(config.roles['coder']['reasoning_effort'])                      # judging and building keep their thinking
        self.assertEqual(TokenPolicyConfig({}).enabled, False)

    def test_invalid_values_refuse_start(self):
        for bad in ({'enabled': 'yes'}, {'default': {'reasoning_effort': 'max'}}, {'default': {'max_output_tokens': 10}},
                    {'default': {'max_output_tokens': 5000, 'output_cap': 4000}}, {'default': {'colour': 'red'}}, {'roles': {'x': 'y'}},
                    {'escalation': {'factor': 1}}, {'escalation': {'max_retries': -1}}, {'min_output_tokens': 0}, 'x'):
            with self.assertRaises(ValueError, msg=str(bad)): TokenPolicyConfig(bad)
        with self.assertRaises(ValueError): TokenPolicyConfig.load(Path(tempfile.gettempdir()) / 'nope_token_policy.yaml')

    def test_role_overrides_inherit_the_default(self):
        p = policy()
        self.assertEqual(p.for_role('reviewer'), {'reasoning_effort': 'none', 'reasoning_budget_tokens': None, 'max_output_tokens': 500, 'output_cap': 2000})
        self.assertEqual(p.for_role('coder')['reasoning_effort'], None)
        self.assertEqual(p.for_role('unknown_role')['max_output_tokens'], 1000)


class PlanTest(unittest.TestCase):
    def test_budget_is_the_role_value_clipped_to_what_the_window_has_left(self):
        p = policy()
        self.assertEqual(p.plan('reviewer', 1000, 8192)['max_tokens'], 500)
        plan = p.plan('coder', 7000, 8192)                                                   # only 1192 left
        self.assertEqual((plan['max_tokens'], plan['output_cap']), (1192, 1192))
        self.assertEqual(p.plan('reviewer', 1000, 8192)['reasoning_effort'], 'none')

    def test_input_that_fills_the_window_is_refused_not_sent(self):
        with self.assertRaises(TokenBudgetError) as ctx: policy().plan('coder', 8100, 8192)
        self.assertEqual(ctx.exception.code, 'context_overflow'); self.assertEqual(ctx.exception.detail['room'], 92)

    def test_overrides_and_bad_input(self):
        p = policy()
        self.assertEqual(p.plan('coder', 100, 8192, reasoning_effort='none')['reasoning_effort'], 'none')
        self.assertEqual(p.plan('coder', 100, 8192, max_output_tokens=200)['max_tokens'], 200)
        self.assertEqual(p.plan('coder', 100, 8192, max_output_tokens=20)['max_tokens'], 128)          # never below the minimum that can hold an answer
        with self.assertRaises(ValueError): p.plan('coder', 100, 8192, reasoning_effort='max')
        for bad in ((True, 8192), (-1, 8192), (10, 0), (10, None)):
            with self.assertRaises(TokenBudgetError): p.plan('coder', *bad)

    def test_escalation_is_bounded_by_attempts_cap_and_window(self):
        p = policy(); plan = p.plan('reviewer', 1000, 8192)
        bigger = p.escalate(plan, 0)
        self.assertEqual(bigger['max_tokens'], 1000); self.assertEqual(bigger['reasoning_effort'], 'none')
        self.assertIsNone(p.escalate(bigger, 1))                                              # one retry only
        capped = dict(plan, max_tokens=1900, output_cap=2000)
        self.assertEqual(p.escalate(capped, 0)['max_tokens'], 2000)
        self.assertIsNone(p.escalate(dict(plan, max_tokens=2000, output_cap=2000), 0))        # nothing left to give
        self.assertIsNone(policy(escalation={'max_retries': 0}).escalate(plan, 0))


class BudgetTest(unittest.TestCase):
    def test_budget_is_planned_only_when_thinking_is_on_and_validated(self):
        p = policy(roles={'coder': {'reasoning_budget_tokens': 800, 'max_output_tokens': 3000, 'output_cap': 9000},
                          'reviewer': {'reasoning_effort': 'none', 'reasoning_budget_tokens': 800}})
        self.assertEqual(p.plan('coder', 100, 8192)['thinking_budget_tokens'], 800)
        self.assertIsNone(p.plan('reviewer', 100, 8192)['thinking_budget_tokens'])              # thinking is off: nothing to cap
        self.assertIsNone(p.plan('coder', 100, 8192, reasoning_effort='none')['thinking_budget_tokens'])
        self.assertIsNone(policy().plan('coder', 100, 8192)['thinking_budget_tokens'])           # not set: the model's own behaviour
        for bad in (5, 70000, 'x', True):
            with self.assertRaises(ValueError, msg=str(bad)): TokenPolicyConfig({'default': {'reasoning_budget_tokens': bad}})

    def test_adapter_sends_only_the_known_budget_field(self):
        seen = []
        class A(OpenAICompatibleLocalAdapter):
            def _request(self, method, path, payload=None):
                seen.append(payload); return {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}], 'usage': None}
        a = A('a', 'http://127.0.0.1:1')
        a.chat([{'role': 'user', 'content': 'x'}], model='m', thinking_budget_tokens=256, max_reasoning_tokens=5, reasoning_budget=5)
        self.assertEqual(seen[0]['thinking_budget_tokens'], 256)
        self.assertEqual(set(seen[0]) - {'model', 'messages', 'stream'}, {'thinking_budget_tokens'})        # unknown fields never reach the engine
        for bad in (0, -1, 'x', True, 70000):
            with self.assertRaises(ModelAdapterError, msg=str(bad)): a.chat([{'role': 'user', 'content': 'x'}], model='m', thinking_budget_tokens=bad)


class AdapterTest(unittest.TestCase):
    def adapter(self):
        seen = []
        class A(OpenAICompatibleLocalAdapter):
            def _request(self, method, path, payload=None):
                seen.append(payload); return {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}], 'usage': None}
        return A('a', 'http://127.0.0.1:1'), seen

    def test_effort_is_sent_only_when_given_and_only_known_values(self):
        a, seen = self.adapter()
        a.chat([{'role': 'user', 'content': 'x'}], model='m'); a.chat([{'role': 'user', 'content': 'x'}], model='m', reasoning_effort='none')
        self.assertNotIn('reasoning_effort', seen[0]); self.assertEqual(seen[1]['reasoning_effort'], 'none')
        with self.assertRaises(ModelAdapterError): a.chat([{'role': 'user', 'content': 'x'}], model='m', reasoning_effort='max')


class MetricsTest(unittest.TestCase):
    def test_reasoning_tokens_are_recorded_and_summed(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = __import__('yaml').safe_load((RUNTIME / 'config' / 'job_supervisor.yaml').read_text(encoding='utf-8'))['context_manager']; raw['enabled'] = True
            cm = ContextManager(Path(tmp), ContextConfig(raw), artifacts=ArtifactStore(Path(tmp) / 'artifacts', AuditLog(Path(tmp) / 'audit.jsonl')))
            cm.record_usage('SDJ-1', 'A1', messages=[{'role': 'user', 'content': 'x'}], usage={'input_tokens': 20, 'output_tokens': 300, 'reasoning_tokens': 250}, model_ref='p:m')
            cm.record_usage('SDJ-1', 'A2', messages=[{'role': 'user', 'content': 'x'}], usage={'input_tokens': 20, 'output_tokens': 50}, model_ref='p:m')
            summary = cm.metrics.summary('SDJ-1')
            self.assertEqual((summary['output_tokens'], summary['reasoning_tokens']), (350, 250))


class HandlerPolicyTest(WorkerBase):
    def run_with(self, replies, pol=None, estimate=lambda messages: 100, window=8192, role='reviewer'):
        self.job(role=role); calls = []
        def infer(jid, request):
            calls.append(request); return replies[min(len(calls) - 1, len(replies) - 1)]
        handler = model_text_handler(infer, lambda job: [{'role': 'user', 'content': 'q'}], policy=pol, estimate_tokens=estimate)
        self.sup.resolver = lambda r, req, exclude, independent_of: {'role': r, 'provider_ref': 'lm-studio', 'capability_id': 'c', 'independence_key': 'k',
                                                                   'context_window': window, 'estimated_resources': {}, 'model': KEY}
        return self.worker(handler, roles=(role,)).run_once(), calls

    @staticmethod
    def ok(text='answer', out=60, reasoning=0, truncated=False):
        return {'status': 'completed', 'model_result': {'content': text, 'truncated': truncated, 'empty_answer': not text, 'model': KEY,
                                                        'usage': {'input_tokens': 30, 'output_tokens': out, 'reasoning_tokens': reasoning}}}

    def test_the_thinking_budget_reaches_the_request(self):
        pol = policy(roles={'reviewer': {'reasoning_budget_tokens': 600}})
        _, calls = self.run_with([self.ok()], pol)
        self.assertEqual(calls[0]['thinking_budget_tokens'], 600); self.assertNotIn('reasoning_effort', calls[0])

    def test_the_role_decides_effort_and_budget_and_the_cost_is_reported(self):
        out, calls = self.run_with([self.ok(out=70)], policy())
        self.assertEqual((calls[0]['reasoning_effort'], calls[0]['max_tokens']), ('none', 500))
        self.assertEqual(out['result']['token_report'], {'calls': 1, 'input_tokens': 30, 'output_tokens': 70, 'reasoning_tokens': 0, 'reasoning_chars': 0,
                                                         'wasted_output_tokens': 0, 'reasoning_effort': 'none', 'thinking_budget_tokens': None, 'max_tokens': 500})

    def test_judging_roles_keep_the_models_own_thinking(self):
        _, calls = self.run_with([self.ok()], policy(), role='verifier')
        self.assertNotIn('reasoning_effort', calls[0]); self.assertEqual(calls[0]['max_tokens'], 1000)

    def test_a_cut_off_answer_gets_one_bigger_try_and_the_first_is_counted_as_waste(self):
        out, calls = self.run_with([self.ok(text='', out=500, reasoning=500, truncated=True), self.ok(out=700, reasoning=600)], policy())
        self.assertEqual([c['max_tokens'] for c in calls], [500, 1000])
        report = out['result']['token_report']
        self.assertEqual((report['calls'], report['output_tokens'], report['wasted_output_tokens'], report['max_tokens']), (2, 1200, 500, 1000))

    def test_a_cut_off_partial_answer_is_retried_with_a_policy(self):
        out, calls = self.run_with([self.ok(text='half', truncated=True), self.ok(text='whole')], policy())
        self.assertEqual((len(calls), out['result']['text']), (2, 'whole'))

    def test_a_cut_off_partial_answer_is_accepted_without_a_policy_and_says_so(self):
        out, calls = self.run_with([self.ok(text='half', truncated=True)], None)
        self.assertEqual((len(calls), out['result']['text'], out['result']['truncated']), (1, 'half', True))

    def test_still_cut_off_after_the_retry_is_a_failure(self):
        out, calls = self.run_with([self.ok(text='', truncated=True)], policy())
        self.assertEqual((out['status'], len(calls)), ('failed', 2))

    def test_input_that_fills_the_window_never_reaches_the_model(self):
        out, calls = self.run_with([self.ok()], policy(), estimate=lambda messages: 8150)
        self.assertEqual((out['status'], calls), ('failed', []))
        job = self.sup.store.load(out['job_id']); self.assertEqual(job['attempt_log'][-1]['failure_class'], 'context_overflow')

    def test_policy_needs_an_estimator_and_a_window(self):
        out, calls = self.run_with([self.ok()], policy(), estimate=None)
        self.assertEqual((out['status'], calls), ('failed', []))

    def test_disabled_policy_changes_nothing(self):
        _, calls = self.run_with([self.ok()], TokenPolicy(TokenPolicyConfig({})))
        self.assertEqual(calls[0]['max_tokens'], 800); self.assertNotIn('reasoning_effort', calls[0])


if __name__ == '__main__':
    unittest.main()
