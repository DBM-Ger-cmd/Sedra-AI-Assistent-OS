// Spec des Werkzeugs im Schein-DOM (Spec 4, D4.4/D4.6): mounten in einen leeren Container, Ereignis senden, Text prüfen.
// `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`; tests/test_uix_shell_d_pure.py ruft sie so auf. Die Browserseite prüft uix_check.
'use strict';
const assert = require('node:assert/strict');
globalThis.sedra = {registerTool(){}};
require('../../ui/dom.js');
const {tool, slotRows, wartetZuLange} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const TS = '2026-10-21T08:00:00Z';
const MODELS = [{type: 'model', id: 'coder.qwen', title: 'coder.qwen', state: 'geladen', summary: 'coder.qwen – qwen · läuft mit Kontext 32768', actions: [], links: []},
                {type: 'model', id: 'coder.alt', title: 'coder.alt', state: 'bereit', summary: 'coder.alt', actions: [], links: []}];
const SLOTS = {gesamt: 3, modell: 'coder.qwen', warte_max_s: 120,
  belegt: [{slot: 1, run_id: 'L-12', agent_id: 'A-CO', titel: 'CSV-Export bauen', prioritaet: 'agent', seit: TS, mission_id: 'M-7'},
           {slot: 2, run_id: 'L-13', agent_id: 'A-UA', titel: 'Bericht', prioritaet: 'captain', seit: TS}],
  schlange: [{run_id: 'L-14', agent_id: 'A-PL', prioritaet: 'routine', seit: TS, entscheidung: 'gate:HG-9'}]};
const AGENTS = {type: 'agent', items: [{id: 'A-CO', title: 'Coder'}, {id: 'A-UA', title: 'Unterarbeiter'}, {id: 'A-PL', title: 'Planer'}]};
const answer = (models, slots)=>(path, body)=>body.type === 'agent' ? AGENTS : Object.assign({type: 'model', items: models}, slots ? {slots} : {});
async function mount(fn){
  const el = K.container(), ctx = K.context({type: 'model', id: 'alle', title: 'Modelle und Slots', collection: true}, fn);
  await tool.mount(el, ctx);
  await K.settle();
  return {el, ctx};
}

check('drei Slots, zwei belegt mit Agent, Lauf und Priorität; einer frei', async()=>{
  const {el, ctx} = await mount(answer(MODELS, SLOTS));
  assert.deepEqual(ctx.calls.map(c=>c.path), ['/api/objects', '/api/objects']);
  assert.match(el.textContent, /2 von 3 Slots belegt/);
  const rows = el.querySelectorAll('tr').slice(1);
  assert.deepEqual(rows.map(r=>r.className), ['t-slots-row belegt', 't-slots-row belegt', 't-slots-row frei']);
  assert.match(rows[0].textContent, /CoderCSV-Export bauen · L-12 MissionAgent/);
  assert.match(rows[1].textContent, /Captain/);
});

check('Warteschlange in Reihenfolge; zu lange gewartet mit Cloud-Vorschlag', async()=>{
  const {el} = await mount(answer(MODELS, SLOTS));
  assert.match(el.textContent, /Warteschlange · 1/);
  assert.match(el.textContent, /1\.PlanerRoutine · L-14/);
  assert.match(el.textContent, /Wartet länger als 120 s – Cloud-Vorschlag liegt im Posteingang\./);
});

check('Agent und Mission öffnen sich aus der Zeile', async()=>{
  const {el, ctx} = await mount(answer(MODELS, SLOTS));
  const links = el.querySelectorAll('.t-slots-link');
  links[0].click(); links[1].click();
  assert.deepEqual(ctx.opened, [{type: 'agent', id: 'A-CO', title: 'Coder'}, {type: 'task', id: 'M-7', title: 'CSV-Export bauen'}]);
  assert.deepEqual(tool.actions(), [], 'keine Verben: Laden und Entladen bleibt in der Werkstatt');
});

check('ohne Scheduler: ein Modellserver, ein Platz – mit dem laufenden Modell', async()=>{
  const {el} = await mount(answer(MODELS));
  assert.match(el.textContent, /Ein Modellserver, ein Platz\. Parallele Slots kommen mit dem Scheduler \(Spec 2\)\./);
  assert.match(el.textContent, /Läuft: coder\.qwen – qwen · läuft mit Kontext 32768/);
});

check('kein Modell geladen', async()=>{
  const {el} = await mount(answer([MODELS[1]]));
  assert.match(el.textContent, /Kein Modell geladen – Slots gibt es erst nach dem Laden/);
});

check('nicht lesbar: rote Zeile, „Noch einmal lesen“', async()=>{
  let n = 0;
  const {el, ctx} = await mount((p, b)=>b.type === 'agent' ? AGENTS : (++n === 1 ? new Error('Keine Verbindung zur Runtime') : {type: 'model', items: MODELS, slots: SLOTS}));
  assert.match(el.textContent, /nicht lesbar: Keine Verbindung/);
  await el.querySelector('button').click(); await K.settle();
  assert.match(el.textContent, /2 von 3 Slots belegt/);
  assert.equal(ctx.calls.filter(c=>c.body.type === 'model').length, 2);
});

check('slot.changed liest neu; zehn auf einmal höchstens zweimal', async()=>{
  const {ctx} = await mount(answer(MODELS, SLOTS));
  for(let i = 0; i < 10; i++) ctx.bus.emit('slot.changed', {slot: 1, state: 'frei'});
  await K.settle();
  assert.ok(ctx.calls.filter(c=>c.body.type === 'model').length <= 3);
});

check('rein: Slots ohne Lücke, Wartezeit gegen die Obergrenze', ()=>{
  assert.deepEqual(slotRows({gesamt: 2, belegt: [{slot: 2, run_id: 'L'}]}).map(r=>r.zustand), ['frei', 'belegt']);
  assert.deepEqual(slotRows({}).length, 0);
  const t = Date.parse(TS);
  assert.equal(wartetZuLange({seit: TS}, 120, t + 121000), true);
  assert.equal(wartetZuLange({seit: TS}, 120, t + 60000), false);
  assert.equal(wartetZuLange({seit: 'kaputt'}, 120, t), false);
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
