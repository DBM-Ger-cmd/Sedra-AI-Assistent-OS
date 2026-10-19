// Werkzeug „Werkstatt“ – the models: load, unload, test (COCKPIT_MODUL_v1 rule 3: the toolbar carries the verbs of the object).
// It writes nothing by itself: loading goes through the runtime's own route, every change of a recipe is a decision at the desk.
//
// Build 24 (Ticket B6-G-06, Klaus 15.10.2026: „keine Dummys“): zwei Abschnitte, die der Baum des Cockpits seit Build 7 versprach und die
// nur das alte SEDRA-XP-Fenster hatte (uix/js/model_add.js, standard_test.js) – hier mit denselben Routen des Servers:
//   Neues Modell   GGUF wählen (Dialog dieses PCs, Modellordner oder Pfad) → Datei lesen → Rezept prüfen → Freigabe als Entscheidung.
//                  Geschrieben wird erst nach der Freigabe (POST /api/model/add/request legt das Gate vor; das Anwenden ist die Antwort
//                  „freigeben und anwenden“ im Werkzeug Entscheidungen – derselbe Weg wie jede Änderung an role_routing.yaml).
//   Teststrecke    der Standardtest des geladenen Modells: Dauer und Kriterien wählen, starten, Fortschritt, Ergebnis; die Empfehlung
//                  wird als Änderungsantrag angelegt (POST /api/routing-config/request), nie direkt geschrieben.
// Das Objekt entscheidet, welcher Abschnitt offen ist: {type: model, id: neu} → Neues Modell, {id: teststrecke} → Teststrecke, sonst die Liste.
// `recipeLine`, `sectionFor`, `explainAddError`, `stdResultLines` sind rein und werden mit node geprüft.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const MODEL_ROLES = [['coder', 'Coder'], ['planner', 'Planer'], ['reviewer', 'Prüfer'], ['tester', 'Tester'], ['documentation', 'Doku'], ['verifier', 'Verifizierer']];
  const STD_DURATIONS = [['schnell', 'Schnell · 5 Min.'], ['standard', 'Standard · 15 Min.'], ['langzeit', 'Langzeit · 90 Min.']];
  const STD_CRITERIA = [['stabilitaet', 'Stabilität (Fehler, Abbrüche)'], ['tokens', 'Token-Geschwindigkeit'],
                        ['lesen_schreiben', 'Lesen und Schreiben (Textverarbeitung)'], ['coder', 'Coder-Leistung (kleine Programmieraufgaben)']];
  const POLL_MS = 5000;

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

  // which section the object opens (pure): the tree says „Modell hinzufügen“ or „Teststrecke“, the tool keeps that promise
  function sectionFor(object){
    const id = object && object.id;
    if(id === 'neu' || id === 'hinzufuegen') return 'neu';
    if(id === 'teststrecke' || id === 'standardtest') return 'teststrecke';
    return null;
  }

  // the server's error words, in the Captain's language (pure)
  function explainAddError(m){
    const s = String(m || '');
    if(s.includes('valid_gguf_model_required')) return 'Das ist keine GGUF-Datei (Endung .gguf) oder sie fehlt.';
    if(s.includes('gguf_magic_missing')) return 'Die Datei beginnt nicht wie eine GGUF-Datei; vermutlich unvollständig heruntergeladen.';
    if(s.includes('recipe_id_taken')) return 'Diese Rezept-ID gibt es schon; bitte eine andere wählen.';
    if(s.includes('recipe_id_invalid')) return 'Rezept-ID: kleinbuchstaben.kleinbuchstaben, z. B. coder.local_mein_modell';
    if(s.includes('absolute_path_required')) return 'Bitte den vollständigen Pfad zur GGUF-Datei angeben (z. B. D:\\Modelle\\x.gguf).';
    if(s.includes('path_not_found')) return 'Datei nicht gefunden.';
    if(s.includes('path_required')) return 'Bitte eine Datei wählen oder den Pfad eingeben.';
    if(s.includes('no_model_loaded')) return 'Kein Modell geladen. Erst oben ein Rezept laden, dann die Teststrecke starten.';
    if(s.includes('standard_test_running')) return 'Es läuft schon ein Standardtest.';
    if(s.includes('recipe_for_model_missing')) return 'Zum geladenen Modell gibt es kein Rezept; die Teststrecke braucht eins.';
    if(s.includes('criteria_required')) return 'Mindestens ein Kriterium wählen.';
    return s;
  }

  // the lines of a finished Standardtest (pure)
  function stdResultLines(out){
    return ((out || {}).results || []).map(r=>{
      if(r.status !== 'ok') return 'Kontext ' + r.context + ': nicht geladen';
      const parts = ['Kontext ' + r.context];
      if(r.tokens_per_s != null) parts.push(r.tokens_per_s + ' Token/s');
      if(r.read_per_s != null) parts.push(r.read_per_s + ' Token/s lesen');
      if(r.coder_pass != null) parts.push('Coder ' + Math.round(r.coder_pass * 100) + ' %');
      parts.push(r.stable ? 'stabil' : 'instabil (' + r.errors + ' Fehler)');
      return parts.join(' · ');
    });
  }

  const tool = {
    id: 'workshop',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-shop');
      this.section = sectionFor(ctx.object);
      this.add = {step: 'pick', path: '', browse: null, view: null, error: '', busy: false, roles: ['coder', 'planner', 'reviewer', 'tester'], recipeId: '', context: null, request: null};
      this.std = {duration: 'schnell', criteria: ['stabilitaet', 'tokens'], state: null, error: '', timer: null};
      this.offs = [];
      this.offs.push(ctx.bus.on('model.changed', ()=>this.refresh()));
      this.offs.push(ctx.bus.on('decision.answered', ()=>this.refresh()));
      return this.refresh();
    },

    unmount(){
      (this.offs || []).forEach(off=>{ try{ off(); }catch(_e){} });
      this.offs = [];
      if(this.std && this.std.timer){ clearInterval(this.std.timer); this.std.timer = null; }
      this.el.classList.remove('t-shop'); this.el.replaceChildren();
    },

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
      if(!view.loader_enabled) box.append(d().el('div', 's-note warn', 'Der Modell-Lader ist gerade nicht bereit. Ein Laden braucht keine Freigabe; die Einstellungen werden beim Start gelesen – nach einer Korrektur SEDRA neu starten.'));

      box.append(d().el('h5', 's-head', 'Rezepte'));
      (view.recipes || []).forEach(r=>{
        const zuletzt = !!view.zuletzt && view.zuletzt === r.id;      // das zuletzt geladene Modell ist die Vorgabe
        const row = d().el('div', 't-shop-row' + (r.loaded ? ' on' : '') + (zuletzt ? ' zuletzt' : ''));
        const head = d().el('div', 's-row');
        head.append(d().el('b', null, r.id));
        if(r.loaded) head.append(d().el('span', 's-note ok s-small', 'geladen'));
        if(zuletzt && !r.loaded) head.append(d().el('span', 's-note s-small', 'zuletzt verwendet'));
        row.append(head, d().el('small', 's-muted', recipeLine(r)));
        const verbs = d().el('div', 's-row');
        if(r.loaded){
          verbs.append(d().button('Entladen', ()=>this.ctx.api('/api/model/unload', {method: 'POST', body: {}}).then(()=>this.refresh())));
          verbs.append(d().button('Testen', ()=>this.test(r.id)));
        }else if(r.enabled && r.model && view.loader_enabled){
          verbs.append(d().button(zuletzt ? 'Laden (zuletzt)' : 'Laden', ()=>this.ctx.api('/api/model/load', {method: 'POST', body: {recipe_id: r.id}}).then(()=>this.refresh()), zuletzt ? 'p' : ''));
        }
        row.append(verbs);
        box.append(row);
      });
      if(!(view.recipes || []).length) box.append(d().empty('Noch kein Rezept. Unten „Neues Modell“: eine GGUF-Datei wird zum Rezept.'));
      this.out = d().el('div');
      box.append(this.out);

      // offene Freigaben zu Modellen – dieselbe Liste, die das Werkzeug Entscheidungen zeigt
      const open = (view.open_requests || []).filter(q=>q.kind === 'model_add' || q.kind === 'routing');
      if(open.length){
        const o = d().el('div', 's-note warn');
        o.append(d().el('span', null, open.length === 1 ? 'Eine Freigabe wartet: ' + ((open[0].binding || {}).describe || open[0].kind) + ' ' : open.length + ' Freigaben warten. '));
        o.append(d().button('Zu den Entscheidungen', ()=>this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true})));
        box.append(o);
      }

      // die beiden Abschnitte, die der Baum verspricht
      this.addBox = this.details('Neues Modell', 'GGUF-Datei wählen, Rezept prüfen, freigeben – dann laden und testen', this.section === 'neu', 'neu');
      this.stdBox = this.details('Teststrecke: Standardtest', 'mit welchem Kontext das geladene Modell am besten läuft', this.section === 'teststrecke', 'teststrecke');
      box.append(this.addBox.wrap, this.stdBox.wrap);
      this.el.replaceChildren(box);
      this.renderAdd();
      this.renderStd();
      if(this.section === 'neu' && !this.add.browse) this.browse('');
      if(!this.std.state) this.pollStd();
    },

    details(title, hint, open, key){
      const wrap = d().el('details', 't-shop-section');
      wrap.dataset.section = key;
      wrap.open = !!open;
      const sum = d().el('summary');
      sum.append(d().el('b', null, title), d().el('small', 's-muted', ' ' + hint));
      const body = d().el('div', 's-col t-shop-body');
      wrap.append(sum, body);
      wrap.addEventListener('toggle', ()=>{ if(wrap.open && key === 'neu' && !this.add.browse) this.browse(''); });
      return {wrap, body};
    },

    // ---- Neues Modell -------------------------------------------------------------------------------------------
    renderAdd(){
      const a = this.add, body = this.addBox.body;
      body.replaceChildren();
      if(a.error) body.append(d().el('div', 's-note bad', a.error));
      if(a.busy) body.append(d().el('div', 's-note', 'Bitte warten …'));
      if(a.step === 'pick'){
        body.append(d().el('div', 's-note', 'Schritt 1 von 3: GGUF-Datei wählen. Der Dialog öffnet sich auf diesem PC (Explorer bzw. Finder); alternativ aus dem Modellordner wählen oder den Pfad eingeben.'));
        const row = d().el('div', 's-row t-shop-form');
        const pick = d().button('Datei wählen …', ()=>this.pick(), 'p'); pick.disabled = a.busy;
        const input = d().el('input', 't-shop-input'); input.placeholder = 'oder vollständiger Pfad zur .gguf-Datei'; input.value = a.path;
        input.setAttribute('aria-label', 'Pfad zur GGUF-Datei');
        input.oninput = ()=>{ a.path = input.value; };
        input.onkeydown = e=>{ if(e.key === 'Enter' && a.path.trim()) this.inspect(); };
        const go = d().button('Prüfen', ()=>{ if(!a.path.trim()){ a.error = explainAddError('path_required'); this.renderAdd(); return; } return this.inspect(); });
        row.append(pick, input, go);
        body.append(row);
        const br = a.browse;
        if(br){
          if(!br.root) body.append(d().el('div', 's-note', br.note || 'Kein Modellordner eingetragen.'));
          else{
            const crumb = d().el('div', 't-shop-crumb');
            const rootA = d().el('a', null, 'Modellordner'); d().clickable(rootA, ()=>this.browse('')); crumb.append(rootA);
            const parts = br.path ? br.path.split('/') : [];
            parts.forEach((p, i)=>{ crumb.append(' / '); const link = d().el('a', null, p); d().clickable(link, ()=>this.browse(parts.slice(0, i + 1).join('/'))); crumb.append(link); });
            body.append(crumb);
            const list = d().el('div', 't-shop-files');
            (br.entries || []).forEach(e=>{
              const c = d().el('div', 't-shop-file' + (e.type === 'dir' ? ' dir' : ''));
              c.append(d().el('span', null, (e.type === 'dir' ? '📁 ' : '📄 ') + e.name));
              if(e.type === 'file') c.append(d().el('small', 's-muted', (e.size_gb == null ? '?' : e.size_gb) + ' GB'));
              d().clickable(c, ()=>{ if(e.type === 'dir') this.browse((br.path ? br.path + '/' : '') + e.name); else { a.path = e.path; this.inspect(); } });
              list.append(c);
            });
            if(!(br.entries || []).length) list.append(d().el('div', 's-muted', 'Hier liegen keine .gguf-Dateien.'));
            if(br.truncated) list.append(d().el('div', 's-muted', 'Liste gekürzt – bitte in einen Unterordner gehen oder den Pfad eingeben.'));
            body.append(list);
          }
        }
      }else if(a.step === 'inspect' && a.view){
        const v = a.view, info = v.info || {}, r = v.recipe;
        body.append(d().el('div', 's-note', 'Schritt 2 von 3: Rezept prüfen. Alles unten kommt aus der Datei selbst; Rezept-ID, Rollen und Kontext kannst du ändern.'));
        const facts = d().el('div', 't-shop-facts');
        [['Name', info.name || 'Modell'], ['Datei', info.path], ['Architektur', (info.architecture || '?') + (info.expert_count ? ' · MoE mit ' + info.expert_count + ' Experten' : '')],
         ['Quantisierung', info.quantization || '?'], ['Größe', info.size_gb + ' GB'], ['Kontext laut Datei', info.context_length || 'unbekannt'], ['Schichten', info.block_count || '?']]
          .forEach(([k, val])=>{ facts.append(d().el('span', 's-muted', k), d().el('span', null, String(val))); });
        body.append(facts);
        if(!v.in_models_root && v.models_root) body.append(d().el('div', 's-note warn', 'Die Datei liegt außerhalb des Modellordners (' + v.models_root + '). Das geht, aber die Modell-Quarantäne kennt sie dann nicht.'));
        const form = d().el('div', 't-shop-facts');
        const idIn = d().el('input', 't-shop-input'); idIn.value = a.recipeId; idIn.setAttribute('aria-label', 'Rezept-ID'); idIn.onchange = ()=>{ a.recipeId = idIn.value.trim(); };
        form.append(d().el('b', null, 'Rezept-ID'), idIn);
        const rolesBox = d().el('div', 's-row');
        MODEL_ROLES.forEach(([id, label])=>{
          const lab = d().el('label', 't-shop-check'); const cb = d().el('input'); cb.type = 'checkbox'; cb.checked = a.roles.includes(id);
          cb.onchange = ()=>{ a.roles = MODEL_ROLES.map(x=>x[0]).filter(x=>x === id ? cb.checked : a.roles.includes(x)); };
          lab.append(cb, ' ' + label); rolesBox.append(lab);
        });
        form.append(d().el('b', null, 'Rollen'), rolesBox);
        const ctx = d().el('select', 't-shop-input'); ctx.setAttribute('aria-label', 'Standard-Kontext');
        (r.profile.context.tiers || []).forEach(t=>{ const o = d().el('option', null, 'Kontext ' + t + (t === r.profile.context.maximum ? ' (Maximum der Datei)' : '')); o.value = String(t); ctx.append(o); });
        ctx.value = String(a.context); ctx.onchange = ()=>{ a.context = Number(ctx.value); };
        form.append(d().el('b', null, 'Standard-Kontext'), ctx);
        body.append(form);
        const det = d().el('details'); det.append(d().el('summary', null, 'Rezept, wie es in ' + v.overlay + ' geschrieben wird'));
        det.append(d().el('pre', 's-pre', v.yaml)); body.append(det);
        const row = d().el('div', 's-row');
        const req = d().button('Rezept anlegen (Freigabe)', ()=>this.request(), 'p'); req.disabled = a.busy || !a.roles.length;
        row.append(req, d().button('Neu berechnen', ()=>this.inspect()), d().button('Andere Datei', ()=>{ a.step = 'pick'; a.view = null; a.error = ''; this.renderAdd(); }));
        body.append(row);
      }else if(a.step === 'gate'){
        const b = (a.request || {}).binding || {};
        body.append(d().el('div', 's-note ok', 'Schritt 3 von 3: Die Freigabe liegt vor – ' + (b.describe || 'neues Rezept') + '. Genau dieser Block wird geschrieben, nichts sonst. Nach „freigeben und anwenden“ steht das Rezept oben in der Liste mit „Laden“, danach „Testen“.'));
        const row = d().el('div', 's-row');
        row.append(d().button('Zu den Entscheidungen', ()=>this.ctx.shell.open({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true}), 'p'),
                   d().button('Weiteres Modell', ()=>this.resetAdd()));
        body.append(row);
      }
    },

    async pick(){
      const a = this.add; a.busy = true; a.error = ''; this.renderAdd();
      try{
        const out = await this.ctx.api('/api/model/pick', {method: 'POST', body: {}});
        if(out.picked){ a.path = out.path; a.busy = false; return this.inspect(); }
        if(out.reason === 'no_dialog') a.error = 'Auf diesem PC gibt es keinen Dateidialog; bitte aus dem Modellordner wählen oder den Pfad eingeben.';
        else if(out.reason !== 'cancelled') a.error = 'Der Dateidialog ging nicht: ' + out.reason;
      }catch(err){ a.error = explainAddError(err.message); }
      a.busy = false; this.renderAdd();
    },

    async browse(sub){
      const a = this.add; a.busy = true; a.error = ''; this.renderAdd();
      try{ a.browse = await this.ctx.api('/api/model/browse', {method: 'POST', body: {path: sub || ''}}); }
      catch(err){ a.error = 'Ordner nicht lesbar: ' + explainAddError(err.message); }
      a.busy = false; this.renderAdd();
    },

    async inspect(){
      const a = this.add; a.busy = true; a.error = ''; this.renderAdd();
      try{
        const body = {path: a.path, roles: a.roles};
        if(a.recipeId) body.recipe_id = a.recipeId;
        if(a.context) body.context_recommended = a.context;
        a.view = await this.ctx.api('/api/model/inspect', {method: 'POST', body});
        a.recipeId = a.view.recipe.id; a.context = a.view.recipe.profile.context.recommended; a.step = 'inspect';
      }catch(err){ a.error = explainAddError(err.message); a.view = null; }
      a.busy = false; this.renderAdd();
    },

    async request(){
      const a = this.add; a.busy = true; a.error = ''; this.renderAdd();
      try{
        a.request = await this.ctx.api('/api/model/add/request', {method: 'POST', body: {path: a.path, roles: a.roles, recipe_id: a.recipeId, context_recommended: a.context}});
        a.step = 'gate';
        this.ctx.bus.emit('decision.pending', {id: 'request:' + a.request.mission_id, kind: 'request:model_add', title: (a.request.binding || {}).describe || ''});
      }catch(err){ a.error = explainAddError(err.message); }
      a.busy = false; this.renderAdd();
    },

    resetAdd(){
      Object.assign(this.add, {step: 'pick', path: '', view: null, error: '', busy: false, recipeId: '', context: null, request: null});
      this.renderAdd();
    },

    // ---- Teststrecke --------------------------------------------------------------------------------------------
    renderStd(){
      const s = this.std, body = this.stdBox.body;
      body.replaceChildren();
      body.append(d().el('div', 's-note', 'Findet heraus, mit welchem Kontext das geladene Modell am besten läuft. Das Modell wird dafür mehrfach neu geladen; danach steht es wieder mit dem Kontext, der übrig bleibt. Die Empfehlung wird nur als Freigabe angelegt.'));
      const loaded = ((this.view || {}).recipes || []).find(r=>r.loaded);
      if(!loaded) body.append(d().el('div', 's-note warn', 'Kein Modell geladen – die Teststrecke braucht eins. Oben ein Rezept laden.'));
      const form = d().el('div', 't-shop-facts');
      const dur = d().el('select', 't-shop-input'); dur.setAttribute('aria-label', 'Dauer');
      STD_DURATIONS.forEach(([v, label])=>{ const o = d().el('option', null, label); o.value = v; dur.append(o); });
      dur.value = s.duration; dur.onchange = ()=>{ s.duration = dur.value; };
      form.append(d().el('b', null, 'Dauer'), dur);
      const crit = d().el('div', 's-col');
      STD_CRITERIA.forEach(([v, label])=>{
        const lab = d().el('label', 't-shop-check'); const cb = d().el('input'); cb.type = 'checkbox'; cb.checked = s.criteria.includes(v);
        cb.onchange = ()=>{ s.criteria = STD_CRITERIA.map(x=>x[0]).filter(x=>x === v ? cb.checked : s.criteria.includes(x)); };
        lab.append(cb, ' ' + label); crit.append(lab);
      });
      form.append(d().el('b', null, 'Kriterien'), crit);
      body.append(form);
      if(s.error) body.append(d().el('div', 's-note bad', s.error));
      const st = s.state || {state: 'bereit'};
      if(st.state === 'läuft'){
        const last = (st.progress || []).slice(-1)[0] || {};
        body.append(d().el('div', 's-note', 'Läuft: Kontext ' + (last.context || '?') + ' (' + (last.state || '…') + ') · Dauer ' + (st.duration || '') + ' · Rezept ' + (st.recipe_id || '')));
      }
      if(st.state === 'fehler') body.append(d().el('div', 's-note bad', 'Der Standardtest ist fehlgeschlagen: ' + (st.error || 'unbekannt') + '.'));
      if(st.state === 'fertig' && st.result) body.append(this.stdResult(st.result));
      const go = d().button(st.state === 'läuft' ? 'Läuft …' : 'Standardtest starten', ()=>this.startStd(), 'p');
      go.disabled = st.state === 'läuft' || !s.criteria.length || !loaded;
      const goRow = d().el('div', 's-row'); goRow.append(go); body.append(goRow);
      if(st.state === 'läuft' && !s.timer) s.timer = setInterval(()=>this.pollStd(), POLL_MS);
      if(st.state !== 'läuft' && s.timer){ clearInterval(s.timer); s.timer = null; }
    },

    stdResult(out){
      const wrap = d().el('div', 't-shop-row');
      wrap.append(d().el('b', null, 'Ergebnis · ' + (out.recipe_id || '')));
      stdResultLines(out).forEach(t=>wrap.append(d().el('div', 's-muted', t)));
      const rec = out.recommendation || {};
      if(rec.context){
        wrap.append(d().el('div', 's-note ok', 'Empfehlung: Kontext ' + rec.context + ' (' + (rec.reason || '') + ')'));
        wrap.append(d().button('Empfehlung als Freigabe anlegen', async()=>{
          await this.ctx.api('/api/routing-config/request', {method: 'POST', body: {recipe_id: out.recipe_id, field: 'context_recommended', value: Number(rec.context)}});
          this.ctx.bus.emit('decision.pending', {id: 'request:routing', kind: 'request:routing', title: 'Kontext ' + rec.context + ' für ' + out.recipe_id});
          await this.refresh();
        }, 'p'));
      }else wrap.append(d().el('div', 's-note warn', rec.reason || 'Keine Empfehlung.'));
      return wrap;
    },

    async pollStd(){
      if(!this.el) return;
      try{ this.std.state = await this.ctx.api('/api/standard-test'); }
      catch(_e){ return; }
      if(this.stdBox) this.renderStd();
    },

    async startStd(){
      const s = this.std; s.error = '';
      try{ s.state = await this.ctx.api('/api/standard-test/start', {method: 'POST', body: {duration: s.duration, criteria: s.criteria}}); }
      catch(err){ s.error = explainAddError(err.message); }
      this.renderStd();
    },

    // ---- kurzer Test eines geladenen Rezepts (wie bisher) -------------------------------------------------------
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
      const out = [{label: 'Neues Modell', run: ()=>{ this.section = 'neu'; if(this.addBox){ this.addBox.wrap.open = true; this.addBox.wrap.scrollIntoView({block: 'nearest'}); } }}];
      if(!loaded) return out;
      return out.concat([{label: 'Entladen', run: ()=>this.ctx.api('/api/model/unload', {method: 'POST', body: {}}).then(()=>this.refresh())},
                         {label: 'Testen', run: ()=>this.test(loaded.id)}]);
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraWorkshopPure = {recipeLine, sectionFor, explainAddError, stdResultLines};
  if(typeof module !== 'undefined' && module.exports) module.exports = {recipeLine, sectionFor, explainAddError, stdResultLines, MODEL_ROLES, STD_DURATIONS, STD_CRITERIA};
})();
