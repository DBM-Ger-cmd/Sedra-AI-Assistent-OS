import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import json, tempfile, unittest
from pathlib import Path
from guppi_runtime.devvm import DevWorkspace
from guppi_runtime.devvm_tools import DevToolBox, broker_runner, ROLE_TOOLS
from guppi_runtime.model_tools import run_tool_loop

POLICY = {'max_files': 20, 'max_file_bytes': 4000, 'max_input_bytes': 20000}


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ws = DevWorkspace(Path(self.tmp.name), 'M-TOOLS001', policy=dict(POLICY)); self.ws.create()
    def box(self, role='coder', **kw): return DevToolBox(self.ws, role, **kw)


class RoleTests(Case):
    def test_each_role_sees_only_its_tools_and_a_terminal_call(self):
        coder, reviewer, tester = self.box('coder'), self.box('reviewer'), self.box('tester', vm_runner=lambda c: {})
        self.assertIn('write_file', coder.names); self.assertNotIn('write_file', reviewer.names); self.assertNotIn('run_tests', coder.names)   # no VM runner: no VM tools
        self.assertEqual((coder.terminal, reviewer.terminal, tester.terminal), ('submit_result', 'submit_review', 'submit_result'))
        self.assertIn('run_tests', tester.names); self.assertIn('run_python', tester.names)
        self.assertEqual(len(coder.schemas()), len(coder.names)); self.assertEqual([s['function']['name'] for s in reviewer.schemas()][-1], 'submit_review')
        self.assertIn('run_tests', self.box('coder', vm_runner=lambda c: {}).names)
        for role in ROLE_TOOLS: self.assertTrue(self.box(role).system)
        with self.assertRaises(ValueError): self.box('wizard')
    def test_a_tool_the_role_does_not_have_is_an_error_text_that_names_the_real_ones(self):
        out = self.box('reviewer').call('write_file', {'path': 'a.py', 'content': 'x'})
        self.assertTrue(out.startswith('error: unknown tool write_file')); self.assertIn('read_file', out); self.assertEqual(self.ws.tree(), [])


