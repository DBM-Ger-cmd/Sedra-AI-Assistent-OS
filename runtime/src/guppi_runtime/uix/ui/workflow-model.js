// Shared editor model: keep unknown n8n JSON fields and connection kinds intact.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const clone = value=>JSON.parse(JSON.stringify(value));
  const id = ()=>root.crypto && root.crypto.randomUUID ? root.crypto.randomUUID() : 'n-' + Date.now() + '-' + Math.random().toString(16).slice(2);
  const types = [
    ['manualTrigger', 'Manueller Start', 1], ['set', 'Felder setzen', 3.4],
    ['if', 'Bedingung prüfen', 2.2], ['noOp', 'Weitergeben', 1], ['stickyNote', 'Notiz', 1]
  ];
  function parameters(type){
    if(type === 'set') return {assignments: {assignments: [{id: id(), name: 'text', value: 'Hallo aus SEDRA', type: 'string'}]}, options: {}};
    if(type === 'if') return {conditions: {options: {caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2}, conditions: [{id: id(), leftValue: '={{ $json.text }}', rightValue: 'Hallo aus SEDRA', operator: {type: 'string', operation: 'equals'}}], combinator: 'and'}, options: {}};
    if(type === 'stickyNote') return {content: 'Prozess vor Tool. Menschliche Freigaben bleiben bei SEDRA.', width: 240, height: 100};
    return {};
  }
  function node(type, nodes){
    const row = types.find(t=>t[0] === type);
    if(!row) throw new Error('Unbekannter Knotentyp.');
    let name = row[1], n = 2;
    while(nodes.some(x=>x.name === name)) name = row[1] + ' ' + n++;
    return {id: id(), name, type: 'n8n-nodes-base.' + type, typeVersion: row[2], position: [nodes.length * 260, 120], parameters: parameters(type)};
  }
  function example(){
    const nodes = [];
    ['manualTrigger', 'set', 'if', 'noOp', 'noOp'].forEach(t=>nodes.push(node(t, nodes)));
    nodes[3].name = 'Treffer anzeigen'; nodes[3].position = [780, 20];
    nodes[4].name = 'Abweichung anzeigen'; nodes[4].position = [780, 240];
    const doc = {name: 'SEDRA · Erster n8n-Workflow', nodes, connections: {}, settings: {executionOrder: 'v1'}, active: false};
    connect(doc, nodes[0].name, nodes[1].name, 0); connect(doc, nodes[1].name, nodes[2].name, 0);
    connect(doc, nodes[2].name, nodes[3].name, 0); connect(doc, nodes[2].name, nodes[4].name, 1);
    return doc;
  }
  function connect(doc, from, to, branch){
    if(from === to || !doc.nodes.some(n=>n.name === from) || !doc.nodes.some(n=>n.name === to)) throw new Error('Verbindung braucht zwei verschiedene Knoten.');
    const outputs = doc.connections[from] || (doc.connections[from] = {});
    const main = outputs.main || (outputs.main = []);
    while(main.length <= branch) main.push([]);
    if(!main[branch].some(e=>e.node === to && e.type === 'main' && e.index === 0)) main[branch].push({node: to, type: 'main', index: 0});
  }
  function remove(doc, name){
    doc.nodes = doc.nodes.filter(n=>n.name !== name); delete doc.connections[name];
    Object.values(doc.connections).forEach(out=>Object.keys(out).forEach(kind=>{
      out[kind] = out[kind].map(branch=>branch.filter(e=>e.node !== name));
    }));
  }
  function rename(doc, old, name){
    name = name.trim();
    if(!name || name.length > 200 || ['__proto__', 'constructor', 'prototype'].includes(name) || doc.nodes.some(n=>n.name === name && n.name !== old)) throw new Error('Knotenname fehlt, ist reserviert oder schon vergeben.');
    if(old === name) return;
    if(doc.nodes.some(n=>JSON.stringify(n.parameters).includes('$node') || JSON.stringify(n.parameters).includes('$('))) throw new Error('Namensreferenzen in Ausdrücken zuerst prüfen; Umbenennen hier gesperrt.');
    const target = doc.nodes.find(n=>n.name === old); target.name = name;
    if(Object.prototype.hasOwnProperty.call(doc.connections, old)){
      doc.connections[name] = doc.connections[old]; delete doc.connections[old];
    }
    Object.values(doc.connections).forEach(out=>Object.values(out).forEach(branches=>branches.forEach(b=>b.forEach(e=>{ if(e.node === old) e.node = name; }))));
  }
  function parse(text){
    if(new TextEncoder().encode(text).length > 1000000) throw new Error('Datei ist größer als 1 MB.');
    const doc = JSON.parse(text.replace(/^\uFEFF/, ''));
    if(!doc || Array.isArray(doc) || !Array.isArray(doc.nodes) || !doc.connections || typeof doc.connections !== 'object' || !doc.name) throw new Error('Eine einzelne n8n-Workflow-Datei mit name, nodes und connections wird benötigt.');
    return doc;
  }
  function sharing(doc){
    const secret = /password|secret|token|authorization|api.?key|credential|authentication|header/i;
    const clean = value=>Array.isArray(value) ? value.map(clean) : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).map(([k, v])=>[k, secret.test(k) ? '[REDACTED]' : clean(v)])) : value;
    const out = clean(doc); delete out.pinData; delete out.staticData; return out;
  }
  root.sedraWorkflowModel = {clone, types, node, example, connect, remove, rename, parse, sharing};
})();
