// Shared process semantics, stored as standard n8n notes. No course data here.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const PREFIX = 'SEDRA_PROCESS_V1\n';
  const labels = {manual: 'Menschlich', assisted: 'Assistiert', automatable: 'Automatisierungskandidat',
    board: 'Aus Vorlage / Board', proposal: 'Ergänzter Vorschlag', confirmed: 'Bestätigt',
    start: 'Start', task: 'Arbeitsschritt', decision: 'Entscheidung', end: 'Ende', annotation: 'Hinweis', data: 'Ein-/Ausgabe (Daten)', store: 'Datenspeicher'};
  function get(node){
    if(typeof node.notes !== 'string' || !node.notes.startsWith(PREFIX))return null;
    try{return JSON.parse(node.notes.slice(PREFIX.length));}catch(_e){return null;}
  }
  function has(doc){return doc.nodes.some(n=>typeof n.notes === 'string' && n.notes.startsWith(PREFIX));}
  function blank(node){
    return {schema: 1, kind: node.type.endsWith('.manualTrigger') ? 'start' : node.type.endsWith('.if') ? 'decision' : 'task',
      mode: 'manual', source: 'proposal', role_status: 'proposal', core_step: 0,
      supplier: '', input: '', output: '', customer: '', role: '', evidence: '', completion: '', exception: '',
      automation_reason: '', risk: '', original_notes: node.notes || ''};
  }
  function set(node, values){node.notes = PREFIX + JSON.stringify(values);node.notesInFlow = false;}
  function rows(doc){return doc.nodes.map(n=>({node: n, meta: get(n)})).filter(r=>r.meta);}
  function cores(doc){return rows(doc).filter(r=>r.meta.core_step > 0).sort((a, b)=>a.meta.core_step - b.meta.core_step);}
  function coreProjection(doc){
    const nodes = cores(doc).map((r, i)=>{const n = root.sedraWorkflowModel.clone(r.node);n.position = [i * 260, 80];return n;});
    const out = {name: doc.name, nodes, connections: {}};
    for(let i = 0; i < nodes.length - 1; i++)out.connections[nodes[i].name] = {main: [[{node: nodes[i + 1].name, type: 'main', index: 0}]]};
    return out;
  }
  // Lücken in den Prozessangaben: je Schritt fehlende Pflichtangaben (Start und Ende brauchen keinen Input bzw. Output; Hinweise nichts).
  const NEED = {role: 'Rolle', input: 'Eingabe', output: 'Ergebnis', evidence: 'Nachweis', completion: 'Abschlusskriterium'};
  function gaps(doc){
    const items = [];
    rows(doc).forEach(({node, meta})=>{
      if(meta.kind === 'annotation')return;
      const missing = Object.keys(NEED).filter(k=>!(meta[k] || '').trim() && !(k === 'input' && meta.kind === 'start') && !(k === 'output' && meta.kind === 'end'));
      if(missing.length)items.push({name: node.name, fields: missing.map(k=>NEED[k])});
    });
    return {steps: items.length, missing: items.reduce((n, i)=>n + i.fields.length, 0), items};
  }
  root.sedraWorkflowProcess = {PREFIX, labels, get, has, blank, set, rows, cores, coreProjection, gaps};
})();