class WorkTests(Case):
    def test_a_coder_session_from_nothing_to_a_commit(self):
        b = self.box()
        self.assertEqual(b.call('list_dir', {}), '(empty)')
        self.assertEqual(b.call('write_file', {'path': 'calc/ops.py', 'content': 'def add(a, b):\n    return a + b\n'}), 'created calc/ops.py (32 bytes)')   # the folder is made on the way
        self.assertTrue(b.call('write_file', {'path': 'calc/ops.py', 'content': 'def add(a, b):\n    return a + b\n'}).startswith('overwrote'))
        self.assertEqual(b.call('make_dir', {'path': 'tests'}), 'created folder tests')
        b.call('write_file', {'path': 'tests/test_ops.py', 'content': 'from calc.ops import add\n'})
        self.assertEqual(b.call('list_dir', {}), 'dir  calc/\ndir  tests/')
        self.assertIn('file ops.py (32 B)', b.call('list_dir', {'path': 'calc'}))
        self.assertEqual(b.call('check_syntax', {'path': 'calc/ops.py'}), 'ok: the file parses')
        b.call('write_file', {'path': 'bad.py', 'content': 'def f(:\n'}); self.assertTrue(b.call('check_syntax', {'path': 'bad.py'}).startswith('SyntaxError line 1'))
        self.assertIn('calc/ops.py:1: def add(a, b):', b.call('search_text', {'text': 'DEF ADD'}))
        self.assertEqual(b.call('search_text', {'text': 'nothing like this'}), '(no match)')
        self.assertIn('added: bad.py, calc/ops.py, tests/test_ops.py', b.call('git_status', {}))
        self.assertEqual(b.call('git_log', {}), '(no commits yet)')
        self.assertTrue(b.call('git_commit', {'message': 'first'}).startswith('committed '))
        self.assertEqual(b.call('git_status', {}), 'clean: nothing changed since the last commit'); self.assertEqual(b.call('diff_files', {}), '(no changes since the last commit)')
        b.call('move_file', {'source': 'bad.py', 'destination': 'old/bad.py'}); b.call('delete_file', {'path': 'old/bad.py'})
        self.assertIn('deleted: bad.py', b.call('git_status', {})); self.assertIn('--- a/bad.py', b.call('diff_files', {}))
        r = self.box('reviewer'); self.assertTrue(r.call('git_log', {'limit': 5}).endswith(' first'))
        self.assertEqual(b.call('submit_result', {'summary': 'done'}), 'received'); self.assertEqual(b.final, {'summary': 'done'})
    def test_a_failed_edit_names_the_exact_text_when_only_the_white_space_differs_or_the_most_similar_lines(self):
        b = self.box(); nl = chr(10)
        b.call('write_file', {'path': 'a.py', 'content': 'def f(x):' + nl + '    total = x + 1' + nl + '    return total' + nl + nl + 'def g():' + nl + '    return 2' + nl})
        spaced = b.call('edit_file', {'path': 'a.py', 'old': 'total   =  x + 1' + nl + 'return total', 'new': 'x'})
        self.assertIn('IS in the file at lines 2-3', spaced); self.assertIn('    total = x + 1' + nl + '    return total', spaced)
        similar = b.call('edit_file', {'path': 'a.py', 'old': 'def f(y):', 'new': 'x'})
        self.assertIn('most similar lines', similar); self.assertIn('line 1: def f(x):', similar)
        self.assertIn('No similar line', b.call('edit_file', {'path': 'a.py', 'old': 'qqqqqqqq zzzz', 'new': 'x'}))
        self.assertEqual(self.ws.read('a.py').count('total = x + 1'), 1)

    def test_one_call_may_carry_at_most_6000_characters_and_the_answer_says_how_to_go_on(self):
        ws = DevWorkspace(Path(self.tmp.name), 'M-TOOLS002', policy={'max_files': 20, 'max_file_bytes': 60000, 'max_input_bytes': 200000}); ws.create()
        b = DevToolBox(ws, 'coder'); nl = chr(10); part = ('x = 1' + nl) * 1000
        self.assertEqual(len(part), 6000)
        self.assertTrue(b.call('write_file', {'path': 'a.py', 'content': part}).startswith('created'))
        for call in (('write_file', {'path': 'b.py', 'content': part + 'y'}), ('append_file', {'path': 'a.py', 'content': part + 'y'}), ('edit_file', {'path': 'a.py', 'old': 'x = 1', 'new': part + 'y'})):
            out = b.call(*call)
            self.assertTrue(out.startswith('error: too long: 6001 characters'), out); self.assertIn('append_file', out)
        self.assertEqual(len(ws.read('a.py')), 6000); self.assertNotIn('b.py', ws.tree())

    def test_a_placeholder_of_the_shortened_history_is_never_written_into_a_file(self):
        b = self.box()
        self.assertTrue(b.call('write_file', {'path': 'tm.py', 'content': 'x = 1'}).startswith('created'))
        for call in (('write_file', {'path': 'n.py', 'content': '[written: 1704 characters, they are in the file now]'}),
                     ('append_file', {'path': 'tm.py', 'content': 'def f():' + chr(10) + '    [...cut...] ' + chr(10)}),
                     ('edit_file', {'path': 'tm.py', 'old': 'x = 1', 'new': '[written: 12 characters, they are in the file now]'})):
            out = b.call(*call)
            self.assertTrue(out.startswith('error: '), out); self.assertIn('placeholder', out); self.assertIn('read_file', out)
        self.assertEqual(self.ws.read('tm.py'), 'x = 1'); self.assertNotIn('n.py', self.ws.tree())
        self.assertTrue(b.call('write_file', {'path': 'ok.py', 'content': 'note = "written: 5 characters"'}).startswith('created'))

    def test_a_refused_credential_like_name_says_how_to_go_on(self):
        out = self.box().call('write_file', {'path': 'token_meter.py', 'content': 'x = 1'})
        self.assertTrue(out.startswith('error: potential_credential_file'), out); self.assertIn('choose another name', out)

    def test_append_file_adds_to_the_end_and_needs_the_file_first(self):
        b = self.box(); nl = chr(10)
        self.assertIn('create it with write_file first', b.call('append_file', {'path': 'a.py', 'content': 'x = 1'}))
        b.call('write_file', {'path': 'a.py', 'content': 'x = 1'})
        self.assertTrue(b.call('append_file', {'path': 'a.py', 'content': 'y = 2' + nl}).startswith('appended to a.py'))
        b.call('append_file', {'path': 'a.py', 'content': 'z = 3' + nl})
        self.assertEqual(self.ws.read('a.py'), 'x = 1' + nl + 'y = 2' + nl + 'z = 3' + nl)
        self.assertTrue(b.call('append_file', {'path': 'a.py', 'content': ''}).startswith('error:'))
        self.assertNotIn('append_file', self.box('reviewer').names); self.assertIn('append_file', b.names)

    def test_edit_file_replaces_one_exact_piece_and_refuses_the_ambiguous(self):
        b = self.box(); nl = chr(10)
        b.call('write_file', {'path': 'a.py', 'content': 'x = 1' + nl + 'y = 1' + nl})
        self.assertEqual(b.call('edit_file', {'path': 'a.py', 'old': 'x = 1', 'new': 'x = 2'}), 'edited a.py (12 bytes)'); self.assertEqual(self.ws.read('a.py'), 'x = 2' + nl + 'y = 1' + nl)
        self.assertIn('not found', b.call('edit_file', {'path': 'a.py', 'old': 'z = 9', 'new': 'z'}))
        self.assertIn('occurs 2 times', b.call('edit_file', {'path': 'a.py', 'old': ' = ', 'new': '=='}))
        self.assertTrue(b.call('edit_file', {'path': 'a.py', 'old': '', 'new': 'x'}).startswith('error:')); self.assertTrue(b.call('edit_file', {'path': 'a.py', 'old': 'x'}).startswith('error:'))
        self.assertTrue(b.call('edit_file', {'path': 'nope.py', 'old': 'x', 'new': 'y'}).startswith('error:'))
        self.assertNotIn('edit_file', self.box('reviewer').names); self.assertEqual(self.ws.read('a.py'), 'x = 2' + nl + 'y = 1' + nl)

    def test_the_usual_ways_models_name_the_root_and_a_path_are_understood_but_nothing_else_gets_in(self):
        b = self.box(); b.call('write_file', {'path': 'pkg/a.py', 'content': 'x = 1\n'})
        for root in ('', '.', './', '/', '/workspace', '/workspace/', 'workspace'):
            self.assertEqual(b.call('list_dir', {'path': root}), 'dir  pkg/', root)
        self.assertEqual(b.call('list_dir', {}), 'dir  pkg/')
        for spelling in ('pkg/a.py', './pkg/a.py', '/workspace/pkg/a.py', 'workspace/pkg/a.py'):
            self.assertEqual(b.call('read_file', {'path': spelling}), 'x = 1\n', spelling)
        self.assertIn('file a.py', b.call('list_dir', {'path': './pkg'}))
        self.assertEqual(b.call('move_file', {'source': '/workspace/pkg/a.py', 'destination': './new/b.py'}), 'moved pkg/a.py to new/b.py')
        for bad in ('/etc/passwd', '/root', '../x.py', '/workspace/../x.py', '.hidden.py', 'C:/x.py'):
            for tool in ('read_file', 'list_dir', 'delete_file'):
                self.assertTrue(b.call(tool, {'path': bad}).startswith('error:'), (tool, bad))
        out = b.call('read_file', {'path': '/etc/passwd'}); self.assertIn('no leading slash', out)
        self.assertIn('allowed file types', b.call('write_file', {'path': 'x.exe', 'content': 'x'})); self.assertIn('use list_dir', b.call('read_file', {'path': 'nope.py'}))

    def test_a_failed_call_keeps_its_error_text_in_the_journal(self):
        b = self.box(); b.call('read_file', {'path': 'nope.py'}); b.call('list_dir', {})
        self.assertIn('file_not_found', b.journal[0]['error']); self.assertNotIn('error', b.journal[1])

    def test_mistakes_come_back_as_text_never_as_exceptions(self):
        b = self.box()
        for name, args, part in (('read_file', {}, 'path is required'), ('read_file', {'path': 'nope.py'}, 'file_not_found'), ('write_file', {'path': '../x.py', 'content': 'x'}, 'error:'),
                                 ('write_file', {'path': 'a.exe', 'content': 'x'}, 'unsupported_workspace_file_type'), ('write_file', {'path': 'a.py'}, 'content is required'),
                                 ('write_file', {'path': 'big.py', 'content': 'x' * 5000}, 'file_too_large'), ('move_file', {'source': 'a.py'}, 'destination is required'),
                                 ('git_commit', {}, 'message is required'), ('git_commit', {'message': 'x'}, 'nothing_to_commit'), ('delete_file', {'path': 'ghost.py'}, 'path_not_found'),
                                 ('search_text', {'text': ''}, 'text is required'), ('read_file', 'not a dict', 'arguments must be a JSON object')):
            out = b.call(name, args); self.assertTrue(out.startswith('error:'), (name, out)); self.assertIn(part, out, (name, out))
        self.assertEqual(b.ws.tree(), [])
    def test_submit_review_validates_the_verdict(self):
        r = self.box('reviewer')
        self.assertTrue(r.call('submit_review', {'verdict': 'MAYBE'}).startswith('error')); self.assertIsNone(r.final)
        r.call('submit_review', {'verdict': 'FAIL', 'cause': 'x' * 900}); self.assertEqual((r.final['verdict'], len(r.final['cause'])), ('FAIL', 500))


