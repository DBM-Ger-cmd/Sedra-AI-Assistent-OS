// Werkzeug „Organigramm“ (Spec 4, D4.2.1): das Team als Baum oder Liste – Vorgesetzte, Rolle, Status, Budget und offene
// Entscheidungen je Agent. Gelesen wird mit einer Anfrage (POST /api/objects {type:'agent'}); gehandelt nur mit den Verben, die der
// Server in `actions` anbietet (POST /api/actions). Kein Zeitgeber: neu gelesen wird bei Ereignissen und bei `desk.resync`.
// Ehrlich leer (UIX-10): fehlt `quelle` oder ist die Orchestrierung aus, sagt die Seite das – keine erfundene Zahl.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const B = ()=>root.sedraOrgBaum;
  const MASCHINENRAUM = {type: 'machine', id: 'machine', title: 'Maschinenraum'};
  const STATUS = {aktiv: 'aktiv', arbeitet: 'arbeitet', pausiert: 'pausiert', beendet: 'beendet'};
  // Verben, die Angaben brauchen: das Formular nennt sie, die Prüfung bleibt beim Server
  const FORMS = {
    einstellen: [['name', 'Name'], ['vorlage', 'Vorlage (Rezept)'], ['reports_to', 'Vorgesetzter', 'agent'], ['budget_tokens', 'Budget in Token', 'number']],
    einordnen: [['reports_to', 'Neuer Vorgesetzter', 'agent']]
  };

  // In welchem Zustand die Liste ist (rein): aus, fehler, bereit – oder ein Lesefehler. Ein alter Server ohne `quelle` heißt „aus“.
  function quelleZustand(liste, fehler){
    if(fehler){
      const t = String(fehler);
      if(t.indexOf('unknown_object_type') >= 0) return 'aus';
      return t.indexOf('orchestra_busy') >= 0 ? 'belegt' : 'lesefehler';
    }
    const z = ((liste || {}).quelle || {}).zustand;
    return z === 'bereit' || z === 'fehler' ? z : 'aus';
  }

  // Was der Baum zeigt (rein): ohne beendete, außer der Schalter steht
  function sichtbar(items, beendeteZeigen){
    return (items || []).filter(a=>beendeteZeigen || (a.status || a.state) !== 'beendet');
  }

  function statusWort(a){ return a.arbeitet ? 'arbeitet' : (STATUS[a.status || a.state] || String(a.status || a.state || '')); }

  // Der Satz nach einem Verb (rein): mit Gate ist es ein Antrag, nicht „erledigt“
  function ergebnisSatz(out){
    if(out && (out.needs_gate || (out.result && (out.result.decision || out.result.gate_id || out.result.status === 'pending'))))
      return 'Antrag liegt im Posteingang.';
    return 'Erledigt.';
  }

  const tool = {
    id: 'org',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      this.liste = null; this.fehler = null; this.hinweis = null; this.form = null; this.beendete = false;
      el.classList.add('t-org');
      let running = null, again = false;                       // ein Lesen läuft, ein weiteres wird gemerkt (D4.6)
      this.schub = ()=>{
        if(running){ again = true; return running; }
        running = this.refresh().finally(()=>{ running = null; if(again){ again = false; this.schub(); } });
        return running;
      };
      ['agent.changed', 'budget.warning', 'decision.pending', 'decision.answered', 'desk.resync'].forEach(n=>ctx.bus.on(n, ()=>this.schub()));
      return this.schub();
    },

    unmount(){ this.el.classList.remove('t-org'); this.el.replaceChildren(); this.liste = null; },

    async refresh(){
      if(!this.el) return;
      try{ this.liste = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'agent'}}); this.fehler = null; }
      catch(err){ this.fehler = err.message || String(err); }
      this.draw();
    },

    open(object){ this.ctx.shell.open(object); },

    draw(){
      const box = d().el('div', 's-col');
      const zustand = quelleZustand(this.liste, this.fehler);
      if(this.hinweis) box.append(d().el('div', 's-note' + (this.hinweis.bad ? ' bad' : ''), this.hinweis.text));
      if(zustand === 'aus' || zustand === 'fehler'){
        box.append(d().el('div', 's-note' + (zustand === 'fehler' ? ' bad' : ''), zustand === 'fehler'
          ? 'Die Orchestrierung ist ausgefallen: ' + ((this.liste.quelle || {}).grund || 'ohne Grund') + '.'
          : 'Die Orchestrierung ist ausgeschaltet (Schalter „orchestra“). Sobald sie läuft, steht das Team hier.'));
        box.append(d().button('Maschinenraum öffnen', ()=>this.open(MASCHINENRAUM)));
        return this.el.replaceChildren(box);
      }
      if(zustand === 'belegt' || zustand === 'lesefehler'){
        box.append(d().el('div', 's-note bad', zustand === 'belegt' ? 'Die Datenbank ist gerade belegt.' : 'Das Team ist nicht lesbar: ' + this.fehler));
        box.append(d().button('Noch einmal lesen', ()=>this.schub()));
        return this.el.replaceChildren(box);
      }
      const alle = this.liste.items || [];
      const items = sichtbar(alle, this.beendete);
      if(this.form) box.append(this.drawForm(alle));
      if(!alle.length){
        box.append(d().empty('Noch keine Agenten. „Einstellen“ legt den Unterarbeiter an.'));
        return this.el.replaceChildren(box);
      }
      const kompakt = !!(this.ctx.object && this.ctx.object.kompakt);
      if(!kompakt) box.append(this.toolbar(alle));
      const view = (this.ctx.object && this.ctx.object.view) === 'liste' && !kompakt ? 'liste' : 'baum';
      box.append(kompakt ? this.drawKompakt(items) : view === 'liste' ? this.drawListe(items, alle) : this.drawBaum(items));
      this.el.replaceChildren(box);
    },

    toolbar(alle){
      const bar = d().el('div', 's-row t-org-bar');
      const view = (this.ctx.object && this.ctx.object.view) === 'liste' ? 'liste' : 'baum';
      [['baum', 'Baum'], ['liste', 'Liste']].forEach(([v, label])=>{
        const b = d().button(label, ()=>this.open({type: 'agent', id: 'alle', title: 'Organigramm', collection: true, view: v}), v === view ? 'p' : '');
        b.setAttribute('aria-pressed', String(v === view));
        bar.append(b);
      });
      const n = alle.filter(a=>(a.status || a.state) === 'beendet').length;
      if(n) bar.append(d().button(this.beendete ? 'Beendete ausblenden' : 'Beendete zeigen (' + n + ')', ()=>{ this.beendete = !this.beendete; this.draw(); }));
      return bar;
    },

    balken(a){
      const b = B().budgetBalken(a.budget);
      if(!b) return d().el('small', 's-muted', a.budget === undefined ? 'Budget: noch keine Daten' : 'Budget: ohne Grenze');
      const wrap = d().el('div', 't-org-budget ' + b.stufe);
      const bar = d().el('div', 't-org-bar-track');
      const fill = d().el('div', 't-org-bar-fill');
      fill.style.width = b.breite + '%';
      bar.append(fill);
      wrap.append(bar, d().el('small', null, b.text + (b.stufe === 'ok' ? '' : ' · ' + b.stufe)));
      return wrap;
    },

    karte(a){
      const card = d().el('div', 't-org-card');
      card.dataset.agent = String(a.id);
      const head = d().el('div', 't-org-card-head');
      const dot = d().el('i', 't-org-dot ' + statusWort(a));
      dot.setAttribute('aria-hidden', 'true');
      head.append(dot, d().el('b', null, a.title || a.id));
      const offen = Number(a.offene_entscheidungen) || 0;
      if(offen){ const badge = d().el('span', 't-org-badge', String(offen)); badge.title = offen + ' offene Entscheidung(en)'; head.append(badge); }
      card.append(head, d().el('small', 's-muted', (a.rolle || '') + (a.rolle ? ' · ' : '') + statusWort(a)), this.balken(a));
      d().clickable(card, ()=>this.open({type: 'agent', id: a.id, title: a.title || a.id}));
      const verbs = a.actions || [];
      if(verbs.length){
        const menu = d().el('div', 't-org-verbs');
        menu.hidden = true;
        verbs.forEach(v=>menu.append(d().button(v.label || v.verb, ()=>this.verb(a, v))));
        const more = d().button('⋯', ()=>{ menu.hidden = !menu.hidden; }, 't-org-more');
        more.title = 'Verben'; more.setAttribute('aria-label', 'Verben von ' + (a.title || a.id));
        head.append(more);
        card.append(menu);
      }
      return card;
    },

    drawBaum(items){
      const L = B().layoutTree(items, {kartenbreite: 200, kartenhoehe: 96, abstand: 24});
      const byId = new Map(items.map(a=>[String(a.id), a]));
      const area = d().el('div', 't-org-tree');
      const canvas = d().el('div', 't-org-canvas');
      canvas.style.width = L.breite + 'px'; canvas.style.height = L.hoehe + 'px';
      const pos = new Map(L.knoten.map(k=>[k.id, k]));
      L.linien.forEach(l=>{
        const a = pos.get(l.von), b = pos.get(l.nach), mid = b.y - 12;
        const seg = (x, y, w, h)=>{ const s = d().el('i', 't-org-line'); Object.assign(s.style, {left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px'}); canvas.append(s); };
        const ax = a.x + 100, bx = b.x + 100;
        seg(ax, a.y + 96, 1, mid - a.y - 96);
        seg(Math.min(ax, bx), mid, Math.abs(bx - ax) + 1, 1);
        seg(bx, mid, 1, 12);
      });
      L.knoten.forEach(k=>{
        const card = k.id === B().CAPTAIN ? this.captain() : this.karte(byId.get(k.id));
        card.style.left = k.x + 'px'; card.style.top = k.y + 'px';
        canvas.append(card);
      });
      area.append(canvas);
      const box = d().el('div', 's-col');
      box.append(area);
      if(L.ohneVorgesetzten.length){
        const rest = d().el('div', 't-org-rest');
        rest.append(d().el('div', 's-head', 'Nicht eingeordnet'));
        L.ohneVorgesetzten.forEach(id=>rest.append(this.karte(byId.get(id))));
        box.append(rest);
      }
      return box;
    },

    captain(){
      const card = d().el('div', 't-org-card captain');
      card.append(d().el('b', null, 'Captain'), d().el('small', 's-muted', 'entscheidet die Gates'));
      return card;
    },

    drawKompakt(items){
      const L = B().layoutTree(items);
      const byId = new Map(items.map(a=>[String(a.id), a]));
      const list = d().el('div', 't-org-kompakt');
      L.knoten.filter(k=>k.id !== B().CAPTAIN).concat(L.ohneVorgesetzten.map(id=>({id, ebene: 1}))).forEach(k=>{
        const a = byId.get(k.id), b = B().budgetBalken(a.budget);
        const row = d().el('div', 's-row t-org-line-row');
        row.style.paddingLeft = ((k.ebene - 1) * 16) + 'px';
        row.append(d().el('i', 't-org-dot ' + statusWort(a)), d().el('span', null, a.title || a.id),
                   d().el('small', 's-muted', (a.rolle || '') + (b ? ' · ' + b.breite + ' %' : '')));
        if(Number(a.offene_entscheidungen)) row.append(d().el('span', 't-org-badge', String(a.offene_entscheidungen)));
        d().clickable(row, ()=>this.open({type: 'agent', id: a.id, title: a.title || a.id}));
        list.append(row);
      });
      return list;
    },

    drawListe(items, alle){
      const names = new Map(alle.map(a=>[String(a.id), a.title || a.id]));
      const t = d().el('table', 's-table t-org-table');
      const head = d().el('tr');
      ['Name', 'Rolle', 'Vorgesetzter', 'Status', 'Budget', 'Entscheidungen'].forEach(h=>head.append(d().el('th', null, h)));
      t.append(head);
      items.slice().sort((x, y)=>String(x.title || x.id).localeCompare(String(y.title || y.id), 'de')).forEach(a=>{
        const tr = d().el('tr');
        const b = B().budgetBalken(a.budget);
        const boss = a.reports_to ? names.get(String(a.reports_to)) || String(a.reports_to) + ' (unbekannt)' : 'Captain';
        tr.append(d().el('td', null, a.title || a.id), d().el('td', null, a.rolle || '–'), d().el('td', null, boss),
                  d().el('td', null, statusWort(a)), d().el('td', null, b ? b.breite + ' %' : '–'), d().el('td', null, String(Number(a.offene_entscheidungen) || 0)));
        d().clickable(tr, ()=>this.open({type: 'agent', id: a.id, title: a.title || a.id}));
        t.append(tr);
      });
      return t;
    },

    drawForm(alle){
      const {verb, agent} = this.form;
      const box = d().el('form', 's-card s-col t-org-form');
      box.append(d().el('b', null, (verb.label || verb.verb) + (agent ? ' – ' + (agent.title || agent.id) : '')));
      const fields = {};
      FORMS[verb.verb].forEach(([key, label, art])=>{
        const row = d().el('label', 's-col s-small');
        row.append(d().el('span', 's-muted', label));
        let input;
        if(art === 'agent'){
          input = d().el('select');
          const none = d().el('option', null, 'Captain (kein Vorgesetzter)'); none.value = ''; input.append(none);
          alle.filter(a=>!agent || a.id !== agent.id).forEach(a=>{ const o = d().el('option', null, a.title || a.id); o.value = String(a.id); input.append(o); });
        }else{ input = d().el('input'); input.type = art === 'number' ? 'number' : 'text'; }
        fields[key] = input;
        row.append(input);
        box.append(row);
      });
      const bar = d().el('div', 's-row');
      bar.append(d().button('Absenden', async()=>{
        const args = {};
        Object.keys(fields).forEach(k=>{ const v = fields[k].value; args[k] = fields[k].type === 'number' ? (v === '' ? null : Number(v)) : v; });
        await this.run(agent, verb, args);
      }, 'p'), d().button('Abbrechen', ()=>{ this.form = null; this.draw(); }));
      box.append(bar);
      box.onsubmit = e=>e.preventDefault();
      return box;
    },

    verb(agent, verb){
      if(FORMS[verb.verb]){ this.form = {verb, agent}; this.hinweis = null; this.draw(); return Promise.resolve(); }
      if(verb.confirm && !confirm(verb.confirm)) return Promise.resolve();
      return this.run(agent, verb, {});
    },

    async run(agent, verb, args){
      const body = agent ? {type: 'agent', id: agent.id, verb: verb.verb, args} : {type: 'agent', verb: verb.verb, args};
      try{
        const out = await this.ctx.api('/api/actions', {method: 'POST', body});
        this.form = null;
        this.hinweis = {text: (verb.label || verb.verb) + ': ' + ergebnisSatz(out)};
      }catch(err){ this.hinweis = {text: err.message || String(err), bad: true}; }   // das Formular bleibt stehen
      this.draw();
    },

    // Die Verben am Typ (Kopfzeile): nur, was die Liste des Servers anbietet (z. B. „einstellen“)
    actions(){
      const verbs = (this.liste && this.liste.actions) || [];
      return verbs.map(v=>({label: v.label || v.verb, run: ()=>this.verb(null, v)}));
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraOrgPure = {quelleZustand, sichtbar, ergebnisSatz, statusWort};
  if(typeof module !== 'undefined' && module.exports) module.exports = {quelleZustand, sichtbar, ergebnisSatz, statusWort, tool};
})();
