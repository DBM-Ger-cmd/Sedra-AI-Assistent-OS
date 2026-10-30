"""Vertrag 1.1 im Browser-Teil (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §3, §9.3–§9.5, §10.3; Abnahme A1, A2, A4-Teil, A11, A12, A13).

Rein mit node: ui/lifecycle.js in einem leeren Kontext, Schein-Speicher für die Sitzung, Schein-Uhr fürs Bündeln, Schein-api für die
Ablage. Kein Browser nötig."""
import unittest

from test_uix_contract import NODE, UIX, run_js

LIFE = [UIX / 'ui' / 'lifecycle.js']

SCHEIN = """
  function speicher(werfen){ const m = new Map(); return {
    get length(){ return m.size; }, key(i){ return Array.from(m.keys())[i] || null; },
    getItem(k){ if(werfen) throw new Error('privat'); return m.has(k) ? m.get(k) : null; },
    setItem(k, v){ if(werfen) throw new Error('voll'); m.set(k, String(v)); }, removeItem(k){ m.delete(k); }, _m: m }; }
  function uhr(){ const t = {n: 0, f: new Map(), setTimeout(f){ t.n += 1; t.f.set(t.n, f); return t.n; }, clearTimeout(id){ t.f.delete(id); },
                  lauf(){ const fs = Array.from(t.f.values()); t.f.clear(); fs.forEach(f=>f()); } }; return t; }
"""


