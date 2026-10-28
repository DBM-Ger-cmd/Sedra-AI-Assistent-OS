"""T7 der Harness-Shell: der Vertrag der Dateien (ohne Browser; den Browser prüft benchmarks/uix_check.py --shell harness)."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

from guppi_runtime.desk.gateway import SLOTS, check_shell

ORDNER = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'shells' / 'harness'
UI = ORDNER.parents[1] / 'ui'


class HarnessShellTests(unittest.TestCase):
    def test_manifest_wird_angenommen(self):
        man, fehler = check_shell(yaml.safe_load((ORDNER / 'shell.yaml').read_text(encoding='utf-8')), ORDNER)
        self.assertEqual(fehler, [])
        self.assertEqual(man['provides'], ['seite', 'reiter', 'flaeche', 'eingabe', 'taskleiste'])
        self.assertTrue(all(z in SLOTS for z in man['provides']))
        self.assertEqual(man['js'][-1], 'shell.js', 'shell.js registriert und kommt zuletzt')
        for weg in ('GET /api/harness/*', 'POST /api/harness/*', 'PATCH /api/harness/*', 'DELETE /api/harness/*', 'GET /api/strip'):
            self.assertIn(weg, man['api'])

    def test_alle_dateien_der_spec_sind_da(self):
        for name in ('shell.yaml', 'README.md', 'arbeitsplatz.yaml', 'seite.js', 'reiter.js', 'verlauf.js', 'eingabe.js', 'taskleiste.js',
                     'shell.css', 'preview.png'):
            self.assertTrue((ORDNER / name).is_file(), name)

    def test_farben_nur_aus_token(self):
        css = (ORDNER / 'shell.css').read_text(encoding='utf-8')
        self.assertIsNone(re.search(r'#[0-9a-fA-F]{3,8}\b', css), 'kein Hex-Wert in shell.css')
        self.assertNotRegex(css, r'\brgba?\(', 'Mischungen nur per color-mix aus Tokens')

    def test_kein_rohes_html(self):
        for js in ORDNER.glob('*.js'):
            text = js.read_text(encoding='utf-8')
            self.assertNotIn('innerHTML', text, js.name)
            self.assertNotIn('insertAdjacentHTML', text, js.name)
            self.assertNotIn('http://', text.replace('http://www.w3.org/2000/svg', ''), js.name + ': nichts aus dem Netz')
            self.assertNotIn('https://', text, js.name)

    def test_ereignisse_der_harness_auf_dem_bus(self):
        bus = (UI / 'bus.js').read_text(encoding='utf-8')
        self.assertIn("'harness.sitzung'", bus)
        self.assertIn("'harness.antwort'", bus)

    def test_reiter_merken_nur_ids(self):
        reiter = (ORDNER / 'reiter.js').read_text(encoding='utf-8')
        self.assertIn("'sedra.harness.reiter'", reiter)
        self.assertIn('filter(id=>ID.test(id))', reiter)

    @unittest.skipUnless(shutil.which('node'), 'node fehlt')
    def test_markdown_bloecke(self):
        text = '## Titel\n\nEin **fetter** Satz.\n\n- a\n- b\n\n1. eins\n\n| x | y |\n|---|---|\n| 1 | 2 |\n\n```py\n<script>alert(1)</script>\n```\n'
        code = ('const m = require(' + json.dumps(str(ORDNER / 'markdown.js')) + '); '
                'process.stdout.write(JSON.stringify(m.bloecke(' + json.dumps(text) + ')));')
        out = json.loads(subprocess.run(['node', '-e', code], capture_output=True, text=True, encoding='utf-8', check=True).stdout)
        self.assertEqual([b['art'] for b in out], ['kopf', 'absatz', 'ul', 'ol', 'tabelle', 'code'])
        self.assertEqual(out[4]['reihen'], [['1', '2']])
        self.assertEqual(out[5]['text'], '<script>alert(1)</script>', 'Code bleibt Text')


if __name__ == '__main__':
    unittest.main()
