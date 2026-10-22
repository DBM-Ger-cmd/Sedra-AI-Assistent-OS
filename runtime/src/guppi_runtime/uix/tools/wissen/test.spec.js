// Spec des Werkzeugs „Wissen“ (Spec 7, D7.9) im Schein-DOM: `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`;
// tests/test_uix_shell_d_pure.py ruft sie so auf. Quellen, Index, Suche, Vorschläge, der Leerzustand ohne Schalter, die Inline-Formulare
// statt prompt(), Treffer → Quelle und Zitat → Treffer. Linie L3: höchstens 20 Prüfungen.
'use strict';
const assert = require('node:assert/strict');
globalThis.sedra = {registerTool(){}};
globalThis.prompt = ()=>{ throw new Error('prompt() ist verboten'); };
require('../../ui/dom.js');
const {zitatTeile, fehlerSatz, stufePruefen} = require('./zitate.js');
const {tool, zustandText, trefferZeile, ergebnisSatz, markierungText} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const STAND = {modell_id: 'bge-m3@abc#modell#1024#e1', bereit: true, grund: null, abschnitte: 2040, vektoren: 2040, abdeckung: 1.0, modus: 'hybrid', neuaufbau: false,
               server_laeuft: true, letzter_lauf: {art: 'einbetten', status: 'fertig', start: '2026-10-22T10:00:00Z', eingebettet: 16}, pause_grund: null, quellen: 2, vorschlaege_offen: 1,
               zerleger: 'z2', fusion: 'f1', geraet: 'cpu', lage: 'frei'};
const SPEICHER = {type: 'wissen', id: 'speicher', title: 'Wissen', state: 'hybrid', summary: 's', actions: [], links: [], stand: STAND};
const QUELLE = {type: 'wissen_quelle', id: 'Q-1', title: 'repo/docs', state: 'aktiv', summary: 's', links: [], aktiv: true, adapter: 'markdown', stufe: 1, projekt: null,
                personenbezug: false, abschnitte: 1900, stand: '2026-10-22T10:00:00Z', actions: [{verb: 'abschalten', label: 'Abschalten', needs_gate: false, confirm: null},
                  {verb: 'stufe_heraufsetzen', label: 'Stufe heraufsetzen', needs_gate: false, confirm: null}, {verb: 'neu_beantragen', label: 'Neu beantragen', needs_gate: true, confirm: null}]};
const TREFFER = {id: 'W0123456789', quelle: 'Q-1', datei: 'docs/A.md', stelle: 'Titel > Lease', datum: '2026-10-20T10:00:00Z', text: 'Vor dem Laden die Lease holen. Siehe [W0123456789].', hash: 'h',
                 punkte: 0.0123, rang_wort: 1, rang_vektor: 3, guete: 1.0, personenbezug: false, befunde: []};
const VORSCHLAG = {type: 'wissen_vorschlag', id: 'WV-1', title: 'Lease zuerst', state: 'offen', summary: 'von A-3 · Stufe 2 · 1 Belege', links: [], text: 'Text', belege: ['W0123456789'],
                   agent_id: 'A-3', lauf_id: 'J-1', aufgabe_id: 'I-1', actions: []};
