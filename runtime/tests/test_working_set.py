"""Phase 9: the working set. Mechanics only; no model."""
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from guppi_runtime.artifacts import ArtifactStore
from guppi_runtime.audit import AuditLog
from guppi_runtime.context_manager import ContextConfig, ContextError, ContextManager
from guppi_runtime.development_contracts import development_contract
from guppi_runtime.development_evidence import DevelopmentEvidenceStore
from guppi_runtime.job_worker import model_text_handler
from guppi_runtime.working_set import WorkingSet, common_prefix, keywords
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
JOB = 'SDJ-0123456789AB'


def para(topic, n=60):
    return f'{topic}: ' + ' '.join(f'{topic}-detail-{i} observed on unit {i}' for i in range(n))


class Base(unittest.TestCase):
    window = 6000

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audit = AuditLog(self.root / 'audit.jsonl')
        artifacts = ArtifactStore(self.root / 'artifacts', self.audit)
        raw = yaml.safe_load((RUNTIME / 'config' / 'job_supervisor.yaml').read_text(encoding='utf-8'))['context_manager']; raw['enabled'] = True
        self.cm = ContextManager(self.root, ContextConfig(raw), artifacts=artifacts, audit=self.audit, evidence_store=DevelopmentEvidenceStore(self.root / 'ev.jsonl', self.audit))
        self.job = {'job_id': JOB, 'parent_job_id': None, 'permission_level': 2, 'state': 'BUILDING', 'attempt_log': [],
                    'contract': development_contract(objective='probe objective', classification='E1', acceptance_criteria=[{'type': 'x', 'id': 'a'}],
                                                     verification_plan=[{'type': 'deterministic_tests'}])}
        self.ws = self.make()

    def make(self, **kw):
        budget = self.cm.budget_manager.build_budget(self.window)
        manifest = self.cm.assembly.build_manifest(self.job, task='do the probe', budget=budget)
        return WorkingSet(self.cm, self.root / 'ws', self.job, manifest=manifest, **kw)

    def fill(self, n, topic='turn', start=0):
        for i in range(start, start + n):
            self.ws.add('turn', para(f'{topic}{i}', 40), role='user' if i % 2 == 0 else 'assistant')


class HeadAndPrefixTest(Base):
    def test_head_is_byte_identical_between_steps_and_contains_the_contract(self):
        a = self.ws.compose('step one')
        self.ws.add('turn', 'an answer', role='assistant')
        b = self.ws.compose('step two')
        self.assertEqual(a['prefix_digest'], b['prefix_digest']); self.assertEqual(a['messages'][0], b['messages'][0])
        self.assertIn('probe objective', a['messages'][0]['content']); self.assertIn('POLICIES AND LIMITS', a['messages'][0]['content'])

    def test_two_working_sets_from_the_same_inputs_give_the_same_prompt(self):
        other = self.make()
        self.ws.state['seq'] = other.state['seq'] = 0
        for ws in (self.ws, other): ws.add('turn', 'hello', role='user'); ws.add('turn', 'hi', role='assistant')
        self.assertEqual(self.ws.compose('go')['messages'], other.compose('go')['messages'])

    def test_between_compactions_the_prompt_only_grows_at_the_end(self):
        self.ws.add('turn', 'first question', role='user')
        self.ws.compose('step 1')
        self.ws.add('turn', 'first answer', role='assistant')
        second = self.ws.compose('step 2')
        self.assertGreater(second['reuse_of_previous'], 0.55)             # everything but the changed step text is shared
        self.ws.add('turn', 'second question', role='user'); self.ws.add('turn', 'second answer', role='assistant')
        third = self.ws.compose('step 3')
        self.assertGreater(third['reuse_of_previous'], 0.55)
        self.assertEqual(third['messages'][0], second['messages'][0])

    def test_roles_alternate_and_the_last_message_is_the_step(self):
        for text, role in (('u1', 'user'), ('u2', 'user'), ('a1', 'assistant'), ('a2', 'assistant'), ('u3', 'user')):
            self.ws.add('turn', text, role=role)
        self.ws.add('tool_result', 'tool says ok', role='tool')
        roles = [m['role'] for m in self.ws.compose('now')['messages']]
        self.assertEqual(roles[0], 'system'); self.assertEqual(roles[-1], 'user'); self.assertEqual(roles[1], 'user')
        self.assertTrue(all(a != b for a, b in zip(roles[1:], roles[2:])))


