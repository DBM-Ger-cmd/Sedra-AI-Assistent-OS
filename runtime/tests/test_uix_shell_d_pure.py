"""Die Node-Tests der reinen Teile von Shell D (Spec 4, D4.4, G2-S4-18).

Jede `*.test.js` in der Shell und in den Werkzeugen des Teams läuft mit node; sie meldet `{checks, failed}` als letzte Zeile.
Heute gibt es den Fensterstapel und den Ereignisschub der Shell (`stapel.test.js`); `baum.test.js`, `spalten.test.js`,
`cron.test.js` und `verlauf.test.js` kommen mit ihren Werkzeugen (S4.4 bis S4.8) und werden dann ohne Änderung hier mitgeprüft.
Dazu die `test.spec.js` der Werkzeuge: das Werkzeug in einem leeren Container im Schein-DOM (`tests/uix_spec_dom.js`, mit
`node -r` vorgeladen), Ereignis senden, Text prüfen. Linie L3: höchstens 20 Prüfungen je Datei."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'
FOLDERS = [UIX / 'shells' / 'paperclip'] + [UIX / 'tools' / t for t in ('org', 'board', 'routines', 'slots', 'gauge-slots', 'agentfenster', 'costs', 'wissen')]
SPEC_DOM = Path(__file__).resolve().parent / 'uix_spec_dom.js'
MAX_CHECKS = 20


def node_tests():
    return sorted(f for folder in FOLDERS if folder.is_dir() for f in list(folder.glob('*.test.js')) + list(folder.glob('test.spec.js')))


class NodeTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which('node'):
            self.skipTest('node is not installed')

    def test_every_node_test_of_shell_d_passes_and_stays_small(self):
        files = node_tests()
        self.assertIn('stapel.test.js', [f.name for f in files], 'der Fensterstapel hat seinen Node-Test')
        for f in files:
            with self.subTest(str(f.relative_to(UIX))):
                pre = ['-r', str(SPEC_DOM)] if f.name == 'test.spec.js' else []
                run = subprocess.run(['node', *pre, f.name], cwd=f.parent, capture_output=True, text=True, encoding='utf-8', timeout=60)
                last = (run.stdout.strip().splitlines() or ['{}'])[-1]
                self.assertEqual(run.returncode, 0, run.stdout[-800:] + run.stderr[-400:])
                result = json.loads(last)
                self.assertEqual(result['failed'], 0)
                self.assertGreater(result['checks'], 0)
                self.assertLessEqual(result['checks'], MAX_CHECKS, 'Linie L3: höchstens 20 Prüfungen je Gruppe')


if __name__ == '__main__':
    unittest.main()
