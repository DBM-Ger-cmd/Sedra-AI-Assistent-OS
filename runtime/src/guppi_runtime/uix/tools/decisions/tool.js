// Werkzeug „Entscheidungen“ – the one place a decision is answered (COCKPIT_MODUL_v1 rule 2).
// Mission gates and change requests arrive in one shape from the desk (/api/decisions); the three ways are always the same words,
// and answering goes through the shell, so an answer given in the Gespräch and one given here do exactly the same thing.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const WAY_LABEL = {einmal: 'Einmal freigeben', freigeben_und_anwenden: 'Freigeben und anwenden', aendern: 'Grenze ändern …', ablehnen: 'Ablehnen'};

  const tool = {
    id: 'decisions',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-dec');
      ctx.bus.on('decision.pending', ()=>this.refresh());
      ctx.bus.on('decision.answered', ()=>this.refresh());
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-dec'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let view;
      try{ view = await this.ctx.api('/api/decisions'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Entscheidungen nicht lesbar: ' + err.message)); return; }
      this.items = view.items || [];
      const box = d().el('div', 's-col');
      box.append(d().el('h5', 's-head', 'Entscheidungen · ' + (this.items.length || 'keine')));
      if(!this.items.length){
        box.append(d().empty('Nichts wartet. Hier erscheint jede Freigabe – aus einer Aufgabe, aus der Werkstatt oder aus der Bibliothek.'));
      }
      this.items.forEach(item=>box.append(this.card(item)));
      this.el.replaceChildren(box);
    },

    card(item){
      const card = d().el('div', 's-note warn t-dec-card');
      card.append(d().el('b', null, item.title));
      card.append(d().el('div', 't-dec-what', item.describe || ''));
      if((item.risks || []).length) card.append(d().el('small', 's-muted', 'Risiken: ' + item.risks.join(', ')));
      if(item.note && item.note !== item.describe) card.append(d().el('small', 's-muted', item.note));
      const binding = item.binding || {};
      if(binding.block || binding.text){
        const det = d().el('details');
        det.append(d().el('summary', null, 'Genau dieser Text'));
        det.append(d().el('pre', 's-pre', binding.block || binding.text));
        card.append(det);
      }else if(binding.section || binding.key){
        card.append(d().el('small', 's-muted', [binding.section, binding.key].filter(Boolean).join('.') + ': ' + String(binding.old) + ' → ' + String(binding.new)));
      }
      const row = d().el('div', 's-row');
      (item.ways || []).forEach(way=>{
        row.append(d().button(WAY_LABEL[way] || way, async()=>{
          if(way !== 'ablehnen' && !confirm('Genau das einmal freigeben?\n\n' + item.title + '\n' + (item.describe || ''))) return;
          await this.ctx.shell.decide(item.id, way);
          await this.refresh();
        }, way === 'ablehnen' ? '' : 'p'));
      });
      if(item.mission_id) row.append(d().button('Aufgabe öffnen', ()=>this.ctx.shell.open({type: 'task', id: item.mission_id, title: item.title.slice(0, 40)})));
      card.append(row);
      return card;
    },

    // Die Entscheidung selbst wird in der Karte beantwortet; die Werkbank-Zeile bleibt hier leer (Regel 3: keine Navigation, keine Entscheidung).
    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
