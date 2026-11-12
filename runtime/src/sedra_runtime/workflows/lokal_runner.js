'use strict';
// Der Rechenkern des SEDRA-Eigenablaufs (workflows/lokal.py): wertet n8n-Ausdrücke und Code-Knoten in einer abgeschotteten Umgebung aus.
// Läuft mit `node --permission` (kein Dateizugriff, keine Kindprozesse, keine Worker). Daten gehen nur als Text hinein und heraus;
// im Sandkasten gibt es kein process, kein require, kein fetch und kein eval (codeGeneration aus). Je Aufgabe ein frischer Kontext.
const vm = require('node:vm');

const BOOTSTRAP = `
(function(){
  const job = JSON.parse(__job);
  const NODES = job.nodes, ITEMS = job.items, INDEX = job.index;
  const hole = (name, b) => {
    if(!Object.prototype.hasOwnProperty.call(NODES, name)) throw new Error("Der Knoten '" + name + "' hat in diesem Lauf noch keine Daten");
    return NODES[name][b === undefined ? 0 : b] || [];
  };
  globalThis.$ = function(name){
    return {first: b => hole(name, b)[0], last: b => { const a = hole(name, b); return a[a.length - 1]; }, all: b => hole(name, b),
            get item(){ return hole(name)[INDEX]; }};
  };
  globalThis.$input = {all: () => ITEMS, first: () => ITEMS[0], last: () => ITEMS[ITEMS.length - 1], get item(){ return ITEMS[INDEX]; }};
  globalThis.$items = () => ITEMS;
  globalThis.$itemIndex = INDEX; globalThis.$runIndex = 0;
  globalThis.$json = ITEMS[INDEX] ? ITEMS[INDEX].json : (ITEMS[0] ? ITEMS[0].json : {});
  globalThis.$now = new Date(job.now); globalThis.$today = new Date(job.now);
})();
`;

function ausfuehren(task, items, nodes, now) {
  const sandbox = Object.create(null);
  sandbox.__job = JSON.stringify({nodes, items: task.items || items, index: task.index || 0, now});
  const ctx = vm.createContext(sandbox, {codeGeneration: {strings: false, wasm: false}});
  new vm.Script(BOOTSTRAP).runInContext(ctx, {timeout: 2000});
  const body = task.kind === 'expr' ? 'return (' + task.source + '\n);' : task.source;
  const code = '(function(){ "use strict"; const __r = (function(){' + body + '\n})();' +
    ' return JSON.stringify(__r === undefined ? null : __r, (k, v) => (typeof v === "number" && !isFinite(v)) ? null : (typeof v === "bigint" ? Number(v) : v)); })()';
  const text = new vm.Script(code, {filename: 'sedra-ausdruck'}).runInContext(ctx, {timeout: task.timeout || 3000});
  return text === undefined ? null : JSON.parse(text);
}

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => { raw += c; });
process.stdin.on('end', () => {
  let job;
  try { job = JSON.parse(raw); } catch (e) { process.stdout.write(JSON.stringify({fehler: 'auftrag_ungueltig'})); return; }
  const now = new Date().toISOString();
  const ergebnisse = job.tasks.map(task => {
    try { return {ok: true, wert: ausfuehren(task, job.items || [], job.nodes || {}, now)}; }
    catch (e) { return {ok: false, fehler: String(e && e.message ? e.message : e).slice(0, 400)}; }
  });
  process.stdout.write(JSON.stringify({ergebnisse}));
});
