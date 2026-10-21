// Spec des Nachweises „Kosten“ neben einem Issue (Spec 4, D4.2.8) im Schein-DOM. Die Mission-Ansicht prüfen uix_check und test_uix_contract.
// `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`; tests/test_uix_shell_d_pure.py ruft sie so auf.
'use strict';
const assert = require('node:assert/strict');
globalThis.sedra = {registerTool(){}};
require('../../ui/dom.js');
const {tool, cloudText, budgetText} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const COST = {tokens: 12000, attempts: 2, quellen: ['provider'], input_tokens: 9000, output_tokens: 3000, route: 'cloud', provider: 'anbieter-a', model: 'modell-x'};
const answer = (issue, budget)=>(path, body)=>{
  if(path === '/api/cost') return COST;
  if(body.type === 'issue') return issue instanceof Error ? issue : issue;
  if(body.type === 'budget') return budget;
  return new Error('unerwartet');
};
async function mount(object, fn){
  const el = K.container(), ctx = K.context(object, fn);
  await tool.mount(el, ctx);
  await K.settle();
  return {el, ctx};
}
const ISSUE = {type: 'issue', id: 'UA-2', title: 'Bauen', bearbeiter: 'A-CO', mission_id: 'M-7', actions: [], links: []};

check('Issue: Budget des Bearbeiters mit Prozent, Token des Laufs, Cloud-Kennzeichen', async()=>{
  const b = {prozent: 55, verbraucht_token: 110000, grenze_token: 200000, grenze_eur_cent: null, verbraucht_eur_cent: null, stufe: 'ok'};
  const {el, ctx} = await mount({type: 'issue', id: 'UA-2'}, answer(ISSUE, b));
  assert.deepEqual(ctx.calls.map(c=>[c.path, c.body]), [['/api/objects', {type: 'issue', id: 'UA-2'}], ['/api/objects', {type: 'budget', id: 'A-CO'}], ['/api/cost', {task_id: 'M-7'}]]);
  assert.match(el.textContent, /55 % · 110\.000 \/ 200\.000 Token/);
  assert.doesNotMatch(el.textContent, /€/, 'ohne Euro-Daten kein „0 €“');
  assert.match(el.textContent, /12\.000 Token · 2 Aufrufe im Lauf M-7/);
  assert.match(el.textContent, /Cloud · anbieter-a \/ modell-x/);
});

check('Issue ohne Bearbeiter und ohne Lauf', async()=>{
  const {el, ctx} = await mount({type: 'issue', id: 'UA-5'}, answer({type: 'issue', id: 'UA-5', actions: [], links: []}));
  assert.match(el.textContent, /Noch niemand zugewiesen – kein Budget\./);
  assert.match(el.textContent, /Noch kein Lauf/);
  assert.equal(ctx.calls.length, 1);
});

check('Budget nicht lesbar (Typ fehlt): noch keine Daten, keine Zahl', async()=>{
  const {el} = await mount({type: 'issue', id: 'UA-2'}, answer(ISSUE, new Error('unknown_object_type')));
  assert.match(el.textContent, /Budget von A-CO: noch keine Daten\./);
});

check('ohne Desk-Typ issue: der Nachweis sagt, dass es das erst mit der Orchestrierung gibt', async()=>{
  const {el} = await mount({type: 'issue', id: 'UA-2'}, answer(new Error('unknown_object_type')));
  assert.match(el.textContent, /gibt es mit der Orchestrierung/);
});

check('budget.warning des Bearbeiters liest neu, eines anderen nicht', async()=>{
  const {ctx} = await mount({type: 'issue', id: 'UA-2'}, answer(ISSUE, {state: 'Warnung', summary: 'Token 170000/200000'}));
  const n = ctx.calls.length;
  ctx.bus.emit('budget.warning', {agent_id: 'A-PL', prozent: 90, stufe: 'warnung'}); await K.settle();
  assert.equal(ctx.calls.length, n);
  ctx.bus.emit('budget.warning', {agent_id: 'A-CO', prozent: 90, stufe: 'warnung'}); await K.settle();
  assert.ok(ctx.calls.length > n);
});

check('reine Sätze: Cloud nur bei route cloud; Budget aus dem Desk-Satz', ()=>{
  assert.equal(cloudText({route: 'lokal'}), null);
  assert.equal(cloudText({}), null);
  assert.equal(budgetText({state: 'Warnung', summary: 'Token 170000/200000'}).stufe, 'warnung');
  assert.equal(budgetText({}), null);
});

check('Mission: Kennzeichen am Lauf aus der Cloud', async()=>{
  const {el} = await mount({type: 'task', id: 'M-7'}, ()=>COST);
  assert.match(el.textContent, /Cloud · anbieter-a \/ modell-x/);
  const lokal = await mount({type: 'task', id: 'M-8'}, ()=>Object.assign({}, COST, {route: 'lokal'}));
  assert.doesNotMatch(lokal.el.textContent, /Cloud/);
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
