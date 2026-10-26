// Werkzeug „Wissen“ – die Ansicht Quellen (SPEC_WERKZEUG_WISSEN_v2 §3.3): eine Liste statt einer Tabelle mit acht Spalten.
// Je Quelle: Titel und Pfad, Marken in Klartext (Art, Stufe, Projekt, Personenbezug), rechts Abschnitte und Stand; die Handlungen
// der Quelle liegen in einem Menü „⋯“ an der Zeile. Stufe heraufsetzen und Neu beantragen als Auswahl mit Klartext statt Zahl.
// Ein Treffer markiert hier seine Quelle. Der Antrag für eine neue Quelle ist geführt (antrag.js). Vor tool.js geladen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const Z = ()=>root.sedraWissenZitate;

  function markierung(t, m){
    const row = d().el('div', 's-row s-small t-wissen-markierung');
    const text = d().el('span', 's-muted');
    Z().zitatKnoten(text, root.sedraWissenPure.markierungText(m), id=>t.zeigeTreffer(id));
    row.append(text, d().button('Markierung aufheben', ()=>{ t.s.markiert = null; return t.draw(); }));
    return row;
  }

  // Inline-Formular (kein prompt()): „Stufe heraufsetzen“ (nur enger, ohne Gate) und „Neu beantragen“ (Antrag mit Stufe).
  // Ein Feld im Formular: Enter sendet es nach HTML genau einmal ab, „Abbrechen“ löst es nicht aus (Vertrag 1.1, V6).
  function stufeForm(t, q){
    const f = t.s.stufeForm, herauf = f.verb === 'stufe_heraufsetzen';
    const form = d().el('form', 's-row t-wissen-stufe-form');
    const label = d().el('label', 's-row s-small');
    const wahl = d().el('select', 't-wissen-stufe-feld t-wissen-fokus'); wahl.setAttribute('aria-label', 'Wer darf lesen');
    for(let n = herauf ? q.stufe + 1 : 0; n <= 6; n++){ const o = d().el('option', null, Z().stufeText(n)); o.value = String(n); wahl.append(o); }
    wahl.value = String(herauf ? Math.min(q.stufe + 1, 6) : q.stufe);
    label.append(d().el('span', 's-muted', herauf ? 'Enger machen – wer darf dann lesen?' : 'Neuer Antrag – wer darf lesen?'), wahl);
    const fehler = d().el('small', 's-note bad t-wissen-stufe-fehler'); fehler.hidden = true;
    const ab = ()=>{ t.s.stufeForm = null; return t.draw(); };
    const ok = async()=>{
      const p = Z().stufePruefen(wahl.value, herauf ? q.stufe : undefined);
      if(!p.ok){ fehler.textContent = p.satz; fehler.hidden = false; wahl.focus(); return; }
      t.sage(await t.verb(f.verb, {stufe: p.stufe}, q.id, 'wissen_quelle'));
      t.s.stufeForm = null; t.d.quellen = null;
      await t.refresh(false);
    };
    form.onsubmit = e=>{ e.preventDefault(); return ok(); };
    form.onkeydown = e=>{ if(e.key === 'Escape'){ e.preventDefault(); ab(); } };
    form.append(label, d().button('Abbrechen', ab), d().button(herauf ? 'Bestätigen' : 'Antrag stellen', ok, 'p'), fehler);
    return form;
  }

  function zeile(t, q){
    const s = t.s, m = s.markiert, hier = !!(m && String(q.id) === m.quelle);
    const box = d().el('div', 's-card s-col t-wissen-quelle' + (q.aktiv ? '' : ' t-wissen-aus') + (hier ? ' t-wissen-markiert' : ''));
    box.dataset.quelle = String(q.id);
    const kopf = d().el('div', 's-row t-wissen-quelle-kopf');
    const links = d().el('div', 's-col t-wissen-quelle-name');
    links.append(d().el('b', null, q.title));
    const marken = d().el('div', 's-row');
    marken.append(d().el('span', 't-wissen-marke', Z().artText(q.adapter)));
    const stufe = d().el('span', 't-wissen-marke' + (q.stufe >= 3 ? ' eng' : ''), 'Stufe ' + q.stufe); stufe.title = Z().stufeText(q.stufe); marken.append(stufe);
    marken.append(d().el('span', 't-wissen-marke', q.projekt ? 'Projekt ' + q.projekt : 'alle Projekte'));
    if(q.personenbezug) marken.append(d().el('span', 't-wissen-marke warn', 'Personenbezug'));
    links.append(marken);
    const rechts = d().el('small', 's-muted t-wissen-quelle-zahl',
      q.aktiv ? d().fmtNumber(q.abschnitte) + ' Abschnitte · ' + (q.stand ? d().fmtTime(q.stand) : 'noch nicht abgeglichen') : 'aus');
    kopf.append(links, rechts);
    if((q.actions || []).length){
      const menu = d().el('button', 's-btn t-wissen-menu', '⋯'); menu.type = 'button';
      menu.title = 'Handlungen für diese Quelle'; menu.setAttribute('aria-label', 'Handlungen für ' + q.title);
      menu.setAttribute('aria-expanded', s.menu === q.id ? 'true' : 'false');
      menu.onclick = ()=>{ s.menu = s.menu === q.id ? null : q.id; return t.draw(); };
      kopf.append(menu);
    }
    box.append(kopf);
    if(s.menu === q.id){
      const row = d().el('div', 's-row t-wissen-menu-liste');
      (q.actions || []).forEach(v=>row.append(d().button((v.label || v.verb) + (v.verb === 'stufe_heraufsetzen' || v.verb === 'neu_beantragen' ? ' …' : ''), async()=>{
        s.menu = null;
        if(v.verb === 'stufe_heraufsetzen' || v.verb === 'neu_beantragen'){ s.stufeForm = {id: q.id, verb: v.verb}; return t.draw(); }
        t.sage(await t.verb(v.verb, {}, q.id, 'wissen_quelle'));
        t.d.quellen = null;
        await t.refresh(false);
      })));
      box.append(row);
    }
    if(hier) box.append(markierung(t, m));
    if(s.stufeForm && s.stufeForm.id === q.id) box.append(stufeForm(t, q));
    return box;
  }

  const ansicht = {
    async laden(t){ if(!t.d.quellen) t.d.quellen = (await t.post({type: 'wissen_quelle'})).items || []; },
    zeichnen(t){
      const s = t.s, box = d().el('div', 's-col');
      if(s.antrag && root.sedraWissenAntrag) box.append(root.sedraWissenAntrag.zeichnen(t));
      const alle = t.d.quellen || [];
      if(!alle.length){
        box.append(d().empty('Keine Quellen. Eine Quelle ist ein Ordner, eine Datei oder einer der drei Speicher; sie wird erst nach deiner Freigabe im Posteingang aufgenommen.'));
        if(!s.antrag) box.append(d().button('Quelle beantragen …', ()=>{ s.antrag = {schritt: 1}; return t.draw(); }, 'p'));
        return box;
      }
      const filter = d().el('div', 's-row t-wissen-filter');
      [['alle', 'alle'], ['aktiv', 'aktiv'], ['aus', 'aus']].forEach(([id, label])=>{
        filter.append(d().button(label, ()=>{ s.filterQuellen = id; return t.draw(); }, s.filterQuellen === id ? 'p' : ''));
      });
      box.append(filter);
      const m = s.markiert;
      if(m && !alle.some(q=>String(q.id) === m.quelle)) box.append(d().el('div', 's-note warn', 'Die Quelle ' + m.quelle + ' des Treffers steht nicht mehr in der Liste.'));
      const liste = d().el('div', 's-col t-wissen-quellen');
      alle.filter(q=>s.filterQuellen === 'alle' || (s.filterQuellen === 'aktiv' ? q.aktiv : !q.aktiv)).forEach(q=>liste.append(zeile(t, q)));
      box.append(liste);
      return box;
    },
    aktionen(t){
      return [{label: 'Quelle beantragen …', run: ()=>{ t.s.antrag = {schritt: 1}; t.s.ansicht = 'quellen'; return t.draw(); }},
              {label: 'Erstbestückung beantragen', run: async()=>{ t.sage(await t.verb('erstbestueckung')); t.d.quellen = null; await t.refresh(false); }}];
    }
  };

  root.sedraWissenAnsichten = Object.assign(root.sedraWissenAnsichten || {}, {quellen: ansicht});
})();
