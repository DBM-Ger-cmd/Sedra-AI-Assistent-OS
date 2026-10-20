// Werkzeug „Transkript“ (Fisch, 19.10.2026) – nach LocalScribe (Import, Suche, Export) und VoiceBrief (Record, Versionen, Golden Record).
// Vertrag: nur im eigenen Container, nur ctx.api, kein Speicher. Die Shell „Fisch“ reicht den Satz der Wolke als ctx.object.frage
// herein: er wird die Suche im geöffneten Transkript. Ein Objekt mit einer Transkript-Kennung (T-…) öffnet diesen Record direkt
// (so führt der Rekorder her). Sprache → Text ist Sache des Kerns (sprache/): das Werkzeug zeigt nur die Auskunft. SEDRA-KI-Zugang:
// „Erkenntnisse mit SEDRA“ liest die Fassung (Zusammenfassung, Entscheidungen, offene Fragen, Aufgaben – an die Fassung gebunden).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const STATUS = {entwurf: ['Entwurf', 'muted'], geprueft: ['Geprüft', 'ok'], freigegeben: ['Freigegeben · Golden Record', 'done']};
  const SPRACHEN = [['de', 'Deutsch'], ['en', 'Englisch'], ['fr', 'Französisch'], ['es', 'Spanisch'], ['it', 'Italienisch']];

  function zeit(s){ const m = Math.floor(s / 60), r = Math.floor(s % 60); return String(m).padStart(2, '0') + ':' + String(r).padStart(2, '0'); }
  function pill(text, tone){ return d().el('span', 't-tk-pill ' + (tone || 'muted'), text); }

  const tool = {
    id: 'transkript',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-transkript');
      this.frage = (ctx.object || {}).frage || '';
      this.direkt = /^T-[0-9A-F]{8}$/.test(String((ctx.object || {}).id || '')) ? ctx.object.id : null;
      this.offen = null; this.treffer = null;
      this.build();
      return this.liste();
    },

    unmount(){ this.el.classList.remove('t-transkript'); this.el.replaceChildren(); },

    build(){
      this.listeBox = d().el('div', 't-tk-liste');
      this.detail = d().el('div', 't-tk-detail');
      this.el.replaceChildren(this.listeBox, this.detail);
    },

    async liste(){
      try{
        const r = await this.ctx.api('/api/fisch/transkripte');
        this.alle = r.transkripte || []; this.stt = r.stt || {};
        this.drawListe();
        if(this.direkt && !this.offen){ const id = this.direkt; this.direkt = null; await this.oeffnen(id); }
        else if(this.frage && this.alle.length && !this.offen) await this.oeffnen(this.alle[0].id);
        else if(!this.offen) this.drawDetail();
      }catch(err){ this.listeBox.replaceChildren(d().el('div', 's-note bad', 'Transkripte nicht lesbar: ' + err.message)); }
    },

    drawListe(){
      const box = this.listeBox; box.replaceChildren();
      box.append(d().el('h5', 's-head', 'Transkripte · ' + this.alle.length));
      if(this.stt && this.stt.status !== 'bereit') box.append(d().el('div', 's-note t-tk-stt', 'Sprache → Text: ' + this.stt.note + (this.stt.install ? ' (' + this.stt.install + ')' : '')));
      else if(this.stt) box.append(d().el('div', 's-note t-tk-stt', 'Sprache → Text: ' + this.stt.provider + ' ist da – aufnehmen im Rekorder.'));
      this.alle.forEach(t=>{
        const row = d().el('div', 't-tk-row' + (this.offen && this.offen.id === t.id ? ' on' : ''));
        row.append(d().el('b', null, t.titel), d().el('small', 's-muted', t.sprache + ' · ' + t.cues + ' Cues · Fassung ' + t.aktuell + (t.geschaetzt ? ' · Zeiten geschätzt' : '')),
                   pill(STATUS[t.status][0], STATUS[t.status][1]));
        d().clickable(row, ()=>this.oeffnen(t.id));
        box.append(row);
      });
      box.append(this.importForm());
    },

    importForm(){
      const f = d().el('details', 't-tk-import'); f.open = !this.alle.length;
      f.append(d().el('summary', null, 'Importieren – TXT, SRT oder VTT'));
      const titel = d().el('input'); titel.placeholder = 'Titel, z. B. Kundengespräch 19.10.';
      const quelle = d().el('input'); quelle.placeholder = 'Herkunft (Dateiname, frei)';
      const sprache = d().el('select'); SPRACHEN.forEach(([v, l])=>{ const o = d().el('option', null, l); o.value = v; sprache.append(o); });
      const text = d().el('textarea'); text.rows = 6; text.placeholder = 'Den Text oder die SRT/VTT-Untertitel hier einfügen …';
      const stand = d().el('small', 's-muted', 'Die Sprache ist deine Angabe – wie bei LocalScribe steht sie vor jedem Modell. Reiner Text bekommt geschätzte Zeiten.');
      const go = d().button('Importieren', async()=>{
        if(!titel.value.trim() || !text.value.trim()){ stand.textContent = 'Titel und Text sind nötig.'; return; }
        try{
          const made = await this.ctx.api('/api/fisch/transkript/import', {method: 'POST', body: {titel: titel.value.trim(), text: text.value, sprache: sprache.value, quelle: quelle.value.trim()}});
          titel.value = ''; text.value = ''; quelle.value = '';
          await this.liste(); await this.oeffnen(made.id);
        }catch(err){ stand.textContent = 'Import fehlgeschlagen: ' + err.message; }
      }, 'p');
      const row = d().el('div', 't-tk-row2'); row.append(titel, sprache, quelle);
      const row2 = d().el('div', 't-tk-row2'); row2.append(go, stand);
      f.append(row, text, row2);
      return f;
    },

    async oeffnen(id){
      try{
        this.offen = await this.ctx.api('/api/fisch/transkript', {method: 'POST', body: {id}});
        this.treffer = null;
        this.drawListe(); this.drawDetail();
        if(this.frage){ const q = this.frage; this.frage = ''; this.suchfeld.value = q; await this.suchen(); }
      }catch(err){ this.detail.replaceChildren(d().el('div', 's-note bad', 'Transkript nicht lesbar: ' + err.message)); }
    },

    drawDetail(){
      const t = this.offen, box = this.detail; box.replaceChildren();
      if(!t){ box.append(d().el('div', 's-note', 'Links ein Transkript wählen oder eines importieren.')); return; }
      const kopf = d().el('div', 't-tk-kopf');
      kopf.append(d().el('div', 't-tk-titel', t.titel), pill(STATUS[t.status][0], STATUS[t.status][1]),
                  d().el('small', 's-muted', 'Fassung ' + t.fassung.version + ' (' + t.fassung.herkunft + ') · ' + t.cues.length + ' Cues · ' + t.sprache + (t.quelle ? ' · ' + t.quelle : '')));
      box.append(kopf);

      // Handlungen des Records: der Weg Entwurf → geprüft → freigegeben; pseudonymisieren nur vor der Freigabe; Export immer
      const verbs = d().el('div', 't-tk-verbs');
      if(t.status !== 'freigegeben'){
        verbs.append(d().button('Pseudonymisieren', ()=>this.tun('/api/fisch/transkript/pseudonymisieren', {id: t.id}, 'Neue Fassung mit Platzhaltern; das Mapping liegt getrennt, nie im Export.'), ''));
        if(t.status === 'entwurf') verbs.append(d().button('Als geprüft markieren', ()=>this.tun('/api/fisch/transkript/status', {id: t.id, status: 'geprueft'}), ''));
        if(t.status === 'geprueft') verbs.append(d().button('Freigeben (Golden Record)', ()=>this.tun('/api/fisch/transkript/status', {id: t.id, status: 'freigegeben'}, 'Die Fassung wird eingefroren; danach gibt es keine neue Fassung mehr.'), 'p'));
      }else{
        verbs.append(d().button('Freigabe zurücknehmen', ()=>this.tun('/api/fisch/transkript/status', {id: t.id, status: 'entwurf'}, 'Der Record wird wieder ein Entwurf.'), ''));
      }
      ['txt', 'srt', 'vtt', 'json', 'md'].forEach(f=>verbs.append(d().button((f === 'md' ? 'Protokoll (MD)' : 'Export ' + f.toUpperCase()), ()=>this.exportieren(f), '')));
      box.append(verbs);
      this.meldung = d().el('div', 't-tk-meldung'); box.append(this.meldung);
      box.append(this.erkenntnisse(t));

      // Fassungen
      const vs = d().el('div', 't-tk-versionen');
      t.versionen.forEach(v=>{
        const b = d().button('Fassung ' + v.version + ' · ' + v.herkunft + (v.mapping ? ' (Mapping getrennt)' : ''), ()=>this.fassung(v.version), v.version === t.fassung.version ? 'p' : '');
        vs.append(b);
      });
      box.append(vs);

      // Suche
      const such = d().el('div', 't-tk-such');
      this.suchfeld = d().el('input'); this.suchfeld.placeholder = 'Suchen – ganze Wörter, in Reihenfolge';
      this.suchfeld.onkeydown = e=>{ if(e.key === 'Enter') this.suchen(); };
      such.append(this.suchfeld, d().button('Suchen', ()=>this.suchen(), ''));
      this.suchStand = d().el('small', 's-muted', ''); such.append(this.suchStand);
      box.append(such);

      // Cues
      this.cueBox = d().el('div', 't-tk-cues');
      this.drawCues();
      box.append(this.cueBox);
    },

    drawCues(){
      const t = this.offen, hit = new Set((this.treffer || []).map(x=>x.cue));
      this.cueBox.replaceChildren(...t.cues.map((c, i)=>{
        const row = d().el('div', 't-tk-cue' + (hit.has(i) ? ' hit' : ''));
        row.append(d().el('span', 't-tk-zeit', zeit(c.start) + '–' + zeit(c.end)), d().el('span', 't-tk-text', c.text));
        return row;
      }));
    },

    // ---- SEDRA-KI-Zugang: die Erkenntnis aus der Fassung – gebunden an ihre Fassung (VoiceBrief), gespeichert am Record
    erkenntnisse(t){
      const box = d().el('section', 't-tk-erk'); box.setAttribute('aria-label', 'Erkenntnisse');
      const kopf = d().el('div', 't-tk-erk-kopf');
      kopf.append(d().el('b', null, 'Erkenntnisse mit SEDRA'),
                  d().button(t.erkenntnisse ? 'Neu lesen' : 'Fassung lesen', ()=>this.erkennen(t), t.erkenntnisse ? '' : 'p'),
                  d().button('An den Übersetzer', ()=>this.ctx.shell.open({type: 'uebersetzung', id: 'wolke', title: 'Übersetzen', frage: t.erkenntnisse ? t.erkenntnisse.zusammenfassung : t.cues.map(c=>c.text).join(' ').slice(0, 2000)}), ''));
      box.append(kopf);
      this.erkStand = d().el('small', 's-muted', t.erkenntnisse ? '' : 'SEDRA liest die Fassung lokal: Zusammenfassung, Entscheidungen, offene Fragen, Aufgaben. Nichts wird erfunden.');
      box.append(this.erkStand);
      const e = t.erkenntnisse;
      if(!e) return box;
      if(e.version !== t.fassung.version) box.append(d().el('div', 's-note warn', 'Aus Fassung ' + e.version + ' – die gezeigte ist Fassung ' + t.fassung.version + '. „Neu lesen“ bindet sie an diese.'));
      box.append(d().el('p', 't-tk-erk-text', e.zusammenfassung || '–'));
      const block = (titel, items, mitAuftrag)=>{
        const b = d().el('div', 't-tk-erk-block'); b.append(d().el('h6', null, titel + ' · ' + items.length));
        if(!items.length) b.append(d().el('small', 's-muted', 'keine'));
        items.forEach(text=>{
          const row = d().el('div', 't-tk-erk-row'); row.append(d().el('span', null, text));
          if(mitAuftrag) row.append(d().button('Als Auftrag anlegen', ()=>this.auftrag(text), ''));
          b.append(row);
        });
        return b;
      };
      box.append(block('Entscheidungen', e.entscheidungen || [], false), block('Offene Fragen', e.offen || [], false), block('Aufgaben', e.aufgaben || [], true));
      box.append(d().el('small', 's-muted', 'Modell ' + e.model + ' · ' + String(e.at || '').slice(0, 16).replace('T', ' ') + (e.truncated ? ' · Antwort abgeschnitten' : '')));
      return box;
    },

    async erkennen(t){
      this.erkStand.textContent = 'SEDRA liest …';
      try{
        const r = await this.ctx.api('/api/fisch/transkript/erkenntnisse', {method: 'POST', body: {id: t.id}});
        if(r.status !== 'completed'){ this.erkStand.textContent = r.status === 'no_model' ? 'Kein Modell geladen – in der Werkstatt eines laden.' : 'Das ging nicht: ' + r.message; return; }
        await this.oeffnen(t.id);
      }catch(err){ this.erkStand.textContent = 'Das ging nicht: ' + err.message; }
    },

    async auftrag(text){
      try{
        const m = ((await this.ctx.api('/api/chat', {method: 'POST', body: {intent: text}})) || {}).mission || {};
        this.meldung.textContent = 'Auftrag angelegt – geplant, nicht ausgeführt: ' + String(m.intent || text).slice(0, 80);
        this.ctx.shell.open({type: 'task', id: m.mission_id, title: String(m.intent || 'Aufgabe').slice(0, 40)});
      }catch(err){ this.meldung.textContent = 'Auftrag ging nicht: ' + err.message; }
    },

    async fassung(version){
      this.offen = await this.ctx.api('/api/fisch/transkript', {method: 'POST', body: {id: this.offen.id, version}});
      this.treffer = null; this.drawDetail();
    },

    async suchen(){
      const q = this.suchfeld.value.trim();
      if(!q){ this.treffer = null; this.suchStand.textContent = ''; this.drawCues(); return; }
      const r = await this.ctx.api('/api/fisch/transkript/suche', {method: 'POST', body: {id: this.offen.id, frage: q}});
      this.treffer = r.treffer || [];
      this.suchStand.textContent = this.treffer.length + (this.treffer.length === 1 ? ' Treffer' : ' Treffer') + ' für „' + q + '“';
      this.drawCues();
      const first = this.cueBox.querySelector('.hit'); if(first && first.scrollIntoView) first.scrollIntoView({block: 'nearest'});
    },

    async tun(route, body, confirmText){
      if(confirmText && typeof confirm === 'function' && !confirm(confirmText)) return;
      try{
        const r = await this.ctx.api(route, {method: 'POST', body});
        await this.liste(); await this.oeffnen(body.id);
        if(r.funde !== undefined) this.meldung.textContent = 'Fassung ' + r.version + ' angelegt · ' + r.funde + ' Stellen durch Platzhalter ersetzt.';
      }catch(err){ this.meldung.textContent = 'Das ging nicht: ' + err.message; }
    },

    async exportieren(fmt){
      try{
        const r = await this.ctx.api('/api/fisch/transkript/export', {method: 'POST', body: {id: this.offen.id, format: fmt}});
        this.meldung.replaceChildren(d().el('span', null, 'Exportiert nach ' + r.datei + ' (Fassung ' + r.version + (r.vorlaeufig ? ', vorläufig – noch nicht freigegeben' : ', freigegeben') + '). '),
                                     d().button('Kopieren', ()=>{ try{ navigator.clipboard.writeText(r.inhalt); }catch(_e){} }, ''));
      }catch(err){ this.meldung.textContent = 'Export fehlgeschlagen: ' + err.message; }
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
