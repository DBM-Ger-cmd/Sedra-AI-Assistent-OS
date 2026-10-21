// Node-Test der reinen Teile von Shell D (Spec 4, D4.4): Fensterstapel und Ereignisschub. Läuft mit `node stapel.test.js`;
// tests/test_uix_shell_d_pure.py ruft jede *.test.js von Shell D und ihrer Werkzeuge so auf. Nicht im Manifest: der Browser lädt sie nie.
'use strict';
const assert = require('node:assert/strict');
const W = require('./windows.js');
const N = require('./nav.js');

const checks = [];
function check(name, fn){ checks.push([name, fn]); }

const agent = id=>({type: 'agent', id, title: 'Agent ' + id});
const openAll = ids=>ids.reduce((list, id)=>W.openWindow(list, agent(id)), []);
const openIds = list=>list.filter(w=>!w.small).map(w=>w.id);
const smallIds = list=>list.filter(w=>w.small).map(w=>w.id);

check('ein Fenster je Agent, wiederholtes Öffnen holt es nach vorn', ()=>{
  const list = W.openWindow(openAll(['A', 'B']), agent('A'));
  assert.deepEqual(list.map(w=>w.id), ['B', 'A']);
});

check('höchstens vier offen, das älteste wird zum Reiter', ()=>{
  const list = openAll(['A', 'B', 'C', 'D', 'E', 'F']);
  assert.equal(W.MAX_OPEN, 4);
  assert.deepEqual(openIds(list), ['C', 'D', 'E', 'F']);
  assert.deepEqual(smallIds(list), ['A', 'B'], 'verkleinert, nicht geschlossen');
});

check('ein Reiter wieder offen verkleinert das nächstälteste', ()=>{
  const list = W.toggleWindow(openAll(['A', 'B', 'C', 'D', 'E']), 'A');
  assert.deepEqual(openIds(list), ['C', 'D', 'E', 'A']);
  assert.deepEqual(smallIds(list), ['B']);
});

check('verkleinern und schließen', ()=>{
  const list = W.toggleWindow(openAll(['A', 'B']), 'B');
  assert.deepEqual(smallIds(list), ['B']);
  assert.deepEqual(W.closeWindow(list, 'B').map(w=>w.id), ['A']);
  assert.deepEqual(W.closeWindow(list, 'gibts-nicht').length, 2);
});

check('ohne ID kein Fenster', ()=>{
  assert.deepEqual(W.openWindow([], {type: 'agent'}), []);
  assert.deepEqual(W.openWindow([], null), []);
});

check('die gemerkte Liste wird geprüft, bevor sie zählt', ()=>{
  const raw = [{id: 'A', title: 'Planer'}, {id: 'A'}, null, {id: 3}, 'x', {id: 'B', small: 1}, {id: 'C'}, {id: 'D'}, {id: 'E'}, {id: 'F', title: ''}];
  const list = W.sanitize(raw);
  assert.deepEqual(list.map(w=>w.id), ['A', 'B', 'C', 'D', 'E', 'F'], 'doppelt und kaputt fliegen raus');
  assert.equal(list[0].title, 'Planer');
  assert.equal(list[5].title, 'F', 'ohne Titel steht die ID');
  assert.equal(openIds(list).length, 4);
  assert.deepEqual(W.sanitize('kaputt'), []);
});

check('ein Fenster zeichnen nur Werkzeuge, die das Einzelobjekt ausdrücklich nennen', ()=>{
  const L = require('../../ui/loader.js');
  const m = (id, handles, slot)=>({id, kind: 'object', handles, slot: slot || 'inhalt'});
  const all = [m('crew', ['agent']), m('fenster', ['agent:*']), m('nur-a7', ['agent:A-7']), m('kosten', ['agent:*'], 'nachweis'), m('org', ['agent:alle'])];
  const ids = id=>W.windowTools(all, agent(id), L.handlesMatch).map(t=>t.id);
  assert.deepEqual(ids('A-1'), ['fenster'], 'die Rollenliste (ohne Zusatz) nicht, Nachweise nicht, die Sammlung nicht');
  assert.deepEqual(ids('A-7'), ['fenster', 'nur-a7']);
  assert.deepEqual(W.windowTools([m('crew', ['agent'])], agent('A-1'), L.handlesMatch), [], 'ohne Werkzeug: Leerzustand');
});

check('ein Schub von zehn Ereignissen liest höchstens zweimal', async()=>{
  let reads = 0;
  const run = N.coalesce(()=>new Promise(ok=>setImmediate(()=>{ reads += 1; ok(); })));
  const waits = [];
  for(let i = 0; i < 10; i++) waits.push(run());
  await Promise.all(waits);
  await new Promise(ok=>setImmediate(ok)); await new Promise(ok=>setImmediate(ok));
  assert.equal(reads, 2);
  await run();
  assert.equal(reads, 3, 'danach liest ein neues Ereignis wieder');
});

check('ein Lesefehler sperrt den Schub nicht', async()=>{
  let calls = 0;
  const run = N.coalesce(()=>{ calls += 1; if(calls === 1) throw new Error('kaputt'); });
  await run().catch(()=>{});
  await run();
  assert.equal(calls, 2);
});

(async()=>{
  let failed = 0;
  for(const [name, fn] of checks){
    try{ await fn(); console.log('ok   ' + name); }
    catch(err){ failed += 1; console.log('FAIL ' + name + ': ' + err.message); }
  }
  console.log(JSON.stringify({checks: checks.length, failed}));
  process.exitCode = failed ? 1 : 0;
})();
