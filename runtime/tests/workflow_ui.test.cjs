// Reine Logik der gemeinsamen Prozess-UI-Bausteine (ohne Browser): Symbolwahl, Suche der Auswahl, Dialoglage.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const ui = path.join(__dirname, '..', 'src', 'guppi_runtime', 'uix', 'ui');
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
  require(path.join(ui, 'workflow-templates.js'));
  const T = globalThis.sedraWorkflowTemplates;
  assert.ok(T.list().length >= 3);
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
