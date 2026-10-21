// Spec des Werkzeugs im Schein-DOM (Spec 4, D4.4/D4.6): mounten in einen leeren Container, Ereignis senden, Text prüfen.
// `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`; tests/test_uix_shell_d_pure.py ruft sie so auf. Die Browserseite prüft uix_check.
'use strict';
const assert = require('node:assert/strict');
globalThis.sedra = {registerTool(){}};
require('../../ui/dom.js');
require('./cron.js');
const {tool, taktSatz} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const TS = '2026-10-21T08:00:00Z';
const BEREIT = {zustand: 'bereit', grund: '', takt: {zustand: 'läuft', letzter: TS}};
const R1 = {type: 'routine', id: 'R-1', title: 'Morgendlicher Bericht', state: 'an', summary: '', actions: [], links: [], agent_id: 'A-UA', cron: '30 6 * * *',
  zeitzone: 'Europe/Berlin', nachholen: 'auslassen', enabled: true, letzter_lauf: {termin: TS, ausgang: 'erzeugt', issue_id: 'UA-1'}, next_run: '2026-10-22T04:30:00Z',
  vorlage: {titel: 'Bericht', beschreibung: 'Was gestern geschah'}, laeufe: [{termin: TS, ausgang: 'erzeugt', issue_id: 'UA-1'}]};
const R2 = {type: 'routine', id: 'R-2', title: 'Wochenreview', state: 'aus', summary: '', actions: [], links: [], agent_id: 'A-RE', cron: '0 9 * * 1',
  zeitzone: 'Europe/Berlin', nachholen: 'nachholen', enabled: false, letzter_lauf: null, next_run: null};
const AGENTS = {type: 'agent', items: [{id: 'A-UA', title: 'Unterarbeiter', status: 'aktiv'}, {id: 'A-RE', title: 'Reviewer', status: 'pausiert'}]};
const answer = (routines, extra)=>(path, body)=>{
  if(path === '/api/actions') return (extra && extra.action) instanceof Function ? extra.action(body) : (extra && extra.action) || {status: 'done', needs_gate: true};
  if(body.type === 'agent') return AGENTS;
  if(body.id) return routines.find(r=>r.id === body.id) || {type: 'routine', id: body.id, title: body.id, state: 'nicht gefunden', missing: true, actions: [], links: []};
  return Object.assign({type: 'routine', items: routines, quelle: BEREIT}, (extra && extra.liste) || {});
};
const ALLE = {type: 'routine', id: 'alle', title: 'Routinen', collection: true};
async function mount(object, fn){
  const el = K.container(), ctx = K.context(object || ALLE, fn);
  await tool.mount(el, ctx);
  await K.settle();
  return {el, ctx};
}
const btn = (el, label)=>el.querySelectorAll('button').find(b=>b.textContent === label);

check('Tabelle: Zeitplan in Worten, Nachholen, an/aus, Agent pausiert', async()=>{
  const {el} = await mount(null, answer([R1, R2]));
  const rows = el.querySelectorAll('tr').slice(1);
  assert.deepEqual(rows.map(r=>r.dataset.routine), ['R-1', 'R-2']);
  assert.match(rows[0].textContent, /jeden Tag um 06:30 Uhr \(Europe\/Berlin\)/);
  assert.match(rows[0].textContent, /verpasste auslassen/);
  assert.match(rows[0].textContent, /Aufgabe erzeugt/);
  assert.match(rows[1].textContent, /Agent pausiert – es entstehen keine Aufgaben/);
  assert.match(rows[1].textContent, /montags um 09:00 Uhr/);
  assert.match(rows[1].textContent, /noch nie/);
});

check('Takt: läuft, aus, unbekannt', async()=>{
  const {el} = await mount(null, answer([R1]));
  assert.match(el.querySelector('.t-routines-takt').textContent, /^Takt läuft/);
  assert.match(taktSatz({takt: {zustand: 'aus'}}).text, /Routinen laufen nur, solange die Oberfläche läuft/);
  assert.match(taktSatz({}).text, /Takt unbekannt/);
});

check('ein unbekannter Ausdruck steht unverändert da', async()=>{
  const {el} = await mount(null, answer([Object.assign({}, R1, {cron: '@daily'})]));
  assert.match(el.textContent, /@daily \(Europe\/Berlin\)/);
});

