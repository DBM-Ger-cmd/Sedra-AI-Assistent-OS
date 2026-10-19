// Werkzeug „Planungstisch“ (19.10.2026) – die Arbeitsumgebung für KI-Assistenten: links das Gespräch mit einer Rolle,
// rechts die Vorschläge (Ziele mit Stufen, Aufträge) als Karten, die der Captain übernimmt oder verwirft, und was heute festgelegt wurde.
// Nichts läuft ohne den Klick des Captains. Regeln des Vertrags: nur im eigenen Container, nur ctx.api und ctx.bus, kein Speicher.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const ROLLEN_WORT = {planner: 'Planer', researcher: 'Rechercheur', coder: 'Entwickler', reviewer: 'Prüfer', documentation: 'Dokumentar',
                       'context curator': 'Kontextpfleger'};
  const MAX_HISTORY = 8;

  // Die Rollen aus den Rezepten (rein, wie in der Besatzung): 'coder.local_primary' -> coder; der Planer steht immer zuerst
  function rollenAus(recipes){
    const seen = new Set(['planner']);
    const out = [{id: 'planner', label: 'Planer'}];
    (recipes || []).forEach(r=>(r.roles || []).forEach(role=>{
      const id = String(role).replace(/[._-]/g, ' ').trim().toLowerCase();
      if(!id || seen.has(id)) return;
      seen.add(id);
      out.push({id, label: ROLLEN_WORT[id] || (id.charAt(0).toUpperCase() + id.slice(1))});
    }));
    return out;
  }

  // Was eine Vorschlagskarte sagt (rein)
  function kartenText(a){
    if(!a) return null;
    if(a.kind === 'intent') return {art: 'Ziel', titel: a.title, text: a.text || '', stufen: a.stufen || []};
    if(a.kind === 'task') return {art: 'Auftrag', titel: a.title || String(a.text || '').slice(0, 60), text: a.text || '', stufen: []};
    if(a.kind === 'verb') return {art: 'Handlung', titel: a.label + ': ' + (a.title || a.id), text: a.needs_gate ? 'braucht eine Freigabe' : '', stufen: []};
    if(a.kind === 'open') return {art: 'Fenster', titel: a.title || a.place || '', text: '', stufen: []};
    return null;
  }

  const tool = {
    id: 'planung',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-planung');
      this.history = []; this.missionId = ''; this.vorschlaege = []; this.festgelegt = []; this.rolle = 'planner'; this.busy = false;
      this.build();
      this.offs = [ctx.bus.on('task.changed', ()=>this.drawFestgelegt())];
      return this.ladeRollen();
    },

    unmount(){ (this.offs || []).forEach(off=>{ if(typeof off === 'function') off(); }); this.el.classList.remove('t-planung'); this.el.replaceChildren(); },

    build(){
      const links = d().el('section', 't-planung-gespraech');
      const kopf = d().el('div', 't-planung-kopf');
      this.rollePick = d().el('select', 't-planung-rolle'); this.rollePick.setAttribute('aria-label', 'Rolle des Assistenten');
      this.rollePick.onchange = ()=>{ this.rolle = this.rollePick.value; this.sag('Hinweis', 'Jetzt spricht ' + this.rolleWort() + '. Das Gespräch läuft weiter.', 'note'); };
      kopf.append(d().el('b', null, 'Gespräch mit '), this.rollePick);
      this.log = d().el('div', 't-planung-log'); this.log.setAttribute('aria-live', 'polite');
      this.sag('Hinweis', 'Sag, worum es geht – der Assistent macht daraus Ziele mit Stufen und Aufträge. Jeder Vorschlag erscheint rechts; erst dein Klick legt ihn an.', 'note');
      const eingabe = d().el('div', 't-planung-eingabe');
      this.feld = d().el('textarea'); this.feld.rows = 2;
      this.feld.placeholder = 'Zum Beispiel: Wir wollen 3D-Assets über einen Etsy-Shop verkaufen – plane das mit mir.';
      this.feld.setAttribute('aria-label', 'Nachricht an den Assistenten');
      this.feld.onkeydown = e=>{ if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); this.senden(); } };
      const knoepfe = d().el('div', 't-planung-knoepfe');
      this.sendBtn = d().button('Senden', ()=>this.senden(), 'p');
      knoepfe.append(this.sendBtn,
        d().button('Als Ziel', ()=>this.direkt('intent'), ''),
        d().button('Als Auftrag', ()=>this.direkt('task'), ''),
        d().el('small', 's-muted', 'Enter sendet · „Als Ziel“ / „Als Auftrag“ legen den Satz ohne Assistenten an'));
      eingabe.append(this.feld, knoepfe);
      links.append(kopf, this.log, eingabe);

      const rechts = d().el('aside', 't-planung-tisch');
      this.vorschlagBox = d().el('div', 't-planung-vorschlaege');
      this.festBox = d().el('div', 't-planung-festgelegt');
      rechts.append(d().el('h5', 's-head', 'Vorschläge'), this.vorschlagBox, d().el('h5', 's-head', 'Heute festgelegt'), this.festBox);
      this.el.replaceChildren(links, rechts);
      this.drawVorschlaege(); this.drawFestgelegt();
    },

    async ladeRollen(){
      const models = await this.ctx.api('/api/models').catch(()=>({}));
      this.rollen = rollenAus(models.recipes);
      this.rollePick.replaceChildren(...this.rollen.map(r=>{ const o = d().el('option', null, r.label); o.value = r.id; return o; }));
      this.rollePick.value = this.rolle;
    },

    rolleWort(){ return ((this.rollen || []).find(r=>r.id === this.rolle) || {}).label || 'der Assistent'; },

    sag(wer, text, tone){
      const row = d().el('p', 't-planung-line' + (tone ? ' ' + tone : ''));
      row.append(d().el('b', null, wer), d().el('span', null, ' ' + text));
      this.log.append(row); this.log.scrollTop = this.log.scrollHeight;
      return row;
    },

    /* ---------------- das Gespräch ---------------- */
    async senden(){
      const text = this.feld.value.trim();
      if(!text || this.busy) return;
      this.feld.value = ''; this.busy = true; this.sendBtn.disabled = true;
      this.sag('Du', text, 'me');
      const warten = this.sag(this.rolleWort(), 'Denkt nach …', 'note');
      try{
        const out = await this.ctx.api('/api/planung/reply', {method: 'POST', body: {text, history: this.history.slice(-MAX_HISTORY), rolle: this.rolle, mission_id: this.missionId}});
        warten.remove();
        if(out.status === 'no_model'){
          this.sag('Hinweis', (out.message || 'Kein Modell geladen.') + ' In der Werkstatt ein Modell laden – oder den Satz mit „Als Ziel“ / „Als Auftrag“ direkt anlegen.', 'warn');
          this.feld.value = text; return;
        }
        if(out.status !== 'completed'){ this.sag('Hinweis', 'Der Assistent hat nicht geantwortet: ' + (out.message || out.status), 'warn'); this.feld.value = text; return; }
        this.missionId = out.mission_id || this.missionId;
        this.history.push({role: 'user', content: text}, {role: 'assistant', content: out.reply || ''});
        this.sag(this.rolleWort(), out.reply || '(keine Antwort)', '');
        const neu = (out.ui_actions || []).map(kartenText).filter(Boolean).map((k, i)=>Object.assign(k, {action: out.ui_actions[i]}));
        if(neu.length){ this.vorschlaege.push(...neu); this.drawVorschlaege(); this.sag('Hinweis', neu.length + (neu.length === 1 ? ' Vorschlag liegt' : ' Vorschläge liegen') + ' rechts auf dem Tisch.', 'note'); }
      }catch(err){ warten.remove(); this.sag('Hinweis', 'Das hat nicht geklappt: ' + err.message, 'warn'); this.feld.value = text; }
      finally{ this.busy = false; this.sendBtn.disabled = false; }
    },

    // Ohne Assistenten: der Satz im Feld wird direkt ein Ziel oder ein Auftrag – als Vorschlag, den der Captain gleich übernimmt
    direkt(kind){
      const text = this.feld.value.trim();
      if(!text) return;
      const a = kind === 'intent' ? {kind: 'intent', title: text.slice(0, 80), text} : {kind: 'task', text, title: text.slice(0, 60)};
      this.vorschlaege.push(Object.assign(kartenText(a), {action: a}));
      this.feld.value = ''; this.drawVorschlaege();
    },

    /* ---------------- der Tisch: Vorschläge und Festgelegtes ---------------- */
    drawVorschlaege(){
      const box = this.vorschlagBox; box.replaceChildren();
      if(!this.vorschlaege.length){ box.append(d().el('div', 's-note', 'Noch nichts. Was der Assistent vorschlägt, liegt hier – Ziel, Auftrag oder Handlung – bis du es übernimmst oder verwirfst.')); return; }
      this.vorschlaege.forEach((v, i)=>{
        const karte = d().el('div', 't-planung-karte ' + v.action.kind);
        const kopf = d().el('div', 't-planung-karte-kopf');
        kopf.append(d().el('span', 't-planung-art', v.art), d().el('b', null, v.titel));
        karte.append(kopf);
        if(v.text && v.text !== v.titel) karte.append(d().el('p', 't-planung-karte-text', v.text));
        if(v.stufen.length){
          const ol = d().el('ol', 't-planung-stufen');
          v.stufen.forEach(s=>ol.append(d().el('li', null, s)));
          karte.append(ol);
        }
        const row = d().el('div', 't-planung-karte-row');
        row.append(d().button('Übernehmen', ()=>this.uebernehmen(i), 'p'), d().button('Verwerfen', ()=>{ this.vorschlaege.splice(i, 1); this.drawVorschlaege(); }, ''));
        karte.append(row);
        box.append(karte);
      });
    },

    async uebernehmen(i){
      const v = this.vorschlaege[i]; if(!v) return;
      const a = v.action;
      try{
        let objekt = null, wort = '';
        if(a.kind === 'intent'){
          const body = {title: a.title, text: a.text || ''};
          if((a.stufen || []).length) body.stufen = a.stufen;
          const made = await this.ctx.api('/api/intent/create', {method: 'POST', body});
          objekt = {type: 'intent', id: made.id, title: made.title};
          wort = 'Ziel angelegt' + ((made.stufen || []).length ? ' mit ' + made.stufen.length + ' Stufen' : '') + ': ' + made.title + '.';
        }else if(a.kind === 'task'){
          const out = await this.ctx.api('/api/chat', {method: 'POST', body: {intent: a.text}});
          const m = out.mission || {};
          objekt = {type: 'task', id: m.mission_id, title: String(m.intent || a.title).slice(0, 40)};
          wort = 'Auftrag angelegt – geplant, nicht ausgeführt: ' + (m.intent || a.title).slice(0, 80) + '.';
        }else if(a.kind === 'verb'){
          const out = await this.ctx.api('/api/actions', {method: 'POST', body: {type: a.type, id: a.id, verb: a.verb}});
          const res = (out && out.result) || {};
          objekt = res.mission_id ? {type: 'task', id: res.mission_id, title: 'Aufgabe'} : {type: a.type, id: a.id, title: a.title || a.id};
          wort = (a.needs_gate ? a.label + ' liegt zur Freigabe bei den Entscheidungen.' : 'Erledigt: ' + a.label + '.');
        }else if(a.kind === 'open'){
          const p = ((root.sedraPlaces && root.sedraPlaces.PLACES) || []).find(x=>x.id === a.place);
          objekt = a.object || (p && p.object); wort = objekt ? 'Geöffnet: ' + (objekt.title || a.title) + '.' : 'Diesen Ort kennt die Oberfläche nicht.';
          if(objekt){ this.ctx.shell.open(objekt); this.vorschlaege.splice(i, 1); this.drawVorschlaege(); this.sag('Hinweis', wort, 'note'); return; }
        }
        this.vorschlaege.splice(i, 1);
        if(objekt && objekt.id) this.festgelegt.push(Object.assign({art: v.art, titel: objekt.title || v.titel}, objekt));
        this.sag('Hinweis', wort, 'note');
        this.drawVorschlaege(); this.drawFestgelegt();
      }catch(err){ this.sag('Hinweis', 'Übernehmen hat nicht geklappt: ' + err.message, 'warn'); }
    },

    drawFestgelegt(){
      const box = this.festBox; box.replaceChildren();
      if(!this.festgelegt.length){ box.append(d().el('div', 's-note', 'Noch nichts in dieser Sitzung. Alles, was du übernimmst, steht hier – und bei den Zielen und Issues.')); return; }
      this.festgelegt.slice().reverse().forEach(f=>{
        const row = d().el('div', 't-planung-fest');
        row.append(d().el('span', 't-planung-art', f.art), d().el('span', null, f.titel), d().el('small', 's-muted', 'öffnen ›'));
        d().clickable(row, ()=>this.ctx.shell.open({type: f.type, id: f.id, title: f.titel}));
        box.append(row);
      });
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraPlanungPure = {rollenAus, kartenText};
  if(typeof module !== 'undefined' && module.exports) module.exports = {rollenAus, kartenText};
})();
