// Werkzeug „Bibliothek“ – the skills: SEDRA's own capabilities, the imported libraries, the Captain's own skills.
// Reading is free, writing is a decision: the tool only asks for it (POST …/custom/request) and the desk puts it where every
// decision is answered. Three shelves, as in Build 5, now inside one container instead of a window.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'library',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-lib');
      this.shelf = (ctx.object && ctx.object.id === 'eigene') ? 'eigene' : 'own';
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-lib'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let view;
      try{ view = await this.ctx.api('/api/library'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Bibliothek nicht lesbar: ' + err.message)); return; }
      this.view = view;
      const box = d().el('div', 's-col');
      const tabs = d().el('div', 's-row');
      [['own', 'Fähigkeiten · ' + (view.own || []).length], ['eigene', 'Eigene · ' + (view.custom || []).length], ['regale', 'Regale · ' + (view.libraries || []).length]]
        .forEach(([id, label])=>{
          const b = d().el('button', 's-btn' + (this.shelf === id ? ' p' : ''), label);
          b.onclick = ()=>{ this.shelf = id; this.refresh(); };
          tabs.append(b);
        });
      box.append(tabs);

      if(this.shelf === 'own'){
        (view.own || []).forEach(s=>{
          const row = d().el('div', 't-lib-row');
          row.append(d().el('b', null, s.name || s.id), d().el('small', 's-muted', s.description || ''));
          if((s.triggers || []).length) row.append(d().el('small', 's-muted', 'greift bei: ' + s.triggers.slice(0, 4).join(', ')));
          box.append(row);
        });
        if(!(view.own || []).length) box.append(d().empty('Noch keine Fähigkeiten registriert.'));
      }else if(this.shelf === 'eigene'){
        box.append(d().el('div', 's-note', 'Eigene Skills liegen unter local_config/skill_library. Geschrieben wird nur nach einer Freigabe; die alte Datei wird vorher gesichert.'));
        (view.custom || []).forEach(s=>{
          const row = d().el('div', 't-lib-row');
          row.append(d().el('b', null, s.id || s.name), d().el('small', 's-muted', s.description || ''));
          box.append(row);
        });
        if(!(view.custom || []).length) box.append(d().empty('Noch keiner. Im Gespräch sagen, was der Skill können soll – GUPPI schlägt ihn vor, du gibst ihn frei.'));
      }else{
        (view.libraries || []).forEach(l=>{
          const row = d().el('div', 't-lib-row' + (l.available ? '' : ' off'));
          row.append(d().el('b', null, l.name), d().el('small', 's-muted', (l.available ? l.count + ' Skills' : (l.hint || 'nicht gebaut')) + ' · Lizenz ' + l.license));
          if(l.note) row.append(d().el('small', 's-muted', l.note));
          box.append(row);
        });
      }
      this.el.replaceChildren(box);
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
