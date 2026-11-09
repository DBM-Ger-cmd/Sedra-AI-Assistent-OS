// Node-Test der reinen Teile des roten Knopfes: `node workflow-notaus.test.js`. Läuft über tests/test_fabrik_notaus.py.
'use strict';
const assert = require('node:assert/strict');
const N = require('./workflow-notaus.js');

const checks = [];
function check(name, fn){ checks.push([name, fn]); }

check('statusText: ohne Marke nichts, mit Marke Titel und Uhrzeit', ()=>{
  assert.equal(N.statusText(null), null);
  const s = N.statusText({seit: '2026-11-09T12:27:05+00:00', grund: 'Notaus durch den Captain (roter Knopf)'});
  assert.equal(s.titel, 'FABRIK ANGEHALTEN');
  assert.match(s.zeile, /^Seit 12:27 Uhr – es startet nichts Neues\. Notaus/);
  assert.match(N.statusText({}).zeile, /^Seit eben Uhr/);
});
check('berichtText: Einzahl, Mehrzahl, Antworten nur wenn welche da sind', ()=>{
  assert.equal(N.berichtText({laeufe: ['L-1'], aufgaben: ['T-1']}), 'Fabrik angehalten: 1 Lauf gestoppt, 1 Aufgabe zurückgenommen.');
  assert.equal(N.berichtText({laeufe: ['a', 'b'], aufgaben: [], antworten: ['A-1', 'A-2']}), 'Fabrik angehalten: 2 Läufe gestoppt, 0 Aufgaben zurückgenommen, 2 Antworten abgebrochen.');
  assert.equal(N.berichtText(null), 'Fabrik angehalten: 0 Läufe gestoppt, 0 Aufgaben zurückgenommen.');
});
check('berichtText: der beendete Bau steht im Bericht', ()=>{
  assert.match(N.berichtText({laeufe: [], aufgaben: [], bau: 4711}), /0 Aufgaben zurückgenommen, Bau-Lauf beendet\.$/);
  assert.doesNotMatch(N.berichtText({laeufe: [], aufgaben: [], bau: null}), /Bau/);
});
check('berichtText: Fehler stehen im Bericht, nie verschwiegen', ()=>{
  const t = N.berichtText({laeufe: [], aufgaben: [], fehler: ['Lauf L-1: nicht_laufend', 'Aufgabe T-2: x', 'dritter']});
  assert.match(t, /Nicht alles ließ sich stoppen \(3\): Lauf L-1: nicht_laufend; Aufgabe T-2: x$/);
});

let failed = 0;
for(const [name, fn] of checks){
  try{ fn(); console.log('ok   ' + name); }
  catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + err.message); }
}
console.log(JSON.stringify({checks: checks.length, failed}));
process.exitCode = failed ? 1 : 0;
