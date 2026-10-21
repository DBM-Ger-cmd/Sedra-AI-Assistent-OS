// Node-Test der reinen Logik der Routinen (Spec 4, D4.4): `node cron.test.js`. Läuft über tests/test_uix_shell_d_pure.py.
'use strict';
const assert = require('node:assert/strict');
const {cronText} = require('./cron.js');

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const satz = (expr, want)=>check(expr + ' → ' + want, ()=>assert.equal(cronText(expr), want));

satz('30 6 * * *', 'jeden Tag um 06:30 Uhr');
satz('0 9 * * 1', 'montags um 09:00 Uhr');
satz('0 9 * * 1-5', 'montags bis freitags um 09:00 Uhr');
satz('0 9 * * 5,1,3', 'montags, mittwochs und freitags um 09:00 Uhr');
satz('0 8 * * sat,SUN', 'samstags und sonntags um 08:00 Uhr');
satz('0 7 * * 7', 'sonntags um 07:00 Uhr');
satz('*/15 * * * *', 'alle 15 Minuten');
satz('0 */2 * * *', 'alle 2 Stunden zur vollen Stunde');
satz('15 * * * *', 'stündlich zur Minute 15');
satz('0 8-17 * * 1-5', 'montags bis freitags stündlich von 08 bis 17 Uhr zur vollen Stunde');
satz('0,30 6,18 * * *', 'jeden Tag um 06:00, 06:30, 18:00 und 18:30 Uhr');
satz('0 6 1,15 * *', 'am 1. und 15. des Monats um 06:00 Uhr');
satz('0 6 1 jan,jul *', 'am 1. des Monats im Januar und Juli um 06:00 Uhr');
satz('0 6 1 * 1', 'am 1. des Monats oder montags um 06:00 Uhr');

check('mit Zeitzone', ()=>assert.equal(cronText('30 6 * * *', 'Europe/Berlin'), 'jeden Tag um 06:30 Uhr (Europe/Berlin)'));

check('unlesbar oder ungültig → null (das Werkzeug zeigt den Ausdruck)', ()=>{
  ['', '* * * *', '0 6 * * * *', '60 6 * * *', '0 24 * * *', '0 6 32 * *', '0 6 * 13 *', '0 6 * * 8', 'x 6 * * *', '*/0 * * * *', '5-1 * * * *', '0 6 * * */2', null]
    .forEach(e=>assert.equal(cronText(e), null, String(e)));
});

let failed = 0;
for(const [name, fn] of checks){
  try{ fn(); console.log('ok   ' + name); }
  catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + err.message); }
}
console.log(JSON.stringify({checks: checks.length, failed}));
process.exitCode = failed ? 1 : 0;
