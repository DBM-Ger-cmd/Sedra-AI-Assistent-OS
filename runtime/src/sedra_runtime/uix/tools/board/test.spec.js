// Spec des Werkzeugs im Schein-DOM (Spec 4, D4.4/D4.6): mounten in einen leeren Container, Ereignis senden, Text prüfen.
// `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`; tests/test_uix_shell_d_pure.py ruft sie so auf. Die Browserseite prüft uix_check.
'use strict';
const assert = require('node:assert/strict');
const tools = [];
globalThis.sedra = {registerTool: t=>tools.push(t)};
require('../../ui/dom.js');
require('./spalten.js');
require('./detail.js');
const {tool} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const BEREIT = {zustand: 'bereit', grund: '', takt: null};
const is = (id, title, zustand, bearbeiter, prioritaet, extra)=>Object.assign({type: 'issue', id, title, state: zustand, summary: '', actions: [], links: [],
  zustand, bearbeiter, prioritaet, blocker: [], kommentare: 0, eltern_id: null, mission_id: null, vorhaben_id: 'V-1', projekt_id: 'P-1', geaendert: '2026-10-21T08:00:00Z'}, extra || {});
const ISSUES = [is('UA-1', 'CSV-Export planen', 'erledigt', 'A-PL', 2, {kommentare: 2}), is('UA-2', 'CSV-Export bauen', 'in_arbeit', 'A-CO', 3, {eltern_id: 'UA-1', mission_id: 'M-7'}),
  is('UA-3', 'Export prüfen', 'wartet', 'A-RE', 2, {blocker: ['UA-2'], eltern_id: 'UA-1'}), is('UA-4', 'Doku', 'zugewiesen', 'A-PL', 1),
  is('UA-5', 'Altlasten', 'offen', null, 1), is('UA-6', 'Prototyp', 'abgebrochen', 'A-CO', 0)];
const AGENTS = {type: 'agent', items: [{id: 'A-PL', title: 'Planer'}, {id: 'A-CO', title: 'Coder'}, {id: 'A-RE', title: 'Reviewer'}], quelle: BEREIT};
const answer = (issues, extra)=>(path, body)=>{
  if(path === '/api/actions') return (extra && extra.action) || {status: 'done', needs_gate: false};
  if(body.type === 'agent') return AGENTS;
  if(body.id){ const hit = issues.find(i=>i.id === body.id); return hit || {type: 'issue', id: body.id, title: body.id, state: 'nicht gefunden', missing: true, actions: [], links: []}; }
  return Object.assign({type: 'issue', items: issues, quelle: BEREIT}, (extra && extra.liste) || {});
};
const ALLE = {type: 'issue', id: 'alle', title: 'Issues', collection: true};

async function mount(object, fn){
  const el = K.container(), ctx = K.context(object || ALLE, fn);
  await tool.mount(el, ctx);
  await K.settle();
  return {el, ctx};
}
const btn = (el, label)=>el.querySelectorAll('button').find(b=>b.textContent === label);

check('Liste: alle sechs, nach Zustand geordnet, Namen statt IDs', async()=>{
  const {el} = await mount(null, answer(ISSUES));
  const rows = el.querySelectorAll('tr').slice(1);
  assert.deepEqual(rows.map(r=>r.dataset.issue), ['UA-5', 'UA-4', 'UA-2', 'UA-3', 'UA-1', 'UA-6']);
  assert.deepEqual(rows[2].children.map(td=>td.textContent), ['CSV-Export bauen UA-2', 'In Arbeit', 'Coder', '3', '', '']);
  assert.match(rows[3].textContent, /⛔ UA-2/);
});

