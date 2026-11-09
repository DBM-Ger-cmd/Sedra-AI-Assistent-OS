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

    def test_node_test_chat_und_minimap(self):
        if not shutil.which('node'):
            self.skipTest('node fehlt')
        run = subprocess.run(['node', 'workflow-chat.test.js'], cwd=UI, capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout[-900:] + run.stderr[-300:])
        ergebnis = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertEqual(ergebnis['failed'], 0)
        self.assertLessEqual(ergebnis['checks'], 20)

    def test_die_datei_bleibt_unter_400_zeilen(self):
        for name in ('workflow-layout.js', 'workflow-canvas.js', 'workflow-extras.js', 'workflow-editor.js', 'workflow-chat.js', 'workflow-minimap.js'):
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

    def editor_oeffnen(self, page, kind):
        app = self.open(page, kind)
        if kind == 'workflow':
            app.get_by_role('tab', name='Editor').click()
        return app

    def test_minimap_laesst_sich_verschieben_bleibt_in_der_flaeche_und_wird_gemerkt(self):
        def run(page, url):
            app = self.bau_oeffnen(page, 'workflow')
            griff = app.get_by_role('button', name='Minimap verschieben', exact=False)
            griff.scroll_into_view_if_needed()
            flaeche = app.locator('.t-wf-canvas').bounding_box()
            vorher = griff.bounding_box()
            page.mouse.move(vorher['x'] + 8, vorher['y'] + 8); page.mouse.down()
            page.mouse.move(vorher['x'] - 500, vorher['y'] - 240, steps=6); page.mouse.up()
            nachher = griff.bounding_box()
            self.assertLess(nachher['x'], vorher['x'] - 400)
            self.assertLess(nachher['y'], vorher['y'] - 200)
            # weit über den Rand hinaus gezogen: sie bleibt ganz in der Fläche
            page.mouse.move(nachher['x'] + 8, nachher['y'] + 8); page.mouse.down(); page.mouse.move(1, 1, steps=4); page.mouse.up()
            rand = griff.bounding_box()
            self.assertGreaterEqual(rand['x'], flaeche['x']); self.assertGreaterEqual(rand['y'], flaeche['y'])
            # Pfeiltaste verschiebt, Pos1 stellt die Ausgangslage wieder her
            griff.focus(); x0 = griff.bounding_box()['x']; page.keyboard.press('ArrowRight')
            self.assertGreater(griff.bounding_box()['x'], x0)
            page.keyboard.press('Home')
            self.assertAlmostEqual(griff.bounding_box()['x'], vorher['x'], delta=2)
            # die Karte unter dem Griff springt weiter wie bisher: ein Klick in die Minimap verschiebt die Ansicht, kein Fehler
            app.locator('.t-wf-minimap-svg').click(position={'x': 40, 'y': 40})
        self.session(run)

    def test_chat_oeffnen_frage_ohne_modell_und_hinweis_im_chat_besprechen(self):
        def run(page, url):
            app = self.bau_oeffnen(page, 'workflow')
            self.assertFalse(app.locator('.t-wf-chat').is_visible())
            # der Hinweis zum Prozess lässt sich im Chat besprechen: der Chat öffnet, die Frage steht im Feld
            app.get_by_role('button', name='Im Chat besprechen').click()
            app.locator('.t-wf-chat').wait_for()
            self.assertIn('Prozessmodell', app.get_by_label('Frage an SEDRA zum Prozess').input_value())
            app.get_by_label('Frage an SEDRA zum Prozess').fill('Warum gibt es zwei Schleifen?')
            app.get_by_role('button', name='Frage senden').click()
            hinweis = app.locator('.t-wf-chat-hinweis')
            hinweis.wait_for(timeout=30000)
            # ohne geladenes Modell: klare Meldung, die Frage bleibt im Feld, die Sitzung mit der Vorlage Prozessmodellierer ist angelegt
            self.assertIn('Kein Modell', hinweis.inner_text())
            self.assertEqual(app.get_by_label('Frage an SEDRA zum Prozess').input_value(), 'Warum gibt es zwei Schleifen?')
            liste = page.evaluate("()=>window.sedraBoot.ctx.api('/api/harness/sitzungen')")
            vorlagen = [s['vorlage'] for s in liste['sitzungen']]
            self.assertIn('n8n-workflow-manager', vorlagen)
            app.get_by_role('button', name='Chat schließen').click()
            self.assertFalse(app.locator('.t-wf-chat').is_visible())
        self.session(run)

    def test_chat_auch_im_szenario_studio_und_anregungen_fuellen_das_feld(self):
        def run(page, url):
            app = self.open(page, 'scenario')
            app.get_by_role('button', name='Chat zum Prozess öffnen oder schließen').click()
            app.locator('.t-wf-chat').wait_for()
            app.get_by_role('button', name='Finde Lücken').click()
            self.assertIn('Lücken', app.get_by_label('Frage an SEDRA zum Prozess').input_value())
            # Escape schließt das Fenster, ohne den Rest der Oberfläche zu stören
            app.get_by_label('Frage an SEDRA zum Prozess').press('Escape')
            self.assertFalse(app.locator('.t-wf-chat').is_visible())
        self.session(run)


if __name__ == '__main__':
    unittest.main()
