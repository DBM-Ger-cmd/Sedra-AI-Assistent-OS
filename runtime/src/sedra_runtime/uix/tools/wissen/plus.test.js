// Node-Test der reinen Teile des Plus im Werkzeug „Wissen“: `node plus.test.js`. Läuft über tests/test_uix_shell_d_pure.py.
'use strict';
const assert = require('node:assert/strict');
const P = require('./plus.js');

const checks = [];
function check(name, fn){ checks.push([name, fn]); }

check('teileVon: Stücke unter dem Limit, lückenlos und ohne Überlapp', ()=>{
  const t = P.teileVon(1300, 500);
  assert.deepEqual(t, [[0, 500], [500, 500], [1000, 300]]);
  assert.equal(t.reduce((a, [, l])=>a + l, 0), 1300);
});
check('teileVon: genau ein Vielfaches, eine leere Datei, eine kleine Datei', ()=>{
  assert.deepEqual(P.teileVon(1000, 500), [[0, 500], [500, 500]]);
  assert.deepEqual(P.teileVon(0), [[0, 0]]);
  assert.deepEqual(P.teileVon(10), [[0, 10]]);
});
check('teileVon: das Standardstück bleibt unter 1 MB als Base64', ()=>{
  const t = P.teileVon(5 * 1024 * 1024);
  assert.ok(t.every(([, l])=>Math.ceil(l / 3) * 4 < 1024 * 1024 - 2000));
});
check('endungOk: erlaubte Arten, Groß-/Kleinschreibung, Fremdes', ()=>{
  ['a.md', 'B.TXT', 'x/y.docx', 'c.csv', 'd.pdf', 'e.xlsx', 'f.pptx'].forEach(n=>assert.equal(P.endungOk(n), true, n));
  ['a.exe', 'bild.png', 'ohne', '.md.exe', ''].forEach(n=>assert.equal(P.endungOk(n), false, n));
  assert.equal(P.endungOk(null), false);
});
check('werteVon: ein Ordner im Projekt, Adapter dokumente, Stufe 3 und Personenbezug vorbelegt', ()=>{
  const w = P.werteVon({eingang: 'local_config/wissen/eingang/E-1', muster: '*.md,*.txt'});
  assert.deepEqual(w, {adapter: 'dokumente', wurzel: 'projekt', pfad: 'local_config/wissen/eingang/E-1', muster: '*.md,*.txt', stufe: 3, projekt: null, personenbezug: true});
});
check('pruefungVon: Zahl in Klartext, Übersprungenes genannt, nie „schon da“', ()=>{
  const eins = P.pruefungVon({dateien: 1});
  assert.equal(eins.satz, '1 Datei im Eingang.');
  assert.equal(eins.status, 'erledigt');
  assert.equal(eins.schon_da, false);
  const viele = P.pruefungVon({dateien: 12, uebersprungen: {art: 2, gross: 1, link: 0, limit: 0}});
  assert.match(viele.satz, /^12 Dateien im Eingang, 3 übersprungen/);
});

let failed = 0;
for(const [name, fn] of checks){
  try{ fn(); console.log('ok   ' + name); }
  catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + err.message); }
}
console.log(JSON.stringify({checks: checks.length, failed}));
process.exitCode = failed ? 1 : 0;
