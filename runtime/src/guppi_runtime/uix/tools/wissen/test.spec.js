// Spec des Werkzeugs „Wissen“ v2 (Spec 7, D7.9; SPEC_WERKZEUG_WISSEN_v2) im Schein-DOM: `node -r ../../../../../tests/uix_spec_dom.js test.spec.js`;
// tests/test_uix_shell_d_pure.py ruft sie so auf. Suche als Start, Karten, Quellen als Liste mit Menü, geführter Antrag, Messung,
// Vorschläge, Leerzustände, Inline-Formulare statt prompt(), Gedächtnis (Sitzung ohne Inhalt). Linie L3: höchstens 20 Prüfungen.
'use strict';
const assert = require('node:assert/strict');
globalThis.sedra = {registerTool(){}};
globalThis.prompt = ()=>{ throw new Error('prompt() ist verboten'); };
require('../../ui/dom.js');
const {zitatTeile, fehlerSatz, stufePruefen, artText, stufeText, hervorheben, relevanz} = require('./zitate.js');
require('./suche.js'); require('./quellen.js');
const {VORLAGEN, schonDa, argsVon} = require('./antrag.js');
const {fortschritt} = require('./messung.js');
const {tool, zustandText, trefferZeile, ergebnisSatz, markierungText, ansichtFuer} = require('./tool.js');
const K = globalThis.specKit;

const checks = [];
function check(name, fn){ checks.push([name, fn]); }
const STAND = {modell_id: 'bge-m3@abc#modell#1024#e1', bereit: true, grund: null, abschnitte: 2040, vektoren: 2040, abdeckung: 1.0, modus: 'hybrid', neuaufbau: false,
               server_laeuft: true, letzter_lauf: {art: 'einbetten', status: 'fertig', start: '2026-10-22T10:00:00Z', eingebettet: 16}, pause_grund: null, quellen: 2, vorschlaege_offen: 1,
               zerleger: 'z2', fusion: 'f1', geraet: 'cpu', lage: 'frei'};
const SPEICHER = {type: 'wissen', id: 'speicher', title: 'Wissen', state: 'hybrid', summary: 's', actions: [], links: [], stand: STAND};
const QUELLE = {type: 'wissen_quelle', id: 'Q-1', title: 'repo/docs', state: 'aktiv', summary: 's', links: [], aktiv: true, adapter: 'markdown', wurzel: 'repo', pfad: 'docs', stufe: 1, projekt: null,
                personenbezug: false, abschnitte: 1900, stand: '2026-10-22T10:00:00Z', actions: [{verb: 'abschalten', label: 'Abschalten', needs_gate: false, confirm: null},
                  {verb: 'stufe_heraufsetzen', label: 'Stufe heraufsetzen', needs_gate: false, confirm: null}, {verb: 'neu_beantragen', label: 'Neu beantragen', needs_gate: true, confirm: null}]};
const TREFFER = {id: 'W0123456789', quelle: 'Q-1', datei: 'docs/A.md', stelle: 'Titel > Lease', datum: '2026-10-20T10:00:00Z', text: 'Vor dem Laden die Lease holen. Siehe [W0123456789].', hash: 'h',
                 punkte: 0.0123, rang_wort: 1, rang_vektor: 3, guete: 1.0, personenbezug: false, befunde: []};
const VORSCHLAG = {type: 'wissen_vorschlag', id: 'WV-1', title: 'Lease zuerst', state: 'offen', summary: 'von A-3 · Stufe 2 · 1 Belege', links: [], text: 'Text', belege: ['W0123456789'],
                   agent_id: 'A-3', lauf_id: 'J-1', aufgabe_id: 'I-1', actions: []};
