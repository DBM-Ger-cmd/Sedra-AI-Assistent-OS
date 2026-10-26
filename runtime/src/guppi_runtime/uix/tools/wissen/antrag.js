// Werkzeug „Wissen“ – der geführte Antrag für eine Quelle (SPEC_WERKZEUG_WISSEN_v2 §3.4, WZ4). Ein Dialog im Werkzeug, vier Schritte:
// 1 Was soll SEDRA lernen? (Vorlagen; was schon freigegeben ist, ist nicht doppelt wählbar – Lehre aus Prüfung F4)
// 2 Wo genau? (Pfad und Dateiarten, Vorprüfung über das Verb quelle_pruefen: Dateien, etwa Abschnitte, Überschneidung)
// 3 Wer darf es lesen? (Stufe mit Klartext aus permission_levels.yaml, Projekt, Personenbezug)
// 4 Zusammenfassung → Antrag im Posteingang. Die Eingaben stehen in der Ablage: ein Shell-Wechsel mittendrin verliert nichts.
// `VORLAGEN`, `schonDa` und `argsVon` sind rein. Vor tool.js geladen; quellen.js zeichnet den Dialog.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const Z = ()=>root.sedraWissenZitate;
  const LOGBUCH = 'docs/LOGBUCH_AGENT_MANAGER.md', GW = 'local_config/gateway/wissen.sqlite';

  const VORLAGEN = [
    {id: 'doku', titel: 'Doku und Specs des Repos', text: 'Markdown unter docs/ – Doku und Specs von SEDRA', pfadFrei: true,
     werte: {adapter: 'markdown', wurzel: 'repo', pfad: 'docs', muster: '*.md', stufe: 1, personenbezug: false}},
    {id: 'ordner', titel: 'Ein Ordner im Projekt', text: 'Notizen, Texte, Protokolle im Projektordner (Vorgabe: Stufe 3, Personenbezug)', pfadFrei: true,
     werte: {adapter: 'markdown', wurzel: 'projekt', pfad: '', muster: '*.md', stufe: 3, personenbezug: true}},
    {id: 'logbuch', titel: 'Logbuch', text: 'die Zeilen des Logbuchs, mit Datum',
     werte: {adapter: 'logbuch', wurzel: 'repo', pfad: LOGBUCH, muster: '*.md', stufe: 1, personenbezug: false}},
    {id: 'knowledge', titel: 'Wissenssätze von SEDRA', text: 'der Speicher knowledge',
     werte: {adapter: 'knowledge', wurzel: 'projekt', pfad: 'runtime_data/knowledge/records.jsonl', muster: '', stufe: 1, personenbezug: false}},
    {id: 'arbeitsumfeld', titel: 'Arbeitsumfeld', text: 'was SEDRA über seine Oberfläche weiß',
     werte: {adapter: 'arbeitsumfeld', wurzel: 'projekt', pfad: 'local_config/arbeitsumfeld/wissen.sqlite', muster: '', stufe: 1, personenbezug: false}},
    {id: 'gateway', titel: 'GateWay-Wissen', text: 'Regelbuch und Leitfaden des KI GateWay',
     werte: {adapter: 'gateway', wurzel: 'projekt', pfad: GW + '#wissen', muster: '', stufe: 1, personenbezug: false}},
    {id: 'gateway-eigene', titel: 'Eigene Einträge im GateWay', text: 'was du im GateWay selbst eingetragen hast – mit Personenbezug',
     werte: {adapter: 'gateway', wurzel: 'projekt', pfad: GW + '#eigene', muster: '', stufe: 3, personenbezug: true}},
    {id: 'eigen', titel: 'Eigene Angabe', text: 'Art, Wurzel und Pfad selbst wählen', frei: true, pfadFrei: true,
     werte: {adapter: 'markdown', wurzel: 'repo', pfad: 'docs', muster: '*.md', stufe: 1, personenbezug: false}}
  ];
  const MUSTER = [['*.md', '*.md'], ['*.txt', '*.txt'], ['*.md,*.txt', '*.md und *.txt']];

  // ist genau diese Quelle schon freigegeben und aktiv? (rein)
  function schonDa(quellen, w){
    return (quellen || []).some(q=>q.aktiv && q.adapter === w.adapter && q.wurzel === w.wurzel && q.pfad === w.pfad);
  }
  // die Argumente des Verbs quelle_beantragen aus den Werten (rein)
  function argsVon(w){
    return {adapter: w.adapter, wurzel: w.wurzel, pfad: w.pfad, muster: w.muster, stufe: Number(w.stufe), projekt: w.projekt ? String(w.projekt) : null, personenbezug: !!w.personenbezug};
  }

  const auswahl = (pairs, wert, label)=>{
    const s = d().el('select'); s.setAttribute('aria-label', label);
    pairs.forEach(([v, l])=>{ const o = d().el('option', null, l); o.value = v; s.append(o); }); s.value = wert; return s;
  };
  const feld = (box, label, input)=>{ const row = d().el('label', 's-col s-small'); row.append(d().el('span', 's-muted', label), input); box.append(row); return input; };

  async function pruefen(t){
    const a = t.s.antrag;
    a.pruefung = {laeuft: true}; t.draw();
    a.pruefung = await t.verb('quelle_pruefen', argsVon(a.werte));
    t.draw();
  }
  const geprueft = a=>a.pruefung && a.pruefung.status === 'erledigt' && (a.pruefung.dateien === null || a.pruefung.dateien > 0) && !a.pruefung.schon_da;

  function schritt1(t, box){
    const a = t.s.antrag;
    box.append(d().el('b', null, '1 · Was soll SEDRA lernen?'));
    const grid = d().el('div', 't-wissen-vorlagen');
    VORLAGEN.forEach(v=>{
      const da = !v.frei && schonDa(t.d.quellen, v.werte);
      const karte = d().el('div', 's-card t-wissen-vorlage' + (da ? ' t-wissen-aus' : '') + (a.vorlage === v.id ? ' on' : ''));
      karte.dataset.vorlage = v.id;
      karte.append(d().el('b', null, v.titel), d().el('small', 's-muted', da ? 'ist schon da' : v.text));
      if(!da) d().clickable(karte, ()=>{
        a.vorlage = v.id; a.werte = Object.assign({}, v.werte); a.pruefung = null; a.schritt = 2;
        if(!v.pfadFrei) return pruefen(t);                 // fester Pfad: gleich prüfen
        return t.draw();
      });
      else karte.setAttribute('aria-disabled', 'true');
      grid.append(karte);
    });
    box.append(grid);
  }

  function schritt2(t, box){
    const a = t.s.antrag, v = VORLAGEN.find(x=>x.id === a.vorlage) || VORLAGEN[0], w = a.werte;
    box.append(d().el('b', null, '2 · Wo genau? – ' + v.titel));
    const form = d().el('form', 's-col t-wissen-form'); form.onsubmit = e=>e.preventDefault();
    let adapter = null, wurzel = null, pfad = null, muster = null;
    if(v.frei){
      adapter = feld(form, 'Art', auswahl([['markdown', 'Doku (Markdown)'], ['text', 'Text'], ['logbuch', 'Logbuch'], ['knowledge', 'Speicher knowledge'],
                                           ['arbeitsumfeld', 'Arbeitsumfeld'], ['gateway', 'GateWay (#wissen oder #eigene)']], w.adapter, 'Art'));
      wurzel = feld(form, 'Wurzel', auswahl([['repo', 'das Repo (Doku, Specs)'], ['projekt', 'das Projekt (Arbeitsordner)']], w.wurzel, 'Wurzel'));
    }
    if(v.pfadFrei){
      pfad = feld(form, 'Pfad (relativ zur Wurzel, z. B. docs oder notizen/kunde.md)', d().el('input', 't-wissen-fokus')); pfad.value = w.pfad || '';
      muster = feld(form, 'Dateiarten', auswahl(MUSTER, w.muster || '*.md', 'Dateiarten'));
    }else form.append(d().el('small', 's-muted', (w.wurzel === 'repo' ? 'Repo' : 'Projekt') + ' › ' + w.pfad));
    const uebernehmen = ()=>{
      if(adapter) w.adapter = adapter.value;
      if(wurzel) w.wurzel = wurzel.value;
      if(pfad) w.pfad = pfad.value.trim();
      if(muster) w.muster = muster.value;
    };
    const p = a.pruefung;
    if(p && p.laeuft) form.append(d().el('div', 's-note', 'Prüfe …'));
    else if(p) form.append(d().el('div', 's-note' + (p.status === 'fehler' || p.schon_da || p.dateien === 0 ? ' bad' : (p.ueberschneidung || []).length ? ' warn' : ' ok'), p.satz || ''));
    const row = d().el('div', 's-row');
    row.append(d().button('Zurück', ()=>{ a.schritt = 1; return t.draw(); }),
               d().button('Prüfen', ()=>{ uebernehmen(); return pruefen(t); }, geprueft(a) ? '' : 'p', {absenden: !geprueft(a)}));
    const weiter = d().button('Weiter', ()=>{ uebernehmen(); a.schritt = 3; return t.draw(); }, geprueft(a) ? 'p' : '', {absenden: geprueft(a)});
    weiter.disabled = !geprueft(a);
    row.append(weiter);
    form.append(row);
    box.append(form);
  }

  function schritt3(t, box){
    const a = t.s.antrag, w = a.werte;
    box.append(d().el('b', null, '3 · Wer darf es lesen?'));
    const form = d().el('form', 's-col t-wissen-form'); form.onsubmit = e=>e.preventDefault();
    const stufe = feld(form, 'Stufe', auswahl(Z().STUFEN.map((_, n)=>[String(n), Z().stufeText(n)]), String(w.stufe), 'Stufe'));
    stufe.classList.add('t-wissen-fokus');
    const projekt = feld(form, 'Projekt (leer = alle Projekte)', d().el('input')); projekt.value = w.projekt || '';
    const pb = d().el('input'); pb.type = 'checkbox'; pb.checked = !!w.personenbezug;
    const pbRow = d().el('label', 's-row s-small'); pbRow.append(pb, d().el('span', null, 'Personenbezug – bleibt lokal, geht nie in eine Cloud')); form.append(pbRow);
    const row = d().el('div', 's-row');
    row.append(d().button('Zurück', ()=>{ a.schritt = 2; return t.draw(); }),
               d().button('Weiter', ()=>{ w.stufe = Number(stufe.value); w.projekt = projekt.value.trim() || null; w.personenbezug = !!pb.checked; a.schritt = 4; return t.draw(); }, 'p', {absenden: true}));
    form.append(row);
    box.append(form);
  }

  function schritt4(t, box){
    const a = t.s.antrag, w = a.werte, p = a.pruefung || {};
    box.append(d().el('b', null, '4 · Zusammenfassung'));
    const liste = d().el('ul', 't-wissen-zusammen');
    [Z().artText(w.adapter) + ': ' + (w.wurzel === 'repo' ? 'Repo' : 'Projekt') + ' › ' + w.pfad + (w.muster ? ' (' + w.muster + ')' : ''),
     p.satz || '', Z().stufeText(w.stufe), w.projekt ? 'nur Projekt ' + w.projekt : 'alle Projekte', w.personenbezug ? 'mit Personenbezug – bleibt lokal' : 'ohne Personenbezug']
      .filter(Boolean).forEach(x=>liste.append(d().el('li', null, x)));
    const form = d().el('form', 's-col'); form.onsubmit = e=>e.preventDefault();
    const row = d().el('div', 's-row');
    row.append(d().button('Zurück', ()=>{ a.schritt = 3; return t.draw(); }), d().button('Antrag stellen', async()=>{
      const out = await t.verb('quelle_beantragen', argsVon(w));
      t.sage(out);
      if(out && out.status === 'beantragt'){ t.s.antrag = null; t.hinweis = {text: root.sedraWissenPure.ergebnisSatz(out) + ' – dort freigeben, dann wird die Quelle aufgenommen.'}; }
      t.d.quellen = null;
      await t.refresh(false);
    }, 'p', {absenden: true}));
    form.append(liste, row);
    box.append(form);
  }

  function zeichnen(t){
    const a = t.s.antrag;
    const box = d().el('section', 's-card s-col t-wissen-antrag'); box.setAttribute('aria-label', 'Quelle beantragen');
    const kopf = d().el('div', 's-row');
    kopf.append(d().el('b', null, 'Quelle beantragen'), d().el('small', 's-muted', 'Schritt ' + a.schritt + ' von 4'));
    const zu = d().button('Abbrechen', ()=>{ t.s.antrag = null; return t.draw(); }); zu.style.marginLeft = 'auto'; kopf.append(zu);
    box.append(kopf);
    box.onkeydown = e=>{ if(e.key === 'Escape'){ e.preventDefault(); t.s.antrag = null; t.draw(); } };
    [schritt1, schritt2, schritt3, schritt4][Math.max(0, Math.min(3, (a.schritt || 1) - 1))](t, box);
    return box;
  }

  root.sedraWissenAntrag = {zeichnen, VORLAGEN, schonDa, argsVon};
  if(typeof module !== 'undefined' && module.exports) module.exports = {VORLAGEN, schonDa, argsVon};
})();
