// Werkzeug „Logbuch“ – the audit chain: time, event, component. The Cockpit keeps IDs and phases out of the way (rule 6);
// here is where they belong. Whether the chain is intact is the first thing the Captain sees, because that is what it is for.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // the events in the Captain's words; an unknown type keeps its technical name (pure)
  const WORDS = {BOOT_STARTED: 'Start begonnen', SYSTEM_READY: 'System bereit', MISSION_CREATED: 'Aufgabe angelegt',
                 MISSION_PHASE_CHANGED: 'Aufgabe weiter', GATE_CREATED: 'Freigabe angefragt', GATE_APPROVED: 'freigegeben',
                 GATE_REJECTED: 'abgelehnt', LOCAL_SWITCH_CHANGED: 'Schalter geändert', ROUTING_RECIPE_ADDED: 'Rezept hinzugefügt',
                 ROUTING_PROFILE_CHANGED: 'Modellkombination gewechselt', UIX_CHAT_ATTACH: 'Datei angehängt',
                 UIX_TOOL_DENIED: 'Werkzeug abgewiesen', MODEL_LOADED: 'Modell geladen', MODEL_UNLOADED: 'Modell entladen'};

  function words(type){ return WORDS[type] || String(type || '').toLowerCase().replace(/_/g, ' '); }

  const tool = {
    id: 'logbook',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-log');
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-log'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let v;
      try{ v = await this.ctx.api('/api/audit'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Logbuch nicht lesbar: ' + err.message)); return; }
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note ' + (v.chain_ok ? 'ok' : 'bad'),
        v.chain_ok ? 'Die Kette ist intakt: jeder Eintrag hängt am vorigen.' : 'Die Kette ist unterbrochen – das ist ernst. Nichts überschreiben, den Ordner sichern.'));
      const t = d().el('table', 's-table');
      const head = d().el('tr');
      head.append(d().el('th', null, 'Zeit'), d().el('th', null, 'Ereignis'), d().el('th', null, 'Teil'));
      t.append(head);
      (v.events || []).slice().reverse().forEach(e=>{
        const tr = d().el('tr');
        tr.append(d().el('td', null, d().fmtTime(e.timestamp)), d().el('td', null, words(e.event_type)), d().el('td', 's-muted', e.component || ''));
        tr.title = e.event_type + (e.mission_id ? ' · ' + e.mission_id : '');
        t.append(tr);
      });
      box.append(t);
      if(!(v.events || []).length) box.append(d().empty('Noch keine Einträge.'));
      this.el.replaceChildren(box);
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraLogbookPure = {words, WORDS};
  if(typeof module !== 'undefined' && module.exports) module.exports = {words, WORDS};
})();
