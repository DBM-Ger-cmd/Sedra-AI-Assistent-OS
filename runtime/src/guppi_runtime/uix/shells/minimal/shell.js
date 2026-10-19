// Die Minimal-Shell (Entwurf E, SHELL_WERKZEUG_VERTRAG_v1 §4, Spec `SPEC_SHELL_E_UND_MODULE_v1.md`).
//
// Ein Schreibtisch statt eines Cockpits: Menüleiste oben, freie Fenster, Ablage unten, die Entscheidung rechts oben.
// Sie lädt **dieselben Werkzeuge** wie das Cockpit und kennt keines beim Namen – außer dem Gespräch, das der Vertrag selbst
// benennt. Was hier anders aussieht, ist Form; was gleich bleibt, ist der Vertrag.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  root.sedra.registerShell({
    id: 'minimal',

    async start(ctx){
      this.ctx = ctx;
      this.api = ctx.api;
      this.onProblem = ctx.onProblem;
      const host = document.getElementById('sedra-root');
      host.classList.add('sh-min');
      host.replaceChildren();

      this.el = {
        bar: d().el('header', 'sh-min-bar-top'),
        desk: d().el('main', 'sh-min-desk'),
        shelf: d().el('footer', 'sh-min-shelf')
      };
      this.el.bar.setAttribute('aria-label', 'Menüleiste');
      this.el.shelf.setAttribute('aria-label', 'Ablage');
      host.append(this.el.bar, this.el.desk, this.el.shelf);

      this.shellApi = {open: o=>this.openObject(o), notify: (text, tone)=>this.notify(text, tone),
                       decide: (id, way)=>this.decide(id, way), theme: name=>root.sedraBoot.setTheme(name),
                       reload: ()=>location.reload()};      // nach einem Shell-Wechsel: die Seite neu laden gehört der Shell, nicht dem Werkzeug

      this.windows = root.sedraMinWindows.makeWindows(this.el.desk, this);
      this.menubar = root.sedraMinMenubar.makeMenubar(this.el.bar, this);
      this.shelf = root.sedraMinShelf.makeShelf(this.el.shelf, this);
      this.shelf.load();                         // die eigene Ablage aus uix.yaml (Build 19); bis dahin steht die Vorgabe
      this.note = root.sedraMinShelf.makeNote(this.el.desk, this);

      this.openTalk();

      ctx.bus.on('object.open', o=>this.openObject(o));
      ctx.bus.on('decision.pending', ()=>this.afterChange());
      ctx.bus.on('decision.answered', ()=>this.afterChange());
      ctx.bus.on('task.changed', ()=>this.afterChange());
      ctx.bus.on('model.changed', ()=>this.menubar.refresh());
      ctx.bus.on('desk.error', e=>this.notify('Die Runtime meldet: ' + e.message, 'warn'));

      document.addEventListener('keydown', e=>{
        if((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K')){ e.preventDefault(); this.menubar.openPlaces(); }
        else if(e.key === 'Escape' && this.menubar.isOpen()) this.menubar.closeMenu();
        else if(e.key === 'Escape' && root.sedraMinShelfEdit.isOpen()) root.sedraMinShelfEdit.close();
      });

      if(!this.windows.restore()) this.openObject({type: 'task', id: 'alle', title: 'Aufgaben', collection: true});
      this.shelf.mark();
      await Promise.all([this.menubar.refresh(), this.note.refresh()]).catch(e=>this.onProblem('Start', e));
      root.sedraBoot.onProblem = text=>this.notify(text, 'warn');
      (root.sedraBoot.problems || []).forEach(text=>this.notify(text, 'warn'));
    },

    // Das Gespräch: ein Fenster, das bleibt. Ohne es gäbe es kein Eingabefeld (Regel 1) – darum hat es keinen Schließknopf.
    openTalk(){
      const manifest = this.ctx.tools.all().find(t=>t.kind === 'panel' && t.id === 'talk');
      if(!manifest){
        this.notify('Das Werkzeug „Gespräch“ fehlt – ohne es gibt es kein Eingabefeld. uix.yaml prüfen.', 'warn');
        return;
      }
      const screen = {w: window.innerWidth, h: window.innerHeight};
      this.windows.open({type: 'talk', id: 'guppi', title: 'SEDRA'},
                        {manifests: [manifest], closable: false,
                         box: {x: screen.w - 420, y: 220, w: 380, h: 420}});
    },

    // Eine Zeile von der Shell im Gespräch – Hinweise, Probleme; nichts, was eine Antwort braucht.
    notify(text, tone){
      const mod = this.ctx.tools.mod('talk');
      if(mod && mod.say) mod.say(text, tone || 'note');
      else console.warn('[minimal]', text);
    },

    // Ein Auftrag aus der Ablage: der Satz geht ins Gespräch, als hätte der Captain ihn getippt (Build 19). Nichts läuft hier.
    sendToTalk(text){
      const mod = this.ctx.tools.mod('talk');
      if(!mod || !mod.send){ this.notify('Ohne das Gespräch kann kein Auftrag gesendet werden.', 'warn'); return; }
      const talk = this.windows.windows.get('talk:guppi');
      if(talk) this.windows.focus(talk);
      return mod.send(text);
    },

    openObject(object){
      if(!object || !object.type || !object.id) return;
      this.windows.open(object);
      this.shelf.mark();
      this.note.refresh().catch(()=>{});         // dito: die Karte rechts oben folgt der eigenen Handlung sofort
      this.ctx.bus.emit('talk.context', {object: {type: object.type, id: object.id, title: object.title || ''}});
    },

    // Der eine Ort, an dem geantwortet wird – egal ob aus der Karte, dem Werkzeug oder dem Gespräch (Regel 2).
    async decide(id, way){
      const out = await this.api('/api/decisions/answer', {method: 'POST', body: {id, way}});
      this.ctx.bus.emit('decision.answered', {id, kind: 'answered'});
      await this.afterChange();
      return out;
    },

    async afterChange(){
      this.windows.refreshVerbs();
      this.shelf.mark();
      await Promise.all([this.menubar.refresh(), this.note.refresh()]).catch(e=>this.onProblem('Auffrischen', e));
    },

    // Welches Fenster vorn steht: das Gespräch folgt ihm, damit „mach weiter“ weiß, worum es geht.
    onWindowFocus(object){
      this.shelf.mark();
      if(object) this.ctx.bus.emit('talk.context', {object: {type: object.type, id: object.id, title: object.title || ''}});
    }
  });
})();
