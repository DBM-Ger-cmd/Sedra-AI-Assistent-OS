// Spec des Instruments im Schein-DOM (Spec 4, D4.4): mounten, eine Lesung der Leiste übergeben, Text prüfen.
// `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`; tests/test_uix_shell_d_pure.py ruft sie so auf.
'use strict';
const assert = require('node:assert/strict');
globalThis.sedra = {registerTool(){}};
require('../../ui/dom.js');
const {tool} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
function mount(){
  const el = K.container(), ctx = K.context(null, ()=>{ throw new Error('ein Instrument liest nicht selbst'); });
  tool.mount(el, ctx);
  return {el, ctx};
}

check('mit Daten: Wert, Hinweis, Ton', ()=>{
  const {el} = mount();
  tool.update({slots: {value: '2/3', hint: '1 wartet', tone: 'warn'}}, null);
  assert.equal(el.textContent, 'Slots2/31 wartet');
  assert.ok(el.classList.contains('warn'));
});

check('ohne Feld slots (kein Scheduler): „–“ und „noch keine Daten“', ()=>{
  const {el} = mount();
  tool.update({gpu: {value: '12 GB'}}, null);
  assert.equal(el.textContent, 'Slots–noch keine Daten');
});

check('Leiste nicht lesbar', ()=>{
  const {el} = mount();
  tool.update(null, 'Keine Verbindung');
  assert.equal(el.textContent, 'Slots–nicht lesbar');
  assert.equal(el.title, 'Keine Verbindung');
});

check('Klick öffnet Modelle und Slots; kein eigener Aufruf; unmount räumt auf', ()=>{
  const {el, ctx} = mount();
  el.click();
  assert.deepEqual(ctx.opened, [{type: 'model', id: 'alle', title: 'Modelle und Slots', collection: true}]);
  assert.equal(ctx.calls.length, 0);
  tool.unmount(el);
  assert.equal(el.children.length, 0);
  assert.ok(!el.classList.contains('t-gauge-slots'));
});

let failed = 0;
for(const [name, fn] of checks){
  try{ fn(); console.log('ok   ' + name); }
  catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + (err && err.stack || err)); }
}
console.log(JSON.stringify({checks: checks.length, failed}));
process.exitCode = failed ? 1 : 0;
