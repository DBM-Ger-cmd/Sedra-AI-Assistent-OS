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
  root.sedraWorkflowProcess = {PREFIX, labels, get, has, blank, set, rows, cores, coreProjection};
})();
