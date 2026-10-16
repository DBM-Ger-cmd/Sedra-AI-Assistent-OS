// Werkzeug „Projekt“ – the files of the project; a file opens as its own tab (COCKPIT_MODUL_v1 rule 4: kein Sammelreiter).
// Read-only in Build 7: the server's project routes read, they never write. Writing a file is a decision (Build 8/9).
//
// Build 24 (Ticket B6-G-06, „keine Dummys“): „Neues Projekt“ ist ein Formular, kein Hinweis mehr – der Name geht an
// POST /api/project/create (der Ordner entsteht unter projects/, über das Dateisystem-Werkzeug der Runtime, mit Audit). Das Objekt
// {type: project, id: neu} öffnet das Formular; ein Projekt wählt man über die Reihe oben. `projectLabel` und `sortEntries` sind rein.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // folders first, then files, both by name (pure)
  function sortEntries(entries){
    return (entries || []).slice().sort((a, b)=>(a.kind === b.kind ? String(a.name || a.path).localeCompare(String(b.name || b.path)) : (a.kind === 'dir' ? -1 : 1)));
  }

  // what a project is called in the row of projects (pure): the registry says display_name, older records name
  function projectLabel(p){ return String((p && (p.display_name || p.name || p.project_id)) || 'Projekt'); }

  // a name the registry accepts (pure): 1–80 characters after trimming
  function nameOk(name){ const n = String(name || '').trim(); return n.length >= 1 && n.length <= 80; }

  const tool = {
    id: 'files',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-files');
      this.path = '';
      this.form = {open: !!(ctx.object && ctx.object.id === 'neu'), name: '', error: '', busy: false, created: null};
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-files'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      const projects = await this.ctx.api('/api/projects').catch(()=>[]);
      this.projects = projects;
      const box = d().el('div', 's-col');
      this.formBox = d().el('div', 's-col');
      box.append(this.formBox);
      this.renderForm();
      if(!projects.length){
        if(!this.form.open) box.append(d().el('div', 's-note', 'Noch kein Projekt angelegt. „Neues Projekt“ legt einen Ordner unter projects/ an; danach fragt SEDRA einmal nach Modus und Grenzen.'));
        this.el.replaceChildren(box);
        return;
      }
      if(!this.project || !projects.some(p=>p.project_id === this.project.project_id)) this.project = projects[0];
      if(projects.length > 1){
        const row = d().el('div', 's-row');
        projects.forEach(p=>{
          const b = d().el('button', 's-btn' + (p.project_id === this.project.project_id ? ' p' : ''), projectLabel(p));
          b.onclick = ()=>{ this.project = p; this.path = ''; this.refresh(); };
          row.append(b);
        });
        box.append(row);
      }
      let listing;
      try{ listing = await this.ctx.api('/api/project/files', {method: 'POST', body: {project_id: this.project.project_id, path: this.path}}); }
      catch(err){ box.append(d().el('div', 's-note bad', 'Dateien nicht lesbar: ' + err.message)); this.el.replaceChildren(box); return; }
      box.append(d().el('h5', 's-head', projectLabel(this.project) + (this.path ? ' · ' + this.path : '')));
      if(this.path){
        const up = d().el('div', 't-files-row');
        up.append(d().el('span', null, '⟵ eine Ebene höher'));
        d().clickable(up, ()=>{ this.path = this.path.split('/').slice(0, -1).join('/'); this.refresh(); });
        box.append(up);
      }
      const entries = sortEntries(listing.entries || listing.files || []);
      entries.forEach(e=>{
        const row = d().el('div', 't-files-row');
        row.append(d().el('span', null, (e.kind === 'dir' ? '📁 ' : '📄 ') + (e.name || e.path)));
        if(e.size !== undefined) row.append(d().el('small', 's-muted', d().fmtBytes(e.size)));
        d().clickable(row, ()=>{
          if(e.kind === 'dir'){ this.path = (this.path ? this.path + '/' : '') + (e.name || e.path); return this.refresh(); }
          this.show((this.path ? this.path + '/' : '') + (e.name || e.path));
        });
        box.append(row);
      });
      if(!entries.length) box.append(d().empty('Dieser Ordner ist leer.'));
      this.body = d().el('div');
      box.append(this.body);
      this.el.replaceChildren(box);
    },

    // ---- Neues Projekt
    renderForm(){
      const f = this.form, box = this.formBox;
      box.replaceChildren();
      if(f.created){
        const note = d().el('div', 's-note ok');
        note.append(d().el('span', null, 'Projekt „' + projectLabel(f.created) + '“ ist angelegt (' + (f.created.workspace_path || '') + '). Als Nächstes Modus und Grenzen bestätigen – ohne sie bleibt jede Aufgabe stehen. '));
        note.append(d().button('Modus und Grenzen', ()=>this.ctx.shell.open({type: 'boundary', id: 'projekt', title: 'Modus und Grenzen'}), 'p'));
        box.append(note);
      }
      if(!f.open){
        // der Knopf steht hier nur, wenn es noch kein Projekt gibt; sonst ist er das Verb des Werkstücks (Werkbank-Zeile, Regel 3)
        if(!(this.projects || []).length){
          const row = d().el('div', 's-row');
          row.append(d().button('Neues Projekt', ()=>{ f.open = true; f.created = null; this.renderForm(); const i = box.querySelector('input'); if(i) i.focus(); }, 'p'));
          box.append(row);
        }
        return;
      }
      const card = d().el('div', 't-files-new');
      card.append(d().el('b', null, 'Neues Projekt'));
      card.append(d().el('small', 's-muted', 'Ein Name, ein Ordner unter projects/. Kein Pfad von außerhalb – SEDRA arbeitet nur in seinen eigenen Projektordnern.'));
      if(f.error) card.append(d().el('div', 's-note bad', f.error));
      const row = d().el('div', 's-row t-files-form');
      const input = d().el('input', 't-files-input'); input.placeholder = 'Name des Projekts (1–80 Zeichen)'; input.value = f.name; input.maxLength = 80;
      input.setAttribute('aria-label', 'Name des Projekts');
      input.oninput = ()=>{ f.name = input.value; };
      input.onkeydown = e=>{ if(e.key === 'Enter'){ e.preventDefault(); this.create(); } else if(e.key === 'Escape'){ f.open = false; this.renderForm(); } };
      const go = d().button('Anlegen', ()=>this.create(), 'p'); go.disabled = f.busy;
      const cancel = d().button('Abbrechen', ()=>{ f.open = false; f.error = ''; this.renderForm(); });
      row.append(input, go, cancel);
      card.append(row);
      box.append(card);
    },

    async create(){
      const f = this.form;
      if(!nameOk(f.name)){ f.error = 'Bitte einen Namen mit 1 bis 80 Zeichen eingeben.'; this.renderForm(); return; }
      f.busy = true; f.error = ''; this.renderForm();
      try{
        const rec = await this.ctx.api('/api/project/create', {method: 'POST', body: {name: f.name.trim()}});
        f.created = rec; f.open = false; f.name = ''; f.busy = false;
        this.project = rec; this.path = '';
        await this.refresh();
      }catch(err){
        const m = String(err.message || err);
        f.error = m.includes('project_limit') ? 'Es gibt schon 64 Projekte – mehr verwaltet die Runtime nicht.'
                : m.includes('project_creation_blocked') ? 'Der Ordner konnte nicht angelegt werden (Dateisystem-Werkzeug hat es abgelehnt; siehe Logbuch).'
                : m.includes('project_name_required') ? 'Bitte einen Namen mit 1 bis 80 Zeichen eingeben.' : 'Anlegen fehlgeschlagen: ' + m;
        f.busy = false; this.renderForm();
      }
    },

    async show(path){
      this.body.replaceChildren(d().el('div', 's-note', 'Lese ' + path + ' …'));
      try{
        const file = await this.ctx.api('/api/project/file', {method: 'POST', body: {project_id: this.project.project_id, path}});
        const box = d().el('div', 's-col');
        box.append(d().el('h5', 's-head', path));
        box.append(d().el('pre', 's-pre', String(file.content || file.text || '').slice(0, 20000)));
        this.body.replaceChildren(box);
      }catch(err){ this.body.replaceChildren(d().el('div', 's-note bad', 'Datei nicht lesbar: ' + err.message)); }
    },

    actions(){
      return [{label: 'Neues Projekt', run: ()=>{ this.form.open = true; this.form.created = null; this.renderForm(); const i = this.formBox.querySelector('input'); if(i) i.focus(); }}];
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraFilesPure = {sortEntries, projectLabel, nameOk};
  if(typeof module !== 'undefined' && module.exports) module.exports = {sortEntries, projectLabel, nameOk};
})();
