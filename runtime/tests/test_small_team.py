import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
import small_team as st
from rework_bench import TASKS

FIXED_REGEX = 'import re\n\n\ndef check_id(s):\n    """Return s if it is 1-12 lower-case letters, else raise ValueError("bad_id")."""\n    if not re.match(r"^[a-z]{1,12}\\Z", s):\n        raise ValueError("bad_id")\n    return s\n'

def tcall(name, args, cid='c1'):
    return {'id': cid, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}

def reply(calls=None, content='', finish='tool_calls'):
    return {'choices': [{'message': {'content': content, 'tool_calls': calls or []}, 'finish_reason': finish}]}

class SmallTeamTests(unittest.TestCase):
    def item(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        task = TASKS[0]; folder = Path(tmp.name)
        (folder / 'mod.py').write_text(task['code'], encoding='utf-8'); (folder / 'failure.txt').write_text(st.failure_text(task, ['Lektion']), encoding='utf-8')
        return {'task': task, 'seed': 0, 'folder': folder, 'rounds': [], 'candidate': None}
    def test_repair_via_tools_is_graded_statically(self):
        it = self.item()
        script = iter([reply([tcall('read_file', {'path': 'mod.py'})]), reply([tcall('submit_fix', {'code': FIXED_REGEX}, 'c2')])])
        out = st.repair(lambda body: next(script), it)
        self.assertTrue(out['fixed'] and out['submitted']); self.assertEqual(out['tool_calls'], ['read_file', 'submit_fix'])
        self.assertEqual((it['folder'] / 'fix.py').read_text(encoding='utf-8'), FIXED_REGEX)
    def test_repair_falls_back_to_a_code_block_when_no_tool_was_called(self):
        out = st.repair(lambda body: reply(content='Hier:\n```python\n' + FIXED_REGEX + '```', finish='stop'), self.item())
        self.assertTrue(out['fixed']); self.assertFalse(out['submitted'])
    def test_review_in_both_modes(self):
        it = self.item(); it['candidate'] = {'code': FIXED_REGEX}
        out = st.review(lambda body: reply([tcall('submit_review', {'verdict': 'FAIL', 'cause': 'x'})]), it, 'tools')
        self.assertEqual((out['verdict'], out['cause']), ('FAIL', 'x'))
        seen = {}
        def post(body): seen.update(body); return reply(content='Kurz.\nVERDICT: PASS', finish='stop')
        out = st.review(post, it, 'inline')
        self.assertEqual(out['verdict'], 'PASS'); self.assertIn('--- candidate.py ---', seen['messages'][0]['content']); self.assertNotIn('tools', seen)
        self.assertIsNone(st.review(lambda body: reply(content='keine Antwort im Format', finish='length'), it, 'inline')['verdict'])
    def test_summary_counts_false_rejections_and_false_passes(self):
        def rnd(fixed, verdict): return {'candidate': {'fixed': fixed, 'seconds': 1.0}, 'review': {'verdict': verdict, 'seconds': 2.0}}
        items = [{'rounds': [rnd(True, 'FAIL'), rnd(True, 'PASS')], 'final_fixed': True}, {'rounds': [rnd(False, 'PASS')], 'final_fixed': False},
                 {'rounds': [rnd(False, None)], 'final_fixed': False}]
        s = st.summarize(items)
        self.assertEqual((s['solo_fixed'], s['team_fixed'], s['false_rejections'], s['false_passes'], s['no_verdict'], s['correct_calls']), ('1/3', '1/3', 1, 1, 1, 1))

    def test_judged_summary_counts_executed_passes_not_static_grades(self):
        ok = {'error': None, 'passed': 9, 'total': 9, 'failures': []}; bad = {'error': None, 'passed': 7, 'total': 9, 'failures': ['x']}
        def rnd(entry, fixed, review=None): return {'candidate': {'fixed': fixed}, 'judge': entry, **({'review': review} if review else {})}
        items = [{'rounds': [rnd(ok, True)], 'final_fixed': True},
                 {'rounds': [rnd(bad, True, {'verdict': None}), rnd(ok, True)], 'final_fixed': True},          # static grade said fine, the test did not
                 {'rounds': [rnd(bad, False, {'verdict': 'FAIL'}), rnd(bad, False)], 'final_fixed': False}]
        s = st.summarize_judged(items)
        self.assertEqual((s['solo_pass'], s['team_pass'], s['repairs'], s['reviewer_calls'], s['reviewer_no_verdict'], s['static_solo_fixed'], s['static_team_fixed']),
                         ('1/3', '2/3', 2, 2, 1, '2/3', '2/3'))

    def test_small_models_get_at_most_one_lesson_the_best_fitting_one(self):
        from types import SimpleNamespace as NS
        from guppi_runtime.knowledge import KnowledgeStore
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        store = KnowledgeStore(Path(tmp.name) / 'r.jsonl')
        store.add_lesson('digits', 'DIGITS lesson', triggers=['regex', 'digits', 'port'])
        store.add_lesson('wrap', 'WRAP lesson', triggers=['raise valueerror('])
        store.add_lesson('url', 'URL lesson', triggers=['urlparse', '.port'])
        task = {'code': 'def f(u):\n    p = urlparse(u).port\n    raise ValueError("x")\n', 'repro': 'port 80'}
        args = lambda **kw: NS(no_lessons=False, all_lessons=False, max_lessons=1, **kw)
        self.assertEqual(st.pick_lessons(store, task, args()), ['URL lesson'])                                 # two triggers occur (`urlparse`, `.port`); the generic `port` lesson is dropped as not specific enough
        self.assertEqual(st.pick_lessons(store, task, NS(no_lessons=False, all_lessons=False, max_lessons=2)), ['URL lesson', 'WRAP lesson'])
        self.assertEqual(st.pick_lessons(store, {'code': 'raise ValueError("x")', 'repro': ''}, args()), ['WRAP lesson'])
        self.assertEqual(st.pick_lessons(store, task, NS(no_lessons=True, all_lessons=False, max_lessons=1)), [])
        self.assertEqual(st.pick_lessons(store, task, NS(no_lessons=False, all_lessons=True, max_lessons=1)), ['DIGITS lesson', 'WRAP lesson', 'URL lesson'])   # the old behaviour, for comparison
        self.assertEqual(st.pick_lessons(store, {'code': 'x = settings["port"]', 'repro': ''}, args()), [])


if __name__ == '__main__':
    unittest.main()
