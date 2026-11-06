"""T7 der Harness-Shell: der Vertrag der Dateien (ohne Browser; den Browser prüft benchmarks/uix_check.py --shell harness)."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

from sedra_runtime.desk.gateway import SLOTS, check_shell

ORDNER = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix' / 'shells' / 'harness'
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
        for name in ('harness.aufgabe', 'harness.vorarbeiter', 'harness.lauf', 'harness.karte'):       # Stufe 3 (P-16)
            self.assertIn("'" + name + "'", bus, name)

    def test_reiter_merken_nur_ids(self):
        reiter = (ORDNER / 'reiter.js').read_text(encoding='utf-8')
        self.assertIn("'sedra.harness.reiter'", reiter)
        # A29 (1.11.): gemerkt werden Sitzungs-IDs und die Reiter aufgaben:/einstellungen:/builder: (Desktop Builder, 05.11.) – nie diff:, lauf: oder app: (die kommen aus dem Arbeitsstand)
        self.assertIn("const merkbar = id=>ID.test(id) || /^(aufgaben|einstellungen|builder):/.test(String(id));", reiter)
        self.assertIn('filter(merkbar)', reiter)

    @unittest.skipUnless(shutil.which('node'), 'node fehlt')
    def test_markdown_bloecke(self):
        text = '## Titel\n\nEin **fetter** Satz.\n\n- a\n- b\n\n1. eins\n\n| x | y |\n|---|---|\n| 1 | 2 |\n\n```py\n<script>alert(1)</script>\n```\n'
        code = ('const m = require(' + json.dumps(str(ORDNER / 'markdown.js')) + '); '
                'process.stdout.write(JSON.stringify(m.bloecke(' + json.dumps(text) + ')));')
        out = json.loads(subprocess.run(['node', '-e', code], capture_output=True, text=True, encoding='utf-8', check=True).stdout)
        self.assertEqual([b['art'] for b in out], ['kopf', 'absatz', 'ul', 'ol', 'tabelle', 'code'])
        self.assertEqual(out[4]['reihen'], [['1', '2']])
        self.assertEqual(out[5]['text'], '<script>alert(1)</script>', 'Code bleibt Text')

    def bloecke(self, text):
        code = ('const m = require(' + json.dumps(str(ORDNER / 'markdown.js')) + '); '
                'process.stdout.write(JSON.stringify(m.bloecke(' + json.dumps(text) + ')));')
        return json.loads(subprocess.run(['node', '-e', code], capture_output=True, text=True, encoding='utf-8', check=True).stdout)

    @unittest.skipUnless(shutil.which('node'), 'node fehlt')
    def test_markdown_listen(self):
        # eine nummerierte Liste mit Leerzeilen bleibt eine Liste (vorher zwei Listen, beide ab 1)
        lose = self.bloecke('1. a\n\n2. b\n\n3. c')
        self.assertEqual([(b['art'], [p['text'] for p in b['punkte']]) for b in lose], [('ol', ['a', 'b', 'c'])])
        # die Startnummer bleibt erhalten
        self.assertEqual(self.bloecke('3. drei\n4. vier')[0]['start'], 3)
        # verschachtelt: der Punkt nach der Unterliste gehört wieder zur äußeren Liste
        tief = self.bloecke('- a\n  - b\n    - c\n  - d\n- e')[0]
        self.assertEqual([p['text'] for p in tief['punkte']], ['a', 'e'])
        unter = tief['punkte'][0]['inhalt'][0]
        self.assertEqual([p['text'] for p in unter['punkte']], ['b', 'd'])
        self.assertEqual(unter['punkte'][0]['inhalt'][0]['punkte'][0]['text'], 'c')
        # Code in einem Punkt bleibt Code (mit Zeilenumbrüchen), nicht eine Zeile Text
        mit_code = self.bloecke('1. a\n   ```py\n   x = 1\n   y = 2\n   ```\n2. b')[0]
        self.assertEqual(mit_code['punkte'][0]['inhalt'], [{'art': 'code', 'sprache': 'py', 'text': 'x = 1\ny = 2'}])
        self.assertEqual(mit_code['punkte'][1]['text'], 'b')
        # Fortsetzungszeile und neuer Absatz im Punkt; die Liste endet am Absatz ohne Einzug; ul und ol wechseln die Liste
        fort = self.bloecke('- a\n  weiter\n\n  neu\n- b\n\nEnde\n\n1. x')
        self.assertEqual([b['art'] for b in fort], ['ul', 'absatz', 'ol'])
        self.assertEqual(fort[0]['punkte'][0]['text'], 'a weiter')
        self.assertEqual(fort[0]['punkte'][0]['inhalt'], [{'art': 'absatz', 'text': 'neu'}])

    def teile(self, text):
        code = ('const m = require(' + json.dumps(str(ORDNER / 'markdown.js')) + '); '
                'process.stdout.write(JSON.stringify(m.teile(' + json.dumps(text) + ')));')
        return json.loads(subprocess.run(['node', '-e', code], capture_output=True, text=True, encoding='utf-8', check=True).stdout)

    @unittest.skipUnless(shutil.which('node'), 'node fehlt')
    def test_markdown_links_streichung_kursiv(self):
        arten = lambda text: [(x['art'], x['text']) for x in self.teile(text)]
        self.assertEqual(arten('a ~~alt~~ b'), [('text', 'a '), ('streich', 'alt'), ('text', ' b')])
        self.assertEqual(arten('_kursiv_ und *auch*'), [('kursiv', 'kursiv'), ('text', ' und '), ('kursiv', 'auch')])
        # snake_case und Rechnungen bleiben Text
        self.assertEqual(arten('a_b_c und 2 * 3 * 4'), [('text', 'a_b_c und 2 * 3 * 4')])
        link = self.teile('Siehe [Doku](https://example.com/x?y=1).')[1]
        self.assertEqual((link['art'], link['text'], link['url']), ('link', 'Doku', 'https://example.com/x?y=1'))
        self.assertEqual(self.teile('[m](mailto:a@b.de)')[0]['url'], 'mailto:a@b.de')
        # nur http, https und mailto werden zu Ankern; alles andere bleibt Text
        for boese in ('[x](javascript:alert(1))', '[x](data:text/html,hi)', '[x](/relativ)', '[x](file:///C:/geheim)'):
            self.assertNotIn('link', [x['art'] for x in self.teile(boese)], boese)
        # ein Link darf Formatierung tragen, aber keinen zweiten Link; Code bleibt Code
        innen = self.teile('[**fett**](https://a.de)')[0]
        self.assertEqual((innen['art'], innen['text']), ('link', '**fett**'))
        self.assertEqual(arten('`[a](https://b.de)`'), [('code', '[a](https://b.de)')])

    def test_takt_nur_fuer_sichtbares(self):
        # HS-52a: ein Takt nur für sichtbare Anzeigen (Taskleiste, offenes Start-Menü) und nur bei sichtbarem Tab; sonst Ereignisse
        erlaubt = {'taskleiste.js', 'startmenue.js'}
        for js in ORDNER.glob('*.js'):
            text = js.read_text(encoding='utf-8')
            if 'setInterval' in text:
                self.assertIn(js.name, erlaubt, js.name + ': ein neuer Takt braucht einen Eintrag in HS-52a')
                self.assertIn('document.hidden', text, js.name + ': der Takt ruht bei verstecktem Tab')
        menue = (ORDNER / 'startmenue.js').read_text(encoding='utf-8')
        self.assertIn('clearInterval', menue, 'der Takt des Start-Menüs endet mit dem Schließen')


if __name__ == '__main__':
    unittest.main()
