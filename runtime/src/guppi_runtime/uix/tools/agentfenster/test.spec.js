// Spec des Werkzeugs im Schein-DOM (Spec 4, D4.4/D4.6): zwei Fenster zugleich, Ereignis senden, Text prüfen.
// `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`; tests/test_uix_shell_d_pure.py ruft sie so auf. Die Browserseite prüft uix_check.
'use strict';
const assert = require('node:assert/strict');
globalThis.sedra = {registerTool(){}};
require('../../ui/dom.js');
require('./verlauf.js');
const {tool} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const TS = '2026-10-21T08:00:00Z';
const budget = (prozent, stufe)=>({grenze_token: 200000, verbraucht_token: prozent * 2000, grenze_eur_cent: null, verbraucht_eur_cent: null, prozent, stufe});
const ag = (id, title, rolle, boss, extra)=>Object.assign({type: 'agent', id, title, state: 'aktiv', summary: '', actions: [], links: [], rolle, reports_to: boss,
  status: 'aktiv', arbeitet: false, budget: budget(35, 'ok'), offene_entscheidungen: 0}, extra || {});
const ANWEISEN = {verb: 'anweisen', label: 'Senden'};
const AGENTS = {'A-UA': ag('A-UA', 'Unterarbeiter', 'unterarbeiter', null, {arbeitet: true, actions: [ANWEISEN, {verb: 'pausieren', label: 'Pausieren', needs_gate: false}]}),
  'A-CO': ag('A-CO', 'Coder', 'coder', 'A-UA', {offene_entscheidungen: 1, budget: budget(55, 'ok')}),
  'A-RE': ag('A-RE', 'Reviewer', 'reviewer', 'A-UA', {status: 'pausiert', state: 'pausiert', actions: [ANWEISEN]}),
  'A-PL': ag('A-PL', 'Planer', 'planer', 'A-UA', {budget: budget(100, 'gestoppt')})};
const msg = (id, agent, rolle, text, state, extra)=>Object.assign({type: 'gespraech', id, title: text, state, summary: text, actions: [], links: [],
  agent_id: agent, rolle, ts: TS, issue_id: null, mission_id: null, route: 'lokal', provider_id: null, model: null}, extra || {});
const MESSAGES = [msg(1, 'A-UA', 'captain', 'Bau den CSV-Export.', 'angenommen', {issue_id: 'UA-1'}), msg(2, 'A-UA', 'agent', 'Drei Issues angelegt.', 'beantwortet'),
  msg(3, 'A-UA', 'captain', 'Wie weit?', 'wartet_freigabe'), msg(4, 'A-CO', 'captain', 'Nimm UA-2 zuerst.', 'angenommen', {issue_id: 'UA-2'}),
  msg(5, 'A-CO', 'agent', 'Erster Entwurf steht.', 'beantwortet', {route: 'cloud', provider_id: 'anbieter-a', model: 'modell-x'})];
const ISSUES = [{type: 'issue', id: 'UA-1', title: 'CSV planen', zustand: 'erledigt', bearbeiter: 'A-PL'}, {type: 'issue', id: 'UA-2', title: 'CSV bauen', zustand: 'in_arbeit', bearbeiter: 'A-CO', eltern_id: 'UA-1', mission_id: 'M-7'},
  {type: 'issue', id: 'UA-3', title: 'Export prüfen', zustand: 'wartet', bearbeiter: 'A-RE', eltern_id: 'UA-1'}];

function server(over){
  const o = over || {};
  return (path, body, n)=>{
    if(path === '/api/actions') return o.action ? o.action(body, n) : {status: 'done', needs_gate: false};
    if(body.type === 'agent') return o.agent ? o.agent(body) : (AGENTS[body.id] || {type: 'agent', id: body.id, title: body.id, state: 'nicht gefunden', missing: true, actions: [], links: []});
    if(body.type === 'issue') return {type: 'issue', items: ISSUES, quelle: {zustand: 'bereit'}};
    if(body.type === 'gespraech') return o.gespraech ? o.gespraech(body) : {type: 'gespraech', items: MESSAGES.filter(m=>m.agent_id === body.agent), mehr: false, quelle: {zustand: 'bereit'}};
    return new Error('unerwartet');
  };
}
async function mount(id, fn){
  const el = K.container(), ctx = K.context({type: 'agent', id, title: id}, fn || server());
  await tool.mount(el, ctx);
  await K.settle();
  return {el, ctx};
}
const btn = (el, label)=>el.querySelectorAll('button').find(b=>b.textContent === label);

