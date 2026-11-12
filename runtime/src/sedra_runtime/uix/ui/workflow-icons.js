// Eigener Symbolsatz der Prozess-Apps (24x24, Linienzeichnung). Keine Fremdsymbole, keine Hersteller-Logos.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const NS = 'http://www.w3.org/2000/svg';
  const ICONS = {
    manualTrigger: ['M8 5v14l11-7z'],
    start: ['M8 5v14l11-7z'],
    clock: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M12 7v5l3.5 2'],
    set: ['M4 20h4L19 9l-4-4L4 16z', 'M13 7l4 4'],
    if: ['M5 12h5', 'M10 12l7-6', 'M10 12l7 6', 'M17 3.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z', 'M17 15.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z'],
    router: ['M5 12h5', 'M10 12l7-6', 'M10 12l7 6', 'M17 3.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z', 'M17 15.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z'],
    decision: ['M12 3l9 9-9 9-9-9z'],
    noOp: ['M5 12h14', 'M13 6l6 6-6 6'],
    stickyNote: ['M5 4h14v11l-5 5H5z', 'M14 20v-5h5'],
    human: ['M12 4a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z', 'M5 20a7 7 0 0 1 14 0'],
    task: ['M6 4h12v16H6z', 'M9 9h6', 'M9 13h6'],
    end: ['M5 12l5 5 9-10'],
    data: ['M7 5h14l-4 14H3z'],
    store: ['M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3z', 'M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6', 'M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3'],
    plus: ['M12 5v14', 'M5 12h14'],
    copy: ['M9 9h11v11H9z', 'M5 15V4h11'],
    trash: ['M4 7h16', 'M9 7V4h6v3', 'M6 7l1 13h10l1-13'],
    bolt: ['M13 3L5 13h6l-1 8 8-10h-6z'],
    unknown: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7', 'M12 17h.01'],
    // Weitere Knotenarten (selbst gezeichnet, gleiche Linienstärke): Schlüssel = letzter Teil des n8n-Typs, damit der Import sie ohne Zuordnung findet.
    formTrigger: ['M5 4h14v16H5z', 'M8 9h8', 'M8 13h8', 'M8 17h4'],
    extractFromFile: ['M6 3h8l4 4v14H6z', 'M14 3v4h4', 'M9 13h6', 'M9 17h6'],
    code: ['M9 7l-5 5 5 5', 'M15 7l5 5-5 5', 'M13.5 5l-3 14'],
    dataTable: ['M4 5h16v14H4z', 'M4 10h16', 'M4 15h16', 'M10 5v14'],
    informationExtractor: ['M4 6h10', 'M4 12h7', 'M4 18h10', 'M16 10a3 3 0 1 0 0 .01', 'M18.5 12.5L21 15'],
    lmChatAnthropic: ['M12 4a6 6 0 0 0-6 6c0 2 1 3 1 5h10c0-2 1-3 1-5a6 6 0 0 0-6-6z', 'M9 19h6', 'M10 22h4'],
    lmChatOpenAi: ['M12 4a6 6 0 0 0-6 6c0 2 1 3 1 5h10c0-2 1-3 1-5a6 6 0 0 0-6-6z', 'M9 19h6', 'M10 22h4'],
    lmChatOllama: ['M12 4a6 6 0 0 0-6 6c0 2 1 3 1 5h10c0-2 1-3 1-5a6 6 0 0 0-6-6z', 'M9 19h6', 'M10 22h4'],
    agent: ['M12 3v3', 'M6 8h12v10H6z', 'M9.5 12h.01', 'M14.5 12h.01', 'M9 15h6'],
    webhook: ['M8 8a4 4 0 1 1 5 3.8L9 19', 'M5 19a2.5 2.5 0 1 0 0 .01', 'M19 19a2.5 2.5 0 1 0 0 .01', 'M7.5 19h9'],
    httpRequest: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M3 12h18', 'M12 3c3 3 3 15 0 18', 'M12 3c-3 3-3 15 0 18'],
    scheduleTrigger: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M12 7v5l3.5 2'],
    switch: ['M4 12h5', 'M9 12l8-7', 'M9 12h8', 'M9 12l8 7'],
    merge: ['M4 6h6l4 6-4 6H4', 'M14 12h6', 'M17 9l3 3-3 3'],
    filter: ['M4 5h16l-6 8v6l-4-2v-4z'],
    wait: ['M7 3h10', 'M7 21h10', 'M8 3c0 5 8 5 8 9s-8 4-8 9'],
    emailSend: ['M4 6h16v12H4z', 'M4 7l8 6 8-6'],
    aggregate: ['M5 5h6v6H5z', 'M13 13h6v6h-6z', 'M11 8h5v5', 'M8 11v5h5'],
    executeWorkflow: ['M4 5h7v6H4z', 'M13 13h7v6h-7z', 'M11 8h3v8', 'M14 16h-1']
  };
  const LABELS = {manualTrigger: 'Auslöser', start: 'Start', clock: 'Zeit', set: 'Daten', if: 'Bedingung', router: 'Router', decision: 'Entscheidung', noOp: 'Weitergabe',
    stickyNote: 'Notiz', human: 'Mensch', task: 'Aufgabe', end: 'Ende', data: 'Daten', store: 'Speicher', plus: 'Hinzufügen', copy: 'Duplizieren', trash: 'Löschen', bolt: 'Auslöser', unknown: 'Unbekannt',
    formTrigger: 'Formular', extractFromFile: 'PDF lesen', code: 'Code', dataTable: 'Tabelle', informationExtractor: 'Informationen ziehen', lmChatAnthropic: 'Sprachmodell',
    lmChatOpenAi: 'Sprachmodell', lmChatOllama: 'Sprachmodell', agent: 'Agent', webhook: 'Webhook', httpRequest: 'Web-Anfrage', scheduleTrigger: 'Zeitplan', switch: 'Mehrere Wege',
    merge: 'Zusammenführen', filter: 'Filter', wait: 'Warten', emailSend: 'E-Mail', aggregate: 'Zusammenfassen', executeWorkflow: 'Workflow aufrufen'};
  const known = key => Object.prototype.hasOwnProperty.call(ICONS, key);
  // Symbolschlüssel für einen Knoten; meta ist die Prozessangabe, falls vorhanden.
  function key(node, meta){
    if(meta){
      if(meta.kind === 'task') return meta.mode === 'manual' ? 'human' : 'task';
      if(['start', 'decision', 'end', 'data', 'store'].includes(meta.kind)) return meta.kind;
      return 'task';
    }
    const last = String((node && node.type) || '').split('.').pop();
    return known(last) ? last : 'unknown';
  }
  // Fügt das Symbol als <g> in einen SVG-Elternknoten ein; x/y ist die Mitte, size die Kantenlänge.
  function append(parent, name, x, y, size){
    const k = known(name) ? name : 'unknown', scale = (size || 24) / 24;
    const g = document.createElementNS(NS, 'g');
    g.setAttribute('class', 't-wf-icon');
    g.setAttribute('transform', `translate(${x - 12 * scale} ${y - 12 * scale}) scale(${scale})`);
    g.setAttribute('aria-hidden', 'true');
    ICONS[k].forEach(d=>{const p = document.createElementNS(NS, 'path');p.setAttribute('d', d);g.append(p);});
    parent.append(g);
    return g;
  }
  root.sedraWorkflowIcons = {key, append, known, label: name=>LABELS[known(name) ? name : 'unknown'], names: ()=>Object.keys(ICONS)};
})();
