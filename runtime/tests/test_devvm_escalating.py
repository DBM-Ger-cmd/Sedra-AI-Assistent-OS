import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import json, tempfile, unittest
from pathlib import Path
from guppi_runtime.devvm import DevWorkspace
from guppi_runtime.devvm_agents import DevOrchestrator, ModelHost

POLICY = {'max_files': 20, 'max_file_bytes': 8000, 'max_input_bytes': 20000}
GOOD_CHECK = 'from a import x\nassert x == 1'


def tc(name, args, i=1):
    return {'id': f'c{i}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}


def answer(calls=None, content=''):
    return {'choices': [{'message': {'content': content, 'tool_calls': calls or []}, 'finish_reason': 'tool_calls' if calls else 'stop'}], 'usage': {'completion_tokens': 10}}


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ws = DevWorkspace(Path(self.tmp.name), 'M-ESCAL001', policy=dict(POLICY)); self.ws.create()
        self.seen, self.scripts, self.loads, self.lines = [], {}, [], []
        outer = self
        class Loader:
            def load(self, key):
                outer.loads.append(key)
                def plain(body, key=key):
                    outer.seen.append((key, body)); return next(outer.scripts[key])
                return key, plain, {}
            def unload(self): pass
        self.host = ModelHost(Loader())

    def team(self, **kw):
        # the strong model is the checker's model ('p'): after the checker it is already loaded
        return DevOrchestrator(self.ws, self.host, {'planner': 'p', 'coder': 'c', 'coder_strong': 'p'}, mode='escalating', say=self.lines.append, **kw)
    def script(self, key, turns): self.scripts[key] = iter(turns)
    def write(self, x, i=1): return answer([tc('write_file', {'path': 'a.py', 'content': f'x = {x}\n'}, i)])
    def done(self, i=1): return answer([tc('submit_result', {'summary': 'done'}, i)])
    def checker(self, check=GOOD_CHECK): return answer([tc('submit_plan', {'steps': [{'title': 'task', 'instruction': 'make a.py with x = 1', 'check': check}]})])
    def prompts(self, key): return [b['messages'][1]['content'] for k, b in self.seen if k == key]


class EscalatingTests(Case):
    def test_the_small_developer_alone_and_a_passing_check_costs_no_strong_work(self):
        self.script('c', [self.write(1), self.done(2)]); self.script('p', [self.checker()])
        out = self.team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}).run('make a.py with x = 1')
        self.assertTrue(out['accepted']); self.assertEqual(out['mode'], 'escalating'); self.assertEqual(out['escalations'], 0)
        self.assertEqual([r['label'] for r in out['agent_runs']], ['coder (alone)', 'checker']); self.assertEqual(self.loads, ['c', 'p'])
        self.assertEqual([r['verdict'] for r in out['steps'][0]['rounds']], ['PASS(test)']); self.assertEqual(self.ws.log()[0]['message'], 'task'); self.assertFalse(out['steps'][0]['unjudged'])
        self.assertIn('already made a first attempt', self.prompts('p')[0]); self.assertIn('make a.py with x = 1', self.prompts('c')[0])
        self.assertNotIn('check script', self.prompts('c')[0])                                           # the developer never sees the check in the first attempt
        coder_tools = [t['function']['name'] for t in [b for k, b in self.seen if k == 'c'][0]['tools']]; self.assertNotIn('git_commit', coder_tools); self.assertNotIn('delegate', coder_tools)

    def test_a_failing_check_brings_the_strong_model_in_without_a_model_swap(self):
        self.script('c', [self.write(0), self.done(2)]); self.script('p', [self.checker(), self.write(1), self.done(2)])
        answers = iter([{'status': 'failed', 'output': 'AssertionError'}, {'status': 'completed', 'output': 'ok'}])
        out = self.team(vm_runner=lambda c: next(answers)).run('make a.py with x = 1')
        self.assertTrue(out['accepted']); self.assertEqual(out['escalations'], 1); self.assertEqual(self.ws.read('a.py'), 'x = 1\n')
        self.assertEqual([r['label'] for r in out['agent_runs']], ['coder (alone)', 'checker', 'coder (strong) r1']); self.assertEqual(self.loads, ['c', 'p'])      # the checker had loaded it
        self.assertEqual([r['verdict'] for r in out['steps'][0]['rounds']], ['FAIL(test)', 'PASS(test)'])
        strong = self.prompts('p')[1]
        self.assertIn('does NOT meet the requirement: the check script of this step fails:\nAssertionError', strong); self.assertIn(GOOD_CHECK, strong); self.assertIn('first attempt', strong)

    def test_when_the_strong_model_fails_too_the_work_is_committed_as_unreviewed(self):
        self.script('c', [self.write(0), self.done(2)]); self.script('p', [self.checker(), self.write(2), self.done(2), self.write(3, 3), self.done(4), self.verdict('FAIL')])
        fails = iter([{'status': 'failed', 'output': f'AssertionError {n}'} for n in range(3)])
        out = self.team(vm_runner=lambda c: next(fails), max_rounds=2).run('t')
        self.assertFalse(out['accepted']); self.assertEqual(out['escalations'], 2); self.assertEqual([r['verdict'] for r in out['steps'][0]['rounds']], ['FAIL(test)'] * 3)
        self.assertEqual(self.ws.log()[0]['message'], 'UNREVIEWED: task')

    def test_without_a_vm_runner_nothing_can_be_judged_and_the_strong_model_is_never_loaded(self):
        self.script('c', [self.write(1), self.done(2)])
        out = self.team().run('t')
        self.assertTrue(out['accepted']); self.assertTrue(out['steps'][0]['unjudged']); self.assertEqual(self.loads, ['c']); self.assertEqual(len(out['agent_runs']), 1)
        self.assertEqual(out['steps'][0]['rounds'][0]['verdict'], 'unjudged')

    def test_an_unusable_check_gets_one_retry_and_then_the_attempt_stays_unjudged(self):
        bad = "import os\nos.makedirs('calc')\n"
        self.script('c', [self.write(1), self.done(2)]); self.script('p', [self.checker(bad), self.checker(bad)])
        out = self.team(vm_runner=lambda c: self.fail('an unusable check must not run')).run('t')
        self.assertEqual([r['label'] for r in out['agent_runs']], ['coder (alone)', 'checker', 'checker (retry)']); self.assertEqual((out['replans'], out['dropped_checks']), (1, 1))
        self.assertTrue(out['steps'][0]['unjudged']); self.assertIn('Your previous check was unusable: it creates or changes files', self.prompts('p')[1])
        self.scripts = {}; self.seen.clear(); self.ws = DevWorkspace(Path(self.tmp.name), 'M-ESCAL002', policy=dict(POLICY)); self.ws.create()
        self.script('c', [self.write(1), self.done(2)]); self.script('p', [self.checker(bad), self.checker()])
        out = self.team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}).run('t')
        self.assertEqual((out['replans'], out['dropped_checks']), (1, 0)); self.assertFalse(out['steps'][0]['unjudged']); self.assertEqual(out['steps'][0]['rounds'][0]['verdict'], 'PASS(test)')

    def test_a_check_that_is_itself_broken_does_not_count_against_the_developer(self):
        self.script('c', [self.write(1), self.done(2)]); self.script('p', [self.checker()])
        broken = 'Traceback (most recent call last):\n  File "/workspace/acceptance_step1.py", line 1, in <module>\nNameError: name \'y\' is not defined'
        out = self.team(vm_runner=lambda c: {'status': 'failed', 'output': broken}).run('t')
        self.assertTrue(out['accepted']); self.assertTrue(out['steps'][0]['unjudged']); self.assertEqual(out['escalations'], 0); self.assertEqual(out['broken_checks'], 1)

    def test_at_most_one_lesson_reaches_either_developer(self):
        self.script('c', [self.write(0), self.done(2)]); self.script('p', [self.checker(), self.write(1), self.done(2)])
        answers = iter([{'status': 'failed', 'output': 'AssertionError'}, {'status': 'completed', 'output': 'ok'}])
        out = self.team(vm_runner=lambda c: next(answers)).run('t', lessons=['LESSON-ONE', 'LESSON-TWO'])
        self.assertEqual(out['lessons_used'], 1)
        for text in (self.prompts('c')[0], self.prompts('p')[1]):
            self.assertIn('LESSON-ONE', text); self.assertNotIn('LESSON-TWO', text)
        self.assertNotIn('LESSON-ONE', self.prompts('p')[0])                                              # the checker is not a developer and gets none

    def verdict(self, v, cause='x', i=1): return answer([tc('submit_review', {'verdict': v, 'cause': cause}, i)])

    def test_the_same_failure_twice_makes_the_check_suspect_and_the_strong_model_arbitrates(self):
        self.script('c', [self.write(0), self.done(2)]); self.script('p', [self.checker(), self.write(2), self.done(2), self.verdict('PASS')])
        out = self.team(vm_runner=lambda c: {'status': 'failed', 'output': 'AssertionError'}, max_rounds=3).run('t')
        self.assertTrue(out['accepted']); self.assertTrue(out['steps'][0]['rounds'][-1].get('overruled_check')); self.assertEqual(out['escalations'], 1)
        self.assertEqual(self.ws.log()[0]['message'], 'task (check disputed)'); self.assertEqual(self.loads, ['c', 'p'])      # no extra swap

    def test_an_arbiter_that_does_not_pass_the_work_leaves_it_unreviewed(self):
        self.script('c', [self.write(0), self.done(2)]); self.script('p', [self.checker(), self.write(2), self.done(2), self.verdict('FAIL')])
        out = self.team(vm_runner=lambda c: {'status': 'failed', 'output': 'AssertionError'}, max_rounds=3).run('t')
        self.assertFalse(out['accepted']); self.assertEqual(self.ws.log()[0]['message'], 'UNREVIEWED: task')

    def test_the_audit_names_the_mode(self):
        class Audit:
            def __init__(self): self.events = []
            def append(self, event, **kw): self.events.append((event, kw.get('payload')))
        audit = Audit(); self.script('c', [self.write(1), self.done(2)]); self.script('p', [self.checker()])
        DevOrchestrator(self.ws, self.host, {'planner': 'p', 'coder': 'c', 'coder_strong': 'p'}, mode='escalating', audit=audit, vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}).run('t')
        done = [p for e, p in audit.events if e == 'DEVVM_RUN_DONE'][0]; step = [p for e, p in audit.events if e == 'DEVVM_STEP'][0]
        self.assertEqual((done['mode'], done['steps'], step['mode'], step['unjudged']), ('escalating', 1, 'escalating', False))