const FRAGE = {frage_sha256: 'a'.repeat(64), zeit: '2026-10-22T10:00:00Z', modus: 'hybrid', ids: ['W0123456789'], urteil: null};
const answer = (over)=>(path, body)=>{
  if(path === '/api/actions'){
    const o = over || {};
    if(body.verb === 'suche') return {status: 'done', result: o.suche || {status: 'erledigt', modus: 'hybrid', hinweis: null, treffer: [TREFFER], ms: 12, woerter: ['lease']}};
    if(body.verb === 'nachfuehren') return {status: 'done', result: {status: 'erledigt', abgleich: {neu: 1, geaendert: 0, entfernt: 0}, einbetten: {eingebettet: 1, ende: 'fertig', grund: ''}}};
    if(body.verb === 'quelle_beantragen' || body.verb === 'neu_beantragen') return {status: 'done', result: {status: 'beantragt', text: 'Antrag liegt im Posteingang'}};
    if(body.verb === 'quelle_pruefen') return {status: 'done', result: o.pruefen || {status: 'erledigt', dateien: 1, abschnitte_etwa: 40, ueberschneidung: [], schon_da: false, satz: '1 Datei, etwa 40 Abschnitte.'}};
    if(body.verb === 'nachmessung') return {status: 'done', result: {status: 'erledigt', saetze: [Object.assign({}, FRAGE)]}};
    if(body.verb === 'stufe_heraufsetzen' && o.stufe) return o.stufe;
    return {status: 'done', result: {status: 'erledigt'}};
  }
  if(body.type === 'wissen') return over && over.speicher !== undefined ? over.speicher : SPEICHER;
  if(body.type === 'wissen_quelle') return {type: 'wissen_quelle', items: [QUELLE], quelle: {zustand: 'bereit'}};
  if(body.type === 'wissen_vorschlag') return {type: 'wissen_vorschlag', items: [VORSCHLAG]};
  return new Error('unerwartet');
};
async function mount(object, fn, extra){
  const el = K.container(), ctx = Object.assign(K.context(object, fn), extra || {});
  await tool.mount(el, ctx);
  await K.settle();
  return {el, ctx};
}
const knopf = (el, label)=>{ const b = el.querySelectorAll('button').find(x=>x.textContent === label); assert.ok(b, 'Knopf ' + label); return b; };
const klick = async(el, label)=>{ await knopf(el, label).onclick({stopPropagation(){}, preventDefault(){}}); await K.settle(); };
const verben = ctx=>ctx.calls.filter(c=>c.path === '/api/actions').map(c=>c.body);
const gehoert = (ctx, name)=>{ const l = []; ctx.bus.on(name, p=>l.push(p)); return l; };
async function suche(el, frage){ el.querySelector('input.t-wissen-frage').value = frage; await klick(el, 'Suchen'); }

check('Start ist die Suche (WZ1): Reiter mit Zahlen aus dem einen Objekt, Stand mit Tausenderpunkt, nichts weiter gelesen', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, answer());
  assert.equal(el.querySelector('button.t-wissen-tab.on').dataset.ansicht, 'suche');
  assert.match(el.textContent, /Hybride Suche · Abdeckung 100 % · 2\.040 Abschnitte/);
  assert.match(el.textContent, /Quellen \(2\)/); assert.match(el.textContent, /Vorschläge ⚠ 1/);
  assert.deepEqual(ctx.calls.map(c=>c.body.type), ['wissen']);
  assert.ok(el.querySelector('input.t-wissen-frage.t-wissen-fokus'), 'das Feld hat den Fokus');
  assert.equal(knopf(el, 'Suchen').type, 'submit', 'Enter im Feld sucht');
});

check('Suche: Karte mit Stelle als Titel, Suchwort markiert, Relevanzbalken; Kennung und Ränge erst unter „Details“', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, answer());
  await suche(el, 'Lease holen');
  assert.deepEqual(verben(ctx)[0], {type: 'wissen', verb: 'suche', args: {frage: 'Lease holen', k: 5}});
  const card = el.querySelector('[data-id="W0123456789"]');
  assert.equal(card.querySelector('b.t-wissen-stelle').textContent, 'Titel > Lease');
  assert.match(card.textContent, /Q-1 · docs\/A\.md · Stand 2026-10-20/);
  assert.equal(card.querySelector('mark.t-wissen-mark').textContent, 'Lease');
  assert.equal(card.querySelector('div.t-wissen-balken').firstChild.style.width, '100%');
  assert.doesNotMatch(card.textContent, /Wort 1, Vektor 3/);
  await klick(card, 'Details');
  assert.match(el.textContent, /\[W0123456789\] docs\/A\.md > Titel > Lease · Stand 2026-10-20 · Wort 1, Vektor 3 · 0\.0123/);
});