class CompactionTest(Base):
    def test_old_turns_leave_the_window_in_one_block_and_the_recent_ones_stay(self):
        self.fill(30)
        out = self.ws.compose('continue')
        self.assertGreaterEqual(out['archived_blocks'], 1)
        self.assertLessEqual(out['tokens'], self.ws.compact_at + 50)
        kept = [e['entry_id'] for e in self.ws.state['entries']]
        self.assertEqual(kept[-4:], [f'E{n:05d}' for n in range(27, 31)])                    # keep_recent
        block = self.ws.state['blocks'][0]
        self.assertTrue(set(block['entry_ids']).isdisjoint(kept))

    def test_the_archived_text_is_stored_whole_and_can_be_read_back_exactly(self):
        self.fill(30)
        self.ws.compose('go')
        block = self.ws.state['blocks'][0]
        data = self.cm.offloader.read_range(block['artifact_id'], 0, block['ranges'][0]['length'])
        self.assertTrue(data.decode().startswith(f"[{block['entry_ids'][0]} user/turn]\n" + 'turn0: turn0-detail-0'))
        self.assertEqual(len(block['ranges']), len(block['entry_ids']))

    def test_pinned_and_critical_entries_survive_verbatim(self):
        self.ws.add('decision', 'DECISION: never touch the production database', role='user', pinned=True)
        self.fill(30)
        out = self.ws.compose('go')
        self.assertIn('PINNED FACTS', out['messages'][0]['content'])
        self.assertIn('DECISION: never touch the production database', out['messages'][0]['content'])

    def test_prefix_changes_only_when_a_block_is_archived(self):
        self.fill(6)
        before = self.ws.compose('a')
        self.fill(2, start=6)
        after = self.ws.compose('b')
        self.assertEqual(before['messages'][0], after['messages'][0]) if after['archived_blocks'] == before['archived_blocks'] else None
        self.fill(30, start=8)
        later = self.ws.compose('c')
        self.assertGreater(later['archived_blocks'], after['archived_blocks'])
        self.assertNotEqual(later['messages'][0]['content'], after['messages'][0]['content'])         # the index line was added

    def test_compaction_by_hand_and_nothing_to_do(self):
        self.assertIsNone(self.ws.compact())
        self.fill(3)
        self.assertIsNone(self.ws.compact(force=True))                      # not more than keep_recent turns
        self.fill(8, start=3)
        block = self.ws.compact(force=True)
        self.assertEqual(len(block['entry_ids']), 7); self.assertEqual(len(self.ws.state['entries']), 4)

    def test_counters_and_audit(self):
        self.fill(30); self.ws.compose('x')
        summary = self.cm.metrics.summary(JOB)
        self.assertGreaterEqual(summary['compaction_count'], 1); self.assertGreater(summary['estimated_tokens_saved'], 0)
        self.assertTrue(any(json.loads(l)['event_type'] == 'WORKING_SET_BLOCK_ARCHIVED' for l in (self.root / 'audit.jsonl').read_text(encoding='utf-8').splitlines()))

    def test_the_index_stays_small_however_many_blocks_there_are(self):
        for round_ in range(10):
            self.fill(8, topic=f'r{round_}x', start=round_ * 8); self.ws.compact(force=True)
        index = self.ws._index_text()
        self.assertGreater(len(self.ws.state['blocks']), 5)
        self.assertLessEqual(self.cm.estimate(index), self.ws.index_share * self.window + 80)
        self.assertIn('older blocks omitted', index); self.assertIn('B001', index)               # hidden, but named: still reachable by id


