// Node-Test von Layout und Kantenführung der Workflow-Darstellungen: `node workflow-layout.test.js`. Läuft über tests/test_uix_shell_d_pure.py.
'use strict';
const assert = require('node:assert/strict');
const L = require('./workflow-layout.js');

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const knoten = (name, type)=>({id: name, name, type: type || 'n8n-nodes-base.noOp', position: [0, 0], parameters: {}});
const doc = (namen, kanten)=>{
  const connections = {};
  kanten.forEach(([v, n, ast])=>{ const c = connections[v] || (connections[v] = {main: []}); while(c.main.length <= (ast || 0)) c.main.push([]); c.main[ast || 0].push({node: n, type: 'main', index: 0}); });
  return {nodes: namen.map(n=>knoten(n, n === 'Auftrag' ? 'n8n-nodes-base.manualTrigger' : /\?$/.test(n) ? 'n8n-nodes-base.if' : undefined)), connections};
};
// der Prozess „Vollautomatischer Bau“: zwei Prüfungen mit Rücksprung auf „Stufe bauen“, eine Eskalation und der Weg zum Produkt
const BAU = doc(['Auftrag', 'Spec', 'Bauen', 'Test?', 'Fehler', 'Versuche?', 'Eskalation', 'Uebernehmen', 'Letzte?', 'Produkt', 'Captain'],
  [['Auftrag', 'Spec'], ['Spec', 'Bauen'], ['Bauen', 'Test?'], ['Test?', 'Uebernehmen', 0], ['Test?', 'Fehler', 1], ['Fehler', 'Versuche?'],
   ['Versuche?', 'Bauen', 0], ['Versuche?', 'Eskalation', 1], ['Uebernehmen', 'Letzte?'], ['Letzte?', 'Produkt', 0], ['Letzte?', 'Bauen', 1], ['Produkt', 'Captain']]);
const GROESSE = [96, 130];
const kisten = (ordnung, aus)=>Object.entries(ordnung.pos).filter(([n])=>!aus.includes(n)).map(([, p])=>[p[0], p[1], GROESSE[0], GROESSE[1]]);

