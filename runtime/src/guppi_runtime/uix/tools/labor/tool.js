// Werkzeug „KI Labor“ (Cockpit, Werkstatt): Anbieter und Schlüssel, Modelle, Tests – die Kette an einem Ort.
// Jeder Test läuft auf Knopfdruck. Ein Schlüssel wird nie angezeigt. Die Tests lesen die gespeicherte Konfiguration.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const NVIDIA_SNAPSHOT_IDS = [
    'deepseek-ai/deepseek-v4.1-flash', 'google/diffusiongemma-26b-a4b-it', 'google/gemma-4-31b-it', 'meta/muse-glimmer-30b',
    'nvidia/cosmos3-nano', 'nvidia/cosmos3-nano-reasoner', 'nvidia/ising-calibration-1.5-31b', 'nvidia/kumo-tabular',
    'nvidia/kumo-relational', 'nvidia/nemotron-3-embed-1b', 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
    'nvidia/nemotron-3-ultra-550b-a55b', 'nvidia/nemotron-3.5-content-safety', 'nvidia/nemotron-3.5-lightning-30b-a3b',
    'nvidia/nemotron-3.5-super-vl-120b-a12b', 'nvidia/riva-translate-4b-instruct-v2', 'poolside/laguna-xs-2.1',
    'stepfun-ai/step-5-preview', 'z-ai/glm-5-3', 'z-ai/glm-5-3-flash', 'resemble-ai/chatterbox-multilingual'
  ];
  const KEY_TEXT = {
    umgebung: 'Schlüssel: aus der Umgebungsvariable (wird nicht angezeigt)',
    gespeichert: 'Schlüssel: verschlüsselt gespeichert',
    fehlt: 'Schlüssel: fehlt'
  };
  const TABS = [['anbieter', 'Anbieter und Schlüssel'], ['modelle', 'Modelle'], ['test', 'Tests'], ['laeufe', 'Läufe']];
  const RUN_STATUS = {finished: 'fertig', error: 'Fehler', turn_limit: 'Schrittlimit', stopped: 'gestoppt', blocked: 'gesperrt', off: 'aus', 'läuft': 'läuft'};

  const tool = {
    id: 'labor',
    tab: 'anbieter',
    models: {},          // Anbieter-Id -> Modell-Kennungen vom Anbieter
    modelsProvider: '',
    query: '',
    pubFilter: [],
    sortBy: 'name',
    page: 1,
    tests: {},           // Anbieter-Id -> Ergebnis des letzten Verbindungstests
    modelRuns: {},       // Anbieter-Id -> Ergebnis des letzten Modelltests
    running: '',         // was gerade läuft (für die Anzeige)
    runs: [],            // die Läufe aus den Protokollen (Tab „Läufe“)
    openRuns: {},        // „Art|Name“ -> offen (Details einer Karte sind aufgeklappt)

    mount(el, ctx){
      this.el = el; this.ctx = ctx; this.msg = '';
      el.classList.add('t-labor');
      this.timer = setInterval(()=>{ if(this.tab === 'laeufe') this.loadRuns(); }, 5000);   // die Läufe laufen weiter: alle 5 Sekunden neu lesen
      return this.refresh();
    },

    unmount(){ clearInterval(this.timer); this.el.classList.remove('t-labor'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let data;
      try{ data = await this.ctx.api('/api/cloud'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'KI Labor nicht lesbar: ' + err.message)); return; }
      this.data = data;
      this.draw();
    },

    draw(){
      const data = this.data || {};
      const box = d().el('div', 's-col labor-main');
      box.append(this.header(data));
      const bar = d().el('div', 's-row labor-tabs');
      TABS.forEach(([id, label])=>bar.append(d().button(label, ()=>{ this.tab = id; if(id === 'laeufe') this.loadRuns(); this.draw(); }, id === this.tab ? 'p' : undefined)));
      box.append(bar);
      if(this.tab === 'modelle') box.append(this.modelsView(data));
      else if(this.tab === 'test') box.append(this.testView(data));
      else if(this.tab === 'laeufe') box.append(this.runsView());
      else box.append(this.providersView(data));
      this.el.replaceChildren(box);
    },

    // ---- Tab 4: die Läufe. Jeder Lauf eine Karte, nebeneinander – man sieht sofort, was welches Modell tut
    async loadRuns(){
      try{ this.runs = (await this.ctx.api('/api/labor/runs')).runs || []; }
      catch(err){ this.runs = []; this.msg = 'Läufe nicht lesbar: ' + err.message; }
      if(this.tab === 'laeufe') this.draw();
    },

    runsView(){
      const box = d().el('div', 's-col');
      const head = d().el('div', 's-row');
      head.append(d().el('span', 's-small s-muted', this.runs.length + ' Läufe · alle 5 Sekunden aktualisiert'), d().button('Jetzt aktualisieren', ()=>this.loadRuns()));
      box.append(head);
      if(!this.runs.length) box.append(d().el('div', 's-small s-muted', 'Noch keine Läufe.'));
      const grid = d().el('div', 'labor-grid');
      this.runs.forEach(r=>grid.append(this.runCard(r)));
      box.append(grid);
      return box;
    },

    // Jede Karte klappt für sich auf: die Details stehen in ihrer eigenen Box, die dann die ganze Breite nimmt
    runCard(r){
      const key = r.kind + '|' + r.name;
      const open = !!(this.openRuns || {})[key];
      const card = d().el('div', 'labor-model' + (open ? ' is-default' : ''));
      if(open) card.style.gridColumn = '1 / -1';
      const tone = r.status === 'finished' ? 'ok' : (r.status === 'läuft' ? '' : 'warn');
      card.append(d().el('div', 'labor-pub', r.kind + ' · ' + r.name), d().el('div', 'labor-name', r.model || '(kein Modell)'));
      card.append(d().el('span', 'labor-badge ' + tone, RUN_STATUS[r.status] || r.status), d().el('span', 'labor-badge', r.calls + ' Aufrufe'), d().el('span', 'labor-badge', r.writes.length + ' Dateien'));
      if(r.blocked) card.append(d().el('span', 'labor-badge warn', r.blocked + ' gesperrt'));
      card.append(d().el('div', 's-small s-muted', 'zuletzt: ' + r.last), d().button(open ? 'Details zuklappen' : 'Details', ()=>{ this.openRuns = {...(this.openRuns || {}), [key]: !open}; this.draw(); }));
      if(open){
        card.append(d().el('div', 's-small', 'Erlaubt: ' + (r.allow.join(', ') || '–')));
        if(r.detail) card.append(d().el('div', 's-small warn', 'Grund: ' + r.detail));
        if(r.writes.length){ const list = d().el('ul', 'labor-steps'); r.writes.forEach(w=>list.append(d().el('li', null, w))); card.append(list); }
        else card.append(d().el('div', 's-small s-muted', 'Noch keine geschriebene Datei.'));
      }
      return card;
    },

    // Kopf: der Gesamtzustand in einem Satz, wie die Statusleiste der Vorlage
    header(data){
      const live = data.live || [];
      const on = data.enabled;
      const text = !on ? 'Cloud ist AUS. Kein Anbieter wird genutzt.'
        : live.length ? 'Aktiv: ' + live.join(', ') + '. Im laufenden Server bereit.'
        : 'Eingeschaltet, aber im laufenden Server noch kein Anbieter. Nach dem Neustart wirksam.';
      const row = d().el('div', 's-row labor-head');
      row.append(d().el('span', 'labor-dot ' + (on && live.length ? 'ok' : 'off')), d().el('b', null, 'KI Labor'), d().el('span', 's-small s-muted', ' ' + text));
      return row;
    },

    // ---- Tab 1: Anbieter, Schlüssel, Status
    providersView(data){
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note', 'Was den Rechner verlässt, prüft der Inhaltsschutz bei jedem Aufruf. Personenbezug wird vor dem Versand pseudonymisiert und anonymisiert.'));
      if(data.restart_needed) box.append(d().el('div', 's-note warn', 'Gespeichert, aber noch nicht wirksam: Neustart der Oberfläche nötig.'));
      const master = d().el('label', 's-field');
      const masterBox = d().el('input'); masterBox.type = 'checkbox'; masterBox.id = 'laborMaster'; masterBox.checked = !!data.enabled;
      master.append(masterBox, ' Cloud-Modelle insgesamt einschalten');
      box.append(master);
      // Speichern direkt oben, damit man es nach dem Ändern nicht suchen muss (gilt für alle Anbieter darunter)
      box.append(d().button('Einstellungen speichern', ()=>this.save(), 'p'), d().el('div', 's-small s-muted', this.msg));
      for(const p of data.providers || []){
        const card = d().el('div', 'labor-card s-provider');
        card.dataset.provider = p.id;
        card.append(d().el('div', 's-head', p.id + ' · ' + (p.kind === 'anthropic' ? 'Anthropic Messages API' : 'OpenAI-kompatibel')));
        let status = p.status === 'bereit' ? 'bereit' : p.status === 'nicht bereit' ? 'nicht bereit – ' + p.reasons.join(', ') : 'aus';
        if(p.status === 'bereit') status += p.live ? ' · läuft jetzt' : ' · läuft nach dem nächsten Start';
        card.append(d().el('span', 'labor-badge ' + (p.status === 'bereit' ? 'ok' : p.status === 'nicht bereit' ? 'warn' : ''), 'Status: ' + status));
        const on = d().el('label', 's-field'); const onBox = d().el('input'); onBox.type = 'checkbox'; onBox.className = 'cp-enabled'; onBox.checked = !!p.enabled;
        on.append(onBox, ' Anbieter aktiv'); card.append(on);
        const url = d().el('input'); url.type = 'text'; url.className = 'cp-url'; url.value = p.base_url; url.maxLength = 200;
        card.append(d().el('label', 's-field', 'Adresse (https)'), url);
        card.append(d().el('div', 's-small s-muted', KEY_TEXT[p.key] || ''));
        if(p.key_store_available){
          const pw = d().el('input'); pw.type = 'password'; pw.className = 'cp-key'; pw.autocomplete = 'off'; pw.placeholder = 'Neuer API-Schlüssel';
          const save = d().button('Schlüssel speichern', ()=>this.saveKey(p.id, pw.value));
          const del = d().button('Schlüssel löschen', ()=>this.clearKey(p.id));
          card.append(pw, save, del);
        } else {
          card.append(d().el('div', 's-small s-muted', 'Die verschlüsselte Ablage läuft nur unter Windows. Hier bleibt die Umgebungsvariable GUPPI_SECRET_' + p.id.toUpperCase().replace(/-/g, '_') + '_API_KEY.'));
        }
        box.append(card);
      }
      return box;
    },

    // ---- Tab 2: Modellkatalog, Vorbild build.nvidia.com: Filterspalte, Suche, Sortierung, Karten, Seiten
    // Welches Modell ein Modul nutzt: Gespräch und Redesign-Lauf (Zuordnung in der Konfiguration, module_models)
    moduleBlock(data){
      const box = d().el('div', 'labor-card');
      box.append(d().el('div', 's-head', 'Module und ihr Modell'));
      const current = data.module_models || {};
      const options = [];
      (data.providers || []).forEach(p=>{
        if(p.status !== 'bereit') return;
        [...new Set([p.default_model, ...(this.models[p.id] || [])].filter(Boolean))].forEach(m=>options.push({provider: p.id, model: m}));
      });
      [['chat', 'Gespräch (Vorgabe neben Senden)'], ['redesign', 'Redesign-Lauf']].forEach(([mod, label])=>{
        const row = d().el('div', 's-row');
        const sel = d().el('select');
        const none = d().el('option', null, '(keins)'); none.value = ''; sel.append(none);
        options.forEach(o=>{ const op = d().el('option', null, o.provider + ' · ' + o.model); op.value = o.provider + '|' + o.model; sel.append(op); });
        const cur = current[mod];
        if(cur && cur.provider && cur.model){
          const value = cur.provider + '|' + cur.model;
          if(![...sel.options].some(o=>o.value === value)){ const op = d().el('option', null, cur.provider + ' · ' + cur.model); op.value = value; sel.append(op); }
          sel.value = value;
        }
        sel.onchange = ()=>this.setModule(mod, sel.value);
        row.append(d().el('span', 's-small', label), sel);
        box.append(row);
      });
      return box;
    },

    async setModule(mod, value){
      const body = value ? {module: mod, provider: value.split('|')[0], model: value.slice(value.indexOf('|') + 1)} : {module: mod, provider: null};
      try{
        await this.ctx.api('/api/cloud/module-model', {method: 'POST', body: JSON.stringify(body)});
        this.msg = mod + ': ' + (value ? value.replace('|', ' · ') : 'keins Modell') + ' gespeichert.';
      }catch(err){ this.msg = 'Nicht gespeichert: ' + err.message; }
      await this.refresh();
    },

    modelsView(data){
      const box = d().el('div', 's-col');
      box.append(this.moduleBlock(data));
      const providers = data.providers || [];
      const pid = this.modelsProvider || (providers.find(p=>p.key !== 'fehlt') || providers[0] || {}).id;
      this.modelsProvider = pid;
      const prov = providers.find(p=>p.id === pid) || {};

      const bar = d().el('div', 's-row labor-bar');
      const pick = d().el('select');
      providers.forEach(p=>{ const o = d().el('option', null, p.id + ' · ' + p.status); o.value = p.id; pick.append(o); });
      pick.value = pid;
      pick.onchange = ()=>{ this.modelsProvider = pick.value; this.page = 1; this.draw(); };
      const search = d().el('input'); search.type = 'search'; search.placeholder = 'Modell suchen …'; search.value = this.query;
      search.oninput = ()=>{ this.query = search.value; this.page = 1; this.draw(); };
      const sort = d().el('select');
      [['name', 'Name A–Z'], ['anbieter', 'Anbieter']].forEach(([v, t])=>{ const o = d().el('option', null, t); o.value = v; sort.append(o); });
      sort.value = this.sortBy;
      sort.onchange = ()=>{ this.sortBy = sort.value; this.page = 1; this.draw(); };
      bar.append(pick, d().button('Modelle abfragen', ()=>this.fetchModels(pid)), search, sort);
      box.append(bar);

      const cols = d().el('div', 'labor-cols');
      const aside = d().el('aside', 'labor-aside');
      const main = d().el('div', 'labor-main-col');
      cols.append(aside, main);
      box.append(cols);

      const live = this.models[pid] || null;
      const list = live || (pid === 'nvidia' ? NVIDIA_SNAPSHOT_IDS : []);
      let source;
      if(prov.key === 'fehlt') source = 'Ohne Schlüssel kann SEDRA nichts abfragen. Den Schlüssel trägst du unter „Anbieter und Schlüssel“ ein.';
      else if(live) source = list.length + ' Modelle, vom Anbieter abgefragt.';
      else if(pid === 'nvidia') source = 'Vorschlag von der NVIDIA-Seite (16.10.2026), nicht live geprüft. „Modelle abfragen“ holt die echte Liste.';
      else source = 'Noch nicht abgefragt – „Modelle abfragen“.';
      main.append(d().el('div', 's-small ' + (live ? 'ok' : 'warn'), source));

      const pubs = {};
      list.forEach(id=>{ const p = id.split('/')[0]; pubs[p] = (pubs[p] || 0) + 1; });
      aside.append(d().el('div', 'labor-head-small', 'Anbieter (' + Object.keys(pubs).length + ')'));
      Object.keys(pubs).sort().forEach(p=>{
        const row = d().el('label', 'labor-facet');
        const cb = d().el('input'); cb.type = 'checkbox'; cb.checked = this.pubFilter.includes(p);
        cb.onchange = ()=>{ this.pubFilter = cb.checked ? [...this.pubFilter, p] : this.pubFilter.filter(x=>x !== p); this.page = 1; this.draw(); };
        row.append(cb, ' ' + p + ' · ' + pubs[p]);
        aside.append(row);
      });

      const q = this.query.trim().toLowerCase();
      let shown = list.filter(id=>(!q || id.toLowerCase().includes(q)) && (!this.pubFilter.length || this.pubFilter.includes(id.split('/')[0])));
      shown = this.sortBy === 'anbieter' ? shown.sort((a, b)=>a.localeCompare(b)) : shown.sort((a, b)=>a.split('/').pop().localeCompare(b.split('/').pop()));
      main.append(d().el('div', 's-small s-muted', shown.length + ' Modelle'));

      const PER = 12, pages = Math.max(1, Math.ceil(shown.length / PER));
      this.page = Math.min(this.page, pages);
      const grid = d().el('div', 'labor-grid');
      shown.slice((this.page - 1) * PER, this.page * PER).forEach(id=>grid.append(this.modelCard(pid, id, prov, !!live)));
      main.append(grid);
      if(pages > 1){
        const pager = d().el('div', 's-row labor-pager');
        const prev = d().button('‹', ()=>{ this.page -= 1; this.draw(); }); prev.disabled = this.page <= 1;
        const next = d().button('›', ()=>{ this.page += 1; this.draw(); }); next.disabled = this.page >= pages;
        pager.append(prev, d().el('span', 's-small', 'Seite ' + this.page + ' von ' + pages), next);
        main.append(pager);
      }
      if(!shown.length && list.length) main.append(d().el('div', 's-small s-muted', 'Kein Modell passt zur Suche oder zum Filter.'));
      if(this.msg) main.append(d().el('div', 's-small s-muted', this.msg));
      return box;
    },

    modelCard(pid, id, prov, isLive){
      const slash = id.indexOf('/');
      const card = d().el('div', 'labor-model' + (prov.default_model === id ? ' is-default' : ''));
      card.append(d().el('div', 'labor-pub', slash > 0 ? id.slice(0, slash) : ''), d().el('div', 'labor-name', slash > 0 ? id.slice(slash + 1) : id));
      const badges = d().el('div');
      if(!isLive && pid === 'nvidia') badges.append(d().el('span', 'labor-badge ok', 'Free Endpoint'));
      badges.append(d().el('span', 'labor-badge', isLive ? 'vom Anbieter' : 'Vorschlag'));
      if(prov.default_model === id) badges.append(d().el('span', 'labor-badge ok', 'Standard'));
      card.append(badges);
      const take = d().button(prov.default_model === id ? 'Ist der Standard' : 'Als Standard nehmen', ()=>this.setDefault(pid, id));
      take.disabled = prov.default_model === id;
      card.append(take);
      return card;
    },

    // ---- Tab 3: Tests. Verbindung in Schritten, und alle Modelle einmal
    testView(data){
      const box = d().el('div', 's-col');
      box.append(d().el('div', 's-note', 'Die Tests lesen die gespeicherte Konfiguration. Ist der Hauptschalter oder der Anbieter aus, wird nichts gesendet. Jeder Test kostet Anbieter-Tokens und läuft nur auf Klick.'));
      if(this.running) box.append(d().el('div', 's-note warn', this.running));
      for(const p of data.providers || []){
        const card = d().el('div', 'labor-card');
        card.append(d().el('div', 's-head', p.id));
        const row = d().el('div', 's-row');
        row.append(d().button('Verbindung testen', ()=>this.connectionTest(p.id)), d().button('Alle Modelle testen', ()=>this.modelTest(p.id)));
        card.append(row);
        if(this.tests[p.id]) card.append(this.stepsView(this.tests[p.id]));
        if(this.modelRuns[p.id]) card.append(this.runView(this.modelRuns[p.id]));
        box.append(card);
      }
      return box;
    },

    stepsView(res){
      const list = d().el('ol', 'labor-steps');
      res.steps.forEach(s=>{
        const li = d().el('li', s.ok ? 'ok' : 'warn', (s.ok ? '✓ ' : '✗ ') + s.step + ' – ' + (s.detail || '') + (s.ms ? ' (' + s.ms + ' ms)' : ''));
        list.append(li);
      });
      return list;
    },

    runView(res){
      const box = d().el('div', 's-col');
      if(res.total === undefined) { box.append(d().el('div', 's-note warn', res.detail || 'Kein Ergebnis.')); return box; }
      box.append(d().el('div', 's-note ' + (res.ok ? 'ok' : 'warn'), res.passed + ' von ' + res.total + ' Modellen haben geantwortet.'));
      const table = d().el('table', 's-table');
      res.results.forEach(r=>{
        const tr = d().el('tr', r.ok ? 'ok' : 'warn');
        tr.append(d().el('td', null, r.model), d().el('td', null, r.ok ? 'OK' : 'Fehler'), d().el('td', 's-small', (r.ok ? (r.reply || '') : r.detail) + (r.ms ? ' · ' + r.ms + ' ms' : '')));
        table.append(tr);
      });
      box.append(table);
      return box;
    },

    async connectionTest(pid){
      this.running = 'Verbindung zu ' + pid + ' wird geprüft …'; this.draw();
      try{ this.tests[pid] = await this.ctx.api('/api/labor/connection', {method: 'POST', body: JSON.stringify({provider: pid})}); }
      catch(err){ this.tests[pid] = {ok: false, steps: [{step: 'Test', ok: false, detail: err.message}]}; }
      this.running = ''; this.tab = 'test'; this.draw();
    },

    async modelTest(pid){
      this.running = 'Alle Modelle von ' + pid + ' werden einzeln angesprochen. Das kann einige Minuten dauern …'; this.draw();
      try{ this.modelRuns[pid] = await this.ctx.api('/api/labor/models-test', {method: 'POST', body: JSON.stringify({provider: pid})}); }
      catch(err){ this.modelRuns[pid] = {ok: false, detail: err.message}; }
      this.running = ''; this.tab = 'test'; this.draw();
    },

    collect(){
      const providers = {};
      this.el.querySelectorAll('.s-provider, .labor-card[data-provider]').forEach(card=>{
        if(!card.dataset.provider) return;
        providers[card.dataset.provider] = {
          enabled: card.querySelector('.cp-enabled').checked,
          base_url: card.querySelector('.cp-url').value.trim()
        };
      });
      const master = this.el.querySelector('#laborMaster');
      return {enabled: master ? master.checked : !!(this.data || {}).enabled, providers};
    },

    async save(){
      try{
        await this.ctx.api('/api/cloud/save', {method: 'POST', body: JSON.stringify(this.collect())});
        this.msg = 'Gespeichert. Die Tests lesen das sofort; der laufende Server braucht für Anrufe den Neustart.';
      }catch(err){ this.msg = 'Nicht gespeichert: ' + err.message; }
      await this.refresh();
    },

    async setDefault(pid, id){
      try{
        await this.ctx.api('/api/cloud/save', {method: 'POST', body: JSON.stringify({enabled: !!(this.data || {}).enabled, providers: {[pid]: {default_model: id}}})});
        this.msg = id + ' ist jetzt das Standardmodell von ' + pid + '.';
      }catch(err){ this.msg = 'Nicht gespeichert: ' + err.message; }
      await this.refresh();
    },

    async fetchModels(pid){
      this.msg = 'Modelle werden beim Anbieter abgefragt …'; this.draw();
      try{
        const out = await this.ctx.api('/api/cloud/models', {method: 'POST', body: JSON.stringify({provider: pid})});
        this.models[pid] = out.models;
        this.msg = out.models.length ? out.models.length + ' Modelle von ' + pid + ' geladen.' : 'Der Anbieter meldet keine Modelle für diesen Schlüssel.';
      }catch(err){ this.msg = 'Modelle nicht abgefragt: ' + err.message; }
      await this.refresh();
    },

    async saveKey(provider, value){
      try{
        await this.ctx.api('/api/cloud/key', {method: 'POST', body: JSON.stringify({provider, value})});
        this.msg = 'Schlüssel für ' + provider + ' verschlüsselt gespeichert.';
      }catch(err){ this.msg = 'Schlüssel nicht gespeichert: ' + err.message; }
      await this.refresh();
    },

    async clearKey(provider){
      try{
        await this.ctx.api('/api/cloud/key', {method: 'POST', body: JSON.stringify({provider, clear: true})});
        this.msg = 'Schlüssel für ' + provider + ' gelöscht.';
      }catch(err){ this.msg = 'Nicht gelöscht: ' + err.message; }
      await this.refresh();
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