class RecallTest(Base):
    def test_a_step_gets_the_archived_part_that_matches_it_and_not_the_rest(self):
        self.ws.add('turn', 'We chose the zebracorn adapter because ' + para('zebracorn', 30), role='user')
        self.ws.add('turn', 'ok', role='assistant')
        self.fill(30, topic='noise', start=2)
        self.ws.compact(force=True)
        hit = self.ws.compose('why did we pick the zebracorn adapter?')
        self.assertEqual(hit['recalled'][0]['block_id'], 'B001')
        self.assertIn('zebracorn', hit['messages'][-1]['content']); self.assertIn('RECALLED FROM ARCHIVE B001', hit['messages'][-1]['content'])
        miss = self.ws.compose('what is the weather like today?')
        self.assertEqual(miss['recalled'], []); self.assertNotIn('RECALLED', miss['messages'][-1]['content'])

    def test_recalled_text_is_redacted_and_bounded(self):
        self.ws.add('turn', 'config api_key = sk-secret-123456 for the quokka service ' + para('quokka', 40), role='user')
        self.fill(30, topic='noise', start=1); self.ws.compact(force=True)
        got = self.ws.recall('B001', 'quokka service config', max_tokens=300)
        self.assertNotIn('sk-secret-123456', got['text']); self.assertIn('REDACTED', got['text']); self.assertLessEqual(got['tokens'], 300)

    def test_recall_by_id_and_unknown_block(self):
        self.fill(12); self.ws.compact(force=True)
        self.assertTrue(self.ws.recall('B001')['text'])
        with self.assertRaises(ContextError) as ctx: self.ws.recall('B999')
        self.assertEqual(ctx.exception.code, 'piece_not_found')

    def test_recall_never_pushes_the_prompt_past_the_window(self):
        self.ws.add('turn', 'zebracorn ' * 30, role='user'); self.fill(40, start=1); self.ws.compact(force=True)
        out = self.ws.compose('zebracorn zebracorn ' + 'zebracorn ' * 20)
        self.assertLessEqual(out['tokens'], self.window)

    def test_recall_can_be_switched_off(self):
        ws = self.make(recall_k=0)
        for i in range(12): ws.add('turn', para(f'zebracorn{i}', 30), role='user' if i % 2 == 0 else 'assistant')
        ws.compact(force=True)
        self.assertEqual(ws.compose('zebracorn?')['recalled'], [])


class ToolResultTest(Base):
    def test_a_large_tool_result_enters_as_a_summary_with_a_reference(self):
        dump = '\n'.join(f'line {i}: processing item {i} ok' for i in range(4000)) + '\nERROR: item 4001 failed\n'
        entry = self.ws.add('tool_result', dump, role='tool', source={'tool': 'filesystem', 'operation': 'read'})
        self.assertIsNotNone(entry['artifact']); self.assertLess(entry['tokens'], 1200); self.assertNotIn('line 3999', entry['text'])
        self.assertGreater(self.cm.metrics.summary(JOB)['tool_output_offloaded_bytes'], 10000)

    def test_a_small_tool_result_stays_inline_and_is_redacted(self):
        entry = self.ws.add('tool_result', 'status ok, password = hunter2', role='tool')
        self.assertIsNone(entry['artifact']); self.assertNotIn('hunter2', entry['text'])


