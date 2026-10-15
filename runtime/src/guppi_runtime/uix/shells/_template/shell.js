// Vorlage für eine Shell (§4). Sie besitzt den Bildschirm – und kennt kein Werkzeug beim Namen: sie fragt die Registrierung,
// wer einen Objekttyp zeichnet, und gibt ihm einen Container. Mehr ist eine Shell nicht.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  root.sedra.registerShell({
    id: 'beispiel',

    async start(ctx){
      this.ctx = ctx;
      const host = document.getElementById('sedra-root');
      host.classList.add('sh-beispiel');
      this.body = d().el('div', 'sh-beispiel-body');
      // Die Verben des Objekts (Cockpit-Regel 3): eine Shell zeigt, was man mit dem Werkstück tun kann. `data-verbs` ist die
      // Vertragsmarke, an der die Abnahme sie zählt.
      this.verbs = d().el('div', 'sh-beispiel-verbs');
      this.verbs.dataset.verbs = '';
      host.replaceChildren(this.body, this.verbs);

      // Das Gespräch ist ein Werkzeug (kind: panel) – ohne es gibt es kein Eingabefeld.
      const talk = ctx.tools.all().find(t=>t.id === 'talk');
      if(talk){
        const slot = d().el('div', 'sh-beispiel-talk');
        host.append(slot);
        root.sedraLifecycle.mountTool(ctx.tools.mod('talk'), slot, ctx.makeContext(talk, null, this.shellApi()), ctx.onProblem);
      }

      ctx.bus.on('object.open', o=>this.open(o));
      this.open({type: 'task', id: 'alle', title: 'Aufgaben', collection: true});
    },

    // Was ein Werkzeug von der Shell bekommt: einen Weg zum Öffnen, einen zum Melden, einen zum Entscheiden.
    shellApi(){
      return {open: o=>this.open(o), notify: text=>console.info('[shell]', text),
              decide: (id, way)=>this.ctx.api('/api/decisions/answer', {method: 'POST', body: {id, way}}),
              reload: ()=>location.reload()};
    },

    open(object){
      if(!object) return;
      this.body.replaceChildren();
      const tools = this.ctx.tools.for(object.type);
      if(!tools.length){ this.body.append(d().empty('Kein Werkzeug für „' + object.type + '“.')); return; }
      (this.mounted || []).forEach(s=>root.sedraLifecycle.unmountTool(s, this.ctx.onProblem));
      this.mounted = tools.map(manifest=>{
        const slot = d().el('div', 'sh-beispiel-tool');
        slot.dataset.tool = manifest.id;            // Vertragsmarke: so findet die Abnahme den Container jedes Werkzeugs
        if(manifest.slot === 'nachweis') slot.dataset.slot = 'nachweis';   // … und weiß, was Nachweis ist
        this.body.append(slot);
        return root.sedraLifecycle.mountTool(this.ctx.tools.mod(manifest.id), slot,
                                             this.ctx.makeContext(manifest, object, this.shellApi()), this.ctx.onProblem);
      });
      // erst fragen, wenn gezeichnet ist – vorher weiß ein Werkzeug noch nicht, welche Handlungen sein Objekt hat
      Promise.all(this.mounted.map(s=>s.ready)).then(()=>this.drawVerbs()).catch(()=>this.drawVerbs());
    },

    drawVerbs(){
      this.verbs.replaceChildren();
      (this.mounted || []).forEach(state=>{
        if(state.el.dataset.slot === 'nachweis') return;      // die Verben gehören dem Werkstück, nicht dem Nachweis
        root.sedraLifecycle.actionsOf(state).forEach(a=>this.verbs.append(d().button(a.label, async()=>{ await a.run(); this.drawVerbs(); })));
      });
    }
  });
})();
