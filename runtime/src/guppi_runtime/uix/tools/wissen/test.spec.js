// Spec des Werkzeugs „Wissen“ (Spec 7, D7.9) im Schein-DOM: `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`;
// tests/test_uix_shell_d_pure.py ruft sie so auf. Quellen, Index, Suche, Vorschläge und der Leerzustand ohne Schalter.
'use strict';
const assert = require('node:assert/strict');
globalThis.sedra = {registerTool(){}};
globalThis.prompt = ()=>'3';
require('../../ui/dom.js');
const {tool, zustandText, trefferZeile, ergebnisSatz} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const STAND = {modell_id: 'bge-m3@abc#modell#1024#e1', bereit: true, grund: null, abschnitte: 2040, vektoren: 2040, abdeckung: 1.0, modus: 'hybrid', neuaufbau: false,
               server_laeuft: true, letzter_lauf: {art: 'einbetten', status: 'fertig', start: '2026-10-22T10:00:00Z', eingebettet: 16}, pause_grund: null, quellen: 2, vorschlaege_offen: 1,
               zerleger: 'z2', fusion: 'f1', geraet: 'cpu', lage: 'frei'};
const SPEICHER = {type: 'wissen', id: 'speicher', title: 'Wissen', state: 'hybrid', summary: 's', actions: [], links: [], stand: STAND};
const QUELLE = {type: 'wissen_quelle', id: 'Q-1', title: 'repo/docs', state: 'aktiv', summary: 's', links: [], aktiv: true, adapter: 'markdown', stufe: 1, projekt: null,
                personenbezug: false, abschnitte: 1900, stand: '2026-10-22T10:00:00Z', actions: [{verb: 'abschalten', label: 'Abschalten', needs_gate: false, confirm: null}]};
const TREFFER = {id: 'W0123456789', quelle: 'Q-1', datei: 'docs/A.md', stelle: 'Titel > Lease', datum: '2026-10-20T10:00:00Z', text: 'Vor dem Laden die Lease holen.', hash: 'h',
                 punkte: 0.0123, rang_wort: 1, rang_vektor: 3, guete: 1.0, personenbezug: false, befunde: []};
const VORSCHLAG = {type: 'wissen_vorschlag', id: 'WV-1', title: 'Lease zuerst', state: 'offen', summary: 'von A-3 · Stufe 2 · 1 Belege', links: [], text: 'Text', belege: ['W0123456789'],
                   agent_id: 'A-3', lauf_id: 'J-1', aufgabe_id: 'I-1', actions: []};
const answer = (over)=>(path, body)=>{
  if(path === '/api/actions'){
    if(body.verb === 'suche') return {status: 'done', result: over && over.suche ? over.suche : {status: 'erledigt', modus: 'hybrid', hinweis: null, treffer: [TREFFER], ms: 12, woerter: ['lease']}};
    if(body.verb === 'nachfuehren') return {status: 'done', result: {status: 'erledigt', abgleich: {neu: 1, geaendert: 0, entfernt: 0}, einbetten: {eingebettet: 1, ende: 'fertig', grund: ''}}};
    if(body.verb === 'quelle_beantragen') return {status: 'done', result: {status: 'beantragt', text: 'Antrag liegt im Posteingang'}};
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
  el.querySelector('[data-id="W0123456789"]').firstChild.onclick();
  assert.deepEqual(ctx.opened, [{type: 'wissen', id: 'speicher', title: 'Wissen', view: 'quellen', quelle: 'Q-1'}]);
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
