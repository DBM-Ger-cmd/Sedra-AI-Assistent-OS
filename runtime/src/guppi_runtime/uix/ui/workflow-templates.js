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
    {id: 'pruefkette', title: 'Muster B: Prüfkette mit zwei Wegen', description: 'Auslöser, Bedingung (Raute), danach Treffer oder Abweichung. Der Ablauf wählt seinen Weg selbst.', chips: ['manualTrigger', 'set', 'if', 'noOp'],
      build: ()=>{const d = M().example();d.name = 'Prüfkette mit zwei Wegen';return d;}},
    {id: 'weitergabe', title: 'Muster A: Auslöser, dann Aktion', description: 'Auslöser, Daten setzen, Ergebnis weitergeben. Der einfachste, robusteste Baustein ohne Verzweigung.', chips: ['manualTrigger', 'set', 'noOp'],
      build: ()=>chain('Einfache Weitergabe', ['manualTrigger', 'set', 'noOp'], ['Start', 'Daten setzen', 'Ergebnis'])},
    {id: 'aufbereitung', title: 'Daten in zwei Schritten aufbereiten', description: 'Zwei Datenschritte hintereinander mit Notiz für die Absicht.', chips: ['manualTrigger', 'set', 'set', 'noOp', 'stickyNote'],
      build: ()=>{const d = chain('Daten aufbereiten', ['manualTrigger', 'set', 'set', 'noOp'], ['Start', 'Rohdaten setzen', 'Felder bereinigen', 'Ergebnis']);
        const note = M().node('stickyNote', d.nodes);note.position = [230, 20];d.nodes.push(note);return d;}}
    ,{id: 'muster-c', title: 'Muster C: Auslöser, KI-Schritt, Aktion (Prozessmodell)', description: 'Beschreibt einen KI-Schritt mit Prüfung durch einen Menschen. Nur Darstellung: ein KI-Knoten ist nicht ausführbar.', chips: ['start', 'task', 'human', 'end'],
      build: ()=>{
        const P = root.sedraWorkflowProcess, doc = chain('KI-Schritt mit Prüfung', ['manualTrigger', 'noOp', 'noOp', 'noOp'], ['Anfrage erfassen', 'Anfrage klassifizieren', 'Entwurf prüfen', 'Ergebnis weitergeben']);
        const spec = [['start', 'manual', 'Fachstelle', ''], ['task', 'assisted', 'KI-Schritt', 'Ein Sprachmodell klassifiziert oder entwirft; das Ergebnis ist ein Vorschlag.'], ['task', 'manual', 'Prüfende Person', 'Der Entwurf wird fachlich geprüft und freigegeben.'], ['end', 'automatable', 'Fachstelle', '']];
        doc.nodes.forEach((n, i)=>{const meta = P.blank(n);Object.assign(meta, {kind: spec[i][0], mode: spec[i][1], role: spec[i][2], risk: spec[i][3], core_step: i + 1, source: 'proposal'});P.set(n, meta);n.disabled = true;});
        return doc;
      }}
  ];
  root.sedraWorkflowTemplates = {list: ()=>TEMPLATES.map(t=>({id: t.id, title: t.title, description: t.description, chips: t.chips.slice()})), build: id=>{const t = TEMPLATES.find(x=>x.id === id);if(!t)throw new Error('Unbekannte Vorlage.');return t.build();}};
})();
