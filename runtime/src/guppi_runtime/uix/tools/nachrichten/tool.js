// Werkzeug „Nachrichten“ (Fisch, 19.10.2026) – Profil und Brief aus gegebenen Quellen (Translator Fisch v0.1, Skill B, ohne Netz).
// Vertrag: nur im eigenen Container, nur ctx.api, kein Speicher (das Profil liegt im Projekt). Die Shell „Fisch“ reicht den Satz der
// Wolke als ctx.object.frage herein: er wird zu den Interessen dieses Briefs.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const TIEFEN = [['kurz', 'Kurz'], ['standard', 'Standard'], ['deep_dive', 'Deep Dive']];
  const BRIEFS = [['morning', 'Morning Brief'], ['wochenrueckblick', 'Wochenrückblick'], ['thema', 'Ein Thema']];
  const EBENEN = [['kurz', 'Kurz'], ['warum', 'Warum relevant?'], ['tiefe', 'Deep Dive'], ['quelle', 'Quelle']];

  function feld(label, el){ const l = d().el('label', 't-nw-feld'); l.append(d().el('span', null, label), el); return l; }

  const tool = {
    id: 'nachrichten',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-nachrichten');
      this.quellen = []; this.meldungen = []; this.offen = {};
      this.build((ctx.object || {}).frage || '');
      return this.ladeProfil();
    },

    unmount(){ this.el.classList.remove('t-nachrichten'); this.el.replaceChildren(); },

    build(frage){
      // Profil
      const profil = d().el('details', 't-nw-profil'); profil.open = !!frage || true;
      profil.append(d().el('summary', null, 'Profil – wofür der Brief gemacht wird'));
      this.interessen = d().el('input'); this.interessen.placeholder = 'Interessen, durch Komma: Local AI, Automatisierung, Handwerk';
      this.ausschluss = d().el('input'); this.ausschluss.placeholder = 'Weniger oder gar nicht: Promi, Sport …';
      this.region = d().el('input'); this.region.placeholder = 'DE/EU';
      this.tiefe = d().el('select'); TIEFEN.forEach(([v, l])=>{ const o = d().el('option', null, l); o.value = v; this.tiefe.append(o); });
      this.anzahl = d().el('input'); this.anzahl.type = 'number'; this.anzahl.min = '1'; this.anzahl.max = '20'; this.anzahl.value = '5';
      this.brief = d().el('select'); BRIEFS.forEach(([v, l])=>{ const o = d().el('option', null, l); o.value = v; this.brief.append(o); });
      const grid = d().el('div', 't-nw-grid');
      grid.append(feld('Interessen', this.interessen), feld('Ausschluss', this.ausschluss), feld('Region', this.region),
                  feld('Tiefe', this.tiefe), feld('Meldungen', this.anzahl), feld('Briefart', this.brief));
      this.profilStand = d().el('small', 's-muted', '');
      const prow = d().el('div', 't-nw-row');
      prow.append(d().button('Profil speichern', ()=>this.profilSpeichern(), ''), this.profilStand);
      profil.append(grid, prow);
      if(frage) this.interessen.value = frage;

      // Quellen
      const quellen = d().el('div', 't-nw-quellen');
      quellen.append(d().el('h5', 's-head', 'Quellen für diesen Brief'),
                     d().el('small', 's-muted', 'Der Translator hat kein Netz: er liest nur, was du hier hineinlegst – Meldungen, Mails, Notizen. Jede Meldung nennt ihre Quelle mit Namen.'));
      this.qName = d().el('input'); this.qName.placeholder = 'Name der Quelle, z. B. Pressemitteilung Firma A';
      this.qDatum = d().el('input'); this.qDatum.placeholder = 'Datum (frei)'; this.qDatum.size = 12;
      this.qText = d().el('textarea'); this.qText.rows = 4; this.qText.placeholder = 'Text der Quelle einfügen …';
      const qrow = d().el('div', 't-nw-row');
      qrow.append(this.qName, this.qDatum, d().button('Quelle hinzufügen', ()=>this.quelleHinzu(), ''));
      this.qListe = d().el('div', 't-nw-qliste');
      quellen.append(qrow, this.qText, this.qListe);

      this.go = d().button('Brief erstellen', ()=>this.briefErstellen(), 'p');
      const grow = d().el('div', 't-nw-row');
      grow.append(this.go, d().el('small', 's-muted', 'nur aus den Quellen oben · keine Mindestmenge · Unsicheres wird so genannt'));
      this.out = d().el('div', 't-nw-out'); this.out.setAttribute('aria-live', 'polite');
      this.el.replaceChildren(profil, quellen, grow, this.out);
      this.drawQuellen();
    },

    profilLesen(){
      return {interessen: this.interessen.value, ausschluss: this.ausschluss.value, region: this.region.value || 'DE/EU', sprache: 'de',
              tiefe: this.tiefe.value, max_items: parseInt(this.anzahl.value, 10) || 5, brief: this.brief.value};
    },

    async ladeProfil(){
      const r = await this.ctx.api('/api/fisch/profil').catch(()=>null);
      if(!r) return;
      const p = r.profil || {};
      if(!this.interessen.value) this.interessen.value = (p.interessen || []).join(', ');
      this.ausschluss.value = (p.ausschluss || []).join(', '); this.region.value = p.region || 'DE/EU';
      this.tiefe.value = p.tiefe || 'standard'; this.anzahl.value = String(p.max_items || 5); this.brief.value = p.brief || 'morning';
      this.profilStand.textContent = r.gespeichert ? 'gespeichert im Projekt' : 'noch nicht gespeichert';
    },

    async profilSpeichern(){
      try{
        await this.ctx.api('/api/fisch/profil/speichern', {method: 'POST', body: {profil: this.profilLesen()}});
        this.profilStand.textContent = 'gespeichert im Projekt';
      }catch(err){ this.profilStand.textContent = 'nicht gespeichert: ' + err.message; }
    },

    quelleHinzu(){
      const name = this.qName.value.trim(), text = this.qText.value.trim();
      if(!name || !text){ this.qName.focus(); return; }
      this.quellen.push({name, text, datum: this.qDatum.value.trim()});
      this.qName.value = ''; this.qText.value = ''; this.qDatum.value = '';
      this.drawQuellen();
    },

    drawQuellen(){
      this.qListe.replaceChildren(...this.quellen.map((q, i)=>{
        const row = d().el('div', 't-nw-quelle');
        row.append(d().el('b', null, q.name), d().el('small', 's-muted', (q.datum ? q.datum + ' · ' : '') + q.text.length + ' Zeichen'),
                   d().button('✕', ()=>{ this.quellen.splice(i, 1); this.drawQuellen(); }, ''));
        return row;
      }));
      if(!this.quellen.length) this.qListe.append(d().el('div', 's-note', 'Noch keine Quelle. Ohne Quelle gibt es keinen Brief – der Fisch erfindet nichts.'));
    },

    async briefErstellen(){
      if(!this.quellen.length){ this.out.replaceChildren(d().el('div', 's-note', 'Erst mindestens eine Quelle hineinlegen.')); return; }
      this.go.disabled = true;
      this.out.replaceChildren(d().el('div', 's-note t-nw-wartet', 'Der Translator liest die Quellen …'));
      try{
        const out = await this.ctx.api('/api/fisch/brief', {method: 'POST', body: {quellen: this.quellen, profil: this.profilLesen()}});
        this.out.replaceChildren(this.ergebnis(out));
      }catch(err){ this.out.replaceChildren(d().el('div', 's-note bad', 'Das hat nicht geklappt: ' + err.message)); }
      finally{ this.go.disabled = false; }
    },

    ergebnis(out){
      if(out.status === 'no_model') return d().el('div', 's-note bad', (out.message || 'Kein Modell geladen.') + ' In der Werkstatt ein Modell laden.');
      if(out.status !== 'completed') return d().el('div', 's-note bad', 'Das Modell hat nicht geantwortet: ' + (out.message || out.status));
      const box = d().el('div', 't-nw-brief');
      const items = out.meldungen || [];
      box.append(d().el('h5', 's-head', 'Brief · ' + items.length + (items.length === 1 ? ' Meldung' : ' Meldungen') + ' aus ' + (out.quellen || []).length + ' Quellen'));
      if(!items.length) box.append(d().el('div', 's-note', out.hinweis || 'Keine Meldung.'));
      items.forEach((m, i)=>box.append(this.meldung(m, i)));
      return box;
    },

    // Eine Meldung: vier Ebenen (Kurz · Warum relevant? · Deep Dive · Quelle) und „Warum zeigst du mir das?“
    meldung(m, i){
      const karte = d().el('div', 't-nw-meldung ' + (m.quelle_bekannt ? '' : 'unsicher'));
      const kopf = d().el('div', 't-nw-mkopf');
      kopf.append(d().el('b', null, m.titel), d().el('span', 't-nw-vertrauen ' + m.vertrauen, 'Vertrauen: ' + m.vertrauen));
      karte.append(kopf);
      const tabs = d().el('div', 't-nw-ebenen'); const body = d().el('div', 't-nw-ebene');
      const zeige = e=>{
        this.offen[i] = e;
        tabs.querySelectorAll('button').forEach(b=>b.classList.toggle('on', b.dataset.e === e));
        body.replaceChildren();
        if(e === 'quelle') body.append(d().el('div', null, m.quelle_bekannt ? 'Quelle: ' + m.quelle : 'Quelle „' + (m.quelle || '?') + '“ ist keine der gegebenen – diese Meldung ist unsicher.'));
        else body.append(d().el('div', null, m[e] || '–'));
      };
      EBENEN.forEach(([e, l])=>{ const b = d().button(l, ()=>zeige(e), ''); b.dataset.e = e; tabs.append(b); });
      karte.append(tabs, body);
      zeige(this.offen[i] || 'kurz');
      const warum = d().el('details', 't-nw-warum');
      warum.append(d().el('summary', null, 'Warum zeigst du mir das?'), d().el('div', null, m.warum || '–'));
      karte.append(warum);
      if((m.tags || []).length){ const tags = d().el('div', 't-nw-tags'); m.tags.forEach(t=>tags.append(d().el('span', null, t))); karte.append(tags); }
      return karte;
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
