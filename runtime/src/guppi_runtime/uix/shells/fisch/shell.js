// Shell „Translator“ (19.10.2026) – nach dem Translator-Fisch-Konzept v0.1: ein Goldfischglas, ein Goldfisch, die Eingabe als Wolke,
// Antworten als Blasen; vier Modi: Übersetzen · News · Aufnahme · Transkript. Die Shell besitzt den Bildschirm und gibt den Werkzeugen Container;
// sie kennt kein Werkzeug beim Namen (außer dem Gespräch, das der Vertrag nennt – es ist eine Schublade wie in Paperclip).
// Der Satz aus der Wolke geht als `frage` in das Objekt des Modus; das Werkzeug des Modus macht daraus seine Arbeit.
// Farben nur über Tokens (--fisch-…, ui/tokens.css). Der Fisch ist eine eigene Zeichnung aus CSS, keine fremde Figur.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const MODI = [
    {id: 'uebersetzen', label: 'Übersetzen', hint: 'eine Nachricht für eine andere Rolle', object: {type: 'uebersetzung', id: 'wolke', title: 'Übersetzen'},
     platzhalter: 'Was soll der Translator für eine andere Rolle neu formulieren?'},
    {id: 'news', label: 'News', hint: 'ein Brief aus deinen Quellen', object: {type: 'nachrichten', id: 'brief', title: 'Nachrichten'},
     platzhalter: 'Wofür interessierst du dich heute? (wird zu den Interessen des Briefs)'},
    {id: 'aufnahme', label: 'Aufnahme', hint: 'aufnehmen, Sprache → Text (Kern)', object: {type: 'aufnahme', id: 'rekorder', title: 'Rekorder'},
     platzhalter: 'Ein Titel für die nächste Aufnahme – Enter trägt ihn in den Rekorder ein'},
    {id: 'transkript', label: 'Transkript', hint: 'importieren, suchen, Erkenntnisse, freigeben', object: {type: 'transkript', id: 'alle', title: 'Transkripte'},
     platzhalter: 'Wonach soll der Translator im Transkript suchen?'}
  ];
  const KEY = 'sedra.fisch.modus';

  // Welcher Modus zu einem Objekttyp gehört (rein)
  function modusFuer(type){ return MODI.find(m=>m.object.type === type) || null; }

  root.sedra.registerShell({
    id: 'fisch',

    async start(ctx){
      this.ctx = ctx; this.api = ctx.api; this.onProblem = ctx.onProblem;
      this.mounted = []; this.unread = 0;
      const host = document.getElementById('sedra-root');
      host.classList.add('sh-fisch');
      host.replaceChildren();
      this.el = {};
      host.append(this.kopf(), this.raum(), this.schublade(), this.fab());
      this.shellApi = {open: o=>this.openObject(o), notify: (t, tone)=>this.notify(t, tone),
                       decide: (id, way)=>this.api('/api/decisions/answer', {method: 'POST', body: {id, way}}), reload: ()=>location.reload()};
      this.mountTalk();
      ctx.bus.on('object.open', o=>this.openObject(o));
      ctx.bus.on('decision.pending', ()=>this.notify('Eine Entscheidung wartet – im Gespräch „Entscheidungen“ sagen.', 'warn'));
      document.addEventListener('keydown', e=>{
        if((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K')){ e.preventDefault(); this.el.feld.focus(); }
        else if(e.key === 'Escape' && !this.el.drawer.hidden) this.toggleTalk(false);
      });
      let modus = 'uebersetzen';
      try{ modus = localStorage.getItem(KEY) || modus; }catch(_e){}
      this.setModus(MODI.some(m=>m.id === modus) ? modus : 'uebersetzen');
      root.sedraBoot.onProblem = text=>this.notify(text, 'warn');
      (root.sedraBoot.problems || []).forEach(text=>this.notify(text, 'warn'));
    },

    // ---- Kopf: Marke, die drei Modi, ein Hinweis
    kopf(){
      const kopf = d().el('header', 'fi-kopf');
      kopf.append(d().el('div', 'fi-marke', 'Translator'), d().el('small', 'fi-marke-sub', 'Bedeutung vor Stil · nichts erfunden · lokal'));
      this.el.modus = d().el('div', 'fi-modus'); this.el.modus.setAttribute('role', 'tablist'); this.el.modus.setAttribute('aria-label', 'Modus');
      MODI.forEach(m=>{
        const b = d().el('button', 'fi-modus-btn', m.label); b.type = 'button'; b.dataset.modus = m.id; b.title = m.hint; b.setAttribute('role', 'tab');
        b.onclick = ()=>this.setModus(m.id);
        this.el.modus.append(b);
      });
      kopf.append(this.el.modus, d().el('small', 'fi-hinweis', 'Strg+K: zur Wolke · Alt+S: Oberfläche'));
      return kopf;
    },

    // ---- Der Raum: das Glas mit dem Fisch, die Wolke, die Blasen
    raum(){
      const raum = d().el('main', 'fi-raum');
      const seite = d().el('div', 'fi-seite');
      const glas = d().el('div', 'fi-glas'); glas.setAttribute('aria-hidden', 'true');
      const wasser = d().el('div', 'fi-wasser');
      this.el.fisch = d().el('div', 'fi-fisch');
      this.el.fisch.append(d().el('span', 'fi-koerper'), d().el('span', 'fi-schwanz'), d().el('span', 'fi-flosse'), d().el('span', 'fi-auge'));
      wasser.append(this.el.fisch, d().el('div', 'fi-sand'));
      for(let i = 0; i < 6; i++){ const b = d().el('span', 'fi-blubber'); b.style.setProperty('--i', String(i)); wasser.append(b); }
      glas.append(d().el('div', 'fi-glanz'), wasser, d().el('div', 'fi-glasrand'));
      this.el.glas = glas;

      const wolke = d().el('form', 'fi-wolke');
      this.el.feld = d().el('textarea'); this.el.feld.rows = 3; this.el.feld.setAttribute('aria-label', 'Frage an den Translator');
      this.el.feld.onfocus = ()=>this.zustand('listening'); this.el.feld.onblur = ()=>{ if(this.el.fisch.dataset.zustand === 'listening') this.zustand('idle'); };
      this.el.feld.onkeydown = e=>{ if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); this.senden(); } };
      const row = d().el('div', 'fi-wolke-row');
      this.el.senden = d().el('button', 'fi-senden', 'Senden'); this.el.senden.type = 'submit';
      row.append(this.el.senden, d().el('small', 'fi-wolke-hint', 'Enter sendet · Shift+Enter: neue Zeile'));
      wolke.append(this.el.feld, row);
      wolke.onsubmit = e=>{ e.preventDefault(); this.senden(); };
      seite.append(wolke, glas);

      this.el.blasen = d().el('section', 'fi-blasen'); this.el.blasen.setAttribute('aria-label', 'Antworten');
      raum.append(seite, this.el.blasen);
      return raum;
    },

    schublade(){
      this.el.drawer = d().el('aside', 'fi-drawer'); this.el.drawer.hidden = true; this.el.drawer.setAttribute('aria-label', 'Gespräch');
      return this.el.drawer;
    },

    fab(){
      this.el.fab = d().el('button', 'fi-fab'); this.el.fab.type = 'button';
      this.el.fab.append(d().el('span', null, 'Mit SEDRA sprechen'), d().el('b', 'fi-fab-count'));
      this.el.fab.onclick = ()=>this.toggleTalk();
      return this.el.fab;
    },

    // ---- Zustände des Fisches (Konzept: idle · listening · thinking · answering · news)
    zustand(z){ this.el.fisch.dataset.zustand = z; this.el.glas.dataset.zustand = z; },

    setModus(id){
      const m = MODI.find(x=>x.id === id) || MODI[0];
      this.modus = m;
      this.el.modus.querySelectorAll('button').forEach(b=>{ const on = b.dataset.modus === m.id; b.classList.toggle('on', on); b.setAttribute('aria-selected', String(on)); });
      this.el.feld.placeholder = m.platzhalter;
      try{ localStorage.setItem(KEY, m.id); }catch(_e){}
      this.openObject(Object.assign({}, m.object));
    },

    // Der Satz aus der Wolke: ins Objekt des Modus – das Werkzeug macht daraus Übersetzung, Interessen oder Suche
    senden(){
      const text = this.el.feld.value.trim();
      if(!text) return;
      this.el.feld.value = '';
      if(this.modus.id === 'aufnahme'){      // der Satz wird der Titel im ersten Feld der Blase – kein neues Mounten, das Pult bleibt
        const titel = this.el.blasen.querySelector('.fi-blase-inhalt input'); if(titel){ titel.value = text; titel.focus(); }
        this.zustand('listening'); return;
      }
      this.zustand('thinking');
      this.openObject(Object.assign({}, this.modus.object, {frage: text}));
      clearTimeout(this.antwortTimer);
      this.antwortTimer = setTimeout(()=>this.zustand(this.modus.id === 'news' ? 'news' : 'answering'), 1200);
    },

    // ---- Die Blase: ein Container je Objekt; Werkstück vorn, Nachweise (slot nachweis) in einer Seitenspalte
    openObject(object){
      if(!object || !object.type) return;
      if(object.type === 'talk'){ this.toggleTalk(true); return; }
      const m = modusFuer(object.type);
      if(m && this.modus && m.id !== this.modus.id){ this.modus = m; this.el.modus.querySelectorAll('button').forEach(b=>b.classList.toggle('on', b.dataset.modus === m.id)); this.el.feld.placeholder = m.platzhalter; try{ localStorage.setItem(KEY, m.id); }catch(_e){} }
      this.mounted.forEach(s=>root.sedraLifecycle.unmountTool(s, this.onProblem)); this.mounted = [];
      this.el.blasen.replaceChildren();
      const tools = this.ctx.tools.for(object.type);
      const blase = d().el('div', 'fi-blase'); blase.dataset.verbs = '';
      blase.append(d().el('div', 'fi-blase-titel', object.title || object.type));
      if(!tools.length){ blase.append(d().empty('Für „' + object.type + '“ gibt es kein Werkzeug.')); this.el.blasen.append(blase); return; }
      const inhalt = tools.filter(t=>(t.slot || 'inhalt') !== 'nachweis'), nachweise = object.collection ? [] : tools.filter(t=>(t.slot || 'inhalt') === 'nachweis');
      const koerper = d().el('div', 'fi-blase-koerper' + (nachweise.length ? ' mit-nachweis' : ''));
      const links = d().el('div', 'fi-blase-inhalt'); koerper.append(links);
      let rechts = null;
      if(nachweise.length){ rechts = d().el('aside', 'fi-blase-nachweis'); rechts.dataset.slot = 'nachweis'; koerper.append(rechts); }
      const mount = (manifest, host)=>{
        const slot = d().el('div', 'fi-tool'); slot.dataset.tool = manifest.id; host.append(slot);
        this.mounted.push(root.sedraLifecycle.mountTool(this.ctx.tools.mod(manifest.id), slot, this.ctx.makeContext(manifest, object, this.shellApi), this.onProblem));
      };
      inhalt.forEach(t=>mount(t, links)); nachweise.forEach(t=>mount(t, rechts));
      blase.append(koerper);
      this.el.blasen.append(blase);
      this.ctx.bus.emit('talk.context', {object: {type: object.type, id: object.id, title: object.title || ''}});
      Promise.all(this.mounted.map(s=>s.ready)).then(()=>this.drawVerbs(blase)).catch(()=>{});
    },

    drawVerbs(blase){
      const alt = blase.querySelector('.fi-verbs'); if(alt) alt.remove();
      const verbs = d().el('div', 'fi-verbs');
      this.mounted.forEach(s=>root.sedraLifecycle.actionsOf(s).forEach(a=>verbs.append(d().button(a.label, async()=>{ await a.run(); this.drawVerbs(blase); }))));
      if(verbs.childNodes.length) blase.insertBefore(verbs, blase.firstChild.nextSibling);
    },

    // ---- Das Gespräch: Schublade (wie Paperclip); einmal gemountet, bleibt gemountet
    mountTalk(){
      const manifest = this.ctx.tools.all().find(t=>t.kind === 'panel' && t.id === 'talk');
      if(!manifest){ this.el.drawer.append(d().empty('Das Werkzeug „Gespräch“ fehlt – ohne es gibt es kein Eingabefeld. uix.yaml prüfen.')); return; }
      const head = d().el('div', 'fi-drawer-head'); head.append(d().el('b', null, 'SEDRA'));
      const close = d().el('button', 's-btn', 'Schließen'); close.type = 'button'; close.onclick = ()=>this.toggleTalk(false); head.append(close);
      const slot = d().el('div', 'fi-drawer-body fi-tool'); slot.dataset.tool = 'talk';
      this.el.drawer.append(head, slot);
      this.talkState = root.sedraLifecycle.mountTool(this.ctx.tools.mod('talk'), slot, this.ctx.makeContext(manifest, null, this.shellApi), this.onProblem);
    },

    toggleTalk(open){
      const show = open === undefined ? this.el.drawer.hidden : !!open;
      this.el.drawer.hidden = !show; this.el.fab.classList.toggle('on', show);
      if(show){ this.unread = 0; this.el.fab.querySelector('.fi-fab-count').textContent = ''; const f = this.el.drawer.querySelector('input, textarea'); if(f) f.focus(); }
    },

    notify(text, tone){
      const mod = this.ctx.tools.mod('talk');
      if(mod && mod.say) mod.say(text, tone || 'note'); else console.warn('[fisch]', text);
      if(this.el.drawer.hidden){ this.unread += 1; this.el.fab.querySelector('.fi-fab-count').textContent = String(this.unread); }
    }
  });

  root.sedraFischPure = {MODI, modusFuer};
  if(typeof module !== 'undefined' && module.exports) module.exports = {MODI, modusFuer};
})();
