import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import json, tempfile, unittest
from pathlib import Path
from guppi_runtime.devvm import DevWorkspace
from guppi_runtime.devvm_agents import DevOrchestrator, ModelHost, run_agent
from guppi_runtime.devvm_tools import DevToolBox

POLICY = {'max_files': 20, 'max_file_bytes': 4000, 'max_input_bytes': 20000}


def tc(name, args, i=1):
    return {'id': f'c{i}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}


def answer(calls=None, content=''):
    return {'choices': [{'message': {'content': content, 'tool_calls': calls or []}, 'finish_reason': 'tool_calls' if calls else 'stop'}], 'usage': {'completion_tokens': 10}}


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ws = DevWorkspace(Path(self.tmp.name), 'M-DELEG001', policy=dict(POLICY)); self.ws.create()
        self.seen, self.scripts, self.loads = [], {}, []
        outer = self
        class Loader:
            def load(self, key):
                outer.loads.append(key)
                def plain(body, key=key):
                    outer.seen.append((key, body)); return next(outer.scripts[key])
                return key, plain, {}
            def unload(self): pass
        self.host = ModelHost(Loader()); self.lines = []

    def script(self, key, turns): self.scripts[key] = iter(turns)
    def team(self, **kw):
        kw.setdefault('mode', 'delegating'); kw.setdefault('max_depth', 2)
        return DevOrchestrator(self.ws, self.host, {'planner': 'p', 'coder': 'c', 'reviewer': 'r', 'coder_strong': 's'}, say=self.lines.append, **kw)
    PLAN = answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py with x = 1', 'check': 'from a import x\nassert x == 1'}]})])
    def write(self, content='x = 1\n', i=1): return answer([tc('write_file', {'path': 'a.py', 'content': content}, i)])
    def delegate(self, role, instruction, i=1): return answer([tc('delegate', {'role': role, 'instruction': instruction}, i)])
    def done(self, i=1): return answer([tc('submit_result', {'summary': 'done'}, i)])
    def verdict(self, v, cause=''): return answer([tc('submit_review', {'verdict': v, 'cause': cause})])


class ToolTests(Case):
    def test_the_delegate_tool_exists_only_with_a_delegator_and_names_the_roles(self):
        self.assertNotIn('delegate', DevToolBox(self.ws, 'coder').names)
        self.assertNotIn('delegate', DevToolBox(self.ws, 'coder', delegator=lambda r, i: 'x').names)                       # no roles allowed: no tool
        box = DevToolBox(self.ws, 'coder', delegator=lambda r, i: 'x', delegate_roles=('reviewer', 'strong_coder'))
        self.assertEqual(box.names[-2:], ('delegate', 'submit_result'))
        desc = [s for s in box.schemas() if s['function']['name'] == 'delegate'][0]['function']['description']; self.assertIn('reviewer, strong_coder', desc)

    def test_calls_validate_count_and_are_limited_and_failures_come_back_as_text(self):
        got = []
        def delegator(role, instruction): got.append((role, instruction)); return f'{role} reports'
        box = DevToolBox(self.ws, 'coder', delegator=delegator, delegate_roles=('reviewer',), max_delegations=2)
        self.assertEqual(box.call('delegate', {'role': 'reviewer', 'instruction': ' check it '}), 'reviewer reports'); self.assertEqual(got, [('reviewer', 'check it')])
        for bad in ({'role': 'strong_coder', 'instruction': 'x'}, {'role': 'reviewer'}, {'role': 'reviewer', 'instruction': '  '}, {}):
            self.assertTrue(box.call('delegate', bad).startswith('error:'), bad)
        self.assertEqual(box.delegations, 1)
        box.call('delegate', {'role': 'reviewer', 'instruction': 'again'})
        self.assertIn('at most 2 helpers', box.call('delegate', {'role': 'reviewer', 'instruction': 'third'})); self.assertEqual((box.delegations, len(got)), (2, 2))
        def boom(role, instruction): raise RuntimeError('helper crashed')
        self.assertIn('helper crashed', DevToolBox(self.ws, 'coder', delegator=boom, delegate_roles=('reviewer',)).call('delegate', {'role': 'reviewer', 'instruction': 'x'}))

    def test_an_explorer_reads_but_cannot_write(self):
        e = DevToolBox(self.ws, 'explorer'); self.assertEqual(e.terminal, 'submit_result'); self.assertNotIn('write_file', e.names); self.assertTrue(e.system)
        self.assertTrue(e.call('write_file', {'path': 'a.py', 'content': 'x'}).startswith('error: unknown tool'))


class HostAndDepthTests(Case):
    def test_a_call_for_another_model_swaps_and_a_call_for_the_loaded_one_does_not(self):
        self.script('a', [{'m': 'a1'}, {'m': 'a2'}]); self.script('b', [{'m': 'b1'}])
        self.host.use('a')
        self.assertEqual(self.host.call('a', {}), {'m': 'a1'}); self.assertEqual(self.loads, ['a'])
        self.assertEqual(self.host.call('b', {}), {'m': 'b1'}); self.assertEqual(self.host.call('a', {}), {'m': 'a2'}); self.assertEqual(self.loads, ['a', 'b', 'a'])

    def test_the_depth_ceiling_is_a_parameter_with_default_one(self):
        post = lambda b: answer([tc('submit_result', {'summary': 's'})])
        self.assertEqual(run_agent('coder', 't', self.ws, post, 'm', depth=1)['stopped_by'], 'hand_in')
        with self.assertRaises(ValueError): run_agent('coder', 't', self.ws, post, 'm', depth=2)
        self.assertEqual(run_agent('coder', 't', self.ws, post, 'm', depth=2, max_depth=2)['depth'], 2)
        with self.assertRaises(ValueError): run_agent('coder', 't', self.ws, post, 'm', depth=3, max_depth=2)

    def test_delegating_mode_needs_the_depth_to_be_raised_on_purpose(self):
        for depth in (1, 0):
            with self.assertRaises(ValueError) as ctx: DevOrchestrator(self.ws, self.host, {}, mode='delegating', max_depth=depth)
            self.assertEqual(str(ctx.exception), 'delegation_needs_depth_2')
        with self.assertRaises(ValueError): DevOrchestrator(self.ws, self.host, {}, mode='free-for-all')
        self.assertEqual(DevOrchestrator(self.ws, self.host, {}).max_depth, 1)                                         # the default stays: no helpers of helpers, no agent-started helpers


class DelegatingRunTests(Case):
    def test_the_developer_asks_a_reviewer_and_a_strong_coder_and_gets_its_own_model_back(self):
        self.script('p', [self.PLAN])
        self.script('c', [self.write('x = 0\n'), self.delegate('reviewer', 'a.py must set x = 1', 2), self.delegate('strong_coder', 'a.py: x must be 1, not 0', 3), self.done(4)])
        self.script('r', [self.verdict('FAIL', 'x is 0, the task wants 1')]); self.script('s', [self.write('x = 1\n'), self.done()])
        out = self.team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}).run('make a.py with x = 1')
        self.assertTrue(out['accepted']); self.assertEqual((out['mode'], out['subagents'], out['delegations']), ('delegating', 2, 2)); self.assertEqual(self.ws.read('a.py'), 'x = 1\n')
        self.assertEqual(self.loads, ['p', 'c', 'r', 'c', 's', 'c'])                          # the developer's later calls went to ITS model again (a wrong route would have eaten another script)
        by_label = {r['label']: r for r in out['agent_runs']}
        sub_r, sub_s, parent = by_label['sub:reviewer of coder s1 r1'], by_label['sub:strong_coder of coder s1 r1'], by_label['coder s1 r1']
        self.assertEqual((sub_r['depth'], sub_r['parent'], sub_s['depth'], sub_s['parent'], parent['depth'], parent['parent']), (2, 'coder s1 r1', 2, 'coder s1 r1', 1, None))
        self.assertEqual((sub_r['model'], sub_s['model'], parent['model']), ('r', 's', 'c')); self.assertEqual(parent['delegations'], 2)
        self.assertEqual([r['role'] for r in out['agent_runs'] if r['role'] == 'reviewer'], ['reviewer'])         # only the helper, no fixed reviewer step in this mode
        coder_last = [b for k, b in self.seen if k == 'c'][-1]['messages']
        tool_texts = [m['content'] for m in coder_last if m['role'] == 'tool']
        self.assertIn('FAIL: x is 0, the task wants 1', tool_texts); self.assertTrue(any('done (workspace now:' in t for t in tool_texts))
        helper_tools = [[t['function']['name'] for t in b['tools']] for k, b in self.seen if k in ('r', 's')]
        self.assertTrue(all('delegate' not in names for names in helper_tools))                                     # helpers are leaves
        self.assertIn('you SHOULD use helper agents', [b for k, b in self.seen if k == 'c'][0]['messages'][1]['content'])
        self.assertEqual(self.ws.log()[0]['message'], 'one')

    def test_the_team_has_a_total_of_helpers_per_run(self):
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py'}]})])])
        self.script('c', [self.delegate('reviewer', 'first', 1), self.delegate('reviewer', 'second', 2), self.done(3)]); self.script('r', [self.verdict('PASS')])
        out = self.team(max_subagents=1).run('t')
        self.assertEqual(out['subagents'], 1); tool_texts = [m['content'] for m in [b for k, b in self.seen if k == 'c'][-1]['messages'] if m['role'] == 'tool']
        self.assertTrue(any('already used its 1 helpers' in t for t in tool_texts))

    def test_a_failing_check_sends_the_developer_round_two_and_unfinished_work_is_committed_as_unreviewed(self):
        self.script('p', [self.PLAN]); self.script('c', [self.write('x = 0\n'), self.done(2), self.write('x = 0\n', 3), self.done(4)])
        out = self.team(vm_runner=lambda c: {'status': 'failed', 'output': 'AssertionError'}).run('t')
        self.assertFalse(out['accepted']); self.assertEqual([r['verdict'] for r in out['steps'][0]['rounds']], ['FAIL(test)', 'FAIL(test)']); self.assertEqual(self.ws.log()[0]['message'], 'UNREVIEWED: one')

    def test_without_a_vm_runner_the_developer_hand_in_is_accepted(self):
        self.script('p', [self.PLAN]); self.script('c', [self.write(), self.done(2)])
        out = self.team().run('t'); self.assertTrue(out['accepted']); self.assertEqual(out['steps'][0]['rounds'][0]['verdict'], 'accepted')

    def test_the_planner_may_hand_reading_the_workspace_to_an_explorer_on_its_own_model(self):
        self.ws.write('lib.py', 'def f():\n    return 1\n')
        self.script('c', [self.done()])
        # the explorer runs on the planner's model: its answer is the next item of the planner script, between the planner's two turns
        self.script('p', [self.delegate('explorer', 'which functions exist?'), answer([tc('submit_result', {'summary': 'lib.py defines f() returning 1'})]),
                          answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'use f'}]}, 2)])])
        out = self.team().run('t')
        explorer = [r for r in out['agent_runs'] if r['role'] == 'explorer'][0]
        self.assertEqual((explorer['model'], explorer['depth'], explorer['parent'], explorer['stopped_by']), ('p', 2, 'planner', 'hand_in'))
        self.assertEqual(self.loads, ['p', 'c'])                                                                  # no model swap for the explorer
        planner_tools = [t['function']['name'] for t in [b for k, b in self.seen if k == 'p'][0]['tools']]; self.assertIn('delegate', planner_tools)
        self.assertIn("you SHOULD first hand the reading", [b for k, b in self.seen if k == 'p'][0]['messages'][1]['content'])
        self.assertEqual(out['plan'], ['one'])

    def test_pipeline_mode_never_offers_delegation(self):
        self.script('p', [self.PLAN]); self.script('c', [self.write(), self.done(2)]); self.script('r', [self.verdict('PASS')])
        out = DevOrchestrator(self.ws, self.host, {'planner': 'p', 'coder': 'c', 'reviewer': 'r'}, mode='pipeline').run('t')
        for k, b in self.seen: self.assertNotIn('delegate', [t['function']['name'] for t in b['tools']])
        self.assertEqual((out['mode'], out['delegations'], out['subagents']), ('pipeline', 0, 0))


if __name__ == '__main__':
    unittest.main()
