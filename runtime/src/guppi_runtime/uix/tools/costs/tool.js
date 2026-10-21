// Werkzeug „Kosten“ – das Münzloch (COCKPIT_MODUL_v1 Regel 5, vierter Nachweis).
// Was diese Aufgabe gekostet hat, und woher die Zahl kommt: vom Anbieter gemeldet oder geschätzt. Beides wird nie vermischt –
// eine Schätzung, die wie eine Messung aussieht, wäre schlimmer als keine Zahl.
// Spec 4 (D4.2.8): neben einem Issue zeigt es das Budget des Bearbeiters und die Token der verknüpften Mission (issueView);
// ein Lauf aus der Cloud trägt das Kennzeichen „Cloud · Anbieter / Modell“ (CLD-06), ein lokaler keines.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Token in Münzen: 1000 Token = 1 Kupfer, 100 Kupfer = 1 Silber, 100 Silber = 1 Gold (rein, wie im Guppy-Meter)
  function coins(tokens){
    const copper = Math.floor((Number(tokens) || 0) / 1000);
    return {gold: Math.floor(copper / 10000), silver: Math.floor(copper / 100) % 100, copper: copper % 100};
  }

  // Ein Satz über die Herkunft der Zahlen (rein)
  function sourceText(quellen){
    const list = quellen || [];
    if(!list.length) return 'Keine Messung hinterlegt.';
    if(list.length === 1 && list[0] === 'provider') return 'Vom Modell selbst gemeldet – exakt.';
    if(list.indexOf('provider') < 0) return 'Geschätzt (das Modell hat keine Zahlen gemeldet).';
    return 'Teils gemeldet, teils geschätzt – die Summe ist eine Untergrenze.';
  }

  // Das Kennzeichen eines Laufs (rein): nur aus der Cloud, sonst null
  function cloudText(v){
    if(!v || v.route !== 'cloud') return null;
    return 'Cloud · ' + (v.provider || v.provider_id || 'Anbieter') + ' / ' + (v.model || 'Modell');
  }

  // Der Budgetsatz eines Agenten (rein): Prozent als Text, Euro nur mit Daten; sonst der Satz des Desk; ohne Daten null
  function budgetText(b){
    if(!b) return null;
    if(typeof b.prozent === 'number'){
      const t = [Math.round(b.prozent) + ' %'];
      if(typeof b.verbraucht_token === 'number' && typeof b.grenze_token === 'number') t.push(b.verbraucht_token.toLocaleString('de-DE') + ' / ' + b.grenze_token.toLocaleString('de-DE') + ' Token');
      if(typeof b.verbraucht_eur_cent === 'number' && typeof b.grenze_eur_cent === 'number') t.push((b.verbraucht_eur_cent / 100).toFixed(2).replace('.', ',') + ' / ' + (b.grenze_eur_cent / 100).toFixed(2).replace('.', ',') + ' €');
      return {prozent: Math.min(100, Math.max(0, Math.round(b.prozent))), text: t.join(' · '), stufe: b.stufe || 'ok'};
    }
    if(b.state || b.summary) return {prozent: null, text: [b.state, b.summary].filter(Boolean).join(' · '), stufe: b.state === 'gestoppt' ? 'gestoppt' : b.state === 'Warnung' ? 'warnung' : 'ok'};
    return null;
  }

  const firstLink = (o, type)=>((o.links || []).find(l=>l && l.type === type) || {}).id || null;

  const tool = {
    id: 'costs',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-costs');
      this.issue = ctx.object && ctx.object.type === 'issue' ? ctx.object.id : null;
      this.mission = this.issue ? null : ctx.object && ctx.object.id;
      this.agent = null;
      ctx.bus.on('task.changed', e=>{ if(e.id === this.mission) this.refresh(); });
      ctx.bus.on('live.line', e=>{ if(e.task_id === this.mission) this.refresh(); });
      ctx.bus.on('issue.changed', e=>{ if(this.issue && e.id === this.issue) this.refresh(); });
      ctx.bus.on('budget.warning', e=>{ if(this.issue && e.agent_id === this.agent) this.refresh(); });
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-costs'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      if(this.issue) return this.issueView();
      let v;
      try{ v = await this.ctx.api('/api/cost', {method: 'POST', body: {task_id: this.mission}}); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Kosten nicht lesbar: ' + err.message)); return; }
      const box = d().el('div', 's-col');
      const head = d().el('div', 's-row');
      const hole = d().el('div', 't-costs-hole');
      hole.setAttribute('aria-hidden', 'true');
      head.append(hole);
      const text = d().el('div');
      text.append(d().el('b', null, d().fmtNumber(v.tokens) + ' Token · ' + v.attempts + ' Aufruf' + (v.attempts === 1 ? '' : 'e')));
      const c = coins(v.tokens);
      text.append(d().el('div', 's-small s-muted', 'Kupfer ' + c.copper + ' · Silber ' + c.silver + ' · Gold ' + c.gold));
      text.append(d().el('div', 's-small s-muted', sourceText(v.quellen)));
      const cloud = cloudText(v);
      if(cloud) text.append(d().el('div', 's-small t-costs-cloud', cloud));
      head.append(text);
      box.append(head);

      if(v.note) box.append(d().el('div', 's-note', v.note));
      if(v.attempts){
        const t = d().el('table', 's-table');
        [['hinein', v.input_tokens], ['heraus', v.output_tokens]].forEach(([label, value])=>{
          const tr = d().el('tr');
          tr.append(d().el('td', 's-muted', label), d().el('td', null, d().fmtNumber(value) + ' Token'));
          t.append(tr);
        });
        if(typeof v.peak_fill === 'number'){
          const tr = d().el('tr');
          tr.append(d().el('td', 's-muted', 'vollster Kontext'), d().el('td', null, Math.round(v.peak_fill * 100) + ' %'));
          t.append(tr);
        }
        box.append(t);
      }
      if(v.today) box.append(d().el('small', 's-muted', 'Heute insgesamt: ' + d().fmtNumber(v.today.tokens) + ' Token in ' + v.today.runs + ' Läufen.'));
      box.append(d().el('small', 's-muted', 'Eine Kostengrenze gibt es noch nicht – sie wird gemessen, nicht geraten (Captain-Entscheidung, Build 9).'));
      this.el.replaceChildren(box);
    },

    // Neben einem Issue: das Budget des Bearbeiters (Desk-Typ `budget`) und die Token der verknüpften Mission über /api/cost
    async issueView(){
      const post = body=>this.ctx.api('/api/objects', {method: 'POST', body});
      let issue;
      try{ issue = await post({type: 'issue', id: this.issue}); }
      catch(err){
        const aus = String(err.message).indexOf('unknown_object_type') >= 0;
        this.el.replaceChildren(aus ? d().empty('Budget und Kosten eines Issues gibt es mit der Orchestrierung.') : d().el('div', 's-note bad', 'Issue nicht lesbar: ' + err.message));
        return;
      }
      const box = d().el('div', 's-col');
      this.agent = issue.bearbeiter || issue.assignee || firstLink(issue, 'agent');
      this.mission = issue.mission_id || firstLink(issue, 'task');
      if(!this.agent) box.append(d().el('small', 's-muted', 'Noch niemand zugewiesen – kein Budget.'));
      else{
        let b = null;
        try{ b = budgetText(await post({type: 'budget', id: this.agent})); }catch(_e){ b = null; }
        if(!b) box.append(d().el('small', 's-muted', 'Budget von ' + this.agent + ': noch keine Daten.'));
        else{
          const wrap = d().el('div', 't-costs-budget ' + b.stufe);
          wrap.append(d().el('small', 's-muted', 'Budget von ' + this.agent));
          if(b.prozent !== null){
            const track = d().el('div', 't-costs-track'), fill = d().el('div', 't-costs-fill');
            fill.style.width = b.prozent + '%';
            track.append(fill);
            wrap.append(track);
          }
          wrap.append(d().el('small', null, b.text));
          box.append(wrap);
        }
      }
      if(this.mission){
        try{
          const v = await this.ctx.api('/api/cost', {method: 'POST', body: {task_id: this.mission}});
          box.append(d().el('b', null, d().fmtNumber(v.tokens) + ' Token · ' + v.attempts + ' Aufruf' + (v.attempts === 1 ? '' : 'e') + ' im Lauf ' + this.mission));
          box.append(d().el('small', 's-muted', sourceText(v.quellen)));
          const cloud = cloudText(v);
          if(cloud) box.append(d().el('div', 's-small t-costs-cloud', cloud));
        }catch(err){ box.append(d().el('div', 's-note bad', 'Kosten des Laufs nicht lesbar: ' + err.message)); }
      }else box.append(d().el('small', 's-muted', 'Noch kein Lauf – noch keine Token.'));
      this.el.replaceChildren(box);
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraCostsPure = {coins, sourceText, cloudText, budgetText};
  if(typeof module !== 'undefined' && module.exports) module.exports = {coins, sourceText, cloudText, budgetText, tool};
})();
