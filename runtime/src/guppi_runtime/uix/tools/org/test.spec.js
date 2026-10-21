// Spec des Werkzeugs im Schein-DOM (Spec 4, D4.4/D4.6): mounten in einen leeren Container, Ereignis senden, Text prüfen.
// `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`; tests/test_uix_shell_d_pure.py ruft sie so auf. Die Browserseite prüft uix_check.
'use strict';
const assert = require('node:assert/strict');
const tools = [];
globalThis.sedra = {registerTool: t=>tools.push(t)};
require('../../ui/dom.js');
require('./baum.js');
const {tool} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const BEREIT = {zustand: 'bereit', grund: '', takt: null};
const budget = (prozent, stufe)=>({grenze_token: 200000, verbraucht_token: prozent * 2000, grenze_eur_cent: null, verbraucht_eur_cent: null, prozent, stufe});
const ag = (id, title, rolle, boss, extra)=>Object.assign({type: 'agent', id, title, state: 'aktiv', summary: '', actions: [], links: [],
  rolle, reports_to: boss, status: 'aktiv', arbeitet: false, budget: budget(10, 'ok'), offene_entscheidungen: 0}, extra || {});
const TEAM = [ag('A-UA', 'Unterarbeiter', 'unterarbeiter', null, {arbeitet: true}), ag('A-PL', 'Planer', 'planer', 'A-UA', {budget: budget(80, 'warnung')}),
  ag('A-CO', 'Coder', 'coder', 'A-UA', {offene_entscheidungen: 1}), ag('A-RE', 'Reviewer', 'reviewer', 'A-UA', {status: 'pausiert', state: 'pausiert'})];
const liste = (items, quelle)=>({type: 'agent', items, quelle});

async function mount(object, answer){
  const el = K.container(), ctx = K.context(object || {type: 'agent', id: 'alle', collection: true}, answer);
  await tool.mount(el, ctx);
  await K.settle();
  return {el, ctx};
}
const text = el=>el.textContent;
const ORG = (path)=>path === '/api/objects' ? liste(TEAM, BEREIT) : {status: 'done', needs_gate: false};

check('Baum: Captain, vier Karten, Badge und Budgetstufe mit Prozent als Text', async()=>{
  const {el, ctx} = await mount(null, ORG);
  assert.deepEqual(ctx.calls.map(c=>[c.path, c.body]), [['/api/objects', {type: 'agent'}]]);
  assert.equal(el.querySelectorAll('.t-org-card').length, 5);
  assert.match(text(el), /Captain/);
  assert.equal(el.querySelector('div.t-org-card[data-agent="A-CO"]').querySelector('.t-org-badge').textContent, '1');
  const pl = el.querySelector('div.t-org-card[data-agent="A-PL"]');
  assert.ok(pl.querySelector('.t-org-budget.warnung'));
  assert.match(text(pl), /80 % · 160\.000 \/ 200\.000 Token · warnung/);
  assert.match(text(el.querySelector('div.t-org-card[data-agent="A-UA"]')), /arbeitet/);
  assert.equal(el.querySelectorAll('.t-org-more').length, 0, 'keine Verben ohne actions');
});

check('ohne quelle (alter Server, Platzhalter): ausgeschaltet, Knopf zum Maschinenraum', async()=>{
  const {el, ctx} = await mount(null, ()=>({type: 'agent', items: []}));
  assert.match(text(el), /Orchestrierung ist ausgeschaltet/);
  await el.querySelector('button').click();
  assert.deepEqual(ctx.opened, [{type: 'machine', id: 'machine', title: 'Maschinenraum'}]);
});

check('ausgefallen: der Grund steht da', async()=>{
  const {el} = await mount(null, ()=>liste([], {zustand: 'fehler', grund: 'orchestra_config_invalid:budget'}));
  assert.match(text(el), /ausgefallen: orchestra_config_invalid:budget\./);
});

check('Datenbank belegt: rote Zeile und „Noch einmal lesen“ liest neu', async()=>{
  let n = 0;
  const {el, ctx} = await mount(null, ()=>(++n === 1 ? new Error('orchestra_busy') : liste(TEAM, BEREIT)));
  assert.match(text(el), /Datenbank ist gerade belegt/);
  await el.querySelector('button').click(); await K.settle();
  assert.equal(ctx.calls.length, 2);
  assert.equal(el.querySelectorAll('.t-org-card').length, 5);
});

check('bereit und leer: der Leerzustand des Werkzeugs', async()=>{
  const {el} = await mount(null, ()=>liste([], BEREIT));
  assert.match(text(el), /Noch keine Agenten/);
});

