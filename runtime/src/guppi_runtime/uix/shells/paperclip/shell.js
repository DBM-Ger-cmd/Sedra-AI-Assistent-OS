// Die Paperclip-Shell (Entwurf D, SHELL_WERKZEUG_VERTRAG_v1 §4, Spec §5).
//
// Eine Firma statt eines Cockpits: Navigation links, Kopfzeile oben, Seiten in der Mitte, das Gespräch als Schublade rechts.
// Das Dashboard zeigt vier Werkzeuge zu vier verschiedenen Sammlungen zugleich – die Prüfung, die weder Cockpit noch Minimal
// stellen konnten. Die Shell kennt kein Werkzeug beim Namen, außer dem Gespräch, das der Vertrag selbst benennt.

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
        drawer: d().el('aside', 'pc-drawer'),
        fab: d().el('button', 'pc-fab')
      };
      this.el.nav.setAttribute('aria-label', 'Navigation');
      this.el.drawer.setAttribute('aria-label', 'Gespräch');
      this.el.drawer.hidden = true;
      this.el.main.append(this.el.top, this.el.page);
      this.el.fab.append(d().el('span', null, 'Mit SEDRA sprechen'), d().el('b', 'pc-fab-count'));
      this.el.fab.onclick = ()=>this.toggleTalk();
      host.append(this.el.nav, this.el.main, this.el.drawer, this.el.fab);

      this.shellApi = {open: o=>this.openObject(o), notify: (text, tone)=>this.notify(text, tone),
                       decide: (id, way)=>this.decide(id, way), theme: name=>root.sedraBoot.setTheme(name),
                       reload: ()=>location.reload()};      // nach einem Shell-Wechsel: die Seite neu laden gehört der Shell, nicht dem Werkzeug

      this.pages = root.sedraPcPages.makePages(this.el.page, this);
      this.nav = root.sedraPcNav.makeNav(this.el.nav, this);
      this.topbar = root.sedraPcTopbar.makeTopbar(this.el.top, this);
      this.nav.build();
      this.topbar.build();
      this.mountTalk();

      ctx.bus.on('object.open', o=>this.openObject(o));
      ctx.bus.on('decision.pending', ()=>this.afterChange());
      ctx.bus.on('decision.answered', ()=>this.afterChange());
      ctx.bus.on('task.changed', ()=>this.afterChange());
      ctx.bus.on('model.changed', ()=>this.refreshInstruments());
      ctx.bus.on('desk.error', e=>this.notify('Die Runtime meldet: ' + e.message, 'warn'));

      document.addEventListener('keydown', e=>{
        if((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K')){ e.preventDefault(); this.topbar.focus(); }
        else if(e.key === 'Escape' && !this.el.drawer.hidden && !this.topbar.isOpen()) this.toggleTalk(false);
      });

      if(!this.pages.restore()) this.pages.open(this.pages.DASHBOARD);
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
    },

    async decide(id, way){
      const out = await this.api('/api/decisions/answer', {method: 'POST', body: {id, way}});
      this.ctx.bus.emit('decision.answered', {id, kind: 'answered'});
      await this.afterChange();
      return out;
    },

    async afterChange(){
      const page = this.pages.current();
      if(page) this.topbar.setPage(page, this.pages.history());
      await Promise.all([this.refreshInstruments(), this.nav.refresh()]).catch(e=>this.onProblem('Auffrischen', e));
    },

    // die Kennzahlen des Dashboards sind die Instrumente – dieselbe Lesung wie in der Leiste des Cockpits
    async refreshInstruments(){
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
