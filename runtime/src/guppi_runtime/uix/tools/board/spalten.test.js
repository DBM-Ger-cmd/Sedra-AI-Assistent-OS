// Node-Test der reinen Logik von „Issues“ (Spec 4, D4.4): `node spalten.test.js`. Läuft über tests/test_uix_shell_d_pure.py.
'use strict';
const assert = require('node:assert/strict');
const S = require('./spalten.js');

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const is = (id, zustand, extra)=>Object.assign({type: 'issue', id, title: 'Issue ' + id, zustand, bearbeiter: null, prioritaet: 1, geaendert: '2026-10-21T08:00:00Z'}, extra || {});

check('sechs Spalten in fester Reihenfolge, auch leer; erledigt und abgebrochen eingeklappt', ()=>{
  const cols = S.boardColumns([]);
  assert.deepEqual(cols.map(c=>c.state), ['offen', 'zugewiesen', 'in_arbeit', 'wartet', 'erledigt', 'abgebrochen']);
  assert.deepEqual(cols.map(c=>c.count), [0, 0, 0, 0, 0, 0]);
  assert.deepEqual(cols.filter(c=>c.eingeklappt).map(c=>c.state), ['erledigt', 'abgebrochen']);
});

check('jedes Issue in seiner Spalte, gezählt', ()=>{
  const cols = S.boardColumns([is('1', 'offen'), is('2', 'in_arbeit'), is('3', 'in_arbeit'), is('4', 'erledigt')]);
  assert.deepEqual(cols.map(c=>c.count), [1, 0, 2, 0, 1, 0]);
});

check('unbekannter Zustand: Spalte „Sonstige“, nichts verschwindet', ()=>{
  const cols = S.boardColumns([is('1', 'offen'), is('2', 'geparkt'), is('3', '')]);
  assert.equal(cols.length, 7);
  assert.deepEqual([cols[6].label, cols[6].items.map(i=>i.id)], ['Sonstige', ['2', '3']]);
});

check('Ordnung: Priorität absteigend, dann jüngste Änderung, dann ID', ()=>{
  const cols = S.boardColumns([is('a', 'offen', {prioritaet: 1, geaendert: '2026-10-20'}), is('b', 'offen', {prioritaet: 3}),
                               is('c', 'offen', {prioritaet: 1, geaendert: '2026-10-22'}), is('d', 'offen', {prioritaet: 1, geaendert: '2026-10-22'})]);
  assert.deepEqual(cols[0].items.map(i=>i.id), ['b', 'c', 'd', 'a']);
});

check('Filter: Bearbeiter, niemand, Text, nur offene', ()=>{
  const items = [is('UA-1', 'offen', {bearbeiter: 'A-CO', title: 'CSV bauen'}), is('UA-2', 'erledigt', {bearbeiter: 'A-CO'}), is('UA-3', 'offen')];
  const ids = f=>S.listRows(items, {filter: f}).map(i=>i.id);
  assert.deepEqual(ids({bearbeiter: 'A-CO'}), ['UA-1', 'UA-2']);
  assert.deepEqual(ids({bearbeiter: '-'}), ['UA-3']);
  assert.deepEqual(ids({text: 'csv'}), ['UA-1']);
  assert.deepEqual(ids({text: 'ua-3'}), ['UA-3']);
  assert.deepEqual(ids({nurOffen: true}), ['UA-1', 'UA-3']);
});

check('Felder aus dem Leser von Spec 1 (assignee, parent_id, Links) wie aus der Fixture', ()=>{
  const f = S.feld({id: 'I-1', title: 'T', state: 'zugewiesen', assignee: 'A-1', parent_id: 'I-0',
                    links: [{type: 'task', id: 'M-1'}, {type: 'intent', id: 'V-1'}, {type: 'project', id: 'P-1'}]});
  assert.deepEqual([f.zustand, f.bearbeiter, f.eltern_id, f.mission_id, f.vorhaben_id, f.projekt_id], ['zugewiesen', 'A-1', 'I-0', 'M-1', 'V-1', 'P-1']);
  assert.equal(S.feld({id: 'x', kommentare: [{}, {}]}).kommentare, 2);
});

check('Zielkette: Vorhaben › Projekt › Eltern › Issue', ()=>{
  const alle = [is('UA-1', 'erledigt', {title: 'Planen'}), is('UA-2', 'in_arbeit', {eltern_id: 'UA-1', title: 'Bauen'})];
  const k = S.chain(is('UA-3', 'wartet', {eltern_id: 'UA-2', vorhaben_id: 'V-1', projekt_id: 'P-1', title: 'Prüfen'}), alle);
  assert.deepEqual(k.map(g=>[g.type, g.id, g.fehlt]), [['intent', 'V-1', false], ['project', 'P-1', false], ['issue', 'UA-1', false],
                                                       ['issue', 'UA-2', false], ['issue', 'UA-3', false]]);
});

check('Zielkette mit fehlendem Glied und mit Zyklus', ()=>{
  const k = S.chain(is('UA-9', 'offen', {eltern_id: 'UA-weg'}), []);
  assert.deepEqual(k.map(g=>[g.id, g.fehlt]), [['UA-weg', true], ['UA-9', false]]);
  const zyklus = [is('A', 'offen', {eltern_id: 'B'}), is('B', 'offen', {eltern_id: 'A'})];
  assert.deepEqual(S.chain(zyklus[0], zyklus).map(g=>g.id), ['B', 'A']);
});

check('die Kette des Servers gilt, wenn er eine liefert', ()=>{
  const k = S.chain({id: 'X', kette: [{type: 'intent', id: 'V-2', title: 'Ziel', fehlt: true}, {type: 'issue', id: 'X', title: 'X'}]});
  assert.deepEqual(k, [{type: 'intent', id: 'V-2', title: 'Ziel', fehlt: true}, {type: 'issue', id: 'X', title: 'X', fehlt: false}]);
});

let failed = 0;
for(const [name, fn] of checks){
  try{ fn(); console.log('ok   ' + name); }
  catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + err.message); }
}
console.log(JSON.stringify({checks: checks.length, failed}));
process.exitCode = failed ? 1 : 0;
