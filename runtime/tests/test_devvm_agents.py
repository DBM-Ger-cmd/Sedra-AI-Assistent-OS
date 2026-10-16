import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import json, tempfile, unittest
from pathlib import Path
from guppi_runtime.devvm import DevWorkspace
from guppi_runtime.devvm_agents import AgentBudget, DevOrchestrator, ModelHost, run_agent

POLICY = {'max_files': 20, 'max_file_bytes': 4000, 'max_input_bytes': 20000}


def tc(name, args, i=1):
    return {'id': f'c{i}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}


def answer(calls=None, content='', tokens=10):
    return {'choices': [{'message': {'content': content, 'tool_calls': calls or []}, 'finish_reason': 'tool_calls' if calls else 'stop'}], 'usage': {'completion_tokens': tokens}}


class Audit:
    def __init__(self): self.events = []
    def append(self, event, **kw): self.events.append((event, kw.get('mission_id'), kw.get('payload')))


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.audit = Audit()
        self.ws = DevWorkspace(Path(self.tmp.name), 'M-AGENT001', policy=dict(POLICY), audit=self.audit); self.ws.create()


class RunAgentTests(Case):
    def post_of(self, turns):
        it = iter(turns); self.bodies = []
        def post(body): self.bodies.append(body); return next(it)
        return post

    def test_a_run_ends_with_the_hand_in_and_leaves_journal_and_audit(self):
        post = self.post_of([answer([tc('write_file', {'path': 'a.py', 'content': 'x = 1\n'})]), answer([tc('submit_result', {'summary': 'wrote a'})])])
        r = run_agent('coder', 'make a.py', self.ws, post, 'jan', audit=self.audit, label='coder s1')
        self.assertEqual((r['stopped_by'], r['calls'], r['final']), ('hand_in', 2, {'summary': 'wrote a'}))
        self.assertEqual([j['tool'] for j in r['journal']], ['write_file', 'submit_result']); self.assertEqual(r['completion_tokens'], 20)
        event = [e for e in self.audit.events if e[0] == 'DEVVM_AGENT_RUN'][0]
        self.assertEqual((event[1], event[2]['role'], event[2]['model'], event[2]['stopped_by'], event[2]['label']), ('M-AGENT001', 'coder', 'jan', 'hand_in', 'coder s1'))
        self.assertEqual(self.bodies[0]['messages'][0]['role'], 'system'); self.assertEqual(self.bodies[0]['messages'][1]['content'], 'make a.py')

    def test_agents_cannot_start_agents(self):
        with self.assertRaises(ValueError) as ctx: run_agent('coder', 'x', self.ws, lambda b: answer(), 'm', depth=2)
        self.assertEqual(str(ctx.exception), 'agent_depth_limit')
        from guppi_runtime.devvm_tools import ROLE_TOOLS, SCHEMAS
        self.assertFalse([n for names in ROLE_TOOLS.values() for n in names if 'agent' in n or 'spawn' in n or 'delegate' in n])      # no tool that starts one
        self.assertFalse([n for n in SCHEMAS if 'agent' in n or 'spawn' in n])

    def test_each_budget_ends_the_run_with_its_own_reason(self):
        varied = lambda n: [answer([tc('write_file', {'path': f'f{i}.py', 'content': f'x = {i}\n'})], tokens=60) for i in range(n)]
        r = run_agent('coder', 't', self.ws, self.post_of(varied(10)), 'm', budget=AgentBudget(max_completion_tokens=100)); self.assertEqual((r['stopped_by'], r['completion_tokens']), ('tokens', 120))
        r = run_agent('coder', 't', self.ws, self.post_of(varied(10)), 'm', budget=AgentBudget(max_turns=3)); self.assertEqual((r['stopped_by'], r['turns']), ('turns', 3))
        r = run_agent('coder', 't', self.ws, self.post_of(varied(10)), 'm', budget=AgentBudget(max_calls=2, max_turns=6)); self.assertEqual(r['stopped_by'], 'calls'); self.assertEqual(r['limit_hit'], '2 tool calls')
        ticks = iter(range(0, 10000, 100)); r = run_agent('coder', 't', self.ws, self.post_of(varied(10)), 'm', budget=AgentBudget(max_seconds=250), clock=lambda: next(ticks)); self.assertEqual(r['stopped_by'], 'time')
        r = run_agent('coder', 't', self.ws, self.post_of([answer(content='I will just talk')]), 'm'); self.assertEqual(r['stopped_by'], 'no_tool_call')

    def test_the_loop_guard_stops_an_agent_that_keeps_reading_the_same_file(self):
        self.ws.write('a.py', 'x = 1\n')
        same = [answer([tc('read_file', {'path': 'a.py'})]) for _ in range(12)]
        r = run_agent('reviewer', 't', self.ws, self.post_of(same), 'm'); self.assertEqual(r['stopped_by'], 'loop'); self.assertGreaterEqual(r['stuck_blocks'], 3)
        self.assertEqual(r['nudges'], 1)                                           # one correction before the run ends

    def test_the_runaway_guard_stops_an_answer_that_is_one_block_repeated(self):
        r = run_agent('coder', 't', self.ws, self.post_of([answer([tc('list_dir', {})], content='blah ' * 2000), answer([tc('submit_result', {'summary': 's'})])]), 'm', budget=AgentBudget(max_nudges=0))
        self.assertEqual(r['stopped_by'], 'runaway'); self.assertIsNone(r['final'])
        r = run_agent('coder', 't', self.ws, self.post_of([answer([tc('list_dir', {})], content='blah ' * 2000)] * 3), 'm')      # with the one correction: the second runaway answer ends the run
        self.assertEqual((r['stopped_by'], r['nudges']), ('runaway', 1))

    def test_a_model_that_cannot_be_reached_ends_as_error(self):
        def post(body): raise OSError('server weg')
        r = run_agent('coder', 't', self.ws, post, 'm'); self.assertEqual(r['stopped_by'], 'error'); self.assertIn('server weg', r['error'])


class HostTests(unittest.TestCase):
    class Loader:
        def __init__(self): self.events = []; self.fail_first = {}
        def load(self, key):
            self.events.append(('load', key))
            def plain(body, key=key):
                if self.fail_first.get(key): self.fail_first[key] -= 1; raise ConnectionResetError('weg')
                return {'model': key}
            return key + '-alias', plain, {'temperature': 0.1}
        def unload(self): self.events.append(('unload',))

    def test_one_model_at_a_time_and_a_swap_only_when_the_model_changes(self):
        loader = self.Loader(); host = ModelHost(loader)
        host.use('a'); host.use('a'); alias, post, sampling = host.use('b')
        self.assertEqual(loader.events, [('load', 'a'), ('unload',), ('load', 'b')]); self.assertEqual((host.swaps, alias, sampling), (2, 'b-alias', {'temperature': 0.1}))
        self.assertEqual(post({}), {'model': 'b'}); host.close(); self.assertEqual(loader.events[-1], ('unload',)); self.assertIsNone(host.current)
    def test_a_crashed_server_is_restarted_once_and_the_call_repeated(self):
        loader = self.Loader(); loader.fail_first['a'] = 1; host = ModelHost(loader)
        _, post, _ = host.use('a')
        self.assertEqual(post({}), {'model': 'a'}); self.assertEqual(len(host.crashes), 1); self.assertEqual(loader.events, [('load', 'a'), ('unload',), ('load', 'a')])
        loader.fail_first['a'] = 2
        with self.assertRaises(ConnectionResetError): host.use('a')[1]({})                         # a second failure is not hidden

    def test_a_refused_request_is_no_crash_and_keeps_the_reason_of_the_server(self):
        import io
        from urllib.error import HTTPError
        loader = self.Loader(); host = ModelHost(loader); host.use('a')
        def refuse(body): raise HTTPError('http://x', 400, 'Bad Request', {}, io.BytesIO(b'{"error": "request exceeds the available context size"}'))
        host.plain = refuse
        with self.assertRaises(RuntimeError) as err: host._post({})
        self.assertIn('400', str(err.exception)); self.assertIn('context size', str(err.exception))
        self.assertEqual((host.crashes, loader.events), ([], [('load', 'a')]))                  # no restart of the model
        def broken(body): raise HTTPError('http://x', 500, 'boom', {}, io.BytesIO(b''))
        host.plain = broken
        self.assertEqual(host._post({}), {'model': 'a'})                                          # a 5xx stays a crash: one restart, then the call is repeated
        self.assertEqual(len(host.crashes), 1)


class TeamTests(Case):
    def setUp(self):
        super().setUp(); self.seen = []; self.scripts = {}
        outer = self
        class Loader:
            def load(self, key):
                def plain(body, key=key):
                    outer.seen.append((key, body)); return next(outer.scripts[key])
                return key, plain, {}
            def unload(self): pass
        self.host = ModelHost(Loader()); self.lines = []

    def team(self, **kw):
        return DevOrchestrator(self.ws, self.host, {'planner': 'p', 'coder': 'c', 'reviewer': 'r'}, audit=self.audit, say=self.lines.append, **dict({'mode': 'pipeline'}, **kw))
    def script(self, role, turns): self.scripts[role] = iter(turns)
    PLAN = answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py with x = 1', 'acceptance': 'a.py exists'}, {'title': 'two', 'instruction': 'make b.py'}]})])
    def coder_turn(self, path): return [answer([tc('write_file', {'path': path, 'content': 'x = 1\n'})]), answer([tc('submit_result', {'summary': 'done ' + path})])]
    def verdict(self, v, cause=''): return answer([tc('submit_review', {'verdict': v, 'cause': cause})])

    def test_plan_then_developer_and_reviewer_per_step_with_a_commit_each(self):
        self.script('p', [self.PLAN]); self.script('c', self.coder_turn('a.py') + self.coder_turn('b.py')); self.script('r', [self.verdict('PASS'), self.verdict('PASS')])
        out = self.team().run('build a and b')
        self.assertTrue(out['accepted']); self.assertEqual(out['plan'], ['one', 'two']); self.assertFalse(out['plan_fallback'])
        self.assertEqual([m['message'] for m in self.ws.log()], ['two', 'one']); self.assertEqual(self.ws.tree(), ['a.py', 'b.py'])
        self.assertEqual([r['role'] for r in out['agent_runs']], ['planner', 'coder', 'reviewer', 'coder', 'reviewer']); self.assertEqual(out['model_swaps'], 5)
        events = [e[0] for e in self.audit.events if e[0].startswith('DEVVM_') and e[0] not in ('DEVVM_WRITE', 'DEVVM_COMMIT', 'DEVVM_CREATED')]
        self.assertEqual(events, ['DEVVM_AGENT_RUN', 'DEVVM_PLAN', 'DEVVM_AGENT_RUN', 'DEVVM_AGENT_RUN', 'DEVVM_STEP', 'DEVVM_AGENT_RUN', 'DEVVM_AGENT_RUN', 'DEVVM_STEP', 'DEVVM_RUN_DONE'])
        self.assertTrue(all(r['journal'] for r in out['agent_runs'])); self.assertTrue(all(e[1] == 'M-AGENT001' for e in self.audit.events))
        coder_tools = [t['function']['name'] for t in next(b for k, b in self.seen if k == 'c')['tools']]
        self.assertNotIn('git_commit', coder_tools); self.assertIn('write_file', coder_tools)            # the team commits, not the developer
        planner_tools = [t['function']['name'] for t in next(b for k, b in self.seen if k == 'p')['tools']]; self.assertNotIn('write_file', planner_tools)

    def test_a_rejected_step_goes_back_to_the_developer_with_the_defect(self):
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py'}]})])])
        self.script('c', self.coder_turn('a.py') + self.coder_turn('a.py')); self.script('r', [self.verdict('FAIL', 'a.py misses the second example'), self.verdict('PASS')])
        out = self.team().run('t')
        self.assertTrue(out['accepted']); self.assertEqual([r['verdict'] for r in out['steps'][0]['rounds']], ['FAIL', 'PASS'])
        second_coder_task = [b for k, b in self.seen if k == 'c'][2]['messages'][1]['content']
        self.assertIn('rejected: a.py misses the second example', second_coder_task); self.assertEqual(self.ws.log()[0]['message'], 'one')

    def test_when_the_rounds_run_out_the_step_is_committed_as_unreviewed(self):
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py'}]})])])
        self.script('c', self.coder_turn('a.py') * 2); self.script('r', [self.verdict('FAIL', 'no'), self.verdict('FAIL', 'still no')])
        out = self.team(max_rounds=2).run('t')
        self.assertFalse(out['accepted']); self.assertFalse(out['steps'][0]['accepted']); self.assertEqual(self.ws.log()[0]['message'], 'UNREVIEWED: one')

    def test_without_a_usable_plan_the_whole_task_is_one_step(self):
        self.script('p', [answer(content='no plan from me')]); self.script('c', self.coder_turn('a.py')); self.script('r', [self.verdict('PASS')])
        out = self.team().run('do everything')
        self.assertTrue(out['plan_fallback']); self.assertEqual(out['plan'], ['whole task']); self.assertIn('do everything', [b for k, b in self.seen if k == 'c'][0]['messages'][1]['content'])

    def test_an_executed_test_is_the_judge_and_a_reviewer_without_verdict_does_not_block(self):
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make test_a.py'}]})])])
        self.script('c', self.coder_turn('test_a.py') + self.coder_turn('test_a.py')); self.script('r', [answer(content='looks fine to me')])
        runs = []
        def runner(commands):
            runs.append(commands); return {'status': 'failed', 'output': 'FAIL: test_x\nAssertionError'} if len(runs) == 1 else {'status': 'completed', 'output': 'OK'}
        out = self.team(vm_runner=runner).run('t')
        rounds = out['steps'][0]['rounds']
        self.assertEqual([(r['test']['passed'], r['verdict']) for r in rounds], [(False, 'FAIL(test)'), (True, 'no_verdict')])      # round 1: the test failed, no reviewer was bothered
        self.assertIn('the unit tests fail:\nFAIL: test_x', [b for k, b in self.seen if k == 'c'][2]['messages'][1]['content'])
        self.assertTrue(out['accepted']); self.assertEqual(len([r for r in out['agent_runs'] if r['role'] == 'reviewer']), 1); self.assertEqual(runs[0], [['python3', '-m', 'unittest', 'discover', '-v']])

    def test_the_planners_check_script_runs_after_the_developer_and_its_failure_goes_back(self):
        plan = answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make test_a.py', 'check': 'assert 1 + 1 == 2'}, {'title': 'two', 'instruction': 'make b.py'}]})])
        self.script('p', [plan]); self.script('c', self.coder_turn('test_a.py') * 2 + self.coder_turn('b.py')); self.script('r', [self.verdict('PASS'), self.verdict('PASS')])
        runs = []
        def runner(commands):
            runs.append(commands[0][1:])
            if len(runs) == 1: return {'status': 'failed', 'output': 'AssertionError: slugify missed the second example'}
            return {'status': 'completed', 'output': 'OK'}
        out = self.team(vm_runner=runner).run('t')
        self.assertTrue(out['accepted']); self.assertIn('acceptance_step1.py', self.ws.tree())              # the check is part of the project afterwards
        self.assertEqual(runs[0], ['acceptance_step1.py'])
        first_coder = [b for k, b in self.seen if k == 'c'][0]['messages'][1]['content']
        self.assertIn('This check script will be run against your work', first_coder); self.assertIn('assert 1 + 1 == 2', first_coder)
        second_coder = [b for k, b in self.seen if k == 'c'][2]['messages'][1]['content']
        self.assertIn('rejected: the check script of this step fails:\nAssertionError: slugify missed the second example', second_coder)
        self.assertNotIn(['-m', 'unittest', 'discover', '-v'], runs[:2])                                      # the unit tests judge only after the LAST step...
        self.assertEqual(runs[-1], ['-m', 'unittest', 'discover', '-v'])                                      # ...and test_a.py exists then
        self.assertEqual([r['verdict'] for r in out['steps'][0]['rounds']], ['FAIL(test)', 'PASS'])

    def test_a_broken_check_script_is_told_apart_from_unfinished_work(self):
        from guppi_runtime.devvm_agents import check_is_broken
        name = 'acceptance_step1.py'
        tb = lambda f, last: f'Traceback (most recent call last):\n  File "/workspace/{f}", line 3, in <module>\n    x\n{last}'
        self.assertTrue(check_is_broken(tb(name, "NameError: name 'os' is not defined"), name))
        self.assertTrue(check_is_broken(tb(name, 'SyntaxError: invalid syntax'), name))
        self.assertFalse(check_is_broken(tb(name, 'AssertionError'), name))                                   # the work does not do what the check asserts
        self.assertFalse(check_is_broken(tb(name, "ImportError: cannot import name 'slugify' from 'textutil'"), name))
        self.assertFalse(check_is_broken(tb('textutil.py', "NameError: name 'y' is not defined"), name))      # the error is in the developer's code, not in the check
        self.assertFalse(check_is_broken('', name))

    def test_a_broken_check_is_dropped_and_the_reviewer_decides(self):
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py', 'check': 'assert os.path.exists("a.py")'}]})])])
        self.script('c', self.coder_turn('a.py')); self.script('r', [self.verdict('PASS')])
        broken = 'Traceback (most recent call last):\n  File "/workspace/acceptance_step1.py", line 1, in <module>\nNameError: name \'os\' is not defined'
        out = self.team(vm_runner=lambda c: {'status': 'failed', 'output': broken}).run('t')
        self.assertTrue(out['accepted']); self.assertEqual(out['broken_checks'], 1); self.assertNotIn('acceptance_step1.py', self.ws.tree())
        self.assertEqual(out['steps'][0]['rounds'][0]['verdict'], 'PASS'); self.assertTrue(any('check script is itself broken' in l for l in self.lines))

    def test_the_strong_developer_takes_over_when_the_small_one_failed_once(self):
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py'}]})])])
        self.script('c', self.coder_turn('a.py')); self.script('s', self.coder_turn('a.py')); self.script('r', [self.verdict('FAIL', 'second example missing'), self.verdict('PASS')])
        team = DevOrchestrator(self.ws, self.host, {'planner': 'p', 'coder': 'c', 'reviewer': 'r', 'coder_strong': 's'}, audit=self.audit, say=self.lines.append, mode='pipeline')
        out = team.run('t')
        self.assertTrue(out['accepted']); self.assertEqual(out['escalations'], 1)
        self.assertEqual([r['model'] for r in out['agent_runs'] if r['role'] == 'coder'], ['c', 's']); self.assertEqual([r['label'] for r in out['agent_runs'] if r['role'] == 'coder'], ['coder s1 r1', 'coder s1 r2 (strong)'])
        self.assertIn('rejected: second example missing', [b for k, b in self.seen if k == 's'][0]['messages'][1]['content'])

    def test_the_reviewer_is_handed_the_diff_and_the_changed_files(self):
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py'}]})])]); self.script('c', self.coder_turn('a.py')); self.script('r', [self.verdict('PASS')])
        self.team().run('t')
        review = [b for k, b in self.seen if k == 'r'][0]['messages'][1]['content']
        self.assertIn('Changed files since the last commit: added: a.py', review); self.assertIn('+++ b/a.py', review); self.assertIn('+x = 1', review)

    def test_check_problem_finds_checks_that_cannot_judge(self):
        from guppi_runtime.devvm_agents import check_problem
        self.ws.write('textutil.py', 'def slugify(t):\n    return t\n')
        self.assertIsNone(check_problem('from textutil import slugify\nassert slugify("a") == "a"\n', self.ws))
        self.assertEqual(check_problem('def f(:\n', self.ws), 'it does not parse')
        self.assertEqual(check_problem("import os\nos.makedirs('calc')\n", self.ws), 'it creates or changes files')
        self.assertEqual(check_problem("with open('a.py', 'w') as f:\n    f.write('x')\n", self.ws), 'it writes files')
        self.assertEqual(check_problem("with open('a.py', mode='a') as f:\n    pass\n", self.ws), 'it writes files')
        self.assertIsNone(check_problem("with open('a.py') as f:\n    assert 'x' in f.read()\n", self.ws))
        self.assertEqual(check_problem('def slugify(t):\n    return t.lower()\nassert slugify("A") == "a"\n', self.ws), 'it defines the code it tests instead of importing it')
        self.assertIsNone(check_problem('def check():\n    from textutil import slugify\n    assert slugify("a") == "a"\ncheck()\n', self.ws))      # a wrapper around the import is fine

    def test_an_unusable_check_is_dropped_before_the_developer_sees_it(self):
        bad = "import os\nos.makedirs('calc')\n"
        plan = answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py', 'check': bad}]})])
        self.script('p', [plan, plan]); self.script('c', self.coder_turn('a.py')); self.script('r', [self.verdict('PASS')])     # the planner is asked a second time and repeats its mistake
        out = self.team(vm_runner=lambda c: self.fail('a dropped check must not run')).run('t')
        self.assertEqual(out['dropped_checks'], 1); self.assertTrue(out['accepted']); self.assertNotIn('check script', [b for k, b in self.seen if k == 'c'][0]['messages'][1]['content'])

    def test_a_plan_with_an_unusable_check_goes_back_to_the_planner_once(self):
        bad = answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py', 'check': "import os\nos.makedirs('calc')\n"}]})])
        good = answer([tc('submit_plan', {'steps': [{'title': 'one fixed', 'instruction': 'make a.py', 'check': 'from a import x\nassert x == 1'}]})])
        self.script('p', [bad, good]); self.script('c', self.coder_turn('a.py')); self.script('r', [self.verdict('PASS')])
        out = self.team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}).run('t')
        self.assertEqual((out['replans'], out['dropped_checks'], out['plan']), (1, 0, ['one fixed']))
        self.assertEqual([r['label'] for r in out['agent_runs'] if r['role'] == 'planner'], ['planner', 'planner (retry)'])
        retry_prompt = [b for k, b in self.seen if k == 'p'][1]['messages'][1]['content']
        self.assertIn('Your previous plan had unusable checks: step 1: it creates or changes files', retry_prompt); self.assertIn('This check script will be run', [b for k, b in self.seen if k == 'c'][0]['messages'][1]['content'])
        self.assertEqual(out['model_swaps'], 3)                                                           # the planner model stayed loaded for the second try

    def test_when_the_second_plan_is_unusable_too_the_first_one_stays(self):
        bad = answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py', 'check': "import os\nos.makedirs('calc')\n"}]})])
        self.script('p', [bad, answer(content='no plan')]); self.script('c', self.coder_turn('a.py')); self.script('r', [self.verdict('PASS')])
        out = self.team(vm_runner=lambda c: self.fail('dropped')).run('t')
        self.assertEqual((out['replans'], out['dropped_checks'], out['plan']), (0, 1, ['one'])); self.assertTrue(out['accepted'])

    def test_the_unittest_command_follows_the_layout_and_no_tests_ran_is_not_the_developers_failure(self):
        from guppi_runtime.devvm_tools import unittest_command
        self.assertEqual(unittest_command(self.ws), ['python3', '-m', 'unittest', 'discover', '-v'])
        self.ws.write('tests/test_ops.py', 'x = 1\n'); self.assertEqual(unittest_command(self.ws), ['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make test_a.py'}]})])]); self.script('c', self.coder_turn('test_a.py')); self.script('r', [self.verdict('PASS')])
        out = self.team(vm_runner=lambda c: {'status': 'failed', 'output': 'Ran 0 tests in 0.000s\n\nNO TESTS RAN'}).run('t')
        self.assertTrue(out['accepted']); self.assertEqual(len([r for r in out['agent_runs'] if r['role'] == 'coder']), 1)          # no retry because of it
        self.assertTrue(any('found no test to run' in l for l in self.lines))

    def arbitrated(self, review):
        plan = answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py', 'check': 'from a import x\nassert x == 2'}]})])
        self.script('p', [plan]); self.script('c', self.coder_turn('a.py') * 2); self.script('r', [review])
        return self.team(vm_runner=lambda c: {'status': 'failed', 'output': 'AssertionError'}).run('t')

    def test_when_the_check_fails_in_the_last_round_the_reviewer_arbitrates_and_only_pass_accepts(self):
        out = self.arbitrated(self.verdict('PASS'))
        self.assertTrue(out['accepted']); rounds = out['steps'][0]['rounds']
        self.assertEqual([r['verdict'] for r in rounds], ['FAIL(test)', 'PASS']); self.assertTrue(rounds[1]['overruled_check']); self.assertTrue(rounds[1]['test_failed'])
        review = [b for k, b in self.seen if k == 'r'][0]['messages'][1]['content']; self.assertIn('An automatic check of this step failed with:\nthe check script of this step fails:\nAssertionError', review); self.assertNotIn('acceptance_step1', review.split('An automatic check')[0])
        self.assertEqual(self.ws.log()[0]['message'], 'one')
        for k in ('c', 'r', 'p'): self.scripts.pop(k, None)
        self.seen.clear(); self.ws = DevWorkspace(Path(self.tmp.name), 'M-AGENT002', policy=dict(POLICY)); self.ws.create()
        self.assertFalse(self.arbitrated(self.verdict('FAIL', 'really wrong'))['accepted'])
        self.ws = DevWorkspace(Path(self.tmp.name), 'M-AGENT003', policy=dict(POLICY)); self.ws.create()
        self.assertFalse(self.arbitrated(answer(content='no verdict'))['accepted'])                        # a reviewer without verdict cannot overrule a failing check

    def test_at_most_one_lesson_ever_reaches_the_developer(self):
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py'}]})])]); self.script('c', self.coder_turn('a.py')); self.script('r', [self.verdict('PASS')])
        out = self.team().run('t', lessons=['LESSON-ONE text', 'LESSON-TWO text', 'LESSON-THREE text'])
        coder_task = [b for k, b in self.seen if k == 'c'][0]['messages'][1]['content']
        self.assertIn('A lesson from the team\'s knowledge base that matches this code:\n- LESSON-ONE text', coder_task)
        self.assertNotIn('LESSON-TWO', coder_task); self.assertNotIn('LESSON-THREE', coder_task); self.assertEqual(out['lessons_used'], 1)
        for k, b in self.seen:
            if k != 'c': self.assertNotIn('LESSON-ONE', json.dumps(b['messages']))                         # planner and reviewer get none
        self.scripts = {}; self.seen.clear(); self.ws = DevWorkspace(Path(self.tmp.name), 'M-AGENT009', policy=dict(POLICY)); self.ws.create()
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'make a.py'}]})])]); self.script('c', self.coder_turn('a.py')); self.script('r', [self.verdict('PASS')])
        out = self.team().run('t'); self.assertEqual(out['lessons_used'], 0); self.assertNotIn('knowledge base', [b for k, b in self.seen if k == 'c'][0]['messages'][1]['content'])

    def test_without_a_vm_runner_the_check_is_not_shown_and_not_run(self):
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'x', 'check': 'assert False'}]})])]); self.script('c', self.coder_turn('a.py')); self.script('r', [self.verdict('PASS')])
        out = self.team().run('t')
        self.assertTrue(out['accepted']); self.assertNotIn('check script', [b for k, b in self.seen if k == 'c'][0]['messages'][1]['content']); self.assertNotIn('acceptance_step1.py', self.ws.tree())

    def test_without_a_vm_runner_or_without_tests_no_test_runs(self):
        self.script('p', [answer([tc('submit_plan', {'steps': [{'title': 'one', 'instruction': 'x'}]})])]); self.script('c', self.coder_turn('a.py')); self.script('r', [self.verdict('PASS')])
        out = self.team(vm_runner=lambda c: self.fail('no tests in the workspace, the VM must not be asked')).run('t')
        self.assertEqual(out['steps'][0]['rounds'][0]['test'], {'ran': False, 'passed': None})


if __name__ == '__main__':
    unittest.main()