check('Board: sechs Spalten, erledigt und abgebrochen nur mit Zahl, aufklappbar', async()=>{
  const {el} = await mount(Object.assign({}, ALLE, {view: 'board'}), answer(ISSUES));
  const cols = el.querySelectorAll('.t-board-col');
  assert.deepEqual(cols.map(c=>c.dataset.state), ['offen', 'zugewiesen', 'in_arbeit', 'wartet', 'erledigt', 'abgebrochen']);
  assert.equal(cols[4].querySelectorAll('.t-board-card').length, 0);
  assert.match(cols[4].textContent, /Erledigt1/);
  await cols[4].querySelector('button').click();
  assert.equal(el.querySelector('section.t-board-col[data-state="erledigt"]').querySelectorAll('.t-board-card').length, 1);
});

check('Filter: Bearbeiter und Text schränken die Liste ein, ohne neu zu lesen', async()=>{
  const {el, ctx} = await mount(null, answer(ISSUES));
  const n = ctx.calls.length;
  const select = el.querySelector('select');
  select.value = 'A-CO'; select.onchange();
  assert.equal(el.querySelectorAll('tr').length - 1, 2);
  const text = el.querySelector('input'); text.value = 'bauen'; text.oninput();
  assert.deepEqual(el.querySelectorAll('tr').slice(1).map(r=>r.dataset.issue), ['UA-2']);
  assert.equal(ctx.calls.length, n);
});

check('kompakt (Dashboard): nur offene, ohne Werkzeugleiste', async()=>{
  const {el} = await mount(Object.assign({}, ALLE, {kompakt: true}), answer(ISSUES));
  assert.equal(el.querySelectorAll('tr').length - 1, 4);
  assert.equal(el.querySelectorAll('select').length, 0);
});

check('aus (unknown_object_type): Hinweis und der Weg zu den Missionen', async()=>{
  const {el, ctx} = await mount(null, (p, b)=>b.type === 'agent' ? AGENTS : new Error('unknown_object_type'));
  assert.match(el.textContent, /Orchestrierung ist ausgeschaltet/);
  await btn(el, 'Läufe (Missionen) ansehen').click();
  assert.deepEqual(ctx.opened[0], {type: 'task', id: 'alle', title: 'Läufe (Missionen)', collection: true});
});

check('ausgefallen und belegt', async()=>{
  let r = await mount(null, (p, b)=>b.type === 'agent' ? AGENTS : {type: 'issue', items: [], quelle: {zustand: 'fehler', grund: 'orchestra_db_error:locked'}});
  assert.match(r.el.textContent, /ausgefallen: orchestra_db_error:locked\./);
  r = await mount(null, (p, b)=>b.type === 'agent' ? AGENTS : new Error('orchestra_busy'));
  assert.match(r.el.textContent, /Datenbank ist gerade belegt/);
  assert.ok(btn(r.el, 'Noch einmal lesen'));
});

check('bereit und leer: Leerzustand mit dem Weg über den Unterarbeiter', async()=>{
  const {el} = await mount(null, answer([]));
  assert.match(el.textContent, /Noch keine Issues\. „Anlegen“ erzeugt/);
});

check('Einzelansicht: Kette, Blocker, Unteraufgaben, Lauf', async()=>{
  const {el, ctx} = await mount({type: 'issue', id: 'UA-3', title: 'Export prüfen'}, answer(ISSUES));
  assert.match(el.textContent, /Vorhaben V-1›Projekt P-1›CSV-Export planen›Export prüfen/);
  assert.match(el.textContent, /⛔ CSV-Export bauen \(UA-2\)/);
  const parent = await mount({type: 'issue', id: 'UA-1', title: 'Planen'}, answer(ISSUES));
  assert.match(parent.el.textContent, /UnteraufgabenCSV-Export bauen/);
  const lauf = await mount({type: 'issue', id: 'UA-2', title: 'Bauen'}, answer(ISSUES));
  await btn(lauf.el, 'Lauf ansehen').click();
  assert.deepEqual(lauf.ctx.opened[0], {type: 'task', id: 'M-7', title: 'Lauf M-7'});
  assert.deepEqual(ctx.calls.filter(c=>c.body && c.body.type === 'issue').map(c=>c.body), [{type: 'issue'}, {type: 'issue', id: 'UA-3'}]);
});