@unittest.skipUnless(NODE, 'node fehlt')
class Gedaechtnis(unittest.TestCase):
    def test_memo_uebersteht_abbau_und_einhaengen(self):
        """A1: ein Wert im Memo ist nach unmount/mount wieder da; anderes Objekt, anderes Memo."""
        out = run_js(LIFE, """
          const l = box.sedraLifecycle;
          const tool = {id: 'probe', mount(el, ctx){ this.ctx = ctx; this.wert = ctx.memo.get('ansicht', 'start'); }, unmount(){}};
          const obj = {type: 'wissen', id: 'speicher'};
          let ctx = {memo: l.memoFuer('probe', obj)};
          let st = l.mountTool(tool, {}, ctx); ctx.memo.set('ansicht', 'quellen'); l.unmountTool(st);
          st = l.mountTool(tool, {}, {memo: l.memoFuer('probe', obj)});
          const zuerst = tool.wert;
          l.mountTool(tool, {}, {memo: l.memoFuer('probe', {type: 'task', id: 'M-1'})});
          console.log(JSON.stringify({zuerst, anderes: tool.wert}));
        """)
        self.assertEqual(out, {'zuerst': 'quellen', 'anderes': 'start'})

    def test_sitzung_nur_mit_manifest_und_mit_grenzen(self):
        """A1/A2: ohne Angabe eine Attrappe; Grenzen 4 KB je Objekt und 64 KB gesamt; kaputtes JSON und ein werfender Speicher brechen nichts."""
        out = run_js(LIFE, SCHEIN + """
          const l = box.sedraLifecycle, s = speicher(), probleme = [];
          const sagen = (id, err)=>probleme.push(err.message);
          const ohne = l.sitzungFuer('probe', {type: 'wissen', id: 'speicher'}, false, s, sagen);
          ohne.set('ansicht', 'quellen');
          const mit = l.sitzungFuer('probe', {type: 'wissen', id: 'speicher'}, true, s, sagen);
          mit.set('ansicht', 'quellen');
          const neu = l.sitzungFuer('probe', {type: 'wissen', id: 'speicher'}, true, s, sagen);   // wie nach dem Neuladen
          const nachNeuladen = neu.get('ansicht');
          mit.set('gross', 'x'.repeat(5000));
          const nachGross = neu.get('gross', 'nicht da');
          for(let i = 0; i < 20; i++) l.sitzungFuer('probe', {type: 'task', id: 'T' + i}, true, s, sagen).set('t', 'y'.repeat(3500));
          s.setItem('sedra.memo.kaputt|task:1', '{kein json');
          const kaputt = l.sitzungFuer('kaputt', {type: 'task', id: '1'}, true, s, sagen).get('a', 'vorgabe');
          const w = l.sitzungFuer('probe', {type: 'task', id: '1'}, true, speicher(true), sagen);
          w.set('a', 1); const geworfen = w.get('a', 'vorgabe');
          console.log(JSON.stringify({attrappe: ohne.get('ansicht', 'leer'), aktiv: ohne.aktiv, nachNeuladen, nachGross,
                                      gesamtGrenze: probleme.some(p=>p.indexOf('64 KB') >= 0), kaputt, geworfen,
                                      schluessel: Array.from(s._m.keys())[0]}));
        """)
        self.assertEqual(out['attrappe'], 'leer'); self.assertFalse(out['aktiv'])
        self.assertEqual(out['nachNeuladen'], 'quellen'); self.assertEqual(out['nachGross'], 'nicht da')
        self.assertTrue(out['gesamtGrenze']); self.assertEqual(out['kaputt'], 'vorgabe'); self.assertEqual(out['geworfen'], 'vorgabe')
        self.assertEqual(out['schluessel'], 'sedra.memo.probe|wissen:speicher')

    def test_ablage_laedt_einmal_und_schreibt_gebuendelt(self):
        """§10.3: get() lädt einmal; viele set() → ein Schreiben nach einer Sekunde; unmount schreibt sofort, was noch offen ist."""
        out = run_js(LIFE, SCHEIN + """
          (async()=>{
            const l = box.sedraLifecycle, u = uhr(), rufe = [];
            const api = async(path, opt)=>{ rufe.push(path + ' ' + JSON.stringify(opt.body)); return path.endsWith('lesen') ? {werte: {frage: 'alt'}, zeit: 5} : {}; };
            const a = l.ablageFuer('wissen', {type: 'wissen', id: 'speicher'}, true, api, u);
            const frage = await a.get('frage'); await a.get('ergebnis', null);
            a.set('frage', 'neu'); a.set('ergebnis', [1, 2]); a.set('frage', 'neuer');
            const vorher = rufe.length; u.lauf(); await new Promise(r=>setTimeout(r, 0));
            a.set('k', 10);
            l.unmountTool({mounted: true, mod: {unmount(){}}, el: {replaceChildren(){}}, ctx: {ablage: a}});
            const ohne = l.ablageFuer('wissen', {type: 'wissen', id: 'speicher'}, false, api, u);
            const panel = l.ablageFuer('talk', null, true, api, u);
            console.log(JSON.stringify({frage, vorher, rufe, ohne: await ohne.get('frage', 'leer'), panel: panel.aktiv}));
          })();
        """)
        self.assertEqual(out['frage'], 'alt')
        self.assertEqual(out['vorher'], 1)                       # nur einmal gelesen, noch nichts geschrieben
        writes = [r for r in out['rufe'] if 'schreiben' in r]
        self.assertEqual(len(writes), 2)                          # einmal gebündelt, einmal beim unmount
        self.assertIn('"frage":"neuer"', writes[0]); self.assertIn('"k":10', writes[1])
        self.assertEqual(out['ohne'], 'leer'); self.assertFalse(out['panel'])

    def test_ablage_set_vor_get_ueberschreibt_nichts(self):
        """Härtung 30.10. (HU-L4): set() vor dem ersten get() – der Server ersetzt die Werte, also werden die vorhandenen erst geholt und bleiben."""
        out = run_js(LIFE, SCHEIN + """
          (async()=>{
            const l = box.sedraLifecycle, u = uhr(), rufe = [];
            const api = async(path, opt)=>{ rufe.push([path, opt.body]); return path.endsWith('lesen') ? {werte: {alt: 'bleibt', frage: 'x'}, zeit: 5} : {}; };
            const a = l.ablageFuer('wissen', {type: 'wissen', id: 'speicher'}, true, api, u);
            a.set('frage', 'neu');
            u.lauf(); await new Promise(r=>setTimeout(r, 0)); await new Promise(r=>setTimeout(r, 0));
            const geschrieben = rufe.filter(r=>r[0].endsWith('schreiben')).map(r=>r[1].werte);
            console.log(JSON.stringify({geschrieben, alt: await a.get('alt', 'weg')}));
          })();
        """)
        self.assertEqual(out['geschrieben'], [{'alt': 'bleibt', 'frage': 'neu'}])
        self.assertEqual(out['alt'], 'bleibt')

    def test_schliessen_vergisst_memo_und_sitzung(self):
        """A11: memoVergessen(objekt) löscht Memo und Sitzung aller Werkzeuge an diesem Objekt, andere bleiben."""
        out = run_js(LIFE, SCHEIN + """
          const l = box.sedraLifecycle, s = speicher();
          const o = {type: 'wissen', id: 'speicher'}, p = {type: 'task', id: 'M-1'};
          l.memoFuer('wissen', o).set('a', 1); l.memoFuer('fundstelle', o).set('b', 2); l.memoFuer('task', p).set('c', 3);
          l.sitzungFuer('wissen', o, true, s).set('a', 1); l.sitzungFuer('task', p, true, s).set('c', 3);
          l.memoVergessen(o, s);
          console.log(JSON.stringify({a: l.memoFuer('wissen', o).get('a', null), b: l.memoFuer('fundstelle', o).get('b', null),
                                      c: l.memoFuer('task', p).get('c', null), keys: Array.from(s._m.keys())}));
        """)
        self.assertEqual((out['a'], out['b'], out['c']), (None, None, 3))
        self.assertEqual(out['keys'], ['sedra.memo.task|task:M-1'])

    def test_scrollposition_kommt_zurueck(self):
        """§3.3: unmount merkt sich scrollTop, mount stellt ihn nach `ready` wieder her."""
        out = run_js(LIFE, """
          (async()=>{
            const l = box.sedraLifecycle, memo = l.memoFuer('probe', {type: 'task', id: 'M-1'});
            const el = {scrollTop: 240, parentElement: null, replaceChildren(){}};
            const tool = {id: 'probe', mount(){ return Promise.resolve(); }, unmount(){}};
            l.unmountTool({mounted: true, mod: tool, el, ctx: {memo}});
            const neu = {scrollTop: 0, parentElement: null};
            const st = l.mountTool(tool, neu, {memo}); await st.ready;
            console.log(JSON.stringify({gemerkt: memo.get('__scroll'), jetzt: neu.scrollTop}));
          })();
        """)
        self.assertEqual(out['gemerkt']['selbst'], 240); self.assertEqual(out['jetzt'], 240)


