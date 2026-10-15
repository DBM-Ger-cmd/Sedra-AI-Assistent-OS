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
      this.input.onkeydown = e=>{ if(e.key === 'Enter'){ e.preventDefault(); const t = this.input.value.trim(); this.input.value = ''; if(t) this.send(t); } };
      const send = d().button('Senden', ()=>{ const t = this.input.value.trim(); this.input.value = ''; if(t) return this.send(t); }, 'p');
      bar.append(this.input, send);
      el.replaceChildren(this.log, bar);

      ctx.bus.on('talk.context', e=>{ this.object = e.object || null; });
      ctx.bus.on('decision.pending', e=>{
        this.pending = e;
        this.say('Eine Entscheidung wartet: ' + (e.title || e.describe || e.id) + ' – auf der Karte, oder hier mit „ja“ oder „nein“.', 'warn');
      });
      ctx.bus.on('decision.answered', ()=>{ this.pending = null; });
      this.say('Bereit. Schreib einen Auftrag, eine Frage, oder nenn einen Ort („Entscheidungen“, „Modelle“).', 'note');
      setTimeout(()=>this.input.focus(), 50);
    },

    unmount(){ this.el.replaceChildren(); this.el.classList.remove('t-talk'); },

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
        const out = await this.ctx.api('/api/chat/reply', {method: 'POST', body: {mission_id: this.mission || '', text, history: this.history.slice(0, -1), attachments: []}});
        row.remove();
        if(out.status === 'completed'){
          this.mission = out.mission_id;
          this.line('GUPPI', out.reply, '');
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
