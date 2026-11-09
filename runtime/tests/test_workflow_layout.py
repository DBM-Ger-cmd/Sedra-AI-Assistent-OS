"""Layout und Kantenführung der Workflow-Darstellungen: der Node-Test (rein) und der echte Browser mit dem Ablauf „Vollautomatischer Bau“
in beiden Apps – nach „Aufräumen“ läuft keine Kante durch einen Knoten, Rücksprünge liegen unter dem Ablauf."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from test_process_browser import ProcessBrowser as _Hilfe

UI = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix' / 'ui'


class LayoutRein(unittest.TestCase):
    def test_node_test_besteht_und_bleibt_klein(self):
        if not shutil.which('node'):
            self.skipTest('node fehlt')
        run = subprocess.run(['node', 'workflow-layout.test.js'], cwd=UI, capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout[-900:] + run.stderr[-300:])
        ergebnis = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertEqual(ergebnis['failed'], 0)
        self.assertLessEqual(ergebnis['checks'], 20)

    def test_die_datei_bleibt_unter_400_zeilen(self):
        for name in ('workflow-layout.js', 'workflow-canvas.js', 'workflow-extras.js'):
            self.assertLess(len((UI / name).read_text(encoding='utf-8').splitlines()), 400, name)


GEOMETRIE = """()=>{
  const wurzel = document.querySelector('.t-n8n-workflow, .t-scenario');
  const kisten = [...wurzel.querySelectorAll('.t-wf-node')].map(g=>{
    const m = /translate\\(([-\\d.]+)[ ,]+([-\\d.]+)\\)/.exec(g.getAttribute('transform') || ''); const b = (g.querySelector('.t-wf-tile, .t-wf-module-ring') || g).getBBox();
    return {x: +m[1] + b.x, y: +m[2] + b.y, w: b.width, h: b.height};
  });
  const treffer = [];
  [...wurzel.querySelectorAll('path.t-wf-edge')].forEach((p, i)=>{
    const l = p.getTotalLength();
    for(let s = 14; s < l - 14; s += 4){
      const q = p.getPointAtLength(s);
      kisten.forEach((k, n)=>{ if(q.x > k.x + 3 && q.x < k.x + k.w - 3 && q.y > k.y + 3 && q.y < k.y + k.h - 3) treffer.push([i, n, Math.round(q.x), Math.round(q.y)]); });
    }
  });
  const unten = Math.max(...kisten.map(k=>k.y + k.h));
  const tiefste = Math.max(...[...wurzel.querySelectorAll('path.t-wf-edge')].map(p=>p.getBBox().y + p.getBBox().height));
  return {knoten: kisten.length, kanten: wurzel.querySelectorAll('path.t-wf-edge').length, treffer, unten, tiefste};
}"""


@unittest.skipUnless(os.environ.get('SEDRA_BROWSER') == '1', 'Set SEDRA_BROWSER=1')
class LayoutImBrowser(unittest.TestCase):
    session = _Hilfe.session
    open = _Hilfe.open

    def bau_oeffnen(self, page, kind):
        app = self.open(page, kind)
        if kind == 'workflow':
            app.get_by_role('tab', name='Übersicht').click()
            app.get_by_role('button', name='Abläufe von SEDRA anlegen oder aktualisieren').click()
            page.wait_for_function("()=>document.querySelectorAll('.t-n8n-workflow .t-wf-card').length>=6")
            app.locator('.t-wf-card', has_text='Vollautomatischer Bau').get_by_role('button', name='Öffnen').click()
            page.wait_for_function("()=>document.querySelector('.t-n8n-workflow input[aria-label=\"Workflow-Titel\"]').value.includes('Vollautomatischer Bau')")
            app.get_by_label('Prozessansicht').select_option('canvas')
            page.wait_for_function("()=>document.querySelectorAll('.t-n8n-workflow .t-wf-node').length>=8")
        return app

    def test_vollautomatischer_bau_nach_aufraeumen_ohne_kante_durch_knoten(self):
        def run(page, url):
            app = self.bau_oeffnen(page, 'workflow')
            app.get_by_role('button', name='Aufräumen: Knoten ordnen').click()
            page.wait_for_timeout(400)
            g = page.evaluate(GEOMETRIE)
            self.assertGreaterEqual(g['knoten'], 8)
            self.assertGreaterEqual(g['kanten'], g['knoten'] - 1)
            self.assertEqual(g['treffer'], [], 'eine Kante läuft durch einen Knoten')
            self.assertGreater(g['tiefste'], g['unten'] - 1, 'Rücksprünge laufen unter dem Ablauf entlang')
        self.session(run)

    def test_szenario_studio_zeichnet_dieselben_wege(self):
        def run(page, url):
            app = self.open(page, 'scenario')
            app.get_by_role('button', name='Aufräumen: Knoten ordnen').click()
            page.wait_for_timeout(300)
            g = page.evaluate(GEOMETRIE)
            self.assertEqual(g['treffer'], [])
        self.session(run)


if __name__ == '__main__':
    unittest.main()