check('Rücksprünge werden erkannt, Vorwärtskanten bleiben', ()=>{
  const e = L.ebenen(BAU);
  assert.deepEqual([...e.zurueck].sort(), ['Letzte?|Bauen|1', 'Versuche?|Bauen|0']);
});
check('jede Vorwärtskante geht nach rechts (Spalte wächst)', ()=>{
  const e = L.ebenen(BAU);
  e.vor.forEach(k=>assert.ok(e.spalte.get(k.nach) > e.spalte.get(k.von), k.von + ' → ' + k.nach));
});
check('der Hauptweg liegt auf einer Zeile', ()=>{
  const o = L.anordnen(BAU);
  ['Auftrag', 'Spec', 'Bauen', 'Test?', 'Uebernehmen', 'Letzte?', 'Produkt'].forEach(n=>assert.equal(o.zeile.get(n), o.zeile.get('Auftrag'), n));
});
check('„Nein“ eines Zweigs liegt unter „Ja“, kein Knoten teilt sich eine Zelle', ()=>{
  const o = L.anordnen(BAU);
  assert.ok(o.zeile.get('Fehler') > o.zeile.get('Test?'));
  const zellen = Object.values(o.pos).map(p=>p.join(','));
  assert.equal(new Set(zellen).size, zellen.length);
});
check('keine Kante läuft durch einen fremden Knoten', ()=>{
  const o = L.anordnen(BAU), ort = (n, ein)=>[o.pos[n][0] + (ein ? 0 : 96), o.pos[n][1] + 48];
  const boden = Math.max(...Object.values(o.pos).map(p=>p[1])) + 160;
  o.kanten.forEach(k=>{
    const rueck = o.zurueck.has(k.von + '|' + k.nach + '|' + k.ast);
    const w = L.fuehren(ort(k.von, false), ort(k.nach, true), kisten(o, [k.von, k.nach]), {boden, bahn: 0, querbahnen: [85, 255, 425]});
    for(let i = 0; i + 1 < w.length; i++){
      kisten(o, [k.von, k.nach]).forEach(r=>{
        const x0 = Math.min(w[i][0], w[i + 1][0]), x1 = Math.max(w[i][0], w[i + 1][0]), y0 = Math.min(w[i][1], w[i + 1][1]), y1 = Math.max(w[i][1], w[i + 1][1]);
        assert.ok(!(x1 > r[0] && x0 < r[0] + r[2] && y1 > r[1] && y0 < r[1] + r[3]), `${k.von} → ${k.nach}${rueck ? ' (Rücksprung)' : ''} schneidet einen Knoten`);
      });
    }
  });
});
check('ein Rücksprung läuft unterhalb des Graphen und endet am Eingang', ()=>{
  const w = L.fuehren([500, 100], [100, 100], [], {boden: 400, bahn: 2});
  assert.equal(Math.max(...w.map(p=>p[1])), 436);
  assert.deepEqual(w[w.length - 1], [100, 100]);
  assert.deepEqual(w[0], [500, 100]);
});
check('Wege sind rechtwinklig', ()=>{
  const w = L.fuehren([0, 0], [300, 170], [], {});
  for(let i = 0; i + 1 < w.length; i++) assert.ok(w[i][0] === w[i + 1][0] || w[i][1] === w[i + 1][1]);
});
check('Überspringen einer Spalte weicht einer Zwischenkante auf eine Querbahn aus', ()=>{
  const kiste = [[224, 20, 96, 130]];
  const w = L.fuehren([96, 70], [450, 70], kiste, {querbahnen: [180]});
  assert.ok(w.length > 4, 'ein Umweg statt der Geraden');
  for(let i = 0; i + 1 < w.length; i++){
    const x0 = Math.min(w[i][0], w[i + 1][0]), x1 = Math.max(w[i][0], w[i + 1][0]), y0 = Math.min(w[i][1], w[i + 1][1]), y1 = Math.max(w[i][1], w[i + 1][1]);
    assert.ok(!(x1 > 224 && x0 < 320 && y1 > 20 && y0 < 150), 'Segment ' + i + ' schneidet die Zwischenkante');
  }
});
check('Schleife ohne Auslöser und Notizen: kein Absturz, jeder Knoten bekommt eine Zelle', ()=>{
  const d = doc(['A', 'B', 'C'], [['A', 'B'], ['B', 'C'], ['C', 'A']]);
  d.nodes.push(knoten('Notiz', 'n8n-nodes-base.stickyNote'));
  const o = L.anordnen(d);
  assert.deepEqual(Object.keys(o.pos).sort(), ['A', 'B', 'C']);
  assert.equal(o.zurueck.size, 1);
});
check('getrennte Teilgraphen und ein leerer Prozess', ()=>{
  const o = L.anordnen(doc(['Auftrag', 'X', 'Y', 'Z'], [['Auftrag', 'X'], ['Y', 'Z']]));
  assert.equal(Object.keys(o.pos).length, 4);
  assert.equal(new Set(Object.values(o.pos).map(p=>p.join(','))).size, 4);
  assert.deepEqual(L.anordnen({nodes: [], connections: {}}).pos, {});
});
check('pfad: abgerundete Ecken, Anfang und Ende bleiben', ()=>{
  const d = L.pfad([[0, 0], [50, 0], [50, 80], [120, 80]]);
  assert.match(d, /^M 0 0 L 42 0 Q 50 0 50 8 L 50 72 Q 50 80 58 80 L 120 80$/);
  assert.equal(L.pfad([[0, 0], [10, 0]]), 'M 0 0 L 10 0');
});
check('mitte: liegt auf dem Weg, in der Mitte der Länge', ()=>{
  assert.deepEqual(L.mitte([[0, 0], [100, 0], [100, 100]]), [100, 0]);
  assert.deepEqual(L.mitte([[0, 0], [40, 0]]), [20, 0]);
});
check('anordnen ändert weder Knoten noch Verbindungen', ()=>{
  const vorher = JSON.stringify(BAU);
  L.anordnen(BAU);
  assert.equal(JSON.stringify(BAU), vorher);
});

let failed = 0;
for(const [name, fn] of checks){
  try{ fn(); console.log('ok   ' + name); }
  catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + err.message); }
}
console.log(JSON.stringify({checks: checks.length, failed}));
process.exitCode = failed ? 1 : 0;
