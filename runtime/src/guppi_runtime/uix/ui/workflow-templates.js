// Eigene Startvorlagen der Prozess-Apps. Inhalte sind SEDRA-eigen (keine Herstellervorlagen) und nur Zeichnungen, nie ausführbar ohne Freigabe.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const M = ()=>root.sedraWorkflowModel;
  function chain(name, kinds, names){
    const doc = {name, nodes: [], connections: {}, settings: {executionOrder: 'v1'}, active: false};
    kinds.forEach((kind, i)=>{const n = M().node(kind, doc.nodes);if(names && names[i])n.name = names[i];n.position = [i * 230, 140];doc.nodes.push(n);});
    for(let i = 0; i + 1 < doc.nodes.length; i++) M().connect(doc, doc.nodes[i].name, doc.nodes[i + 1].name, 0);
    return doc;
  }
  const TEMPLATES = [
    {id: 'pruefkette', title: 'Prüfkette mit zwei Wegen', description: 'Start, Daten setzen, Bedingung prüfen, danach Treffer oder Abweichung.', chips: ['manualTrigger', 'set', 'if', 'noOp'],
      build: ()=>{const d = M().example();d.name = 'Prüfkette mit zwei Wegen';return d;}},
    {id: 'weitergabe', title: 'Einfache Weitergabe', description: 'Start, Daten setzen, Ergebnis weitergeben. Der kürzeste lauffähige Ablauf.', chips: ['manualTrigger', 'set', 'noOp'],
      build: ()=>chain('Einfache Weitergabe', ['manualTrigger', 'set', 'noOp'], ['Start', 'Daten setzen', 'Ergebnis'])},
    {id: 'aufbereitung', title: 'Daten in zwei Schritten aufbereiten', description: 'Zwei Datenschritte hintereinander mit Notiz für die Absicht.', chips: ['manualTrigger', 'set', 'set', 'noOp', 'stickyNote'],
      build: ()=>{const d = chain('Daten aufbereiten', ['manualTrigger', 'set', 'set', 'noOp'], ['Start', 'Rohdaten setzen', 'Felder bereinigen', 'Ergebnis']);
        const note = M().node('stickyNote', d.nodes);note.position = [230, 20];d.nodes.push(note);return d;}}
  ];
  root.sedraWorkflowTemplates = {list: ()=>TEMPLATES.map(t=>({id: t.id, title: t.title, description: t.description, chips: t.chips.slice()})), build: id=>{const t = TEMPLATES.find(x=>x.id === id);if(!t)throw new Error('Unbekannte Vorlage.');return t.build();}};
})();