check('Fundstelle und „Ins Gespräch“ senden wissen.auswahl – das Gespräch bekommt Zweck und Stelle', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, answer());
  const auswahl = gehoert(ctx, 'wissen.auswahl');
  await suche(el, 'Lease');
  await klick(el, 'Fundstelle');
  assert.deepEqual(auswahl[0], {id: 'W0123456789', quelle: 'Q-1'});
  assert.ok(el.querySelector('[data-id="W0123456789"]').classList.contains('t-wissen-aktiv'));
  await klick(el, 'Ins Gespräch');
  assert.deepEqual(auswahl[1], {id: 'W0123456789', quelle: 'Q-1', zweck: 'gespraech', stelle: 'Titel > Lease'});
  assert.match(el.textContent, /Die Fundstelle \[W0123456789\] steht jetzt im Gespräch/);
});

check('Treffer → Quelle: die Liste markiert die Quelle mit Stelle und Datum; „Markierung aufheben“ nimmt sie weg', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, answer());
  await suche(el, 'Lease');
  await klick(el.querySelector('[data-id="W0123456789"]'), 'Quelle');
  assert.deepEqual(ctx.opened, [], 'kein object.open: die Quelle wird im eigenen Container markiert');
  const zeile = el.querySelector('div.t-wissen-quelle.t-wissen-markiert');
  assert.ok(zeile && zeile.dataset.quelle === 'Q-1');
  assert.match(el.textContent, /Treffer \[W0123456789\] · docs\/A\.md > Titel > Lease · Stand 2026-10-20/);
  await klick(el, 'Markierung aufheben');
  assert.equal(el.querySelector('div.t-wissen-quelle.t-wissen-markiert'), null);
});

check('Zitat [W…] ist ein Verweis: Enter hebt den Treffer hervor; eine fremde ID sagt, dass sie nicht in der Suche steht', async()=>{
  const {el} = await mount({type: 'wissen', id: 'speicher'}, answer());
  await suche(el, 'Lease');
  const zitat = el.querySelector('span.t-wissen-zitat');
  assert.ok(zitat && zitat.textContent === '[W0123456789]' && zitat.getAttribute('role') === 'button');
  await zitat.onkeydown({key: 'Enter', preventDefault(){}}); await K.settle();
  assert.ok(el.querySelector('[data-id="W0123456789"]').classList.contains('t-wissen-aktiv'));
  tool.zeigeTreffer('Wfedcba9876'); await K.settle();
  assert.match(el.textContent, /\[Wfedcba9876\] steht nicht in der letzten Suche/);
  assert.equal(el.querySelector('.t-wissen-aktiv'), null);
});

check('Quellen als Liste: Marken in Klartext, 1.900 Abschnitte; die Handlungen im Menü „⋯“', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher', view: 'quellen'}, answer());
  const q = el.querySelector('div.t-wissen-quelle');
  assert.equal(q.dataset.quelle, 'Q-1');
  assert.match(q.textContent, /repo\/docs/); assert.match(q.textContent, /Doku/); assert.match(q.textContent, /Stufe 1/); assert.match(q.textContent, /alle Projekte/);
  assert.match(q.textContent, /1\.900 Abschnitte/);
  assert.equal(el.querySelectorAll('table').length, 0, 'keine Tabelle mehr');
  assert.equal(el.querySelectorAll('button').filter(b=>b.textContent === 'Abschalten').length, 0, 'erst nach dem Menü');
  await klick(el, '⋯');
  await klick(el, 'Abschalten');
  assert.deepEqual(verben(ctx)[0], {type: 'wissen_quelle', verb: 'abschalten', args: {}, id: 'Q-1'});
});

