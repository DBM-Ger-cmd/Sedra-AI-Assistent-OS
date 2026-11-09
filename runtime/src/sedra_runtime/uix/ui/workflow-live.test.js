// Node-Test der reinen Teile der Fabrikhalle im Live-Reiter: `node workflow-live.test.js`. Läuft über tests/test_workflow_fabrik.py.
'use strict';
const assert = require('node:assert/strict');
const L = require('./workflow-live.js');

const checks = [];
function check(name, fn){ checks.push([name, fn]); }

check('laufText: Zustände der Läufe in Klartext, Unbekanntes bleibt sichtbar', ()=>{
  assert.equal(L.laufText('laeuft'), 'läuft');
  assert.equal(L.laufText('ok'), 'fertig');
  assert.equal(L.laufText('fehler'), 'Fehler');
  assert.equal(L.laufText('verloren'), 'verloren');
  assert.equal(L.laufText('seltsam'), 'seltsam');
  assert.equal(L.laufText(null), 'unbekannt');
});
check('laufZeile: Name, Zustand und Dauer; ohne Dauer ohne Strich', ()=>{
  assert.equal(L.laufZeile({name: 'Tests', status: 'laeuft', dauer_s: 125}), 'Tests · läuft · 2 Min.');
  assert.equal(L.laufZeile({lauf: 'run_tests', status: 'ok', dauer_s: null}), 'run_tests · fertig');
  assert.equal(L.laufZeile({status: 'fehler', dauer_s: 12}), 'Lauf · Fehler · 12 Sek.');
});
check('halleText: Einzahl und Mehrzahl, fehlende Zahlen sind null', ()=>{
  assert.deepEqual(L.halleText({laeuft: 1, aufgaben: 1, freigaben: 1}), ['1 Lauf läuft', '1 Aufgabe aktiv', '1 Freigabe wartet auf dich']);
  assert.deepEqual(L.halleText({laeuft: 3, aufgaben: 0, freigaben: 2}), ['3 Läufe laufen', '0 Aufgaben aktiv', '2 Freigaben warten auf dich']);
  assert.deepEqual(L.halleText(null), ['0 Läufe laufen', '0 Aufgaben aktiv', '0 Freigaben warten auf dich']);
});
check('kartenText: Rohname request: fällt weg, Werkzeug und Ziel bleiben, doppelte Begründung auch', ()=>{
  assert.equal(L.kartenText({werkzeug: 'request:wissen_quelle', ziel: 'Wissensquelle freigeben: repo/docs'}), 'Wissensquelle freigeben: repo/docs');
  assert.equal(L.kartenText({werkzeug: 'lauf_starten', ziel: 'run_tests', begruendung: 'Abnahme'}), 'lauf_starten · run_tests – Abnahme');
  assert.equal(L.kartenText({werkzeug: 'x', ziel: 'y', begruendung: 'y'}), 'x · y');
  assert.equal(L.kartenText(null), 'Freigabe');
});
check('dauerText und zusammenfassung bleiben, wie sie waren', ()=>{
  assert.equal(L.dauerText(59), '59 Sek.');
  assert.equal(L.dauerText(3900), '1 Std. 5 Min.');
  assert.equal(L.dauerText(-1), '–');
  assert.equal(L.zusammenfassung({}), 'Gerade läuft nichts.');
  assert.equal(L.zusammenfassung({laeuft: 1, wartet: 2, veraltet: 1}), '1 läuft · 2 warten auf dich · 1 ohne Meldung');
});

let failed = 0;
for(const [name, fn] of checks){
  try{ fn(); console.log('ok   ' + name); }
  catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + err.message); }
}
console.log(JSON.stringify({checks: checks.length, failed}));
process.exitCode = failed ? 1 : 0;
