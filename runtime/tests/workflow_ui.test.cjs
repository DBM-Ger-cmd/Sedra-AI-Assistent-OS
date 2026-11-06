// Reine Logik der gemeinsamen Prozess-UI-Bausteine (ohne Browser): Symbolwahl, Suche der Auswahl, Dialoglage.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const ui = path.join(__dirname, '..', 'src', 'sedra_runtime', 'uix', 'ui');
for (const f of ['workflow-icons.js', 'workflow-dialog.js', 'workflow-picker.js']) require(path.join(ui, f));
const I = globalThis.sedraWorkflowIcons, D = globalThis.sedraWorkflowDialog, P = globalThis.sedraWorkflowPicker;

test('Symbolschluessel folgt Knotentyp und Prozessangabe', () => {
  assert.equal(I.key({type: 'n8n-nodes-base.set'}, null), 'set');
  assert.equal(I.key({type: 'n8n-nodes-base.if'}, null), 'if');
  assert.equal(I.key({type: 'n8n-nodes-base.frei.erfunden'}, null), 'unknown');
  assert.equal(I.key({type: 'x'}, {kind: 'task', mode: 'manual'}), 'human');
  assert.equal(I.key({type: 'x'}, {kind: 'task', mode: 'assisted'}), 'task');
  assert.equal(I.key({type: 'x'}, {kind: 'decision'}), 'decision');
});

test('jedes Symbol hat Beschriftung und Zeichnung', () => {
  for (const name of I.names()) { assert.ok(I.known(name)); assert.ok(I.label(name).length > 0); }
  assert.equal(I.label('gibt-es-nicht'), I.label('unknown'));
});

test('Auswahl: Suche ignoriert Gross-/Kleinschreibung und Umlaute, gruppiert nach Kategorie', () => {
  const items = [
    {label: 'Auslöser', category: 'Start', hint: 'Manueller Start'},
    {label: 'Daten bearbeiten', category: 'Daten'},
    {label: 'Bedingung', category: 'Ablauf', keywords: 'if router'},
    {label: 'Weitergabe', category: 'Ablauf'}
  ];
  assert.equal(P.filter(items, '').length, 3);
  assert.deepEqual(P.filter(items, 'AUSLOSER').map(g => g.category), ['Start']);
  assert.deepEqual(P.filter(items, 'router')[0].items.map(i => i.label), ['Bedingung']);
  assert.deepEqual(P.filter(items, 'zzz'), []);
  assert.equal(P.filter(items, 'daten bearbeiten')[0].items.length, 1);
});

test('Dialog bleibt im Host und weicht aus, wenn rechts kein Platz ist', () => {
  const host = {w: 800, h: 500}, size = {w: 320, h: 260};
  const right = D.place(host, size, {x: 100, y: 200, w: 72, h: 72});
  assert.ok(right.left >= 172 && right.left + size.w <= host.w);
  const flip = D.place(host, size, {x: 700, y: 200, w: 72, h: 72});
  assert.ok(flip.left + size.w <= 700 && flip.left >= 12);
  const low = D.place(host, size, {x: 100, y: 490, w: 72, h: 72});
  assert.ok(low.top + size.h <= host.h);
  const centred = D.place(host, size, null);
  assert.equal(centred.left, 240);
});

test('Vorlagen: jede baut einen gueltigen Ablauf ohne Rechte', () => {
  require(path.join(ui, 'workflow-model.js'));
  require(path.join(ui, 'workflow-process.js'));
  require(path.join(ui, 'workflow-templates.js'));
  const T = globalThis.sedraWorkflowTemplates;
  assert.ok(T.list().length >= 4);
  const c = T.build('muster-c');
  assert.ok(c.nodes.every(n => n.disabled === true && n.notes.startsWith('SEDRA_PROCESS_V1')), 'Prozessmodell ist deaktiviert');
  for (const t of T.list()) {
    const doc = T.build(t.id);
    const names = new Set(doc.nodes.map(n => n.name));
    assert.equal(names.size, doc.nodes.length, 'Namen eindeutig');
    assert.equal(doc.active, false);
    for (const [from, out] of Object.entries(doc.connections)) {
      assert.ok(names.has(from));
      for (const branches of out.main) for (const e of branches) assert.ok(names.has(e.node));
    }
    assert.ok(doc.nodes.some(n => n.type.endsWith('.manualTrigger')) || doc.nodes.length);
  }
  assert.throws(() => T.build('gibt-es-nicht'));
});