class CheckFirstTests(Case):
    MODELS = {'planner': 'p', 'coder': 'c', 'coder_strong': 'p'}

    def first_team(self, models=None, **kw):
        return DevOrchestrator(self.ws, self.host, models or self.MODELS, mode='escalating', say=self.lines.append, check_first=True, **kw)

    def test_the_check_is_written_before_the_code_from_the_task_alone(self):
        self.script('p', [self.checker()]); self.script('c', [self.write(1), self.done(2)])
        out = self.first_team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}).run('make `a.py` with x = 1')
        self.assertTrue(out['accepted']); self.assertEqual(self.loads, ['p', 'c'])
        self.assertEqual([r['label'] for r in out['agent_runs']], ['checker', 'coder (alone)'])
        self.assertIn('No code exists yet', self.prompts('p')[0]); self.assertNotIn('already made a first attempt', self.prompts('p')[0])
        self.assertIn('ONE complete valid example', self.prompts('p')[0])
        self.assertEqual([r['verdict'] for r in out['steps'][0]['rounds']], ['PASS(test)'])

    def test_a_check_may_import_the_module_the_task_names_before_it_exists(self):
        helper = 'from calc import add\ndef helper(v):\n    return v\nassert helper(add(1, 2)) == 3'
        self.script('p', [self.checker(helper)]); self.script('c', [self.write(1), self.done(2)])
        out = self.first_team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}).run('Create `calc.py` with add(a, b).')
        self.assertEqual(out['rejected_checks'], []); self.assertFalse(out['steps'][0]['unjudged'])
        self.setUp()
        self.script('p', [self.checker(helper), self.checker(helper)]); self.script('c', [self.write(1), self.done(2)])
        out = self.first_team(vm_runner=lambda c: self.fail('an unusable check must not run')).run('Create the add function.')
        self.assertEqual(len(out['rejected_checks']), 2); self.assertTrue(out['steps'][0]['unjudged'])

    def test_different_models_for_coder_and_checker_never_run_at_the_same_time(self):
        self.script('p', [self.checker()]); self.script('c', [self.write(1), self.done(2)])
        out = self.first_team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}, parallel_check=True).run('make `a.py` with x = 1')
        self.assertTrue(out['accepted']); self.assertEqual(self.loads, ['p', 'c'])

    def test_with_one_model_code_and_check_run_at_the_same_time_and_the_model_is_loaded_once(self):
        import threading
        threads, order = set(), []
        coder_turns, checker_turns = iter([self.write(1), self.done(2)]), iter([self.checker()])
        outer = self
        class Loader:
            def load(self, key):
                outer.loads.append(key)
                def plain(body):
                    threads.add(threading.get_ident())
                    is_coder = any(t['function']['name'] == 'write_file' for t in body['tools'])
                    order.append('coder' if is_coder else 'checker')
                    return next(coder_turns if is_coder else checker_turns)
                return key, plain, {}
            def unload(self): pass
        host = ModelHost(Loader())
        team = DevOrchestrator(self.ws, host, {'planner': 'm', 'coder': 'm', 'coder_strong': 'm'}, mode='escalating', say=self.lines.append, check_first=True, parallel_check=True,
                               vm_runner=lambda c: {'status': 'completed', 'output': 'ok'})
        out = team.run('make `a.py` with x = 1')
        self.assertTrue(out['accepted']); self.assertEqual(self.loads, ['m']); self.assertEqual(len(threads), 2); self.assertEqual(sorted(set(order)), ['checker', 'coder'])
        self.assertEqual(self.ws.read('a.py'), 'x = 1\n')

    def test_an_arbiter_model_of_its_own_judges_when_the_checks_keep_failing(self):
        models = {**self.MODELS, 'arbiter': 'a'}
        self.script('c', [self.write(0), self.done(2)]); self.script('p', [self.checker(), self.write(2), self.done(2), self.write(3, 3), self.done(4)])
        self.script('a', [answer([tc('submit_review', {'verdict': 'PASS', 'cause': ''})])])
        fails = iter([{'status': 'failed', 'output': f'AssertionError {n}'} for n in range(3)])
        out = DevOrchestrator(self.ws, self.host, models, mode='escalating', say=self.lines.append, vm_runner=lambda c: next(fails), max_rounds=2).run('t')
        self.assertIn('a', self.loads); self.assertTrue(any(r.get('overruled_check') for r in out['steps'][0]['rounds'])); self.assertTrue(out['accepted'])
        self.assertEqual([r['model'] for r in out['agent_runs'] if r['label'].startswith('arbiter')], ['a'])