check('Stufe heraufsetzen: Auswahl mit Klartext statt prompt(); Esc schließt, zu niedrig wird abgewiesen, Bestätigen ruft das Verb', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher', view: 'quellen'}, answer());
  await klick(el, '⋯'); await klick(el, 'Stufe heraufsetzen …');
  let feld = el.querySelector('select.t-wissen-stufe-feld');
  assert.equal(feld.value, '2'); assert.match(feld.children[0].textContent, /^Stufe 2 – /);
  assert.equal(knopf(el, 'Abbrechen').type, 'button', 'Enter löst Abbrechen nicht aus');
  el.querySelector('form.t-wissen-stufe-form').onkeydown({key: 'Escape', preventDefault(){}}); await K.settle();
  assert.equal(el.querySelector('select.t-wissen-stufe-feld'), null);
  await klick(el, '⋯'); await klick(el, 'Stufe heraufsetzen …');
  feld = el.querySelector('select.t-wissen-stufe-feld'); feld.value = '1';
  await el.querySelector('form.t-wissen-stufe-form').onsubmit({preventDefault(){}}); await K.settle();
  assert.match(el.textContent, /Heraufsetzen heißt enger: die Stufe muss höher als 1 sein/);
  assert.equal(verben(ctx).length, 0);
  feld.value = '3'; await klick(el, 'Bestätigen');
  assert.deepEqual(verben(ctx)[0], {type: 'wissen_quelle', verb: 'stufe_heraufsetzen', args: {stufe: 3}, id: 'Q-1'});
  assert.equal(el.querySelector('select.t-wissen-stufe-feld'), null);
  assert.match(el.textContent, /Erledigt\./);
});

check('Neu beantragen per Enter; ein Fehler aus ctx.api() steht als ein Satz', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher', view: 'quellen'}, answer());
  await klick(el, '⋯'); await klick(el, 'Neu beantragen …');
  const feld = el.querySelector('select.t-wissen-stufe-feld'); assert.equal(feld.value, '1'); feld.value = '0';
  await el.querySelector('form.t-wissen-stufe-form').onsubmit({preventDefault(){}}); await K.settle();
  assert.deepEqual(verben(ctx)[0], {type: 'wissen_quelle', verb: 'neu_beantragen', args: {stufe: 0}, id: 'Q-1'});
  assert.match(el.textContent, /Antrag liegt im Posteingang/);
  const kaputt = await mount({type: 'wissen', id: 'speicher', view: 'quellen'}, answer({stufe: new Error('object_not_found')}));
  await klick(kaputt.el, '⋯'); await klick(kaputt.el, 'Stufe heraufsetzen …'); await klick(kaputt.el, 'Bestätigen');
  assert.match(kaputt.el.textContent, /Dieses Objekt gibt es nicht mehr/);
  assert.equal(kaputt.el.querySelectorAll('.bad').length, 1, 'ein Hinweis, kein zweiter');
});

check('Antrag geführt (WZ4): was schon da ist, ist nicht wählbar; fester Pfad prüft sofort; vier Schritte bis zum Antrag', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher', view: 'quellen'}, answer());
  await tool.actions().find(a=>a.label === 'Quelle beantragen …').run(); await K.settle();
  assert.match(el.textContent, /Schritt 1 von 4/);
  assert.equal(el.querySelector('[data-vorlage="doku"]').getAttribute('aria-disabled'), 'true', 'docs ist schon freigegeben');
  await el.querySelector('[data-vorlage="logbuch"]').onclick({stopPropagation(){}}); await K.settle();
  assert.equal(verben(ctx)[0].verb, 'quelle_pruefen');
  assert.match(el.textContent, /1 Datei, etwa 40 Abschnitte/);
  assert.equal(knopf(el, 'Weiter').disabled, false);
  await klick(el, 'Weiter'); assert.match(el.textContent, /3 · Wer darf es lesen\?/);
  await klick(el, 'Weiter'); assert.match(el.textContent, /4 · Zusammenfassung/);
  await klick(el, 'Antrag stellen');
  const a = verben(ctx).find(b=>b.verb === 'quelle_beantragen');
  assert.deepEqual(a.args, {adapter: 'logbuch', wurzel: 'repo', pfad: 'docs/LOGBUCH_AGENT_MANAGER.md', muster: '*.md', stufe: 1, projekt: null, personenbezug: false});
  assert.equal(a.id, undefined, 'Typ-Verb ohne Objekt');
  assert.match(el.textContent, /Antrag liegt im Posteingang – dort freigeben/);
  assert.equal(el.querySelector('section.t-wissen-antrag'), null);
});

