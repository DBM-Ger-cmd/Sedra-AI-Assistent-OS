import json
import tempfile
import unittest
from pathlib import Path

from guppi_runtime import labor_runs


def write(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in events) + '\n', encoding='utf-8')


class RunsFromLogs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='labor-runs-')
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_running_finished_and_failed_runs_are_told_apart(self):
        start = {'event': 'LAUF_START', 'payload': {'model': 'm/a', 'provider': 'nvidia', 'allow': ['shells/x/a.css']}, 't': '10:00:00'}
        write(self.root / 'redesign' / 'lauf_retro.jsonl', [start,
              {'event': 'SG_MODEL_CALL', 't': '10:00:05', 'payload': {}},
              {'event': 'SANDBOX_WRITE', 't': '10:00:09', 'payload': {'path': 'shells/x/a.css', 'bytes': 10}}])
        write(self.root / 'redesign' / 'lauf_minimal.jsonl', [start,
              {'event': 'SG_MODEL_CALL', 't': '10:01:00', 'payload': {}},
              {'event': 'SG_BLOCKED', 't': '10:01:01', 'payload': {}},
              {'event': 'LAUF_ENDE', 't': '10:02:00', 'payload': {'status': 'error', 'detail': 'cloud_api_error:TimeoutError', 'turns': 1}}])
        write(self.root / 'redesign' / 'spec_lab' / 'lauf_gemma.jsonl', [start,
              {'event': 'LAUF_ENDE', 't': '10:03:00', 'payload': {'status': 'finished', 'turns': 7}}])
        runs = {(r['kind'], r['name']): r for r in labor_runs.list_runs(self.root)}
        self.assertEqual(runs[('Umbau', 'retro')]['status'], 'läuft', 'a run without an end is running')
        self.assertEqual(runs[('Umbau', 'retro')]['writes'], ['shells/x/a.css'])
        self.assertEqual(runs[('Umbau', 'minimal')]['status'], 'error')
        self.assertEqual(runs[('Umbau', 'minimal')]['blocked'], 1)
        self.assertEqual(runs[('Spec', 'gemma')]['status'], 'finished')
        self.assertEqual(runs[('Umbau', 'retro')]['model'], 'm/a')

    def test_missing_folder_gives_no_runs_and_no_error(self):
        self.assertEqual(labor_runs.list_runs(self.root / 'gibt-es-nicht'), [])

    def test_broken_lines_are_skipped(self):
        path = self.root / 'redesign' / 'lauf_kaputt.jsonl'
        path.parent.mkdir(parents=True)
        path.write_text('{nicht json\n{"event": "LAUF_START", "payload": {"model": "m"}}\n', encoding='utf-8')
        self.assertEqual(labor_runs.list_runs(self.root)[0]['model'], 'm')


if __name__ == '__main__':
    unittest.main()
