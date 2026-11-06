// Werkzeug „Tests“ – was über einen Kandidaten nachgewiesen ist (COCKPIT_MODUL_v1 Regel 5: Nachweise, nicht Versprechen).
// Es zeigt den Stand, den der Kandidatenbericht selbst festhält: wurden Tests ausgeführt, wo, was sagen die statischen Prüfungen,
// und was blockiert die isolierte Ausführung. Ein nicht gelaufener Test wird nie als „grün“ dargestellt.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Ein Satz über den Teststand – und ob er beruhigend ist oder nicht (rein)
  function verdict(report){
    if(!report || !report.exists) return {tone: '', text: 'Kein Kandidatenbericht: diese Aufgabe ändert keine Dateien.'};
    if(report.ready_for_merge) return {tone: 'ok', text: 'Geprüft und bereit zur Übernahme.'};
    if(report.tests_executed) return {tone: report.host_code_executed ? 'warn' : 'ok',
      text: report.host_code_executed ? 'Getestet – aber auf diesem Rechner, nicht isoliert.' : 'In der Entwicklungsumgebung getestet.'};
    return {tone: 'warn', text: 'Noch nicht getestet. Der Diff ist geprüft, die Tests sind nicht gelaufen – das ist kein grünes Licht.'};
  }

  const tool = {
    id: 'tests',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-tests');
      this.mission = ctx.object && ctx.object.id;
      ctx.bus.on('task.changed', e=>{ if(e.id === this.mission) this.refresh(); });
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-tests'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let report;
      try{ report = await this.ctx.api('/api/candidate/report', {method: 'POST', body: {mission_id: this.mission}}); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Nachweise nicht lesbar: ' + err.message)); return; }
      this.report = report;
      const box = d().el('div', 's-col');
      const v = verdict(report);
      box.append(d().el('div', 's-note ' + v.tone, v.text));
      if(!report.exists){ this.el.replaceChildren(box); return; }

      if(report.qualification_text) box.append(d().el('small', 's-muted', 'Stand: ' + report.qualification_text));

      if((report.static_checks || []).length){
        box.append(d().el('h5', 's-head', 'Statische Prüfungen'));
        const t = d().el('table', 's-table');
        report.static_checks.forEach(c=>{
          const tr = d().el('tr');
          const ok = String(c.check || '').endsWith('PASS');
          tr.append(d().el('td', null, c.path || '–'), d().el('td', ok ? 's-ok' : 's-bad', String(c.check || '').replace(/_/g, ' ').toLowerCase()));
          t.append(tr);
        });
        box.append(t);
      }

      if((report.commands || []).length){
        box.append(d().el('h5', 's-head', 'Geplante Testläufe'));
        report.commands.forEach(cmd=>box.append(d().el('pre', 's-pre', Array.isArray(cmd) ? cmd.join(' ') : String(cmd))));
      }
      if(report.execution_ready === false){
        box.append(d().el('div', 's-note warn', 'Isoliert ausführen geht hier nicht: ' + ((report.blockers || []).join(', ') || 'Grund unbekannt')
          + '. Gebaut wird trotzdem – getestet wird dann nicht isoliert.'));
      }
      if((report.files || []).length){
        box.append(d().el('h5', 's-head', 'Dateien des Kandidaten'));
        const t = d().el('table', 's-table');
        report.files.forEach(f=>{
          const tr = d().el('tr');
          tr.append(d().el('td', null, f.path), d().el('td', 's-muted', d().fmtBytes(f.bytes)));
          t.append(tr);
        });
        box.append(t);
      }
      box.append(d().el('small', 's-muted', 'Quelle: candidate-report.json dieser Aufgabe' + (report.created_at ? ' · ' + d().fmtTime(report.created_at) : '')));
      this.el.replaceChildren(box);
    },

    // Ein Nachweis trägt keine Verben an der Werkbank: „Testen“ gehört dem Kandidaten und steht dort (candidate/tool.js).
    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraTestsPure = {verdict};
  if(typeof module !== 'undefined' && module.exports) module.exports = {verdict};
})();
