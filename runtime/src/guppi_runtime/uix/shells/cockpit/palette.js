// Cockpit shell – the palette (Strg+K) and the router of the one input (COCKPIT_MODUL_v1 rule 1).
// There is no second permanent field: the Gespräch is the input, and a short navigation phrase opens a place instead of asking GUPPI.
// routeText() and matchPlaces() are pure, as in Build 6's command.js – that is what node tests; the browser part is the overlay.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const P = ()=>root.sedraPlaces;                 // die Ortskunde steht im Vertrag (ui/places.js), nicht in dieser Shell
  const PLACES = P().PLACES, normalize = P().normalize;
  // Werkzeuge der Werkstatt, die im Ortsverzeichnis des Vertrags (ui/places.js) noch fehlen: nur das Cockpit kennt sie hier
  const COCKPIT_PLACES = PLACES.concat([
    {id: 'master', label: 'Master-Chat', hint: 'das Gespräch unten', words: ['master', 'chat', 'gespräch', 'gespraech'], object: {type: 'talk', id: 'master', title: 'Master-Chat'}},
    {id: 'labor', label: 'KI Labor', hint: 'Anbieter, Schlüssel, Modelle, Tests', words: ['labor', 'anbieter', 'schlüssel', 'schluessel', 'cloud'], object: {type: 'labor', id: 'ki', title: 'KI Labor'}},
    {id: 'runs', label: 'KI Labor · Läufe', hint: 'Protokolle der Modellläufe', words: ['läufe', 'laeufe', 'lauf', 'protokolle'], object: {type: 'labor', id: 'laeufe', title: 'KI Labor · Läufe'}}
  ]);
  const paletteRows = text=>P().paletteRows(text, COCKPIT_PLACES);

  function makePalette(shell){
    let host = null, index = 0, input = null;

    function build(){
      host = d().el('div', 'pal');
      host.hidden = true;
      const box = d().el('div', 'pal-box');
      input = d().el('input');
      input.placeholder = 'Wohin oder was? – „Entscheidungen“, „Modelle“, oder ein Auftrag für GUPPI';
      input.setAttribute('aria-label', 'Kommando');
      const list = d().el('div', 'pal-list');
      input.oninput = ()=>{ index = 0; renderList(list); };
      input.onkeydown = e=>{
        const rows = paletteRows(input.value);
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
      const rows = paletteRows(input.value);
      index = Math.max(0, Math.min(index, rows.length - 1));
      list.replaceChildren(...rows.map((r, i)=>{
        const line = d().el('div', 'pal-row' + (i === index ? ' on' : ''));
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

  root.sedraPalette = {makePalette};

})();