test('Prozessangaben: Luecken werden je Schritt benannt, Start braucht keine Eingabe', () => {
  require(path.join(ui, 'workflow-model.js'));
  require(path.join(ui, 'workflow-process.js'));
  const P = globalThis.sedraWorkflowProcess, M = globalThis.sedraWorkflowModel;
  const doc = {name: 'x', nodes: [M.node('manualTrigger', []), M.node('noOp', [])], connections: {}};
  doc.nodes[0].name = 'Anfrage erfassen';
  const start = P.blank(doc.nodes[0]); start.kind = 'start'; start.role = 'Fachstelle'; start.output = 'Vorgang'; start.evidence = 'Eintrag'; start.completion = 'erfasst';
  P.set(doc.nodes[0], start);
  const task = P.blank(doc.nodes[1]); task.role = 'Prüfung'; P.set(doc.nodes[1], task);
  const g = P.gaps(doc);
  assert.equal(g.steps, 1);
  assert.deepEqual(g.items[0].fields, ['Eingabe', 'Ergebnis', 'Nachweis', 'Abschlusskriterium']);
  const full = Object.assign({}, task, {input: 'a', output: 'b', evidence: 'c', completion: 'd'}); P.set(doc.nodes[1], full);
  assert.equal(P.gaps(doc).missing, 0);
});

test('Parameteransicht: Vorschau rechnet Felder setzen und Bedingung wie das Ausfuehrungsprofil', () => {
  require(path.join(ui, 'workflow-model.js'));
  require(path.join(ui, 'workflow-ndv.js'));
  const N = globalThis.sedraWorkflowNdv, M = globalThis.sedraWorkflowModel;
  assert.equal(N.resolve('={{ $json.a.b }}', {a: {b: 5}}), 5);
  assert.equal(N.resolve('={{ $json.__proto__.x }}', {}), undefined);
  assert.equal(N.resolve('fest', {}), 'fest');
  const doc = M.example();                      // Start -> Felder setzen -> Bedingung -> Treffer / Abweichung
  const sim = N.simulate(doc, {text: 'egal'});
  assert.deepEqual(sim.get('Felder setzen').outs[0], {text: 'Hallo aus SEDRA'});
  assert.equal(sim.get('Treffer anzeigen').input.text, 'Hallo aus SEDRA');
  assert.equal(sim.has('Abweichung anzeigen'), false, 'der Nein-Weg bekommt keinen Eintrag');
  const set = doc.nodes[1]; set.parameters.assignments.assignments[0].value = 'anders';
  const sim2 = N.simulate(doc, {});
  assert.ok(sim2.has('Abweichung anzeigen') && !sim2.has('Treffer anzeigen'));
  assert.equal(N.previewIf({conditions: {conditions: [{leftValue: 5, rightValue: 3, operator: {type: 'number', operation: 'gt'}}], combinator: 'and', options: {}}}, {}), true);
  assert.equal(N.previewIf({conditions: {conditions: [{leftValue: 'ABC', rightValue: 'abc', operator: {type: 'string', operation: 'equals'}}], combinator: 'and', options: {caseSensitive: false}}}, {}), true);
  assert.equal(N.previewSet({includeOtherFields: true, assignments: {assignments: [{name: 'n', value: '={{ $json.x }}', type: 'string'}]}}, {x: 1, y: 2}).y, 2);
});

test('Parameteransicht: Pruefung lehnt ab, was das Ausfuehrungsprofil ablehnt', () => {
  require(path.join(ui, 'workflow-ndv.js'));
  const N = globalThis.sedraWorkflowNdv;
  const set = rows => ({assignments: {assignments: rows}});
  assert.throws(() => N.check('set', set([])), /Mindestens ein Feld/);
  assert.throws(() => N.check('set', set([{name: '1x', value: 'a', type: 'string'}])), /ungültig/);
  assert.throws(() => N.check('set', set([{name: 'a', value: '={{ process.env.X }}', type: 'string'}])), /nicht erlaubt/);
  assert.throws(() => N.check('set', set([{name: 'a', value: 'text', type: 'number'}])), /Zahl/);
  assert.doesNotThrow(() => N.check('set', set([{name: 'a', value: '={{ $json.b }}', type: 'number'}])));
  assert.throws(() => N.check('if', {conditions: {conditions: []}}), /Mindestens eine Bedingung/);
  assert.throws(() => N.check('if', {conditions: {conditions: [{operator: {type: 'string', operation: 'gt'}}]}}), /Operator/);
});