class PathSpellingTests(Case):
    def test_write_file_cleans_the_path_like_every_other_tool(self):
        b = self.box('solo')
        for spelled, real in (('./a.py', 'a.py'), ('/workspace/b.py', 'b.py'), ('workspace/c.py', 'c.py')):
            self.assertEqual(b.call('write_file', {'path': spelled, 'content': 'x = 1\n'}), f'created {real} (6 bytes)')
        self.assertEqual(self.ws.tree(), ['a.py', 'b.py', 'c.py'])
        self.assertTrue(b.call('write_file', {'path': './a.py', 'content': 'x = 2\n'}).startswith('overwrote a.py'))
        b.call('write_file', {'path': 'long.py', 'content': 'x = 1\n' * 20})
        self.assertIn('write_file refused: long.py already exists', b.call('write_file', {'path': '/workspace/long.py', 'content': 'y\n'}))


class ReadTests(Case):
    def test_a_long_file_is_read_to_the_end_in_parts_even_beyond_the_old_character_cut(self):
        b = self.box('solo')
        self.ws.policy['max_file_bytes'] = 200_000; self.ws.policy['max_input_bytes'] = 400_000
        self.ws.write('big.txt', ''.join(f'line {i:05d} ' + 'x' * 40 + '\n' for i in range(1, 1201)))      # about 62,000 characters
        last = b.call('read_file', {'path': 'big.txt', 'start': 1151, 'end': 1200})
        self.assertTrue(last.startswith('[lines 1151-1200 of 1200.]')); self.assertIn('line 01200', last)
        self.assertIn('Next: read_file with start=151.', b.call('read_file', {'path': 'big.txt'}))

    def test_end_before_start_is_an_error_and_very_long_lines_are_cut_with_a_note(self):
        b = self.box('solo')
        self.ws.write('a.txt', ''.join(f'l{i}\n' for i in range(1, 300)))
        self.assertEqual(b.call('read_file', {'path': 'a.txt', 'start': 100, 'end': 50}), 'error: end (50) is before start (100)')
        self.ws.policy['max_file_bytes'] = 200_000; self.ws.policy['max_input_bytes'] = 400_000
        self.ws.write('wide.txt', ''.join('y' * 2000 + '\n' for _ in range(90)))
        out = b.call('read_file', {'path': 'wide.txt', 'start': 1, 'end': 90})
        self.assertTrue(out.endswith('read a smaller part with start and end]')); self.assertLess(len(out), 40_200)


