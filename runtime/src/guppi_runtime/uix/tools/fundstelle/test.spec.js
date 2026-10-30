// Spec des Werkzeugs „Fundstelle“ (SPEC_SHELL_WISSEN_v1 §4.2, W3) im Schein-DOM: `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`.
'use strict';
const assert = require('node:assert/strict');
globalThis.sedra = {registerTool(){}};
require('../../ui/dom.js');
require('../../ui/zitate.js');     // seit Härtung E4 in ui/
const {kopfText, teile, tool} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const A = {id: 'W0123456789', quelle: 'Q-1', datei: 'docs/A.md', stelle: 'Titel > Lease', datum: '2026-10-20T10:00:00Z', text: 'Vor dem Laden die Lease holen.',
           stufe: 1, projekt: null, personenbezug: true, adapter: 'markdown', quelle_pfad: 'repo/docs', befunde: [],
           davor: {id: 'W0123456788', stelle: 'Titel', text: 'Einleitung'}, danach: null};
const antwort = fehler=>(path, body)=>{
  if(path === '/api/objects' && body.type === 'wissen_abschnitt') return fehler || {type: 'wissen_abschnitt', id: body.id, abschnitt: Object.assign({}, A, {id: body.id})};
  return new Error('unerwartet');
};
async function mount(object, fn, extra){
  const el = K.container(), ctx = Object.assign(K.context(object, fn), extra || {});
  await tool.mount(el, ctx); await K.settle();
  return {el, ctx};
}

check('leer: sagt, was hier steht; liest nichts', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, antwort());
  assert.match(el.textContent, /Wähle einen Treffer im Wissen/);
  assert.equal(ctx.calls.length, 0);
});

check('wissen.auswahl zeigt den Abschnitt mit Nachbarn, Kopf, Personenbezug und markierten Suchwörtern', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, antwort());
  ctx.bus.emit('wissen.auswahl', {id: 'W0123456789', quelle: 'Q-1', woerter: ['lease']}); await K.settle();
  assert.deepEqual(ctx.calls[0].body, {type: 'wissen_abschnitt', id: 'W0123456789'});
  assert.match(el.textContent, /Titel > Lease/); assert.match(el.textContent, /docs\/A\.md · Stand 2026-10-20 · Stufe 1 · alle Projekte/);
  assert.match(el.textContent, /Personenbezug – bleibt lokal/); assert.match(el.textContent, /davor: Titel/); assert.match(el.textContent, /Einleitung/);
  assert.equal(el.querySelector('mark.t-fundstelle-mark').textContent, 'Lease');
});

check('„Ins Gespräch“ sendet wissen.auswahl mit Zweck; der eigene Empfang ignoriert ihn; „Quelle zeigen“ öffnet die Quellen', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, antwort());
  const gehoert = []; ctx.bus.on('wissen.auswahl', e=>gehoert.push(e));
  await tool.zeigen('W0123456789'); await K.settle();
  const n = ctx.calls.length;
  await el.querySelectorAll('button').find(b=>b.textContent === 'Ins Gespräch übernehmen').onclick({stopPropagation(){}}); await K.settle();
  assert.deepEqual(gehoert[0], {id: 'W0123456789', quelle: 'Q-1', zweck: 'gespraech', stelle: 'Titel > Lease'});
  assert.equal(ctx.calls.length, n, 'kein neues Lesen');
  await el.querySelectorAll('button').find(b=>b.textContent === 'Quelle zeigen').onclick({stopPropagation(){}});
  assert.deepEqual(ctx.opened[0], {type: 'wissen', id: 'speicher', title: 'Wissen', view: 'quellen', quelle: 'Q-1'});
});

check('nicht lesbar: ein Satz; eine fremde Kennung wird nicht gelesen', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, antwort(new Error('wis_abschnitt_unbekannt')));
  await tool.zeigen('W0123456789'); await K.settle();
  assert.match(el.textContent, /gibt es nicht mehr, oder er ist für dich nicht lesbar/);
  await tool.zeigen('../etc'); await K.settle();
  assert.equal(ctx.calls.length, 1);
});

check('Gedächtnis: nur die Kennung in der Sitzung, nach dem Neuladen wieder gelesen', async()=>{
  const m = new Map(); const sitzung = {get: (n, v)=>m.has(n) ? m.get(n) : v, set: (n, v)=>m.set(n, v), clear(){}};
  const a = await mount({type: 'wissen', id: 'speicher'}, antwort(), {sitzung});
  await tool.zeigen('W0123456789'); await K.settle();
  assert.deepEqual([...m], [['abschnitt', 'W0123456789']]);
  tool.unmount(a.el);
  const b = await mount({type: 'wissen', id: 'speicher'}, antwort(), {sitzung});
  assert.match(b.el.textContent, /Vor dem Laden die Lease holen/);
});

check('reine Teile', ()=>{
  assert.equal(kopfText(Object.assign({}, A, {projekt: 'P1'})), 'docs/A.md · Stand 2026-10-20 · Stufe 1 · Projekt P1');
  assert.equal(kopfText(null), '');
  assert.deepEqual(teile('Die Lease', ['lease']).filter(t=>t.mark).map(t=>t.text), ['Lease']);
});

(async()=>{
  let failed = 0;
  for(const [name, fn] of checks){
    try{ await fn(); console.log('ok   ' + name); }
    catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + (err && err.stack || err)); }
  }
  console.log(JSON.stringify({checks: checks.length, failed}));
  process.exitCode = failed ? 1 : 0;
})();