check('Ereignisflut: zehn Ereignisse, höchstens zwei Lesungen', async()=>{
  const {ctx} = await mount(null, ORG);
  for(let i = 0; i < 10; i++) ctx.bus.emit('agent.changed', {id: 'A-CO'});
  ctx.bus.emit('desk.resync');
  await K.settle();
  assert.ok(ctx.calls.length <= 3, ctx.calls.length + ' Lesungen');
});

check('Liste und Umschalter: der Wechsel geht als object.open mit view an die Shell', async()=>{
  const {el, ctx} = await mount({type: 'agent', id: 'alle', collection: true, view: 'liste'}, ORG);
  assert.equal(el.querySelectorAll('tr').length, 5);
  assert.deepEqual(el.querySelectorAll('tr')[1].children.map(td=>td.textContent), ['Coder', 'coder', 'Unterarbeiter', 'aktiv', '10 %', '1']);
  const baum = el.querySelectorAll('button').find(b=>b.textContent === 'Baum');
  await baum.click();
  assert.equal(ctx.opened[0].view, 'baum');
});

check('Karte öffnet das Agentenfenster', async()=>{
  const {el, ctx} = await mount(null, ORG);
  el.querySelector('div.t-org-card[data-agent="A-PL"]').click();
  assert.deepEqual(ctx.opened, [{type: 'agent', id: 'A-PL', title: 'Planer'}]);
});

check('Verb mit Gate: Antrag liegt im Posteingang, die Anzeige ändert sich nicht selbst', async()=>{
  const team = TEAM.map(a=>a.id === 'A-CO' ? Object.assign({}, a, {actions: [{verb: 'pausieren', label: 'Pausieren', needs_gate: true}]}) : a);
  const {el, ctx} = await mount(null, p=>p === '/api/objects' ? liste(team, BEREIT) : {status: 'done', needs_gate: true});
  await el.querySelectorAll('button').find(b=>b.textContent === 'Pausieren').click(); await K.settle();
  assert.deepEqual(ctx.calls[1], {path: '/api/actions', body: {type: 'agent', id: 'A-CO', verb: 'pausieren', args: {}}});
  assert.match(text(el), /Pausieren: Antrag liegt im Posteingang\./);
  assert.equal(ctx.calls.length, 2, 'nicht selbst neu gelesen – das macht agent.changed');
});

check('Verb abgewiesen: Satz des Servers, das Formular bleibt stehen', async()=>{
  const team = TEAM.map(a=>a.id === 'A-RE' ? Object.assign({}, a, {actions: [{verb: 'einordnen', label: 'Einordnen'}]}) : a);
  const {el, ctx} = await mount(null, p=>p === '/api/objects' ? liste(team, BEREIT) : new Error('delegation_not_allowed'));
  await el.querySelectorAll('button').find(b=>b.textContent === 'Einordnen').click();
  const select = el.querySelector('select');
  assert.equal(select.children.length, 4, 'Captain und drei andere, nicht er selbst');
  select.value = 'A-CO';
  await el.querySelectorAll('button').find(b=>b.textContent === 'Absenden').click(); await K.settle();
  assert.deepEqual(ctx.calls[1].body, {type: 'agent', id: 'A-RE', verb: 'einordnen', args: {reports_to: 'A-CO'}});
  assert.match(text(el), /delegation_not_allowed/);
  assert.ok(el.querySelector('form'), 'Eingabe bleibt stehen');
});

check('Verben am Typ nur aus der Liste des Servers', async()=>{
  await mount(null, ORG);
  assert.deepEqual(tool.actions(), []);
  await mount(null, ()=>Object.assign(liste(TEAM, BEREIT), {actions: [{verb: 'einstellen', label: 'Einstellen'}]}));
  assert.deepEqual(tool.actions().map(a=>a.label), ['Einstellen']);
});

check('kompakt (Dashboard): eine Zeile je Agent, eingerückt nach Ebene', async()=>{
  const {el} = await mount({type: 'agent', id: 'alle', collection: true, kompakt: true}, ORG);
  const rows = el.querySelectorAll('.t-org-line-row');
  assert.equal(rows.length, 4);
  assert.deepEqual(rows.map(r=>r.style.paddingLeft), ['0px', '16px', '16px', '16px']);
  assert.equal(el.querySelectorAll('button').length, 0, 'kein Umschalter auf der Karte');
});

check('unmount hinterlässt den Container leer', async()=>{
  const {el} = await mount(null, ORG);
  tool.unmount(el);
  assert.equal(el.children.length, 0);
  assert.ok(!el.classList.contains('t-org'));
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
