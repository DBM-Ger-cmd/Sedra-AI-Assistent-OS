// Werkzeug „Rekorder“ (Kern Sprache, 19.10.2026) – aufnehmen, abspielen, Sprache → Text. Für jede Shell: es zeichnet den Typ
// `aufnahme`. Die Aufnahme läuft im Kern (sprache/kern.py); das Werkzeug steuert sie über ctx.api und zeigt den Stand. Ohne Provider auf
// dem Rechner sagt das Werkzeug das und zeigt den Installationsbefehl; die Abschrift von Hand ist der ehrliche Weg bis dahin.
// Vertrag: nur im eigenen Container, nur ctx.api, kein Speicher, kein eigenes fetch.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const SPRACHEN = [['de', 'Deutsch'], ['en', 'Englisch'], ['fr', 'Französisch'], ['es', 'Spanisch'], ['it', 'Italienisch']];
  const STT = {offen: ['noch kein Text', 'muted'], laeuft: ['Sprache → Text läuft …', 'warn'], fertig: ['Transkript da', 'ok'], fehler: ['Fehler', 'bad']};

  function zeit(s){ s = Math.max(0, Math.floor(s || 0)); return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0'); }
  // Das Werkzeug speichert nichts im Browser (Vertrag): die Empfindlichkeit gilt für diese Ansicht
let empfindlichkeitWert = 12;
function empfindlichkeit(){ return empfindlichkeitWert; }
function empfindlichkeitSpeichern(v){ empfindlichkeitWert = Number(v); }
function pill(text, tone){ return d().el('span', 't-rk-pill ' + (tone || 'muted'), text); }

  const tool = {
    id: 'rekorder',

    mount(el, ctx){
      this.el = el; this.ctx = ctx; this.alle = []; this.stt = null; this.offen = null; this.laeuft = false;
      el.classList.add('t-rekorder');
      this.build();
      this.kernHolen(); this.kernPoll = setInterval(()=>this.kernHolen(), 700);
      return this.laden();
    },

    // Die Aufnahme läuft im Kern: ein Shell-Wechsel (unmount) stoppt sie nicht
    unmount(){
      clearInterval(this.poll); clearInterval(this.kernPoll);
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
        const letzte = this.alle[0];
        this.zuletzt.textContent = letzte ? 'Zuletzt: „' + letzte.titel + '“ · ' + zeit(letzte.dauer) + ' · ' + (letzte.stt.status === 'fertig' ? 'Transkript da' : 'noch kein Text') : 'Noch keine Aufnahme.';
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
      // Kopf der Steuerzentrale: Punkt, Status und die Zeit – wie der Rekorder der Leiste
      this.kopfPunkt = d().el('span', 't-rk-punkt');
      this.status = d().el('span', 't-rk-status', 'Bereit');
      this.uhr = d().el('div', 't-rk-uhr', '00:00'); this.uhr.setAttribute('aria-live', 'off');
      const kopf = d().el('div', 't-rk-kopf'); kopf.append(this.kopfPunkt, this.status, this.uhr);
      const zeile = d().el('div', 't-rk-zeile');
      this.titel = d().el('input'); this.titel.placeholder = 'Titel, z. B. Teamrunde 19.10.'; this.titel.setAttribute('aria-label', 'Titel');
      this.sprache = d().el('select'); this.sprache.setAttribute('aria-label', 'Sprache');
      SPRACHEN.forEach(([v, l])=>{ const o = d().el('option', null, l); o.value = v; this.sprache.append(o); });
      zeile.append(this.titel, this.sprache);
      // Knopf und Pegel; der Regler hebt die Anzeige an (nur Anzeige, die Aufnahme bleibt gleich)
      const mitte = d().el('div', 't-rk-mitte');
      this.knopf = d().el('button', 't-rk-knopf', 'Aufnehmen'); this.knopf.type = 'button'; this.knopf.setAttribute('aria-label', 'Aufnahme starten');
      this.knopf.onclick = ()=>this.laeuft ? this.stop() : this.start();
      this.pegel = d().el('div', 't-rk-pegel'); this.pegel.setAttribute('aria-hidden', 'true');
      for(let i = 0; i < 16; i++) this.pegel.append(d().el('span', 't-rk-balken'));
      this.empf = d().el('input', 't-rk-empf'); this.empf.type = 'range'; this.empf.min = '0'; this.empf.max = '24'; this.empf.step = '1';
      this.empf.value = String(empfindlichkeit()); this.empf.setAttribute('aria-label', 'Empfindlichkeit des Pegels');
      this.empf.oninput = ()=>{ empfindlichkeitSpeichern(this.empf.value); this.zeichnePegel(this.lastPegel || 0); };
      const empfZeile = d().el('div', 't-rk-empfzeile'); empfZeile.append(d().el('small', 't-rk-label', 'Empfindlichkeit'), this.empf);
      mitte.append(this.knopf, this.pegel);
      const verbs = d().el('div', 't-rk-verbs');
      this.pauseBtn = d().button('Pause', ()=>this.pause(), ''); this.pauseBtn.disabled = true;
      this.abbrBtn = d().button('Verwerfen', ()=>this.abbrechen(), ''); this.abbrBtn.disabled = true;
      verbs.append(this.pauseBtn, this.abbrBtn);
      this.zuletzt = d().el('small', 't-rk-zuletzt', '');
      this.meldung = d().el('div', 't-rk-meldung', 'Die Aufnahme läuft im Kern am Rechner und bleibt im Projekt (sprache/aufnahmen). Kein Netz.');
      p.append(kopf, zeile, mitte, empfZeile, verbs, this.zuletzt, this.meldung);
    },

    zeichnePegel(v){
      this.lastPegel = v;
      const db = (v || 0) * 60 - 60 + Number(this.empf.value);
      const n = this.laeuft ? Math.round(Math.max(0, Math.min(1, (db + 60) / 60)) * this.pegel.children.length) : 0;
      Array.from(this.pegel.children).forEach((b, i)=>b.classList.toggle('on', i < n));
    },

    // ---- Der Kern nimmt auf: das Pult zeigt nur den Stand, den der Kern meldet (auch nach einem Shell-Wechsel)
    async kernHolen(){
      try{ this.kernStand(await this.ctx.api('/api/sprache/kern/stand')); }catch(_err){}
    },

    kernStand(s){
      if(!this.pult || !s) return;
      const laeuft = s.status === 'laeuft' || s.status === 'pause', pause = s.status === 'pause';
      this.laeuft = laeuft;
      this.pult.classList.toggle('laeuft', laeuft); this.pult.classList.toggle('pause', pause);
      this.kopfPunkt.classList.toggle('rec', laeuft && !pause); this.kopfPunkt.classList.toggle('pause', pause);
      this.status.textContent = laeuft ? (pause ? 'Pause' : 'Nimmt auf') : 'Bereit';
      this.status.className = 't-rk-status' + (laeuft ? (pause ? ' pause' : ' rec') : '');
      this.knopf.textContent = laeuft ? 'Stopp' : 'Aufnehmen';
      this.knopf.setAttribute('aria-label', laeuft ? 'Aufnahme beenden' : 'Aufnahme starten');
      this.pauseBtn.disabled = !laeuft; this.abbrBtn.disabled = !laeuft; this.pauseBtn.textContent = pause ? 'Weiter' : 'Pause';
      if(laeuft){
        this.uhr.textContent = zeit(s.sekunden); this.zeichnePegel(s.pegel);
        this.meldung.textContent = (pause ? 'Pause · ' : '') + d().fmtBytes(s.groesse) + ' · ' + s.stuecke + ' Stücke gesichert';
      }
    },

    async start(){
      this.knopf.disabled = true;
      try{ this.kernStand(await this.ctx.api('/api/sprache/kern/start', {method: 'POST', body: {titel: this.titel.value.trim(), sprache: this.sprache.value}})); this.titel.value = ''; }
      catch(err){ this.meldung.textContent = 'Keine Aufnahme: ' + err.message; }
      this.knopf.disabled = false;
    },

    async pause(){
      const weiter = this.pult.classList.contains('pause');
      try{ this.kernStand(await this.ctx.api(weiter ? '/api/sprache/kern/weiter' : '/api/sprache/kern/pause', {method: 'POST', body: {}})); }
      catch(err){ this.meldung.textContent = 'Pause ging nicht: ' + err.message; }
    },

    async stop(){
      this.knopf.disabled = true;
      try{
        const a = await this.ctx.api('/api/sprache/kern/stopp', {method: 'POST', body: {}});
        this.meldung.textContent = 'Gesichert: „' + a.titel + '“ · ' + zeit(a.dauer) + ' · ' + d().fmtBytes(a.groesse);
        this.titel.value = ''; this.offen = a.id;
      }catch(err){ this.meldung.textContent = 'Nicht gesichert: ' + err.message; }
      await this.kernHolen(); await this.laden();
      this.knopf.disabled = false;
    },

    async abbrechen(){
      try{ await this.ctx.api('/api/sprache/kern/verwerfen', {method: 'POST', body: {}}); this.meldung.textContent = 'Verworfen – nichts gespeichert.'; }
      catch(err){ this.meldung.textContent = 'Verwerfen ging nicht: ' + err.message; }
      await this.kernHolen(); this.uhr.textContent = '00:00'; await this.laden();
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
