// Werkzeug „Wissen“ v2 (Spec 7, D7.9; SPEC_WERKZEUG_WISSEN_v2): der Wissensspeicher in vier Ansichten – Suche (Start), Quellen,
// Vorschläge, Messung (Index und Nachmessung). Hier: Zustand, Gedächtnis, Reiterzeile, Handlungen der Werkbank-Zeile, Vorschläge.
// Die Ansichten zeichnen suche.js, quellen.js (mit dem geführten Antrag aus antrag.js) und messung.js; zitate.js hat die reinen Teile.
// Gelesen wird nur über POST /api/objects, gehandelt nur über POST /api/actions; eine Freigabe ist ein Antrag im Posteingang.
// Kein Zeitgeber: neu gelesen wird bei decision.answered und desk.resync. Aufklappen, Formulare, Filter zeichnen aus dem Vorrat (V7).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const Z = ()=>root.sedraWissenZitate;
  const A = ()=>root.sedraWissenAnsichten || {};
  const ANSICHTEN = [['suche', 'Suche'], ['quellen', 'Quellen'], ['vorschlaege', 'Vorschläge'], ['eigenes', 'Eigenes'], ['messung', 'Messung']];
  // WZ2: index und nachmessung sind Abschnitte der Messung; eigenes sind die Notizen des Captains (Wissensbasis §4.4, eigenes.js)
  const UM = {index: 'messung', nachmessung: 'messung'};
  // was wohin gehört (Vertrag 1.1): Zustand der Ansicht in die Sitzung, Inhalt (Frage, Treffer, Eingaben) in die Ablage
  const SITZUNG = ['ansicht', 'k', 'abschnitt', 'aufgeklappt', 'filterQuellen', 'filterVorschlaege', 'markiertQuelle', 'filterOffen'];
  const ABLAGE = ['frage', 'ergebnis', 'ergebnisZeit', 'antrag', 'markiert', 'entwurf', 'filter'];   // filter: Projekt ist Inhalt
  const LEER = Object.freeze({get: (_n, v)=>v, set(){}, clear(){}});
  const LEER_ABLAGE = Object.freeze({get: async(_n, v)=>v, set(){}, clear(){}, flush(){}});

  // Der Satz zum Stand des Index (rein)
  function zustandText(stand){
    if(!stand) return 'Kein Stand.';
    const p = Math.round((stand.abdeckung || 0) * 100), z = n=>root.sedraDom.fmtNumber(n);
    if(!stand.bereit) return 'Nur Volltextsuche (' + (stand.grund || 'kein Modell') + ') · ' + z(stand.abschnitte) + ' Abschnitte';
    if(stand.neuaufbau) return 'Neuaufbau läuft · Abdeckung ' + p + ' % · ' + z(stand.vektoren) + ' von ' + z(stand.abschnitte) + ' eingebettet';
    return (stand.modus === 'hybrid' ? 'Hybride Suche' : 'Nur Volltextsuche') + ' · Abdeckung ' + p + ' % · ' + z(stand.abschnitte) + ' Abschnitte';
  }

  // Die Details eines Treffers (rein): [id] Datei > Stelle · Datum · Ränge · Punkte – steht zugeklappt unter „Details“
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

  // welche Ansicht ein Objekt öffnet (rein): view am Objekt geht vor, dann die Sitzung, dann die Suche (WZ1)
  function ansichtFuer(view, gemerkt){
    const bekannt = ANSICHTEN.map(a=>a[0]);
    const v = UM[view] || view;
    if(bekannt.indexOf(v) >= 0) return v;
    return bekannt.indexOf(gemerkt) >= 0 ? gemerkt : 'suche';
  }

  const tool = {
    id: 'wissen',

    async mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-wissen');
      const o = ctx.object || {};
      this.memo = ctx.memo || LEER; this.sitzung = ctx.sitzung || LEER; this.ablage = ctx.ablage || LEER_ABLAGE;
      this.d = {speicher: null, quellen: null, vorschlaege: null, nachmessung: null, notizen: null};
      this.fehler = null; this.hinweis = null; this.laedt = false; this.frisch = false;   // frisch: Treffer dieser Sitzung (sonst „Treffer von HH:MM“)
      // der Zustand: aus dem Memo (dieselbe Seite), sonst Sitzung und Ablage (nach Neuladen oder Shell-Wechsel)
      const s = {ansicht: 'suche', abschnitt: null, k: 5, aufgeklappt: [], filterQuellen: 'alle', filterVorschlaege: 'offen', markiertQuelle: null,
                 frage: '', ergebnis: null, ergebnisZeit: null, antrag: null, markiert: null, aktiv: null, menu: null, stufeForm: null,
                 entwurf: null, loeschen: null, filter: null, filterOffen: false};
      const vorher = this.memo.get('zustand', null);
      if(vorher) Object.assign(s, vorher);
      else{
        SITZUNG.forEach(k=>{ s[k] = this.sitzung.get(k, s[k]); });
        for(const k of ABLAGE) s[k] = await this.ablage.get(k, s[k]);
      }
      s.ansicht = ansichtFuer(o.view, s.ansicht);
      if(o.view === 'index' || o.view === 'nachmessung') s.abschnitt = o.view;
      if(o.quelle){ s.markiert = {quelle: String(o.quelle)}; s.ansicht = o.view ? s.ansicht : 'quellen'; }
      else if(s.markiert && s.markiertQuelle !== s.markiert.quelle) s.markiert = s.markiertQuelle ? {quelle: s.markiertQuelle} : null;
      // ein Auftrag aus der Shell (Palette „Im Wissen suchen“, Menü „Quelle für Wissen“) liegt einmal im Memo, nie im Objekt
      const auftrag = this.memo.get('auftrag', null);
      if(auftrag){ this.memo.set('auftrag', null); if(auftrag.frage){ s.ansicht = 'suche'; s.frage = auftrag.frage; } if(auftrag.antrag){ s.ansicht = 'quellen'; s.antrag = {schritt: 1}; } }
      this.s = s;
      ['decision.answered', 'desk.resync'].forEach(n=>ctx.bus.on(n, ()=>this.refresh(true)));
      await this.refresh(false);
      if(auftrag && auftrag.frage && A().suche && A().suche.suchen) await A().suche.suchen(this, auftrag.frage, s.k || 5);
    },

    unmount(){ this.merken(); this.el.classList.remove('t-wissen'); this.el.replaceChildren(); this.d = null; },

    // ---- Gedächtnis: nach jeder Änderung (Vertrag 1.1); in die Sitzung nur Zustand der Ansicht, nie Frage oder Treffer
    merken(){
      if(!this.s) return;
      const s = this.s;
      s.markiertQuelle = s.markiert ? s.markiert.quelle : null;
      this.memo.set('zustand', Object.assign({}, s));
      SITZUNG.forEach(k=>this.sitzung.set(k, s[k]));
      ABLAGE.forEach(k=>this.ablage.set(k, s[k]));
    },

    post(body){ return this.ctx.api('/api/objects', {method: 'POST', body}); },
    act(body){ return this.ctx.api('/api/actions', {method: 'POST', body}); },
    // Ein Verb des Desk; ein Fehler aus ctx.api() wird ein Ergebnis {status: fehler, satz} auf Deutsch, nie eine Konsolenzeile
    verb(verb, args, id, type){
      return this.act(Object.assign({type: type || 'wissen', verb, args: args || {}}, id ? {id} : {}))
        .then(r=>r && r.result !== undefined ? r.result : r, err=>({status: 'fehler', code: String(err && err.message || err), satz: Z().fehlerSatz(err)}));
    },
    sage(out, bad){ this.hinweis = {text: ergebnisSatz(out), bad: bad || (out && out.status === 'fehler')}; },

    // Der Speicher und die Daten der offenen Ansicht lesen. `alles`: auch die Vorräte der anderen Ansichten verwerfen.
    async refresh(alles){
      if(!this.el || !this.d) return;
      try{ this.d.speicher = await this.post({type: 'wissen', id: 'speicher'}); this.fehler = null; }
      catch(err){ this.fehler = Z().fehlerSatz(err); this.d.speicher = null; }
      if(alles) Object.assign(this.d, {quellen: null, vorschlaege: null, nachmessung: null, notizen: null});
      return this.laden();
    },
    // nur, was die Ansicht braucht und noch nicht im Vorrat ist (V7: Aufklappen und Formulare lesen nichts)
    async laden(){
      const v = A()[this.s.ansicht];
      if(!this.aus() && v && v.laden){
        try{ await v.laden(this); }
        catch(err){ this.hinweis = {text: 'Nicht lesbar: ' + Z().fehlerSatz(err), bad: true}; }
      }
      return this.draw();
    },
    aus(){ return this.fehler ? this.fehler.indexOf('unknown_object_type') >= 0 : ((this.d.speicher || {}).state === 'aus'); },

    wechseln(ansicht){
      this.s.ansicht = ansicht; this.s.menu = null; this.hinweis = null;
      // die Werkbank-Zeile zeigt die Handlungen der Ansicht (WZ3): der Shell sagen, dass sie sich geändert haben
      return this.laden().then(()=>{ try{ this.ctx.bus.emit('object.actions', {type: 'wissen', id: 'speicher'}); }catch(_e){} });
    },

    draw(){
      if(!this.el || !this.d) return;
      this.merken();
      const box = d().el('div', 's-col');
      if(this.fehler || this.aus()){
        const sp = this.d.speicher || {};
        box.append(d().el('div', 's-note' + (this.aus() ? '' : ' bad'), this.aus() ? 'Der Wissensspeicher ist ausgeschaltet (Schalter „wissen“ in local_config/switches.yaml)' + (sp.grund ? ' – ' + sp.grund : '') + '. Sobald er läuft, stehen Suche, Quellen und Messung hier.' : 'Wissen nicht lesbar: ' + this.fehler));
        if(!this.aus()) box.append(d().button('Erneut versuchen', ()=>this.refresh(true)));
        return this.el.replaceChildren(box);
      }
      const stand = (this.d.speicher || {}).stand || {};
      box.append(d().el('div', 's-note t-wissen-stand ' + (stand.modus === 'hybrid' ? 'ok' : 'warn'), zustandText(stand)));
      box.append(this.reiter(stand));
      if(this.hinweis) box.append(d().el('div', 's-note' + (this.hinweis.bad ? ' bad' : ''), this.hinweis.text));
      const teil = d().el('div', 't-wissen-teil');
      const v = A()[this.s.ansicht];
      try{ teil.append(v ? v.zeichnen(this) : this.zeichneVorschlaege()); }
      catch(err){ teil.append(d().el('div', 's-note bad', 'Nicht lesbar: ' + Z().fehlerSatz(err))); }
      box.append(teil);
      this.el.replaceChildren(box);
      const fokus = this.el.querySelector('.t-wissen-fokus') || this.el.querySelector('.t-wissen-aktiv') || this.el.querySelector('.t-wissen-markiert');
      if(fokus){ if(fokus.tagName === 'INPUT' || fokus.tagName === 'SELECT') fokus.focus(); else if(fokus.scrollIntoView) fokus.scrollIntoView({block: 'nearest'}); }
    },

    // §3.1: Reiter statt Knopfreihe; Zahlen aus dem einen Objekt `wissen:speicher` (Z2), Pfeiltasten wechseln
    reiter(stand){
      const tabs = d().el('div', 's-row t-wissen-tabs'); tabs.setAttribute('role', 'tablist');
      ANSICHTEN.forEach(([id, label], i)=>{
        let text = label;
        if(id === 'quellen' && stand.quellen) text += ' (' + stand.quellen + ')';
        if(id === 'vorschlaege' && stand.vorschlaege_offen) text += ' ⚠ ' + stand.vorschlaege_offen;
        const b = d().el('button', 's-btn t-wissen-tab' + (this.s.ansicht === id ? ' on' : '') + (id === 'vorschlaege' && stand.vorschlaege_offen ? ' warn' : ''), text);
        b.type = 'button'; b.dataset.ansicht = id; b.setAttribute('role', 'tab'); b.setAttribute('aria-selected', this.s.ansicht === id ? 'true' : 'false');
        b.tabIndex = this.s.ansicht === id ? 0 : -1;
        b.onclick = ()=>this.wechseln(id);
        b.onkeydown = e=>{
          const n = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
          if(n){ e.preventDefault(); this.wechseln(ANSICHTEN[(i + n + ANSICHTEN.length) % ANSICHTEN.length][0]); }
        };
        tabs.append(b);
      });
      return tabs;
    },

    // Treffer → Quelle: die Ansicht „Quellen“ mit der Quelle des Treffers markiert (Stelle, Datum, ID in der Zeile darunter)
    zeigeQuelle(t){
      this.s.markiert = {quelle: String(t.quelle), id: t.id, datei: t.datei, stelle: t.stelle, datum: t.datum};
      return this.wechseln('quellen');
    },
    // Zitat [W…] → Treffer: in der Ansicht „Suche“ hervorgehoben, wenn er in der letzten Suche steht
    zeigeTreffer(id){
      const da = ((this.s.ergebnis || {}).treffer || []).some(t=>t.id === id);
      this.s.aktiv = da ? id : null;
      this.s.ansicht = 'suche';
      this.hinweis = da ? null : {text: 'Der Abschnitt [' + id + '] steht nicht in der letzten Suche. Suche neu, dann ist er hier anklickbar.'};
      return this.draw();
    },

    // ---- Vorschläge (§3.5): Filter offen · entschieden · alle; Entscheidung im Posteingang mit einem Klick
    zeichneVorschlaege(){
      const box = d().el('div', 's-col');
      const filter = d().el('div', 's-row t-wissen-filter');
      [['offen', 'offen'], ['entschieden', 'entschieden'], ['alle', 'alle']].forEach(([id, label])=>{
        filter.append(d().button(label, ()=>{ this.s.filterVorschlaege = id; return this.draw(); }, this.s.filterVorschlaege === id ? 'p' : ''));
      });
      box.append(filter);
      const alle = this.d.vorschlaege || [];
      const items = alle.filter(v=>this.s.filterVorschlaege === 'alle' || (this.s.filterVorschlaege === 'offen' ? v.state === 'offen' : v.state !== 'offen'));
      if(!items.length){ box.append(d().empty(alle.length ? 'In diesem Filter keine Vorschläge.' : 'Keine Vorschläge. Ein Agent kann in einem Lauf Wissen vorschlagen; es wird erst nach deiner Freigabe im Posteingang aufgenommen.')); return box; }
      const zeige = id=>this.zeigeTreffer(id);
      items.forEach(v=>{
        const card = d().el('div', 's-card s-col t-wissen-vorschlag'); card.dataset.id = v.id;
        const head = d().el('div', 's-row');
        head.append(d().el('b', null, v.title), d().el('span', 't-wissen-marke' + (v.state === 'offen' ? ' warn' : ''), v.state), d().el('span', 's-small s-muted', v.summary));
        card.append(head, Z().zitatKnoten(d().el('pre', 't-wissen-text t-wissen-kurz'), v.text, zeige));
        const herkunft = d().el('small', 's-muted', 'Herkunft: Agent ' + (v.agent_id || '?') + ' · Lauf ' + (v.lauf_id || '?') + ' · Aufgabe ' + (v.aufgabe_id || '?') + ' · Belege ');
        Z().zitatKnoten(herkunft, (v.belege || []).map(i=>'[' + i + ']').join(' ') || 'keine', zeige);
        card.append(herkunft);
        const row = d().el('div', 's-row');
        if(v.state === 'offen'){
          card.append(d().el('small', 's-note', 'Freigeben oder ablehnen im Posteingang.'));
          // der eine Posteingang (das Werkzeug „Entscheidungen“ zeigt alle offenen; ein Reiter je Vorschlag wäre nur ein Doppel)
          row.append(d().button('Im Posteingang entscheiden', ()=>this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true}), 'p'));
        }
        (v.actions || []).forEach(a=>row.append(d().button(a.label || a.verb, async()=>{ this.sage(await this.verb(a.verb, {}, v.id, 'wissen_vorschlag')); await this.refresh(true); })));
        if(v.agent_id) row.append(d().button('Agent öffnen', ()=>this.ctx.shell.open({type: 'agent', id: v.agent_id, title: v.agent_id})));
        card.append(row);
        box.append(card);
      });
      return box;
    },

    // ---- die Werkbank-Zeile (Regel 3, WZ3): die Handlungen der offenen Ansicht
    actions(){
      if(!this.s || !this.d || this.fehler || this.aus()) return [];
      const v = A()[this.s.ansicht];
      if(v && v.aktionen) return v.aktionen(this);
      if(this.s.ansicht === 'vorschlaege') return [{label: 'Zum Posteingang', run: ()=>this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true})}];
      return [];
    }
  };

  // die Vorschläge lesen (die Ansicht hat keinen eigenen Baustein)
  root.sedraWissenAnsichten = Object.assign(root.sedraWissenAnsichten || {}, {vorschlaege: {
    async laden(t){ if(!t.d.vorschlaege) t.d.vorschlaege = (await t.post({type: 'wissen_vorschlag', status: ''})).items || []; },
    zeichnen(t){ return t.zeichneVorschlaege(); }
  }});

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraWissenPure = {zustandText, trefferZeile, ergebnisSatz, markierungText, ansichtFuer};
  if(typeof module !== 'undefined' && module.exports) module.exports = {zustandText, trefferZeile, ergebnisSatz, markierungText, ansichtFuer, tool};
})();
