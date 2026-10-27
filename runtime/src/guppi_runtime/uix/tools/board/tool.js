// Werkzeug „Issues“ (Spec 4, D4.2.2): die Aufgaben des Teams als Liste oder Board nach Zustand, und ein Issue im Einzelnen
// (detail.js). Gelesen wird über POST /api/objects, gehandelt nur mit den Verben aus `actions` (POST /api/actions). Karten werden
// nicht gezogen: den Zustand ändert die Orchestrierung, nicht die Maus. Kein Zeitgeber – neu gelesen wird bei Ereignissen.
// Ehrlich leer (UIX-10): ohne `quelle` oder bei ausgeschalteter Orchestrierung sagt die Seite das und zeigt den Weg zu den Missionen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const S = ()=>root.sedraBoardSpalten;
  const MASCHINENRAUM = {type: 'machine', id: 'machine', title: 'Maschinenraum'};
  const MISSIONEN = {type: 'task', id: 'alle', title: 'Läufe (Missionen)', collection: true};
  const KOMPAKT_MAX = 8;
  // Verben, die Angaben brauchen (Name, Beschriftung, Art); die Prüfung bleibt beim Server
  const FORMS = {
    anlegen: [['titel', 'Titel'], ['beschreibung', 'Beschreibung', 'text'], ['vorhaben_id', 'Vorhaben (optional)'], ['bearbeiter', 'Bearbeiter (optional)', 'agent']],
    zuweisen: [['bearbeiter', 'Bearbeiter', 'agent']],
    blocker_setzen: [['blocker', 'Blockiert durch', 'issue']],
    kommentieren: [['text', 'Kommentar', 'text']]
  };

  function quelleZustand(liste, fehler){
    if(fehler){
      const t = String(fehler);
      if(t.indexOf('unknown_object_type') >= 0) return 'aus';
      return t.indexOf('orchestra_busy') >= 0 ? 'belegt' : 'lesefehler';
    }
    const z = ((liste || {}).quelle || {}).zustand;
    return z === 'bereit' || z === 'fehler' ? z : 'aus';
  }

  function ergebnisSatz(out){
    if(out && (out.needs_gate || (out.result && (out.result.decision || out.result.gate_id || out.result.status === 'pending'))))
      return 'Antrag liegt im Posteingang.';
    return 'Erledigt.';
  }

  const einzeln = o=>!!(o && o.id && o.id !== 'alle' && !o.collection);

  const tool = {
    id: 'board',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      this.liste = null; this.issue = null; this.namen = new Map(); this.fehler = null; this.hinweis = null; this.form = null;
      this.filter = {bearbeiter: '', text: '', nurOffen: false}; this.offen = {};
      el.classList.add('t-board');
      let running = null, again = false;
      this.schub = ()=>{
        if(running){ again = true; return running; }
        running = this.refresh().finally(()=>{ running = null; if(again){ again = false; this.schub(); } });
        return running;
      };
      ['issue.changed', 'agent.changed', 'decision.answered', 'desk.resync'].forEach(n=>ctx.bus.on(n, ()=>this.schub()));
      return this.schub();
    },

    unmount(){ this.el.classList.remove('t-board'); this.el.replaceChildren(); this.liste = null; this.issue = null; },

    async refresh(){
      if(!this.el) return;
      const o = this.ctx.object || {};
      const agents = this.ctx.api('/api/objects', {method: 'POST', body: {type: 'agent'}}).catch(()=>null);
      try{
        const [liste, issue] = await Promise.all([this.ctx.api('/api/objects', {method: 'POST', body: {type: 'issue'}}),
          einzeln(o) ? this.ctx.api('/api/objects', {method: 'POST', body: {type: 'issue', id: o.id}}) : null]);
        this.liste = liste; this.issue = issue; this.fehler = null;
      }catch(err){ this.fehler = err.message || String(err); }
      const a = await agents;
      this.namen = new Map(((a || {}).items || []).map(x=>[String(x.id), String(x.title || x.id)]));
      this.draw();
    },

    open(object){ this.ctx.shell.open(object); },
    name(id){ return id ? (this.namen.get(String(id)) || String(id)) : 'niemand'; },

    draw(){
      const box = d().el('div', 's-col');
      const zustand = quelleZustand(this.liste, this.fehler);
      if(this.hinweis) box.append(d().el('div', 's-note' + (this.hinweis.bad ? ' bad' : ''), this.hinweis.text));
      if(zustand === 'aus' || zustand === 'fehler'){
        box.append(d().el('div', 's-note' + (zustand === 'fehler' ? ' bad' : ''), zustand === 'fehler'
          ? 'Die Orchestrierung ist ausgefallen: ' + ((this.liste.quelle || {}).grund || 'ohne Grund') + '.'
          : 'Die Orchestrierung ist ausgeschaltet (Schalter „orchestra“). Sobald sie läuft, stehen die Issues des Teams hier.'));
        const bar = d().el('div', 's-row');
        bar.append(d().button('Läufe (Missionen) ansehen', ()=>this.open(MISSIONEN)), d().button('Maschinenraum öffnen', ()=>this.open(MASCHINENRAUM)));
        box.append(bar);
        return this.el.replaceChildren(box);
      }
      if(zustand === 'belegt' || zustand === 'lesefehler'){
        box.append(d().el('div', 's-note bad', zustand === 'belegt' ? 'Die Datenbank ist gerade belegt.' : 'Die Issues sind nicht lesbar: ' + this.fehler));
        box.append(d().button('Noch einmal lesen', ()=>this.schub()));
        return this.el.replaceChildren(box);
      }
      if(einzeln(this.ctx.object)){ box.append(root.sedraBoardDetail.draw(this)); return this.el.replaceChildren(box); }
      if(this.form && !this.form.issue) box.append(this.drawForm(this.form));
      const items = this.liste.items || [];
      if(!items.length){
        box.append(d().empty('Noch keine Issues. „Anlegen“ erzeugt eine Aufgabe für einen Agenten; eine Anweisung an den Unterarbeiter erzeugt sie für dich.'));
        return this.el.replaceChildren(box);
      }
      const kompakt = !!(this.ctx.object && this.ctx.object.kompakt);
      const view = !kompakt && (this.ctx.object || {}).view === 'board' ? 'board' : 'liste';
      if(!kompakt) box.append(this.toolbar(view, items));
      this.result = d().el('div', 't-board-result');
      box.append(this.result);
      this.el.replaceChildren(box);
      this.drawResult(view, kompakt);
    },

    toolbar(view, items){
      const bar = d().el('div', 's-row t-board-bar');
      [['liste', 'Liste'], ['board', 'Board']].forEach(([v, label])=>{
        const b = d().button(label, ()=>this.open({type: 'issue', id: 'alle', title: 'Issues', collection: true, view: v}), v === view ? 'p' : '');
        b.setAttribute('aria-pressed', String(v === view));
        bar.append(b);
      });
      const wer = d().el('select');
      wer.setAttribute('aria-label', 'Bearbeiter');
      const ids = Array.from(new Set(items.map(i=>S().feld(i).bearbeiter).filter(Boolean))).sort();
      [['', 'alle Bearbeiter'], ['-', 'niemand']].concat(ids.map(id=>[id, this.name(id)])).forEach(([v, label])=>{
        const o = d().el('option', null, label); o.value = v; wer.append(o);
      });
      wer.value = this.filter.bearbeiter;
      wer.onchange = ()=>{ this.filter.bearbeiter = wer.value; this.drawResult(view); };
      const text = d().el('input');
      text.type = 'search'; text.placeholder = 'Text …'; text.value = this.filter.text;
      text.setAttribute('aria-label', 'Text');
      text.oninput = ()=>{ this.filter.text = text.value; this.drawResult(view); };
      const nur = d().el('label', 's-row s-small');
      const box = d().el('input'); box.type = 'checkbox'; box.checked = this.filter.nurOffen;
      box.onchange = ()=>{ this.filter.nurOffen = box.checked; this.drawResult(view); };
      nur.append(box, d().el('span', null, 'nur offene'));
      bar.append(wer, text, nur);
      return bar;
    },

    drawResult(view, kompakt){
      const items = (this.liste && this.liste.items) || [];
      if(view === 'board') return this.result.replaceChildren(this.drawBoard(items));
      let rows = S().listRows(items, {filter: kompakt ? {nurOffen: true} : this.filter});
      const mehr = kompakt && rows.length > KOMPAKT_MAX ? rows.length - KOMPAKT_MAX : 0;
      if(mehr) rows = rows.slice(0, KOMPAKT_MAX);
      const t = d().el('table', 's-table t-board-table');
      const head = d().el('tr');
      (kompakt ? ['Issue', 'Zustand', 'Bearbeiter'] : ['Issue', 'Zustand', 'Bearbeiter', 'Priorität', 'Blocker', 'Kommentare'])
        .forEach(h=>head.append(d().el('th', null, h)));
      t.append(head);
      rows.forEach(i=>{
        const tr = d().el('tr');
        tr.dataset.issue = i.id;
        const titel = d().el('td');
        titel.append(d().el('b', null, i.title), d().el('small', 's-muted', ' ' + i.id));
        tr.append(titel, d().el('td', 't-board-state ' + i.zustand, this.zustandWort(i.zustand)), d().el('td', null, this.name(i.bearbeiter)));
        if(!kompakt) tr.append(d().el('td', null, String(i.prioritaet)), d().el('td', null, i.blocker.length ? '⛔ ' + i.blocker.join(', ') : ''),
                               d().el('td', null, i.kommentare ? String(i.kommentare) : ''));
        d().clickable(tr, ()=>this.open({type: 'issue', id: i.id, title: i.title}));
        t.append(tr);
      });
      const out = d().el('div', 's-col');
      out.append(rows.length ? t : d().empty('Kein Issue passt zum Filter.'));
      if(mehr) out.append(d().el('small', 's-muted', 'und ' + mehr + ' weitere unter „Issues“'));
      this.result.replaceChildren(out);
    },

    zustandWort(z){ const hit = S().ZUSTAENDE.find(x=>x[0] === z); return hit ? hit[1] : (z || '–'); },

    drawBoard(items){
      const grid = d().el('div', 't-board-grid');
      S().boardColumns(items, {filter: this.filter}).forEach(col=>{
        const zu = col.eingeklappt && !this.offen[col.state];
        const box = d().el('section', 't-board-col' + (zu ? ' zu' : ''));
        box.dataset.state = col.state;
        const head = d().el('header', 's-row');
        head.append(d().el('b', null, col.label), d().el('span', 's-muted', String(col.count)));
        if(col.eingeklappt) head.append(d().button(zu ? '▸' : '▾', ()=>{ this.offen[col.state] = zu; this.drawResult('board'); }, 't-board-fold'));
        box.append(head);
        if(!zu) col.items.forEach(i=>{
          const card = d().el('div', 't-board-card');
          card.dataset.issue = i.id;
          card.append(d().el('b', null, i.title));
          const meta = d().el('small', 's-muted', this.name(i.bearbeiter) + ' · P' + i.prioritaet + (i.blocker.length ? ' · ⛔ blockiert' : '') +
                                                  (i.kommentare ? ' · 💬 ' + i.kommentare : ''));
          card.append(meta);
          d().clickable(card, ()=>this.open({type: 'issue', id: i.id, title: i.title}));
          box.append(card);
        });
        grid.append(box);
      });
      return grid;
    },

    // Ein kleines Formular für ein Verb mit Angaben; `form` = {verb, issue}
    drawForm(form){
      const {verb, issue} = form;
      const box = d().el('form', 's-card s-col t-board-form');
      box.append(d().el('b', null, (verb.label || verb.verb) + (issue ? ' – ' + (issue.title || issue.id) : '')));
      const fields = {};
      FORMS[verb.verb].forEach(([key, label, art])=>{
        const row = d().el('label', 's-col s-small');
        row.append(d().el('span', 's-muted', label));
        let input;
        if(art === 'agent' || art === 'issue'){
          input = d().el('select');
          const none = d().el('option', null, art === 'agent' ? 'niemand' : '–'); none.value = ''; input.append(none);
          const choices = art === 'agent' ? Array.from(this.namen.entries())
            : ((this.liste && this.liste.items) || []).filter(i=>!issue || String(i.id) !== String(issue.id)).map(i=>[String(i.id), i.title + ' (' + i.id + ')']);
          choices.forEach(([v, l])=>{ const o = d().el('option', null, l); o.value = v; input.append(o); });
        }else if(art === 'text'){ input = d().el('textarea'); input.rows = 3; }
        else{ input = d().el('input'); input.type = 'text'; }
        if(form.werte && form.werte[key] !== undefined) input.value = form.werte[key];
        fields[key] = input;
        row.append(input);
        box.append(row);
      });
      const bar = d().el('div', 's-row');
      bar.append(d().button('Absenden', async()=>{
        const args = {};
        Object.keys(fields).forEach(k=>{ args[k] = fields[k].value; });
        form.werte = args;                              // abgewiesen: die Eingabe bleibt stehen
        await this.run(issue, verb, args);
      }, 'p', {absenden: true}));
      if(verb.verb !== 'kommentieren') bar.append(d().button('Abbrechen', ()=>{ this.form = null; this.draw(); }));
      box.append(bar);
      box.onsubmit = e=>e.preventDefault();
      return box;
    },

    verb(issue, verb){
      if(FORMS[verb.verb]){ this.form = {verb, issue}; this.hinweis = null; this.draw(); return Promise.resolve(); }
      if(!confirm(verb.confirm || ((verb.label || verb.verb) + (issue ? ' – ' + (issue.title || issue.id) : '') + '?'))) return Promise.resolve();
      return this.run(issue, verb, {});
    },

    async run(issue, verb, args){
      const body = issue ? {type: 'issue', id: issue.id, verb: verb.verb, args} : {type: 'issue', verb: verb.verb, args};
      try{
        const out = await this.ctx.api('/api/actions', {method: 'POST', body});
        this.form = null;
        if(this.kform && verb.verb === 'kommentieren') this.kform.werte = {};     // gesendet: das Feld wird leer
        this.hinweis = {text: (verb.label || verb.verb) + ': ' + ergebnisSatz(out)};
      }catch(err){ this.hinweis = {text: err.message || String(err), bad: true}; }
      this.draw();
    },

    // Die Kopfzeile der Seite: am Typ „anlegen“ (aus der Liste), am Issue die Verben ohne Formular (z. B. „abbrechen“)
    actions(){
      if(einzeln(this.ctx && this.ctx.object)){
        const issue = this.issue;
        if(!issue || issue.missing) return [];
        return (issue.actions || []).filter(v=>!FORMS[v.verb]).map(v=>({label: v.label || v.verb, run: ()=>this.verb(issue, v)}));
      }
      return ((this.liste && this.liste.actions) || []).map(v=>({label: v.label || v.verb, run: ()=>this.verb(null, v)}));
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraBoardPure = {quelleZustand, ergebnisSatz, FORMS};
  if(typeof module !== 'undefined' && module.exports) module.exports = {quelleZustand, ergebnisSatz, FORMS, tool};
})();
