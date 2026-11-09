// Node-Test der reinen Teile von Chat und Minimap der Workflow-Darstellungen: `node workflow-chat.test.js`. Läuft über tests/test_workflow_layout.py.
'use strict';
const assert = require('node:assert/strict');
const C = require('./workflow-chat.js');
const M = require('./workflow-minimap.js');

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const knoten = (name, type)=>({id: name, name, type: type || 'n8n-nodes-base.noOp'});
const DOC = {name: 'Bau', nodes: [knoten('Auftrag', 'n8n-nodes-base.manualTrigger'), knoten('Test?', 'n8n-nodes-base.if'), knoten('Fertig'), knoten('Fehler'), knoten('Notiz', 'n8n-nodes-base.stickyNote')],
  connections: {Auftrag: {main: [[{node: 'Test?', type: 'main', index: 0}]]}, 'Test?': {main: [[{node: 'Fertig', type: 'main', index: 0}], [{node: 'Fehler', type: 'main', index: 0}]]}}};

check('kontextText: Schritte ohne Notizen, Ja/Nein an der Prüfung, markierter Schritt', ()=>{
  const t = C.kontextText(DOC, {ausgewaehlt: 'Fehler', art: n=>n.name === 'Auftrag' ? 'Menschlich' : null});
  assert.match(t, /^Prozess „Bau“, 4 Schritte\./);
  assert.match(t, /1\. Auftrag \(Menschlich\)/);
  assert.match(t, /4\. Fehler \(noOp\) \[markiert\]/);
  assert.doesNotMatch(t, /Notiz/);
  assert.match(t, /Test\? → Fertig \(Ja\); Test\? → Fehler \(Nein\)/);
});
check('kontextText: begrenzt, leerer Prozess und fehlende Teile ohne Absturz', ()=>{
  const gross = {nodes: Array.from({length: 400}, (_, i)=>knoten('Schritt mit langem Namen ' + i)), connections: {}};
  assert.ok(C.kontextText(gross).length <= 3500);
  assert.match(C.kontextText({nodes: [], connections: {}}), /0 Schritte/);
  assert.match(C.kontextText(null), /ohne Titel/);
});
check('frageVon und nachrichtenVon: der Stand des Prozesses bleibt aus der Anzeige', ()=>{
  const gesendet = C.frageVon('Prozess X', 'Warum?');
  const out = C.nachrichtenVon([{typ: 'kopf'}, {typ: 'captain', text: gesendet}, {typ: 'modell', text: 'Weil …', ende: 'fertig'}, {typ: 'werkzeug'}]);
  assert.deepEqual(out, [{rolle: 'captain', text: 'Warum?'}, {rolle: 'modell', text: 'Weil …', fehler: null}]);
});
check('nachrichtenVon: Fehlerantwort, leere Modellzeile, kaputte Einträge', ()=>{
  const out = C.nachrichtenVon([null, 'x', {typ: 'modell', text: '', ende: 'fehler', grund: 'Modell weg'}, {typ: 'modell', text: '', ende: 'fertig'}, {typ: 'captain', text: 'frei'}]);
  assert.deepEqual(out, [{rolle: 'modell', text: '', fehler: 'Modell weg'}, {rolle: 'captain', text: 'frei'}]);
});
check('kurz: schneidet mit Auslassung, lässt Kurzes', ()=>{
  assert.equal(C.kurz('abcdef', 4), 'abc…');
  assert.equal(C.kurz('abc', 4), 'abc');
  assert.equal(C.kurz(null, 4), '');
});
check('begrenze: die Minimap bleibt ganz in der Fläche', ()=>{
  assert.deepEqual(M.begrenze(-50, -50, [800, 500], [170, 110]), [4, 4]);
  assert.deepEqual(M.begrenze(900, 700, [800, 500], [170, 110]), [626, 386]);
  assert.deepEqual(M.begrenze(100, 120, [800, 500], [170, 110]), [100, 120]);
});
check('anteile: Lage als Anteil des freien Platzes, in 0 bis 1', ()=>{
  assert.deepEqual(M.anteile(315, 195, [800, 500], [170, 110]), [0.5, 0.5]);
  assert.deepEqual(M.anteile(-10, 9999, [800, 500], [170, 110]), [0, 1]);
  assert.deepEqual(M.anteile(5, 5, [100, 100], [100, 100]), [1, 1]);
});

let failed = 0;
for(const [name, fn] of checks){
  try{ fn(); console.log('ok   ' + name); }
  catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + err.message); }
}
console.log(JSON.stringify({checks: checks.length, failed}));
process.exitCode = failed ? 1 : 0;
