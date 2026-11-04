// Werkzeug „Entscheidungen“ – the one place a decision is answered (COCKPIT_MODUL_v1 rule 2).
// Mission gates and change requests arrive in one shape from the desk (/api/decisions); the three ways are always the same words,
// and answering goes through the shell, so an answer given in the Gespräch and one given here do exactly the same thing.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const WAY_LABEL = {einmal: 'Einmal freigeben', freigeben_und_anwenden: 'Freigeben und anwenden', aendern: 'Grenze ändern …', ablehnen: 'Ablehnen', cloud_diesen_lauf: 'Nur diesen Lauf in die Cloud', bestaetigen: 'Entsperren'};

  const KIND_LABEL = {harness_code_stand: 'Code-Stand übernehmen', harness_projekt: 'Ordner als Projekt öffnen', harness_katalog: 'Freigabe-Regeln des Harness ändern', harness_vorlage: 'Grenzen einer Vorlage ändern', harness_aufgabe: 'Aufgabe für eine Sitzung freigeben'};

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
      const stand = JSON.stringify(this.items.map(x=>[x.id, x.title, x.ways]));
      if(stand === this._stand && this.el.firstChild) return;          // nichts Neues: die Stelle, an der man liest, und ein halber „Sicher?“-Klick bleiben
      this._stand = stand;
      const oben = this.el.scrollTop;
      const box = d().el('div', 's-col');
      box.append(d().el('h5', 's-head', 'Entscheidungen · ' + (this.items.length || 'keine')));
      if(!this.items.length){
        box.append(d().empty('Nichts wartet. Hier erscheint jede Freigabe – aus einer Aufgabe, aus der Werkstatt oder aus der Bibliothek.'));
      }
      this.items.forEach(item=>box.append(this.card(item)));
      this.el.replaceChildren(box);
      this.el.scrollTop = oben;
    },

    card(item){
      const card = d().el('div', 's-note warn t-dec-card');
      card.append(d().el('b', null, item.title));
      const art = KIND_LABEL[String(item.kind || '').replace('request:', '')] || ''; if(art) card.append(d().el('small', 's-muted', art));
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
        // Zweiter Klick statt confirm(): ein Browser-Dialog wird in eingebetteten Fenstern (Pane, App-Fenster) unterdrückt und antwortet dort
        // still mit „Nein“ – der Knopf tat dann nichts (Modellserver gesperrt, 1.11.2026: „lässt sich nicht entsperren“).
        const label = WAY_LABEL[way] || way;
        const knopf = d().button(label, async()=>{
          if(way !== 'ablehnen' && !knopf.dataset.sicher){
            knopf.dataset.sicher = '1'; knopf.textContent = 'Sicher? ' + label;
            setTimeout(()=>{ if(knopf.isConnected){ delete knopf.dataset.sicher; knopf.textContent = label; } }, 5000);
            return;
          }
          await this.ctx.shell.decide(item.id, way);
          await this.refresh();
        }, way === 'ablehnen' ? '' : 'p');
        row.append(knopf);
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