def run_driver(files):
    """Runs the evidence driver the way the microVM would (a fresh interpreter in a folder with the workspace files) and returns its stdout."""
    import os, subprocess, sys
    with tempfile.TemporaryDirectory() as tmp:
        for name, content in files.items():
            (Path(tmp) / name).write_text(content, encoding='utf-8')
        run = subprocess.run([sys.executable, 'driver.py', 'check.py'], cwd=tmp, capture_output=True, text=True, timeout=60)
        return run.stdout + run.stderr


class EvidenceTests(Case):
    def table(self, check, work):
        from guppi_runtime.devvm_evidence import DRIVER, parse
        return parse(run_driver({'driver.py': DRIVER, 'check.py': check, **work}))

    def test_a_chain_of_conditions_names_the_first_false_part_with_both_values(self):
        from guppi_runtime.devvm_evidence import bug_report
        work = {'a.py': 'x = 3\ny = [1, 2]\nz = None\n'}
        check = '\n'.join(['from a import x, y, z', 'assert x == 3 and y == [1, 2, 5] and z is None', 'assert 7 in y', 'assert z is not None', 'assert x == 4', ''])
        report = bug_report(self.table(check, work), limit=4)
        self.assertIn('`y == [1, 2, 5]`: expected [1, 2, 5] but the work gives [1, 2]', report)       # the part of the chain, not the whole line
        self.assertIn('`7 in y`: left side is 7, right side is [1, 2]', report)
        self.assertIn('`z is not None`: left side is None, right side is None', report)
        self.assertIn('expects 4 but the work gives 3', report)                                          # a plain == keeps the old wording
        self.assertNotIn('`x == 4`', report)

    def test_a_script_that_stops_in_a_loop_names_the_line_and_the_case(self):
        from guppi_runtime.devvm_evidence import bug_report
        nl = chr(10)
        check = nl.join(['from a import f', 'assert f(1) == 1', 'for bad in (None, [], {"x": 1}):', '    try: f(bad)', '    except ValueError: pass', '    else: raise AssertionError("no error for a bad value")', ''])
        work = {'a.py': 'def f(v):' + nl + '    if v is None: raise ValueError("x")' + nl + '    return v' + nl}
        report = bug_report(self.table(check, work))
        self.assertIn('The test script stopped with: AssertionError: no error for a bad value', report)
        self.assertIn('line 6', report); self.assertIn('bad=[]', report)

    def test_a_bug_report_names_the_first_failing_assertions_with_expected_and_actual(self):
        from guppi_runtime.devvm_evidence import bug_report
        nl = chr(10)
        check = nl.join(['from a import x', 'assert x == 1', 'assert x == 3', 'assert x == 7', 'assert x == 8', ''])
        work = {'a.py': 'x = 3' + nl}
        report = bug_report(self.table(check, work))
        self.assertIn('expects 1 but the work gives 3', report)
        self.assertIn('expects 7 but the work gives 3', report)
        self.assertNotIn('expects 8', report)
        self.assertEqual(bug_report(self.table(nl.join(['from a import x', 'assert x == 3', '']), work)), '')
        self.assertEqual(bug_report({'sites': []}), '')
        self.assertIn('line 2', bug_report(self.table(check, work), limit=1))
        self.assertNotIn('expects 7', bug_report(self.table(check, work), limit=1))

    def test_every_assertion_is_run_to_the_end_with_what_it_got_and_expected(self):
        check = ('from a import x\n\ndef test():\n    assert x == 1\n    for v in (1, 2, 3):\n        assert x + v > 0\n    assert x == 5, "msg"\n    assert [x] == [1, 2]\n\ntest()\nassert x\n')
        data = self.table(check, {'a.py': 'x = 3\n'})
        self.assertIsNone(data['setup_error'])
        rows = {s['n']: s for s in data['sites']}
        self.assertEqual(sorted(rows), [1, 2, 3, 4, 5])
        self.assertEqual((rows[1]['fail'], rows[1]['first']['got'], rows[1]['first']['expected']), (1, '3', '1'))
        self.assertEqual((rows[2]['pass'], rows[2]['fail']), (3, 0))
        self.assertEqual((rows[3]['first']['got'], rows[3]['first']['expected']), ('3', '5'))
        self.assertEqual((rows[4]['first']['got'], rows[4]['first']['expected']), ('[3]', '[1, 2]'))
        self.assertEqual(rows[5]['pass'], 1)
        self.assertEqual(rows[1]['line'], 4)

    def test_the_script_runs_as_if_started_with_python3_file(self):
        check = ('import os, sys\nsys.path.insert(0, os.path.dirname(__file__))\nfrom a import x\n\ndef main():\n    assert x == 3\n\nif __name__ == "__main__":\n    main()\nassert x == 4\n')
        data = self.table(check, {'a.py': 'x = 3\n'})
        self.assertIsNone(data['setup_error'])
        rows = {s['n']: s for s in data['sites']}
        self.assertEqual((rows[1]['pass'], rows[2]['fail']), (1, 1))

    def test_assertions_that_never_ran_are_reported_as_not_reached_and_not_as_passing(self):
        from guppi_runtime.devvm_evidence import format_evidence
        data = self.table('import nothing_here\nassert True\n', {})
        text = format_evidence('', data)
        self.assertIn('NOT REACHED', text); self.assertNotIn('passes (0 of 0)', text); self.assertIn('1 were not reached.', text); self.assertIn('ModuleNotFoundError', text)

    def test_many_failing_assertions_are_summarised_and_passing_ones_are_ranges(self):
        from guppi_runtime.devvm_evidence import format_evidence
        sites = [{'n': i, 'line': i, 'src': 'assert f(%d) == 1' % i, 'pass': 1 if i in (1, 2, 3, 20) else 0, 'fail': 0 if i in (1, 2, 3, 20) else 1, 'error': 0,
                  'first': None if i in (1, 2, 3, 20) else {'got': '[%d]' % i, 'expected': '[]'}} for i in range(1, 21)]
        text = format_evidence('', {'sites': sites, 'setup_error': None})
        self.assertIn('#4 (line 4) FAILS', text); self.assertIn('#11 (line 11) FAILS', text); self.assertNotIn('#12 (line 12) FAILS', text)
        self.assertIn('and 8 more assertions fail: #12-#19', text); self.assertIn('pass: #1-#3, #20', text); self.assertIn('16 of 20 assertions fail.', text)
        self.assertLess(len(text), 3500)

    def test_an_error_inside_an_assertion_and_a_broken_script_are_reported_not_raised(self):
        data = self.table('from a import x\nassert x.missing == 1\nassert x == 3\n', {'a.py': 'x = 3\n'})
        rows = {s['n']: s for s in data['sites']}
        self.assertEqual((rows[1]['error'], rows[2]['pass']), (1, 1)); self.assertIn('AttributeError', rows[1]['first']['error'])
        data = self.table('import nothing_here\nassert True\n', {})
        self.assertIn('ModuleNotFoundError', data['setup_error']); self.assertEqual(data['sites'][0]['pass'] + data['sites'][0]['fail'], 0)

    def test_the_output_is_parsed_only_when_the_driver_reported(self):
        from guppi_runtime.devvm_evidence import parse
        self.assertIsNone(parse('')); self.assertIsNone(parse('Traceback...')); self.assertIsNone(parse('EVIDENCE_JSON {broken')); self.assertIsNone(parse('EVIDENCE_JSON [1]'))
        self.assertEqual(parse('noise\nEVIDENCE_JSON {"sites": [], "setup_error": null}\n')['sites'], [])

    def test_the_evidence_text_numbers_the_assertions_and_says_how_many_fail(self):
        from guppi_runtime.devvm_evidence import format_evidence
        data = self.table('from a import x\nassert x == 3\nassert x == 1\n', {'a.py': 'x = 3\n'})
        text = format_evidence('', data)
        self.assertIn('pass: #1', text); self.assertIn('#2 (line 3) FAILS 1 of 1 times: expected 1 but the work gives 3', text); self.assertIn('1 of 2 assertions fail.', text)
        self.assertLessEqual(len(format_evidence('', {'sites': [{'n': i, 'line': i, 'src': 'assert ' + 'x' * 200, 'pass': 0, 'fail': 1, 'error': 0, 'first': {'got': '1', 'expected': '2'}} for i in range(100)], 'setup_error': None})), 6100)

    def test_the_arbiter_sees_the_check_results_and_the_rules_and_the_helper_files_are_gone(self):
        models = {**CheckFirstTests.MODELS, 'arbiter': 'a'}
        check = 'from a import x\nassert x == 1\nassert x == 5'
        self.script('c', [self.write(0), self.done(2)]); self.script('p', [self.checker(check), self.write(3), self.done(2), self.write(3, 3), self.done(4)])
        self.script('a', [answer([tc('submit_review', {'verdict': 'PASS', 'cause': '#1: NONE'})])])
        calls = []
        ws = self.ws

        def runner(commands):
            name = commands[0][1]
            calls.append(name)
            if name == 'acceptance_evidence.py':
                return {'status': 'completed', 'output': run_driver({'driver.py': ws.read('acceptance_evidence.py'), 'check.py': ws.read('acceptance_evidence_check.py'), 'a.py': ws.read('a.py')})}
            return {'status': 'failed', 'output': 'AssertionError first'}
        out = DevOrchestrator(self.ws, self.host, models, mode='escalating', say=self.lines.append, vm_runner=runner, max_rounds=2).run('t')
        prompt = self.prompts('a')[0]
        self.assertIn('Evidence about the automatic check', prompt); self.assertIn('#1 (line 2) FAILS 1 of 1 times: expected 1 but the work gives 3', prompt)
        self.assertIn('#2 (line 3) FAILS 1 of 1 times: expected 5 but the work gives 3', prompt); self.assertIn('2 of 2 assertions fail.', prompt)
        self.assertIn('How to judge: the work is judged against the TASK', prompt); self.assertIn('The check itself may be wrong', prompt)
        self.assertIn('acceptance_evidence.py', calls); self.assertNotIn('acceptance_evidence.py', self.ws.tree()); self.assertNotIn('acceptance_evidence_check.py', self.ws.tree())
        self.assertTrue(out['accepted'])

    def test_without_a_vm_runner_or_a_driver_report_the_arbiter_gets_the_old_prompt(self):
        team = self.team()
        self.assertEqual(team._evidence({'check': 'assert True'}), '')
        team = self.team(vm_runner=lambda c: {'status': 'completed', 'output': 'no report'})
        self.assertEqual(team._evidence({'check': 'assert True'}), ''); self.assertEqual(team._evidence({'check': ''}), '')
        self.assertEqual([p for p in self.ws.tree() if p.startswith('acceptance_')], [])


