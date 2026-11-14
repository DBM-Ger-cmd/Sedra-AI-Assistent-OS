// verlaufstream.js – Mixin für Streaming-Event-Handler & Ansichts-Logik
// Ausgelagert aus verlauf.js um Zeilenlimit (400) einzuhalten
// Einbindung: NACH verlaufmixin.js, VOR verlauf.js in desk.html

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const md = ()=>root.sedraHarness.markdown;
  const Z = ()=>root.sedraHarness.zeilen;
  const werkzeugZeile = (...x)=>Z().werkzeugZeile(...x), werkzeugEnde = (...x)=>Z().werkzeugEnde(...x), denkZeile = (...x)=>Z().denkZeile(...x), ende = (...x)=>Z().ende(...x),
        wissenOeffnen = (...x)=>Z().wissenOeffnen(...x), wissenBlock = (...x)=>Z().wissenBlock(...x);
  const ID = root.sedraHarness.reiter.ID;
  function token(){ return decodeURIComponent((location.hash || '').replace(/^#/, '')); }
  const karteKarte = (...x)=>root.sedraHarness.karte.karteKarte(...x);
  const diffAnsicht = (...x)=>root.sedraHarness.karte.diffAnsicht(...x);

  // Mixin-Funktionen aus verlaufmixin.js
  const {lobZeichen, startbild, dracheIdleStart, dracheExitAnimation, kurz} = root.sedraHarness.verlaufMixin || {};

  // ---- eine Ansicht je Reiter
  function ansicht(S, id){
    if(String(id).startsWith('diff:')) return diffAnsicht(S, id);
    if(String(id).startsWith('aufgaben:')) return root.sedraHarness.aufgabe.ansicht(S, id);
    if(String(id).startsWith('lauf:')) return root.sedraHarness.lauf.ansicht(S, id);
    if(String(id).startsWith('app:')) return root.sedraHarness.app.ansicht(S, id);
    if(String(id).startsWith('builder:')) return root.sedraHarness.builder.ansicht(S, id);
    if(String(id).startsWith('einstellungen:')) return root.sedraHarness.einstellungen.ansicht(S, id);
    const box = d().el('div', 'hs-verlauf');
    const liste = d().el('div', 'hs-liste');
    box.append(liste);
    box.addEventListener('click', e=>{
      const pf = e.target.closest && e.target.closest('.hs-wz-pfad');
      if(pf){ e.preventDefault(); e.stopPropagation(); root.sedraHarness.vorschau.oeffnen(S, a, pf.dataset.pfad); return; }
      const sum = e.target.closest && e.target.closest('.hs-wz > summary');
      if(sum && root.sedraHarness.vorschau.werkzeug(S, a, sum.parentNode)) e.preventDefault();
    });
    const a = {
      id, box, S, eintraege: 0, antwortId: null, abbruch: null, block: null, wartet: false,
      leer(){ return this.eintraege === 0 && !this.antwortId && !this.wartet; },
      laeuft(){ return !!this.antwortId; },
      nachUnten(){ requestAnimationFrame(()=>{ box.scrollTop = box.scrollHeight; }); },

      async denkenNachladen(z, aid){
        try{
          const s = await S.api('/api/harness/sitzungen/' + this.id);
          const e = (s.eintraege || []).filter(x=>x.typ === 'modell' && x.antwort_id === aid).pop();
          if(!e || !e.denken_text || !z.denken) return;
          const pre = z.denken.querySelector('pre');
          pre.textContent = e.denken_text;
          if(e.denken_ungeprueft) pre.classList.add('hs-ungeprueft');
          z.denken.querySelector('summary').textContent = 'Dachte nach · ' + Number(e.denken_zeichen || e.denken_text.length).toLocaleString('de-DE') + ' Zeichen'
            + (e.denken_text.length < (e.denken_zeichen || 0) ? ' (Anfang gespeichert)' : '') + (e.denken_ungeprueft ? ' · ungeprüft' : '');
        }catch(_e){ }
      },

      fensterOeffnen(ui){
        const ort = (root.sedraPlaces && root.sedraPlaces.PLACES || []).find(p=>p.id === ui.oeffnen);
        if(ort) root.sedraHarness.app.oeffnen(S, ort);
        else S.hinweis('Das Fenster „' + (ui.titel || ui.oeffnen) + '“ gibt es in dieser Oberfläche nicht.', 'note');
      },
      abbauen(){ if(this.abbruch) this.abbruch.abort(); },

      lobMarkieren(info){
        const kinder = [...liste.children];
        let i = kinder.length - 1;
        while(i >= 0 && !kinder[i].classList.contains('hs-captain')) i--;
        for(let j = (i < 0 ? kinder.length : i) - 1; j >= 0; j--){
          if(kinder[j].classList.contains('hs-antwort')){ if(!kinder[j].querySelector('.hs-lob')) kinder[j].append(lobZeichen(info)); return true; }
        }
        return false;
      },

      zeigeLeer(){
        liste.replaceChildren();
        if(this.leer()) {
          const start = startbild(S);
          const dracheEl = start.querySelector('.hs-drache');
          if (dracheEl) {
            setTimeout(() => dracheEl.classList.add('idle'), 800);
            this._dracheEl = dracheEl;
          }
          liste.append(start);
        }
        S.leerGeaendert(this);
      },

      neu(knoten){
        const start = liste.querySelector('.hs-start');
        if(start) start.remove();
        liste.append(knoten);
        const unten = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
        if(unten) this.nachUnten();
        S.leerGeaendert(this);
        return knoten;
      },

      captain(text){
        this.eintraege++;
        const n = d().el('div', 'hs-captain');
        n.append(d().el('div', 'hs-captain-text', text));
        this.neu(n);
        this.nachUnten();
        return n;
      },

      notiz(text, ton){ this.eintraege++; this.neu(d().el('div', 'hs-notiz s-note ' + (ton || 'note'), text)); },

      codeHinweis(S, projekt){
        if(!projekt) return;
        S.api('/api/harness/code_stand?projekt=' + encodeURIComponent(projekt)).then(c=>{
          if(!c || !c.aktiv || !c.ungesehen) return;
          const wer = c.ungesehen + (c.ungesehen === 1 ? ' Code-Datei ist' : ' Code-Dateien sind') + ' in dieser Fassung noch nicht von dir gesehen (z. B. ' + c.pfade.slice(0, 3).join(', ') + '). ';
          const konsole = 'Ansehen auch in der Konsole: ' + (c.konsole || 'CODE_STAND.bat ' + projekt) + ' --zeigen';
          S.api('/api/harness/code_stand/antrag', {method: 'POST', body: {projekt}}).then(a=>{
            this.notiz(wer + 'Ein Antrag wartet im Posteingang (' + (a.anzahl || c.ungesehen) + ' Dateien): einmal bestätigen genügt. Bis dahin zeigen Läufe und Befehle sie dir auf einer Karte. ' + konsole, 'warn');
          }).catch(()=>this.notiz(wer + 'Läufe und Befehle zeigen sie dir zuerst auf einer Karte; übernehmen in der Konsole. ' + konsole, 'warn'));
        }).catch(()=>{});
      },

      async laden(){
        if(!ID.test(this.id)){ this.zeigeLeer(); return; }
        let s;
        try{ s = await S.api('/api/harness/sitzungen/' + this.id); }
        catch(err){ this.zeigeLeer(); this.notiz('Sitzung nicht lesbar: ' + err.message, 'bad'); return; }
        liste.replaceChildren();
        this.eintraege = 0;
        let block = null, letzte = null;
        const entschieden = {}, gelobt = {};
        (s.eintraege || []).forEach(e=>{ if(e.typ === 'karte' && e.entscheidung) entschieden[e.karte_id] = e; if(e.typ === 'belohnung') gelobt[e.antwort_id] = e; });
        for(const e of s.eintraege || []){
          if(e.typ === 'captain'){ this.captain(e.text || ''); block = null; }
          else if(e.typ === 'werkzeug' && e.antwort_id !== s.laeuft){
            if(!block){ block = this.neu(d().el('div', 'hs-antwort')); this.eintraege++; }
            const row = werkzeugZeile(e.name, kurz(e.args), e.args);
            werkzeugEnde(row, e.status, e.dauer_s, e.ergebnis, e.stufe, e.regel);
            block.append(row);
            letzte = e;
          }
          else if(e.typ === 'karte' && e.zustand === 'offen'){
            if(!block){ block = this.neu(d().el('div', 'hs-antwort')); this.eintraege++; }
            block.append(karteKarte(S, this, e, entschieden[e.karte_id] || null));
          }
          else if(e.typ === 'wissen'){ this.neu(wissenBlock(e.text)); this.eintraege++; block = null; }
          else if(e.typ === 'zusammenfassung'){
            const det = d().el('details', 'hs-zusammenfassung');
            det.append(d().el('summary', null, (e.art === 'auszug' ? 'Früheres Gespräch als Auszug ohne Modell (' : 'Früheres Gespräch zusammengefasst (') + (e.nachrichten || '?') + ' Nachrichten) – steht im Systemprompt'), d().el('pre', 'hs-pre', e.text || ''));
            this.neu(det); block = null;
          }
          else if(e.typ === 'modell'){
            if(!block){ block = this.neu(d().el('div', 'hs-antwort')); this.eintraege++; }
            if(Array.isArray(e.kontext) && e.kontext[1]) S.kontextStand = {sitzung: this.id, belegt: e.kontext[0], fenster: e.kontext[1]};
            if(e.denken_zeichen){
              const dz = denkZeile('Dachte nach · ' + e.denken_zeichen.toLocaleString('de-DE') + ' Zeichen' + (e.denken_text ? (e.denken_text.length < e.denken_zeichen ? ' (Anfang gespeichert)' : '') + (e.denken_ungeprueft ? ' · ungeprüft' : '') : ' (nicht gespeichert – ältere Antwort, vor dem Speichern der Gedanken)'));
              if(e.denken_text){ dz.querySelector('pre').textContent = e.denken_text; if(e.denken_ungeprueft) dz.querySelector('pre').classList.add('hs-ungeprueft'); }
              block.prepend(dz);
            }
            if(e.zurueckgehalten) block.append(d().el('div', 'hs-zurueck', e.zurueckgehalten));
            else if(e.text) block.append(md().render(e.text));
            ende(block, e, wissenOeffnen(S));
            if(gelobt[e.antwort_id]) block.append(lobZeichen(gelobt[e.antwort_id]));
            block = null;
          }
        }
        if(letzte) root.sedraHarness.vorschau.beruehrt(S, this, letzte.name, letzte.args, letzte.status);
        if(s.kaputt) this.notiz(s.kaputt + ' Zeile(n) der Sitzungsdatei waren nicht lesbar und fehlen hier.', 'warn');
        if(s.laeuft) this.strom(s.laeuft, 0);
        else this.zeigeLeerWennNoetig();
        this.nachUnten();
      },

      zeigeLeerWennNoetig(){ if(this.leer()) this.zeigeLeer(); else S.leerGeaendert(this); },

      async senden(text, projekt, vorlage){
        if(this.antwortId || this.wartet) return false;
        if(this.ladung) await this.ladung;
        if(!S.modell){
          await S.modellLaden();
          if(!S.modell){ this.wartet = true; try{ await root.sedraHarness.modell.autoLaden(S, (t, art)=>this.notiz(t, art)); }finally{ this.wartet = false; } }
          if(!S.modell && !ID.test(this.id)){ this.notiz('Kein Modell geladen – wähle unten ein Modell und klicke „Laden“.', 'warn'); root.sedraHarness.eingabe.modellMenue(S, true); return false; }
        }
        this.wartet = true;
        let blase = null;
        try{
          if(!ID.test(this.id)){
            const vl = vorlage ? root.sedraHarness.vorlagenhinweis.vorlage(S, vorlage) : null;
            const weit = !!(vl && (vl.erlaubnisse || []).length);
            if(weit && !(await root.sedraHarness.vorlagenhinweis.bestaetigen(S, vl))){ this.notiz('Abgebrochen: ohne die Freigaben legt SEDRA diese Sitzung nicht an.', 'note'); return false; }
            const kopf = await S.api('/api/harness/sitzungen', {method: 'POST', body: Object.assign({projekt, vorlage: vorlage || undefined}, weit ? {erlaubnisse_bestaetigt: true} : {})});
            const alt = this.id;
            this.id = kopf.id;
            root.sedraHarness.reiter.umbenennen(S, alt, kopf.id);
            this.codeHinweis(S, projekt);
          }
          blase = this.captain(text);
          if (this._dracheEl) {
            this._dracheEl.classList.add('exiting');
            setTimeout(() => { this._dracheEl.remove(); this._dracheEl = null; }, 500);
          }
          const out = await S.api('/api/harness/sitzungen/' + this.id + '/nachricht', {method: 'POST', body: {text}});
          if(out.status === 'kein_modell' && out.wissen_antwort){ this.neu(wissenBlock(out.wissen_antwort)); this.eintraege++; root.sedraHarness.eingabe.modellMenue(S, true); S.sitzungenLaden(); return true; }
          if(out.status === 'kein_modell'){
            blase.remove(); this.eintraege--; blase = null;
            this.notiz(out.grund || 'Kein Modell geladen – wähle unten ein Modell und klicke „Laden“.', 'warn'); root.sedraHarness.eingabe.modellMenue(S, true);
            S.modellLaden();
            return false;
          }
          this.strom(out.antwort_id, 0);
          S.sitzungenLaden();
          return true;
        }catch(err){
          if(blase){ blase.remove(); this.eintraege--; }
          this.notiz(/karte_offen/.test(err.message) ? 'Erst die offene Freigabe-Karte entscheiden – dann geht es weiter.' : 'Nicht gesendet: ' + err.message,
                     /karte_offen/.test(err.message) ? 'warn' : 'bad');
          return false;
        }finally{
          this.wartet = false;
          S.leerGeaendert(this);
        }
      },

      async stoppen(){
        if(!this.antwortId) return;
        this.phase('Stopp angefordert – endet mit dem nächsten Schritt des Modells');
        if(this.block) this.block.append(d().el('div', 'hs-notiz s-note warn', 'Stopp angefordert … das Modell hört beim nächsten Schritt auf (bei langer Prompt-Verarbeitung kann das dauern).'));
        try{ await S.api('/api/harness/antworten/' + this.antwortId + '/stopp', {method: 'POST', body: {}}); }
        catch(err){ S.hinweis('Stopp fehlgeschlagen: ' + err.message, 'bad'); }
      },

      async strom(aid, ab){
        if(this.gestreamt && this.gestreamt.has(aid)) return;
        this.antwortId = aid;
        (this.gestreamt = this.gestreamt || new Set()).add(aid);
        this._seit = performance.now();
        this.eintraege++;
        const block = this.block = this.neu(d().el('div', 'hs-antwort laeuft'));
        const z = {seg: null, roh: '', denken: null, denkenText: '', denkenAb: null, werkzeuge: {}, letzte: ab || 0, fertig: false};
        root.sedraHarness.eingabe.zustand(S);
        root.sedraHarness.taskleiste.zeichnen(S);
        root.sedraHarness.reiter.zeichnen(S);
        let versuche = 0;
        while(!z.fertig && versuche < 6){
          try{
            await this.lesen(aid, z, block);
            if(!z.fertig){ versuche++; await new Promise(r=>setTimeout(r, 800 * versuche)); }
          }catch(err){
            if(err && err.name === 'AbortError') return;
            if(err && err.status === 404){ z.fertig = true; this.antwortId = null; await this.laden(); break; }
            versuche++;
            await new Promise(r=>setTimeout(r, 800 * versuche));
          }
        }
        if(!z.fertig){ block.append(d().el('div', 'hs-zurueck', 'Verbindung zum Strom verloren – die Antwort steht nach dem Ende in der Sitzung.')); }
        block.classList.remove('laeuft');
        this.antwortId = null; this.block = null;
        root.sedraHarness.eingabe.zustand(S);
        root.sedraHarness.taskleiste.zeichnen(S);
        root.sedraHarness.reiter.zeichnen(S);
        S.sitzungenLaden();
      },

      async lesen(aid, z, block){
        this.abbruch = new AbortController();
        await root.sedraHarness.strom.lesen(aid, z, (name, daten)=>this.ereignis(name, daten, z, block), {'X-SEDRA-Token': token(), 'X-SEDRA-Shell': 'harness'}, this.abbruch);
      },

      phase(text){ this._phase = text ? {text, seit: performance.now()} : null; root.sedraHarness.taskleiste.zeichnen(S); },

      ereignis(name, x, z, block){
        const unten = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
        if(name === 'zug.start'){ z.seg = null; z.roh = ''; this.phase('denkt'); }
        else if(name === 'denken'){
          if(!z.denken){ z.denken = denkZeile('Denkt nach …'); block.insertBefore(z.denken, block.firstChild); z.denkenAb = x.t || 0; }
          if(x.stueck){ z.denkenText += x.stueck; z.denken.querySelector('pre').textContent = z.denkenText; }
          z.denken.querySelector('summary').textContent = root.sedraHarness.strom.denkText(x, z.denkenAb);
        }
        else if(name === 'text.ungeprueft'){
          if(!z.seg){ z.seg = d().el('div', 'hs-text hs-ungeprueft streaming'); z.seg.title = 'ungeprüft: der Inhaltsschutz urteilt nach dem Zug'; block.append(z.seg); z.roh = ''; }
          if(!z.erstesWort){ z.erstesWort = performance.now(); block.dataset.erstesWortT = String(x.t); this.phase('schreibt'); }
          z.roh += x.stueck || '';
          z.seg.textContent = z.roh;
        }
        else if(name === 'text.geprueft'){
          const text = typeof x.text === 'string' ? x.text : z.roh;
          if(text.trim()){
            const fertig = md().render(text);
            fertig.classList.add('verified');
            if(z.seg) z.seg.replaceWith(fertig); else block.append(fertig);
          }else if(z.seg) z.seg.remove();
          z.seg = null; z.roh = '';
        }
        else if(name === 'text.zurueckgehalten'){
          if(z.seg) z.seg.remove();
          block.append(d().el('div', 'hs-zurueck', (x.grund || 'Vom Inhaltsschutz zurückgehalten.')));
          z.seg = null; z.roh = '';
        }
        else if(name === 'werkzeug.start'){
          this.phase('Werkzeug ' + (x.name || ''));
          const row = werkzeugZeile(x.name, x.kurz, x.args);
          z.werkzeuge[x.aufruf_id] = row; z.seg = null; (z.args || (z.args = {}))[x.aufruf_id] = {name: x.name, args: x.args};
          block.append(row);
        }
        else if(name === 'werkzeug.ende'){
          const row = z.werkzeuge[x.aufruf_id];
          if(row) werkzeugEnde(row, x.status, x.dauer_s, x.ergebnis !== undefined ? x.ergebnis : x.kurz, x.stufe, x.regel);
          const w = (z.args || {})[x.aufruf_id];
          if(w) root.sedraHarness.vorschau.beruehrt(S, this, w.name, w.args, x.status);
          if(x.ui && x.ui.verknuepfungen) S.freigabenLaden();
          if(x.ui && x.ui.oeffnen) this.fensterOeffnen(x.ui);
        }
        else if(name === 'karte'){ this.phase('wartet auf Freigabe'); block.append(karteKarte(S, this, x, null)); z.seg = null; root.sedraHarness.vorschau.karte(S, this, x); }
        else if(name === 'kontext'){ block.dataset.kontext = x.belegt + '/' + x.fenster; S.kontextStand = {sitzung: id, belegt: x.belegt, fenster: x.fenster}; root.sedraHarness.eingabe.kontextZeigen(S); }
        else if(name === 'denken.begrenzt'){
          this.notiz('Das Modell hat sein ganzes Antwortbudget beim Denken verbraucht und nichts geantwortet. SEDRA versucht es einmal mit doppeltem Budget (' + Number(x.max_tokens).toLocaleString('de-DE') + ' Token); das Denken bleibt, wie es ist.', 'warn');
        }
        else if(name === 'kontext.gekuerzt'){
          this.notiz(x.stufe === 'voll' ? 'Das Kontextfenster ist voll.' : 'Kontextfenster fast voll (' + Number(x.vorher).toLocaleString('de-DE') + ' von ' + Number(x.fenster).toLocaleString('de-DE') + ' Token geschätzt): alte Ergebnisse wurden gekürzt (jetzt ≈ ' + Number(x.nachher).toLocaleString('de-DE') + ')' + (x.stufe === 'abschluss' ? ' – SEDRA antwortet jetzt ohne weitere Werkzeuge.' : '.'), x.stufe === 'ok' || x.stufe === 'kuerzen' ? 'note' : 'warn');
        }
        else if(name === 'verlauf.zusammenfassung'){
          if(x.phase === 'start') this.phase('fasst das frühere Gespräch zusammen');
          else if(x.phase === 'ende') this.notiz(x.art === 'auszug' ? 'Das Modell hat nichts zusammengefasst – stattdessen steht ein Auszug (erste Sätze von ' + x.nachrichten + ' Nachrichten) im Systemprompt.' : 'Früheres Gespräch zusammengefasst (' + x.nachrichten + ' Nachrichten, ' + x.zeichen + ' Zeichen) – es steht jetzt im Systemprompt.', x.art === 'auszug' ? 'warn' : 'note');
          else this.notiz('Zusammenfassung des früheren Gesprächs gescheitert: ' + x.grund + ' – die Antwort läuft ohne sie weiter.', 'warn');
        }
        else if(name === 'fehler'){
          const zeile = d().el('div', 'hs-zurueck bad', 'Fehler: ' + (x.grund || '') + ' ');
          const weg = d().el('button', 'hs-knopf hs-klein', 'Logbuch öffnen'); weg.type = 'button';
          weg.onclick = ()=>{ const o = (root.sedraPlaces && root.sedraPlaces.PLACES || []).find(p=>p.id === 'logbook'); if(o) root.sedraHarness.app.oeffnen(S, o); else root.sedraHarness.einstellungen.oeffnen(S, 'system/audit'); };
          zeile.append(weg); block.append(zeile);
        }
        else if(name === 'ende'){
          this._phase = null;
          if(z.seg){ z.seg.classList.remove('hs-ungeprueft'); z.seg = null; }
          if(z.denken && z.denkenText === '' && !z.denken.querySelector('summary').textContent.startsWith('Denkt nach (')) z.denken.querySelector('summary').textContent = 'Dachte nach';
          else if(z.denken) z.denken.querySelector('summary').textContent = z.denken.querySelector('summary').textContent.replace('Denkt', 'Dachte');
          if(z.denken && z.denkenText === '') this.denkenNachladen(z, this.antwortId);
          ende(block, x, wissenOeffnen(S));
          S.tokenLaden();
        }
        if(unten) this.nachUnten();
      }
    };
    if(ID.test(id)) a.ladung = a.laden(); else a.zeigeLeer();
    return a;
  }



  function fertigGemeldet(S, sid, aid){
    const a = S.ansichten.get(sid);
    if(a && !a.laeuft() && !(aid && a.gestreamt && a.gestreamt.has(aid))) a.laden();
  }

  root.sedraHarness = root.sedraHarness || {};
  function laeuftGemeldet(S, sid, aid){
    const a = S.ansichten.get(sid);
    if(a && a.strom && !a.laeuft() && aid && !(a.gestreamt && a.gestreamt.has(aid))) a.strom(aid, 0);
  }

  root.sedraHarness.verlauf = {ansicht, fertigGemeldet, laeuftGemeldet, drache};
  // Ensure ansicht is accessible globally for tests
  root.sedraHarness.verlauf.ansicht = ansicht;
})();