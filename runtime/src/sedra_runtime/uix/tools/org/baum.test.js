// Node-Test der reinen Logik des Organigramms (Spec 4, D4.4): `node baum.test.js`. Läuft über tests/test_uix_shell_d_pure.py.
'use strict';
const assert = require('node:assert/strict');
const B = require('./baum.js');

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const ag = (id, boss, title)=>({id, reports_to: boss, title: title || id});
const at = (L, id)=>L.knoten.find(k=>k.id === id);
const O = {kartenbreite: 200, kartenhoehe: 80, abstand: 20};

check('leer: nur der Captain', ()=>{
  const L = B.layoutTree([], O);
  assert.deepEqual(L.knoten.map(k=>k.id), ['captain']);
  assert.deepEqual(L.linien, []);
  assert.deepEqual(L.ohneVorgesetzten, []);
  assert.equal(L.breite, 200);
});

check('Kette: jede Ebene eine Zeile tiefer, alle auf einer Linie', ()=>{
  const L = B.layoutTree([ag('A', null), ag('B', 'A'), ag('C', 'B')], O);
  assert.deepEqual(L.knoten.map(k=>[k.id, k.ebene, k.y]), [['captain', 0, 0], ['A', 1, 100], ['B', 2, 200], ['C', 3, 300]]);
  assert.equal(new Set(L.knoten.map(k=>k.x)).size, 1);
  assert.equal(L.hoehe, 380);
});

check('Fächer: Geschwister nach Name, Eltern über der Mitte', ()=>{
  const L = B.layoutTree([ag('UA', null), ag('R', 'UA', 'Reviewer'), ag('P', 'UA', 'Planer'), ag('C', 'UA', 'Coder')], O);
  assert.deepEqual(L.knoten.filter(k=>k.ebene === 2).map(k=>k.id), ['C', 'P', 'R']);
  assert.deepEqual(['C', 'P', 'R'].map(id=>at(L, id).x), [0, 220, 440]);
  assert.equal(at(L, 'UA').x, 220);
  assert.equal(L.breite, 640);
  assert.deepEqual(L.linien.filter(l=>l.von === 'UA').map(l=>l.nach), ['C', 'P', 'R']);
});

check('breiter Teilbaum schiebt den Nachbarn', ()=>{
  const L = B.layoutTree([ag('UA', null), ag('A', 'UA'), ag('B', 'UA'), ag('A1', 'A'), ag('A2', 'A'), ag('A3', 'A')], O);
  assert.equal(at(L, 'B').x, 660, 'B steht rechts neben den drei Kindern von A');
  assert.equal(at(L, 'A').x, 220);
  assert.equal(L.breite, 860);
});

check('Zyklus und Selbstverweis: nichts hängt, beide nicht eingeordnet', ()=>{
  const L = B.layoutTree([ag('UA', null), ag('X', 'Y'), ag('Y', 'X'), ag('S', 'S')], O);
  assert.deepEqual(L.knoten.map(k=>k.id), ['captain', 'UA']);
  assert.deepEqual(L.ohneVorgesetzten, ['S', 'X', 'Y']);
});

check('unbekannter Vorgesetzter: der Agent und seine Untergebenen sind nicht eingeordnet', ()=>{
  const L = B.layoutTree([ag('UA', null), ag('W', 'weg'), ag('W1', 'W')], O);
  assert.deepEqual(L.ohneVorgesetzten, ['W', 'W1']);
});

check('Tiefe begrenzt', ()=>{
  const L = B.layoutTree([ag('A', null), ag('B', 'A'), ag('C', 'B')], Object.assign({tiefeMax: 2}, O));
  assert.deepEqual(L.knoten.map(k=>k.id), ['captain', 'A', 'B']);
  assert.deepEqual(L.ohneVorgesetzten, ['C']);
});

check('Budgetstufe kommt vom Server, sonst aus seinen Schwellen, sonst keine', ()=>{
  assert.equal(B.budgetStufe({prozent: 95, stufe: 'warnung'}), 'warnung');
  assert.equal(B.budgetStufe({prozent: 95, schwellen: {warnung: 80, gestoppt: 100}}), 'warnung');
  assert.equal(B.budgetStufe({prozent: 100, schwellen: {warnung: 80, gestoppt: 100}}), 'gestoppt');
  assert.equal(B.budgetStufe({prozent: 95}), null, 'keine erfundene Schwelle');
  assert.equal(B.budgetStufe(null), null);
});

check('Balken: Prozent als Text, Euro nur mit Daten, über 100 gedeckelt', ()=>{
  const b = B.budgetBalken({prozent: 62.4, verbraucht_token: 124800, grenze_token: 200000, grenze_eur_cent: null, verbraucht_eur_cent: null, stufe: 'ok'});
  assert.equal(b.breite, 62);
  assert.equal(b.text, '62 % · 124.800 / 200.000 Token');
  assert.equal(B.budgetBalken({prozent: 130, stufe: 'gestoppt', verbraucht_eur_cent: 250, grenze_eur_cent: 200}).breite, 100);
  assert.match(B.budgetBalken({prozent: 130, verbraucht_eur_cent: 250, grenze_eur_cent: 200}).text, /2,50 \/ 2,00 €/);
  assert.equal(B.budgetBalken({}), null);
});

let failed = 0;
for(const [name, fn] of checks){
  try{ fn(); console.log('ok   ' + name); }
  catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + err.message); }
}
console.log(JSON.stringify({checks: checks.length, failed}));
process.exitCode = failed ? 1 : 0;