check('Antrag: ohne Dateien bleibt „Weiter“ gesperrt; Esc bricht ab', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher', view: 'quellen'}, answer({pruefen: {status: 'erledigt', dateien: 0, abschnitte_etwa: 0, ueberschneidung: [], schon_da: false, satz: 'Keine passende Datei unter diesem Pfad.'}}));
  await tool.actions()[0].run(); await K.settle();
  await el.querySelector('[data-vorlage="ordner"]').onclick({stopPropagation(){}}); await K.settle();
  el.querySelector('input.t-wissen-fokus').value = 'notizen';
  await klick(el, 'Prüfen');
  assert.deepEqual(verben(ctx)[0].args, {adapter: 'markdown', wurzel: 'projekt', pfad: 'notizen', muster: '*.md', stufe: 3, projekt: null, personenbezug: true});
  assert.match(el.textContent, /Keine passende Datei/);
  assert.equal(knopf(el, 'Weiter').disabled, true);
  assert.equal(knopf(el, 'Prüfen').type, 'submit', 'Enter prüft');
  el.querySelector('section.t-wissen-antrag').onkeydown({key: 'Escape', preventDefault(){}}); await K.settle();
  assert.equal(el.querySelector('section.t-wissen-antrag'), null);
});

check('Messung (WZ2): view index öffnet den Index oben, Details zeigen die Modell-ID; Nachführen meldet die Zahlen', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher', view: 'index'}, answer());
  assert.equal(el.querySelector('button.t-wissen-tab.on').dataset.ansicht, 'messung');
  assert.ok(el.querySelector('section.t-wissen-index.t-wissen-markiert'));
  assert.match(el.textContent, /100 % eingebettet \(2\.040 von 2\.040\)/); assert.match(el.textContent, /einbetten · fertig/);
  assert.doesNotMatch(el.textContent, /bge-m3@abc/);
  await klick(el.querySelector('section.t-wissen-index'), 'Details');
  assert.match(el.textContent, /bge-m3@abc#modell#1024#e1/);
  await tool.actions().find(a=>a.label === 'Nachführen').run(); await K.settle();
  assert.ok(verben(ctx).some(b=>b.verb === 'nachfuehren'));
  assert.match(el.textContent, /Abgleich: 1 neu, 0 geändert, 0 entfernt · Einbetten: 1 \(fertig\)/);
});

check('Nachmessung: drei Knöpfe je Frage, eine Bewertung zeichnet nur ihre Zeile; Abschließen ohne Urteil sagt, was fehlt', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher', view: 'nachmessung'}, answer());
  assert.ok(el.querySelector('section.t-wissen-nachmessung.t-wissen-markiert'), 'der verlangte Abschnitt steht oben');
  await tool.actions().find(a=>a.label === 'Nachmessung abschließen').run(); await K.settle();
  assert.match(el.textContent, /Erst mindestens eine Frage bewerten/);
  const vorher = el.querySelector('section.t-wissen-index');
  await klick(el, 'getroffen');
  assert.deepEqual(verben(ctx).find(b=>b.verb === 'nachmessung_bewerten').args, {frage_sha256: 'a'.repeat(64), urteil: 'getroffen'});
  assert.equal(el.querySelector('section.t-wissen-index'), vorher, 'der Rest bleibt stehen');
  assert.equal(knopf(el, 'getroffen').getAttribute('aria-pressed'), 'true');
});

