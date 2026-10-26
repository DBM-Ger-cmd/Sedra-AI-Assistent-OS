// The Cockpit shell (COCKPIT_MODUL_v1 §1/§2, SHELL_WERKZEUG_VERTRAG_v1 §4). It owns the screen and nothing else:
// strip (instruments), tree (navigation), dock (containers per object), Gespräch (one input), palette (Strg+K).
// It knows no tool by name – it asks the registry who handles an object type. The only top-level code is registerShell.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  root.sedra.registerShell({
    id: 'cockpit',

    async start(ctx){
      this.ctx = ctx;
      this.api = ctx.api;
      this.onProblem = ctx.onProblem;
      const host = document.getElementById('sedra-root');
      host.classList.add('ck');
      host.replaceChildren();

      // ---- the zones, in the order of §1
      this.el = {
        strip: d().el('div', 'ck-strip'),
        tree: d().el('nav', 'ck-tree'),
        bench: d().el('section', 'ck-bench'),
        talk: d().el('section', 'ck-talk')
      };
      this.el.strip.setAttribute('aria-label', 'Instrumente');
      this.el.tree.setAttribute('aria-label', 'Navigation');
      const middle = d().el('div', 'ck-middle');
      middle.append(this.el.tree, this.el.bench);
      host.append(this.el.strip, middle, this.el.talk);

      // ---- the pieces of the shell
      this.dock = root.sedraDock.makeDock(this.el.bench, this);
      this.tree = root.sedraTree.makeTree(this.el.tree, this);
      this.strip = root.sedraStrip.makeStrip(this.el.strip, this);
      this.palette = root.sedraPalette.makePalette(this);
      this.shellApi = {open: o=>this.openObject(o), notify: (text, tone)=>this.notify(text, tone),
                       decide: (id, way)=>this.decide(id, way), theme: name=>root.sedraBoot.setTheme(name),
                       // nach einem Shell-Wechsel: neu laden gehört der Shell; vorher Arbeitsstand und Ablage hinaus (Vertrag 1.1 §10.4)
                       reload: ()=>root.sedraWechsel && root.sedraWechsel.neuLaden ? root.sedraWechsel.neuLaden() : location.reload()};
      // Vertrag 1.1 (§9.5): Baum, Leiste und Werkbank-Zeile frischen höchstens einmal je 500 ms auf – ein Lauf sendet viele Ereignisse
      const B = root.sedraLifecycle.buendeln;
      this.auffrischen = B(()=>{ this.strip.refresh(); this.dock.refreshVerbs(); this.tree.refresh().catch(e=>this.onProblem('Baum', e)); }, 500);
      this.leisteAuffrischen = B(()=>this.strip.refresh(), 500);
      this.melder = root.sedraStand.makeMelder(this.api);

      // the Gespräch is a tool like every other one (rule 11); it gets the bottom zone as its container
      this.mountTalk();

      ctx.bus.on('object.open', o=>this.openObject(o));
      ctx.bus.on('decision.pending', ()=>this.auffrischen());
      ctx.bus.on('decision.answered', ()=>this.auffrischen());
      ctx.bus.on('task.changed', ()=>this.auffrischen());
      ctx.bus.on('model.changed', ()=>this.leisteAuffrischen());
      ctx.bus.on('desk.error', e=>this.notify('Die Runtime meldet: ' + e.message, 'warn'));

      document.addEventListener('keydown', e=>{
        if((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K')){ e.preventDefault(); this.palette.toggle(); }
        else if(e.key === 'Escape' && this.palette.isOpen()) this.palette.close();
      });

      // what the Captain sees first: his last layout plus what he had open in another shell (§10.4), otherwise the tasks
      const stand = await this.melder.holen();
      const hatte = this.dock.restore();
      const mit = root.sedraStand.uebernahme(stand, this.dock.offeneObjekte(), o=>this.dock.kann(o));
      this.dock.uebernehmen(mit.neu, mit.vorn);
      if(!hatte && !mit.neu.length) this.dock.open({type: 'task', id: 'alle', title: 'Aufgaben', collection: true});
      else this.dock.abgleichen(mit.vorn || undefined);
      if(mit.von && mit.von !== 'cockpit' && mit.neu.length)
        this.notify('Aus der Oberfläche „' + mit.von + '“ mitgenommen: ' + mit.neu.length + (mit.neu.length === 1 ? ' offenes Objekt.' : ' offene Objekte.'), 'note');
      await Promise.all([this.strip.refresh(), this.tree.refresh()]).catch(e=>this.onProblem('Start', e));
      root.sedraBoot.onProblem = text=>this.notify(text, 'warn');
      (root.sedraBoot.problems || []).forEach(text=>this.notify(text, 'warn'));
      const open = await this.api('/api/decisions').catch(()=>null);
      if(open && open.items && open.items.length) this.openObject({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true});
    },

    // ---- the Gespräch, bottom, always there (rule 1)
    mountTalk(){
      const manifest = this.ctx.tools.all().find(t=>t.kind === 'panel' && t.id === 'talk');
      if(!manifest){
        this.el.talk.append(d().empty('Das Werkzeug „Gespräch“ fehlt – ohne es gibt es kein Eingabefeld. uix.yaml prüfen.'));
        return;
      }
      const context = this.ctx.makeContext(manifest, null, this.shellApi);
      this.talkState = root.sedraLifecycle.mountTool(this.ctx.tools.mod('talk'), this.el.talk, context, this.onProblem);
      this.talkCtx = context;
    },

    // a line from the shell in the Gespräch: problems, hints, nothing that needs an answer
    notify(text, tone){
      const mod = this.ctx.tools.mod('talk');
      if(mod && mod.say) mod.say(text, tone || 'note');
      else console.warn('[cockpit]', text);
    },

    // the one input routes here (palette.js decides): a place, or a line for SEDRA
    talk(text){
      const mod = this.ctx.tools.mod('talk');
      if(mod && mod.send) return mod.send(text);
      this.notify('Das Gespräch ist nicht geladen; der Auftrag wurde nicht gesendet.', 'warn');
    },

    // every way into an object goes through here: tree, palette, a link inside a tool, the Gespräch
    openObject(object){
      if(!object || !object.type || !object.id) return;
      // der Master-Chat ist das Gespräch unten: kein Reiter, nur der Cursor in das Eingabefeld
      if(object.type === 'talk'){ const field = this.el.talk.querySelector('textarea, input'); if(field) field.focus(); return; }
      this.dock.open(object);
      this.tree.mark(object);
      this.ctx.bus.emit('talk.context', {object: {type: object.type, id: object.id, title: object.title || ''}});
    },

    // the one place decisions are answered, wherever the Captain said yes (rule 2)
    async decide(id, way){
      const out = await this.api('/api/decisions/answer', {method: 'POST', body: {id, way}});
      await Promise.all([this.strip.refresh(), this.tree.refresh()]);
      this.ctx.bus.emit('decision.answered', {id, kind: 'answered'});
      return out;
    },

    // ＋ Neu (rule 8): Vorhaben · Projekt · Datei öffnen · Modell hinzufügen – jeder Eintrag öffnet ein Werkzeug,
    // das genau das kann (Build 24: Projekt anlegen und Modell hinzufügen sind Abschnitte ihrer Werkzeuge, keine Hinweise mehr)
    openNew(anchor){
      const menu = d().el('div', 'ck-menu');
      const add = (label, hint, fn)=>{
        const item = d().el('div', 'ck-menu-item');
        item.append(d().el('b', null, label), d().el('small', null, hint));
        d().clickable(item, ()=>{ menu.remove(); fn(); });
        menu.append(item);
      };
      add('Vorhaben', 'den Satz aufschreiben, um den es geht – SEDRA macht Aufgaben daraus', ()=>this.openObject({type: 'intent', id: 'alle', title: 'Vorhaben', collection: true}));
      add('Projekt', 'einen Ordner unter projects/ als Projekt anlegen', ()=>this.openObject({type: 'project', id: 'neu', title: 'Neues Projekt'}));
      add('Datei öffnen', 'eine Datei des Projekts als eigener Reiter', ()=>this.openObject({type: 'project', id: 'dateien', title: 'Dateien'}));
      add('Modell hinzufügen', 'GGUF wählen, Rezept prüfen, Freigabe – dann laden', ()=>this.openObject({type: 'model', id: 'neu', title: 'Neues Modell'}));
      const box = anchor.getBoundingClientRect();
      menu.style.top = (box.bottom + 4) + 'px';
      menu.style.left = Math.max(8, box.right - 280) + 'px';
      document.body.append(menu);
      setTimeout(()=>{
        const away = e=>{ if(!menu.contains(e.target)){ menu.remove(); document.removeEventListener('mousedown', away); } };
        document.addEventListener('mousedown', away);
      }, 0);
    },

    // the dock tells the shell which object is in front: the Gespräch follows it (rule: talk.context)
    onDockChanged(object, offen, zuletzt){
      this.tree.mark(object);
      if(object) this.ctx.bus.emit('talk.context', {object: {type: object.type, id: object.id, title: object.title || ''}});
      if(this.melder && offen) this.melder.offen(offen, object ? object.type + ':' + object.id : null, zuletzt);   // §10.2
    },

    // ein Reiter wurde geschlossen: der Arbeitsstand vergisst ihn samt seiner Ablage, in jeder Shell (§9.3)
    onDockClosed(object){ if(this.melder) this.melder.geschlossen(object); }
  });
})();