const answer = (over)=>(path, body)=>{
  if(path === '/api/actions'){
    if(body.verb === 'suche') return {status: 'done', result: over && over.suche ? over.suche : {status: 'erledigt', modus: 'hybrid', hinweis: null, treffer: [TREFFER], ms: 12, woerter: ['lease']}};
    if(body.verb === 'nachfuehren') return {status: 'done', result: {status: 'erledigt', abgleich: {neu: 1, geaendert: 0, entfernt: 0}, einbetten: {eingebettet: 1, ende: 'fertig', grund: ''}}};
    if(body.verb === 'quelle_beantragen' || body.verb === 'neu_beantragen') return {status: 'done', result: {status: 'beantragt', text: 'Antrag liegt im Posteingang'}};
    if(body.verb === 'stufe_heraufsetzen') return over && over.stufe ? over.stufe : {status: 'done', result: {status: 'erledigt'}};
    return {status: 'done', result: {status: 'erledigt'}};
  }
  if(body.type === 'wissen') return over && over.speicher !== undefined ? over.speicher : SPEICHER;
  if(body.type === 'wissen_quelle') return {type: 'wissen_quelle', items: [QUELLE], quelle: {zustand: 'bereit'}};
  if(body.type === 'wissen_vorschlag') return {type: 'wissen_vorschlag', items: [VORSCHLAG]};
  return new Error('unerwartet');
};
async function mount(object, fn){
  const el = K.container(), ctx = K.context(object, fn);
  await tool.mount(el, ctx);
  await K.settle();
  return {el, ctx};
}
const klick = (el, label)=>{ const b = el.querySelectorAll('button').find(x=>x.textContent === label); assert.ok(b, 'Knopf ' + label); return b.onclick({stopPropagation(){}}); };

check('Quellen: Stand oben, Tabelle mit Pfad, Adapter, Stufe, Abschnitten und den Verben der Quelle', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, answer());
  assert.match(el.textContent, /Hybride Suche · Abdeckung 100 % · 2040 Abschnitte/);
  assert.match(el.textContent, /repo\/docs/); assert.match(el.textContent, /markdown/); assert.match(el.textContent, /1900/);
  assert.ok(el.querySelector('[data-quelle="Q-1"]'));
  assert.deepEqual(ctx.calls.map(c=>c.body.type), ['wissen', 'wissen_quelle']);
  await klick(el, 'Abschalten'); await K.settle();
  const a = ctx.calls.find(c=>c.path === '/api/actions');
  assert.deepEqual(a.body, {type: 'wissen_quelle', verb: 'abschalten', args: {}, id: 'Q-1'});
});

check('Quelle beantragen: das Formular ruft das Typ-Verb mit den Feldern des Antrags', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, answer());
  await klick(el, 'Quelle beantragen …'); await K.settle();
  el.querySelectorAll('input').find(i=>i.value === 'docs').value = 'docs/specs';
  await klick(el, 'Antrag stellen'); await K.settle();
  const a = ctx.calls.find(c=>c.path === '/api/actions');
  assert.equal(a.body.verb, 'quelle_beantragen');
  assert.deepEqual(a.body.args, {adapter: 'markdown', wurzel: 'repo', pfad: 'docs/specs', muster: '*.md', stufe: 1, projekt: null, personenbezug: false});
  assert.equal(a.body.id, undefined, 'Typ-Verb ohne Objekt');
  assert.match(el.textContent, /Antrag liegt im Posteingang/);
});

check('Index: Modell-ID, Abdeckung, letzter Lauf; Nachführen meldet die Zahlen', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher', view: 'index'}, answer());
  assert.match(el.textContent, /bge-m3@abc#modell#1024#e1/); assert.match(el.textContent, /einbetten · fertig/); assert.match(el.textContent, /16 eingebettet/);
  await klick(el, 'Nachführen'); await K.settle();
  assert.equal(ctx.calls.find(c=>c.path === '/api/actions').body.verb, 'nachfuehren');
  assert.match(el.textContent, /Abgleich: 1 neu, 0 geändert, 0 entfernt · Einbetten: 1 \(fertig\)/);
});

