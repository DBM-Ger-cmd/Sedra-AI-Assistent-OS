// UI contract 1.0 – der Creator einer Shell aus Vorgabe, der Teil im Browser (Build 17, Schritt 3).
//
// Ein Block, den das Werkzeug „Module“ und der Einstieg gleich zeigen: ein Satz an SEDRA oder eine der drei Vorlagen, dann
// Satz und Skizze der Vorgabe, dann „So anlegen“. Der Server macht die Vorgabe (desk/vorgabe.py, Schema-Zwang am Modell) und
// legt sie an (module_scaffold mit vorgabe); hier wird nichts erfunden – nur gezeigt und gefragt.
// Classic script: definiert window.sedraVorgabe; die Skizze (sketchRows) ist rein und läuft in node.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const SHORT = {leiste: 'Instrumente', orte: 'Orte', werkstueck: 'Werkstück', gespraech: 'Gespräch', entscheidungen: 'Entscheidungen', leer: ''};

  // rein: Zeilen aus Zellen {zone, label, weight} für die kleine Skizze
  function sketchRows(vorgabe){
    const v = vorgabe || {};
    return (v.raster || []).map(row=>String(row).split('|').map(z=>({zone: z, label: SHORT[z] === undefined ? z : SHORT[z],
      weight: z === 'orte' ? 1 : z === 'entscheidungen' ? 1.5 : z === 'werkstueck' ? 4 : 2})));
  }

  function sketch(vorgabe){
    const box = d().el('div', 'vg-sketch');
    box.setAttribute('aria-label', 'Skizze der Anordnung');
    sketchRows(vorgabe).forEach(cells=>{
      const row = d().el('div', 'vg-row');
      row.style.gridTemplateColumns = cells.map(c=>c.weight + 'fr').join(' ');
      row.style.flex = cells.some(c=>c.zone === 'werkstueck') ? '3' : '1';
      cells.forEach(c=>{ const cell = d().el('div', 'vg-cell vg-' + c.zone); cell.append(d().el('span', null, c.label)); row.append(cell); });
      box.append(row);
    });
    if(((vorgabe || {}).gespraech || {}).art === 'schublade') box.append(d().el('div', 'vg-drawer', 'Gespräch (Schublade)'));
    return box;
  }

  // der Block: api ist das ctx.api des Moduls, done(out) läuft nach dem Anlegen (das Werkzeug frischt auf, der Einstieg wählt)
  function block(api, notify, done){
    const box = d().el('div', 'vg');
    const head = d().el('b', null, 'Eigene Oberfläche aus einer Vorgabe');
    const hint = d().el('small', 's-muted', 'Beschreib die Anordnung – oder nimm eine Vorlage. Kein Code, kein Gate: der Rahmen baut den Bildschirm aus der Vorgabe.');
    const text = d().el('textarea', 'vg-text');
    text.placeholder = 'Zum Beispiel: links die Aufgaben und das Logbuch, rechts das Werkstück mit Nachweisen daneben, das Gespräch als Schublade, keine Instrumente';
    text.rows = 2; text.setAttribute('aria-label', 'Wunsch für die Oberfläche');
    const idRow = d().el('div', 'vg-ids');
    const id = d().el('input'); id.placeholder = 'id, z. B. meine-bruecke'; id.setAttribute('aria-label', 'id der Oberfläche');
    const name = d().el('input'); name.placeholder = 'Name, z. B. Meine Brücke'; name.setAttribute('aria-label', 'Name der Oberfläche');
    idRow.append(id, name);
    const buttons = d().el('div', 'vg-buttons');
    const preview = d().el('div', 'vg-preview'); preview.hidden = true;
    let chosen = null;

    const show = (vorgabe, sentence, source)=>{
      chosen = vorgabe;
      preview.hidden = false;
      preview.replaceChildren(sketch(vorgabe), d().el('p', 'vg-sentence', sentence),
        d().el('small', 's-muted', source),
        d().button('So anlegen', async()=>{
          const mid = id.value.trim() || chosen.id || 'meine';
          const out = await api('/api/uix/scaffold', {method: 'POST', body: {kind: 'shell', id: mid, name: name.value.trim() || chosen.name || mid, vorgabe: chosen}});
          notify(out.note, 'note');
          preview.hidden = true; chosen = null; text.value = '';
          if(done) await done(out);
        }, 'p'));
    };

    const ask = d().button('SEDRA fragen', async()=>{
      const mid = id.value.trim() || 'meine';
      const out = await api('/api/uix/vorgabe', {method: 'POST', body: {text: text.value, id: mid, name: name.value.trim()}});
      show(out.vorgabe, out.sentence, 'Vorschlag von SEDRA (' + (out.model || 'lokales Modell') + ', ' + out.rounds + ' Runde' + (out.rounds > 1 ? 'n' : '') + ') – geprüft gegen das Schema. Nichts ist angelegt.');
    }, 'p');
    buttons.append(ask);
    box.append(head, hint, text, idRow, buttons, preview);

    api('/api/uix/vorgaben').then(v=>{
      ask.disabled = !v.model;
      if(!v.model) buttons.append(d().el('small', 's-muted', v.note || ''));
      (v.templates || []).forEach(t=>buttons.append(d().button(t.name, ()=>show(Object.assign({}, t.vorgabe, {id: id.value.trim() || 'meine', name: name.value.trim() || t.name}), t.sentence, 'Vorlage „' + t.name + '“: ' + t.hint), '')));
    }).catch(err=>{ buttons.append(d().el('small', 's-note bad', 'Vorlagen nicht erreichbar: ' + err.message)); });
    return box;
  }

  root.sedraVorgabe = {sketchRows, sketch, block};
  if(typeof module !== 'undefined' && module.exports) module.exports = {sketchRows};
})();
