const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const box = {crypto: require('node:crypto').webcrypto, TextEncoder};
vm.createContext(box);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/sedra_runtime/uix/ui/workflow-model.js'), 'utf8'), box);
const M = box.sedraWorkflowModel;
vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/sedra_runtime/uix/ui/workflow-process.js'), 'utf8'), box);
const P = box.sedraWorkflowProcess;
const plain = x=>JSON.parse(JSON.stringify(x));

test('sample has a complete true/false branch', ()=>{
  const doc = M.example();
  assert.equal(doc.nodes.length, 5);
  assert.equal(doc.connections['Bedingung prüfen'].main.length, 2);
});
test('unknown metadata survives editor parse and export', ()=>{
  const doc = M.example();doc.future = {keep: ['x']};doc.nodes[1].type = 'unknown.community';
  assert.deepEqual(plain(M.parse(JSON.stringify(doc))), plain(doc));
});
test('rename rewires inputs, outputs and other connection types', ()=>{
  const doc = M.example();
  doc.connections['Manueller Start'].ai_tool = [[{node: 'Felder setzen', type: 'ai_tool', index: 0}]];
  M.rename(doc, 'Felder setzen', 'Daten lesen');
  assert.equal(doc.connections['Manueller Start'].main[0][0].node, 'Daten lesen');
  assert.equal(doc.connections['Manueller Start'].ai_tool[0][0].node, 'Daten lesen');
  assert.ok(doc.connections['Daten lesen']);
});
test('remove cleans every reference without dropping other fields', ()=>{
  const doc = M.example();doc.future = true;M.remove(doc, 'Felder setzen');
  assert.equal(doc.nodes.length, 4);
  assert.equal(doc.connections['Manueller Start'].main[0].length, 0);
  assert.equal(doc.future, true);
});
test('prototype names and ambiguous expression renames are refused', ()=>{
  const doc = M.example();
  assert.throws(()=>M.rename(doc, 'Felder setzen', '__proto__'));
  doc.nodes[1].parameters = {value: '={{ $("Felder setzen").item.json }}'};
  assert.throws(()=>M.rename(doc, 'Felder setzen', 'Another'));
});
test('sharing copy redacts secrets without mutating the original', ()=>{
  const doc = M.example();doc.nodes[1].credentials = {id: 'private'};doc.pinData = {sensitive: true};
  const copy = M.sharing(doc);
  assert.equal(copy.nodes[1].credentials, '[REDACTED]');
  assert.equal(copy.pinData, undefined);
  assert.equal(doc.nodes[1].credentials.id, 'private');
});
test('core projection changes neither positions nor edges in the original', ()=>{
  const doc = M.example();
  doc.nodes.slice(1, 3).forEach((n, i)=>{const meta = P.blank(n);meta.core_step = i + 1;P.set(n, meta);});
  const original = JSON.stringify(doc), projected = P.coreProjection(doc);
  assert.equal(projected.nodes.length, 2);
  projected.nodes[0].position[0] = 999;
  assert.equal(JSON.stringify(doc), original);
});
test('adding process semantics retains existing free notes', ()=>{
  const doc = M.example(), n = doc.nodes[1];n.notes = 'Keep original note';
  P.set(n, P.blank(n));assert.equal(P.get(n).original_notes, 'Keep original note');assert.ok(P.has(doc));
});
