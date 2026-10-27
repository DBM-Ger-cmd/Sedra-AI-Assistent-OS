// Die Start-Shell – der Einstieg: hier wird die Oberfläche gewählt, angelegt oder von außen vorgelegt.
//
// Sie ist die Standard-Shell, solange der Captain keine gewählt hat (local_config/uix.yaml ohne `shell`). Danach startet
// SEDRA direkt in der gewählten; zurück hierher führt das Werkzeug „Module“ in jeder Shell („Diese Shell nehmen“ → Start).
//
// Was sie tut, ist Konfiguration der Shell selbst – welche Form läuft – und gehört deshalb hierher, wie das Layout zu jeder
// anderen Shell. Alles andere überlässt sie den Werkzeugen: das Gespräch unten, die Entscheidungen, sobald eine wartet.
// Sie öffnet keine Objekte (provides ohne dock/windows); die Abnahme weiß das aus dem Manifest.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const TRUST = {CORE: 'im Paket', CAPTAIN: 'von dir angelegt', COMMUNITY: 'von außen – nur Leserouten'};

  root.sedra.registerShell({
    id: 'start',

    async start(ctx){
      this.ctx = ctx;
      this.api = ctx.api;
      this.onProblem = ctx.onProblem;
      const host = document.getElementById('sedra-root');
      host.classList.add('st');
      host.replaceChildren();

      this.el = {
        head: d().el('header', 'st-head'),
        main: d().el('main', 'st-main'),
        side: d().el('aside', 'st-side'),
        talk: d().el('section', 'st-talk')
      };
      this.el.side.hidden = true;
      this.el.main.setAttribute('aria-label', 'Oberfläche wählen');
      const body = d().el('div', 'st-body');
      body.append(this.el.main, this.el.side);
      host.append(this.el.head, body, this.el.talk);

      this.shellApi = {open: o=>this.openObject(o), notify: (text, tone)=>this.notify(text, tone),
                       decide: (id, way)=>this.decide(id, way), theme: name=>root.sedraBoot.setTheme(name),
                       reload: ()=>root.sedraWechsel && root.sedraWechsel.neuLaden ? root.sedraWechsel.neuLaden() : location.reload()};

      this.buildHead();
      this.mountTalk();
      ctx.bus.on('tools.refresh', ()=>this.refresh());
      ctx.bus.on('decision.pending', ()=>this.decisions());
      ctx.bus.on('decision.answered', ()=>this.decisions());
      ctx.bus.on('desk.error', e=>this.notify('Die Runtime meldet: ' + e.message, 'warn'));
      await Promise.all([this.refresh(), this.decisions()]).catch(e=>this.onProblem('Start', e));
      root.sedraBoot.onProblem = text=>this.notify(text, 'warn');
      (root.sedraBoot.problems || []).forEach(text=>this.notify(text, 'warn'));
    },

    buildHead(){
      const h = this.el.head;
      h.append(d().el('span', 'st-mark'), d().el('b', null, 'SEDRA'));
      h.append(d().el('span', 'st-head-text', 'Wähle die Oberfläche. Du kannst sie jederzeit im Werkzeug „Module“ wechseln – oder direkt dort starten: START_SEDRA <id>.'));
    },

    // ---- die Liste der Oberflächen: aus derselben Route wie das Werkzeug „Module“
    async refresh(){
      let view;
      try{ view = await this.api('/api/uix/modules'); }
      catch(err){ this.el.main.replaceChildren(d().el('div', 's-note bad', 'Oberflächen nicht lesbar: ' + err.message)); return; }
      this.view = view;
      const grid = d().el('div', 'st-grid');
      view.shells.filter(s=>s.id !== 'start').forEach(s=>grid.append(this.card(s)));   // die Auswahl selbst steht nicht zur Wahl
      const col = d().el('div', 'st-col');
      col.append(grid, this.make());
      if(view.rejected.length){
        const note = d().el('div', 's-note warn');
        note.append(d().el('b', null, view.rejected.length + ' Modul(e) nicht geladen – '), d().el('span', null, 'Grund und Datei stehen im Werkzeug „Module“ der gewählten Oberfläche.'));
        col.append(note);
      }
      this.el.main.replaceChildren(col);
    },

    card(s){
      const box = d().el('article', 'st-card' + (s.enabled ? ' on' : ''));
      const pic = d().el('div', 'st-pic');
      if(s.preview){
        const img = d().el('img');
        img.alt = '';
        img.src = '/uix/shells/' + s.id + '/preview.png';     // nur, wenn die Liste sagt, dass es eines gibt – kein 404 ins Leere
        pic.append(img);
      }else pic.append(d().el('span', 'st-pic-none', 'kein Bild – preview.png in den Ordner legen'));
      const text = d().el('div', 'st-card-text');
      text.append(d().el('h2', null, s.name), d().el('p', null, s.description || ''),
                  d().el('small', 's-muted', TRUST[s.trust] || s.trust));
      const row = d().el('div', 's-row');
      if(s.enabled) row.append(d().el('span', 's-note ok', 'läuft gerade'));
      else row.append(d().button('Diese Oberfläche nehmen', async()=>{
        await this.api('/api/uix/shell', {method: 'POST', body: {shell: s.id}});
        this.shellApi.reload();
      }, 'p'));
      row.append(d().button(s.default ? 'Ist der Standard' : 'Zum Standard machen', async()=>{
        const out = await this.api('/api/uix/standard', {method: 'POST', body: {shell: s.id}});
        this.notify(out.note, 'note');
        await this.refresh();
      }));
      box.append(pic, text, row);
      return box;
    },

    // ---- eigene anlegen (Audit) oder fremde vorlegen (Gate) – die beiden Wege, die auch das Werkzeug „Module“ kennt
    make(){
      const box = d().el('div', 'st-make');
      const own = d().el('div', 'st-make-row');
      const id = d().el('input');
      id.placeholder = 'Name in kleinen Buchstaben, z. B. meine-bruecke';
      id.setAttribute('aria-label', 'Name der neuen Oberfläche');
      own.append(d().el('b', null, 'Eigene Oberfläche anlegen'),
                 d().el('small', 's-muted', 'Aus der Vorlage: ein funktionierendes Minimum mit Kommentaren, umbenannt und geprüft. Kein Gate – eigene Form.'),
                 id, d().button('Anlegen', async()=>{
                   const out = await this.api('/api/uix/scaffold', {method: 'POST', body: {kind: 'shell', id: id.value.trim()}});
                   id.value = '';
                   this.notify(out.note, 'note');
                   await this.refresh();
                 }));
      const foreign = d().el('div', 'st-make-row');
      const folder = d().el('input');
      folder.placeholder = 'Ordner auf diesem Rechner – vollständiger Pfad';
      folder.setAttribute('aria-label', 'Ordner der fremden Oberfläche');
      foreign.append(d().el('b', null, 'Oberfläche von außen vorlegen'),
                     d().el('small', 's-muted', 'Manifest, Prüfsummen und Durchsicht stehen danach rechts in der Entscheidung. Eingebaut wird erst nach deiner Freigabe.'),
                     folder, d().button('Vorlegen', async()=>{
                       await this.api('/api/uix/install', {method: 'POST', body: {kind: 'shell', source: folder.value.trim()}});
                       folder.value = '';
                       await this.decisions();
                     }));
      box.append(own);
      if(root.sedraVorgabe){            // Build 17: aus einer Vorgabe – Satz an SEDRA oder Vorlage, Skizze, anlegen und gleich nehmen
        const vg = d().el('div', 'st-make-row');
        vg.append(root.sedraVorgabe.block(this.api, (t, tone)=>this.notify(t, tone), async out=>{
          await this.api('/api/uix/shell', {method: 'POST', body: {shell: out.id}});
          this.shellApi.reload();                       // wie „Diese Oberfläche nehmen“: die gewählte Shell startet
        }));
        box.append(vg);
      }
      box.append(foreign);
      return box;
    },

    // ---- Entscheidungen: das Werkzeug, sobald etwas wartet – an der Seite, mit derselben Antwortroute wie überall
    async decisions(){
      let view = null;
      try{ view = await this.api('/api/decisions'); }catch(_e){ return; }
      const n = ((view || {}).summary || {}).count || ((view || {}).items || []).length || 0;
      if(!n){
        if(this.decisionState) root.sedraLifecycle.unmountTool(this.decisionState, this.onProblem);
        this.decisionState = null;
        this.el.side.hidden = true;
        return;
      }
      if(this.decisionState) return;                 // steht schon; das Werkzeug hört den Bus selbst
      const tools = this.ctx.tools.for('decision').filter(m=>m.slot !== 'nachweis');
      if(!tools.length) return;
      this.el.side.hidden = false;
      this.el.side.replaceChildren();
      const slot = d().el('div', 'st-tool');
      slot.dataset.tool = tools[0].id;
      this.el.side.append(slot);
      const object = {type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true};
      this.decisionState = root.sedraLifecycle.mountTool(this.ctx.tools.mod(tools[0].id), slot, this.ctx.makeContext(tools[0], object, this.shellApi), this.onProblem);
    },

    mountTalk(){
      const manifest = this.ctx.tools.all().find(t=>t.kind === 'panel' && t.id === 'talk');
      if(!manifest){ this.el.talk.append(d().empty('Das Werkzeug „Gespräch“ fehlt. uix.yaml prüfen.')); return; }
      const slot = d().el('div', 'st-tool');
      slot.dataset.tool = 'talk';
      this.el.talk.append(slot);
      this.talkState = root.sedraLifecycle.mountTool(this.ctx.tools.mod('talk'), slot, this.ctx.makeContext(manifest, null, this.shellApi), this.onProblem);
    },

    notify(text, tone){
      const mod = this.ctx.tools.mod('talk');
      if(mod && mod.say) mod.say(text, tone || 'note'); else console.warn('[start]', text);
    },

    // Diese Shell öffnet keine Objekte. Wer eines will, bekommt den ehrlichen Satz – und den Weg.
    openObject(object){
      if(object && object.type === 'decision'){ this.decisions(); return; }
      this.notify('Diese Oberfläche zeigt nur die Auswahl. Nimm eine Oberfläche oben, dann öffnet sich „' + ((object || {}).title || (object || {}).type || '') + '“ dort.', 'note');
    },

    async decide(id, way){
      const out = await this.api('/api/decisions/answer', {method: 'POST', body: {id, way}});
      this.ctx.bus.emit('decision.answered', {id, kind: 'answered'});
      await Promise.all([this.decisions(), this.refresh()]);
      return out;
    }
  });
})();
