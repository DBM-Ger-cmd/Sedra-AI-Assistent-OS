// Werkzeug „Entwurf“ (Cockpit, Werkstatt): links das Gespräch mit einem Cloud-Modell, rechts die Vorschau des Entwurfs.
// Die Antworten werden nur als Text gezeigt. Eine HTML-Seite aus dem Codeblock läuft erst in der Vorschau, in einem isolierten
// Rahmen (sandbox ohne Zugriff auf die Oberfläche). Gespeichert wird im Entwurfsordner, nie im Live-Code.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const GUIDE = ('Du hilfst beim Entwerfen von Webseiten und Figuren für SEDRA (reines HTML, CSS und JavaScript, Three.js über ' +
    'cdn.jsdelivr.net). Wenn du eine Vorschau willst, antworte mit genau einem vollständigen HTML-Dokument in einem Codeblock, ' +
    'der mit ```html beginnt. Schreibe davor höchstens drei kurze Sätze, was du gemacht hast. Keine anderen Netzadressen. ' +
    'Als Vorarbeiter darfst du diese Aktionen auslösen, indem du einen Codeblock mit ```vorarbeiter und einem JSON-Objekt schreibst: ' +
    '{"aktion": "lauf_status"} · {"aktion": "lauf_starten", "args": {"lauf": "shells" | "spec" | "pipeline" | "<eigener Name>"}} · ' +
    '{"aktion": "rendern", "args": {"ordner": "workbench", "datei": "<name>.scad"}} · ' +
    '{"aktion": "lauf_anlegen","args": {"name": "…", "art": "bewerten" | "bauen", "lab": "…", "model": "…", "task": "…", "allow": ["…"], "outputs": ["…"]}}. ' +
    'Bevor du einen Lauf anlegst, frage im Gespräch nach, was fehlt: wo gearbeitet und gespeichert werden soll (Ordner unter redesign/), ' +
    'welche Dateien geschrieben werden dürfen und was am Ende herauskommen soll. Erfinde keinen Ordner und keinen Modellnamen. ' +
    '{"aktion": "pruefen", "args": {"ordner": "drache_lab" | "paperclip_lab"}}. Sonst nichts Weiteres.');
  const AMPEL_ZEICHEN = {gruen: '✓ schnell', gelb: '◐ langsam', rot: '✗ antwortet nicht', grau: '○ ungeprüft'};
  const CODE = /```html\s*([\s\S]*?)```/;
  const ACTION = /```vorarbeiter\s*([\s\S]*?)```/;

  const tool = {
    id: 'entwurf',
    history: [],
    models: [],        // {value, label} aus den bereiten Anbietern
    drafts: [],
    current: '',       // Name des gezeigten Entwurfs

    mount(el, ctx){
      this.el = el; this.ctx = ctx; this.history = []; this.current = '';
      el.classList.add('t-entwurf');
      const left = d().el('section', 'et-chat');
      this.log = d().el('div', 'et-log');
      this.log.setAttribute('role', 'log');
      this.picker = d().el('select', 'et-pick');
      this.picker.setAttribute('aria-label', 'Modell für den Entwurf');
      const first = d().el('option', null, 'GUPPI lokal'); first.value = 'local';
      this.picker.append(first);
      this.input = d().el('textarea', 'et-input');
      this.input.placeholder = 'Beschreibe, was du sehen willst · Strg+Enter sendet';
      this.input.setAttribute('aria-label', 'Nachricht an das Modell');
      this.input.onkeydown = e=>{ if(e.key === 'Enter' && (e.ctrlKey || e.metaKey)){ e.preventDefault(); this.send(); } };
      const row = d().el('div', 'et-row');
      const vorschau = d().button('Vorschau aus', ()=>{
        const aus = el.classList.toggle('et-ohne-vorschau');
        vorschau.textContent = aus ? 'Vorschau ein' : 'Vorschau aus';
      });
      const seiten = d().button('Seiten tauschen', ()=>el.classList.toggle('et-getauscht'));
      const blasen = d().button('Ohne Blasen', ()=>{
        const aus = el.classList.toggle('et-ohne-blasen');
        blasen.textContent = aus ? 'Mit Blasen' : 'Ohne Blasen';
      });
      this.ampel = d().el('span', 'et-ampel aus');
      this.picker.addEventListener('change', ()=>this.ampelZeigen());
      this.gruen = d().button('Grüne zuerst', ()=>this.gruenZeigen());
      row.append(this.picker, this.ampel, this.gruen, d().button('Senden', ()=>this.send(), 'p'), d().button('Neu beginnen', ()=>this.reset()), vorschau, seiten, blasen);
      left.append(this.log, this.input, row);

      const right = d().el('section', 'et-preview');
      this.drafts = d().el('select', 'et-drafts');
      this.drafts.setAttribute('aria-label', 'gespeicherte Entwürfe');
      this.drafts.onchange = ()=>this.open(this.drafts.value);
      this.frame = d().el('iframe', 'et-frame');
      this.frame.setAttribute('sandbox', 'allow-scripts');
      this.frame.setAttribute('title', 'Vorschau des Entwurfs');
      right.append(d().el('div', 'et-bar', null), this.frame);
      right.firstChild.append(d().el('b', 'et-titel', 'Vorschau Fenster'), this.drafts, d().button('Aktualisieren', ()=>this.listDrafts()));
      left.prepend(d().el('div', 'et-kopf', 'Chat Fenster'));
      el.replaceChildren(right, left);

      this.say('Schreib, was du entwerfen willst. Ich antworte im Gespräch; eine Seite erscheint rechts in der Vorschau.', 'note');
      this.loadModels();
      this.listDrafts();
    },

    unmount(){ this.el.classList.remove('t-entwurf'); this.el.replaceChildren(); },

    line(who, text, tone){
      const row = d().el('p', 'et-line' + (tone ? ' ' + tone : ''));
      row.append(d().el('b', null, who), d().el('span', null, ' ' + text));
      this.log.append(row);
      this.log.scrollTop = this.log.scrollHeight;
      return row;
    },

    say(text, tone){ this.line('GUPPI', text, tone === 'warn' ? 'warn' : 'note'); },

    reset(){ this.history = []; this.log.replaceChildren(); this.say('Neues Gespräch. Was soll entstehen?', 'note'); },

    // Die bereiten Cloud-Modelle in die Auswahl (wie im Gespräch). Ohne Cloud bleibt die Auswahl leer.
    async loadModels(){
      try{
        const v = await this.ctx.api('/api/cloud');
        if(!v.enabled) return this.say('Die Cloud ist aus. Für den Entwurf erst in der KI Labor einschalten.', 'warn');
        for(const p of v.providers || []){
          if(p.status !== 'bereit') continue;
          let list = [], zust = {};
          try{ const r = await this.ctx.api('/api/cloud/models', {method: 'POST', body: {provider: p.id}}); list = (r.models || []).slice(); zust = r.zustand || {}; }
          catch(_err){ list = []; }
          if(p.default_model && !list.includes(p.default_model)) list.unshift(p.default_model);
          if(!list.length) continue;
          const group = d().el('optgroup'); group.label = p.id;
          list.forEach(id=>{
            const a = (zust[id] || {}).ampel || 'grau';
            const o = d().el('option', null, id + '  ' + AMPEL_ZEICHEN[a]); o.value = 'cloud:' + p.id + '|' + id; o.dataset.ampel = a;
            group.append(o);
          });
          this.picker.append(group);
        }
        const pre = (v.module_models || {}).chat;
        if(pre && pre.provider && pre.model) this.picker.value = 'cloud:' + pre.provider + '|' + pre.model;
        this.ampelZeigen();
      }catch(err){ this.say('Modelle nicht lesbar: ' + err.message, 'warn'); }
    },

    // Schalter „Grüne zuerst“: oben in der Auswahl eine Gruppe mit allen grünen Modellen (gleiche Werte, also gleiche Wahl)
    gruenZeigen(){
      this.gruenZuerst = !this.gruenZuerst;
      this.gruen.textContent = this.gruenZuerst ? 'Grüne: an' : 'Grüne zuerst';
      this.picker.querySelectorAll('optgroup[data-kandidaten]').forEach(g=>g.remove());
      if(!this.gruenZuerst) return;
      const gruen = [...this.picker.options].filter(o=>o.dataset.ampel === 'gruen');
      if(!gruen.length){ this.say('Noch kein grünes Modell: erst eins benutzen oder im KI Labor testen.', 'note'); return; }
      const group = d().el('optgroup'); group.label = 'Grüne Kandidaten'; group.dataset.kandidaten = '1';
      gruen.forEach(o=>{ const c = d().el('option', null, o.textContent); c.value = o.value; c.dataset.ampel = 'gruen'; group.append(c); });
      this.picker.insertBefore(group, this.picker.children[1] || null);
    },

    // der Punkt zeigt den Zustand des gewählten Modells; bei „GUPPI lokal“ bleibt er aus
    ampelZeigen(){
      if(!this.ampel) return;
      const o = this.picker.selectedOptions && this.picker.selectedOptions[0];
      if(!this.picker.value || !o){ this.ampel.className = 'et-ampel aus'; this.ampel.title = 'GUPPI lokal'; return; }
      const a = o.dataset.ampel || 'grau';
      this.ampel.className = 'et-ampel ' + a;
      this.ampel.title = AMPEL_ZEICHEN[a] || AMPEL_ZEICHEN.grau;
    },

    async send(){
      const text = this.input.value.trim();
      this.input.value = '';
      if(!text) return;
      const local = this.picker.value === 'local' || !this.picker.value;
      const who = local ? 'GUPPI lokal' : this.picker.value.slice('cloud:'.length).replace('|', ' / ');
      this.line('Du', text, 'me');
      if(!this.history.length) this.history.push({role: 'user', content: GUIDE}, {role: 'assistant', content: 'Verstanden.'});
      this.history.push({role: 'user', content: text});
      const row = this.line(who, 'denkt nach …', 'note');
      try{
        let out;
        if(local) out = await this.ctx.api('/api/chat/reply', {method: 'POST', body: {mission_id: '', text, history: this.history.slice(0, -1), attachments: [], vorgang: ''}});
        else{
          const [pid, model] = this.picker.value.slice('cloud:'.length).split('|');
          out = await this.ctx.api('/api/chat/cloud', {method: 'POST', body: {provider: pid, model, text, history: this.history.slice(0, -1)}});
        }
        row.remove();
        const ok = local ? out.status === 'completed' : out.status === 'completed';
        if(!ok){ this.history.pop(); return this.say('Nicht beantwortet: ' + ((out.reasons || []).join(', ') || out.message || out.status), 'warn'); }
        const reply = out.reply || '';
        this.history.push({role: 'assistant', content: reply});
        const match = CODE.exec(reply);
        const prose = reply.replace(ACTION, '').replace(match ? match[0] : '', match ? '[Vorschau-Code – siehe rechts]' : '').trim();
        this.line(who, prose, '');
        if(match) this.offerPreview(match[1]);
        const act = ACTION.exec(reply);
        if(act) await this.runAction(act[1]);
      }catch(err){ this.history.pop(); row.remove(); this.say('Fehler: ' + err.message, 'warn'); }
    },

    // Vorarbeiter-Aktion aus der Antwort: feste Liste, Ergebnis im Gespräch
    async runAction(json){
      let req;
      try{ req = JSON.parse(json); }catch(_err){ return this.say('Aktion nicht lesbar.', 'warn'); }
      try{
        const out = await this.ctx.api('/api/vorarbeiter/aktion', {method: 'POST', body: {aktion: req.aktion, args: req.args || {}}});
        this.say('Aktion ' + req.aktion + ': ' + JSON.stringify(out).slice(0, 600), 'note');
      }catch(err){ this.say('Aktion ' + req.aktion + ' abgelehnt: ' + err.message, 'warn'); }
    },

    offerPreview(code){
      const btn = d().button('In Vorschau zeigen', ()=>this.preview(code), 'p');
      const wrap = d().el('div', 'et-offer');
      wrap.append(btn);
      this.log.append(wrap);
      this.log.scrollTop = this.log.scrollHeight;
    },

    // Speichern im Entwurfsordner und sofort zeigen (die Vorschau hat keinen Zugriff auf die Oberfläche)
    async preview(code){
      try{
        const saved = await this.ctx.api('/api/entwurf/save', {method: 'POST', body: {content: code, ext: 'html'}});
        this.current = saved.name;
        this.frame.srcdoc = code;
        await this.listDrafts();
        this.say('Vorschau: ' + saved.name + ' (gespeichert).', 'note');
      }catch(err){ this.say('Vorschau nicht gespeichert: ' + err.message, 'warn'); }
    },

    async listDrafts(){
      try{
        const out = await this.ctx.api('/api/entwurf/list', {method: 'POST', body: {}});
        this.drafts.replaceChildren();
        const none = d().el('option', null, 'gespeicherte Entwürfe'); none.value = ''; this.drafts.append(none);
        (out.entwuerfe || []).forEach(n=>{ const o = d().el('option', null, n); o.value = n; this.drafts.append(o); });
        this.drafts.value = this.current || '';
      }catch(_err){ /* ohne Liste bleibt die Vorschau nutzbar */ }
    },

    async open(name){
      if(!name) return;
      try{
        const out = await this.ctx.api('/api/entwurf/read', {method: 'POST', body: {name}});
        this.current = name;
        this.frame.srcdoc = out.content;
      }catch(err){ this.say('Entwurf nicht lesbar: ' + err.message, 'warn'); }
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