check('Suche ohne Treffer im Volltext zeigt den Hinweis des Servers; ohne Hinweis den des Werkzeugs', async()=>{
  const {el} = await mount({type: 'wissen', id: 'speicher'}, answer({suche: {status: 'erledigt', modus: 'volltext', hinweis: 'Nur Volltextsuche (wis_engine_fehlt): Treffer mit anderen Worten können fehlen.', treffer: [], ms: 3, woerter: ['x']}}));
  await suche(el, 'x');
  assert.match(el.textContent, /Nur Volltextsuche \(wis_engine_fehlt\)/); assert.match(el.textContent, /nichts gefunden/);
  const s = await mount({type: 'wissen', id: 'speicher'}, answer({suche: {status: 'erledigt', modus: 'volltext', hinweis: null, treffer: [TREFFER], ms: 3, woerter: ['x']}}));
  assert.match(s.el.textContent, /Noch keine Suche/);
  await suche(s.el, 'x');
  assert.match(s.el.textContent, /Nur Volltextsuche: Treffer mit anderen Worten können fehlen/);
});

check('Vorschläge: Herkunft und Belege als Verweise, „Im Posteingang entscheiden“ öffnet den einen Posteingang; Filter', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher', view: 'vorschlaege'}, answer());
  assert.match(el.textContent, /Lease zuerst/); assert.match(el.textContent, /Agent A-3 · Lauf J-1 · Aufgabe I-1 · Belege \[W0123456789\]/);
  assert.equal(el.querySelectorAll('span.t-wissen-zitat').length, 1);
  await klick(el, 'Im Posteingang entscheiden');
  assert.deepEqual(ctx.opened[0], {type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true});
  await klick(el, 'entschieden');
  assert.match(el.textContent, /In diesem Filter keine Vorschläge/);
});

