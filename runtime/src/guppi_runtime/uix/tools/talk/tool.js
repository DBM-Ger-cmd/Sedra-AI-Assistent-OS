// Werkzeug „Gespräch“ (kind: panel) – the one input of the Cockpit (COCKPIT_MODUL_v1 rule 1).
// It talks to the loaded model (/api/chat/reply), follows the object in front (talk.context), understands a navigation phrase
// without asking the model, and takes „einmal ja“ as an answer to the decision that waits (rule 2: same audit, one place).
// Build 19: GUPPI moves in the module environment. The model proposes (`ui_actions` in the answer); this tool draws a button for
// each, and only the Captain's click opens the window or runs the verb – over `POST /api/actions`, the way every tool button goes.
// When the Captain's own sentence asked to open something, that sentence is the approval and the window opens at once.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // '' or the way the Captain answered a waiting decision in plain words (pure, node tests it)
  function yesNo(text){
    const t = String(text || '').toLowerCase().replace(/[.,!?]/g, ' ').replace(/\s+/g, ' ').trim();
    if(/^(einmal ja|ja einmal|einmal öffnen|einmal oeffnen|ja, einmal|ja einmal freigeben)$/.test(t)) return 'einmal';
    if(/^(ja|ja bitte|freigeben|freigabe|ja freigeben)$/.test(t)) return 'einmal';     // nicht „ok“: das ist oft nur ein Nicken
    if(/^(nein|ablehnen|nicht|stopp|stop|lass es)$/.test(t)) return 'ablehnen';
    return '';
  }

  // Which decision a plain „ja“/„nein“ answers: the one GUPPI announced if it still waits, else the only one. Pure, node tests it.
  // (PC-Test 15.10.: „ja“ ging ans Modell, weil die gemerkte Ankündigung weg war – jetzt wird die Liste frisch gelesen.)
  function pickDecision(items, announced){
    const list = Array.isArray(items) ? items : [];
    if(announced){ const same = list.find(d=>d.id === announced); if(same) return same; }
    return list.length === 1 ? list[0] : null;
  }

  // The way a decision is answered with „ja“: a change request is approved and applied in one go, everything else once
  function wayFor(decision, answer){
    if(answer === 'ablehnen') return 'ablehnen';
    const ways = (decision && decision.ways) || [];
    if(ways.includes('freigeben_und_anwenden')) return 'freigeben_und_anwenden';
    return ways.includes('einmal') ? 'einmal' : (ways[0] || 'einmal');
  }

  // What a button under an answer says (pure)
  function actionLabel(a){
    if(!a) return '';
    if(a.kind === 'open') return 'Öffnen: ' + (a.title || a.place || (a.object && a.object.id) || 'Fenster');
    if(a.kind === 'verb') return a.label + ': ' + (a.title || a.id) + (a.needs_gate ? ' (mit Freigabe)' : '');
    if(a.kind === 'intent') return 'Als Vorhaben anlegen: ' + a.title;
    return '';
  }

  const tool = {
    id: 'talk',
    history: [],
    mission: null,
    object: null,
    pending: null,

    mount(el, ctx){
      this.el = el; this.ctx = ctx; this.history = [];
      el.classList.add('t-talk');
      this.log = d().el('div', 't-talk-log');
      this.log.setAttribute('role', 'log');
      const bar = d().el('div', 't-talk-in');
      this.input = d().el('input');
      this.input.placeholder = 'Antwort oder Auftrag · Enter sendet';
      this.input.setAttribute('aria-label', 'Gespräch mit GUPPI');
      this.input.onkeydown = e=>{ if(e.key === 'Enter'){ e.preventDefault(); this.submit(); } };
      // Wahl neben Senden: GUPPI lokal (Standard) oder ein Cloud-Modell aus der KI Labor
      this.picker = d().el('select', 't-talk-pick');
      this.picker.setAttribute('aria-label', 'Modell für diese Frage');
      const local = d().el('option', null, 'GUPPI lokal'); local.value = '';
      this.picker.append(local);
      const send = d().button('Senden', ()=>this.submit(), 'p');
      bar.append(this.input, this.picker, send);
      el.replaceChildren(this.grip(el), this.log, bar);
      this.loadCloud();

      ctx.bus.on('talk.context', e=>{ this.object = e.object || null; });
      // B6-G-03: der zuletzt geöffnete GateWay-Vorgang geht mit jeder Frage mit – so weiß die Wissensbasis, worum es geht
      ctx.bus.on('object.open', e=>{ if(e && e.type === 'gateway' && e.id && e.id !== 'alle') this.vorgang = e.id; });
      ctx.bus.on('decision.pending', e=>{
        this.pending = e;
        this.say('Eine Entscheidung wartet: ' + (e.title || e.describe || e.id) + ' – auf der Karte, oder hier mit „ja“ oder „nein“.', 'warn');
      });
      ctx.bus.on('decision.answered', ()=>{ this.pending = null; });
      this.say('Bereit. Schreib einen Auftrag, eine Frage, oder nenn einen Ort („Entscheidungen“, „Modelle“).', 'note');
      setTimeout(()=>this.input.focus(), 50);
    },

    unmount(){ this.el.replaceChildren(); this.el.classList.remove('t-talk'); },

    // Eingabe absenden: mit gewähltem Cloud-Modell in die Cloud, sonst wie bisher zu GUPPI
    submit(){
      const t = this.input.value.trim();
      this.input.value = '';
      if(!t) return;
      if(this.picker.value) return this.sendCloud(this.picker.value, t);
      return this.send(t);
    },

    // Griff oben am Gespräch: nach oben ziehen macht es höher, nach unten niedriger. Die Höhe bleibt pro Anzeige gespeichert.
    grip(el){
      const g = d().el('div', 't-talk-grip');
      g.setAttribute('role', 'separator');
      g.setAttribute('aria-label', 'Höhe des Gesprächs ändern (ziehen)');
      g.onpointerdown = e=>{
        e.preventDefault();
        const shell = el.closest('.ck') || el.parentElement;
        const box = el.closest('.ck-talk') || el;
        const startY = e.clientY, startH = box.getBoundingClientRect().height;
        const move = ev=>{
          const h = Math.max(96, Math.min(root.innerHeight * 0.75, startH + (startY - ev.clientY)));
          shell.style.setProperty('--talk-h', Math.round(h) + 'px');
        };
        const up = ()=>{ root.removeEventListener('pointermove', move); root.removeEventListener('pointerup', up); };
        root.addEventListener('pointermove', move); root.addEventListener('pointerup', up);
      };
      return g;
    },

    // Die Cloud-Modelle, die im Labor bereit sind (nur lesen). Ist die Cloud aus, bleibt die Wahl bei „GUPPI lokal“.
    async loadCloud(){
      try{
        const v = await this.ctx.api('/api/cloud');
        if(!v.enabled) return;
        for(const p of v.providers || []){
          if(p.status !== 'bereit') continue;
          let list = [];
          try{ list = ((await this.ctx.api('/api/cloud/models', {method: 'POST', body: {provider: p.id}})).models || []).slice(); }
          catch(_err){ list = []; }
          if(p.default_model && !list.includes(p.default_model)) list.unshift(p.default_model);
          if(!list.length) continue;
          const group = d().el('optgroup');
          group.label = 'Cloud · ' + p.id;
          list.forEach(id=>{ const o = d().el('option', null, id); o.value = 'cloud:' + p.id + '|' + id; group.append(o); });
          this.picker.append(group);
        }
        // Die Zuordnung „chat“ (KI Labor, module_models) ist die Vorgabe: neue Fragen gehen dorthin, „GUPPI lokal“ bleibt wählbar
        const pre = (v.module_models || {}).chat;
        if(pre && pre.provider && pre.model){
          const value = 'cloud:' + pre.provider + '|' + pre.model;
          if(![...this.picker.options].some(o=>o.value === value)){
            const group = d().el('optgroup'); group.label = 'Vorgabe';
            const o = d().el('option', null, pre.model); o.value = value; group.append(o);
            this.picker.append(group);
          }
          this.picker.value = value;
        }
      }catch(_err){ /* ohne Cloud gibt es nur GUPPI lokal */ }
    },

    // Eine Frage an ein Cloud-Modell. Der Inhaltsschutz läuft auf dem Server; die Antwort steht mit Modellnamen im Gespräch.
    async sendCloud(value, text){
      const [pid, model] = value.slice('cloud:'.length).split('|');
      this.line('Du', text, 'me');
      this.history.push({role: 'user', content: text});
      const who = 'Cloud · ' + pid + ' / ' + model;
      const row = this.line(who, 'Denkt nach …', 'note');
      try{
        const out = await this.ctx.api('/api/chat/cloud', {method: 'POST', body: {provider: pid, model, text, history: this.history.slice(0, -1)}});
        row.remove();
        if(out.status === 'completed'){
          this.line(who, out.reply || '(leere Antwort)', '');
          this.history.push({role: 'assistant', content: out.reply || ''});
        }else{
          this.history.pop();
          this.line('GUPPI', 'Die Cloud hat die Frage nicht beantwortet: ' + ((out.reasons || []).join(', ') || out.status), 'warn');
        }
      }catch(err){
        this.history.pop(); row.remove();
        this.line('GUPPI', 'Cloud-Antwort fehlgeschlagen: ' + err.message, 'warn');
      }
    },

    // a line in the log; who said it decides how it looks
    line(who, text, tone){
      const row = d().el('p', 't-talk-line' + (tone ? ' ' + tone : ''));
      row.append(d().el('b', null, who), d().el('span', null, ' ' + text));
      this.log.append(row);
      this.log.scrollTop = this.log.scrollHeight;
      return row;
    },

    // the shell speaks through here (problems, hints); never a question
    say(text, tone){ if(this.log) this.line('GUPPI', text, tone === 'warn' ? 'warn' : 'note'); },

    async send(text){
      this.line('Du', text, 'me');
      const route = root.sedraPlaces && root.sedraPlaces.routeText(text);   // Ortskunde aus dem Vertrag, nicht aus einer Shell
      if(route && route.kind === 'place'){
        this.ctx.shell.open(route.object);
        this.line('GUPPI', 'Geöffnet: ' + route.object.title + '.', 'note');
        return;
      }
      const answer = yesNo(text);
      if(answer && await this.answerDecision(answer)) return;
      const row = this.line('GUPPI', 'Denkt nach …', 'note');
      this.history.push({role: 'user', content: text});
      try{
        const out = await this.ctx.api('/api/chat/reply', {method: 'POST', body: {mission_id: this.mission || '', text, history: this.history.slice(0, -1), attachments: [], vorgang: this.vorgang || ''}});
        row.remove();
        if(out.status === 'completed'){
          this.mission = out.mission_id || this.mission;
          this.line('GUPPI', out.reply, '');
          if(out.quelle) this.line('GUPPI', 'Quelle: ' + out.quelle + ' – ohne Modell beantwortet.', 'note');
          this.history.push({role: 'assistant', content: out.reply});
          this.offer(out.ui_actions, text);
        }else if(out.status === 'no_model'){
          this.history.pop();
          this.line('GUPPI', 'Kein Modell geladen – in der Werkstatt eins laden, dann antworte ich.', 'warn');
          this.ctx.shell.open({type: 'model', id: 'alle', title: 'Werkstatt'});
        }else{
          this.history.pop();
          this.line('GUPPI', 'Das Modell hat nicht geantwortet: ' + (out.message || out.status), 'warn');
        }
      }catch(err){
        this.history.pop(); row.remove();
        this.line('GUPPI', 'Fehler: ' + err.message, 'warn');
      }
    },

    // „ja“/„nein“ on a waiting decision. Returns false when there is nothing to answer – then the sentence goes to GUPPI.
    async answerDecision(answer){
      let items;
      try{ items = ((await this.ctx.api('/api/decisions')) || {}).items || []; }
      catch(_e){ return false; }
      if(!items.length){ this.pending = null; return false; }
      const target = pickDecision(items, this.pending && this.pending.id);
      if(!target){
        this.line('GUPPI', 'Es warten ' + items.length + ' Entscheidungen – welche meinst du? Sie stehen auf der Karte und im Fenster „Entscheidungen“.', 'warn');
        return true;
      }
      try{
        await this.ctx.shell.decide(target.id, wayFor(target, answer));
        this.line('GUPPI', answer === 'ablehnen' ? 'Abgelehnt: ' + target.title + '. Nichts ist passiert; es steht im Logbuch.'
                                                  : 'Freigegeben: ' + target.title + ' – im Logbuch festgehalten.', 'note');
        this.pending = null;
      }catch(err){ this.line('GUPPI', 'Das ging nicht: ' + err.message, 'warn'); }
      return true;
    },

    // The buttons under an answer. Nothing here runs without the Captain – except opening a window he asked for himself.
    offer(actions, said){
      const list = (Array.isArray(actions) ? actions : []).filter(a=>actionLabel(a)).slice(0, 4);
      if(!list.length) return;
      const asked = root.sedraPlaces && root.sedraPlaces.wantsOpen ? root.sedraPlaces.wantsOpen(said) : false;
      const row = d().el('div', 't-talk-offer');
      list.forEach(a=>{
        if(a.kind === 'open' && asked){ this.openAction(a); return; }
        const b = d().button(actionLabel(a), async()=>{
          await this.runAction(a);
          b.replaceWith(d().el('small', 't-talk-done', '✓ ' + actionLabel(a)));
        }, a.kind === 'verb' && a.needs_gate ? '' : 'p');
        if(a.confirm) b.title = a.confirm;
        row.append(b);
      });
      if(row.childNodes.length){ this.log.append(row); this.log.scrollTop = this.log.scrollHeight; }
    },

    openAction(a){
      const object = a.object || (()=>{
        const p = ((root.sedraPlaces && root.sedraPlaces.PLACES) || []).find(x=>x.id === a.place);
        return p ? p.object : null;
      })();
      if(!object){ this.line('GUPPI', 'Diesen Ort kennt die Oberfläche nicht: ' + (a.place || '?'), 'warn'); return; }
      this.ctx.shell.open(object);
      this.line('GUPPI', 'Geöffnet: ' + (object.title || a.title) + '.', 'note');
    },

    async runAction(a){
      if(a.kind === 'open') return this.openAction(a);
      if(a.kind === 'intent'){
        const made = await this.ctx.api('/api/intent/create', {method: 'POST', body: {title: a.title, text: a.text || ''}});
        this.line('GUPPI', 'Vorhaben angelegt: ' + made.title + '. Daraus wird eine Aufgabe, wenn du „Aufgabe daraus machen“ drückst.', 'note');
        this.ctx.shell.open({type: 'intent', id: made.id, title: made.title});
        return;
      }
      if(a.kind !== 'verb') return;
      if(a.confirm && typeof confirm === 'function' && !confirm(a.confirm)) throw new Error('nicht bestätigt');
      const out = await this.ctx.api('/api/actions', {method: 'POST', body: {type: a.type, id: a.id, verb: a.verb}});
      const res = (out && out.result) || {};
      if(res.status === 'boundary') this.line('GUPPI', res.note || 'Eine Grenze steht im Weg – die Entscheidung wartet.', 'warn');
      else if(a.needs_gate) this.line('GUPPI', a.label + ' liegt jetzt zur Freigabe bei den Entscheidungen.', 'note');
      else this.line('GUPPI', 'Erledigt: ' + a.label + ' – ' + (a.title || a.id) + '.', 'note');
      const made = res.mission_id;
      this.ctx.shell.open(made ? {type: 'task', id: made, title: 'Aufgabe'} : {type: a.type, id: a.id, title: a.title || a.id});
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);            // in node only the pure part is read
  root.sedraTalkPure = {yesNo, pickDecision, wayFor, actionLabel};
  if(typeof module !== 'undefined' && module.exports) module.exports = {yesNo, pickDecision, wayFor, actionLabel};
})();
