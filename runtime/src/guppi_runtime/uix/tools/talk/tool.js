// Werkzeug „Gespräch“ (kind: panel) – the one input (COCKPIT_MODUL_v1 rule 1): talks to the model, follows talk.context, routes places, takes „einmal ja“ (rule 2).
// Vertrag 1.1: der Verlauf kommt vom Server (verlauf.js) und übersteht Neuladen und Shell-Wechsel; „Leeren“ leert ihn dort.
// Build 19: SEDRA moves in the module environment. The model proposes (`ui_actions`); this tool draws a button for each, and only the
// Captain's click opens the window or runs the verb (`POST /api/actions`). His own sentence asking to open something is the approval.

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

  // „lade Modell XY“ / „lade qwen 9b“: a plain chat command – no model and no gate needed; the „ja“ after the question is the approval.
  // Returns the words after „lade“ or null. Pure, node tests it.
  function ladeBefehl(text){
    const t = String(text || '').toLowerCase().replace(/[!?]/g, ' ').replace(/\s+/g, ' ').trim();
    const m = t.match(/^(?:bitte )?(?:lade|lad)(?: mir)?(?: das| den| die)? (?:modell )?(.+?)(?: bitte)?$/);
    return m ? m[1].trim() : null;
  }

  // Which recipe the words name: every word must occur in its id or model name. {recipe} | {many: [ids]} | {none: true}. Pure.
  function waehleRezept(query, recipes){
    const words = String(query || '').toLowerCase().split(' ').filter(Boolean);
    const list = (Array.isArray(recipes) ? recipes : []).filter(r => r && r.id);
    if(!words.length) return {none: true};
    const hits = list.filter(r => { const hay = (r.id + ' ' + (r.model || '')).toLowerCase(); return words.every(w => hay.includes(w)); });
    if(hits.length === 1) return {recipe: hits[0]};
    return hits.length ? {many: hits.map(r => r.id)} : {none: true};
  }

  // „ja 2“ / „nein 1“: a number picks one of several waiting decisions. {answer, index} or null. Pure, node tests it.
  function nummerierteAntwort(text){
    const t = String(text || '').toLowerCase().replace(/[.,!?]/g, ' ').replace(/\s+/g, ' ').trim();
    const m = t.match(/^(ja|nein|einmal ja|ja einmal|freigeben|ablehnen) (\d{1,2})$/);
    if(!m) return null;
    return {answer: /nein|ablehnen/.test(m[1]) ? 'ablehnen' : 'einmal', index: Number(m[2])};
  }

  // Which decision a plain „ja“/„nein“ answers: the one SEDRA announced if it still waits, else the only one. Pure, node tests it.
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
    if(a.kind === 'intent') return 'Als Vorhaben anlegen: ' + a.title + ((a.stufen || []).length ? ' (' + a.stufen.length + ' Stufen)' : '');
    return a.kind === 'task' ? 'Als Auftrag anlegen: ' + (a.title || String(a.text || '').slice(0, 60)) : '';
  }

  // Zustand eines Cloud-Modells als Zeichen und Wort (grün schnell, gelb langsam, rot antwortet nicht, grau ungeprüft)
  const AMPEL_ZEICHEN = {gruen: '✓ schnell', gelb: '◐ langsam', rot: '✗ antwortet nicht', grau: '○ ungeprüft'};
  function ampelText(a){ return AMPEL_ZEICHEN[a] || AMPEL_ZEICHEN.grau; }

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
      this.input.setAttribute('aria-label', 'Gespräch mit SEDRA');
      this.input.onkeydown = e=>{ if(e.key === 'Enter'){ e.preventDefault(); this.submit(); } };
      // Wahl neben Senden: SEDRA lokal (Standard) oder ein Cloud-Modell aus der KI Labor
      this.picker = d().el('select', 't-talk-pick');
      this.picker.setAttribute('aria-label', 'Modell für diese Frage');
      const local = d().el('option', null, 'SEDRA lokal'); local.value = '';
      this.picker.append(local);
      // Lokal + KI: das lokale Modell erstellt den Entwurf, das Cloud-Modell prüft ihn – in diesem einen Fenster
      const kombi = d().el('option', null, 'Lokal + KI (zusammen)'); kombi.value = 'kombi';
      this.picker.append(kombi);
      // Zustand des gewählten Modells: Punkt neben der Auswahl
      this.ampel = d().el('span', 't-talk-ampel aus');
      this.picker.addEventListener('change', ()=>{ this.ampelZeigen(); this.ctx.bus.emit('talk.mode', {mode: this.picker.value ? 'cloud' : 'local'}); });
      // Die Leiste (Online-KI) schaltet die Auswahl: lokal = „SEDRA lokal“, cloud = das erste Cloud-Modell der Liste
      ctx.bus.on('talk.mode', e=>{
        if(!e || !this.picker) return;
        if(e.mode === 'local'){ this.picker.value = ''; }
        else if(e.mode === 'cloud'){ const c = [...this.picker.options].find(o=>o.value.startsWith('cloud:')); if(c) this.picker.value = c.value; }
        this.ampelZeigen();
      });
      this.gruen = d().button('Grüne zuerst', ()=>this.gruenZeigen());
      const send = d().button('Senden', ()=>this.submit(), 'p'), leer = d().button('Leeren', ()=>root.sedraTalkVerlauf.leeren(this)); leer.title = 'Gespräch leeren (auch auf dem Server)';
      bar.append(this.input, this.picker, this.ampel, this.gruen, send, leer);
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
      if(root.sedraTalkVerlauf) root.sedraTalkVerlauf.laden(this);
      setTimeout(()=>this.input.focus(), 50);
    },

    unmount(){ this.el.replaceChildren(); this.el.classList.remove('t-talk'); },

    // Eingabe absenden: mit gewähltem Cloud-Modell in die Cloud, sonst wie bisher zu SEDRA
    submit(){
      const t = this.input.value.trim();
      this.input.value = '';
      if(!t) return;
      if(this.picker.value === 'kombi') return this.sendKombi(t);
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

    // Die Cloud-Modelle, die im Labor bereit sind (nur lesen). Ist die Cloud aus, bleibt die Wahl bei „SEDRA lokal“.
    async loadCloud(){
      try{
        const v = await this.ctx.api('/api/cloud');
        if(!v.enabled) return;
        for(const p of v.providers || []){
          if(p.status !== 'bereit') continue;
          let list = [], zust = {};
          try{ const r = await this.ctx.api('/api/cloud/models', {method: 'POST', body: {provider: p.id}}); list = (r.models || []).slice(); zust = r.zustand || {}; }
          catch(_err){ list = []; }
          if(p.default_model && !list.includes(p.default_model)) list.unshift(p.default_model);
          if(!list.length) continue;
          const group = d().el('optgroup');
          group.label = 'Cloud · ' + p.id;
          list.forEach(id=>{
            const a = (zust[id] || {}).ampel || 'grau';
            const o = d().el('option', null, id + '  ' + ampelText(a)); o.value = 'cloud:' + p.id + '|' + id; o.dataset.ampel = a;
            group.append(o);
          });
          this.picker.append(group);
        }
        // Die Zuordnung „chat“ (KI Labor, module_models) ist die Vorgabe: neue Fragen gehen dorthin, „SEDRA lokal“ bleibt wählbar
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
        this.ampelZeigen();
      }catch(_err){ /* ohne Cloud gibt es nur SEDRA lokal */ }
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

    // der Punkt zeigt den Zustand des gewählten Modells; bei „SEDRA lokal“ bleibt er aus
    ampelZeigen(){
      if(!this.ampel) return;
      const o = this.picker.selectedOptions && this.picker.selectedOptions[0];
      if(!this.picker.value || !o){ this.ampel.className = 't-talk-ampel aus'; this.ampel.title = 'SEDRA lokal'; return; }
      const a = o.dataset.ampel || 'grau';
      this.ampel.className = 't-talk-ampel ' + a;
      this.ampel.title = ampelText(a);
    },

    // Eine Frage an ein Cloud-Modell. Der Inhaltsschutz läuft auf dem Server; die Antwort steht mit Modellnamen im Gespräch.
    async sendKombi(text){ return root.sedraTalkKombi.sendKombi(this, text); },
    async sendCloud(value, text){
      const [pid, model] = value.slice('cloud:'.length).split('|');
      this.line('Du', text, 'me');
      this.history.push({role: 'user', content: text});
      const who = 'Cloud · ' + pid + ' / ' + model;
      const row = this.line(who, 'Denkt nach …', 'note');
      try{
        const out = await this.ctx.api('/api/chat/cloud', {method: 'POST', body: {provider: pid, model, text, history: root.sedraTalkVerlauf.fuerCloud(this.history.slice(0, -1))}});
        row.remove();
        if(out.status === 'completed'){
          this.line(who, out.reply || '(leere Antwort)', '');
          this.history.push({role: 'assistant', content: out.reply || ''});
        }else{
          this.history.pop();
          this.line('SEDRA', 'Die Cloud hat die Frage nicht beantwortet: ' + ((out.reasons || []).join(', ') || out.status), 'warn');
        }
      }catch(err){
        this.history.pop(); row.remove();
        this.line('SEDRA', 'Cloud-Antwort fehlgeschlagen: ' + err.message, 'warn');
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

    // „lade …“: die Rezepte lesen, eindeutig treffen, fragen – das Laden kommt erst nach „ja“
    async ladeBefehl(query){
      let recipes = [];
      try{ recipes = (((await this.ctx.api('/api/objects', {method: 'POST', body: {type: 'model'}})) || {}).items || []).map(o=>({id: o.id, model: o.summary || ''})); }   // read-only, wie jede Liste (§10.1)
      catch(err){ this.line('SEDRA', 'Die Modelle sind gerade nicht lesbar: ' + err.message, 'warn'); return; }
      const pick = waehleRezept(query, recipes);
      if(pick.recipe){
        this.pendingLoad = pick.recipe.id;
        this.line('SEDRA', 'Modell „' + (pick.recipe.model || pick.recipe.id) + '“ laden? Antworte mit ja oder nein.', 'note');
        return;
      }
      this.line('SEDRA', pick.many ? 'Mehrere passen: ' + pick.many.join(', ') + '. Genauer benennen.' : 'Kein Modell „' + query + '“ gefunden.', 'warn');
    },

    async laden(recipeId){
      this.line('SEDRA', 'Lade … das dauert einen Moment.', 'note');
      try{
        const out = ((await this.ctx.api('/api/actions', {method: 'POST', body: {type: 'model', id: recipeId, verb: 'laden'}})) || {}).result || {};   // das Verb „laden“ (§10.2), nicht die Modellroute
        this.line('SEDRA', 'Geladen: ' + (out.identifier || recipeId) + ' · Kontext ' + (out.context_length || '?') + '.', 'note');
      }catch(err){ this.line('SEDRA', 'Laden fehlgeschlagen: ' + (err.message === 'verb_not_offered_in_this_state' ? 'das Modell ist nicht einsatzbereit (Werkstatt: Datei hinterlegen oder einschalten).' : err.message), 'warn'); }
    },

    // the shell speaks through here (problems, hints); never a question
    say(text, tone){ if(this.log) this.line('SEDRA', text, tone === 'warn' ? 'warn' : 'note'); },

    async send(text){
      this.line('Du', text, 'me');
      if(this.pendingLoad){                                                 // die Rückfrage von „lade …“ wartet auf ja/nein
        const recipe = this.pendingLoad; this.pendingLoad = null;
        const answer = yesNo(text);
        if(answer === 'einmal'){ await this.laden(recipe); return; }
        if(answer === 'ablehnen'){ this.line('SEDRA', 'Laden abgebrochen.', 'note'); return; }
      }
      const befehl = ladeBefehl(text);
      if(befehl !== null){ await this.ladeBefehl(befehl); return; }
      const route = root.sedraPlaces && root.sedraPlaces.routeText(text);   // Ortskunde aus dem Vertrag, nicht aus einer Shell
      if(route && route.kind === 'place'){
        this.ctx.shell.open(route.object);
        this.line('SEDRA', 'Geöffnet: ' + route.object.title + '.', 'note');
        return;
      }
      const numbered = nummerierteAntwort(text);
      if(numbered && await this.answerDecision(numbered.answer, numbered.index)) return;
      const answer = yesNo(text);
      if(answer && await this.answerDecision(answer)) return;
      const row = this.line('SEDRA', 'Denkt nach …', 'note');
      this.history.push({role: 'user', content: text});
      try{
        const out = await this.ctx.api('/api/chat/reply', {method: 'POST', body: root.sedraTalkVerlauf.antwortKoerper(this, text)});
        row.remove();
        if(out.status === 'completed'){
          this.mission = out.mission_id || this.mission;
          this.line('SEDRA', out.reply, '');
          if(out.quelle) this.line('SEDRA', 'Quelle: ' + out.quelle + ' – ohne Modell beantwortet.', 'note');
          root.sedraTalkVerlauf.antwortMerken(this, out);                   // „Frag das Wissen“: mit Personenbezug nur lokal
          this.offer(out.ui_actions, text);
        }else if(out.status === 'no_model'){
          this.history.pop();
          this.line('SEDRA', 'Kein Modell geladen – in der Werkstatt eins laden, dann antworte ich.', 'warn');
          this.ctx.shell.open({type: 'model', id: 'alle', title: 'Werkstatt'});
        }else{
          this.history.pop();
          this.line('SEDRA', 'Das Modell hat nicht geantwortet: ' + (out.message || out.status), 'warn');
        }
      }catch(err){
        this.history.pop(); row.remove();
        this.line('SEDRA', 'Fehler: ' + err.message, 'warn');
      }
    },

    // „ja“/„nein“ on a waiting decision. Returns false when there is nothing to answer – then the sentence goes to SEDRA.
    async answerDecision(answer, index){
      let items;
      try{ items = ((await this.ctx.api('/api/decisions')) || {}).items || []; }
      catch(_e){ return false; }
      if(!items.length){ this.pending = null; return false; }
      let target = index ? items[index - 1] : pickDecision(items, this.pending && this.pending.id);
      if(index && !target){
        this.line('SEDRA', 'Die Nummer ' + index + ' gibt es nicht. Es warten ' + items.length + ' Entscheidungen.', 'warn');
        return true;
      }
      if(!target){
        // Mehrere warten und keine ist angekündigt: die Liste mit Nummern zeigen, nicht raten
        this.line('SEDRA', 'Es warten ' + items.length + ' Entscheidungen: ' + items.map((it, i)=>(i + 1) + ') ' + (it.title || it.id)).join(' · ')
          + '. Antworte z. B. „ja 1“ oder „nein 2“.', 'warn');
        return true;
      }
      try{
        await this.ctx.shell.decide(target.id, wayFor(target, answer));
        this.line('SEDRA', answer === 'ablehnen' ? 'Abgelehnt: ' + target.title + '. Nichts ist passiert; es steht im Logbuch.'
                                                  : 'Freigegeben: ' + target.title + ' – im Logbuch festgehalten.', 'note');
        this.pending = null;
      }catch(err){ this.line('SEDRA', 'Das ging nicht: ' + err.message, 'warn'); }
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
      const object = a.object || ((((root.sedraPlaces && root.sedraPlaces.PLACES) || []).find(x=>x.id === a.place)) || {}).object || null;
      if(!object){ this.line('SEDRA', 'Diesen Ort kennt die Oberfläche nicht: ' + (a.place || '?'), 'warn'); return; }
      this.ctx.shell.open(object);
      this.line('SEDRA', 'Geöffnet: ' + (object.title || a.title) + '.', 'note');
    },

    async runAction(a){
      if(a.kind === 'open') return this.openAction(a);
      if(a.kind === 'intent'){     // mit Stufen (19.10.): jede Stufe kann später eine Aufgabe werden
        const made = await this.ctx.api('/api/intent/create', {method: 'POST', body: {title: a.title, text: a.text || '', stufen: a.stufen || []}});
        this.line('SEDRA', 'Vorhaben angelegt: ' + made.title + '. Daraus wird eine Aufgabe, wenn du „Aufgabe daraus machen“ drückst.', 'note');
        return this.ctx.shell.open({type: 'intent', id: made.id, title: made.title});
      }
      if(a.kind === 'task'){       // ein Auftrag (propose_task): eine Aufgabe, geplant, nicht ausgeführt – wie ein Satz im Gespräch
        const m = ((await this.ctx.api('/api/chat', {method: 'POST', body: {intent: a.text}})) || {}).mission || {};
        this.line('SEDRA', 'Auftrag angelegt – geplant, nicht ausgeführt: ' + String(m.intent || a.text).slice(0, 80) + '.', 'note');
        return this.ctx.shell.open({type: 'task', id: m.mission_id, title: String(m.intent || 'Aufgabe').slice(0, 40)});
      }
      if(a.kind !== 'verb') return;
      if(a.confirm && typeof confirm === 'function' && !confirm(a.confirm)) throw new Error('nicht bestätigt');
      const out = await this.ctx.api('/api/actions', {method: 'POST', body: {type: a.type, id: a.id, verb: a.verb}});
      const res = (out && out.result) || {};
      if(res.status === 'boundary') this.line('SEDRA', res.note || 'Eine Grenze steht im Weg – die Entscheidung wartet.', 'warn');
      else if(a.needs_gate) this.line('SEDRA', a.label + ' liegt jetzt zur Freigabe bei den Entscheidungen.', 'note');
      else this.line('SEDRA', 'Erledigt: ' + a.label + ' – ' + (a.title || a.id) + '.', 'note');
      const made = res.mission_id;
      this.ctx.shell.open(made ? {type: 'task', id: made, title: 'Aufgabe'} : {type: a.type, id: a.id, title: a.title || a.id});
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);            // in node only the pure part is read
  root.sedraTalkPure = {yesNo, pickDecision, wayFor, actionLabel, ladeBefehl, waehleRezept, nummerierteAntwort};
  if(typeof module !== 'undefined' && module.exports) module.exports = {yesNo, pickDecision, wayFor, actionLabel, ladeBefehl, waehleRezept, nummerierteAntwort};
})();
