// Werkzeug „Rekorder“ (Kern Sprache, 19.10.2026) – aufnehmen, abspielen, Sprache → Text. Für jede Shell: es zeichnet den Typ
// `aufnahme`. Das Mikrofon kommt aus ui/sprache.js (sedraSprache), die Stücke gehen über ctx.api an den Kern. Ohne Provider auf
// dem Rechner sagt das Werkzeug das und zeigt den Installationsbefehl; die Abschrift von Hand ist der ehrliche Weg bis dahin.
// Vertrag: nur im eigenen Container, nur ctx.api, kein Speicher, kein eigenes fetch.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const SPRACHEN = [['de', 'Deutsch'], ['en', 'Englisch'], ['fr', 'Französisch'], ['es', 'Spanisch'], ['it', 'Italienisch']];
  const STT = {offen: ['noch kein Text', 'muted'], laeuft: ['Sprache → Text läuft …', 'warn'], fertig: ['Transkript da', 'ok'], fehler: ['Fehler', 'bad']};

  function zeit(s){ s = Math.max(0, Math.floor(s || 0)); return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0'); }
  function pill(text, tone){ return d().el('span', 't-rk-pill ' + (tone || 'muted'), text); }

  const tool = {
    id: 'rekorder',

    mount(el, ctx){
      this.el = el; this.ctx = ctx; this.griff = null; this.alle = []; this.stt = null; this.offen = null;
      el.classList.add('t-rekorder');
      this.build();
      return this.laden();
    },

    unmount(){
      clearInterval(this.poll);
      if(this.griff){ this.griff.abbrechen().catch(()=>{}); this.griff = null; }
      this.el.classList.remove('t-rekorder'); this.el.replaceChildren();
    },

    build(){
      this.stand = d().el('div', 't-rk-stand');
      this.pult = d().el('section', 't-rk-pult'); this.pult.setAttribute('aria-label', 'Aufnahme');
      this.liste = d().el('section', 't-rk-liste'); this.liste.setAttribute('aria-label', 'Aufnahmen');
      this.el.replaceChildren(this.stand, this.pult, this.liste);
      this.drawPult();
    },

    async laden(){
      try{
        const r = await this.ctx.api('/api/sprache/aufnahmen');
        this.alle = r.aufnahmen || []; this.stt = r.stt || null;
        this.drawStand(); this.drawListe();
        const laeuft = this.alle.some(a=>a.stt && a.stt.status === 'laeuft');
        clearInterval(this.poll); this.poll = laeuft ? setInterval(()=>this.laden(), 3000) : null;
      }catch(err){ this.stand.replaceChildren(d().el('div', 's-note bad', 'Aufnahmen nicht lesbar: ' + err.message)); }
    },

    // ---- Die Auskunft zum Provider: ehrlich, mit Befehl
    drawStand(){
      const s = this.stt; this.stand.replaceChildren();
      if(!s) return;
      const row = d().el('div', 't-rk-provider ' + (s.status === 'bereit' ? 'ok' : 'warn'));
      row.append(d().el('b', null, s.status === 'bereit' ? 'Sprache → Text: ' + s.provider + ' (' + s.modell + ', ' + s.geraet + ')' : 'Sprache → Text: kein Provider'),
                 d().el('span', null, s.note));
      if(s.status !== 'bereit' && s.install) row.append(d().el('code', 't-rk-install', s.install));
      this.stand.append(row);
    },

    // ---- Das Pult: Titel, Sprache, der Knopf, Uhr und Pegel
    drawPult(){
      const p = this.pult; p.replaceChildren();
      const k = root.sedraSprache ? root.sedraSprache.kann() : {ok: false, grund: 'ui/sprache.js fehlt.'};
      const zeile = d().el('div', 't-rk-zeile');
      this.titel = d().el('input'); this.titel.placeholder = 'Titel, z. B. Teamrunde 19.10.'; this.titel.setAttribute('aria-label', 'Titel');
      this.sprache = d().el('select'); this.sprache.setAttribute('aria-label', 'Sprache');
      SPRACHEN.forEach(([v, l])=>{ const o = d().el('option', null, l); o.value = v; this.sprache.append(o); });
      zeile.append(this.titel, this.sprache);
      const mitte = d().el('div', 't-rk-mitte');
      this.knopf = d().el('button', 't-rk-knopf', 'Aufnehmen'); this.knopf.type = 'button'; this.knopf.setAttribute('aria-label', 'Aufnahme starten');
      this.knopf.onclick = ()=>this.griff ? this.stop() : this.start();
      this.uhr = d().el('div', 't-rk-uhr', '00:00'); this.uhr.setAttribute('aria-live', 'off');
      this.pegel = d().el('div', 't-rk-pegel'); this.pegel.setAttribute('aria-hidden', 'true');
      for(let i = 0; i < 12; i++) this.pegel.append(d().el('span', 't-rk-balken'));
      mitte.append(this.knopf, this.uhr, this.pegel);
      const verbs = d().el('div', 't-rk-verbs');
      this.pauseBtn = d().button('Pause', ()=>this.pause(), ''); this.pauseBtn.disabled = true;
      this.abbrBtn = d().button('Verwerfen', ()=>this.abbrechen(), ''); this.abbrBtn.disabled = true;
      verbs.append(this.pauseBtn, this.abbrBtn);
      this.meldung = d().el('div', 't-rk-meldung', k.ok ? 'Die Aufnahme bleibt im Projekt (sprache/aufnahmen). Kein Netz.' : k.grund);
      if(!k.ok) this.knopf.disabled = true;
      p.append(zeile, mitte, verbs, this.meldung);
    },

    zeichnePegel(v){
      const n = Math.round((v || 0) * 12);
      Array.from(this.pegel.children).forEach((b, i)=>b.classList.toggle('on', i < n));
    },

    async start(){
      try{
        this.knopf.disabled = true;
        this.griff = await root.sedraSprache.aufnehmen(this.ctx.api, {
          titel: this.titel.value.trim(), sprache: this.sprache.value,
          onStand: s=>{ this.uhr.textContent = zeit(s.sekunden); this.zeichnePegel(s.pegel); this.meldung.textContent = (s.status === 'pause' ? 'Pause · ' : '') + d().fmtBytes(s.groesse) + ' · ' + s.stuecke + ' Stücke gesichert'; },
          onFehler: text=>{ this.meldung.textContent = 'Ein Stück kam nicht an: ' + text; }
        });
        this.pult.classList.add('laeuft'); this.knopf.textContent = 'Stopp'; this.knopf.setAttribute('aria-label', 'Aufnahme beenden');
        this.pauseBtn.disabled = false; this.abbrBtn.disabled = false; this.knopf.disabled = false;
      }catch(err){ this.griff = null; this.knopf.disabled = false; this.meldung.textContent = 'Keine Aufnahme: ' + err.message; }
    },

    pause(){
      if(!this.griff) return;
      const s = this.griff.stand();
      if(s.status === 'pause'){ this.griff.weiter(); this.pauseBtn.textContent = 'Pause'; this.pult.classList.remove('pause'); }
      else{ this.griff.pause(); this.pauseBtn.textContent = 'Weiter'; this.pult.classList.add('pause'); }
    },

    fertigPult(){
      this.pult.classList.remove('laeuft', 'pause'); this.knopf.textContent = 'Aufnehmen'; this.knopf.setAttribute('aria-label', 'Aufnahme starten');
      this.pauseBtn.disabled = true; this.pauseBtn.textContent = 'Pause'; this.abbrBtn.disabled = true; this.zeichnePegel(0); this.griff = null;
    },

    async stop(){
      const g = this.griff; if(!g) return;
      this.knopf.disabled = true;
      try{
        const a = await g.stop();
        this.fertigPult(); this.meldung.textContent = 'Gesichert: „' + a.titel + '“ · ' + zeit(a.dauer) + ' · ' + d().fmtBytes(a.groesse);
        this.titel.value = ''; this.offen = a.id;
        await this.laden();
      }catch(err){ this.fertigPult(); this.meldung.textContent = 'Nicht gesichert: ' + err.message; await this.laden(); }
      this.knopf.disabled = false;
    },

    async abbrechen(){
      const g = this.griff; if(!g) return;
      await g.abbrechen(); this.fertigPult(); this.uhr.textContent = '00:00'; this.meldung.textContent = 'Verworfen – nichts gespeichert.';
      await this.laden();
    },

    // ---- Die Liste: je Aufnahme eine Karte; die geöffnete zeigt Abspielen, Sprache → Text und Abschrift
    drawListe(){
      const box = this.liste; box.replaceChildren();
      box.append(d().el('h5', 's-head', 'Aufnahmen · ' + this.alle.length));
      if(!this.alle.length){ box.append(d().el('div', 's-note', 'Noch keine Aufnahme. Oben „Aufnehmen“ – der Browser fragt einmal nach dem Mikrofon.')); return; }
      this.alle.forEach(a=>box.append(this.karte(a)));
    },

    karte(a){
      const k = d().el('article', 't-rk-karte' + (this.offen === a.id ? ' on' : ''));
      const kopf = d().el('div', 't-rk-karte-kopf');
      kopf.append(d().el('b', null, a.titel), d().el('small', 's-muted', zeit(a.dauer) + ' · ' + d().fmtBytes(a.groesse) + ' · ' + a.sprache + ' · ' + String(a.created_at || '').slice(0, 16).replace('T', ' ')),
                  pill(STT[a.stt.status][0], STT[a.stt.status][1]));
      d().clickable(kopf, ()=>{ this.offen = this.offen === a.id ? null : a.id; this.drawListe(); });
      k.append(kopf);
      if(this.offen !== a.id) return k;
      const verbs = d().el('div', 't-rk-verbs');
      verbs.append(d().button('Abspielen', ()=>this.abspielen(a, k), ''));
      if(a.stt.status === 'fertig' && a.transkript_id) verbs.append(d().button('Transkript öffnen', ()=>this.ctx.shell.open({type: 'transkript', id: a.transkript_id, title: a.titel}), 'p'));
      else if(a.stt.status !== 'laeuft' && this.stt && this.stt.status === 'bereit') verbs.append(d().button('Sprache → Text (' + this.stt.provider + ')', ()=>this.transkribieren(a, {}), 'p'));
      verbs.append(d().button('Löschen', ()=>this.loeschen(a), ''));
      k.append(verbs);
      if(a.stt.status === 'fehler') k.append(d().el('div', 's-note bad', 'Der Provider meldete: ' + a.stt.fehler));
      if(a.stt.status !== 'laeuft' && !(a.stt.status === 'fertig' && a.transkript_id)) k.append(this.abschrift(a));
      this.audioBox = d().el('div', 't-rk-audio'); k.append(this.audioBox);
      return k;
    },

    abschrift(a){
      const f = d().el('details', 't-rk-abschrift'); f.open = !(this.stt && this.stt.status === 'bereit');
      f.append(d().el('summary', null, 'Abschrift von Hand – wird ein Transkript (Herkunft „manuell“)'));
      const text = d().el('textarea'); text.rows = 5; text.placeholder = 'Was gesagt wurde, in eigenen Worten oder wörtlich …';
      const go = d().button('Als Transkript anlegen', ()=>{ if(text.value.trim()) this.transkribieren(a, {text: text.value}); }, '');
      f.append(text, go);
      return f;
    },

    async abspielen(a, karte){
      try{
        const r = await this.ctx.api('/api/sprache/aufnahme', {method: 'POST', body: {id: a.id}});
        const box = karte.querySelector('.t-rk-audio'); box.replaceChildren();
        if(r.zu_gross || !r.daten){ box.append(d().el('div', 's-note', 'Zu groß zum Abspielen hier – die Datei liegt im Projekt: ' + r.pfad)); return; }
        const bytes = Uint8Array.from(atob(r.daten), c=>c.charCodeAt(0));
        const audio = d().el('audio'); audio.controls = true; audio.src = URL.createObjectURL(new Blob([bytes], {type: r.mime}));
        box.append(audio); audio.play().catch(()=>{});
      }catch(err){ this.meldung.textContent = 'Abspielen ging nicht: ' + err.message; }
    },

    async transkribieren(a, body){
      try{
        const r = await this.ctx.api('/api/sprache/aufnahme/transkribieren', {method: 'POST', body: Object.assign({id: a.id}, body)});
        this.meldung.textContent = r.status === 'laeuft' ? 'Sprache → Text läuft im Hintergrund (' + r.provider + ') – die Karte meldet sich.' : 'Transkript angelegt (' + r.provider + ').';
        await this.laden();
      }catch(err){ this.meldung.textContent = 'Sprache → Text ging nicht: ' + err.message; }
    },

    async loeschen(a){
      if(typeof confirm === 'function' && !confirm('„' + a.titel + '“ löschen? Ein Transkript daraus bleibt.')) return;
      try{ await this.ctx.api('/api/sprache/aufnahme/loeschen', {method: 'POST', body: {id: a.id}}); this.offen = null; await this.laden(); }
      catch(err){ this.meldung.textContent = 'Löschen ging nicht: ' + err.message; }
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
