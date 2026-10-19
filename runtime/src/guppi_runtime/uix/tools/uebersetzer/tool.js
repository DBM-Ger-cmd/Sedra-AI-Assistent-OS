// Werkzeug „Übersetzer“ (Fisch, 19.10.2026) – eine Nachricht für eine andere Rolle neu formulieren (Translator Fisch v0.1, Skill A).
// Vertrag: nur im eigenen Container, nur ctx.api, kein Speicher. Die Shell „Fisch“ reicht den Satz der Wolke als ctx.object.frage
// und die Rollen als ctx.object.von/nach herein; dann läuft die Übersetzung sofort. Sonst hat das Werkzeug ein eigenes Feld.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const TOENE = [['klar', 'klar'], ['freundlich', 'freundlich'], ['formell', 'formell']];
  const TIEFEN = [['kurz', 'kurz'], ['standard', 'standard'], ['ausfuehrlich', 'ausführlich']];

  const tool = {
    id: 'uebersetzer',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-uebersetzer');
      const o = ctx.object || {};
      this.von = o.von || 'alltag'; this.nach = o.nach || 'business';
      this.rollen = [];
      this.build(o.frage || '');
      return this.laden().then(()=>{ if(o.frage) return this.uebersetzen(); });
    },

    unmount(){ this.el.classList.remove('t-uebersetzer'); this.el.replaceChildren(); },

    async laden(){
      const r = await this.ctx.api('/api/fisch/rollen').catch(()=>({rollen: []}));
      this.rollen = r.rollen || [];
      [this.vonPick, this.nachPick].forEach((pick, i)=>{
        pick.replaceChildren(...this.rollen.map(x=>{ const op = d().el('option', null, x.name); op.value = x.id; op.title = x.hinweis; return op; }));
        pick.value = i === 0 ? this.von : this.nach;
      });
    },

    build(frage){
      const kopf = d().el('div', 't-ue-kopf');
      this.vonPick = d().el('select'); this.vonPick.setAttribute('aria-label', 'Von-Rolle');
      this.nachPick = d().el('select'); this.nachPick.setAttribute('aria-label', 'Zu-Rolle');
      const tausch = d().button('⇄', ()=>{ const a = this.vonPick.value; this.vonPick.value = this.nachPick.value; this.nachPick.value = a; }, '');
      tausch.title = 'Rollen tauschen';
      this.ton = d().el('select'); this.ton.setAttribute('aria-label', 'Ton');
      TOENE.forEach(([v, l])=>{ const op = d().el('option', null, l); op.value = v; this.ton.append(op); });
      this.tiefe = d().el('select'); this.tiefe.setAttribute('aria-label', 'Tiefe');
      TIEFEN.forEach(([v, l])=>{ const op = d().el('option', null, l); op.value = v; this.tiefe.append(op); });
      this.tiefe.value = 'standard';
      const feld = (text, sel)=>{ const l = d().el('label', 't-ue-feld', text); l.append(sel); return l; };
      kopf.append(feld('Von', this.vonPick), tausch, feld('Zu', this.nachPick), feld('Ton', this.ton), feld('Tiefe', this.tiefe));
      this.text = d().el('textarea'); this.text.rows = 4; this.text.value = frage;
      this.text.placeholder = 'Die Nachricht, die für die andere Rolle neu formuliert werden soll …';
      this.text.setAttribute('aria-label', 'Nachricht');
      this.text.onkeydown = e=>{ if(e.key === 'Enter' && (e.ctrlKey || e.metaKey)){ e.preventDefault(); this.uebersetzen(); } };
      this.go = d().button('Übersetzen', ()=>this.uebersetzen(), 'p');
      const row = d().el('div', 't-ue-row');
      row.append(this.go, d().el('small', 's-muted', 'Strg+Enter · Bedeutung bleibt, nichts wird erfunden, Unsicheres wird genannt'));
      this.out = d().el('div', 't-ue-out'); this.out.setAttribute('aria-live', 'polite');
      this.el.replaceChildren(kopf, this.text, row, this.out);
    },

    async uebersetzen(){
      const text = this.text.value.trim();
      if(!text){ this.out.replaceChildren(d().el('div', 's-note', 'Erst eine Nachricht eingeben.')); return; }
      this.go.disabled = true;
      this.out.replaceChildren(d().el('div', 's-note t-ue-wartet', 'Der Fisch denkt nach …'));
      try{
        const body = {text, von: this.vonPick.value || this.von, nach: this.nachPick.value || this.nach, ton: this.ton.value, tiefe: this.tiefe.value};
        const out = await this.ctx.api('/api/fisch/uebersetzen', {method: 'POST', body});
        this.out.replaceChildren(this.ergebnis(out, body));
      }catch(err){ this.out.replaceChildren(d().el('div', 's-note bad', 'Das hat nicht geklappt: ' + err.message)); }
      finally{ this.go.disabled = false; }
    },

    ergebnis(out, body){
      if(out.status === 'no_model') return d().el('div', 's-note bad', (out.message || 'Kein Modell geladen.') + ' In der Werkstatt ein Modell laden.');
      if(out.status !== 'completed') return d().el('div', 's-note bad', 'Das Modell hat nicht geantwortet: ' + (out.message || out.status));
      const name = id=>((this.rollen.find(r=>r.id === id) || {}).name) || id;
      const box = d().el('div', 't-ue-ergebnis');
      box.append(d().el('div', 't-ue-weg', name(body.von) + ' → ' + name(body.nach)));
      box.append(d().el('div', 't-ue-text', out.uebersetzung || ''));
      if(!out.format_ok) box.append(d().el('small', 's-muted', 'Das Modell hat nicht im erwarteten Format geantwortet – oben steht seine ganze Antwort, nichts wurde ergänzt.'));
      if((out.unsicherheiten || []).length){
        const u = d().el('div', 't-ue-liste warn'); u.append(d().el('b', null, 'Unsicher oder fehlend'));
        out.unsicherheiten.forEach(x=>u.append(d().el('div', null, '· ' + x)));
        box.append(u);
      }
      if((out.hinweise || []).length){
        const h = d().el('div', 't-ue-liste'); h.append(d().el('b', null, 'Hinweise'));
        out.hinweise.forEach(x=>h.append(d().el('div', null, '· ' + x)));
        box.append(h);
      }
      if(out.truncated) box.append(d().el('small', 's-muted', 'Die Antwort wurde abgeschnitten (Längenlimit).'));
      const fuss = d().el('div', 't-ue-row');
      fuss.append(d().button('Kopieren', ()=>{ try{ navigator.clipboard.writeText(out.uebersetzung || ''); }catch(_e){} }, ''),
                  d().el('small', 's-muted', 'Modell ' + (out.model || '') + ' · lokal, durch den Inhaltsschutz'));
      box.append(fuss);
      return box;
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
