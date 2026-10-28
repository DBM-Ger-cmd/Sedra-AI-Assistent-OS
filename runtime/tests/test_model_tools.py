import json, tempfile, unittest
from pathlib import Path
from guppi_runtime.devenv.model_tools import ToolBox, parse_calls, run_tool_loop

def tc(name, args, cid='c1'):
 return {'id': cid, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}

def answer(message, finish='tool_calls'):
 return {'choices': [{'message': message, 'finish_reason': finish}]}

class ModelToolsTests(unittest.TestCase):
 def setUp(self):
  self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
  self.root = Path(self.tmp.name); (self.root / 'mod.py').write_text('def f():\n  return 1\n', encoding='utf-8')
 def test_tools_are_bound_to_the_folder_and_never_run_code(self):
  box = ToolBox(self.root, ('read_file', 'check_syntax', 'write_file'))
  self.assertIn('return 1', box.call('read_file', {'path': 'mod.py'}))
  for bad in ('../x.py', '..\\x.py', 'C:/Windows/win.ini', ''):
   self.assertTrue(box.call('read_file', {'path': bad}).startswith('error'), bad)
  self.assertEqual(box.call('write_file', {'path': 'a.txt', 'content': 'x'}), 'error: only_py_files_up_to_20kb')
  box.call('write_file', {'path': 'new.py', 'content': 'def f(:\n'})
  self.assertTrue(box.call('check_syntax', {'path': 'new.py'}).startswith('SyntaxError'))
  self.assertEqual(box.call('check_syntax', {'path': 'mod.py'}), 'ok: the file parses')
  self.assertTrue(box.call('shell', {'cmd': 'dir'}).startswith('error: unknown tool'))
  self.assertTrue(box.call('submit_review', {'verdict': 'PASS'}).startswith('error'))   # not a tool of this box
 def test_terminal_tools_validate(self):
  box = ToolBox(self.root, terminal='submit_review')
  self.assertTrue(box.call('submit_review', {'verdict': 'MAYBE'}).startswith('error')); self.assertIsNone(box.final)
  box.call('submit_review', {'verdict': 'FAIL', 'cause': 'x' * 900}); self.assertEqual(box.final['verdict'], 'FAIL'); self.assertEqual(len(box.final['cause']), 500)
 def test_parse_calls_server_format_and_text_format(self):
  self.assertEqual(parse_calls({'tool_calls': [tc('read_file', {'path': 'a'})]}), [('c1', 'read_file', {'path': 'a'})])
  self.assertEqual(parse_calls({'tool_calls': [{'function': {'name': 'x', 'arguments': '{kaputt'}}]})[0][2], None)
  text = 'ich schaue\n<tool_call>\n{"name": "read_file", "arguments": {"path": "mod.py"}}\n</tool_call>'
  self.assertEqual(parse_calls({'content': text}), [('text_0', 'read_file', {'path': 'mod.py'})])
  self.assertEqual(parse_calls({'content': 'nur Text'}), [])
 def test_loop_runs_tools_until_the_terminal_call(self):
  box = ToolBox(self.root, terminal='submit_fix'); sent = []
  script = iter([answer({'content': '', 'tool_calls': [tc('read_file', {'path': 'mod.py'})]}),
                 answer({'content': '', 'tool_calls': [tc('submit_fix', {'code': 'def f():\n  return 2\n'}, 'c2')]})])
  def post(body): sent.append(dict(body, messages=list(body['messages']))); return next(script)
  out = run_tool_loop(post, 'm', [{'role': 'user', 'content': 'fix'}], box, {'temperature': 0.1})
  self.assertEqual(out['final']['code'], 'def f():\n  return 2\n'); self.assertEqual(out['turns'], 2); self.assertEqual(out['tool_calls'], ['read_file', 'submit_fix'])
  self.assertEqual([m['role'] for m in sent[1]['messages']], ['user', 'assistant', 'tool'])      # the tool result went back to the model
  self.assertIn('return 1', sent[1]['messages'][2]['content']); self.assertEqual(len(sent[0]['tools']), 3)
 def test_loop_stops_without_tool_call_on_length_and_on_error(self):
  box = ToolBox(self.root)
  out = run_tool_loop(lambda b: answer({'content': 'Antwort ohne Tool'}, 'stop'), 'm', [], box, {})
  self.assertEqual((out['final'], out['content'], out['turns']), (None, 'Antwort ohne Tool', 1))
  out = run_tool_loop(lambda b: answer({'content': 'abgeschnitt', 'tool_calls': [tc('read_file', {'path': 'mod.py'})]}, 'length'), 'm', [], ToolBox(self.root), {}, cut_retries=0)
  self.assertEqual((out['finish'], out['turns']), ('length', 1))
  def boom(b): raise OSError('server weg')
  out = run_tool_loop(boom, 'm', [], ToolBox(self.root), {})
  self.assertEqual(out['finish'], 'error'); self.assertIn('server weg', out['error'])
 def test_loop_nudges_the_model_to_the_terminal_call_before_the_limit(self):
  sent = []
  def post(body):
   sent.append(len(body['messages']) and body['messages'][-1]['content'])
   return answer({'content': '', 'tool_calls': [tc('read_file', {'path': 'mod.py'})]})
  run_tool_loop(post, 'm', [{'role': 'user', 'content': 'x'}], ToolBox(self.root, terminal='submit_review'), {}, max_turns=4)
  self.assertEqual(sum('Call submit_review now' in str(s) for s in sent), 1)      # once, at turn max-2
 def test_the_loop_forwards_the_extra_sampling_settings_and_ignores_the_rest(self):
  seen = []
  def post(body):
   seen.append(body); return answer({'content': 'done'}, 'stop')
  run_tool_loop(post, 'm', [{'role': 'user', 'content': 'go'}], ToolBox(self.root, terminal='submit_review'), {'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'presence_penalty': True, 'seed': 5, 'evil': 'x'}, max_turns=2)
  self.assertEqual((seen[0]['temperature'], seen[0]['top_p'], seen[0]['top_k']), (0.7, 0.8, 20))
  for key in ('presence_penalty', 'seed', 'evil'):
   self.assertNotIn(key, seen[0])
 def test_an_answer_that_hits_the_limit_gets_a_note_and_a_new_try_instead_of_ending_the_run(self):
  box = ToolBox(self.root, terminal='submit_review')
  replies = [answer({'content': 'x', 'tool_calls': [tc('write_file', {'path': 'a.py', 'content': 'x'})]}, 'length'), answer({'content': 'y'}, 'length'), answer({'content': 'done'}, 'stop')]
  seen = []
  def post(body):
   seen.append(body['messages'][-1]); return replies[len(seen) - 1]
  out = run_tool_loop(post, 'm', [{'role': 'user', 'content': 'go'}], box, {}, max_turns=6)
  self.assertEqual((out['cuts'], out['finish'], out['turns']), (2, 'stop', 3))
  self.assertEqual([m['role'] for m in seen[1:]], ['user', 'user'])
  self.assertIn('SMALLER steps', seen[1]['content'])
  self.assertEqual(sum(1 for m in seen[2:] if m['content'].startswith('Your last answer was cut off')), 1)
 def test_a_third_cut_ends_the_run_as_before(self):
  box = ToolBox(self.root, terminal='submit_review')
  out = run_tool_loop(lambda body: answer({'content': 'x'}, 'length'), 'm', [{'role': 'user', 'content': 'go'}], box, {}, max_turns=8)
  self.assertEqual((out['cuts'], out['finish']), (2, 'length'))
 def test_at_the_limit_without_text_the_answer_comes_without_tools(self):
  # 28.10.2026: gemma rief achtmal dasselbe Werkzeug und schrieb nie Text – die letzte Antwort kommt jetzt ohne Werkzeuge
  seen = []
  def post(body):
   seen.append(body)
   if body['tools']: return answer({'content': '', 'tool_calls': [tc('read_file', {'path': 'mod.py'})]})
   return answer({'content': 'Antwort ohne Werkzeug'}, 'stop')
  box = ToolBox(self.root)
  out = run_tool_loop(post, 'm', [{'role': 'user', 'content': 'frage'}], box, {}, max_turns=3)
  self.assertEqual(out['content'], 'Antwort ohne Werkzeug')
  self.assertEqual(seen[-1]['tools'], [])
  self.assertEqual(out['turns'], 3)
 def test_loop_has_a_turn_limit(self):
  box = ToolBox(self.root)
  out = run_tool_loop(lambda b: answer({'content': '', 'tool_calls': [tc('read_file', {'path': 'mod.py'})]}), 'm', [], box, {}, max_turns=3)
  self.assertEqual((out['turns'], len(out['tool_calls']), out['final']), (3, 3, None))

if __name__ == '__main__':
 unittest.main()


class CompactDuringRunTests(unittest.TestCase):
    def test_old_tool_results_are_shortened_once_the_prompt_grows_past_the_limit(self):
        import json as _json
        from guppi_runtime.devenv.model_tools import run_tool_loop

        class Box:
            final, calls, terminal = None, 0, 'submit_result'
            def schemas(self): return []
            def call(self, name, args):
                self.calls += 1
                return 'x' * 5000

        seen = []
        replies = iter([{'choices': [{'message': {'content': '', 'tool_calls': [{'id': f'c{i}', 'type': 'function', 'function': {'name': 'read_file', 'arguments': _json.dumps({'path': 'a'})}}]}, 'finish_reason': 'tool_calls'}], 'usage': {'prompt_tokens': 30000}} for i in range(12)] + [{'choices': [{'message': {'content': 'done'}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 100}}])
        def post(body):
            seen.append(sum(len(m.get('content') or '') for m in body['messages']))
            return next(replies)
        out = run_tool_loop(post, 'm', [{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 'task'}], Box(), {}, max_turns=14, compact_at=20000)
        self.assertLess(max(seen[8:]), 8 * 5000 + 10 * 600)
        self.assertLess(seen[-1], seen[7] + 5000)


class StubWritesTests(unittest.TestCase):
    def test_old_written_code_becomes_a_note_but_the_path_stays_and_new_messages_are_untouched(self):
        import json as _json
        from guppi_runtime.devenv.model_tools import stub_writes
        def call(i, name, **a): return {'role': 'assistant', 'content': '', 'tool_calls': [{'id': f'c{i}', 'type': 'function', 'function': {'name': name, 'arguments': _json.dumps(a)}}]}
        old = call(1, 'write_file', path='a.py', content='x = 1\n' * 300)
        edit = call(2, 'edit_file', path='a.py', old='y' * 400, new='z' * 5)
        read = call(3, 'read_file', path='a.py')
        recent = call(4, 'write_file', path='b.py', content='q' * 900)
        msgs = [{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 'task'}, old, edit, read] + [{'role': 'tool', 'tool_call_id': 'c', 'content': 'ok'} for _ in range(4)] + [recent, {'role': 'tool', 'tool_call_id': 'c4', 'content': 'ok'}]
        out = stub_writes(msgs, keep_last=3)
        args = _json.loads(out[2]['tool_calls'][0]['function']['arguments'])
        self.assertEqual(args['path'], 'a.py'); self.assertNotIn('content', args); self.assertIn('content: 1800 characters', args['omitted']); self.assertLess(len(_json.dumps(out[2])), 300)
        args = _json.loads(out[3]['tool_calls'][0]['function']['arguments']); self.assertNotIn('old', args); self.assertIn('old: 400 characters', args['omitted']); self.assertEqual(args['new'], 'zzzzz')
        self.assertIs(out[4], read); self.assertIs(out[-2], recent); self.assertEqual(stub_writes(out, keep_last=3), out)


class CompactResetsGuardTests(unittest.TestCase):
    def test_after_the_old_results_are_shortened_the_loop_guard_forgets_the_reads(self):
        import json as _json
        from guppi_runtime.devenv.model_tools import run_tool_loop

        class Guard:
            resets = 0
            def reset(self): Guard.resets += 1

        class Box:
            final, calls, terminal, guard = None, 0, 'submit_result', Guard()
            def schemas(self): return []
            def call(self, name, args): return 'x' * 100

        replies = iter([{'choices': [{'message': {'content': '', 'tool_calls': [{'id': f'c{i}', 'type': 'function', 'function': {'name': 'read_file', 'arguments': _json.dumps({'path': 'a'})}}]}, 'finish_reason': 'tool_calls'}], 'usage': {'prompt_tokens': 30000 if i > 1 else 100}} for i in range(5)] + [{'choices': [{'message': {'content': 'done'}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 100}}])
        run_tool_loop(lambda body: next(replies), 'm', [{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 't'}], Box(), {}, max_turns=8, compact_at=20000)
        self.assertGreaterEqual(Guard.resets, 1)


class RelaxSchemaTests(unittest.TestCase):
    def test_empty_property_maps_and_huge_limits_are_left_out_of_the_wire_copy_only(self):
        from guppi_runtime.devenv.model_tools import relax_schema
        original = {"type": "function", "function": {"name": "git_status", "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}}}
        wire = relax_schema(original)
        self.assertEqual(wire["function"]["parameters"], {"type": "object"})
        self.assertEqual(original["function"]["parameters"]["properties"], {})                            # the original is untouched
        schema = {"type": "object", "properties": {"s": {"type": "string", "maxLength": 5000, "minLength": 1}, "l": {"type": "array", "maxItems": 1998, "items": {"type": "string"}}}, "required": ["s"]}
        self.assertEqual(relax_schema(schema)["properties"]["s"], {"type": "string", "minLength": 1})
        self.assertEqual(relax_schema(schema)["properties"]["l"]["maxItems"], 1998)
        self.assertEqual(relax_schema(schema)["required"], ["s"])

    def test_the_tool_loop_sends_the_relaxed_schemas(self):
        from guppi_runtime.devenv.model_tools import run_tool_loop

        class Box:
            final, calls, terminal, guard = None, 0, "submit_result", None
            def schemas(self): return [{"type": "function", "function": {"name": "git_status", "parameters": {"type": "object", "properties": {}, "required": []}}}]
            def call(self, name, args): return "ok"
        seen = []
        def post(body):
            seen.append(body["tools"]); return {"choices": [{"message": {"content": "done"}, "finish_reason": "stop"}], "usage": {}}
        run_tool_loop(post, "m", [{"role": "user", "content": "t"}], Box(), {})
        self.assertEqual(seen[0][0]["function"]["parameters"], {"type": "object"})
