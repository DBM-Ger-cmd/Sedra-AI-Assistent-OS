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
                       // nach einem Shell-Wechsel: neu laden gehört der Shell; vorher Arbeitsstand und Ablage hinaus (Vertrag 1.1 §10.4)
                       reload: ()=>root.sedraWechsel && root.sedraWechsel.neuLaden ? root.sedraWechsel.neuLaden() : location.reload()};
      this.melder = root.sedraStand.makeMelder(this.api);
      // §9.5: ein Lauf sendet viele Ereignisse – Verben, Ablage, Leiste und Karte frischen höchstens einmal je 500 ms auf
      this.buendel = root.sedraLifecycle.buendeln(()=>this.afterChangeNow(), 500);

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
      ctx.bus.on('object.actions', ()=>this.windows.refreshVerbs());
      ctx.bus.on('desk.error', e=>this.notify('Die Runtime meldet: ' + e.message, 'warn'));

      document.addEventListener('keydown', e=>{
        if((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K')){ e.preventDefault(); this.menubar.openPlaces(); }
        else if(e.key === 'Escape' && this.menubar.isOpen()) this.menubar.closeMenu();
        else if(e.key === 'Escape' && root.sedraMinShelfEdit.isOpen()) root.sedraMinShelfEdit.close();
      });

      // §10.4: die eigenen Fenster, dazu was eine andere Shell offen hatte (höchstens 6 Fenster), das vordere nach vorn
      const stand = await this.melder.holen();
      const hatte = this.windows.restore();
      const mit = root.sedraStand.uebernahme(stand, this.windows.list(), o=>o.type !== 'talk' && this.ctx.tools.forObject(o).length > 0);
      const neu = mit.neu.slice(0, Math.max(0, 6 - this.windows.list().filter(o=>o.type !== 'talk').length));
      neu.forEach(o=>this.windows.open(o));
      const vorn = mit.vorn && this.windows.windows.get(mit.vorn);
      if(vorn) this.windows.focus(vorn);
      if(!hatte && !neu.length) this.openObject({type: 'task', id: 'alle', title: 'Aufgaben', collection: true});
      if(mit.von && mit.von !== 'minimal' && neu.length)
        this.notify('Aus der Oberfläche „' + mit.von + '“ mitgenommen: ' + neu.length + (neu.length === 1 ? ' Fenster.' : ' Fenster.'), 'note');
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
      await this.afterChangeNow();                // die eigene Antwort zählt sofort, nicht erst nach dem Bündel
      return out;
    },

    afterChange(){ this.buendel(); return Promise.resolve(); },

    async afterChangeNow(){
      this.windows.refreshVerbs();
      this.shelf.mark();
      await Promise.all([this.menubar.refresh(), this.note.refresh()]).catch(e=>this.onProblem('Auffrischen', e));
    },

    // Welches Fenster vorn steht: das Gespräch folgt ihm, damit „mach weiter“ weiß, worum es geht.
    onWindowFocus(object){
      this.shelf.mark();
      if(object) this.ctx.bus.emit('talk.context', {object: {type: object.type, id: object.id, title: object.title || ''}});
      this.melden();
    },

    // §10.2: offen sind die Fenster (ohne das Gespräch), vorn das oberste
    melden(){
      if(!this.melder || !this.windows) return;
      const front = this.windows.front();
      this.melder.offen(this.windows.list().filter(o=>o.type !== 'talk'),
                        front && front.type !== 'talk' ? root.sedraStand.schluessel(front) : null);
    },

    onWindowClosed(object){
      root.sedraLifecycle.memoVergessen(object);
      try{ this.ctx.bus.emit('object.close', {type: object.type, id: object.id}); }catch(_e){}
      if(this.melder){ this.melder.geschlossen(object); this.melden(); }
    }
  });
})();