class TidyTests(Case):
    def writes(self, i=1):
        return answer([tc('write_file', {'path': 'a.py', 'content': '"""doc"""\n# note\nx = 1  # trailing\n'}, i), tc('write_file', {'path': 'debug_a.py', 'content': 'print(1)\n'}, i + 1)])

    def run_team(self, **kw):
        self.script('c', [self.writes(), self.done(3)]); self.script('p', [self.checker()])
        return self.team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}, **kw).run('make `a.py` with x = 1')

    def test_with_tidy_the_comments_go_and_new_helper_files_are_deleted_after_the_coder_turn(self):
        out = self.run_team(tidy=True)
        self.assertTrue(out['accepted'])
        self.assertEqual(self.ws.read('a.py'), 'x = 1\n'); self.assertNotIn('debug_a.py', self.ws.tree())
        self.assertEqual([(t['stripped'], t['deleted']) for t in out['tidy']], [(['a.py'], ['debug_a.py'])])
        self.assertTrue(any(line.startswith('   tidy: stripped a.py; deleted debug_a.py') for line in self.lines))

    def test_the_stripped_comments_are_saved_to_the_comment_log_before_they_are_gone(self):
        log = Path(self.tmp.name) / 'logs' / 'comments.jsonl'
        out = self.run_team(tidy=True, comment_log=log, comment_meta={'spec': 's', 'stage': 'one'})
        rows = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
        self.assertEqual([(r['kind'], r['text']) for r in rows], [('docstring', 'doc'), ('comment', 'note'), ('comment', 'trailing')])
        self.assertTrue(all(r['path'] == 'a.py' and r['spec'] == 's' and r['stage'] == 'one' and r['turn'] == 1 for r in rows))
        self.assertNotIn('comments', out['tidy'][0])
        self.assertEqual(self.ws.read('a.py'), 'x = 1\n')

    def test_a_comment_log_that_cannot_be_written_does_not_stop_the_build(self):
        blocked = Path(self.tmp.name) / 'file'
        blocked.write_text('x', encoding='utf-8')
        out = self.run_team(tidy=True, comment_log=blocked / 'sub' / 'c.jsonl')
        self.assertTrue(out['accepted'])
        self.assertTrue(any('comment log not written' in line for line in self.lines))

    def test_without_tidy_nothing_is_touched(self):
        out = self.run_team()
        self.assertIn('# note', self.ws.read('a.py')); self.assertIn('debug_a.py', self.ws.tree()); self.assertEqual(out['tidy'], [])