check('zwei Fenster zugleich, jedes mit seinem eigenen Verlauf', async()=>{
  const a = await mount('A-UA'), b = await mount('A-CO');
  assert.deepEqual(a.el.querySelectorAll('.t-af-msg').map(x=>x.dataset.msg), ['1', '2', '3']);
  assert.deepEqual(b.el.querySelectorAll('.t-af-msg').map(x=>x.dataset.msg), ['4', '5']);
  assert.equal(tool.instanzen.size >= 2, true);
  assert.deepEqual(a.ctx.calls.find(c=>c.body.type === 'gespraech').body, {type: 'gespraech', agent: 'A-UA', limit: 50});
  tool.unmount(a.el);
  assert.equal(a.el.children.length, 0);
  assert.equal(b.el.querySelectorAll('.t-af-msg').length, 2, 'das andere Fenster bleibt');
  tool.unmount(b.el);
});

check('Status unter der Nachricht, Tagestrenner, Cloud nur an der Cloud-Antwort', async()=>{
  const a = await mount('A-UA'), b = await mount('A-CO');
  assert.match(a.el.textContent, /21\.10\.2026/);
  assert.match(a.el.textContent, /angekommen – Issue UA-1 angelegt/);
  assert.match(a.el.textContent, /wartet auf Freigabe im Posteingang/);
  assert.equal(a.el.querySelectorAll('.t-af-cloud').length, 0);
  assert.deepEqual(b.el.querySelectorAll('.t-af-cloud').map(x=>x.textContent), ['Cloud · anbieter-a / modell-x']);
  [a, b].forEach(x=>tool.unmount(x.el));
});

check('Kopf: Budget mit Prozent, Badge mit Weg zum Posteingang; Unterarbeiter und Teilaufgaben', async()=>{
  const co = await mount('A-CO');
  assert.match(co.el.textContent, /Budget 55 % · 110\.000 \/ 200\.000 Token/);
  await btn(co.el, 'Im Posteingang').click();
  assert.deepEqual(co.ctx.opened[0], {type: 'decision', id: 'alle', title: 'Posteingang', collection: true});
  const ua = await mount('A-UA');
  assert.match(ua.el.textContent, /nimmt Anweisungen an und verteilt sie/);
  assert.match(ua.el.textContent, /Teilaufgaben der letzten Anweisung:CSV bauen \(UA-2\)Export prüfen \(UA-3\)/);
  [co, ua].forEach(x=>tool.unmount(x.el));
});

check('Eingabe nur mit anweisen; Coder ohne Verb hat keine', async()=>{
  const co = await mount('A-CO'), ua = await mount('A-UA');
  assert.equal(co.el.querySelector('textarea'), null);
  assert.ok(ua.el.querySelector('textarea'));
  assert.deepEqual(tool.actions(ua.el).map(a=>a.label), ['Pausieren'], 'anweisen ist die Eingabe, nicht ein Knopf im Kopf');
  assert.deepEqual(tool.actions(co.el), []);
  [co, ua].forEach(x=>tool.unmount(x.el));
});

check('Anweisung: abgewiesen bleibt der Text, die Wiederholung trägt denselben Schlüssel', async()=>{
  let fail = true;
  const ua = await mount('A-UA', server({action: ()=>fail ? new Error('text_too_long') : {status: 'done', needs_gate: false}}));
  ua.el.querySelector('textarea').value = 'Bau den Export';
  await btn(ua.el, 'Senden').click(); await K.settle();
  assert.match(ua.el.textContent, /text_too_long/);
  assert.equal(ua.el.querySelector('textarea').value, 'Bau den Export');
  fail = false;
  await btn(ua.el, 'Senden').click(); await K.settle();
  const sent = ua.ctx.calls.filter(c=>c.path === '/api/actions').map(c=>c.body);
  assert.equal(sent.length, 2);
  assert.deepEqual([sent[0].verb, sent[0].args.text], ['anweisen', 'Bau den Export']);
  assert.equal(sent[0].args.key, sent[1].args.key, 'dieselbe Anweisung, derselbe Schlüssel');
  assert.equal(ua.el.querySelector('textarea').value, '');
  ua.el.querySelector('textarea').value = 'Nächste Sache';
  await btn(ua.el, 'Senden').click(); await K.settle();
  const third = ua.ctx.calls.filter(c=>c.path === '/api/actions')[2].body;
  assert.notEqual(third.args.key, sent[1].args.key, 'eine neue Anweisung, ein neuer Schlüssel');
  tool.unmount(ua.el);
});