check('Suche: Treffer mit [id], Quelle, Stelle, Datum, Rang je Liste und Punkten; Klick öffnet die Quellen-Ansicht', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher', view: 'suche'}, answer());
  el.querySelector('input').value = 'Lease holen';
  await klick(el, 'Suchen'); await K.settle();
  const a = ctx.calls.find(c=>c.path === '/api/actions');
  assert.deepEqual(a.body, {type: 'wissen', verb: 'suche', args: {frage: 'Lease holen', k: 5}});
  assert.match(el.textContent, /\[W0123456789\] docs\/A\.md > Titel > Lease · Stand 2026-10-20 · Wort 1, Vektor 3 · 0\.0123/);
  assert.match(el.textContent, /Vor dem Laden die Lease holen\./);
  await el.querySelector('[data-id="W0123456789"]').firstChild.onclick(); await K.settle();
  assert.deepEqual(ctx.opened, [], 'kein object.open: die Quelle wird im eigenen Container markiert');
  const zeile = el.querySelector('tr.t-wissen-markiert');
  assert.ok(zeile && zeile.dataset.quelle === 'Q-1', 'die Quelle des Treffers ist markiert');
  assert.match(el.textContent, /Treffer \[W0123456789\] · docs\/A\.md > Titel > Lease · Stand 2026-10-20/);
  await klick(el, 'Markierung aufheben'); await K.settle();
  assert.equal(el.querySelector('tr.t-wissen-markiert'), null);
});

check('Zitat [W…] im Text ist ein Verweis: Klick hebt den Treffer hervor; eine fremde ID sagt, dass sie nicht in der Suche steht', async()=>{
  const {el} = await mount({type: 'wissen', id: 'speicher', view: 'suche'}, answer());
  el.querySelector('input').value = 'Lease';
  await klick(el, 'Suchen'); await K.settle();
  const zitat = el.querySelector('span.t-wissen-zitat');
  assert.ok(zitat && zitat.textContent === '[W0123456789]' && zitat.getAttribute('role') === 'button');
  await zitat.onkeydown({key: 'Enter', preventDefault(){}}); await K.settle();
  assert.ok(el.querySelector('[data-id="W0123456789"]').classList.contains('t-wissen-aktiv'));
  tool.zeigeTreffer('Wfedcba9876'); await K.settle();
  assert.match(el.textContent, /\[Wfedcba9876\] steht nicht in der letzten Suche/);
  assert.equal(el.querySelector('.t-wissen-aktiv'), null);
});

check('Quelle am Objekt (view quellen, quelle Q-1) ist beim Einhängen markiert; Vorschlag-Belege sind Verweise', async()=>{
  const {el} = await mount({type: 'wissen', id: 'speicher', view: 'quellen', quelle: 'Q-1'}, answer());
  assert.ok(el.querySelector('tr.t-wissen-markiert'));
  assert.match(el.textContent, /Quelle aus der Navigation markiert/);
  const v = await mount({type: 'wissen', id: 'speicher', view: 'vorschlaege'}, answer());
  assert.equal(v.el.querySelectorAll('span.t-wissen-zitat').length, 1, 'der Beleg [W…] ist ein Verweis');
});

check('Stufe heraufsetzen: Inline-Formular statt prompt(); Abbrechen (Esc) schließt, zu niedrige Stufe wird abgewiesen, Bestätigen ruft das Verb', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, answer());
  await klick(el, 'Stufe heraufsetzen'); await K.settle();
  let feld = el.querySelector('input.t-wissen-stufe-feld');
  assert.ok(feld, 'das Formular steht in der Tabelle'); assert.equal(feld.value, '2'); assert.match(el.textContent, /höher als 1, höchstens 6/);
  assert.equal(ctx.calls.filter(c=>c.path === '/api/actions').length, 0, 'noch kein Verb');
  el.querySelector('form.t-wissen-stufe-form').onkeydown({key: 'Escape', preventDefault(){}}); await K.settle();
  assert.equal(el.querySelector('input.t-wissen-stufe-feld'), null, 'Esc schließt das Formular');
  await klick(el, 'Stufe heraufsetzen'); await K.settle();
  feld = el.querySelector('input.t-wissen-stufe-feld'); feld.value = '1';
  await el.querySelector('form.t-wissen-stufe-form').onsubmit({preventDefault(){}}); await K.settle();
  assert.match(el.textContent, /Heraufsetzen heißt enger: die Stufe muss höher als 1 sein/);
  assert.equal(ctx.calls.filter(c=>c.path === '/api/actions').length, 0, 'ungültig: kein Verb');
  feld.value = '3';
  await klick(el, 'Bestätigen'); await K.settle();
  const a = ctx.calls.find(c=>c.path === '/api/actions');
  assert.deepEqual(a.body, {type: 'wissen_quelle', verb: 'stufe_heraufsetzen', args: {stufe: 3}, id: 'Q-1'});
  assert.equal(el.querySelector('input.t-wissen-stufe-feld'), null, 'nach dem Verb ist das Formular zu');
  assert.match(el.textContent, /Erledigt\./);
});