class SoloTests(Case):
    def solo(self, **kw):
        return DevOrchestrator(self.ws, self.host, {'planner': 'c', 'coder': 'c', 'coder_strong': 'c'}, mode='solo', say=self.lines.append, **kw)

    def test_one_developer_works_in_one_conversation_with_no_checker_no_arbiter_and_no_strong_coder(self):
        self.script('c', [self.write(1), answer([tc('run_python', {'path': 'check_a.py'}, 2)]), self.done(3)])
        out = self.solo(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}).run('make a.py with x = 1')
        self.assertEqual(out['mode'], 'solo'); self.assertTrue(out['accepted']); self.assertEqual([r['label'] for r in out['agent_runs']], ['solo developer'])
        self.assertEqual(self.loads, ['c']); self.assertEqual(out['escalations'], 0); self.assertEqual(self.ws.log()[0]['message'], 'task')
        tools = [t['function']['name'] for t in [b for k, b in self.seen if k == 'c'][0]['tools']]
        for name in ('run_python', 'append_file', 'edit_file', 'submit_result'): self.assertIn(name, tools)
        for name in ('git_commit', 'run_tests', 'delegate'): self.assertNotIn(name, tools)
        first = [b for k, b in self.seen if k == 'c'][0]['messages']
        self.assertIn('ONLY developer and the ONLY checker', first[0]['content']); self.assertIn('do not ask questions', first[0]['content'])
        self.assertNotIn('_messages', out['agent_runs'][0])

    def test_after_a_failed_acceptance_test_the_same_developer_continues_his_conversation(self):
        team = self.solo(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'})
        self.script('c', [self.write(0), self.done(2), self.write(1, 3), self.done(4)])
        team.run('make a.py with x = 1')
        before = len([m for k, b in self.seen for m in b['messages'] if k == 'c'])
        result = team.continue_solo('line 1: the test expects 1 but the work gives 0')
        self.assertEqual(result['stopped_by'], 'hand_in'); self.assertEqual(self.ws.read('a.py'), 'x = 1\n')
        last = [b for k, b in self.seen if k == 'c'][-1]['messages']
        roles = [m['role'] for m in last]; self.assertEqual(roles[0], 'system'); self.assertIn('x = 0', json.dumps(last))                 # he remembers what he wrote
        self.assertIn('expects 1 but the work gives 0', [m for m in last if m['role'] == 'user'][-1]['content'])
        self.assertEqual([r['label'] for r in team.runs], ['solo developer', 'solo developer (continued)']); self.assertTrue(before > 0)

    def test_continuing_without_a_first_run_is_refused_and_a_long_history_is_shortened(self):
        with self.assertRaises(ValueError): self.solo().continue_solo('report')
        from guppi_runtime.model_tools import compact_history
        big = [{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 'task'}] + [{'role': 'tool', 'tool_call_id': 'x', 'content': 'y' * 5000} for _ in range(20)]
        small = compact_history(big)
        self.assertEqual(len(small), len(big)); self.assertLess(sum(len(m['content']) for m in small), 8 * 5000 + 20 * 600)
        self.assertEqual(small[0]['content'], 'S'); self.assertEqual(small[1]['content'], 'task'); self.assertEqual(len(small[-1]['content']), 5000); self.assertLess(len(small[5]['content']), 700)
        self.assertEqual(compact_history(big[:5]), big[:5])


class CheckerRulesTests(unittest.TestCase):
    def test_checker_note_carries_the_rules_found_in_the_am_builds(self):
        from guppi_runtime.devvm_agents import CHECKER_NOTE
        for rule in ("ONE complete valid example", "contradict each other", "exactly as the task defines them"):
            self.assertIn(rule, CHECKER_NOTE)
        self.assertIn("submit_plan", CHECKER_NOTE)


if __name__ == '__main__':
    unittest.main()


class CompactArgumentsTests(unittest.TestCase):
    def test_cut_tool_call_arguments_stay_valid_json(self):
        from guppi_runtime.model_tools import compact_history
        call = {'id': 'c1', 'type': 'function', 'function': {'name': 'write_file', 'arguments': json.dumps({'path': 'a.py', 'content': 'x = 1\n' * 500})}}
        msgs = [{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 'task'}, {'role': 'assistant', 'content': None, 'tool_calls': [call]}] + [{'role': 'user', 'content': 'u'} for _ in range(9)]
        small = compact_history(msgs)
        data = json.loads(small[2]['tool_calls'][0]['function']['arguments'])
        self.assertEqual(data['path'], 'a.py'); self.assertLess(len(data['content']), 700)


class SoloStepsTests(Case):
    TASK = 'Write a.py with x = 1.\nWrite b.py with y = 2.\nNo comments.'

    def steps_team(self, **kw):
        return DevOrchestrator(self.ws, self.host, {'planner': 'c', 'coder': 'c', 'coder_strong': 'c'}, mode='solo', plan_steps=True, say=self.lines.append, **kw)

    def plan(self, *steps):
        return answer([tc('submit_plan', {'steps': [{'title': t, 'instruction': i, 'acceptance': 'it works', 'lines': l, 'interface': f} for t, i, l, f in steps]}, 0)])

    def write_b(self, i): return answer([tc('write_file', {'path': 'b.py', 'content': 'y = 2\n'}, i)])

    def solo_requests(self): return [b['messages'] for k, b in self.seen if k == 'c' and b['messages'][0]['content'].startswith('You are the ONLY developer')]

    def test_every_step_gets_a_fresh_short_conversation_with_its_task_lines_word_for_word(self):
        team = self.steps_team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'})
        self.script('c', [self.plan(('first', 'make a', [1], 'a.x'), ('second', 'make b', [2], 'b.y')), self.write(1), self.done(2), self.write_b(3), self.done(4)])
        out = team.run(self.TASK)
        self.assertEqual([r['label'] for r in out['agent_runs']], ['planner', 'solo developer (step 1/2)', 'solo developer (step 2/2)'])
        second = [json.dumps(m) for m in self.solo_requests() if 'YOUR step 2 of 2' in json.dumps(m)][0]
        self.assertNotIn('x = 1\\n', second)
        self.assertIn('1. first - a.x', second); self.assertIn('2. second - b.y', second)
        self.assertIn('Write b.py with y = 2.', second); self.assertIn('No comments.', second)
        self.assertNotIn('Write a.py with x = 1.', second.split('word for word')[1])
        self.assertIn('- step 1 (first): done', second); self.assertIn('a.py (', second)
        self.assertEqual((self.ws.read('a.py'), self.ws.read('b.py')), ('x = 1\n', 'y = 2\n'))

    def test_the_rework_gets_the_whole_task_or_with_fresh_rework_a_new_conversation(self):
        team = self.steps_team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'})
        self.script('c', [self.plan(('only', 'make a', [1], '')), self.write(1), self.done(2), self.write(5, 5), self.done(6)])
        team.run(self.TASK); team.continue_solo('line 1: expects 1')
        last = [b for k, b in self.seen if k == 'c'][-1]['messages']
        self.assertIn('x = 1', json.dumps(last)); self.assertIn('The complete task was:', [m for m in last if m['role'] == 'user'][-1]['content'])
        fresh = DevOrchestrator(self.ws, self.host, {'planner': 'c', 'coder': 'c', 'coder_strong': 'c'}, mode='solo', plan_steps=True, fresh_rework=True, say=self.lines.append, vm_runner=lambda c: {'status': 'completed', 'output': 'ok'})
        self.script('c', [self.plan(('only', 'make a', [1], '')), self.write(1), self.done(2), self.write(1, 3), self.done(4)])
        fresh.run(self.TASK); before = len(self.seen); fresh.continue_solo('line 1: expects 1')
        last = self.seen[before][1]['messages']
        self.assertEqual([m['role'] for m in last][:2], ['system', 'user']); self.assertEqual(len([m for m in last if m['role'] == 'user']), 1); self.assertIn('Write b.py with y = 2.', last[1]['content']); self.assertIn('expects 1', last[1]['content']); self.assertIn('a.py (', last[1]['content'])

    def test_a_plan_with_one_step_is_built_like_plain_solo_and_a_long_task_asks_for_two_steps(self):
        team = self.steps_team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'})
        self.script('c', [self.plan(('only', 'make a', [1], '')), self.write(1), self.done(2)])
        out = team.run(self.TASK)
        self.assertEqual([r['label'] for r in out['agent_runs']], ['planner', 'solo developer'])
        asked = json.dumps([b['messages'] for k, b in self.seen if k == 'c'][0])
        self.assertIn('[1] Write a.py with x = 1.', asked); self.assertNotIn('at least TWO steps', asked)
        self.script('c', [self.plan(('only', 'make a', [1], '')), self.write(1), self.done(2)])
        self.steps_team(vm_runner=lambda c: {'status': 'completed', 'output': 'ok'}).run(self.TASK + ' ' + 'x' * 2000)
        self.assertIn('at least TWO steps', json.dumps([b['messages'] for k, b in self.seen if k == 'c' and 'numbered lines' in json.dumps(b['messages'])][-1]))

    def test_the_syntax_option_sends_a_broken_file_back(self):
        team = self.steps_team(step_syntax_check=True, vm_runner=lambda c: {'status': 'completed', 'output': 'ok'})
        broken = answer([tc('write_file', {'path': 'a.py', 'content': 'def f(:\n'}, 1)])
        self.script('c', [self.plan(('only', 'make a', [1], '')), broken, self.done(2), self.write(1, 3), self.done(4)])
        out = team.run(self.TASK)
        self.assertIn('syntax 1', [r['label'] for r in out['agent_runs']][-1]); self.assertEqual(self.ws.read('a.py'), 'x = 1\n')


class WindowAndRescueTests(Case):
    def team(self, **kw):
        return DevOrchestrator(self.ws, self.host, {'planner': 'c', 'coder': 'c', 'coder_strong': 'c'}, mode='solo', say=self.lines.append, **kw)

    def test_the_limits_follow_the_window_of_the_model(self):
        big, small = self.team(), self.team(context=8192)
        self.assertEqual((big.solo_budget.compact_at, big.solo_budget.stub_at, big.solo_budget.max_tokens_per_answer, big.split_at), (19660, 6553, 8000, 1802))
        self.assertEqual((small.solo_budget.compact_at, small.solo_budget.stub_at, small.solo_budget.max_tokens_per_answer, small.split_at), (4915, 1638, 2048, 900))

    def test_a_run_that_ends_without_a_hand_in_and_leaves_a_broken_file_puts_it_back(self):
        self.ws.write('a.py', 'x = 1\n'); self.ws.commit('start')
        team = self.team()
        broken = answer([tc('write_file', {'path': 'a.py', 'content': 'def f(:\n'}, 1), tc('write_file', {'path': 'new.py', 'content': 'class (:\n'}, 2)])
        self.script('c', [broken])               # then the model answers nothing usable: no hand-in
        run = team._agent('solo', 'task', 'solo developer', model_role='coder', budget=team.solo_budget)
        self.assertNotEqual(run['stopped_by'], 'hand_in')
        self.assertEqual(self.ws.read('a.py'), 'x = 1\n'); self.assertEqual(self.ws.list('')[0]['name'], 'a.py'); self.assertEqual(len(self.ws.list('')), 1)
        self.assertEqual([(r['file'], r['outcome']) for r in team.rescued], [('a.py', 'restored'), ('new.py', 'deleted')])

    def test_a_parsable_file_and_a_hand_in_are_never_touched(self):
        self.ws.write('a.py', 'x = 1\n'); self.ws.commit('start')
        team = self.team()
        self.script('c', [answer([tc('write_file', {'path': 'a.py', 'content': 'x = 2\n'}, 1)]), self.done(2)])
        team._agent('solo', 'task', 'solo developer', model_role='coder', budget=team.solo_budget)
        self.assertEqual(self.ws.read('a.py'), 'x = 2\n'); self.assertEqual(team.rescued, [])

    def test_a_run_reports_the_biggest_prompt_and_the_calls_per_tool(self):
        team = self.team()
        self.script('c', [answer([tc('list_dir', {}, 1)]), answer([tc('list_dir', {'path': ''}, 2)]), self.done(3)])
        run = team._agent('solo', 'task', 'solo developer', model_role='coder', budget=team.solo_budget)
        self.assertEqual(run['tool_counts'], {'list_dir': 2, 'submit_result': 1}); self.assertIn('prompt_peak', run); self.assertTrue(any('peak' in l for l in self.lines))


class ChainedAssertTests(unittest.TestCase):
    def test_chained_asserts_are_found_with_their_part_count(self):
        from guppi_runtime.devvm_evidence import chained_asserts
        nl = chr(10)
        source = nl.join(['assert a == 1', 'assert a == 1 and b == 2', 'assert a == 1 and b == 2 and c == 3', 'assert x or y or z', 'assert p and q and r and s, "message"', ''])
        self.assertEqual(chained_asserts(source), [(3, 3), (5, 4)])
        self.assertEqual(chained_asserts(source, min_parts=2), [(2, 2), (3, 3), (5, 4)])
        self.assertEqual(chained_asserts('def broken(:'), [])
