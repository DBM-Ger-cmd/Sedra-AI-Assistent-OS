import json, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge
from test_team_tasks import GOOD, BAD

def run_on_host_with_trusted_fixtures(candidates):
    """Only for fixtures written in this test file: the real judge never runs model code on this host. /workspace is replaced by a temp folder."""
    folder = judge.prepare(candidates)
    one = (folder / 'judge_one.py'); one.write_text(judge.JUDGE_ONE.replace('/workspace', folder.as_posix()), encoding='utf-8')
    allp = (folder / 'judge_all.py'); allp.write_text(judge.JUDGE_ALL.replace('/workspace', folder.as_posix()), encoding='utf-8')
    out = subprocess.run([sys.executable, str(allp)], capture_output=True, text=True, timeout=120, cwd=folder).stdout
    return json.loads([l for l in out.splitlines() if l.startswith('JUDGE_ALL=')][0][len('JUDGE_ALL='):])

class JudgeTests(unittest.TestCase):
    def test_every_task_has_tests_and_the_tests_match_the_task_set(self):
        from team_tasks import SETS
        self.assertEqual({t['id'] for t in SETS['all']}, set(judge.TESTS))
        for task in SETS['all']:
            self.assertEqual(judge.TESTS[task['id']]['fn'], task['fn'])
            self.assertGreaterEqual(len(judge.TESTS[task['id']]['cases']), 4)
    def test_complete_fixes_pass_every_check_and_the_originals_fail(self):
        res = run_on_host_with_trusted_fixtures({n: (n, c) for n, c in GOOD.items()})
        for name, entry in res.items(): self.assertTrue(judge.all_passed(entry), (name, entry))
        from team_tasks import SETS
        res = run_on_host_with_trusted_fixtures({t['id']: (t['id'], t['code']) for t in SETS['all']})
        for name, entry in res.items(): self.assertFalse(judge.all_passed(entry), name)
    def test_plausible_first_fixes_are_caught_with_a_readable_failure(self):
        res = run_on_host_with_trusted_fixtures({n: (n, c) for n, c in BAD.items()})
        for name, entry in res.items(): self.assertFalse(judge.all_passed(entry), (name, entry))
        self.assertTrue(any('"abc"' in f and "Invalid isoformat string" in f for f in res['isoformat_date']['failures']), res['isoformat_date'])      # the message-sniffing fix leaks the library error for text without "month" in it
        self.assertTrue(any("http://127.0.0.1/" in f for f in res['urlparse_port']['failures']), res['urlparse_port'])
        self.assertIn('expected', res['pair_parse']['failures'][0])
    def test_broken_candidates_are_reported_not_fatal(self):
        res = run_on_host_with_trusted_fixtures({'a': ('flag_words', 'def read_flag(:\n'), 'b': ('flag_words', 'x = 1\n'), 'c': ('flag_words', GOOD['flag_words'])})
        self.assertIn('SyntaxError', res['a']['error']); self.assertIn('KeyError', res['b']['error']); self.assertTrue(judge.all_passed(res['c']))
    def test_feedback_text(self):
        self.assertIn('could not be run', judge.feedback({'error': 'SyntaxError: x', 'passed': 0, 'total': 0, 'failures': []}))
        text = judge.feedback({'error': None, 'passed': 7, 'total': 9, 'failures': ["input ('a',): expected 1, got 2"]})
        self.assertIn('7 of 9', text); self.assertIn("- input ('a',)", text)
        self.assertFalse(judge.all_passed({'error': None, 'passed': 0, 'total': 0, 'failures': []}))
        self.assertEqual(judge.judge('.', {}), {})
    def test_unknown_task_is_refused(self):
        with self.assertRaises(KeyError): judge.prepare({'x': ('nope', 'x = 1')})

if __name__ == '__main__':
    unittest.main()