class OutlineTests(Case):
    def test_the_outline_names_every_kind_of_parameter(self):
        self.ws.write('f.py', 'def a(x, /, y, *rest, k=1, **kw): pass\ndef b(p, *, q): pass\nclass C:\n    def m(self, z): pass\n')
        out = self.box('solo').call('outline', {'path': 'f.py'})
        self.assertIn('def a(x, /, y, *rest, k, **kw)', out); self.assertIn('def b(p, *, q)', out); self.assertIn('  def m(self, z)', out)


class LimitTests(Case):
    def test_forty_calls_then_only_the_hand_in_works(self):
        b = self.box(max_calls=3)
        for i in range(3): self.assertEqual(b.call('search_text', {'text': f'word{i}'}), '(no match)')
        out = b.call('list_dir', {}); self.assertIn('run limit reached (3 tool calls)', out); self.assertEqual(b.limit_hit, '3 tool calls')
        self.assertTrue(b.call('write_file', {'path': 'a.py', 'content': 'x'}).startswith('error: run limit')); self.assertEqual(b.ws.tree(), [])
        self.assertEqual(b.call('submit_result', {'summary': 'what I have'}), 'received'); self.assertEqual(b.final, {'summary': 'what I have'})
        self.assertEqual(DevToolBox(self.ws, 'coder').max_calls, 40); self.assertEqual(DevToolBox(self.ws, 'coder').max_seconds, 600)
    def test_ten_minutes_then_only_the_hand_in_works(self):
        now = [0.0]; b = self.box(clock=lambda: now[0])
        self.assertEqual(b.call('list_dir', {}), '(empty)'); now[0] = 601
        self.assertIn('run limit reached (10 minutes)', b.call('list_dir', {})); self.assertEqual(b.call('submit_result', {'summary': 's'}), 'received')
    def test_the_journal_records_every_call_without_file_contents(self):
        b = self.box(); b.call('write_file', {'path': 'a.py', 'content': 'secret-looking text'}); b.call('read_file', {'path': 'zzz.py'})
        self.assertEqual([(j['n'], j['tool'], j['ok']) for j in b.journal], [(1, 'write_file', True), (2, 'read_file', False)])
        self.assertIn('<19 chars>', b.journal[0]['detail']); self.assertNotIn('secret-looking', b.journal[0]['detail'])
        self.assertEqual(b.calls, ['write_file', 'read_file'])