@unittest.skipUnless(NODE, 'node fehlt')
class VerstecktUndGebuendelt(unittest.TestCase):
    def test_versteckt_halten_ruft_die_haken(self):
        """A12: bereitHalten ruft hidden(el), zeigen ruft shown(el); nur `instanzen: viele` gilt als mehrfach."""
        out = run_js(LIFE, """
          const l = box.sedraLifecycle, log = [];
          const mod = {id: 'board', mount(){}, unmount(){}, hidden(el){ log.push('hidden:' + el.name); }, shown(el){ log.push('shown:' + el.name); }};
          const st = l.mountTool(mod, {name: 'A', hidden: false}, {});
          l.bereitHalten(st); l.bereitHalten(st); const versteckt = st.el.hidden; l.zeigen(st); l.zeigen(st);
          console.log(JSON.stringify({log, versteckt, sichtbar: !st.el.hidden,
                                      viele: l.istMehrfach({instanzen: 'viele'}), eine: l.istMehrfach({}), version: l.VERSION}));
        """)
        self.assertEqual(out['log'], ['hidden:A', 'shown:A'])           # doppelt aufgerufen zählt einmal
        self.assertTrue(out['versteckt']); self.assertTrue(out['sichtbar'])
        self.assertTrue(out['viele']); self.assertFalse(out['eine']); self.assertEqual(out['version'], '1.1')

    def test_zehn_anstoesse_ein_aufruf(self):
        """A13: 10 Anstöße im Fenster → genau ein Aufruf; `jetzt()` ruft sofort und räumt das Fenster ab."""
        out = run_js(LIFE, SCHEIN + """
          const l = box.sedraLifecycle, u = uhr(); let n = 0;
          const b = l.buendeln(()=>{ n += 1; }, 500, u);
          for(let i = 0; i < 10; i++) b();
          const vorher = n; u.lauf(); const nach = n;
          b(); b.jetzt(); u.lauf();
          console.log(JSON.stringify({vorher, nach, ende: n, wartet: b.wartet()}));
        """)
        self.assertEqual(out, {'vorher': 0, 'nach': 1, 'ende': 2, 'wartet': False})


