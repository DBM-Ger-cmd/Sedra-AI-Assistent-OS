// Harness-Shell, Workflow Studio: gemeinsame Helfer der Teile (Prozessangaben, offene Schritte, Katalog-Zahlen).
// Teil von workflow_studio.js: alles hier ist rein oder liest nur. Eigene Texte einsprachig deutsch.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  // Die Prozessangaben, die je Schritt fehlen dürfen (wie ui/workflow-process.js). Start braucht keine Eingabe, Ende kein Ergebnis.
  const ANGABEN = [['role', 'Rolle'], ['input', 'Eingabe'], ['output', 'Ergebnis'], ['evidence', 'Nachweis'], ['completion', 'Abschlusskriterium']];

  // Die Angaben eines Knotens: die gespeicherten, oder für einen Knoten ohne Angaben eine leere Vorlage (P.blank). So gilt der Assistent für jeden Workflow.
  function angabenVon(node){
    const P = root.sedraWorkflowProcess;
    return P.get(node) || P.blank(node);
  }

  // Ein Knoten zählt als Schritt, wenn er kein Notiz-Zettel ist (der bleibt ohne Angaben).
  function istSchritt(node){ return !String(node.type || '').endsWith('.stickyNote'); }

  // Offene Angaben je Schritt aus einem Workflow-Dokument. Rein: liest nur.
  function luecken(doc){
    const P = root.sedraWorkflowProcess;
    if(!P || !doc) return [];
    return (doc.nodes || []).filter(istSchritt).map(node=>{
      const meta = angabenVon(node);
      if(meta.kind === 'annotation') return null;
      const fehlt = ANGABEN.filter(([k])=>!(meta[k] || '').trim() && !(k === 'input' && meta.kind === 'start') && !(k === 'output' && meta.kind === 'end'));
      return {node, name: node.name, fehlt};
    }).filter(x=>x && x.fehlt.length);
  }

  // Alle gespeicherten Workflows mit ihrer Zahl offener Angaben. Liest nur; ein Workflow, der nicht lädt, zählt als „nicht geprüft“.
  async function workflowsZaehlen(api){
    const liste = await api('/api/objects', {method: 'POST', body: {type: 'workflow', id: 'alle'}});
    const eintraege = [];
    for(const r of (liste.items || [])){
      try{
        const rec = r.workflow && r.execution ? r : await api('/api/objects', {method: 'POST', body: {type: 'workflow', id: r.id}});
        const laufbar = !!(rec.execution && rec.execution.executable);
        eintraege.push({id: r.id, title: r.title, revision: r.revision, laufbar, offen: laufbar ? 0 : luecken(rec.workflow).length, geprueft: true});
      }catch(_e){ eintraege.push({id: r.id, title: r.title, revision: r.revision, offen: 0, geprueft: false}); }
    }
    return eintraege;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.workflow_studio_geteilt = {d, ANGABEN, angabenVon, istSchritt, luecken, workflowsZaehlen};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.workflow_studio_geteilt;
})();
