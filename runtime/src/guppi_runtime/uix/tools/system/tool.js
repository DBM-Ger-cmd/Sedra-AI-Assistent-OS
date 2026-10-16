// Werkzeug „System“ – Maschinenraum und Hardware in einem Werkzeug: Zustand der Teile, Entwicklungsumgebung, GPU und Speicher.
// Reading only. What could change something (Schalter, Bindung) is a decision and lives at the desk, not in a toolbar here.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'system',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      this.view = (ctx.object && ctx.object.type === 'hardware') ? 'hardware' : 'machine';
      el.classList.add('t-sys');
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-sys'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let st;
      try{ st = await this.ctx.api('/api/status'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Zustand nicht lesbar: ' + err.message)); return; }
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note ' + (st.system_state === 'READY' ? 'ok' : 'warn'),
        st.system_state === 'READY' ? 'Alle Teile gesund.' : 'Sicherer Modus: mindestens ein Teil meldet ein Problem.'));

      if(this.view === 'hardware'){
        const hw = st.hardware || {};
        const t = d().el('table', 's-table');
        [['Rechner', (hw.os || '') + ' · ' + (hw.architecture || '')], ['Prozessor', (hw.cpu || '') + ' · ' + (hw.cpu_threads || '?') + ' Fäden'],
         ['Arbeitsspeicher', (hw.ram_gb || '?') + ' GB'], ['Grafikkarte', hw.gpu_name || 'keine erkannt'], ['Grafikspeicher', (hw.vram_gb || '?') + ' GB'],
         ['Klasse', hw.hardware_class || '–']].forEach(([k, v])=>{
          const tr = d().el('tr'); tr.append(d().el('td', 's-muted', k), d().el('td', null, String(v))); t.append(tr);
        });
        box.append(d().el('h5', 's-head', 'Hardware'), t);
        const prof = (st.hardware_manager || {}).profile_state || {};
        if(prof.profile_id) box.append(d().el('small', 's-muted', 'Profil: ' + prof.profile_id + ' · ' + (prof.status || '')));
      }else{
        const t = d().el('table', 's-table');
        (st.health || []).forEach(h=>{
          const tr = d().el('tr');
          tr.append(d().el('td', null, h.component_id), d().el('td', h.state === 'HEALTHY' ? '' : 's-note warn', h.state === 'HEALTHY' ? 'gesund' : h.state));
          if((h.blocking_findings || []).length) tr.title = h.blocking_findings.join('; ');
          t.append(tr);
        });
        box.append(d().el('h5', 's-head', 'Teile'), t);

        const dev = st.development_environment || {};
        box.append(d().el('h5', 's-head', 'Entwicklungsumgebung'));
        box.append(d().el('div', 's-note ' + (dev.execution_ready ? 'ok' : 'warn'),
          dev.execution_ready ? 'Bereit: Kandidaten werden isoliert getestet.' : 'Blockiert: ' + ((dev.blockers || []).join(', ') || 'unbekannt') + ' – gebaut wird trotzdem, getestet wird nicht isoliert.'));
        const tools = st.tools || {};
        box.append(d().el('h5', 's-head', 'Werkzeuge der Runtime'));
        box.append(d().el('div', 's-small s-muted', Object.keys(tools).map(k=>k + (tools[k].healthy ? '' : ' (krank)')).join(' · ')));
      }
      this.el.replaceChildren(box);
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
