// Die Paperclip-Shell (Entwurf D, SHELL_WERKZEUG_VERTRAG_v1 §4, Spec §5).
//
// Eine Firma statt eines Cockpits: Navigation links, Kopfzeile oben, Seiten in der Mitte, das Gespräch als Schublade rechts.
// Das Dashboard zeigt vier Werkzeuge zu vier verschiedenen Sammlungen zugleich – die Prüfung, die weder Cockpit noch Minimal
// stellen konnten. Die Shell kennt kein Werkzeug beim Namen, außer dem Gespräch, das der Vertrag selbst benennt.
// Spec 4 (D4.1): rechts neben der Seite der Fensterstapel (Zone `pc-stack`, windows.js) – ein Fenster je Agent. Die Shell hört die
// Ereignisse des Teams (agent.changed, issue.changed, budget.warning, slot.changed) und frischt dann nur auf; einen Takt hat sie nicht.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  root.sedra.registerShell({
    id: 'paperclip',

    async start(ctx){
      this.ctx = ctx;
      this.api = ctx.api;
      this.onProblem = ctx.onProblem;
      this.instruments = [];
      this.unread = 0;
      const host = document.getElementById('sedra-root');
      host.classList.add('pc');
      host.replaceChildren();

      this.el = {
        nav: d().el('nav', 'pc-nav'),
        main: d().el('div', 'pc-main-col'),
        top: d().el('header', 'pc-top'),
        page: d().el('main', 'pc-page'),
        stack: d().el('aside', 'pc-stack'),
        drawer: d().el('aside', 'pc-drawer'),
        fab: d().el('button', 'pc-fab')
      };
      this.el.nav.setAttribute('aria-label', 'Navigation');
      this.el.drawer.setAttribute('aria-label', 'Gespräch');
      this.el.drawer.hidden = true;
      this.el.stack.setAttribute('aria-label', 'Agentenfenster');
      this.el.stack.hidden = true;
      this.el.main.append(this.el.top, this.el.page);
      this.el.fab.append(d().el('span', null, 'Mit SEDRA sprechen'), d().el('b', 'pc-fab-count'));
      this.el.fab.onclick = ()=>this.toggleTalk();
      host.append(this.el.nav, this.el.main, this.el.stack, this.el.drawer, this.el.fab);

      this.shellApi = {open: o=>this.openObject(o), notify: (text, tone)=>this.notify(text, tone),
                       decide: (id, way)=>this.decide(id, way), theme: name=>root.sedraBoot.setTheme(name),
                       // nach einem Shell-Wechsel: neu laden gehört der Shell; vorher Arbeitsstand und Ablage hinaus (Vertrag 1.1 §10.4)
                       reload: ()=>root.sedraWechsel && root.sedraWechsel.neuLaden ? root.sedraWechsel.neuLaden() : location.reload()};
      this.melder = root.sedraStand.makeMelder(this.api);

      this.pages = root.sedraPcPages.makePages(this.el.page, this);
      this.nav = root.sedraPcNav.makeNav(this.el.nav, this);
      this.topbar = root.sedraPcTopbar.makeTopbar(this.el.top, this);
      this.windows = root.sedraPcWindows.makeWindows(this.el.stack, this);
      this.nav.build();
      this.topbar.build();
      this.mountTalk();
      // ein Schub Ereignisse liest einmal, und höchstens einmal nach (D4.6 „Ereignisflut“) – kein Zeitgeber
      this.refresh = root.sedraPcNav.coalesce(()=>this.afterChangeNow());
      this.refreshStrip = root.sedraPcNav.coalesce(()=>this.readInstruments());

      ctx.bus.on('object.open', o=>this.openObject(o));
      ctx.bus.on('decision.pending', ()=>this.afterChange());
      ctx.bus.on('decision.answered', ()=>this.afterChange());
      ctx.bus.on('task.changed', ()=>this.afterChange());
      ctx.bus.on('model.changed', ()=>this.refreshInstruments());
      ctx.bus.on('object.actions', ()=>{ const p = this.pages.current(); if(p) this.topbar.setPage(p, this.pages.history()); this.windows.refreshVerbs(); });
      ctx.bus.on('desk.error', e=>this.notify('Die Runtime meldet: ' + e.message, 'warn'));
      ctx.bus.on('desk.resync', ()=>this.afterChange());
      // Spec 4 (N3): das Team. Die Werkzeuge lesen selbst nach; die Shell frischt Badge, Kacheln und die Verben der Fenster auf.
      ctx.bus.on('agent.changed', ()=>{ this.windows.refreshVerbs(); this.afterChange(); });
      ctx.bus.on('issue.changed', ()=>this.afterChange());
      ctx.bus.on('slot.changed', ()=>this.refreshInstruments());
      ctx.bus.on('budget.warning', e=>{
        const pct = typeof e.prozent === 'number' ? ' bei ' + e.prozent + ' %' : '';
        this.notify('Budget: Agent ' + e.agent_id + pct + (e.stufe === 'gestoppt' ? ' – gestoppt, Entscheidung im Posteingang' : ''), 'warn');
        this.afterChange();
      });

      document.addEventListener('keydown', e=>{
        if((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K')){ e.preventDefault(); this.topbar.focus(); }
        else if(e.key === 'Escape' && !this.el.drawer.hidden && !this.topbar.isOpen()) this.toggleTalk(false);
      });

      // §10.4: was in einer anderen Shell vorn lag, wird hier die Seite (ein Agent: sein Fenster); sonst der eigene Verlauf
      const stand = await this.melder.holen();
      const vorn = ((stand && stand.offen) || []).find(o=>root.sedraStand.schluessel(o) === (stand && stand.vorn));
      const fremd = vorn && stand.shell && stand.shell !== 'paperclip' && this.ctx.tools.forObject(vorn).length;
      if(!this.pages.restore() && !fremd) this.pages.open(this.pages.DASHBOARD);
      this.windows.restore();
      if(fremd){ this.openObject(vorn); this.notify('Aus der Oberfläche „' + stand.shell + '“ mitgenommen: ' + (vorn.title || vorn.type) + '.', 'note'); }
      await Promise.all([this.refreshInstruments(), this.nav.refresh()]).catch(e=>this.onProblem('Start', e));
      root.sedraBoot.onProblem = text=>this.notify(text, 'warn');
      (root.sedraBoot.problems || []).forEach(text=>this.notify(text, 'warn'));
    },

    // Das Gespräch: einmal gemountet, bleibt gemountet. Die Schublade zeigt oder verbirgt nur seinen Container (Spec §5.2.5).
    mountTalk(){
      const manifest = this.ctx.tools.all().find(t=>t.kind === 'panel' && t.id === 'talk');
      if(!manifest){
        this.el.drawer.append(d().empty('Das Werkzeug „Gespräch“ fehlt – ohne es gibt es kein Eingabefeld. uix.yaml prüfen.'));
        return;
      }
      const head = d().el('div', 'pc-drawer-head');
      head.append(d().el('b', null, 'SEDRA'));
      const close = d().el('button', 's-btn', 'Schließen');
      close.onclick = ()=>this.toggleTalk(false);
      head.append(close);
      const slot = d().el('div', 'pc-drawer-body pc-tool');
      slot.dataset.tool = 'talk';
      this.el.drawer.append(head, slot);
      this.talkState = root.sedraLifecycle.mountTool(this.ctx.tools.mod('talk'), slot, this.ctx.makeContext(manifest, null, this.shellApi), this.onProblem);
    },

    toggleTalk(open){
      const show = open === undefined ? this.el.drawer.hidden : !!open;
      this.el.drawer.hidden = !show;
      this.el.fab.classList.toggle('on', show);
      if(show){
        this.unread = 0;
        this.el.fab.querySelector('.pc-fab-count').textContent = '';
        const input = this.el.drawer.querySelector('input, textarea');
        if(input) input.focus();
      }
    },

    // Aus dem Suchfeld: kein Ort, also ein Satz für SEDRA – gesendet wird im Gespräch (derselbe Weg wie die Palette des Cockpits)
    handTo(text){
      this.toggleTalk(true);
      const mod = this.ctx.tools.mod('talk');
      if(mod && mod.send && String(text || '').trim()) mod.send(text);
    },

    notify(text, tone){
      const mod = this.ctx.tools.mod('talk');
      if(mod && mod.say) mod.say(text, tone || 'note');
      else console.warn('[paperclip]', text);
      if(this.el.drawer.hidden){
        this.unread += 1;
        this.el.fab.querySelector('.pc-fab-count').textContent = String(this.unread);
      }
    },

    openObject(object){
      if(!object || !object.type || !object.id) return;
      this.pages.open(object);
      this.refreshInstruments();
      this.nav.refresh().catch(()=>{});          // die eigene Handlung soll sofort zählen, nicht erst mit dem nächsten Ereignis
      this.ctx.bus.emit('talk.context', {object: {type: object.type, id: object.id, title: object.title || ''}});
    },

    // die Seiten melden sich hier, wenn sie stehen: Titel, Zurück, Verben, Leuchten in der Navigation
    onPage(page, history){
      this.topbar.setPage(page, history);
      this.nav.mark(page.object);
      this.melden();
    },

    // §10.2: offen sind die Seiten im Verlauf (das Dashboard ist kein Objekt) und die Agentenfenster; vorn die aktuelle Seite
    melden(){
      if(!this.melder || !this.pages) return;
      const S = root.sedraStand, seiten = this.pages.history().filter(o=>o.type !== 'dashboard').reverse();
      const fenster = this.windows ? this.windows.list().map(w=>({type: 'agent', id: w.id, title: w.title})) : [];
      const cur = this.pages.current();
      this.melder.offen(seiten.concat(fenster), cur && cur.object.type !== 'dashboard' ? S.schluessel(cur.object) : null);
    },

    // ein Agentenfenster wurde geschlossen (§9.3): Gedächtnis vergessen, den Werkzeugen und dem Arbeitsstand sagen
    onWindowClosed(object){
      root.sedraLifecycle.memoVergessen(object);
      try{ this.ctx.bus.emit('object.close', {type: object.type, id: object.id}); }catch(_e){}
      if(this.melder){ this.melder.geschlossen(object); this.melden(); }
    },

    async decide(id, way){
      const out = await this.api('/api/decisions/answer', {method: 'POST', body: {id, way}});
      this.ctx.bus.emit('decision.answered', {id, kind: 'answered'});
      await this.afterChange();
      return out;
    },

    afterChange(){ return this.refresh(); },

    async afterChangeNow(){
      const page = this.pages.current();
      if(page) this.topbar.setPage(page, this.pages.history());
      await Promise.all([this.readInstruments(), this.nav.refresh()]).catch(e=>this.onProblem('Auffrischen', e));
    },

    refreshInstruments(){ return this.refreshStrip(); },

    // die Kennzahlen des Dashboards sind die Instrumente – dieselbe Lesung wie in der Leiste des Cockpits
    async readInstruments(){
      if(!this.instruments.length) return;
      let reading;
      try{ reading = await this.api('/api/strip'); }
      catch(err){ this.instruments.forEach(c=>{ if(c.mod.update) try{ c.mod.update(null, err.message); }catch(_e){} }); return; }
      this.instruments.forEach(c=>{
        if(!c.mod.update) return;
        try{ c.mod.update(reading, null); }catch(err){ this.onProblem('Instrument ' + c.manifest.id, err); }
      });
    }
  });
})();
