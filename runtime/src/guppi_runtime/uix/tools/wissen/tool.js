// Werkzeug „Wissen“ (Spec 7, D7.9; WIS-13): der Wissensspeicher in fünf Ansichten – Quellen, Index, Suche, Nachmessung, Vorschläge.
// Gelesen wird nur über POST /api/objects (Typen wissen, wissen_quelle, wissen_vorschlag), gehandelt nur über POST /api/actions
// mit den Verben des Desk; eine Freigabe (Quelle, Vorschlag) ist ein Antrag im Posteingang, das Werkzeug `decisions` entscheidet.
// Kein Zeitgeber: neu gelesen wird bei decision.answered und desk.resync. Die Ansicht kommt als `view` am Objekt (N5), eine zu
// markierende Quelle als `quelle`. Zitate [W…] und Fehlersätze: zitate.js (vorher geladen). Kein prompt(): Formulare im Container.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const Z = ()=>root.sedraWissenZitate;
  const ANSICHTEN = [['quellen', 'Quellen'], ['index', 'Index'], ['suche', 'Suche'], ['nachmessung', 'Nachmessung'], ['vorschlaege', 'Vorschläge']];
  const ADAPTER = ['markdown', 'text', 'logbuch', 'knowledge', 'arbeitsumfeld', 'gateway'];
  const URTEILE = [['getroffen', 'getroffen'], ['nicht_getroffen', 'nicht getroffen'], ['ohne_antwort', 'ohne Antwort im Speicher']];
  const SPALTEN = ['Pfad', 'Adapter', 'Stufe', 'Projekt', 'Personenbezug', 'Abschnitte', 'Stand', ''];

  // Der Satz zum Stand des Index (rein)
  function zustandText(stand){
    if(!stand) return 'Kein Stand.';
    const p = Math.round((stand.abdeckung || 0) * 100);
    if(!stand.bereit) return 'Nur Volltextsuche (' + (stand.grund || 'kein Modell') + ') · ' + stand.abschnitte + ' Abschnitte';
    if(stand.neuaufbau) return 'Neuaufbau läuft · Abdeckung ' + p + ' % · ' + stand.vektoren + ' von ' + stand.abschnitte + ' eingebettet';
    return (stand.modus === 'hybrid' ? 'Hybride Suche' : 'Nur Volltextsuche') + ' · Abdeckung ' + p + ' % · ' + stand.abschnitte + ' Abschnitte';
  }

  // Ein Treffer als Zeile (rein): [id] Datei > Stelle · Datum · Ränge · Punkte
  function trefferZeile(t){
    const raenge = ['Wort ' + (t.rang_wort === null || t.rang_wort === undefined ? '–' : t.rang_wort), 'Vektor ' + (t.rang_vektor === null || t.rang_vektor === undefined ? '–' : t.rang_vektor)];
    return '[' + t.id + '] ' + t.datei + ' > ' + t.stelle + ' · Stand ' + String(t.datum || '').slice(0, 10) + ' · ' + raenge.join(', ') + ' · ' + Number(t.punkte || 0).toFixed(4) + (t.personenbezug ? ' · Personenbezug' : '');
  }

  // Ergebnis eines Verbs als Satz (rein)
  function ergebnisSatz(out){
    if(!out) return 'Erledigt.';
    if(out.status === 'fehler') return out.satz || out.code || 'Fehler';
    if(out.status === 'beantragt') return out.text || 'Antrag liegt im Posteingang.';
    return 'Erledigt.';
  }

  // Die Zeile unter der markierten Quelle (rein): welcher Treffer dorthin führte
  function markierungText(m){
    if(!m || !m.id) return 'Quelle aus der Navigation markiert.';
    return 'Treffer [' + m.id + '] · ' + (m.datei ? m.datei + ' > ' : '') + (m.stelle || '–') + ' · Stand ' + String(m.datum || '').slice(0, 10);
  }

  const tool = {
    id: 'wissen',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-wissen');
      const o = ctx.object || {};
      this.ansicht = o.view || 'quellen';
      this.markiert = o.quelle ? {quelle: String(o.quelle)} : null;
      this.speicher = null; this.fehler = null; this.hinweis = null; this.ergebnis = null; this.frage = ''; this.form = false; this.stufeForm = null; this.aktiv = null;
      ['decision.answered', 'desk.resync'].forEach(n=>ctx.bus.on(n, ()=>this.refresh()));
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-wissen'); this.el.replaceChildren(); this.speicher = null; },

    post(body){ return this.ctx.api('/api/objects', {method: 'POST', body}); },
    act(body){ return this.ctx.api('/api/actions', {method: 'POST', body}); },
    // Ein Verb des Desk; ein Fehler aus ctx.api() wird ein Ergebnis {status: fehler, satz} auf Deutsch, nie eine Konsolenzeile
    verb(verb, args, id, type){
      return this.act(Object.assign({type: type || 'wissen', verb, args: args || {}}, id ? {id} : {}))
        .then(r=>r && r.result !== undefined ? r.result : r, err=>({status: 'fehler', code: String(err && err.message || err), satz: Z().fehlerSatz(err)}));
    },

    async refresh(){
      if(!this.el) return;
      try{ this.speicher = await this.post({type: 'wissen', id: 'speicher'}); this.fehler = null; }
      catch(err){ this.fehler = Z().fehlerSatz(err); this.speicher = null; }
      return this.draw();
    },

    async draw(){
      const box = d().el('div', 's-col');
      const aus = this.fehler ? this.fehler.indexOf('unknown_object_type') >= 0 : (this.speicher || {}).state === 'aus';
      if(this.fehler || aus){
        box.append(d().el('div', 's-note' + (aus ? '' : ' bad'), aus ? 'Der Wissensspeicher ist ausgeschaltet (Schalter „wissen“ in local_config/switches.yaml)' + ((this.speicher || {}).grund ? ' – ' + this.speicher.grund : '') + '. Sobald er läuft, stehen Quellen, Index und Suche hier.' : 'Wissen nicht lesbar: ' + this.fehler));
        return this.el.replaceChildren(box);
      }
      const stand = (this.speicher || {}).stand || {};
      box.append(d().el('div', 's-note t-wissen-stand ' + (stand.modus === 'hybrid' ? 'ok' : 'warn'), zustandText(stand)));
      const tabs = d().el('div', 's-row t-wissen-tabs');
      ANSICHTEN.forEach(([id, label])=>{
        const b = d().el('button', 's-btn' + (this.ansicht === id ? ' p' : ''), label);
        b.onclick = ()=>{ this.ansicht = id; this.hinweis = null; this.draw(); };
        tabs.append(b);
      });
      box.append(tabs);
      if(this.hinweis) box.append(d().el('div', 's-note' + (this.hinweis.bad ? ' bad' : ''), this.hinweis.text));
      const teil = d().el('div', 't-wissen-teil');
      box.append(teil);
      this.el.replaceChildren(box);
      try{ teil.append(await this['draw_' + this.ansicht](stand)); }
      catch(err){ teil.append(d().el('div', 's-note bad', 'Nicht lesbar: ' + Z().fehlerSatz(err))); }
      const fokus = this.el.querySelector('input.t-wissen-stufe-feld') || this.el.querySelector('.t-wissen-aktiv') || this.el.querySelector('.t-wissen-markiert');
      if(fokus){ if(fokus.tagName === 'INPUT') fokus.focus(); else if(fokus.scrollIntoView) fokus.scrollIntoView({block: 'nearest'}); }
    },

    sage(out, bad){ this.hinweis = {text: ergebnisSatz(out), bad: bad || (out && out.status === 'fehler')}; },

    // Treffer → Quelle: die Ansicht „Quellen“ mit der Quelle des Treffers markiert (Stelle, Datum, ID in der Zeile darunter)
    zeigeQuelle(t){
      this.markiert = {quelle: String(t.quelle), id: t.id, datei: t.datei, stelle: t.stelle, datum: t.datum};
      this.ansicht = 'quellen'; this.hinweis = null;
      return this.draw();
    },

    // Zitat [W…] → Treffer: in der Ansicht „Suche“ hervorgehoben, wenn er in der letzten Suche steht
    zeigeTreffer(id){
      const da = ((this.ergebnis || {}).treffer || []).some(t=>t.id === id);
      this.aktiv = da ? id : null;
      this.hinweis = da ? null : {text: 'Der Abschnitt [' + id + '] steht nicht in der letzten Suche. Suche neu, dann ist er hier anklickbar.'};
      this.ansicht = 'suche';
      return this.draw();
    },

    // ---- Quellen: Pfad, Adapter, Stufe, Projekt, Personenbezug, Abschnitte, Stand; Verben der Quelle; Antrag für eine neue Quelle
    async draw_quellen(){
      const liste = await this.post({type: 'wissen_quelle'});
      const box = d().el('div', 's-col');
      const bar = d().el('div', 's-row');
      bar.append(d().button('Quelle beantragen …', ()=>{ this.form = !this.form; return this.draw(); }));
      bar.append(d().button('Erstbestückung beantragen', async()=>{ this.sage(await this.verb('erstbestueckung')); await this.refresh(); }));
      box.append(bar);
      if(this.form) box.append(this.drawForm());
      const items = liste.items || [];
      if(!items.length){ box.append(d().empty('Keine Quellen. Eine Quelle ist ein Ordner, eine Datei oder einer der drei Speicher; sie wird erst nach deiner Freigabe im Posteingang aufgenommen.')); return box; }
      const m = this.markiert;
      if(m && !items.some(q=>String(q.id) === m.quelle)) box.append(d().el('div', 's-note warn', 'Die Quelle ' + m.quelle + ' des Treffers steht nicht mehr in der Liste.'));
      const t = d().el('table', 's-table t-wissen-table');
      const head = d().el('tr');
      SPALTEN.forEach(h=>head.append(d().el('th', null, h)));
      t.append(head);
      items.forEach(q=>{
        const hier = !!(m && String(q.id) === m.quelle);
        const tr = d().el('tr', (q.aktiv ? '' : 't-wissen-aus') + (hier ? ' t-wissen-markiert' : ''));
        tr.dataset.quelle = String(q.id);
        tr.append(d().el('td', null, q.title), d().el('td', null, q.adapter), d().el('td', null, String(q.stufe)), d().el('td', null, q.projekt || 'alle'),
                  d().el('td', null, q.personenbezug ? 'ja' : 'nein'), d().el('td', null, String(q.abschnitte)), d().el('td', null, q.stand ? d().fmtTime(q.stand) : (q.aktiv ? 'noch nicht' : 'aus')));
        const td = d().el('td', 's-row');
        (q.actions || []).forEach(v=>td.append(d().button(v.label || v.verb, async()=>{
          if(v.verb === 'stufe_heraufsetzen' || v.verb === 'neu_beantragen'){ this.stufeForm = {id: q.id, verb: v.verb, stufe: q.stufe, label: v.label || v.verb}; return this.draw(); }
          this.sage(await this.verb(v.verb, {}, q.id, 'wissen_quelle'));
          await this.refresh();
        })));
        tr.append(td);
        t.append(tr);
        if(hier) t.append(this.zeile(8, 't-wissen-markierung', this.drawMarkierung(m)));
        if(this.stufeForm && this.stufeForm.id === q.id) t.append(this.zeile(8, 't-wissen-stufe', this.drawStufeForm(q)));
      });
      box.append(t);
      return box;
    },

    // eine Zeile über die ganze Tabelle (Markierung, Formular)
    zeile(breite, cls, inhalt){ const tr = d().el('tr', cls); const td = d().el('td'); td.colSpan = breite; td.append(inhalt); tr.append(td); return tr; },

    drawMarkierung(m){
      const row = d().el('div', 's-row s-small');
      const text = d().el('span', 's-muted');
      Z().zitatKnoten(text, markierungText(m), id=>this.zeigeTreffer(id));
      row.append(text, d().button('Markierung aufheben', ()=>{ this.markiert = null; return this.draw(); }));
      return row;
    },

    // Inline-Formular statt prompt(): „Stufe heraufsetzen“ (nur enger, ohne Gate) und „Neu beantragen“ (Antrag mit Stufe)
    drawStufeForm(q){
      const f = this.stufeForm, herauf = f.verb === 'stufe_heraufsetzen';
      const form = d().el('form', 's-row t-wissen-stufe-form');
      const label = d().el('label', 's-row s-small');
      const input = d().el('input', 't-wissen-stufe-feld'); input.type = 'number'; input.min = herauf ? String(q.stufe + 1) : '0'; input.max = '6';
      input.value = String(herauf ? Math.min(q.stufe + 1, 6) : q.stufe); input.setAttribute('aria-label', 'Stufe');
      label.append(d().el('span', 's-muted', herauf ? 'Neue Stufe (höher als ' + q.stufe + ', höchstens 6)' : 'Stufe des neuen Antrags (0–6)'), input);
      const fehler = d().el('small', 's-note bad t-wissen-stufe-fehler'); fehler.hidden = true;
      const ab = ()=>{ this.stufeForm = null; return this.draw(); };
      const ok = async()=>{
        const p = Z().stufePruefen(input.value, herauf ? q.stufe : undefined);
        if(!p.ok){ fehler.textContent = p.satz; fehler.hidden = false; input.focus(); return; }
        this.sage(await this.verb(f.verb, {stufe: p.stufe}, q.id, 'wissen_quelle'));
        this.stufeForm = null;
        await this.refresh();
      };
      form.onsubmit = e=>{ e.preventDefault(); return ok(); };
      form.onkeydown = e=>{ if(e.key === 'Escape'){ e.preventDefault(); ab(); } };
      form.append(label, d().button('Abbrechen', ab), d().button(herauf ? 'Bestätigen' : 'Antrag stellen', ok, 'p'), fehler);
      return form;
    },

    drawForm(){
      const box = d().el('form', 's-card s-col t-wissen-form');
      box.onsubmit = e=>e.preventDefault();
      const f = {};
      const feld = (key, label, input, start)=>{ const row = d().el('label', 's-col s-small'); row.append(d().el('span', 's-muted', label), input); input.value = start; f[key] = input; box.append(row); };
      const select = pairs=>{ const s = d().el('select'); pairs.forEach(([v, l])=>{ const o = d().el('option', null, l); o.value = v; s.append(o); }); return s; };
      feld('adapter', 'Adapter', select(ADAPTER.map(a=>[a, a])), 'markdown');
      feld('wurzel', 'Wurzel', select([['repo', 'repo (Doku, Specs)'], ['projekt', 'projekt (workspace)']]), 'repo');
      feld('pfad', 'Pfad (relativ, bei gateway mit #wissen oder #eigene)', d().el('input'), 'docs');
      feld('muster', 'Dateiarten', select([['*.md', '*.md'], ['*.txt', '*.txt'], ['*.md,*.txt', '*.md und *.txt']]), '*.md');
      feld('stufe', 'Kleinste Stufe, die lesen darf (0–6)', d().el('input'), '1');
      feld('projekt', 'Projekt (leer = alle)', d().el('input'), '');
      const pb = d().el('input'); pb.type = 'checkbox';
      const pbRow = d().el('label', 's-row s-small'); pbRow.append(pb, d().el('span', null, 'Personenbezug (bleibt lokal, nie Cloud)')); box.append(pbRow);
      box.append(d().button('Antrag stellen', async()=>{
        const args = {adapter: f.adapter.value, wurzel: f.wurzel.value, pfad: f.pfad.value, muster: f.muster.value, stufe: Number(f.stufe.value), projekt: f.projekt.value || null, personenbezug: !!pb.checked};
        const out = await this.verb('quelle_beantragen', args);
        this.sage(out); if(out && out.status === 'beantragt') this.form = false;
        await this.refresh();
      }, 'p'));
      return box;
    },

    // ---- Index: Modell-ID, Abdeckung, letzter Lauf, Gerät, Pause-Grund, Modus; Verb Nachführen
    async draw_index(stand){
      const box = d().el('div', 's-col');
      const l = stand.letzter_lauf || {};
      const t = d().el('table', 's-table');
      [['Modell-ID', stand.modell_id || '–'], ['Bereit', stand.bereit ? 'ja' : 'nein' + (stand.grund ? ' (' + stand.grund + ')' : '')], ['Modus', stand.modus || '–'],
       ['Abdeckung', Math.round((stand.abdeckung || 0) * 100) + ' % (' + stand.vektoren + ' von ' + stand.abschnitte + ')'], ['Neuaufbau', stand.neuaufbau ? 'läuft' : 'nein'],
       ['Gerät', (stand.geraet || 'cpu') + ' · Lage ' + (stand.lage || '–')], ['Server', stand.server_laeuft ? 'läuft' : 'aus'],
       ['Letzter Lauf', l.art ? l.art + ' · ' + l.status + ' · ' + d().fmtTime(l.start) + ' · ' + (l.eingebettet || 0) + ' eingebettet' : 'noch keiner'],
       ['Pause-Grund', stand.pause_grund || '–'], ['Zerleger / Fusion', (stand.zerleger || '–') + ' / ' + (stand.fusion || '–')], ['Offene Vorschläge', String(stand.vorschlaege_offen || 0)]]
        .forEach(([k, v])=>{ const tr = d().el('tr'); tr.append(d().el('td', 's-muted', k), d().el('td', null, v)); t.append(tr); });
      box.append(t);
      box.append(d().button('Nachführen', async()=>{
        const out = await this.verb('nachfuehren');
        this.hinweis = out && out.status === 'erledigt' ? {text: 'Abgleich: ' + out.abgleich.neu + ' neu, ' + out.abgleich.geaendert + ' geändert, ' + out.abgleich.entfernt + ' entfernt · Einbetten: ' + out.einbetten.eingebettet + ' (' + out.einbetten.ende + (out.einbetten.grund ? ': ' + out.einbetten.grund : '') + ')'} : {text: ergebnisSatz(out), bad: true};
        await this.refresh();
      }, 'p'));
      box.append(d().el('small', 's-muted', 'Das Einbetten läuft nur auf der CPU und hält an, solange ein Bau die GPU hat (WIS-12). Die GPU-Stufe folgt nach Spec 2.'));
      return box;
    },

    // ---- Suche: Eingabe, Treffer mit [id], Quelle, Stelle, Datum, Rang je Liste, Punkte, Hinweis; Kopfzeile → Quelle markiert, Zitate im Text → Treffer
    async draw_suche(){
      const box = d().el('div', 's-col');
      const form = d().el('form', 's-row'); form.onsubmit = e=>e.preventDefault();
      const input = d().el('input'); input.value = this.frage; input.placeholder = 'Frage an den Wissensspeicher';
      const k = d().el('input'); k.type = 'number'; k.value = '5'; k.min = '1'; k.max = '20'; k.className = 't-wissen-k';
      form.append(input, k, d().button('Suchen', async()=>{
        this.frage = input.value; this.aktiv = null; this.hinweis = null;
        this.ergebnis = await this.verb('suche', {frage: input.value, k: Number(k.value) || 5});
        if(this.ergebnis && this.ergebnis.status === 'fehler') this.sage(this.ergebnis);
        await this.draw();
      }, 'p'));
      box.append(form);
      const r = this.ergebnis;
      if(!r || r.status === 'fehler'){ if(!r) box.append(d().el('small', 's-muted', 'Noch keine Suche. Treffer tragen ihre Kennung [W…]; die Kopfzeile führt zur Quelle.')); return box; }
      box.append(d().el('div', 's-small s-muted', 'Modus ' + r.modus + (r.hinweis ? ' · ' + r.hinweis : '') + ' · ' + (r.ms || 0) + ' ms · Wörter: ' + (r.woerter || []).join(', ')));
      if(r.modus !== 'hybrid' && !r.hinweis) box.append(d().el('div', 's-note warn', 'Nur Volltextsuche: Treffer mit anderen Worten können fehlen.'));
      if(!(r.treffer || []).length){ box.append(d().empty('Im Wissensspeicher habe ich dazu nichts gefunden.')); return box; }
      r.treffer.forEach(t=>{
        const card = d().el('div', 's-card s-col t-wissen-treffer' + (this.aktiv === t.id ? ' t-wissen-aktiv' : ''));
        card.dataset.id = t.id;
        const head = d().el('div', 's-small', trefferZeile(t));
        head.title = 'Quelle ' + t.quelle + ' in der Ansicht „Quellen“ zeigen';
        d().clickable(head, ()=>this.zeigeQuelle(t));
        card.append(head, Z().zitatKnoten(d().el('pre', 't-wissen-text'), t.text, id=>this.zeigeTreffer(id)));
        if((t.befunde || []).length) card.append(d().el('small', 's-note warn', 'Befund des Inhaltsschutzes: ' + t.befunde.join(', ') + ' – Agenten sehen diesen Abschnitt nicht.'));
        box.append(card);
      });
      return box;
    },

    // ---- Nachmessung (D7.11): die Fragen des Captains, je Frage ein Urteil, Abschluss
    async draw_nachmessung(){
      const box = d().el('div', 's-col');
      const out = await this.verb('nachmessung');
      if(out && out.status === 'fehler'){ box.append(d().el('div', 's-note bad', 'Nachmessung nicht lesbar: ' + ergebnisSatz(out))); return box; }
      const saetze = (out && out.saetze) || [];
      if(!saetze.length){ box.append(d().empty('Noch keine Fragen protokolliert. Jede Suche von dir im Werkzeug landet hier (nur Hash und Treffer, kein Fragetext).')); return box; }
      const t = d().el('table', 's-table');
      saetze.forEach(s=>{
        const tr = d().el('tr');
        const sel = d().el('select'); [['', '–']].concat(URTEILE).forEach(([v, l])=>{ const o = d().el('option', null, l); o.value = v; sel.append(o); }); sel.value = s.urteil || '';
        sel.onchange = async()=>{ this.sage(await this.verb('nachmessung_bewerten', {frage_sha256: s.frage_sha256, urteil: sel.value})); await this.draw(); };
        const ids = Z().zitatKnoten(d().el('td', 's-small'), (s.ids || []).map(i=>'[' + i + ']').join(' '), id=>this.zeigeTreffer(id));
        tr.append(d().el('td', 's-small', d().fmtTime(s.zeit)), d().el('td', 's-small s-muted', s.frage_sha256.slice(0, 12) + ' · ' + s.modus), ids, d().el('td', null, sel));
        t.append(tr);
      });
      box.append(t);
      box.append(d().button('Nachmessung abschließen', async()=>{
        const r = await this.verb('nachmessung_abschliessen');
        this.hinweis = r && r.status === 'erledigt' ? {text: r.fragen + ' Fragen, ' + r.getroffen + ' getroffen' + (r.anteil !== null && r.anteil !== undefined ? ' (' + Math.round(r.anteil * 100) + ' %)' : '') + ' · ' + r.datei} : {text: ergebnisSatz(r), bad: true};
        await this.refresh();
      }));
      return box;
    },

    // ---- Vorschläge: offen mit Herkunft und Belegen; die Freigabe läuft im Posteingang (Werkzeug decisions)
    async draw_vorschlaege(){
      const box = d().el('div', 's-col');
      const liste = await this.post({type: 'wissen_vorschlag', status: ''});
      const items = liste.items || [];
      if(!items.length){ box.append(d().empty('Keine Vorschläge. Ein Agent kann in einem Lauf Wissen vorschlagen; es wird erst nach deiner Freigabe im Posteingang aufgenommen.')); return box; }
      const zeige = id=>this.zeigeTreffer(id);
      items.forEach(v=>{
        const card = d().el('div', 's-card s-col t-wissen-vorschlag');
        card.dataset.id = v.id;
        const head = d().el('div', 's-row');
        head.append(d().el('b', null, v.title), d().el('span', 's-small s-muted', v.state + ' · ' + v.summary));
        card.append(head, Z().zitatKnoten(d().el('pre', 't-wissen-text'), v.text, zeige));
        const herkunft = d().el('small', 's-muted', 'Herkunft: Agent ' + (v.agent_id || '?') + ' · Lauf ' + (v.lauf_id || '?') + ' · Aufgabe ' + (v.aufgabe_id || '?') + ' · Belege ');
        Z().zitatKnoten(herkunft, (v.belege || []).map(i=>'[' + i + ']').join(' ') || 'keine', zeige);
        card.append(herkunft);
        if(v.state === 'offen') card.append(d().el('small', 's-note', 'Freigeben oder ablehnen im Posteingang.'));
        const row = d().el('div', 's-row');
        (v.actions || []).forEach(a=>row.append(d().button(a.label || a.verb, async()=>{ this.sage(await this.verb(a.verb, {}, v.id, 'wissen_vorschlag')); await this.refresh(); })));
        if(v.agent_id) row.append(d().button('Agent öffnen', ()=>this.ctx.shell.open({type: 'agent', id: v.agent_id, title: v.agent_id})));
        card.append(row);
        box.append(card);
      });
      return box;
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraWissenPure = {zustandText, trefferZeile, ergebnisSatz, markierungText};
  if(typeof module !== 'undefined' && module.exports) module.exports = {zustandText, trefferZeile, ergebnisSatz, markierungText, tool};
})();
