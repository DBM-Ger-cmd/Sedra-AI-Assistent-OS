// Werkzeug „Modus und Grenzen“ – die vier Stellen, an denen der Mensch steht (COCKPIT_MODUL_v1 Regel 7, §3).
// Es zeigt, was gilt, oder – beim ersten Mal – was SEDRA vorschlägt und warum. Bestätigen und Ändern sind Freigaben; beides
// geht über die Entscheidung, nicht an ihr vorbei. `frei` gibt es für Netz und Löschen nicht: der Knopf fehlt, nicht nur die Wirkung.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const WAYS = ['frei', 'fragt', 'zu'];
  const NEVER_FREE = ['netz', 'loeschen'];
  const WORD = {projekt: 'Projekt', netz: 'Netz', loeschen: 'Löschen', kosten: 'Kosten'};
  const WHAT = {
    projekt: 'Dateien im Projekt ändern',
    netz: 'ins Netz gehen – nachladen, abrufen',
    loeschen: 'Dateien löschen',
    kosten: 'Token je Aufgabe'
  };

  // Welche Wege eine Grenze anbieten darf (rein – P0/P4: Netz und Löschen nie „frei“)
  function waysFor(kind){
    return NEVER_FREE.indexOf(kind) >= 0 ? WAYS.filter(w=>w !== 'frei') : WAYS;
  }

  const tool = {
    id: 'boundaries',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-bound');
      ctx.bus.on('decision.answered', ()=>this.refresh());
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-bound'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let view;
      try{ view = await this.ctx.api('/api/boundaries'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Grenzen nicht lesbar: ' + err.message)); return; }
      this.view = view;
      this.draft = {mode: view.mode, boundaries: Object.assign({}, view.boundaries)};
      const box = d().el('div', 's-col');
      if(!view.project_id){ box.append(d().el('div', 's-note', view.note || 'Kein Projekt.')); this.el.replaceChildren(box); return; }

      if(!view.confirmed){
        const note = d().el('div', 's-note warn');
        note.append(d().el('b', null, 'Noch nicht bestätigt.'));
        note.append(d().el('div', null, view.reason || ''));
        note.append(d().el('small', null, 'Bis du einmal zustimmst, läuft nichts, was eine Grenze berührt.'));
        box.append(note);
      }else{
        box.append(d().el('div', 's-note ok', 'Gilt seit ' + d().fmtTime(view.confirmed_at) + '.'));
      }

      box.append(d().el('h5', 's-head', 'Modus'));
      const modes = d().el('div', 's-row');
      [['sandbox', 'Sandbox'], ['beobachten', 'Beobachten'], ['vertraut', 'Vertraut']].forEach(([id, label])=>{
        const b = d().el('button', 's-btn' + (this.draft.mode === id ? ' p' : ''), label);
        b.onclick = ()=>{ this.draft.mode = id; this.render(box); };
        modes.append(b);
      });
      box.append(modes);

      box.append(d().el('h5', 's-head', 'Grenzen'));
      this.rows = d().el('div', 's-col');
      box.append(this.rows);
      this.renderRows();

      if(view.measured_limit) box.append(d().el('small', 's-muted', 'Gemessen: die teuerste Aufgabe bisher legt die vorläufige Kostengrenze auf ' + d().fmtNumber(view.measured_limit) + ' Token.'));
      else box.append(d().el('small', 's-muted', 'Die Kostengrenze wird gemessen, nicht geraten – zwei Wochen Guppy-Meter auf diesem Rechner.'));
      box.append(d().el('small', 's-muted', '„Frei“ gibt es für Netz und Löschen nicht. Lesen ist immer frei.'));
      this.box = box;
      this.el.replaceChildren(box);
    },

    render(){ this.refresh(); },

    renderRows(){
      const rows = this.rows;
      rows.replaceChildren();
      Object.keys(WORD).forEach(kind=>{
        const row = d().el('div', 't-bound-row');
        const head = d().el('div');
        head.append(d().el('b', null, WORD[kind]), d().el('small', 's-muted', ' · ' + WHAT[kind]));
        row.append(head);
        const choice = d().el('div', 's-row');
        waysFor(kind).forEach(way=>{
          const on = this.draft.boundaries[kind] === way;
          const b = d().el('button', 's-btn' + (on ? ' p' : ''), way);
          b.onclick = ()=>{ this.draft.boundaries[kind] = way; this.renderRows(); };
          choice.append(b);
        });
        if(kind === 'kosten'){
          const number = d().el('input');
          number.type = 'number'; number.min = '1'; number.placeholder = 'oder: ab … Token fragen';
          number.style.width = '180px';
          if(typeof this.draft.boundaries.kosten === 'number') number.value = String(this.draft.boundaries.kosten);
          number.oninput = ()=>{ const v = parseInt(number.value, 10); if(v > 0){ this.draft.boundaries.kosten = v; } };
          choice.append(number);
        }
        row.append(choice);
        rows.append(row);
      });
    },

    // Bestätigen und Ändern sind Freigaben – das Verb kommt vom Desk, der Weg führt über die Entscheidung (Regel 2).
    actions(){
      const view = this.view;
      if(!view || !view.project_id) return [];
      const label = view.confirmed ? 'Änderung vorlegen' : 'Bestätigen';
      return [{label, run: async()=>{
        if(!confirm('Das gilt dann für alles, was in diesem Projekt passiert:\n\n' + this.draft.mode + ' · '
                    + Object.keys(WORD).map(k=>WORD[k] + ': ' + this.draft.boundaries[k]).join(' · '))) return;
        await this.ctx.api('/api/boundaries/request', {method: 'POST', body: {mode: this.draft.mode, boundaries: this.draft.boundaries}});
        await this.refresh();
        this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true});
      }}];
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraBoundPure = {waysFor, WORD, WHAT};
  if(typeof module !== 'undefined' && module.exports) module.exports = {waysFor, WORD, WHAT};
})();