class GuardAndPlannerTests(Case):
    def test_the_same_read_again_and_again_is_warned_then_blocked_and_counted(self):
        b = self.box(); self.ws.write('a.py', 'x = 1\n')
        first, second = b.call('read_file', {'path': 'a.py'}), b.call('read_file', {'path': 'a.py'})
        self.assertEqual((first, second), ('x = 1\n', 'x = 1\n'))
        third = b.call('read_file', {'path': 'a.py'})
        self.assertTrue(third.startswith('x = 1') and 'warning' in third)                                   # one repeat before the block: a warning, the call still works
        fourth = b.call('read_file', {'path': 'a.py'})
        self.assertTrue(fourth.startswith('error: you already made exactly this call')); self.assertEqual(b.stuck_blocks, 1)
        b.call('read_file', {'path': 'a.py'}); self.assertEqual(b.stuck_blocks, 2)
    def test_real_progress_never_trips_the_guard(self):
        b = self.box()
        for i in range(6):
            b.call('write_file', {'path': 'a.py', 'content': f'x = {i}\n'})
            self.assertEqual(b.call('read_file', {'path': 'a.py'}), f'x = {i}\n')                       # same call, but the file changed: a different result each time
        self.assertEqual(b.stuck_blocks, 0)
        for i in range(8): self.assertNotIn('error', b.call('git_status', {}) if i == 0 else 'ok')       # writes and commits are not guarded tools at all
        for i in range(5): b.call('git_commit', {'message': 'again'})
        self.assertEqual(b.stuck_blocks, 0)
    def test_the_planner_reads_and_hands_in_a_checked_plan(self):
        p = self.box('planner')
        self.assertNotIn('write_file', p.names); self.assertEqual(p.terminal, 'submit_plan'); self.assertTrue(p.system)
        for bad in ({}, {'steps': []}, {'steps': 'x'}, {'steps': [{'title': 'a'}]}, {'steps': [{'title': '', 'instruction': 'x'}]}, {'steps': [{'title': 't', 'instruction': 'i'}] * 5}, {'steps': ['text']}):
            self.assertTrue(p.call('submit_plan', bad).startswith('error:'), bad)
        self.assertIsNone(p.final)
        self.assertEqual(p.call('submit_plan', {'steps': [{'title': ' T ', 'instruction': 'do it', 'acceptance': 'works', 'check': 'assert 1 == 1'}, {'title': 'U', 'instruction': 'more'}]}), 'received')
        self.assertEqual(p.final, {'steps': [{'title': 'T', 'instruction': 'do it', 'acceptance': 'works', 'check': 'assert 1 == 1'}, {'title': 'U', 'instruction': 'more', 'acceptance': '', 'check': ''}]})
        p2 = self.box('planner'); p2.call('submit_plan', {'steps': [{'title': 't', 'instruction': 'i', 'check': 'x' * 5000}]}); self.assertEqual(len(p2.final['steps'][0]['check']), 5000)      # never cut silently
        self.assertTrue(self.box('planner').call('submit_plan', {'steps': [{'title': 't', 'instruction': 'i', 'check': 'x' * 9000}]}).startswith('error:'))
    def test_tools_can_be_taken_away_per_run(self):
        c = self.box('coder', exclude=('git_commit',)); self.assertNotIn('git_commit', c.names); self.assertIn('write_file', c.names)
        self.assertTrue(c.call('git_commit', {'message': 'x'}).startswith('error: unknown tool git_commit'))