class OffloadedOutputRecallTest(Base):
    """A large tool result leaves the window as a summary. A later step that asks for something INSIDE it must get exactly that part back."""
    window = 12000

    def dump(self, name, value):
        filler = chr(10).join(f'def helper_{i}(x):  # generic code line {i}' for i in range(700))
        return f'module {name}' + chr(10) + f'{name.upper()}_TIMEOUT_MS = {value}' + chr(10) + filler

    def setUp(self):
        super().setUp()
        for name, value in (('ledger', 4711), ('router', 8123), ('cache', 2468)):
            self.ws.add('tool_result', self.dump(name, value), role='tool', source={'tool': 'filesystem', 'operation': 'read'})
            self.ws.add('turn', f'read {name}', role='assistant')

    def test_a_step_that_names_a_thing_inside_an_offloaded_output_gets_that_line_back(self):
        out = self.ws.compose('What is the value of ROUTER_TIMEOUT_MS?')
        tail = out['messages'][-1]['content']
        self.assertIn('RECALLED FROM OFFLOADED OUTPUT', tail); self.assertIn('ROUTER_TIMEOUT_MS = 8123', tail)
        self.assertNotIn('LEDGER_TIMEOUT_MS = 4711', tail); self.assertEqual([r['kind'] for r in out['recalled']], ['offloaded_output'])
        self.assertEqual(self.ws.stats['offload_recalls'], 1)

    def test_the_recalled_part_is_small_and_never_the_whole_output(self):
        out = self.ws.compose('What is the value of CACHE_TIMEOUT_MS?')
        self.assertLess(out['recalled'][0]['tokens'], 1300); self.assertLess(out['tokens'], self.window)

    def test_a_step_that_names_nothing_in_them_recalls_nothing(self):
        out = self.ws.compose('Say hello to the reviewer.')
        self.assertEqual(out['recalled'], []); self.assertNotIn('RECALLED FROM OFFLOADED', out['messages'][-1]['content'])

    def test_pasted_material_in_a_long_step_does_not_pull_in_recalls_only_its_question_does(self):
        pasted = self.dump('sampler', 9999)[:6000]                                     # the file this step is about: far longer than a question
        out = self.ws.compose(pasted + chr(10) * 2 + 'What is SAMPLER_TIMEOUT_MS in module sampler?')
        self.assertEqual(out['recalled'], [])
        out = self.ws.compose(pasted + chr(10) * 2 + 'What is ROUTER_TIMEOUT_MS, which we read before?')
        self.assertEqual(len(out['recalled']), 1); self.assertIn('ROUTER_TIMEOUT_MS = 8123', out['messages'][-1]['content'])

    def test_the_same_inputs_give_the_same_prompt(self):
        a = self.ws.compose('What is the value of LEDGER_TIMEOUT_MS?')['messages']
        b = self.ws.compose('What is the value of LEDGER_TIMEOUT_MS?')['messages']
        self.assertEqual(a, b)

    def test_it_can_be_switched_off_with_recall_k_zero(self):
        ws = self.make(recall_k=0)
        ws.add('tool_result', self.dump('ledger', 4711), role='tool')
        self.assertEqual(ws.compose('What is the value of LEDGER_TIMEOUT_MS?')['recalled'], [])

    def test_the_memory_of_offloaded_outputs_survives_a_new_working_set_over_the_same_folder(self):
        again = self.make()
        self.assertEqual(len(again.state['offloads']), 3)
        self.assertIn('LEDGER_TIMEOUT_MS = 4711', again.compose('What is LEDGER_TIMEOUT_MS?')['messages'][-1]['content'])

    def test_a_lost_artifact_is_skipped_and_the_step_still_composes(self):
        for item in self.ws.state['offloads']:
            item['artifact_id'] = 'ART-DOES-NOT-EXIST'
        out = self.ws.compose('What is the value of ROUTER_TIMEOUT_MS?')
        self.assertEqual(out['recalled'], [])


class PersistenceAndValidationTest(Base):
    def test_a_new_working_set_over_the_same_folder_continues_where_the_old_one_stopped(self):
        self.fill(30); first = self.ws.compose('go')
        again = self.make()
        second = again.compose('go')
        self.assertEqual(first['messages'], second['messages']); self.assertEqual(again.state['blocks'][0]['block_id'], 'B001')
        again.add('turn', 'next', role='user')
        self.assertEqual(again.state['entries'][-1]['entry_id'], f"E{self.ws.state['seq'] + 1:05d}")

    def test_rehead_replaces_the_head_and_keeps_history_and_archive(self):
        self.fill(30); self.ws.compose('go')
        manifest = self.cm.assembly.build_manifest(self.job, task='a different task', budget=self.cm.budget_manager.build_budget(self.window))
        self.ws.rehead(manifest)
        out = self.ws.compose('go again')
        self.assertIn('a different task', out['messages'][0]['content']); self.assertGreaterEqual(out['archived_blocks'], 1)

    def test_bad_input_is_refused(self):
        for kind, role, text in (('nope', 'user', 'x'), ('turn', 'robot', 'x'), ('turn', 'user', ''), ('turn', 'user', '   '), ('turn', 'user', None)):
            with self.assertRaises(ContextError): self.ws.add(kind, text, role=role)
        with self.assertRaises(ContextError): self.ws.compose('')
        with self.assertRaises(ContextError): self.make(keep_recent=0)
        with self.assertRaises(ContextError): self.make(compact_at=100, target=200)
        with self.assertRaises(ContextError): WorkingSet(self.cm, self.root / 'ws2', {'x': 1}, manifest=self.ws.manifest)

    def test_a_step_that_alone_does_not_fit_is_refused(self):
        with self.assertRaises(ContextError) as ctx: self.ws.compose(para('huge', 4000))
        self.assertEqual(ctx.exception.code, 'minimum_context_exceeds_window')