check('Neu beantragen: Formular mit der Stufe der Quelle, Enter stellt den Antrag; ein Fehler aus ctx.api() steht als Satz, nicht in der Konsole', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, answer());
  await klick(el, 'Neu beantragen'); await K.settle();
  const feld = el.querySelector('input.t-wissen-stufe-feld'); assert.equal(feld.value, '1'); feld.value = '0';
  await el.querySelector('form.t-wissen-stufe-form').onsubmit({preventDefault(){}}); await K.settle();
  const a = ctx.calls.find(c=>c.path === '/api/actions');
  assert.deepEqual(a.body, {type: 'wissen_quelle', verb: 'neu_beantragen', args: {stufe: 0}, id: 'Q-1'});
  assert.match(el.textContent, /Antrag liegt im Posteingang/);
  const kaputt = await mount({type: 'wissen', id: 'speicher'}, answer({stufe: new Error('object_not_found')}));
  await klick(kaputt.el, 'Stufe heraufsetzen'); await K.settle();
  await klick(kaputt.el, 'Bestätigen'); await K.settle();
  assert.match(kaputt.el.textContent, /Dieses Objekt gibt es nicht mehr/);
  assert.equal(kaputt.el.querySelectorAll('.bad').length, 1, 'ein Hinweis, kein zweiter „Fehlgeschlagen“');
});

check('Suche ohne Treffer und im Volltext-Modus zeigt den Hinweis', async()=>{
  const {el} = await mount({type: 'wissen', id: 'speicher', view: 'suche'}, answer({suche: {status: 'erledigt', modus: 'volltext', hinweis: 'Nur Volltextsuche (wis_engine_fehlt): Treffer mit anderen Worten können fehlen.', treffer: [], ms: 3, woerter: ['x']}}));
  el.querySelector('input').value = 'x';
  await klick(el, 'Suchen'); await K.settle();
  assert.match(el.textContent, /Nur Volltextsuche \(wis_engine_fehlt\)/);
  assert.match(el.textContent, /nichts gefunden/);
});

check('Vorschläge: Herkunft und Belege, Hinweis auf den Posteingang', async()=>{
  const {el} = await mount({type: 'wissen', id: 'speicher', view: 'vorschlaege'}, answer());
  assert.match(el.textContent, /Lease zuerst/); assert.match(el.textContent, /Agent A-3 · Lauf J-1 · Aufgabe I-1 · Belege \[W0123456789\]/);
  assert.match(el.textContent, /Freigeben oder ablehnen im Posteingang/);
});

