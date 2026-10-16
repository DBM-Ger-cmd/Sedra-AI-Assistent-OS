// Werkzeug „Live“ – was gerade passiert (COCKPIT_MODUL_v1 Regel 5, erster Nachweis).
// Es fragt einmal nach den Zeilen einer Aufgabe und bekommt alles Weitere über den Strom (`live.line`): der Server sagt, bis zu
// welcher Nummer er ist, das Werkzeug holt genau den Rest. Kein Polling, kein Nachladen von allem.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const SIGN = {step: '›', ok: '✓', bad: '✗', gate: '⟂', note: '·', out: ' '};

  const tool = {
    id: 'live',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-live');
      this.mission = ctx.object && ctx.object.id;
      this.since = 0;
      this.console = d().el('div', 's-live t-live-box');
      this.console.setAttribute('role', 'log');
      this.head = d().el('div', 's-small s-muted');
      const bar = d().el('div', 's-row');
      const again = d().button('Von vorn', async()=>{ this.since = 0; this.console.replaceChildren(); await this.pull(); });
      again.style.marginLeft = 'auto';
      bar.append(this.head, again);
      el.replaceChildren(bar, this.console);
      ctx.bus.on('live.line', e=>{ if(e.task_id === this.mission) this.pull(); });
      ctx.bus.on('task.changed', e=>{ if(e.id === this.mission) this.pull(); });
      return this.pull();
    },

    unmount(){ this.el.classList.remove('t-live'); this.el.replaceChildren(); },

    async pull(){
      if(!this.el) return;
      let view;
      try{ view = await this.ctx.api('/api/live', {method: 'POST', body: {task_id: this.mission, since: this.since}}); }
      catch(err){ this.head.textContent = 'Live nicht lesbar: ' + err.message; return; }
      if(view.note && !view.total){ this.console.replaceChildren(d().el('div', null, view.note)); return; }
      (view.lines || []).forEach(line=>this.append(line));
      this.since = Math.max(this.since, view.total || 0);
      this.head.textContent = view.total + ' Zeile' + (view.total === 1 ? '' : 'n') + ' · der Strom schickt neue von selbst';
    },

    append(line){
      const row = d().el('div', 't-live-line ' + (line.kind || 'note'));
      row.append(d().el('span', 't-live-sign', SIGN[line.kind] || '·'));
      row.append(d().el('span', 't-live-text', line.line));
      if(line.at) row.title = d().fmtTime(line.at);
      this.console.append(row);
      this.console.scrollTop = this.console.scrollHeight;
    },

    // Kein Verb an der Werkbank: „von vorn lesen“ betrifft diese Anzeige, nicht die Aufgabe – der Knopf sitzt im Kopf dieses Werkzeugs.
    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