class VmTests(Case):
    def test_vm_tools_use_the_runner_report_every_state_and_are_limited(self):
        plans = []
        answers = iter([{'status': 'completed', 'output': 'Ran 2 tests\nOK'}, {'status': 'failed', 'output': 'FAILED (failures=1)'}, {'status': 'completed', 'output': 'x'}])
        def runner(commands): plans.append(commands); return next(answers)
        b = self.box('tester', vm_runner=runner)
        self.assertEqual(b.call('run_tests', {}), 'VM run completed:\nRan 2 tests\nOK')
        self.assertTrue(b.call('run_python', {'path': 'main.py'}).startswith('VM run failed:'))
        self.assertEqual(plans, [[['python3', '-m', 'unittest', 'discover', '-v']], [['python3', 'main.py']]])
        self.assertEqual(b.call('run_tests', {}), 'error: at most 2 VM runs per agent run')
        for path in ('../x.py', '.hidden.py', 'a.exe'): self.assertTrue(self.box('tester', vm_runner=runner).call('run_python', {'path': path}).startswith('error:'), path)
    def test_a_gate_or_a_block_means_not_started_and_the_model_is_told(self):
        c = self.box('coder', vm_runner=lambda c: {'status': 'captain_required', 'gate': {'gate_id': 'HG-1234'}})
        out = c.call('run_tests', {}); self.assertTrue(out.startswith('NOT STARTED')); self.assertIn('HG-1234', out)
        self.assertTrue(self.box('coder', vm_runner=lambda c: {'status': 'blocked'}).call('run_tests', {}).startswith('NOT STARTED: the VM run is blocked'))
    def test_broker_runner_previews_asks_the_broker_and_never_starts_anything_itself(self):
        self.ws.write('a.py', 'x = 1\n')
        class Broker:
            def __init__(s): s.seen = []; s.answer = {'status': 'captain_required', 'gate': {'gate_id': 'HG-9'}}
            def preview(s, **kw): s.seen.append(('preview', kw)); return {'request': kw, 'plan_digest': 'd'}
            def execute(s, mission, op, args, token=None): s.seen.append(('execute', mission, op, token)); return s.answer
        broker = Broker(); run = broker_runner(self.ws, broker, 'M-TOOLS001')
        self.assertEqual(run([['python3', 'a.py']]), {'status': 'captain_required', 'gate': {'gate_id': 'HG-9'}})
        self.assertEqual(broker.seen[0][1]['source'], 'devvm/M-TOOLS001/repo/work'); self.assertEqual(broker.seen[1], ('execute', 'M-TOOLS001', 'run', None))
        broker.answer = {'status': 'completed', 'sandbox': {'commands': [{'output': 'one'}, {'output': 'two'}]}}
        self.assertEqual(run([['python3', 'a.py']]), {'status': 'completed', 'output': 'one\ntwo'})
        broker.answer = {'status': 'failed', 'sandbox': {'commands': [{'output': 'boom'}]}}
        self.assertEqual(run([['python3', 'a.py']])['output'], 'boom')