check('leere Anweisung geht nicht hinaus', async()=>{
  const ua = await mount('A-UA');
  await btn(ua.el, 'Senden').click(); await K.settle();
  assert.equal(ua.ctx.calls.filter(c=>c.path === '/api/actions').length, 0);
  assert.match(ua.el.textContent, /leere Anweisung/);
  tool.unmount(ua.el);
});

check('pausiert, Budget gestoppt, unbekannt', async()=>{
  const re = await mount('A-RE'), pl = await mount('A-PL'), weg = await mount('A-WEG');
  assert.match(re.el.textContent, /pausiert – die Anweisung wartet bis zum Fortsetzen/);
  assert.ok(re.el.querySelector('textarea'), 'die Eingabe bleibt beim pausierten Agenten');
  assert.match(pl.el.textContent, /Budget aufgebraucht – Entscheidung im Posteingang/);
  assert.match(weg.el.textContent, /Diesen Agenten gibt es nicht mehr/);
  [re, pl, weg].forEach(x=>tool.unmount(x.el));
});

check('Orchestrierung aus, gespraech fehlt, leer, nicht lesbar', async()=>{
  const aus = await mount('A-UA', server({agent: ()=>new Error('unknown_object_type')}));
  assert.match(aus.el.textContent, /Orchestrierung ist ausgeschaltet/);
  const ohne = await mount('A-UA', server({gespraech: ()=>new Error('unknown_object_type')}));
  assert.match(ohne.el.textContent, /Gespräche gibt es mit der Orchestrierung\./);
  assert.match(ohne.el.textContent, /CSV planen|Keine Issues/);
  const leer = await mount('A-PL', server({gespraech: ()=>({type: 'gespraech', items: [], mehr: false})}));
  assert.match(leer.el.textContent, /Noch nichts gesagt\. Eine Anweisung wird zur Aufgabe\./);
  const kaputt = await mount('A-UA', server({gespraech: ()=>new Error('orchestra_db_error:locked')}));
  assert.ok(btn(kaputt.el, 'Noch einmal lesen'));
  [aus, ohne, leer, kaputt].forEach(x=>tool.unmount(x.el));
});

check('Ältere laden mit vor; die Seite davor kommt vor die Nachrichten', async()=>{
  const ua = await mount('A-UA', server({gespraech: b=>b.vor ? {items: [msg(0, 'A-UA', 'captain', 'Früher', 'beantwortet')], mehr: false}
                                                           : {items: MESSAGES.slice(0, 3), mehr: true}}));
  await btn(ua.el, 'Ältere laden').click(); await K.settle();
  assert.deepEqual(ua.ctx.calls.filter(c=>c.body && c.body.vor !== undefined).map(c=>c.body), [{type: 'gespraech', agent: 'A-UA', vor: 1, limit: 50}]);
  assert.deepEqual(ua.el.querySelectorAll('.t-af-msg').map(x=>x.dataset.msg), ['0', '1', '2', '3']);
  assert.equal(btn(ua.el, 'Ältere laden'), undefined);
  tool.unmount(ua.el);
});

check('Ereignisse: nur der eigene Agent liest neu; zehn auf einmal höchstens zweimal', async()=>{
  const ua = await mount('A-UA'), co = await mount('A-CO');
  const reads = x=>x.ctx.calls.filter(c=>c.body && c.body.type === 'agent').length;
  const [a0, c0] = [reads(ua), reads(co)];
  for(let i = 0; i < 10; i++) ua.ctx.bus.emit('agent.changed', {id: 'A-UA'});
  co.ctx.bus.emit('agent.changed', {id: 'A-UA'});
  co.ctx.bus.emit('budget.warning', {agent_id: 'A-UA', prozent: 90, stufe: 'warnung'});
  await K.settle();
  assert.ok(reads(ua) - a0 >= 1 && reads(ua) - a0 <= 2);
  assert.equal(reads(co), c0, 'das Fenster des Coders bleibt still');
  [ua, co].forEach(x=>tool.unmount(x.el));
});

check('Verb im Kopf mit Gate: Antrag liegt im Posteingang', async()=>{
  const ua = await mount('A-UA', server({action: ()=>({status: 'done', needs_gate: true})}));
  await tool.actions(ua.el)[0].run(); await K.settle();
  assert.deepEqual(ua.ctx.calls.find(c=>c.path === '/api/actions').body, {type: 'agent', id: 'A-UA', verb: 'pausieren', args: {}});
  assert.match(ua.el.textContent, /Pausieren: Antrag liegt im Posteingang\./);
  tool.unmount(ua.el);
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
