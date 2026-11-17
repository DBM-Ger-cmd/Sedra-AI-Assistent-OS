// Aufbau-Aufsicht des Workflow Studios: gilt für jeden Workflow, der in einem Editor geöffnet wird (n8n Workflows, Szenario Studio,
// Workflow Studio). Beim Öffnen wird ein unruhiger Aufbau (Linien durch Kacheln, Linien übereinander, Kreuzungen und Umwege über der
// Grenze) einmal normalisiert; danach zeigt eine Zeile über der Zeichenfläche den Zustand, und „Aufbau aufräumen“ stellt ihn auf Wunsch
// wieder her (rückgängig machbar). Verbindungen, Knoten und Parameter bleiben unberührt, nur Positionen. Die Messung steht in
// workflow-layout-waechter.js (rein, mit Tests über alle gespeicherten Workflows).
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const W = ()=>root.sedraWorkflowWaechter;
  const geometrie = editor=>editor && editor.style === 'scenario' ? W().CIRCLE : W().TILE;

  // Beim Öffnen: gibt das Dokument mit ruhigem Aufbau zurück (oder dasselbe, wenn es schon ruhig ist). Nie ein Fehler.
  function beimOeffnen(doc, editor){
    try{
      if(!W() || !doc || !doc.nodes || doc.nodes.length < 3) return doc;
      const r = W().besser(doc, geometrie(editor));
      return r.verbessert && !r.vorher.ok ? r.doc : doc;
    }catch(_e){ return doc; }
  }

  // Zustandszeile über der Zeichenfläche; wird in draw() des Editors aufgerufen
  function zeige(editor, doc){
    try{
      if(!W() || !editor || !editor.surface || !doc || !doc.nodes) return;
      let zeile = editor.aufbauZeile;
      if(!zeile || !zeile.isConnected){
        zeile = editor.aufbauZeile = root.document.createElement('p');
        zeile.className = 't-wf-aufbau'; zeile.setAttribute('role', 'status');
        editor.surface.parentElement.insertBefore(zeile, editor.surface);
      }
      const b = W().pruefe(doc, geometrie(editor));
      editor.aufbauBefund = b;
      zeile.className = 't-wf-aufbau ' + (b.ok ? 'ok' : 'unruhig');
      zeile.replaceChildren();
      zeile.append(root.document.createTextNode(b.ok ? 'Aufbau: ruhig' : 'Aufbau unruhig: ' + b.meldungen.join(' ')));
      const sperre = editor.editorMode === 'live' || editor.view === 'core' || editor.view === 'logical';
      if(!b.ok && !sperre){
        const knopf = root.document.createElement('button'); knopf.type = 'button'; knopf.className = 't-wf-aufbau-knopf'; knopf.textContent = 'Aufbau aufräumen';
        knopf.onclick = ()=>aufraeumen(editor);
        zeile.append(knopf);
      }
    }catch(_e){ /* die Aufsicht darf die Zeichenfläche nie stören */ }
  }

  function aufraeumen(editor){
    const r = W().besser(editor.state.doc, geometrie(editor));
    const pos = Object.fromEntries(r.doc.nodes.map(n=>[n.name, n.position]));
    editor.change(()=>{ editor.state.doc.nodes.forEach(n=>{ if(pos[n.name]) n.position = pos[n.name].slice(); }); });
    if(editor.notice) editor.notice(r.befund.ok ? 'Aufbau aufgeräumt.' : 'Aufbau verbessert; ' + r.befund.meldungen.join(' '), !r.befund.ok);
  }

  root.sedraWorkflowAufbau = {beimOeffnen, zeige, aufraeumen};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraWorkflowAufbau;
})();