class LoopTests(Case):
    def test_the_standard_loop_drives_a_box_end_to_end(self):
        def call(i, name, args): return {'id': f'c{i}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}
        script = iter([[call(1, 'write_file', {'path': 'pkg/m.py', 'content': 'x = 1\n'}), call(2, 'git_commit', {'message': 'add m'})], [call(3, 'submit_result', {'summary': 'done'})]])
        def post(body): return {'choices': [{'message': {'content': '', 'tool_calls': next(script)}, 'finish_reason': 'tool_calls'}]}
        box = self.box()
        out = run_tool_loop(post, 'm', [{'role': 'system', 'content': box.system}, {'role': 'user', 'content': 'go'}], box, {}, max_turns=6)
        self.assertEqual(out['final'], {'summary': 'done'}); self.assertEqual(out['tool_calls'], ['write_file', 'git_commit', 'submit_result'])
        self.assertEqual(self.ws.tree(), ['pkg/m.py']); self.assertEqual(self.ws.log()[0]['message'], 'add m')


if __name__ == '__main__':
    unittest.main()


class LongFileTests(unittest.TestCase):
    def test_a_long_file_is_read_in_parts_and_has_an_outline(self):
        from guppi_runtime.devvm_tools import READ_LINES, outline, read_part
        text = ''.join(f'x{i} = {i}\n' for i in range(400))
        first = read_part(text)
        self.assertTrue(first.startswith(f'[lines 1-{READ_LINES} of 400. Next: read_file with start={READ_LINES + 1}.]'))
        self.assertEqual(len(first.splitlines()), READ_LINES + 1)
        self.assertIn('x299 = 299', read_part(text, 290, 300)); self.assertNotIn('x288', read_part(text, 290, 300))
        self.assertIn('lines 391-400 of 400.]', read_part(text, 391, 9999))
        self.assertEqual(read_part('a = 1\n'), 'a = 1\n')
        code = 'class A:\n    def go(self, x):\n        return x\n\ndef run(a, b):\n    pass\n'
        rows = outline(code)
        self.assertIn('class A', rows); self.assertIn('def go(self, x)', rows); self.assertIn('def run(a, b)  [to line 6]', rows); self.assertTrue(rows.startswith('6 lines'))
        with self.assertRaises(Exception): outline('def broken(:\n')

    def test_the_solo_developer_has_read_in_parts_and_outline(self):
        from guppi_runtime.devvm_tools import ROLE_TOOLS, SCHEMAS
        self.assertIn('outline', ROLE_TOOLS['solo']); self.assertIn('start', SCHEMAS['read_file']['function']['parameters']['properties'])


class FakeProc:
    def __init__(self, out='', code=None): self.out, self.code, self.killed = out, code, False
    def read(self): out, self.out = self.out, ''; return out
    def poll(self): return self.code
    def terminate(self): self.code = 0 if self.code is None else self.code
    def kill(self): self.killed = True
    def wait(self, timeout=None): return self.code


class JobToolTests(Case):
    def jobs(self, proc):
        from guppi_runtime.coder_ext.bg_jobs import Jobs
        self.spawned = []
        def spawn(argv): self.spawned.append(argv); return proc
        return Jobs(spawn, lambda: 0.0)

    def test_job_tools_exist_only_when_the_caller_passes_jobs(self):
        self.assertNotIn('shell_start', self.box('solo').names)
        b = self.box('solo', jobs=self.jobs(FakeProc()))
        for n in ('shell_start', 'shell_log', 'shell_stop'): self.assertIn(n, b.names)
        self.assertEqual(len(b.schemas()), len(b.names))

    def test_start_log_wake_and_stop(self):
        proc = FakeProc(out='listening on 8000\n')
        b = self.box('solo', jobs=self.jobs(proc))
        out = b.call('shell_start', {'command': 'python -m http.server 8000', 'wake_match': 'listening'})
        self.assertTrue(out.startswith('started J1')); self.assertIn('(job J1 woke you: match: listening on 8000)', out + b.call('list_dir', {}))
        self.assertEqual(self.spawned, [['python', '-m', 'http.server', '8000']])
        self.assertEqual(b.call('shell_log', {'job': 'J1'}), 'listening on 8000')
        self.assertEqual(b.call('shell_stop', {'job': 'J1'}), 'stopped J1 (exit code 0)')
        self.assertTrue(b.call('shell_log', {'job': 'J9'}).startswith('error: shell_log refused'))

    def test_exit_wakes_once_and_bad_arguments_are_error_texts(self):
        b = self.box('solo', jobs=self.jobs(FakeProc(code=3)))
        self.assertIn('(job J1 woke you: exit: 3)', b.call('shell_start', {'command': 'false'}))
        self.assertNotIn('woke you', b.call('list_dir', {}))
        self.assertTrue(b.call('shell_start', {'command': 'x', 'wake_match': '('}).startswith('error: shell_start refused'))
        self.assertTrue(b.call('shell_start', {}).startswith('error: command is required'))

    def test_wake_silence_is_refused_and_a_running_job_says_how_to_wait(self):
        proc = FakeProc(out='', code=None)
        b = self.box('solo', jobs=self.jobs(proc))
        refused = b.call('shell_start', {'command': 'sleep 1', 'wake_silence': 5})
        self.assertTrue(refused.startswith('error: shell_start refused: wake_silence is not available'), refused); self.assertEqual(self.spawned, [])
        self.assertTrue(b.call('shell_start', {'command': 'sleep 1'}).startswith('started J1'))
        out = b.call('shell_log', {'job': 'J1'})
        self.assertIn('is still running; its output arrives when it ends', out); self.assertIn('shell_log with wait', out)
        self.assertTrue(b.call('shell_log', {'job': 'J1', 'wait': -1}).startswith('error: wait must be'))
        self.assertTrue(b.call('shell_log', {'job': 'J1', 'wait': 'x'}).startswith('error: wait must be'))
        self.assertTrue(b.call('shell_log', {'job': 'J9', 'wait': 1}).startswith('error: shell_log refused'))

    def test_shell_log_with_wait_returns_when_the_job_ends_and_carries_the_wake_notes(self):
        class Slow(FakeProc):
            def __init__(self): super().__init__(out='', code=None); self.polls = 0
            def poll(self):
                self.polls += 1
                if self.polls >= 3: self.code = 0; self.out = 'done\n'
                return self.code
        b = self.box('solo', jobs=self.jobs(Slow()))
        b.call('shell_start', {'command': 'sleep 1', 'wake_match': 'done'})
        out = b.call('shell_log', {'job': 'J1', 'wait': 5})
        self.assertIn('done', out.splitlines()[0]); self.assertIn('(job J1 woke you: match: done)', out); self.assertIn('(job J1 woke you: exit: 0)', out)
        self.assertNotIn('woke you', b.call('list_dir', {}))            # the notes were given once, with the call that waited

    def test_a_line_with_shell_syntax_runs_with_sh_c_and_a_plain_command_is_split(self):
        from guppi_runtime.devvm_tools import command_argv
        self.assertEqual(command_argv('python3 -m unittest -v'), ['python3', '-m', 'unittest', '-v'])
        self.assertEqual(command_argv("python3 -c 'x y'"), ['python3', '-c', 'x y'])
        for line in ('cat a.txt | wc -l', 'echo a > t.txt', 'make && make test', 'a; b', 'echo $HOME', 'ls *.py', 'echo `date`', 'a' + chr(10) + 'b'):
            self.assertEqual(command_argv(line), ['sh', '-c', line], line)
        b = self.box('solo', jobs=self.jobs(FakeProc()), protected=['/guppi/runtime'], shell_cwd='/guppi/runtime')
        self.assertTrue(b.call('shell_start', {'command': 'echo go | cat'}).startswith('started J1'))
        self.assertEqual(self.spawned, [['sh', '-c', 'echo go | cat']])

    def test_self_repo_guard_refuses_git_that_rewrites_a_protected_folder(self):
        b = self.box('solo', jobs=self.jobs(FakeProc()), protected=['/guppi/runtime'], shell_cwd='/guppi/runtime')
        out = b.call('shell_start', {'command': 'git reset --hard'})
        self.assertTrue(out.startswith('error: shell_start refused: reset_hard'), out); self.assertEqual(self.spawned, [])
        self.assertTrue(b.call('shell_start', {'command': 'git status'}).startswith('started'))
        self.assertTrue(b.call('shell_start', {'command': "git 'unclosed"}).startswith('error: shell_start refused: unparsable'))
