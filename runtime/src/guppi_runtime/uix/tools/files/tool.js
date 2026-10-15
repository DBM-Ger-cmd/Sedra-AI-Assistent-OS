// Werkzeug „Projekt“ – the files of the project; a file opens as its own tab (COCKPIT_MODUL_v1 rule 4: kein Sammelreiter).
// Read-only in Build 7: the server's project routes read, they never write. Writing a file is a decision (Build 8/9).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // folders first, then files, both by name (pure)
  function sortEntries(entries){
    return (entries || []).slice().sort((a, b)=>(a.kind === b.kind ? String(a.name || a.path).localeCompare(String(b.name || b.path)) : (a.kind === 'dir' ? -1 : 1)));
  }

  const tool = {
    id: 'files',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-files');
      this.path = '';
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-files'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      const projects = await this.ctx.api('/api/projects').catch(()=>[]);
      const box = d().el('div', 's-col');
      if(!projects.length){
        box.append(d().el('div', 's-note', 'Noch kein Projekt angelegt. Sag unten „neues Projekt“ – GUPPI legt den Ordner an und fragt einmal nach Modus und Grenzen.'));
        this.el.replaceChildren(box);
        return;
      }
      this.project = this.project || projects[0];
      if(projects.length > 1){
        const row = d().el('div', 's-row');
        projects.forEach(p=>{
          const b = d().el('button', 's-btn' + (p.project_id === this.project.project_id ? ' p' : ''), p.name || p.project_id);
          b.onclick = ()=>{ this.project = p; this.path = ''; this.refresh(); };
          row.append(b);
        });
        box.append(row);
      }
      let listing;
      try{ listing = await this.ctx.api('/api/project/files', {method: 'POST', body: {project_id: this.project.project_id, path: this.path}}); }
      catch(err){ box.append(d().el('div', 's-note bad', 'Dateien nicht lesbar: ' + err.message)); this.el.replaceChildren(box); return; }
      box.append(d().el('h5', 's-head', (this.project.name || 'Projekt') + (this.path ? ' · ' + this.path : '')));
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

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraFilesPure = {sortEntries};
  if(typeof module !== 'undefined' && module.exports) module.exports = {sortEntries};
})();
