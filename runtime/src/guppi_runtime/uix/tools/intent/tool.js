// Werkzeug „Vorhaben“ – der Satz, um den es geht, und die Aufgaben, die daraus geworden sind (COCKPIT_MODUL_v1 Regel 8).
// Ein Vorhaben führt nichts aus; es kostet nichts, es anzulegen. Erst „Aufgabe daraus machen“ beginnt den gewohnten Weg.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'intent',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-intent');
      this.all = !ctx.object || ctx.object.id === 'alle' || ctx.object.collection;
      this.id = ctx.object && ctx.object.id;
      ctx.bus.on('task.changed', ()=>this.refresh());
      ctx.bus.on('tools.refresh', ()=>this.refresh());
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-intent'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      try{
        if(this.all){
          const view = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'intent'}});
          this.el.replaceChildren(this.list(view.items || []));
          return;
        }
        const obj = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'intent', id: this.id}});
        this.verbs = obj.actions || [];
        this.el.replaceChildren(this.one(obj));
      }catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Vorhaben nicht lesbar: ' + err.message)); }
    },

    list(items){
      const box = d().el('div', 's-col');
      box.append(d().el('h5', 's-head', 'Vorhaben · ' + items.length));
      if(!items.length) box.append(d().empty('Noch kein Vorhaben. Über „＋ Neu“ eines anlegen – oder unten beschreiben, worum es geht.'));
      items.forEach(o=>{
        const row = d().el('div', 't-intent-row' + (o.state === 'wartet auf dich' ? ' warn' : ''));
        row.append(d().el('b', null, o.title), d().el('small', 's-muted', o.summary));
        d().clickable(row, ()=>this.ctx.shell.open({type: 'intent', id: o.id, title: o.title}));
        box.append(row);
      });
      box.append(this.form());
      return box;
    },

    one(o){
      const box = d().el('div', 's-col');
      if(!o || o.state === 'nicht gefunden'){
        box.append(d().el('div', 's-note', 'Dieses Vorhaben gibt es nicht mehr.'));
        return box;
      }
      box.append(d().el('div', 't-intent-title', o.title));
      box.append(d().el('div', 's-note', o.summary));
      if(o.text) box.append(d().el('div', 't-intent-text', o.text));
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

    // Ein neues Vorhaben: ein Titel und ein Satz. Kein Gate – es passiert nichts, bis daraus eine Aufgabe wird.
    form(){
      const box = d().el('div', 's-col t-intent-form');
      box.append(d().el('h5', 's-head', 'Neues Vorhaben'));
      const title = d().el('input');
      title.placeholder = 'Worum geht es? – ein Satz';
      title.setAttribute('aria-label', 'Titel des Vorhabens');
      const text = d().el('textarea');
      text.placeholder = 'Mehr dazu (freiwillig): was dabei herauskommen soll, was nicht passieren darf …';
      text.setAttribute('aria-label', 'Beschreibung');
      const add = d().button('Vorhaben anlegen', async()=>{
        if(!title.value.trim()) return;
        const made = await this.ctx.api('/api/intent/create', {method: 'POST', body: {title: title.value.trim(), text: text.value.trim()}});
        title.value = ''; text.value = '';
        await this.refresh();
        this.ctx.shell.open({type: 'intent', id: made.id, title: made.title});
      }, 'p');
      box.append(title, text, add);
      return box;
    },

    actions(){
      if(this.all || !this.verbs) return [];
      return this.verbs.map(a=>({label: a.label, run: async()=>{
        if(a.confirm && !confirm(a.confirm)) return;
        const out = await this.ctx.api('/api/actions', {method: 'POST', body: {type: 'intent', id: this.id, verb: a.verb}});
        await this.refresh();
        const made = out.result && out.result.mission_id;
        if(made) this.ctx.shell.open({type: 'task', id: made, title: 'Aufgabe'});
      }}));
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