check('ohne Schalter: der Leerzustand sagt, wie man ihn einschaltet (Platzhalter-Objekt oder unbekannter Typ)', async()=>{
  const {el} = await mount({type: 'wissen', id: 'speicher'}, ()=>new Error('unknown_object_type'));
  assert.match(el.textContent, /ausgeschaltet \(Schalter „wissen“/);
  assert.equal(el.querySelectorAll('table').length, 0);
  const aus = await mount({type: 'wissen', id: 'speicher'}, answer({speicher: {type: 'wissen', id: 'speicher', title: 'Wissen', state: 'aus', summary: 's', actions: [], links: [], stand: null, grund: 'wissen_config_invalid:yaml'}}));
  assert.match(aus.el.textContent, /ausgeschaltet .* – wissen_config_invalid:yaml/);
});

check('leer: keine Quellen sagt, was eine Quelle ist; Volltext ohne Server-Hinweis bekommt den Rückfall-Hinweis des Werkzeugs', async()=>{
  const leer = (path, body)=>path === '/api/objects' && body.type === 'wissen_quelle' ? {type: 'wissen_quelle', items: []} : answer()(path, body);
  const {el} = await mount({type: 'wissen', id: 'speicher', view: 'quellen', quelle: 'Q-9'}, leer);
  assert.match(el.textContent, /Keine Quellen\. Eine Quelle ist ein Ordner/);
  assert.equal(el.querySelectorAll('table').length, 0);
  const s = await mount({type: 'wissen', id: 'speicher', view: 'suche'}, answer({suche: {status: 'erledigt', modus: 'volltext', hinweis: null, treffer: [TREFFER], ms: 3, woerter: ['x']}}));
  assert.match(s.el.textContent, /Noch keine Suche/);
  s.el.querySelector('input').value = 'x'; await klick(s.el, 'Suchen'); await K.settle();
  assert.match(s.el.textContent, /Nur Volltextsuche: Treffer mit anderen Worten können fehlen/);
});

check('decision.answered liest neu; unmount räumt auf', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, answer());
  const n = ctx.calls.length;
  ctx.bus.emit('decision.answered', {id: 'request:M-1'}); await K.settle();
  assert.ok(ctx.calls.length > n);
  tool.unmount(el);
  assert.equal(el.childElementCount, 0);
  assert.ok(!el.classList.contains('t-wissen'));
});

check('reine Sätze', ()=>{
  assert.equal(zustandText({bereit: false, grund: 'wis_engine_fehlt', abschnitte: 3, abdeckung: 0}), 'Nur Volltextsuche (wis_engine_fehlt) · 3 Abschnitte');
  assert.equal(zustandText({bereit: true, neuaufbau: true, abschnitte: 10, vektoren: 4, abdeckung: 0.4, modus: 'volltext'}), 'Neuaufbau läuft · Abdeckung 40 % · 4 von 10 eingebettet');
  assert.equal(trefferZeile({id: 'W1', datei: 'a', stelle: 'b', datum: '2026-01-01', punkte: 1, rang_wort: null, rang_vektor: 2, personenbezug: true}), '[W1] a > b · Stand 2026-01-01 · Wort –, Vektor 2 · 1.0000 · Personenbezug');
  assert.equal(ergebnisSatz({status: 'fehler', satz: 'Der Pfad muss relativ sein.'}), 'Der Pfad muss relativ sein.');
  assert.equal(ergebnisSatz({status: 'beantragt', text: 'Antrag liegt im Posteingang'}), 'Antrag liegt im Posteingang');
  assert.deepEqual(zitatTeile('a [W0123456789] b [X1] [W01]'), [{text: 'a '}, {id: 'W0123456789'}, {text: ' b [X1] [W01]'}]);
  assert.deepEqual(zitatTeile(null), []);
  assert.equal(fehlerSatz(new Error('object_not_found')), 'Dieses Objekt gibt es nicht mehr; die Ansicht wird neu gelesen. (object_not_found)');
  assert.equal(fehlerSatz(new Error('Keine Verbindung zur Runtime.')), 'Keine Verbindung zur Runtime.');
  assert.equal(fehlerSatz(''), 'Unbekannter Fehler.');
  assert.deepEqual(stufePruefen('3', 1), {ok: true, stufe: 3});
  assert.equal(stufePruefen('1', 1).ok, false); assert.equal(stufePruefen('7').ok, false); assert.equal(stufePruefen('x').ok, false);
  assert.equal(markierungText({id: 'W1', datei: 'a.md', stelle: 'T', datum: '2026-10-20T10:00:00Z'}), 'Treffer [W1] · a.md > T · Stand 2026-10-20');
});

(async()=>{
  let failed = 0;
  for(const [name, fn] of checks){
    try{ await fn(); console.log('ok   ' + name); }
    catch(err){ failed += 1; console.log('FAIL ' + name + '\n     ' + (err && err.stack || err)); }
  }
  console.log(JSON.stringify({checks: checks.length, failed}));
  process.exitCode = failed ? 1 : 0;
})();
