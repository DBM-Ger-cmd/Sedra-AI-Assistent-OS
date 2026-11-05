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
    bolt: ['M13 3L5 13h6l-1 8 8-10h-6z'],
    unknown: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7', 'M12 17h.01']
  };
  const LABELS = {manualTrigger: 'Auslöser', start: 'Start', clock: 'Zeit', set: 'Daten', if: 'Bedingung', router: 'Router', decision: 'Entscheidung', noOp: 'Weitergabe',
    stickyNote: 'Notiz', human: 'Mensch', task: 'Aufgabe', end: 'Ende', bolt: 'Auslöser', unknown: 'Unbekannt'};
  const known = key => Object.prototype.hasOwnProperty.call(ICONS, key);
  // Symbolschlüssel für einen Knoten; meta ist die Prozessangabe, falls vorhanden.
  function key(node, meta){
    if(meta){
      if(meta.kind === 'task') return meta.mode === 'manual' ? 'human' : 'task';
      if(['start', 'decision', 'end'].includes(meta.kind)) return meta.kind;
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
