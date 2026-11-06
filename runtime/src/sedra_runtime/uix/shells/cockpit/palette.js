// Cockpit shell – the palette (Strg+K) and the router of the one input (COCKPIT_MODUL_v1 rule 1).
// There is no second permanent field: the Gespräch is the input, and a short navigation phrase opens a place instead of asking SEDRA.
// routeText() and matchPlaces() are pure, as in Build 6's command.js – that is what node tests; the browser part is the overlay.
// SPEC_COCKPIT_BAUM_v1 §3.4: die Palette findet auch den Baum (einzelne Aufgaben, Vorhaben, Ansichten), zeigt bei leerer Eingabe
// „Zuletzt“ und bietet „Im Wissen suchen: …“ an. Die Frage geht nur ins Memo des Werkzeugs Wissen, nie in den Browser-Speicher.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const P = ()=>root.sedraPlaces;                 // die Ortskunde steht im Vertrag (ui/places.js), nicht in dieser Shell
  const PLACES = P().PLACES, normalize = P().normalize;
  // Werkzeuge der Werkstatt, die im Ortsverzeichnis des Vertrags (ui/places.js) noch fehlen: nur das Cockpit kennt sie hier
  const COCKPIT_PLACES = PLACES.concat([
    {id: 'master', label: 'Gespräch (Master)', hint: 'ins Eingabefeld unten', words: ['master', 'chat', 'gespräch', 'gespraech'], object: {type: 'talk', id: 'master', title: 'Gespräch'}},
    {id: 'wissensbasis', label: 'Wissensbasis (Oberfläche)', hint: 'in die Shell nur für das Wissen wechseln – nimmt mit, was offen ist', words: ['wissensbasis', 'wissens-shell', 'wissensshell'], object: {type: 'shell', id: 'wissensbasis', title: 'Wissensbasis'}},
    {id: 'runs', label: 'KI Labor · Läufe', hint: 'Protokolle der Modellläufe', words: ['läufe', 'laeufe', 'lauf', 'protokolle'], object: {type: 'labor', id: 'laeufe', title: 'KI Labor · Läufe'}}
  ]);

  // Zeilen des Baums, die zum Getippten passen (rein): jedes Wort des Titels zählt, ab drei Zeichen auch der Anfang
  function baumTreffer(text, baum){
    const q = normalize(text);
    if(q.length < 3) return [];
    return (baum || []).filter(r=>r.kind === 'row' && r.object && r.tone !== 'mehr' && r.object.type !== 'shell')
      .filter(r=>normalize(r.title).split(' ').some(w=>w.startsWith(q)) || normalize(r.title).startsWith(q))
      .slice(0, 6).map(r=>({id: 'baum:' + r.schluessel, label: r.title, hint: r.gruppe + (r.note ? ' · ' + r.note : ''), object: r.object}));
  }

  // die Zeilen der Palette (rein): Orte und Gespräch wie im Vertrag, dazu der Baum, „Zuletzt“ und „Im Wissen suchen“
  function cockpitRows(text, baum, zuletzt){
    const t = String(text || '').trim();
    const rows = P().paletteRows(text, COCKPIT_PLACES);
    if(!t){
      const z = (zuletzt || []).slice(0, 5).map((o, i)=>({id: 'zuletzt:' + i, label: o.title || o.type, hint: 'Zuletzt', object: o}));
      return z.concat(rows);
    }
    const da = new Set(rows.map(r=>r.object ? r.object.type + ':' + r.object.id + ':' + (r.object.view || r.object.ansicht || '') : r.id));
    const baumRows = baumTreffer(t, baum).filter(r=>!da.has(r.object.type + ':' + r.object.id + ':' + (r.object.view || r.object.ansicht || '')));
    const frage = t.replace(/^\?\s*/, '');
    const wissen = frage ? {id: '__wissen', label: 'Im Wissen suchen: ' + frage.slice(0, 60), hint: 'Wissen › Suche – Treffer mit Fundstelle', frage} : null;
    const out = rows.concat(baumRows);
    if(wissen){
      if(t.startsWith('?')) out.unshift(wissen);
      else{ const i = out.findIndex(r=>r.id === '__talk'); out.splice(i >= 0 ? i + 1 : out.length, 0, wissen); }
    }
    return out;
  }

  function makePalette(shell){
    let host = null, index = 0, input = null;
    const rowsFor = text=>cockpitRows(text, shell.tree && shell.tree.rows ? shell.tree.rows() : [], shell.zuletzt || []);

    function build(){
      host = d().el('div', 'pal');
      host.hidden = true;
      const box = d().el('div', 'pal-box');
      input = d().el('input');
      input.placeholder = 'Wohin oder was? – „Entscheidungen“, „Modelle“, eine Aufgabe, ? für das Wissen, oder ein Auftrag für SEDRA';
      input.setAttribute('aria-label', 'Kommando');
      const list = d().el('div', 'pal-list'); list.setAttribute('role', 'listbox');
      input.oninput = ()=>{ index = 0; renderList(list); };
      input.onkeydown = e=>{
        const rows = rowsFor(input.value);
        if(e.key === 'ArrowDown'){ e.preventDefault(); index = Math.min(rows.length - 1, index + 1); renderList(list); }
        else if(e.key === 'ArrowUp'){ e.preventDefault(); index = Math.max(0, index - 1); renderList(list); }
        else if(e.key === 'Enter'){ e.preventDefault(); pick(rows[index]); }
        else if(e.key === 'Escape'){ e.preventDefault(); close(); }
      };
      box.append(input, list);
      host.append(box);
      host.onmousedown = e=>{ if(e.target === host) close(); };
      document.body.append(host);
      return list;
    }

    function renderList(list){
      const rows = rowsFor(input.value);
      index = Math.max(0, Math.min(index, rows.length - 1));
      list.replaceChildren(...rows.map((r, i)=>{
        const line = d().el('div', 'pal-row' + (i === index ? ' on' : '') + (r.hint === 'Zuletzt' ? ' zuletzt' : ''));
        line.setAttribute('role', 'option'); line.setAttribute('aria-selected', i === index ? 'true' : 'false');
        line.append(d().el('b', null, r.label), d().el('small', null, r.hint || ''));
        line.onmousedown = e=>{ e.preventDefault(); pick(r); };
        line.onmousemove = ()=>{ if(index !== i){ index = i; renderList(list); } };
        return line;
      }));
    }

    function pick(row){
      if(!row) return;
      const text = input.value.trim();
      close();
      if(row.id === '__talk') return shell.talk(text);
      if(row.id === '__wissen') return shell.imWissenSuchen(row.frage);
      if(row.object) return shell.openObject(row.object);
    }

    let list = null;
    function open(){
      if(!host) list = build();
      host.hidden = false; input.value = ''; index = 0; renderList(list); input.focus();
    }
    function close(){ if(host) host.hidden = true; }
    function toggle(){ if(!host || host.hidden) open(); else close(); }
    return {open, close, toggle, isOpen: ()=>!!host && !host.hidden};
  }

  root.sedraPalette = {makePalette, cockpitRows, baumTreffer};
  if(typeof module !== 'undefined' && module.exports) module.exports = {cockpitRows, baumTreffer};
})();
