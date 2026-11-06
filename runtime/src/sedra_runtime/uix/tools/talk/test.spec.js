// Spec des Gesprächs (Teile aus Stufe 4–6) im Schein-DOM: `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`.
// tests/test_uix_stufe6.py ruft sie so auf. „Leeren“ mit Rückfrage, was in einen Cloud-Weg darf, der Körper für /api/chat/reply.
'use strict';
const assert = require('node:assert/strict');
require('../../ui/dom.js');
require('./verlauf.js');
const V = globalThis.sedraTalkVerlauf;
const checks = [];
function check(name, fn){ checks.push([name, fn]); }

check('„Leeren“: ein Klick fragt, der zweite leert; Warten und Esc brechen ab', async()=>{
  const calls = [], said = [];
  const tool = {history: [{role: 'user', content: 'x'}], log: null, say: t=>said.push(t), ctx: {api: async(p)=>{ calls.push(p); return {}; }}};
  let timer = null;
  const uhr = {setTimeout: f=>{ timer = f; return 1; }, clearTimeout: ()=>{ timer = null; }};
  const b = V.leerKnopf(tool, uhr);
  assert.equal(b.type, 'button');
  await b.onclick({});
  assert.equal(b.textContent, 'Wirklich leeren?'); assert.ok(b.classList.contains('scharf')); assert.deepEqual(calls, []);
  timer();                                                     // 4 s vorbei
  assert.equal(b.textContent, 'Leeren'); assert.deepEqual(calls, []);
  await b.onclick({}); b.onkeydown({key: 'Escape'});
  assert.equal(b.textContent, 'Leeren'); assert.deepEqual(calls, []);
  await b.onclick({}); await b.onclick({});
  assert.deepEqual(calls, ['/api/chat/verlauf/leeren']); assert.deepEqual(tool.history, []);
  assert.equal(b.textContent, 'Leeren');
});

check('Cloud-Weg: nie eine Antwort mit Personenbezug aus dem Wissen, nur Rolle und Inhalt', ()=>{
  const h = [{role: 'user', content: 'a'}, {role: 'assistant', content: 'Lena', nurLokal: true}, {role: 'user', content: 'b', extra: 1}];
  assert.deepEqual(V.fuerCloud(h), [{role: 'user', content: 'a'}, {role: 'user', content: 'b'}]);
  assert.deepEqual(V.alsHistory([{rolle: 'assistant', text: 'x', nur_lokal: 'ja'}]), [{role: 'assistant', content: 'x', nurLokal: true}]);
});

check('Körper für /api/chat/reply: wissen nur, wenn die Shell es einschaltet', ()=>{
  const tool = {mission: 'M-1', history: [{role: 'user', content: 'a', nurLokal: true}, {role: 'user', content: 'jetzt'}], ctx: {shell: {}}};
  assert.deepEqual(V.antwortKoerper(tool, 'jetzt'), {mission_id: 'M-1', text: 'jetzt', history: [{role: 'user', content: 'a'}], attachments: [], vorgang: ''});
  tool.ctx.shell.wissen = true;
  assert.equal(V.antwortKoerper(tool, 'jetzt').wissen, true);
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
