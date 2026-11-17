// Aufbau-Wächter: gilt für jeden Workflow. Synthetische Fälle plus alle gespeicherten Workflows des Projekts (wenn vorhanden).
const test = require('node:test'), assert = require('node:assert/strict'), fs = require('fs'), path = require('path');
const U = '../src/sedra_runtime/uix/ui/';
const L = require(U + 'workflow-layout.js'), W = require(U + 'workflow-layout-waechter.js'), A = require(U + 'workflow-aufbau.js');

const knoten = (name, type = 'noOp', pos = [0, 0]) => ({name, type: 'n8n-nodes-base.' + type, position: pos});
const kante = (doc, a, b, i = 0) => { doc.connections[a] ??= {}; doc.connections[a].main ??= []; (doc.connections[a].main[i] ??= []).push({node: b}); };
const verwirrt = () => {                                    // absichtlich wirr gelegt: Rücklauf quer, Zeilen vertauscht
  const d = {nodes: [knoten('A', 'manualTrigger', [0, 0]), knoten('B', 'noOp', [600, 300]), knoten('C', 'noOp', [200, 0]), knoten('D', 'if', [400, 300]), knoten('E', 'noOp', [100, 300]), knoten('F', 'noOp', [700, 0])], connections: {}};
  kante(d, 'A', 'B'); kante(d, 'B', 'C'); kante(d, 'C', 'D'); kante(d, 'D', 'E'); kante(d, 'D', 'F', 1); kante(d, 'A', 'D'); kante(d, 'E', 'F');
  return d;
};

test('Messung zählt Kreuzungen, Überlappungen und Linien durch Kacheln', () => {
  const k = [{n: 'X', r: [100, 0, 96, 130]}];
  const kreuz = W.pruefeWege([{von: 'a', nach: 'b', punkte: [[0, 50], [300, 50]]}, {von: 'c', nach: 'd', punkte: [[150, 0], [150, 100]]}], [], {});
  assert.equal(kreuz.kreuzungen, 1);
  const ueber = W.pruefeWege([{von: 'a', nach: 'b', punkte: [[0, 50], [300, 50]]}, {von: 'c', nach: 'd', punkte: [[100, 50], [250, 50]]}], [], {});
  assert.equal(ueber.ueberlappungen, 1); assert.equal(ueber.ok, false);
  const durch = W.pruefeWege([{von: 'a', nach: 'b', punkte: [[0, 50], [300, 50]]}], k, {});
  assert.equal(durch.durchKnoten, 1); assert.equal(durch.ok, false);
});

test('ein wirrer Aufbau wird nie schlechter, Verbindungen und Knoten bleiben unverändert', () => {
  const d = verwirrt(), vorher = JSON.stringify(d), r = W.besser(d);
  assert.equal(JSON.stringify(d), vorher);                                     // Eingabe unberührt
  assert.deepEqual(r.doc.connections, d.connections);
  assert.deepEqual(r.doc.nodes.map(n => n.name), d.nodes.map(n => n.name));
  assert.ok(r.befund.wert <= r.vorher.wert);
});

test('beimOeffnen lässt ruhige Aufbauten stehen und beruhigt unruhige ohne Datenverlust', () => {
  const ruhig = L.logisch(verwirrt());
  assert.equal(A.beimOeffnen(ruhig, {style: 'n8n'}), ruhig);
  const d = verwirrt(), neu = A.beimOeffnen(d, {style: 'n8n'});
  assert.deepEqual(neu.connections, d.connections);
});

test('jeder gespeicherte Workflow des Projekts ist nach dem Öffnen ruhig', () => {
  const dir = path.resolve(__dirname, '../../workspace/SEDRA_OS/runtime_data/workflows');
  if (!fs.existsSync(dir)) return;
  const unruhig = [];
  for (const d of fs.readdirSync(dir)) {
    if (!d.startsWith('WF-')) continue;
    const dateien = fs.readdirSync(path.join(dir, d)).filter(f => /^0.*\.json$/.test(f)).sort();
    if (!dateien.length) continue;
    const w = JSON.parse(fs.readFileSync(path.join(dir, d, dateien[dateien.length - 1]), 'utf8')).workflow;
    if (!w || !w.nodes || w.nodes.length < 3) continue;
    const nachher = W.pruefe(A.beimOeffnen(w, {style: 'n8n'}));
    if (!nachher.ok) unruhig.push(w.name + ': ' + nachher.meldungen.join(' '));
  }
  assert.deepEqual(unruhig, []);
});
