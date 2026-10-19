// Minimal-Shell – ein Feld der Ablage anlegen oder ändern (Build 19).
//
// Drei Arten, wie der Captain sie im Test am PC beschrieben hat:
//   Ort       ein Ort aus der Ortskunde des Vertrags (Maschinenraum, Werkstatt, …) – öffnet sein Fenster
//   Fenster   das Fenster, das gerade vorn steht – z. B. eine bestimmte Aufgabe oder ein Modell
//   Auftrag   ein Satz an SEDRA („Lade das Coder-Modell“, „öffne den Maschinenraum“) – geht beim Klick ins Gespräch und dort
//             den gewohnten Weg; was SEDRA daraus vorschlägt, bekommt der Captain als Knopf. Ausgeführt wird hier nichts.
// Dazu Name und Bildzeichen. `entryFrom` ist rein und wird mit node geprüft – die Prüfung im Server ist dieselbe Form.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const KINDS = [['place', 'Ort'], ['object', 'Fenster vorn'], ['auftrag', 'Auftrag an SEDRA']];

  // Aus dem, was im Formular steht, ein Eintrag – oder ein Satz, was fehlt (rein)
  function entryFrom(form, places, iconFor){
    const label = String(form.label || '').trim().slice(0, 24);
    let entry;
    if(form.kind === 'place'){
      const p = (places || []).find(x=>x.id === form.place);
      if(!p) return {error: 'Bitte einen Ort wählen.'};
      entry = {kind: 'place', place: p.id, label: label || p.label.slice(0, 24), icon: form.icon || iconFor(p.object.type)};
    }else if(form.kind === 'object'){
      const o = form.object;
      if(!o || !o.type || !o.id || o.type === 'talk') return {error: 'Es steht kein Fenster vorn, das sich anheften lässt.'};
      const object = {type: o.type, id: String(o.id), title: String(o.title || o.id).slice(0, 60)};
      if(o.collection) object.collection = true;
      entry = {kind: 'object', object, label: label || object.title.slice(0, 24), icon: form.icon || iconFor(o.type)};
    }else if(form.kind === 'auftrag'){
      const text = String(form.text || '').trim();
      if(!text) return {error: 'Bitte den Satz an SEDRA schreiben.'};
      if(text.length > 400) return {error: 'Höchstens 400 Zeichen.'};
      entry = {kind: 'auftrag', text, label: label || text.slice(0, 24), icon: form.icon || 'auftrag'};
    }else return {error: 'Bitte eine Art wählen.'};
    if(!entry.label) return {error: 'Bitte einen Namen geben.'};
    return {entry};
  }

  let panel = null, state = null, redraw = null;

  function close(){ if(panel){ panel.remove(); panel = null; state = null; redraw = null; } }

  function open(host, shell, opts){
    close();
    const icons = root.sedraMinIcons;
    const places = ()=>(root.sedraPlaces && root.sedraPlaces.PLACES) || [];
    const e = opts.entry;
    const front = opts.front && opts.front.type !== 'talk' ? opts.front : null;
    state = e ? {kind: e.kind, place: e.place || '', object: e.object || front, text: e.text || '', label: e.label, icon: e.icon}
              : {kind: front ? 'object' : 'place', place: '', object: front, text: '', label: '', icon: ''};

    panel = d().el('div', 'sh-min-edit');
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', e ? 'Feld der Ablage ändern' : 'Feld in der Ablage anlegen');
    document.body.append(panel);

    redraw = ()=>{
      panel.replaceChildren();
      panel.append(d().el('b', null, e ? 'Feld ändern' : 'Neues Feld in der Ablage'));
      const seg = d().el('div', 'sh-min-seg');
      KINDS.forEach(([k, label])=>{
        const it = d().el('span', 'sh-min-seg-item' + (state.kind === k ? ' on' : ''), label);
        d().clickable(it, ()=>{ state.kind = k; redraw(); });
        seg.append(it);
      });
      panel.append(seg);

      const body = d().el('div', 'sh-min-edit-body');
      if(state.kind === 'place'){
        const sel = d().el('select');
        sel.setAttribute('aria-label', 'Ort');
        sel.append(new Option('– Ort wählen –', ''));
        places().forEach(p=>sel.append(new Option(p.label + ' · ' + p.hint, p.id)));
        sel.value = state.place || '';
        sel.onchange = ()=>{ state.place = sel.value; };
        body.append(sel);
      }else if(state.kind === 'object'){
        const o = state.object;
        body.append(d().el('small', null, o ? 'Heftet an: ' + (o.title || o.id) + ' (' + o.type + ')'
                                             : 'Es steht kein Fenster vorn. Erst ein Fenster öffnen, dann hier „Fenster vorn“.'));
      }else{
        const ta = d().el('textarea');
        ta.rows = 2; ta.maxLength = 400;
        ta.placeholder = 'Ein Satz an SEDRA, z. B. „Lade das Coder-Modell“ oder „öffne den Maschinenraum“';
        ta.setAttribute('aria-label', 'Auftrag an SEDRA');
        ta.value = state.text;
        ta.oninput = ()=>{ state.text = ta.value; };
        body.append(ta, d().el('small', null, 'Beim Klick geht der Satz ins Gespräch. SEDRA schlägt vor – du entscheidest per Knopf.'));
      }
      const name = d().el('input');
      name.maxLength = 24; name.placeholder = 'Name (leer: aus dem Ort oder Satz)';
      name.setAttribute('aria-label', 'Name des Feldes');
      name.value = state.label || '';
      name.oninput = ()=>{ state.label = name.value; };
      body.append(name);

      const grid = d().el('div', 'sh-min-edit-icons');
      icons.iconIds().forEach(id=>{
        const cell = d().el('span', 'sh-min-edit-icon' + (state.icon === id ? ' on' : ''));
        cell.title = icons.ICONS[id][0];
        cell.append(icons.iconEl(id, 20));
        d().clickable(cell, ()=>{ state.icon = id; [...grid.children].forEach(c=>c.classList.toggle('on', c === cell)); });
        grid.append(cell);
      });
      body.append(d().el('small', null, 'Bildzeichen (leer: passend zur Art)'), grid);
      panel.append(body);

      const said = d().el('small', 'sh-min-edit-said');
      const row = d().el('div', 's-row');
      row.append(d().button(e ? 'Speichern' : 'Anlegen', async()=>{
        const out = entryFrom(state, places(), icons.typeIcon);
        if(out.error){ said.textContent = out.error; return; }
        await opts.done(out.entry);
        close();
      }, 'p'), d().button('Abbrechen', ()=>close()));
      panel.append(said, row);
    };
    redraw();
    setTimeout(()=>{
      const away = ev=>{ if(panel && !panel.contains(ev.target) && !host.contains(ev.target)){ close(); document.removeEventListener('mousedown', away); } };
      document.addEventListener('mousedown', away);
    }, 0);
  }

  // Von außen vorbelegen („Fenster → An die Ablage heften“)
  function prefill(values){ if(state && redraw){ Object.assign(state, values); redraw(); } }

  root.sedraMinShelfEdit = {open, close, prefill, entryFrom, KINDS, isOpen: ()=>!!panel};
  if(typeof module !== 'undefined' && module.exports) module.exports = {entryFrom, KINDS};
})();
