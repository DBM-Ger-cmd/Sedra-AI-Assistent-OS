// Werkzeug „Werkstatt“ – the models: load, unload, test (COCKPIT_MODUL_v1 rule 3: the toolbar carries the verbs of the object).
// It writes nothing by itself: loading goes through the runtime's own route, every change of a recipe is a decision at the desk.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // the line under a recipe, as the Captain reads it (pure)
  function recipeLine(r){
    const bits = [];
    if(r.model) bits.push(String(r.model).split(/[\\/]/).pop());
    if(r.context_recommended) bits.push('Kontext ' + r.context_recommended);
    if(r.size_gb) bits.push(r.size_gb + ' GB');
    if(r.min_vram_gb) bits.push('braucht ' + r.min_vram_gb + ' GB VRAM');
    if(!r.enabled) bits.push('ausgeschaltet');
    if(!r.model) bits.push('kein Modell hinterlegt');
    return bits.join(' · ') || r.provider;
  }

  const tool = {
    id: 'workshop',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-shop');
      ctx.bus.on('model.changed', ()=>this.refresh());
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-shop'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let view;
      try{ view = await this.ctx.api('/api/models'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Werkstatt nicht lesbar: ' + err.message)); return; }
      this.view = view;
      const box = d().el('div', 's-col');
      const server = view.server || {};
      box.append(d().el('div', 's-note' + (server.running ? ' ok' : ''), server.running
        ? 'Geladen: ' + (server.model || '?') + (server.context ? ' · Kontext ' + server.context : '')
        : 'Kein Modell geladen. Ohne Modell antwortet das Gespräch nicht; alles andere läuft weiter.'));
      if(view.lease) box.append(d().el('small', 's-muted', 'GPU-Sperre: ' + (view.lease.owner || '?') + ' · ' + (view.lease.purpose || '')));
      if(!view.loader_enabled) box.append(d().el('div', 's-note warn', 'Der Modell-Lader ist ausgeschaltet (Schalter). Laden ist erst nach einer Freigabe und einem Neustart möglich.'));

      box.append(d().el('h5', 's-head', 'Rezepte'));
      (view.recipes || []).forEach(r=>{
        const row = d().el('div', 't-shop-row' + (r.loaded ? ' on' : ''));
        const head = d().el('div', 's-row');
        head.append(d().el('b', null, r.id));
        if(r.loaded) head.append(d().el('span', 's-note ok s-small', 'geladen'));
        row.append(head, d().el('small', 's-muted', recipeLine(r)));
        const verbs = d().el('div', 's-row');
        if(r.loaded){
          verbs.append(d().button('Entladen', ()=>this.ctx.api('/api/model/unload', {method: 'POST', body: {}}).then(()=>this.refresh())));
          verbs.append(d().button('Testen', ()=>this.test(r.id)));
        }else if(r.enabled && r.model && view.loader_enabled){
          verbs.append(d().button('Laden', ()=>this.ctx.api('/api/model/load', {method: 'POST', body: {recipe_id: r.id}}).then(()=>this.refresh()), 'p'));
        }
        row.append(verbs);
        box.append(row);
      });
      this.out = d().el('div');
      box.append(this.out);
      this.el.replaceChildren(box);
    },

    async test(id){
      this.out.replaceChildren(d().el('div', 's-note', 'Teste ' + id + ' …'));
      try{
        const r = await this.ctx.api('/api/model/test', {method: 'POST', body: {recipe_id: id}});
        this.out.replaceChildren(d().el('div', 's-note ' + (r.status === 'completed' ? 'ok' : 'warn'),
          r.status === 'completed'
            ? 'Antwort in ' + d().fmtDuration(r.seconds) + (r.tokens_per_s ? ' · ' + r.tokens_per_s + ' Token/s' : '') + (r.numbers_ok ? ' · Zählprobe bestanden' : ' · Zählprobe nicht bestanden')
            : 'Test fehlgeschlagen: ' + (r.message || r.status)));
        if(r.reply) this.out.append(d().el('pre', 's-pre', r.reply));
      }catch(err){ this.out.replaceChildren(d().el('div', 's-note bad', 'Test nicht möglich: ' + err.message)); }
    },

    actions(){
      const loaded = ((this.view || {}).recipes || []).find(r=>r.loaded);
      if(!loaded) return [];
      return [{label: 'Entladen', run: ()=>this.ctx.api('/api/model/unload', {method: 'POST', body: {}}).then(()=>this.refresh())},
              {label: 'Testen', run: ()=>this.test(loaded.id)}];
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraWorkshopPure = {recipeLine};
  if(typeof module !== 'undefined' && module.exports) module.exports = {recipeLine};
})();
