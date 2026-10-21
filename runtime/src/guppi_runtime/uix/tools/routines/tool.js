// Werkzeug „Routinen“ (Spec 4, D4.2.3): wiederkehrende Aufgaben – Zeitplan in Worten, Nachhol-Regel, letzte und nächste Ausführung.
// Der Satz zum Zeitplan kommt aus cron.js (nur Anzeige); Termine und das Urteil über einen Ausdruck liefert der Server (`next_run`,
// `cron_invalid`). Gelesen wird über POST /api/objects, gehandelt nur mit Verben aus `actions` – `set_routine` ist ein Antrag im
// Posteingang. Kein Zeitgeber: neu gelesen wird bei Ereignissen; über der Tabelle steht, ob der Takt der Orchestrierung läuft.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const C = ()=>root.sedraRoutinesCron;
  const MASCHINENRAUM = {type: 'machine', id: 'machine', title: 'Maschinenraum'};
  const AUSGANG = {erzeugt: 'Aufgabe erzeugt', ausgelassen: 'ausgelassen', nachgeholt: 'nachgeholt'};
  const NACHHOLEN = {auslassen: 'verpasste auslassen', nachholen: 'verpasste nachholen'};
  const FORM_VERBS = ['anlegen', 'aendern'];

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

  // Die Zeile über der Tabelle (rein): läuft der Takt, aus, oder weiß es der Server nicht (Spec 1, ORC-16)
  function taktSatz(quelle){
    const t = (quelle || {}).takt;
    if(!t || !t.zustand) return {text: 'Takt unbekannt – ob Routinen gerade ausgelöst werden, sagt der Server noch nicht.', tone: ''};
    if(t.zustand === 'aus') return {text: 'Takt aus – Routinen laufen nur, solange die Oberfläche läuft.', tone: 'warn'};
    return {text: 'Takt läuft' + (t.letzter ? ' · letzter Takt ' + d().fmtTime(t.letzter) : '') + '.', tone: 'ok'};
  }

  // Der Zeitplan in Worten (rein): der Satz aus cron.js, sonst der Ausdruck selbst
  function zeitplan(r){
    const cron = r.cron || '', tz = r.zeitzone || r.timezone || '';
    return C().cronText(cron, tz) || (cron ? cron + (tz ? ' (' + tz + ')' : '') : '–');
  }

  const einzeln = o=>!!(o && o.id && o.id !== 'alle' && !o.collection);
  const agentOf = r=>r.agent_id || ((r.links || []).find(l=>l && l.type === 'agent') || {}).id || null;
  const an = r=>r.enabled === undefined ? r.state === 'an' : !!r.enabled;

  const tool = {
    id: 'routines',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      this.liste = null; this.routine = null; this.agenten = new Map(); this.fehler = null; this.hinweis = null; this.form = null;
      el.classList.add('t-routines');
      let running = null, again = false;
      this.schub = ()=>{
        if(running){ again = true; return running; }
        running = this.refresh().finally(()=>{ running = null; if(again){ again = false; this.schub(); } });
        return running;
      };
      ['agent.changed', 'issue.changed', 'decision.answered', 'desk.resync'].forEach(n=>ctx.bus.on(n, ()=>this.schub()));
      return this.schub();
    },

    unmount(){ this.el.classList.remove('t-routines'); this.el.replaceChildren(); this.liste = null; this.routine = null; },

    async refresh(){
      if(!this.el) return;
      const o = this.ctx.object || {};
      const post = body=>this.ctx.api('/api/objects', {method: 'POST', body});
      const agents = post({type: 'agent'}).catch(()=>null);
      try{
        const [liste, one] = await Promise.all([post({type: 'routine'}), einzeln(o) ? post({type: 'routine', id: o.id}) : null]);
        this.liste = liste; this.routine = one; this.fehler = null;
      }catch(err){ this.fehler = err.message || String(err); }
      const a = await agents;
      this.agenten = new Map(((a || {}).items || []).map(x=>[String(x.id), x]));
      this.draw();
    },

    open(object){ this.ctx.shell.open(object); },
    agentName(id){ const a = id && this.agenten.get(String(id)); return a ? String(a.title || a.id) : (id ? String(id) : '–'); },

    // „Agent pausiert – es entstehen keine Aufgaben“ (rein genug: nur aus den gelesenen Agenten)
    agentHinweis(r){
      const a = this.agenten.get(String(agentOf(r)));
      const s = a && (a.status || a.state);
      return s === 'pausiert' || s === 'beendet' ? 'Agent ' + s + ' – es entstehen keine Aufgaben' : '';
    },

    draw(){
      const box = d().el('div', 's-col');
      const zustand = quelleZustand(this.liste, this.fehler);
      if(this.hinweis) box.append(d().el('div', 's-note' + (this.hinweis.bad ? ' bad' : ''), this.hinweis.text));
      if(zustand === 'aus' || zustand === 'fehler'){
        box.append(d().el('div', 's-note' + (zustand === 'fehler' ? ' bad' : ''), zustand === 'fehler'
          ? 'Die Orchestrierung ist ausgefallen: ' + ((this.liste.quelle || {}).grund || 'ohne Grund') + '.'
          : 'Die Orchestrierung ist ausgeschaltet (Schalter „orchestra“). Sobald sie läuft, stehen die Routinen hier.'));
        box.append(d().button('Maschinenraum öffnen', ()=>this.open(MASCHINENRAUM)));
        return this.el.replaceChildren(box);
      }
      if(zustand === 'belegt' || zustand === 'lesefehler'){
        box.append(d().el('div', 's-note bad', zustand === 'belegt' ? 'Die Datenbank ist gerade belegt.' : 'Die Routinen sind nicht lesbar: ' + this.fehler));
        box.append(d().button('Noch einmal lesen', ()=>this.schub()));
        return this.el.replaceChildren(box);
      }
      const takt = taktSatz(this.liste.quelle);
      box.append(d().el('div', 's-note t-routines-takt' + (takt.tone ? ' ' + takt.tone : ''), takt.text));
      if(this.form) box.append(this.drawForm(this.form));
      if(einzeln(this.ctx.object)) box.append(this.drawEine(this.routine));
      else if(!(this.liste.items || []).length) box.append(d().empty('Keine Routinen. Eine Routine legt zu festen Zeiten eine Aufgabe für einen Agenten an; verpasste Läufe werden nach der gewählten Regel nachgeholt oder ausgelassen.'));
      else box.append(this.drawTabelle(this.liste.items));
      this.el.replaceChildren(box);
    },

    letzter(r){
      const l = r.letzter_lauf;
      if(!l) return 'noch nie';
      return d().fmtTime(l.termin) + ' · ' + (AUSGANG[l.ausgang] || l.ausgang || '');
    },

    drawTabelle(items){
      const t = d().el('table', 's-table t-routines-table');
      const head = d().el('tr');
      ['Routine', 'Agent', 'Zeitplan', 'Nachholen', 'An', 'Zuletzt', 'Nächste'].forEach(h=>head.append(d().el('th', null, h)));
      t.append(head);
      items.slice().sort((a, b)=>String(a.title).localeCompare(String(b.title), 'de')).forEach(r=>{
        const tr = d().el('tr');
        tr.dataset.routine = String(r.id);
        const name = d().el('td');
        name.append(d().el('b', null, r.title || r.id));
        const hint = this.agentHinweis(r);
        if(hint) name.append(d().el('div', 's-small t-routines-warn', hint));
        tr.append(name, d().el('td', null, this.agentName(agentOf(r))), d().el('td', null, zeitplan(r)),
                  d().el('td', null, NACHHOLEN[r.nachholen] || r.nachholen || '–'), d().el('td', 't-routines-an ' + (an(r) ? 'an' : 'aus'), an(r) ? 'an' : 'aus'),
                  d().el('td', null, this.letzter(r)), d().el('td', null, r.next_run ? d().fmtTime(r.next_run) : '–'));
        d().clickable(tr, ()=>this.open({type: 'routine', id: r.id, title: r.title || r.id}));
        t.append(tr);
      });
      return t;
    },

    drawEine(r){
      const box = d().el('div', 's-col t-routines-one');
      if(!r || r.missing || r.state === 'nicht gefunden'){
        box.append(d().empty('Diese Routine gibt es nicht (mehr).'));
        box.append(d().button('Zur Liste', ()=>this.open({type: 'routine', id: 'alle', title: 'Routinen', collection: true})));
        return box;
      }
      const head = d().el('div', 's-row');
      head.append(d().el('b', 't-routines-title', r.title || r.id), d().el('span', 't-routines-an ' + (an(r) ? 'an' : 'aus'), an(r) ? 'an' : 'aus'));
      box.append(head);
      const hint = this.agentHinweis(r);
      if(hint) box.append(d().el('div', 's-note warn', hint));
      const t = d().el('table', 's-table');
      [['Agent', this.agentName(agentOf(r))], ['Zeitplan', zeitplan(r)], ['Ausdruck', (r.cron || '–')], ['Nachholen', NACHHOLEN[r.nachholen] || r.nachholen || '–'],
       ['Zuletzt', this.letzter(r)], ['Nächste', r.next_run ? d().fmtTime(r.next_run) : '–']].forEach(([k, v])=>{
        const tr = d().el('tr'); tr.append(d().el('td', 's-muted', k), d().el('td', null, v)); t.append(tr);
      });
      box.append(t);
      const v = r.vorlage || {};
      if(v.titel || v.beschreibung){
        box.append(d().el('h5', 's-head', 'Aufgabenvorlage'));
        box.append(d().el('b', null, v.titel || ''), d().el('div', 's-muted', v.beschreibung || ''));
      }
      box.append(d().el('h5', 's-head', 'Letzte Läufe'));
      const runs = (r.laeufe || []).slice(-20).reverse();
      if(!runs.length) box.append(d().el('small', 's-muted', r.laeufe ? 'Noch keine Läufe.' : 'Die Läufe liefert der Desk noch nicht.'));
      runs.forEach(l=>{
        const row = d().el('div', 's-row s-small t-routines-run');
        row.append(d().el('span', null, d().fmtTime(l.termin)), d().el('span', 's-muted', AUSGANG[l.ausgang] || l.ausgang || ''));
        if(l.issue_id){ const link = d().el('span', 't-routines-link', l.issue_id); d().clickable(link, ()=>this.open({type: 'issue', id: l.issue_id, title: l.issue_id})); row.append(link); }
        box.append(row);
      });
      return box;
    },

    // Anlegen und Ändern: dasselbe Formular; unter dem Zeitplan steht sofort der Satz, maßgeblich bleibt der Server
    drawForm(form){
      const r = form.routine || {}, w = form.werte || {};
      const box = d().el('form', 's-card s-col t-routines-form');
      box.append(d().el('b', null, (form.verb.label || form.verb.verb) + (form.routine ? ' – ' + (r.title || r.id) : '')));
      const fields = {};
      const feld = (key, label, input, start)=>{
        const row = d().el('label', 's-col s-small');
        row.append(d().el('span', 's-muted', label), input);
        input.value = w[key] !== undefined ? w[key] : (start === undefined || start === null ? '' : String(start));
        fields[key] = input; box.append(row);
        return row;
      };
      const select = pairs=>{ const s = d().el('select'); pairs.forEach(([v, l])=>{ const o = d().el('option', null, l); o.value = v; s.append(o); }); return s; };
      feld('titel', 'Titel', d().el('input'), r.title);
      feld('agent_id', 'Agent', select([['', '–']].concat(Array.from(this.agenten.values()).map(a=>[String(a.id), String(a.title || a.id)]))), agentOf(r));
      const cronRow = feld('cron', 'Zeitplan (Cron, fünf Felder)', d().el('input'), r.cron);
      const satz = d().el('small', 't-routines-satz');
      const zeigen = ()=>{
        const text = C().cronText(fields.cron.value, fields.zeitzone ? fields.zeitzone.value : '');
        satz.textContent = text || (fields.cron.value.trim() ? 'Zeitplan wird so gespeichert: ' + fields.cron.value.trim() : '');
      };
      fields.cron.oninput = zeigen;
      cronRow.append(satz);
      feld('zeitzone', 'Zeitzone', d().el('input'), r.zeitzone || r.timezone || 'Europe/Berlin');
      fields.zeitzone.oninput = zeigen;
      feld('nachholen', 'Verpasste Läufe', select(Object.entries(NACHHOLEN)), r.nachholen || 'auslassen');
      const v = r.vorlage || {};
      feld('vorlage_titel', 'Aufgabe: Titel', d().el('input'), v.titel);
      feld('vorlage_beschreibung', 'Aufgabe: Beschreibung', d().el('textarea'), v.beschreibung);
      zeigen();
      const bar = d().el('div', 's-row');
      bar.append(d().button('Absenden', async()=>{
        const args = {};
        Object.keys(fields).forEach(k=>{ args[k] = fields[k].value; });
        form.werte = args;
        await this.run(form.routine, form.verb, args);
      }, 'p'), d().button('Abbrechen', ()=>{ this.form = null; this.draw(); }));
      box.append(bar);
      box.onsubmit = e=>e.preventDefault();
      return box;
    },

    verb(routine, verb){
      if(FORM_VERBS.indexOf(verb.verb) >= 0){ this.form = {verb, routine}; this.hinweis = null; this.draw(); return Promise.resolve(); }
      if(verb.confirm && !confirm(verb.confirm)) return Promise.resolve();
      return this.run(routine, verb, {});
    },

    async run(routine, verb, args){
      const body = routine ? {type: 'routine', id: routine.id, verb: verb.verb, args} : {type: 'routine', verb: verb.verb, args};
      try{
        const out = await this.ctx.api('/api/actions', {method: 'POST', body});
        this.form = null;
        this.hinweis = {text: (verb.label || verb.verb) + ': ' + ergebnisSatz(out)};
      }catch(err){ this.hinweis = {text: err.message || String(err), bad: true}; }     // z. B. cron_invalid: das Formular bleibt
      this.draw();
    },

    // Kopfzeile: an der Sammlung „anlegen“ (aus der Liste), an einer Routine ihre Verben (aendern, ausschalten, einschalten …)
    actions(){
      if(einzeln(this.ctx && this.ctx.object)){
        const r = this.routine;
        if(!r || r.missing) return [];
        return (r.actions || []).map(v=>({label: v.label || v.verb, run: ()=>this.verb(r, v)}));
      }
      return ((this.liste && this.liste.actions) || []).map(v=>({label: v.label || v.verb, run: ()=>this.verb(null, v)}));
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraRoutinesPure = {quelleZustand, ergebnisSatz, taktSatz, zeitplan};
  if(typeof module !== 'undefined' && module.exports) module.exports = {quelleZustand, ergebnisSatz, taktSatz, zeitplan, tool};
})();