check('aus, ausgefallen, belegt, leer', async()=>{
  let r = await mount(null, ()=>({type: 'routine', items: []}));
  assert.match(r.el.textContent, /Orchestrierung ist ausgeschaltet/);
  r = await mount(null, (p, b)=>b.type === 'agent' ? AGENTS : {type: 'routine', items: [], quelle: {zustand: 'fehler', grund: 'orchestra_config_invalid:routine'}});
  assert.match(r.el.textContent, /ausgefallen: orchestra_config_invalid:routine\./);
  r = await mount(null, (p, b)=>b.type === 'agent' ? AGENTS : new Error('orchestra_busy'));
  assert.ok(btn(r.el, 'Noch einmal lesen'));
  r = await mount(null, answer([]));
  assert.match(r.el.textContent, /Keine Routinen\. Eine Routine legt zu festen Zeiten/);
});

check('Einzelansicht: Vorlage und Läufe mit Link aufs Issue', async()=>{
  const {el, ctx} = await mount({type: 'routine', id: 'R-1', title: 'Bericht'}, answer([R1, R2]));
  assert.match(el.textContent, /Aufgabenvorlage/);
  assert.match(el.textContent, /Was gestern geschah/);
  el.querySelector('.t-routines-link').click();
  assert.deepEqual(ctx.opened[0], {type: 'issue', id: 'UA-1', title: 'UA-1'});
  const weg = await mount({type: 'routine', id: 'R-9', title: 'weg'}, answer([R1]));
  assert.match(weg.el.textContent, /gibt es nicht \(mehr\)/);
});

check('Anlegen: der Satz erscheint beim Tippen, abgewiesen bleibt das Formular, sonst Antrag', async()=>{
  let reject = true;
  const {el, ctx} = await mount(null, answer([R1], {liste: {actions: [{verb: 'anlegen', label: 'Anlegen', needs_gate: true}]},
    action: ()=>reject ? new Error('cron_invalid: fünf Felder erwartet') : {status: 'done', needs_gate: true}}));
  assert.deepEqual(tool.actions().map(a=>a.label), ['Anlegen']);
  await tool.actions()[0].run();
  const inputs = el.querySelector('form').querySelectorAll('input');
  const cron = inputs[1];
  cron.value = '*/15 * * * *'; cron.oninput();
  assert.equal(el.querySelector('.t-routines-satz').textContent, 'alle 15 Minuten (Europe/Berlin)');
  cron.value = '0 6 * *'; cron.oninput();
  assert.equal(el.querySelector('.t-routines-satz').textContent, 'Zeitplan wird so gespeichert: 0 6 * *');
  inputs[0].value = 'Nachtlauf';
  await btn(el, 'Absenden').click(); await K.settle();
  assert.match(el.textContent, /cron_invalid: fünf Felder erwartet/);
  assert.equal(el.querySelector('form').querySelectorAll('input')[0].value, 'Nachtlauf');
  reject = false;
  await btn(el, 'Absenden').click(); await K.settle();
  const sent = ctx.calls.filter(c=>c.path === '/api/actions').map(c=>c.body);
  assert.equal(sent[1].verb, 'anlegen');
  assert.equal(sent[1].args.cron, '0 6 * *');
  assert.equal(sent[1].args.titel, 'Nachtlauf');
  assert.match(el.textContent, /Anlegen: Antrag liegt im Posteingang\./);
  assert.equal(el.querySelector('form'), null);
});

check('Verben an der Routine nur aus actions; ausschalten ohne Formular', async()=>{
  const mit = Object.assign({}, R1, {actions: [{verb: 'aendern', label: 'Ändern'}, {verb: 'ausschalten', label: 'Ausschalten', needs_gate: true}]});
  const {el, ctx} = await mount({type: 'routine', id: 'R-1', title: 'Bericht'}, answer([mit]));
  assert.deepEqual(tool.actions().map(a=>a.label), ['Ändern', 'Ausschalten']);
  await tool.actions()[1].run(); await K.settle();
  assert.deepEqual(ctx.calls.find(c=>c.path === '/api/actions').body, {type: 'routine', id: 'R-1', verb: 'ausschalten', args: {}});
  await tool.actions()[0].run();
  assert.equal(el.querySelector('form').querySelectorAll('input')[1].value, '30 6 * * *', 'Ändern füllt das Formular vor');
});

check('Ereignisflut und unmount', async()=>{
  const {el, ctx} = await mount(null, answer([R1]));
  const n = ctx.calls.length;
  for(let i = 0; i < 10; i++) ctx.bus.emit('agent.changed', {id: 'A-UA'});
  await K.settle();
  assert.ok(ctx.calls.length - n <= 4, 'höchstens zwei Lesungen (je Routinen und Agenten)');
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