check('ohne Schalter: der Leerzustand sagt, wie man ihn einschaltet; die Werkbank-Zeile ist dann leer', async()=>{
  const {el} = await mount({type: 'wissen', id: 'speicher'}, ()=>new Error('unknown_object_type'));
  assert.match(el.textContent, /ausgeschaltet \(Schalter „wissen“/);
  assert.deepEqual(tool.actions(), []);
  const aus = await mount({type: 'wissen', id: 'speicher'}, answer({speicher: {type: 'wissen', id: 'speicher', title: 'Wissen', state: 'aus', summary: 's', actions: [], links: [], stand: null, grund: 'wissen_config_invalid:yaml'}}));
  assert.match(aus.el.textContent, /ausgeschaltet .* – wissen_config_invalid:yaml/);
});

check('leer: keine Quellen sagt, was eine Quelle ist, und bietet den Antrag an; eine Quelle aus der Navigation fehlt nicht still', async()=>{
  const leer = (path, body)=>path === '/api/objects' && body.type === 'wissen_quelle' ? {type: 'wissen_quelle', items: []} : answer()(path, body);
  const {el} = await mount({type: 'wissen', id: 'speicher', view: 'quellen', quelle: 'Q-9'}, leer);
  assert.match(el.textContent, /Keine Quellen\. Eine Quelle ist ein Ordner/);
  assert.ok(knopf(el, 'Quelle beantragen …'));
  const da = await mount({type: 'wissen', id: 'speicher', quelle: 'Q-1'}, answer());
  assert.ok(da.el.querySelector('div.t-wissen-quelle.t-wissen-markiert'), 'quelle am Objekt öffnet die Quellen markiert');
  assert.match(da.el.textContent, /Quelle aus der Navigation markiert/);
});

check('Gedächtnis (Vertrag 1.1): Sitzung nur Zustand der Ansicht, Frage und Treffer in der Ablage; nach dem Wechsel sind sie wieder da', async()=>{
  const sitzung = new Map(), ablage = new Map();
  const extra = ()=>({sitzung: {get: (n, v)=>sitzung.has(n) ? sitzung.get(n) : v, set: (n, v)=>sitzung.set(n, v), clear(){}},
                      ablage: {get: async(n, v)=>ablage.has(n) ? ablage.get(n) : v, set: (n, v)=>ablage.set(n, v), clear(){}, flush(){}}});
  const {el} = await mount({type: 'wissen', id: 'speicher'}, answer(), extra());
  await suche(el, 'Lease geheim');
  assert.ok(!JSON.stringify([...sitzung]).includes('geheim'), 'keine Frage in der Sitzung');
  assert.ok(!JSON.stringify([...sitzung]).includes('Vor dem Laden'), 'kein Treffertext in der Sitzung');
  assert.equal(ablage.get('frage'), 'Lease geheim');
  tool.unmount(el);
  const neu = await mount({type: 'wissen', id: 'speicher'}, answer(), extra());
  assert.equal(neu.el.querySelector('input.t-wissen-frage').value, 'Lease geheim');
  assert.ok(neu.el.querySelector('[data-id="W0123456789"]'));
  assert.match(neu.el.textContent, /Treffer von \d\d:\d\d/); assert.ok(knopf(neu.el, 'neu suchen'));
  assert.equal(neu.ctx.calls.filter(c=>c.path === '/api/actions').length, 0, 'nicht neu gesucht');
});

check('Ansicht wechseln meldet object.actions; die Werkbank-Zeile hat die Handlungen der Ansicht (WZ3); Pfeiltasten wechseln', async()=>{
  const {el, ctx} = await mount({type: 'wissen', id: 'speicher'}, answer());
  const gemeldet = gehoert(ctx, 'object.actions');
  assert.deepEqual(tool.actions().map(a=>a.label), ['Neue Suche']);
  await el.querySelector('button.t-wissen-tab.on').onkeydown({key: 'ArrowRight', preventDefault(){}}); await K.settle();
  assert.equal(el.querySelector('button.t-wissen-tab.on').dataset.ansicht, 'quellen');
  assert.deepEqual(gemeldet, [{type: 'wissen', id: 'speicher'}]);
  assert.deepEqual(tool.actions().map(a=>a.label), ['Quelle beantragen …', 'Erstbestückung beantragen']);
  await klick(el, 'Messung');
  assert.deepEqual(tool.actions().map(a=>a.label), ['Nachführen', 'Nachmessung abschließen']);
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
  assert.equal(fehlerSatz(new Error('object_not_found')), 'Dieses Objekt gibt es nicht mehr; die Ansicht wird neu gelesen. (object_not_found)');
  assert.equal(fehlerSatz(''), 'Unbekannter Fehler.');
  assert.deepEqual(stufePruefen('3', 1), {ok: true, stufe: 3}); assert.equal(stufePruefen('1', 1).ok, false); assert.equal(stufePruefen('7').ok, false);
  assert.equal(markierungText({id: 'W1', datei: 'a.md', stelle: 'T', datum: '2026-10-20T10:00:00Z'}), 'Treffer [W1] · a.md > T · Stand 2026-10-20');
  assert.equal(ansichtFuer('index', 'quellen'), 'messung'); assert.equal(ansichtFuer('eigenes'), 'quellen');
  assert.equal(ansichtFuer(undefined, 'vorschlaege'), 'vorschlaege'); assert.equal(ansichtFuer('quatsch', 'auch'), 'suche');
  assert.equal(artText('markdown'), 'Doku'); assert.match(stufeText(0), /^Stufe 0 – /);
  assert.deepEqual(hervorheben('Die Lease holen', ['lease']).filter(t=>t.mark).map(t=>t.text), ['Lease']);
  assert.equal(relevanz(0.5, 1), 0.5); assert.equal(relevanz(1, 0), 0);
  assert.equal(VORLAGEN.length, 8);
  assert.equal(schonDa([QUELLE], VORLAGEN[0].werte), true); assert.equal(schonDa([Object.assign({}, QUELLE, {aktiv: false})], VORLAGEN[0].werte), false);
  assert.deepEqual(argsVon({adapter: 'text', wurzel: 'repo', pfad: 'a', muster: '*.txt', stufe: '2', projekt: '', personenbezug: 1}),
                   {adapter: 'text', wurzel: 'repo', pfad: 'a', muster: '*.txt', stufe: 2, projekt: null, personenbezug: true});
  assert.equal(fortschritt([{urteil: 'getroffen'}, {}]), '1 von 2 Fragen bewertet');
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