@unittest.skipUnless(NODE, 'node fehlt')
class Ortskunde(unittest.TestCase):
    def test_wissen_und_eindeutige_woerter(self):
        """A15: Wissen ist überall ein Ort; „gate“ und „sandbox“ zeigen auf genau einen Ort; „speicher“ bleibt Hardware."""
        out = run_js([UIX / 'ui' / 'places.js'], """
          const P = box.sedraPlaces, ziel = t=>{ const r = P.routeText(t); return r && r.kind === 'place' ? r.id : 'talk'; };
          const zweimal = w=>P.PLACES.filter(p=>p.words.indexOf(w) >= 0).map(p=>p.id);
          console.log(JSON.stringify({
            wissen: ziel('wissen'), speicherW: ziel('wissensspeicher'), db: ziel('öffne die wissensdatenbank'), quellen: ziel('quellen'),
            speicher: ziel('speicher'), gate: zweimal('gate'), sandbox: zweimal('sandbox'),
            nachmessung: (P.routeText('nachmessung').object || {}).view, frage: ziel('was steht im wissen über D7.4?'),
            alt: [ziel('logbuch'), ziel('modelle'), ziel('entscheidungen'), ziel('gateway')]}));
        """)
        self.assertEqual((out['wissen'], out['speicherW'], out['db'], out['quellen']), ('wissen', 'wissen', 'wissen', 'wissen'))
        self.assertEqual(out['speicher'], 'hardware')
        self.assertEqual(out['gate'], ['decisions']); self.assertEqual(out['sandbox'], ['boundary'])
        self.assertEqual(out['nachmessung'], 'messung')
        self.assertEqual(out['frage'], 'talk')                     # eine Frage geht ans Gespräch, nicht an einen Ort
        self.assertEqual(out['alt'], ['logbook', 'models', 'decisions', 'gateway'])


class Knoepfe(unittest.TestCase):
    """Z5/Z6: im echten Browser – nur dort gilt die Regel, nach der Enter den ersten Absende-Knopf eines Formulars klickt."""

    def test_enter_klickt_nur_den_absende_knopf(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('playwright fehlt')
        dom = (UIX / 'ui' / 'dom.js').read_text(encoding='utf-8')
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception as exc:
                self.skipTest(f'kein Browser: {exc}')
            try:
                page = browser.new_page(); page.set_content('<div id=host></div>'); page.add_script_tag(content=dom)
                log = page.evaluate("""()=>{ const d = window.sedraDom, log = [];
                  const bau = (absenden)=>{ const f = d.el('form'); const i = d.el('input'); f.onsubmit = e=>{ e.preventDefault(); log.push('submit'); };
                    f.append(i, d.button('Abbrechen', ()=>log.push('abbrechen')), d.button('OK', ()=>log.push('ok'), 'p', absenden ? {absenden: true} : undefined));
                    document.getElementById('host').replaceChildren(f); return i; };
                  window.__bau = bau; window.__log = log; return log; }""")
                page.evaluate('()=>window.__bau(true).focus()'); page.keyboard.press('Enter'); page.wait_for_timeout(50)
                mit = page.evaluate('()=>window.__log.splice(0)')
                page.evaluate('()=>window.__bau(false).focus()'); page.keyboard.press('Enter'); page.wait_for_timeout(50)
                ohne = page.evaluate('()=>window.__log.splice(0)')
                typen = page.evaluate("()=>Array.from(document.querySelectorAll('button')).map(b=>b.type)")
                # das Stufen-Formular im Wissen: ein Zahlenfeld, „Abbrechen“ und „Bestätigen“ als normale Knöpfe, onsubmit führt aus
                page.evaluate("""()=>{ const d = window.sedraDom, f = d.el('form'), i = d.el('input'); i.type = 'number';
                  f.onsubmit = e=>{ e.preventDefault(); window.__log.push('ok'); };
                  f.append(i, d.button('Abbrechen', ()=>window.__log.push('abbrechen')), d.button('Bestätigen', ()=>window.__log.push('ok'), 'p'));
                  document.getElementById('host').replaceChildren(f); i.focus(); }""")
                page.keyboard.press('Enter'); page.wait_for_timeout(50)
                stufe = page.evaluate('()=>window.__log.splice(0)')
            finally:
                browser.close()
        self.assertEqual(mit, ['ok', 'submit'])                # genau der Absende-Knopf, „Abbrechen“ nicht
        # ohne Absende-Knopf löst Enter keinen Knopf aus; ein Formular mit nur einem Textfeld sendet nach HTML trotzdem ab –
        # das fängt jedes Formular im Paket mit onsubmit = preventDefault ab
        self.assertNotIn('abbrechen', ohne); self.assertNotIn('ok', ohne)
        self.assertEqual(typen, ['button', 'button'])
        self.assertEqual(stufe, ['ok'])                       # genau einmal, und „Abbrechen“ nicht (V6, im Browser bestätigt 26.10.)


if __name__ == '__main__':
    unittest.main()
