// Werkzeug „Vorhaben“ – der Satz, um den es geht, und die Aufgaben, die daraus geworden sind (COCKPIT_MODUL_v1 Regel 8).
// Ein Vorhaben führt nichts aus; es kostet nichts, es anzulegen. Erst „Aufgabe daraus machen“ beginnt den gewohnten Weg.
// Seit 19.10.2026 hat ein Vorhaben Stufen (Werkflow): jede Stufe kann eine Aufgabe werden und hängt dann an ihr; der Zustand einer
// Stufe kommt aus ihren Aufgaben, die erste nicht fertige Stufe ist die aktuelle. Vorlagen (GET /api/intent/vorlagen) geben Stufen vor.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const TONE = {'offen': 'muted', 'in Arbeit': 'ok', 'wartet auf dich': 'warn', 'fertig': 'done'};
  const PHASE = {READY: 'bereit', PLAN: 'geplant', EXECUTE: 'läuft', VERIFY: 'wird geprüft', COMPLETE: 'fertig', FAILED: 'gescheitert'};

  const tool = {
    id: 'intent',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-intent');
      this.all = !ctx.object || ctx.object.id === 'alle' || ctx.object.collection;
      this.kompakt = !!(ctx.object && ctx.object.kompakt);     // auf einer Übersicht (Paperclip-Dashboard): nur die Liste, kein Formular
      this.id = ctx.object && ctx.object.id;
      this.vorlagen = null;
      ctx.bus.on('task.changed', ()=>this.refresh());
      ctx.bus.on('tools.refresh', ()=>this.refresh());
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-intent'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      // Das Werkzeug ist ein Objekt für alle Container: wer nach dem Warten in einen anderen Container zeichnen würde, hört auf.
      // (Gefunden 19.10.: die Sammlung antwortete nach dem Öffnen eines Vorhabens und übermalte dessen Seite.)
      const el = this.el, all = this.all, id = this.id;
      try{
        if(all){
          const view = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'intent'}});
          if(!this.vorlagen) this.vorlagen = ((await this.ctx.api('/api/intent/vorlagen').catch(()=>({}))).vorlagen) || [];
          if(this.el !== el || !this.all) return;
          el.replaceChildren(this.list(view.items || []));
          return;
        }
        const obj = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'intent', id}});
        if(this.el !== el || this.id !== id) return;
        this.obj = obj; this.verbs = obj.actions || [];
        el.replaceChildren(this.one(obj));
      }catch(err){ if(this.el === el) el.replaceChildren(d().el('div', 's-note bad', 'Vorhaben nicht lesbar: ' + err.message)); }
    },

    /* ---------------- die Sammlung ---------------- */
    list(items){
      const box = d().el('div', 's-col');
      box.append(d().el('h5', 's-head', 'Vorhaben · ' + items.length));
      if(!items.length) box.append(d().empty(this.kompakt ? 'Noch kein Vorhaben. Unter „Ziele“ eines anlegen – mit einer Vorlage bekommt es gleich seine Stufen.'
                                                        : 'Noch kein Vorhaben. Unten eines anlegen – mit einer Vorlage bekommt es gleich seine Stufen.'));
      items.forEach(o=>{
        const row = d().el('div', 't-intent-row' + (o.state === 'wartet auf dich' ? ' warn' : ''));
        const head = d().el('div', 't-intent-row-head');
        head.append(d().el('b', null, o.title), this.pill(o.state));
        row.append(head, d().el('small', 's-muted', o.summary));
        if((o.stufen || []).length) row.append(this.progress(o.stufen));
        d().clickable(row, ()=>this.ctx.shell.open({type: 'intent', id: o.id, title: o.title}));
        box.append(row);
      });
      if(!this.kompakt) box.append(this.form());
      return box;
    },

    // Der Fortschritt eines Vorhabens: ein Segment je Stufe, gefärbt nach Zustand – zu lesen auf einen Blick
    progress(stufen){
      const bar = d().el('div', 't-intent-progress');
      bar.setAttribute('aria-label', stufen.filter(s=>s.state === 'fertig').length + ' von ' + stufen.length + ' Stufen fertig');
      stufen.forEach(s=>{ const seg = d().el('span', 't-intent-seg ' + (TONE[s.state] || 'muted')); seg.title = s.name + ' – ' + s.state; bar.append(seg); });
      return bar;
    },

    pill(state){ return d().el('span', 't-intent-pill ' + (TONE[state] || 'muted'), state); },

    /* ---------------- ein Vorhaben ---------------- */
    one(o){
      const box = d().el('div', 's-col');
      if(!o || o.state === 'nicht gefunden'){
        box.append(d().el('div', 's-note', 'Dieses Vorhaben gibt es nicht mehr.'));
        return box;
      }
      const head = d().el('div', 't-intent-row-head');
      head.append(d().el('div', 't-intent-title', o.title), this.pill(o.state));
      box.append(head);
      box.append(d().el('div', 's-note', o.summary));
      if(o.text) box.append(d().el('div', 't-intent-text', o.text));
      const stufen = o.stufen || [];
      if(stufen.length){
        box.append(d().el('h5', 's-head', 'Stufen · ' + stufen.filter(s=>s.state === 'fertig').length + ' von ' + stufen.length + ' fertig'));
        box.append(this.progress(stufen));
        box.append(this.pipeline(stufen));
        return box;
      }
      box.append(d().el('h5', 's-head', 'Aufgaben daraus · ' + (o.tasks || []).length));
      if(!(o.tasks || []).length) box.append(d().empty('Noch keine. „Aufgabe daraus machen“ legt die erste an – geplant, nicht ausgeführt.'));
      (o.links || []).forEach(l=>{
        const row = d().el('div', 't-intent-row');
        row.append(d().el('span', null, l.title));
        d().clickable(row, ()=>this.ctx.shell.open({type: 'task', id: l.id, title: l.title}));
        box.append(row);
      });
      return box;
    },

    // Die Stufen als Weg: Nummer, Name, Zustand, Satz, die Aufgaben daran – und an der aktuellen Stufe der Knopf
    pipeline(stufen){
      const list = d().el('ol', 't-intent-stufen');
      stufen.forEach(s=>{
        const li = d().el('li', 't-intent-stufe ' + (TONE[s.state] || 'muted') + (s.current ? ' current' : ''));
        li.dataset.stufe = String(s.index);
        const head = d().el('div', 't-intent-stufe-head');
        head.append(d().el('span', 't-intent-num', String(s.index + 1)), d().el('b', null, s.name), this.pill(s.state));
        li.append(head);
        if(s.text) li.append(d().el('p', 't-intent-stufe-text', s.text));
        (s.tasks || []).forEach(t=>{
          const row = d().el('div', 't-intent-task' + (t.waits ? ' warn' : ''));
          row.append(d().el('span', null, 'Aufgabe ' + t.id), d().el('small', 's-muted', t.waits ? 'wartet auf dich' : (PHASE[t.phase] || t.phase || '')));
          d().clickable(row, ()=>this.ctx.shell.open({type: 'task', id: t.id, title: t.title}));
          li.append(row);
        });
        if(s.state !== 'fertig' && this.verbOffered('aufgabe_machen')){
          const btn = d().button(s.tasks.length ? 'Noch eine Aufgabe für diese Stufe' : 'Aufgabe daraus machen', ()=>this.makeTask(s.index), s.current ? 'p' : '');
          btn.classList.add('t-intent-stufe-btn');
          li.append(btn);
        }
        list.append(li);
      });
      return list;
    },

    verbOffered(verb){ return (this.verbs || []).some(a=>a.verb === verb); },

    // Eine Stufe wird zur Aufgabe: derselbe Verb-Weg wie jeder Knopf (POST /api/actions), mit der Stufe als Argument
    async makeTask(stufe){
      const out = await this.ctx.api('/api/actions', {method: 'POST', body: {type: 'intent', id: this.id, verb: 'aufgabe_machen', args: {stufe}}});
      await this.refresh();
      const made = out.result && out.result.mission_id;
      if(made) this.ctx.shell.open({type: 'task', id: made, title: 'Aufgabe'});
    },

    /* ---------------- neu anlegen ---------------- */
    // Ein neues Vorhaben: ein Titel und ein Satz – und wahlweise eine Vorlage, die Titel, Satz und Stufen mitbringt.
    // Kein Gate: es passiert nichts, bis daraus eine Aufgabe wird. Der erste Knopf im Formular bleibt „Vorhaben anlegen“.
    form(){
      const box = d().el('div', 's-col t-intent-form');
      box.append(d().el('h5', 's-head', 'Neues Vorhaben'));
      const title = d().el('input');
      title.placeholder = 'Worum geht es? – ein Satz';
      title.setAttribute('aria-label', 'Titel des Vorhabens');
      const text = d().el('textarea');
      text.placeholder = 'Mehr dazu (freiwillig): was dabei herauskommen soll, was nicht passieren darf …';
      text.setAttribute('aria-label', 'Beschreibung');
      const pick = d().el('select', 't-intent-vorlage');
      pick.setAttribute('aria-label', 'Vorlage');
      const preview = d().el('div', 't-intent-preview');
      const vorlagen = this.vorlagen || [];
      const none = d().el('option', null, 'Ohne Vorlage – Stufen kommen später aus dem Gespräch'); none.value = 'leer'; pick.append(none);
      vorlagen.filter(v=>v.id !== 'leer').forEach(v=>{
        const opt = d().el('option', null, v.titel + ' · ' + v.stufen.length + ' Stufen'); opt.value = v.id; pick.append(opt);
      });
      pick.onchange = ()=>{
        const v = vorlagen.find(x=>x.id === pick.value);
        preview.replaceChildren();
        if(!v || v.id === 'leer') return;
        if(!title.value.trim()) title.value = v.titel;
        if(!text.value.trim()) text.value = v.satz;
        const ol = d().el('ol', 't-intent-preview-list');
        v.stufen.forEach(s=>ol.append(d().el('li', null, s.name)));
        preview.append(d().el('small', 's-muted', 'Die Stufen dieser Vorlage – jede kann später eine Aufgabe werden:'), ol);
      };
      const add = d().button('Vorhaben anlegen', async()=>{
        if(!title.value.trim() && pick.value === 'leer') return;
        const body = {title: title.value.trim(), text: text.value.trim()};
        if(pick.value !== 'leer') body.vorlage = pick.value;
        const made = await this.ctx.api('/api/intent/create', {method: 'POST', body});
        title.value = ''; text.value = ''; pick.value = 'leer'; preview.replaceChildren();
        await this.refresh();
        this.ctx.shell.open({type: 'intent', id: made.id, title: made.title});
      }, 'p');
      const row = d().el('div', 't-intent-form-row');
      row.append(add, d().el('label', 't-intent-vorlage-label', 'Vorlage: '), pick);
      box.append(title, text, row, preview);
      return box;
    },

    // Die Verben des Objekts für die Handlungszeile der Shell: bei Stufen gilt „Aufgabe daraus machen“ der aktuellen Stufe
    actions(){
      if(this.all || !this.verbs) return [];
      const stufen = (this.obj && this.obj.stufen) || [];
      const current = stufen.find(s=>s.current);
      return this.verbs.map(a=>({label: a.label + (current ? ' (Stufe ' + (current.index + 1) + ')' : ''), run: async()=>{
        if(a.confirm && !confirm(a.confirm)) return;
        if(a.verb === 'aufgabe_machen' && current) return this.makeTask(current.index);
        const out = await this.ctx.api('/api/actions', {method: 'POST', body: {type: 'intent', id: this.id, verb: a.verb}});
        await this.refresh();
        const made = out.result && out.result.mission_id;
        if(made) this.ctx.shell.open({type: 'task', id: made, title: 'Aufgabe'});
      }}));
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
