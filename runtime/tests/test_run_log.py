import json, tempfile, unittest
from pathlib import Path
from guppi_runtime.jobs.run_log import RunLog

class RunLogTests(unittest.TestCase):
 def setUp(self):
  self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.base = Path(self.tmp.name)
 def index(self):
  return [json.loads(l) for l in (self.base / 'logs' / 'INDEX.jsonl').read_text(encoding='utf-8').splitlines()]
 def test_lines_and_results_are_kept_and_the_index_says_done(self):
  said = []
  with RunLog(self.base, 'bench', {'seeds': 2}, echo=said.append) as log:
   log.say('== round 1'); log.save({'a': 1}); log.save({'a': 2})
  text = log.log_path.read_text(encoding='utf-8')
  self.assertIn('== round 1', text); self.assertIn('run ended: done', text); self.assertIn('== round 1', said)
  self.assertEqual(json.loads(log.json_path.read_text(encoding='utf-8')), {'a': 2})
  rows = self.index(); self.assertEqual([r['status'] for r in rows], ['running', 'done']); self.assertEqual(rows[-1]['config'], {'seeds': 2}); self.assertIn('seconds', rows[-1])
 def test_a_crash_keeps_the_last_saved_state_and_is_marked_failed(self):
  with self.assertRaises(RuntimeError):
   with RunLog(self.base, 'bench', echo=None) as log:
    log.save({'items': [1]}); raise RuntimeError('GPU weg')
  self.assertEqual(json.loads(log.json_path.read_text(encoding='utf-8')), {'items': [1]})
  self.assertEqual(self.index()[-1]['status'], 'failed'); self.assertIn('RuntimeError: GPU weg', log.log_path.read_text(encoding='utf-8'))
  self.assertFalse(list((self.base / 'logs').glob('*.tmp')))
 def test_ctrl_c_is_marked_interrupted_and_runs_do_not_overwrite_each_other(self):
  with self.assertRaises(KeyboardInterrupt):
   with RunLog(self.base, 'bench', echo=None): raise KeyboardInterrupt()
  self.assertEqual(self.index()[-1]['status'], 'interrupted')
  import time; time.sleep(1.1)
  with RunLog(self.base, 'bench', echo=None) as second: second.save({})
  self.assertEqual(len(list((self.base / 'logs').glob('bench_*.log'))), 2)

if __name__ == '__main__':
 unittest.main()
