// Werkzeug „Slots“ (Spec 4, D4.2.4): belegte und freie Plätze des Modellservers, die Läufe darauf und die Warteschlange.
// Die Seite steht über der Werkstatt (`model:alle`, order 5); Laden und Entladen bleibt dort – hier gibt es keine Verben.
// Gelesen wird `POST /api/objects {type:'model'}`; das Feld `slots` liefert Spec 2 (SCH-09). Fehlt es, sagt die Seite das ehrlich.
// Kein Zeitgeber: „seit“ ist eine Uhrzeit, keine mitlaufende Dauer; neu gelesen wird bei slot.changed, model.changed, agent.changed.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const PRIO = {captain: 'Captain', agent: 'Agent', routine: 'Routine'};

  // Eine Zeile je Slot 1..gesamt (rein): belegte mit ihrem Lauf, die übrigen frei
  function slotRows(slots){
    const s = slots || {};
    const belegt = new Map((s.belegt || []).map(b=>[Number(b.slot), b]));
    const n = Math.max(Number(s.gesamt) || 0, ...Array.from(belegt.keys()), 0);
    const rows = [];
    for(let i = 1; i <= n; i++) rows.push(belegt.has(i) ? Object.assign({zustand: 'belegt'}, belegt.get(i), {slot: i}) : {slot: i, zustand: 'frei'});
    return rows;
  }

  // Wartet ein Lauf länger als die Obergrenze? (rein; `jetzt` wird beim Zeichnen übergeben, kein Takt)
  function wartetZuLange(eintrag, warteMaxS, jetzt){
    const t = new Date((eintrag || {}).seit).getTime();
    if(!warteMaxS || isNaN(t)) return false;
    return (jetzt - t) / 1000 > Number(warteMaxS);
  }

  // Der Satz für den Zwischenzustand (rein): kein Modell, oder ein Modell ohne Scheduler
  function ohneSlots(items){
    const geladen = (items || []).find(m=>m.state === 'geladen');
    if(!geladen) return {text: 'Kein Modell geladen – Slots gibt es erst nach dem Laden (Werkstatt unten).', modell: null};
    return {text: 'Ein Modellserver, ein Platz. Parallele Slots kommen mit dem Scheduler (Spec 2).', modell: geladen};
  }

  const tool = {
    id: 'slots',

    mount(el, ctx){
      this.el = el; this.ctx = ctx; this.view = null; this.namen = new Map(); this.fehler = null;
      el.classList.add('t-slots');
      let running = null, again = false;
      this.schub = ()=>{
        if(running){ again = true; return running; }
        running = this.refresh().finally(()=>{ running = null; if(again){ again = false; this.schub(); } });
        return running;
      };
      ['slot.changed', 'model.changed', 'agent.changed', 'desk.resync'].forEach(n=>ctx.bus.on(n, ()=>this.schub()));
      return this.schub();
    },

    unmount(){ this.el.classList.remove('t-slots'); this.el.replaceChildren(); this.view = null; },

    async refresh(){
      if(!this.el) return;
      const post = body=>this.ctx.api('/api/objects', {method: 'POST', body});
      const agents = post({type: 'agent'}).catch(()=>null);
      try{ this.view = await post({type: 'model'}); this.fehler = null; }
      catch(err){ this.fehler = err.message || String(err); }
      const a = await agents;
      this.namen = new Map(((a || {}).items || []).map(x=>[String(x.id), String(x.title || x.id)]));
      this.draw();
    },

    open(object){ this.ctx.shell.open(object); },

    agentLink(id){
      if(!id) return d().el('span', 's-muted', '–');
      const name = this.namen.get(String(id)) || String(id);
      const link = d().el('span', 't-slots-link', name);
      d().clickable(link, ()=>this.open({type: 'agent', id: String(id), title: name}));
      return link;
    },

    draw(){
      const box = d().el('div', 's-col');
      if(this.fehler){
        box.append(d().el('div', 's-note bad', 'Die Modelle sind nicht lesbar: ' + this.fehler), d().button('Noch einmal lesen', ()=>this.schub()));
        return this.el.replaceChildren(box);
      }
      const items = (this.view && this.view.items) || [];
      const slots = this.view && this.view.slots;
      if(!slots || typeof slots !== 'object'){
        const z = ohneSlots(items);
        box.append(d().el('div', 's-note', z.text));
        if(z.modell) box.append(d().el('small', 's-muted', 'Läuft: ' + z.modell.summary));
        return this.el.replaceChildren(box);
      }
      const rows = slotRows(slots);
      const belegt = rows.filter(r=>r.zustand === 'belegt').length;
      const head = d().el('div', 's-row t-slots-head');
      head.append(d().el('b', null, slots.modell || 'Modell'), d().el('span', null, belegt + ' von ' + rows.length + ' Slots belegt'));
      const geladen = items.find(m=>m.state === 'geladen');
      if(geladen) head.append(d().el('small', 's-muted', geladen.summary));
      box.append(head);

      const t = d().el('table', 's-table t-slots-table');
      const th = d().el('tr');
      ['Slot', 'Zustand', 'Agent', 'Lauf', 'Priorität', 'seit'].forEach(h=>th.append(d().el('th', null, h)));
      t.append(th);
      rows.forEach(r=>{
        const tr = d().el('tr', 't-slots-row ' + r.zustand);
        tr.dataset.slot = String(r.slot);
        const agent = d().el('td'); agent.append(r.zustand === 'belegt' ? this.agentLink(r.agent_id) : d().el('span', 's-muted', ''));
        const lauf = d().el('td');
        if(r.zustand === 'belegt'){
          lauf.append(d().el('span', null, (r.titel || '') + (r.run_id ? ' · ' + r.run_id : '')));
          if(r.mission_id){ const m = d().el('span', 't-slots-link', ' Mission'); d().clickable(m, ()=>this.open({type: 'task', id: r.mission_id, title: r.titel || r.mission_id})); lauf.append(m); }
        }
        tr.append(d().el('td', null, String(r.slot)), d().el('td', 't-slots-state', r.zustand), agent, lauf,
                  d().el('td', null, r.zustand === 'belegt' ? (PRIO[r.prioritaet] || r.prioritaet || '–') : ''),
                  d().el('td', null, r.zustand === 'belegt' ? d().fmtTime(r.seit) : ''));
        t.append(tr);
      });
      box.append(t);

      const schlange = Array.isArray(slots.schlange) ? slots.schlange : [];
      box.append(d().el('h5', 's-head', 'Warteschlange · ' + schlange.length));
      if(!schlange.length) box.append(d().el('small', 's-muted', 'Kein Lauf wartet.'));
      const jetzt = Date.now();
      schlange.forEach((q, i)=>{
        const row = d().el('div', 's-row t-slots-queue');
        row.append(d().el('b', null, String(i + 1) + '.'), this.agentLink(q.agent_id), d().el('span', 's-muted', (PRIO[q.prioritaet] || q.prioritaet || '') + (q.run_id ? ' · ' + q.run_id : '')),
                   d().el('small', 's-muted', 'wartet seit ' + d().fmtTime(q.seit)));
        box.append(row);
        if(wartetZuLange(q, slots.warte_max_s, jetzt))
          box.append(d().el('div', 's-note warn', 'Wartet länger als ' + slots.warte_max_s + ' s' + (q.entscheidung || q.decision_id ? ' – Cloud-Vorschlag liegt im Posteingang.' : '.')));
      });
      this.el.replaceChildren(box);
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraSlotsPure = {slotRows, wartetZuLange, ohneSlots};
  if(typeof module !== 'undefined' && module.exports) module.exports = {slotRows, wartetZuLange, ohneSlots, tool};
})();