check('Einzelansicht eines gelöschten Issues', async()=>{
  const {el} = await mount({type: 'issue', id: 'UA-99', title: 'weg'}, answer(ISSUES));
  assert.match(el.textContent, /gibt es nicht \(mehr\)/);
});

check('Kommentieren: abgewiesen bleibt der Text, mit Erfolg wird das Feld leer', async()=>{
  const mit = ISSUES.map(i=>i.id === 'UA-2' ? Object.assign({}, i, {actions: [{verb: 'kommentieren', label: 'Kommentieren'}],
    kommentare: [{autor: 'Coder', autor_art: 'agent', text: 'Entwurf steht', ts: '2026-10-21T08:00:00Z', route: 'cloud', provider_id: 'anbieter-a', model: 'modell-x'}]}) : i);
  let fail = true;
  const {el, ctx} = await mount({type: 'issue', id: 'UA-2', title: 'Bauen'}, (p, b, n)=>p === '/api/actions' ? (fail ? new Error('text_required') : {status: 'done'}) : answer(mit)(p, b, n));
  assert.match(el.textContent, /Cloud · anbieter-a \/ modell-x/);
  el.querySelector('textarea').value = 'Bitte testen';
  await btn(el, 'Absenden').click(); await K.settle();
  assert.match(el.textContent, /text_required/);
  assert.equal(el.querySelector('textarea').value, 'Bitte testen');
  fail = false;
  await btn(el, 'Absenden').click(); await K.settle();
  assert.deepEqual(ctx.calls.filter(c=>c.path === '/api/actions').map(c=>c.body.args), [{text: 'Bitte testen'}, {text: 'Bitte testen'}]);
  assert.equal(el.querySelector('textarea').value, '');
  assert.match(el.textContent, /Kommentieren: Erledigt\./);
});

check('Verben: anlegen am Typ, abbrechen mit Bestätigung als Antrag', async()=>{
  const liste = await mount(null, answer(ISSUES, {liste: {actions: [{verb: 'anlegen', label: 'Anlegen'}]}}));
  assert.deepEqual(tool.actions().map(a=>a.label), ['Anlegen']);
  const mit = ISSUES.map(i=>i.id === 'UA-4' ? Object.assign({}, i, {actions: [{verb: 'abbrechen', label: 'Abbrechen', needs_gate: true}, {verb: 'zuweisen', label: 'Zuweisen'}]}) : i);
  const {el, ctx} = await mount({type: 'issue', id: 'UA-4', title: 'Doku'}, answer(mit, {action: {status: 'done', needs_gate: true}}));
  assert.deepEqual(tool.actions().map(a=>a.label), ['Abbrechen'], 'zuweisen hat ein Formular im Kopf, nicht in der Kopfzeile');
  await tool.actions()[0].run(); await K.settle();
  assert.deepEqual(ctx.calls.find(c=>c.path === '/api/actions').body, {type: 'issue', id: 'UA-4', verb: 'abbrechen', args: {}});
  assert.match(el.textContent, /Abbrechen: Antrag liegt im Posteingang\./);
  assert.ok(liste.el);
});

check('Ereignisflut: zehn issue.changed, höchstens zwei weitere Lesungen', async()=>{
  const {ctx} = await mount(null, answer(ISSUES));
  const n = ctx.calls.filter(c=>c.body && c.body.type === 'issue').length;
  for(let i = 0; i < 10; i++) ctx.bus.emit('issue.changed', {id: 'UA-' + i});
  await K.settle();
  assert.ok(ctx.calls.filter(c=>c.body && c.body.type === 'issue').length - n <= 2);
});

check('Karte öffnet das Issue; unmount leert den Container', async()=>{
  const {el, ctx} = await mount(null, answer(ISSUES));
  el.querySelector('tr[data-issue="UA-4"]').click();
  assert.deepEqual(ctx.opened[0], {type: 'issue', id: 'UA-4', title: 'Doku'});
  tool.unmount(el);
  assert.equal(el.children.length, 0);
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
