// Node-Test der reinen Logik des Agentenfensters (Spec 4, D4.4): `node verlauf.test.js`. Läuft über tests/test_uix_shell_d_pure.py.
'use strict';
const assert = require('node:assert/strict');
const V = require('./verlauf.js');

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const m = (id, extra)=>Object.assign({id, rolle: 'captain', ts: '2026-10-21T08:00:00Z', state: 'angenommen'}, extra || {});

check('zusammenführen: nach ID, ohne Doppel, die neuere Fassung gewinnt', ()=>{
  const out = V.mergeMessages([m(1), m(2, {state: 'wartet_freigabe'})], [m(3), m(2, {state: 'laeuft'})]);
  assert.deepEqual(out.map(x=>x.id), [1, 2, 3]);
  assert.equal(out[1].state, 'laeuft');
});

check('zusammenführen: Zahlen als Zahlen, ältere Seite davor, leer bleibt leer', ()=>{
  assert.deepEqual(V.mergeMessages([m(10)], [m(9), m(2)]).map(x=>x.id), [2, 9, 10]);
  assert.deepEqual(V.mergeMessages(null, undefined), []);
  assert.deepEqual(V.mergeMessages([{id: null}, m('b'), m('a')]).map(x=>x.id), ['a', 'b']);
});

check('Status als Satz', ()=>{
  assert.equal(V.statusText(m(1, {issue_id: 'UA-3'})), 'angekommen – Issue UA-3 angelegt');
  assert.equal(V.statusText(m(1)), 'angekommen');
  assert.equal(V.statusText({status: 'wartet_freigabe'}), 'wartet auf Freigabe im Posteingang');
  assert.equal(V.statusText({status: 'laeuft', mission_id: 'M-12'}), 'Lauf M-12 läuft');
  assert.equal(V.statusText({status: 'beantwortet'}), '');
  assert.equal(V.statusText({status: 'fehler', grund: 'budget_stop'}), 'Fehler: budget_stop');
  assert.equal(V.statusText({}), '');
});

check('Tagestrenner in UTC, in der Reihenfolge der Nachrichten', ()=>{
  const tage = V.byDay([m(1, {ts: '2026-10-20T23:59:00Z'}), m(2, {ts: '2026-10-21T00:01:00Z'}), m(3, {ts: '2026-10-21T09:00:00Z'}), m(4, {ts: null})]);
  assert.deepEqual(tage.map(t=>[t.label, t.items.map(x=>x.id)]), [['20.10.2026', [1]], ['21.10.2026', [2, 3]], ['ohne Datum', [4]]]);
  assert.deepEqual(V.byDay([]), []);
});

check('Cloud-Kennzeichen nur bei route cloud', ()=>{
  assert.equal(V.cloudText({route: 'cloud', provider_id: 'anbieter-a', model: 'modell-x'}), 'Cloud · anbieter-a / modell-x');
  assert.equal(V.cloudText({route: 'lokal', provider_id: 'x'}), null);
  assert.equal(V.cloudText({}), null);
});

let failed = 0;
for(const [name, fn] of checks){
  try{ fn(); console.log('ok   ' + name); }
  catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + err.message); }
}
console.log(JSON.stringify({checks: checks.length, failed}));
process.exitCode = failed ? 1 : 0;
