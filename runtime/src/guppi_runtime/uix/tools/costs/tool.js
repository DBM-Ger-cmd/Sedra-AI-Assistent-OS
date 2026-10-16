// Werkzeug „Kosten“ – das Münzloch (COCKPIT_MODUL_v1 Regel 5, vierter Nachweis).
// Was diese Aufgabe gekostet hat, und woher die Zahl kommt: vom Anbieter gemeldet oder geschätzt. Beides wird nie vermischt –
// eine Schätzung, die wie eine Messung aussieht, wäre schlimmer als keine Zahl.

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

  const tool = {
    id: 'costs',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-costs');
      this.mission = ctx.object && ctx.object.id;
      ctx.bus.on('task.changed', e=>{ if(e.id === this.mission) this.refresh(); });
      ctx.bus.on('live.line', e=>{ if(e.task_id === this.mission) this.refresh(); });
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-costs'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
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

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraCostsPure = {coins, sourceText};
  if(typeof module !== 'undefined' && module.exports) module.exports = {coins, sourceText};
})();
