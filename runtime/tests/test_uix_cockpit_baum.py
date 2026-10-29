"""SPEC_COCKPIT_BAUM_v1 (K1 bis K9): der Baum des Cockpits mit Wissen, Gruppen, „… n weitere“, Tastatur; die Palette mit Baum,
„Zuletzt“ und „Im Wissen suchen“; der Rahmen (Gespräch aufziehbar, Strg+B, Kürzel). Reine Teile mit node, der Rest im Browser."""
import json
import unittest

from test_uix_contract import NODE, UIX, run_js
from test_uix_dock_stufe2 import Basis

COCKPIT = UIX / 'shells' / 'cockpit'


def tree(probe):
    return run_js([COCKPIT / 'tree.js'], probe)


class Rein(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_k1_wissen_in_der_bibliothek(self):
        out = tree("""
          const W = box.sedraTree.wissenNote;
          const st = (m, a, o)=>({state: m, stand: {modus: m, abdeckung: a, vorschlaege_offen: o}});
          const rows = box.sedraTree.treeModel({wissen: st('hybrid', 0.85, 2), wissensbasis: true});
          const w = rows.find(r=>r.title === 'Wissen');
          console.log(JSON.stringify({w: [w.gruppe, w.note, w.tone, w.object.type], shell: rows.some(r=>r.object && r.object.type === 'shell'),
            faelle: [W(st('hybrid', 0.85, 0)).note, W(st('volltext', 0, 0)).note, W({state: 'aus', stand: null}).note, W(null).note, W(st('hybrid', 1, 1)).tone],
            ohne: box.sedraTree.treeModel({}).some(r=>r.object && r.object.type === 'shell'), gespraech: rows.some(r=>r.title === 'Gespräch unten')}));
        """)
        self.assertEqual(out['w'], ['Bibliothek', 'hybrid · 85 % · 2 Vorschläge', 'warn', 'wissen'])
        self.assertEqual(out['faelle'], ['hybrid · 85 %', 'nur Volltext', 'ausgeschaltet', 'ausgeschaltet', 'warn'])
        self.assertTrue(out['shell']); self.assertFalse(out['ohne']); self.assertFalse(out['gespraech'], 'T1')

    def test_k2_nichts_verschwindet_still_und_keine_missions_id(self):
        out = tree("""
          const missions = Array.from({length: 13}, (_, i)=>({mission_id: 'M-' + i, intent: i ? 'Aufgabe ' + i : '', status: 'active'}));
          const intents = Array.from({length: 9}, (_, i)=>({id: 'V-' + i, title: 'Vorhaben ' + i}));
          const rows = box.sedraTree.treeModel({missions, intents});
          const g = n=>rows.filter(r=>r.kind === 'row' && r.gruppe === n).map(r=>r.title);
          console.log(JSON.stringify({aufgaben: g('Aufgaben'), vorhaben: g('Vorhaben'), mehr: rows.filter(r=>r.tone === 'mehr').map(r=>r.object.type + ':' + r.object.id)}));
        """)
        self.assertEqual(len(out['aufgaben']), 13)
        self.assertEqual(out['aufgaben'][0], 'Aufgabe ohne Titel')
        self.assertEqual(out['aufgaben'][-1], '… 1 weitere')
        self.assertNotIn('M-0', json.dumps(out['aufgaben']))
        self.assertEqual(out['vorhaben'][-1], '… 1 weitere')
        self.assertEqual(out['mehr'], ['intent:alle', 'task:alle'])

    def test_k3_k4_zugeklappt_wartet_und_gemerkter_zustand(self):
        out = tree("""
          const T = box.sedraTree;
          const rows = T.treeModel({missions: [{mission_id: 'M-1', intent: 'X', status: 'active', pending_gates: 1}], boundaries: {confirmed: false}});
          const kopf = n=>rows.find(r=>r.kind === 'head' && r.gruppe === n);
          const sicht = T.sichtbar(rows, ['Aufgaben']).filter(r=>r.kind === 'row').map(r=>r.gruppe);
          console.log(JSON.stringify({aufgaben: kopf('Aufgaben').wartet, system: kopf('System').wartet, sicht: [...new Set(sicht)],
            einst: T.sichtbar(rows, ['System']).some(r=>r.title === 'Hardware'), einstAuf: T.sichtbar(rows, ['System', 'Einstellungen']).some(r=>r.title === 'Hardware'),
            kaputt: T.zustandLesen('{x'), fremd: T.zustandLesen(JSON.stringify({offen: [1, 2]})), gut: T.zustandLesen(JSON.stringify({offen: ['System'], aus: true}))}));
        """)
        self.assertEqual((out['aufgaben'], out['system']), (1, 1))
        self.assertEqual(out['sicht'], ['Aufgaben'])
        self.assertFalse(out['einst']); self.assertTrue(out['einstAuf'])
        self.assertEqual(out['kaputt'], {'offen': ['KI GateWay', 'Vorhaben', 'Aufgaben'], 'aus': False})
        self.assertEqual(out['fremd']['offen'], ['KI GateWay', 'Vorhaben', 'Aufgaben'])
        self.assertEqual(out['gut'], {'offen': ['System'], 'aus': True})

    def test_k6_palette_findet_den_baum_zuletzt_und_das_wissen(self):
        out = run_js([UIX / 'ui' / 'places.js', COCKPIT / 'tree.js', COCKPIT / 'palette.js'], """
          const baum = box.sedraTree.treeModel({missions: [{mission_id: 'M-1', intent: 'Ändere Code als Kandidat', status: 'active'}]});
          const R = box.sedraPalette.cockpitRows;
          const zeilen = t=>R(t, baum, [{type: 'logbook', id: 'audit', title: 'Logbuch'}]).map(r=>r.id + '|' + r.label);
          console.log(JSON.stringify({aendere: zeilen('ändere'), leer: zeilen('').slice(0, 2), frage: zeilen('?wie lange dauert der Ofen').slice(0, 1),
                                      wissenNachTalk: zeilen('wie lange dauert der Ofen').slice(0, 2)}));
        """)
        self.assertTrue(any('Ändere Code als Kandidat' in z for z in out['aendere']))
        self.assertEqual(out['leer'][0], 'zuletzt:0|Logbuch')
        self.assertEqual(out['frage'], ['__wissen|Im Wissen suchen: wie lange dauert der Ofen'])
        self.assertEqual([z.split('|')[0] for z in out['wissenNachTalk']], ['__talk', '__wissen'])

    def test_rahmen_rein(self):
        out = run_js([COCKPIT / 'rahmen.js'], """
          const R = box.sedraCockpitRahmen;
          console.log(JSON.stringify([R.hoeheBegrenzen(10, 800), R.hoeheBegrenzen(300, 800), R.hoeheBegrenzen(900, 800), R.hoeheBegrenzen('x', 800),
                                      R.tippt({tagName: 'INPUT'}), R.tippt({tagName: 'DIV'}), R.tippt(null), R.KUERZEL.some(k=>k[0] === 'Strg+B')]));
        """)
        self.assertEqual(out, [64, 300, 400, 64, True, False, False, True])


class ImBrowser(Basis):
    """K4, K5, K7, K9 im Cockpit (Chromium aus playwright)."""

    def test_k5_tastatur_im_baum_und_fokus_nach_dem_neuzeichnen(self):
        page = self.seite()
        page.wait_for_selector('.ck-tree [role=treeitem][tabindex="0"]', timeout=20000)   # Warten auf den Zustand, nicht auf eine Zeit
        page.locator('.ck-tree [role=treeitem][tabindex="0"]').first.focus()
        start = page.evaluate("()=>document.activeElement.dataset.key")
        page.keyboard.press('ArrowDown'); page.keyboard.press('ArrowDown')
        zweite = page.evaluate("()=>document.activeElement.dataset.key")
        self.assertNotEqual(start, zweite)
        page.evaluate("()=>window.sedra.shells.get('cockpit').tree.render()")
        self.assertEqual(page.evaluate("()=>document.activeElement.dataset.key"), zweite, 'der Fokus bleibt auf derselben Zeile')
        page.keyboard.press('Home')
        self.assertEqual(page.evaluate("()=>document.activeElement.dataset.key"), 'g:KI GateWay')
        page.keyboard.press('ArrowLeft')                     # offene Gruppe: zu
        self.assertEqual(page.evaluate("()=>document.activeElement.getAttribute('aria-expanded')"), 'false')
        page.keyboard.press('ArrowRight')
        self.assertEqual(page.evaluate("()=>document.activeElement.getAttribute('aria-expanded')"), 'true')
        self.assertEqual(page.evaluate("()=>document.querySelectorAll('.ck-tree [role=treeitem][tabindex=\"0\"]').length"), 1, 'roving tabindex')
        page.locator('.ck-tree [data-key="g:Bibliothek"]').click()
        page.locator('.ck-tree [data-key="wissen:speicher"]').click()
        page.wait_for_function("()=>(document.querySelector('.dk-tab.on span')||{}).textContent === 'Wissen'", timeout=15000)
        self.assertEqual(page.evaluate("()=>(document.querySelector('.dk-tab.on span')||{}).textContent"), 'Wissen')
        page.reload(); self.uix.wait_until_started(page)
        page.wait_for_selector('.ck-tree [data-key="g:Bibliothek"]', timeout=20000)
        page.wait_for_function("()=>document.querySelector('.ck-tree [data-key=\"g:Bibliothek\"]').getAttribute('aria-expanded') === 'true'", timeout=15000)
        self.assertEqual(page.evaluate("()=>document.querySelector('.ck-tree [data-key=\"g:Bibliothek\"]').getAttribute('aria-expanded')"), 'true', 'K4')
        self.assertEqual(self.fehler, [])

    def test_k7_k9_rahmen_gespraech_baum_und_kuerzel(self):
        page = self.seite()
        hoehe = lambda: page.evaluate("()=>document.querySelector('.ck-talk').getBoundingClientRect().height")
        vorher = hoehe()
        griff = page.locator('.ck-griff').bounding_box()
        page.mouse.move(griff['x'] + 200, griff['y'] + 2); page.mouse.down(); page.mouse.move(griff['x'] + 200, griff['y'] - 150); page.mouse.up()
        self.assertGreater(hoehe(), vorher + 100)
        page.mouse.move(griff['x'] + 200, griff['y'] - 600); page.mouse.down(); page.mouse.move(griff['x'] + 200, 0); page.mouse.up()
        self.assertLessEqual(hoehe(), 450 + 2, 'höchstens die Hälfte des Fensters')
        page.locator('.ck-griff').dblclick()
        self.assertAlmostEqual(hoehe(), vorher, delta=2)
        breite = lambda: page.evaluate("()=>document.querySelector('.ck-tree').getBoundingClientRect().width")
        self.assertGreater(breite(), 200)
        page.keyboard.press('Control+b'); page.wait_for_timeout(200)
        self.assertLess(breite(), 30)
        page.keyboard.press('Control+b'); page.wait_for_timeout(200)
        self.assertGreater(breite(), 200)
        page.locator('.ck-hilfe').click()
        self.assertIn('Strg+B', page.locator('.ck-kuerzel').inner_text())
        page.keyboard.press('Escape')
        self.assertEqual(page.locator('.ck-kuerzel').count(), 0)
        page.locator('body').click(position={'x': 700, 'y': 400}); page.keyboard.press('?')
        self.assertEqual(page.locator('.ck-kuerzel').count(), 1)
        self.assertEqual(self.fehler, [])

    def test_k8_neu_menue_mit_tastatur_und_quelle_fuer_wissen(self):
        page = self.seite()
        knopf = page.locator('button', has_text='＋ Neu').first
        knopf.click()
        page.wait_for_function("()=>document.activeElement && document.activeElement.classList.contains('ck-menu-item')", timeout=15000)
        self.assertEqual(page.evaluate("()=>document.activeElement.classList.contains('ck-menu-item')"), True)
        page.keyboard.press('ArrowUp')
        self.assertIn('Quelle für Wissen', page.evaluate("()=>document.activeElement.innerText"))
        page.keyboard.press('Escape')
        page.wait_for_function("()=>document.querySelectorAll('.ck-menu').length === 0", timeout=15000)
        self.assertEqual(page.locator('.ck-menu').count(), 0)
        self.assertEqual(page.evaluate("()=>document.activeElement.textContent"), knopf.inner_text())
        self.assertEqual(self.fehler, [])


if __name__ == '__main__':
    unittest.main()
