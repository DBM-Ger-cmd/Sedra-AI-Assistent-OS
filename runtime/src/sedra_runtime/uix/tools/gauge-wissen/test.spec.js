// Spec des Instruments „Wissen“ (SPEC_SHELL_WISSEN_v1 §4.3, W4): die vier Zustände und der Klick.
'use strict';
const assert = require('node:assert/strict');
globalThis.sedra = {registerTool(){}};
require('../../ui/dom.js');
const {anzeige, tool} = require('./tool.js');
const K = globalThis.specKit;
const checks = [];
function check(name, fn){ checks.push([name, fn]); }

check('vier Zustände: hybrid, Volltext, Vorschläge offen, aus; dazu nicht lesbar', ()=>{
  const el = K.container(), ctx = K.context(null, ()=>({}));
  tool.mount(el, ctx);
  tool.update({wissen: {value: 'hybrid · 85 %', hint: '120 Abschnitte aus 3 Quellen', tone: 'ok'}}, null);
  assert.match(el.textContent, /hybrid · 85 %/); assert.ok(el.classList.contains('ok'));
  tool.update({wissen: {value: 'nur Volltext', hint: '3 Abschnitte', tone: 'warn'}}, null);
  assert.ok(el.classList.contains('warn')); assert.ok(!el.classList.contains('ok'));
  tool.update({wissen: {value: 'hybrid · 100 %', hint: '2 Vorschläge warten', tone: 'warn'}}, null);
  assert.match(el.textContent, /2 Vorschläge warten/);
  tool.update({}, null);
  assert.match(el.textContent, /aus/); assert.ok(!el.classList.contains('warn'));
  tool.update(null, 'Keine Verbindung');
  assert.ok(el.classList.contains('bad'));
  el.onclick({stopPropagation(){}});
  assert.deepEqual(ctx.opened[0], {type: 'wissen', id: 'speicher', title: 'Wissen'});
  tool.unmount();
  assert.equal(el.childElementCount, 0);
});

check('anzeige ist rein', ()=>{
  assert.deepEqual(anzeige(null, null), {wert: 'aus', hinweis: 'Schalter „wissen“', ton: 'off'});
  assert.deepEqual(anzeige(undefined, null).wert, '…');
  assert.equal(anzeige({value: 'x'}, 'kaputt').ton, 'bad');
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
