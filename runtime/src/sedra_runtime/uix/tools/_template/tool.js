// Vorlage für ein Werkzeug (§4). Beim Laden passiert genau eines: die Registrierung. Sonst nichts.
//
// Die vier Regeln, die die Tests erzwingen:
//   1. Gezeichnet wird nur in `el` – nie in `document`.
//   2. Gesprochen wird nur über `ctx.api()` (Routen aus `api:`) und `ctx.bus` (Ereignisse aus `events:`).
//      Kein eigenes fetch, kein localStorage, kein EventSource.
//   3. Gestylt wird nur unter `.t-<id>`, und jede Farbe ist ein Token aus ui/tokens.css.
//   4. ≤ 400 Zeilen je Datei; `unmount` muss den Container wieder leer hinterlassen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Reine Funktionen (Daten rein, Daten raus) gehören hierher: node prüft sie ohne Browser.
  function satz(objekt){
    return (objekt && objekt.summary) || 'Nichts zu zeigen.';
  }

  const tool = {
    id: 'beispiel',

    // el: der leere Container der Shell. ctx: {object, api, bus, tokens, shell, manifest}
    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-beispiel');
      ctx.bus.on('task.changed', e=>{ if(!ctx.object || e.id === ctx.object.id) this.refresh(); });
      return this.refresh();          // ein Versprechen zurückgeben: die Shell wartet damit auf die Handlungen
    },

    unmount(){ this.el.classList.remove('t-beispiel'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let objekt;
      try{ objekt = await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'task', id: this.ctx.object.id}}); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Nicht lesbar: ' + err.message)); return; }
      this.objekt = objekt;
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note', satz(objekt)));
      this.el.replaceChildren(box);
    },

    // Die Handlungen des Objekts in seinem jetzigen Zustand (Regel 3) – nie Navigation, nie eine Entscheidung.
    // Am besten vom Desk nehmen: `objekt.actions` sagt, was gerade gilt.
    actions(){
      const objekt = this.objekt;
      if(!objekt) return [];
      return (objekt.actions || []).map(a=>({label: a.label, run: async()=>{
        if(a.confirm && !confirm(a.confirm)) return;
        await this.ctx.api('/api/actions', {method: 'POST', body: {type: objekt.type, id: objekt.id, verb: a.verb}});
        await this.refresh();
      }}));
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraBeispielPure = {satz};
  if(typeof module !== 'undefined' && module.exports) module.exports = {satz};
})();
