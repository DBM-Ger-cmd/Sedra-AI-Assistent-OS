// Werkzeug „Aufgabe“ – tasks as sentences, not cards (COCKPIT_MODUL_v1 rule 6: Satz, Fortschrittszeile, Ergebnis;
// keine Missions-IDs und Phasen im Cockpit – die stehen im Logbuch). Opens one task, or the list when the id is 'alle'.
// taskSentence() and progress() are pure; node tests them.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const PHASE = {NEW: 'angenommen', UNDERSTAND: 'verstanden', PLAN: 'geplant', READY: 'bereit', EXECUTE: 'läuft',
                 REVIEW: 'in Prüfung', COMPLETE: 'fertig', FAILED: 'fehlgeschlagen', PAUSED: 'angehalten'};

  // one sentence about this task, in the Captain's words
  function taskSentence(m){
    if(!m) return 'Diese Aufgabe gibt es nicht mehr.';
    const what = String(m.intent || m.objective || 'Aufgabe').replace(/\s+/g, ' ').trim();
    const state = PHASE[m.phase] || String(m.phase || '').toLowerCase();
    if((m.pending_gates || 0) > 0) return what + ' – wartet auf deine Freigabe.';
    if(m.phase === 'COMPLETE') return what + ' – fertig.';
    if(m.phase === 'FAILED') return what + ' – fehlgeschlagen; die Ursache steht im Logbuch.';
    const steps = (m.steps || []).length;
    if(steps) return what + ' – ' + state + ', Schritt ' + Math.min((m.steps_done || 0) + 1, steps) + ' von ' + steps + '.';
    return what + ' – ' + state + '.';
  }

  function progress(m){
    const steps = (m && m.steps || []).length;
    const done = Math.min(m && m.steps_done || 0, steps);
    return {steps, done, percent: steps ? Math.round(100 * done / steps) : 0};
  }

  const tool = {
    id: 'task',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-task');
      ctx.bus.on('task.changed', e=>{ if(this.all || !this.object || e.id === this.object.id) this.refresh(); });
      this.object = ctx.object;
      this.all = !ctx.object || ctx.object.id === 'alle';
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-task'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      try{
        if(this.all){
          const view = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'task'}});
          this.el.replaceChildren(this.list(view.items || []));
          return;
        }
        const obj = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'task', id: this.object.id}});
        this.object = Object.assign({}, this.object, {id: obj.id});
        this.verbs = obj.actions || [];
        this.el.replaceChildren(this.one(obj));
      }catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Aufgaben nicht lesbar: ' + err.message)); }
    },

    list(items){
      const box = d().el('div', 's-col');
      // Stufe 6 (S6-E3): Anträge liefert der Server nicht mehr als Aufgaben; offen ist, was nicht fertig oder fehlgeschlagen ist
      const istOffen = o=>o.state !== 'fertig' && o.state !== 'fehlgeschlagen';
      const open = items.filter(istOffen);
      const done = items.filter(o=>!istOffen(o)).slice(-5).reverse();
      box.append(d().el('h5', 's-head', 'Aufgaben · ' + open.length + ' offen'));
      if(!open.length) box.append(d().empty('Nichts offen. Schreib unten, was gebaut werden soll – SEDRA macht Aufgaben daraus.'));
      open.forEach(o=>box.append(this.row(o)));
      if(done.length){
        box.append(d().el('h5', 's-head', 'Zuletzt abgeschlossen'));
        done.forEach(o=>box.append(this.row(o)));
      }
      return box;
    },

    row(o){
      const line = d().el('div', 't-task-row' + (o.state === 'wartet auf dich' ? ' warn' : ''));
      line.append(d().el('div', 't-task-sentence', o.summary));
      if((o.progress || {}).steps) line.append(this.bar(o.progress));
      d().clickable(line, ()=>this.ctx.shell.open({type: 'task', id: o.id, title: o.title}));
      return line;
    },

    bar(p){
      const bar = d().el('div', 't-task-bar');
      const fill = d().el('span');
      fill.style.width = p.percent + '%';
      bar.append(fill);
      bar.setAttribute('role', 'progressbar');
      bar.setAttribute('aria-valuenow', String(p.percent));
      return bar;
    },

    one(o){
      const box = d().el('div', 's-col');
      if(!o || o.state === 'nicht gefunden'){
        box.append(d().el('div', 's-note', 'Diese Aufgabe steht nicht mehr in der Liste. Im Logbuch ist sie erhalten.'));
        return box;
      }
      box.append(d().el('div', 't-task-sentence big', o.summary));
      if((o.progress || {}).steps){
        box.append(this.bar(o.progress));
        const list = d().el('ol', 't-task-steps');
        (o.steps || []).forEach(step=>list.append(d().el('li', step.done ? 'done' : (step.now ? 'now' : ''), step.text)));
        box.append(list);
      }
      // Verweise statt Navigation im Werkzeug: der Kandidat und die wartende Entscheidung sind einen Klick entfernt (§10.1 links)
      const links = (o.links || []).filter(l=>l.rel !== 'verlauf');
      if(links.length){
        const row = d().el('div', 's-row');
        links.forEach(l=>row.append(d().button(l.title, ()=>this.ctx.shell.open({type: l.type, id: l.id, title: l.title}))));
        box.append(row);
      }
      return box;
    },

    // Die Verben dieses Objekts in seinem Zustand (Regel 3) – nie Navigation, nie eine Entscheidung. Welche gelten, sagt das Desk (§10.2).
    actions(){
      if(this.all || !this.verbs || !this.object) return [];
      return this.verbs.map(a=>({label: a.label, run: async()=>{
        if(a.confirm && !confirm(a.confirm)) return;
        await this.ctx.api('/api/actions', {method: 'POST', body: {type: 'task', id: this.object.id, verb: a.verb}});
        await this.refresh();
      }}));
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraTaskPure = {taskSentence, progress, PHASE};
  if(typeof module !== 'undefined' && module.exports) module.exports = {taskSentence, progress, PHASE};
})();