class HandlerIntegrationTest(Base):
    """The handler sends the composed working set, and the reply goes back into it as a turn."""
    def run_steps(self, steps, window_fill=0):
        sent, replies = [], iter(f'answer {i}' for i in range(100))
        def infer(job_id, request):
            sent.append(request['messages']); return {'status': 'completed', 'model_result': {'content': next(replies), 'usage': {'input_tokens': 10, 'output_tokens': 5}, 'model': 'm'}}
        task = {'text': ''}
        handler = model_text_handler(infer, lambda job: self.ws.compose(task['text'])['messages'],
                                     on_result=lambda job, attempt, result: self.ws.add('turn', result['text'], role='assistant'))
        attempt = {'provider_ref': 'p', 'model': 'm', 'attempt_id': 'ATT-1'}
        for text in steps:
            task['text'] = text
            self.ws.add('turn', text, role='user')
            handler({**self.job, 'requested_role': 'reviewer'}, attempt, None)
        return sent

    def test_the_second_step_sees_the_first_answer_through_the_working_set(self):
        sent = self.run_steps(['what is the plan?', 'and the risks?'])
        self.assertEqual(len(sent), 2)
        flat = chr(10).join(m['content'] for m in sent[1])
        self.assertIn('answer 0', flat); self.assertIn('and the risks?', flat); self.assertEqual(sent[0][0], sent[1][0])        # same head

    def test_a_long_session_stays_inside_the_window_by_archiving(self):
        sent = self.run_steps([para(f'question{i}', 45) for i in range(40)])
        sizes = [self.cm.estimate(chr(10).join(m['content'] for m in msgs)) for msgs in sent]
        self.assertLessEqual(max(sizes), self.window)
        self.assertGreaterEqual(self.ws.status()['blocks'], 1)
        everything = sum(self.cm.estimate(para(f'question{i}', 45)) for i in range(40))
        self.assertLess(sizes[-1], everything / 2)                                   # a resent history would be several times bigger


class RuntimeFactoryTest(unittest.TestCase):
    ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'

    def runtime(self, switches):
        from guppi_runtime.runtime import GuppiRuntime
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        project = Path(tmp.name) / 'project'; (project / 'local_config').mkdir(parents=True)
        if switches: (project / 'local_config' / 'switches.yaml').write_text(switches, encoding='utf-8')
        return GuppiRuntime(project, architecture_root=self.ARCH)

    def test_the_factory_builds_a_working_set_for_the_loaded_window_and_is_off_without_the_switch(self):
        rt = self.runtime('switches:' + chr(10) + '  context_manager: {enabled: true}' + chr(10))
        job = {'job_id': JOB, 'parent_job_id': None, 'permission_level': 2, 'state': 'BUILDING', 'attempt_log': [],
               'contract': development_contract(objective='probe objective', classification='E1', acceptance_criteria=[{'type': 'x', 'id': 'a'}],
                                                verification_plan=[{'type': 'deterministic_tests'}])}
        ws = rt.working_set(job, task='do it', window=16384)
        self.assertEqual(ws.window, rt.context_manager.budget_manager.build_budget(16384)['max_input_tokens']); self.assertLess(ws.window, 16384)   # room for the answer is kept free
        ws.add('turn', 'hello', role='user')
        self.assertIn('probe objective', ws.compose('go')['messages'][0]['content'])
        self.assertTrue((rt.project_root / 'runtime_data' / 'working_sets' / JOB / 'working_set.json').exists())
        with self.assertRaises(ValueError): self.runtime(None).working_set(job, task='x', window=16384)


class HelpersTest(unittest.TestCase):
    def test_keywords_are_distinctive_ordered_and_deterministic(self):
        words = keywords('The cache cache cache and the adapter adapter config.yaml 4711')
        self.assertEqual(words[:2], ['cache', 'adapter']); self.assertNotIn('the', words); self.assertIn('config.yaml', words); self.assertIn('4711', words)
        self.assertEqual(keywords('x ' * 5), [])

    def test_common_prefix(self):
        self.assertEqual((common_prefix('abcdef', 'abcxyz'), common_prefix('', 'a'), common_prefix('same', 'same')), (3, 0, 4))


if __name__ == '__main__':
    unittest.main()
