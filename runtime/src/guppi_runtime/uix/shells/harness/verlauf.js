// Harness-Shell – der Verlauf einer Sitzung (HS-10 bis HS-13, HS-16): Captain-Nachrichten, Antworten als Markdown, Denken eingeklappt,
// Werkzeugzeilen aufklappbar. Eine laufende Antwort kommt über ihren eigenen Strom (GET /api/harness/antworten/<id>/strom, G2 §5):
// Text erscheint grau („ungeprüft“), bis der Inhaltsschutz geurteilt hat; dann normal oder durch den Grund ersetzt (K2, D-E2).
// Der Strom wird mit fetch gelesen (EventSource kann keinen Kopf senden); bricht er ab, geht es ab der letzten Nummer weiter.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const md = ()=>root.sedraHarness.markdown;
  const ID = /^S-[0-9A-F]{8}$/;
  const AUSGABE_KURZ = 4000;               // HS-11: gekürzt ab 4000 Zeichen, mit „ganz anzeigen“
  const ENDE = {erledigt: ['Erledigt', 'ok'], nur_plan: ['Nur Plan – nichts ausgeführt', 'warn'], abgebrochen: ['Abgebrochen', 'warn'],
                fehler: ['Fehler', 'bad'], wartet: ['Wartet auf Freigabe', 'warn']};
  const STATUS = {ok: 'ok', fehler: 'Fehler', wiederholt: 'wiederholt', laeuft: 'läuft', wartet: 'wartet auf Freigabe', verboten: 'verboten',
                  abgelehnt: 'abgelehnt', abgebrochen: 'abgebrochen',
                  hinweis: 'Hinweis – nicht geschrieben'};            // Nachtrag 434b108 (B-8): Fehlerfarbe, weil nichts geschah

  function token(){ return decodeURIComponent((location.hash || '').replace(/^#/, '')); }

  // ---- der Seedrache (HS-04): eine kleine Zeichnung aus Tokens, kein Bild, nichts aus dem Netz
  function drache(){
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 120 120'); svg.setAttribute('class', 'hs-drache'); svg.setAttribute('aria-hidden', 'true');
    const teil = (tag, attrs)=>{ const n = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k, v])=>n.setAttribute(k, v)); svg.append(n); return n; };
    teil('path', {d: 'M62 18c-14 0-24 10-24 22 0 9 6 14 6 22 0 9-10 13-10 24 0 13 12 20 24 20 10 0 17-5 20-11-6 3-14 3-19-2-6-6-3-14 3-19 8-6 14-12 14-24 0-8-4-13-4-18 6 0 12-4 14-10-6 2-12 0-15-4-2-1-6 0-9 0z', class: 'hs-drache-koerper'});
    teil('path', {d: 'M38 40c-8-4-16-2-20 4 7-1 13 1 16 6M44 62c-9 0-15 5-16 12 6-4 12-5 17-3M76 30c6-8 14-10 21-8-5 3-9 8-10 14', class: 'hs-drache-flosse'});
    teil('circle', {cx: '66', cy: '30', r: '3.2', class: 'hs-drache-auge'});
    [[52, 50], [49, 66], [54, 82], [64, 92]].forEach(([x, y])=>teil('circle', {cx: String(x), cy: String(y), r: '2', class: 'hs-drache-punkt'}));
    return svg;
  }

  function startbild(S){
    const box = d().el('div', 'hs-start');
    box.append(drache(), d().el('h1', 'hs-start-titel', 'SEDRA'), d().el('p', 'hs-start-text', 'Worum geht es? Die Antwort streamt, Werkzeugaufrufe stehen sichtbar im Verlauf.'));
    return box;
  }

  function ende(block, daten){
    const art = ENDE[daten.ende];
    const fuss = d().el('div', 'hs-fuss');
    if(art){
      const t = d().el('span', 'hs-ende ' + art[1], art[0] + (daten.ende === 'fehler' && daten.grund ? ': ' + daten.grund : ''));
      fuss.append(t);
    }
    if(daten.abgeschnitten) fuss.append(d().el('span', 'hs-ende warn', 'An der Token-Grenze abgeschnitten'));
    const teile = [];
    if(daten.zuege) teile.push(daten.zuege + (daten.zuege === 1 ? ' Zug' : ' Züge'));
    const tk = daten.token || {};
    if(tk.ein || tk.aus) teile.push((tk.ein || 0).toLocaleString('de-DE') + ' Token ein · ' + (tk.aus || 0).toLocaleString('de-DE') + ' aus');
    if(teile.length) fuss.append(d().el('small', 'hs-leise', teile.join(' · ')));
    if(fuss.childNodes.length) block.append(fuss);
  }

  function werkzeugZeile(name, kurz, args){
    const row = d().el('details', 'hs-wz laeuft');
    const sum = d().el('summary');
    const status = d().el('span', 'hs-wz-status', 'läuft');
    sum.append(d().el('span', 'hs-wz-icon', '⚙'), d().el('b', 'hs-wz-name', name || '?'), d().el('span', 'hs-wz-kurz', kurz || ''),
               d().el('span', 'hs-wz-dauer', ''), status);
    if(args && typeof args.pfad === 'string' && args.pfad && /^datei_/.test(name || '')){          // Stufe 6 (HS-72): die Datei in der Vorschau öffnen und festhalten
      const pf = d().el('button', 'hs-knopf hs-klein hs-wz-pfad', '▸ Vorschau'); pf.type = 'button'; pf.dataset.pfad = args.pfad; pf.title = 'In der Vorschau öffnen und festhalten';
      sum.append(pf);
    }
    const body = d().el('div', 'hs-wz-body');
    body.append(d().el('small', 'hs-leise', 'Eingabe'), d().el('pre', 'hs-pre', args === undefined ? '' : JSON.stringify(args, null, 2)));
    row.append(sum, body);
    return row;
  }

  function werkzeugEnde(row, status, dauer, ergebnis, stufe, regel){
    row.classList.remove('laeuft');
    row.classList.add(status === 'ok' ? 'ok' : (status === 'wiederholt' || status === 'wartet' || status === 'abgelehnt' ? 'warn' : 'bad'));
    row.querySelector('.hs-wz-status').textContent = STATUS[status] || status;
    if(typeof dauer === 'number') row.querySelector('.hs-wz-dauer').textContent = dauer < 1 ? Math.round(dauer * 1000) + ' ms' : dauer.toFixed(1) + ' s';
    if(stufe){                                           // HS-29: Stufe und Regel stehen am Werkzeugaufruf
      const marke = d().el('span', 'hs-wz-stufe ' + stufe, stufe + (regel ? ' · ' + regel : ''));
      marke.title = 'Einstufung: Stufe ' + stufe + (regel ? ', Regel ' + regel : ', keine Regel');
      row.querySelector('summary').insertBefore(marke, row.querySelector('.hs-wz-dauer'));
    }
    const body = row.querySelector('.hs-wz-body');
    const text = String(ergebnis || '');
    const pre = d().el('pre', 'hs-pre', text.length > AUSGABE_KURZ ? text.slice(0, AUSGABE_KURZ) + ' …' : text);
    body.append(d().el('small', 'hs-leise', 'Ausgabe' + (text.length > AUSGABE_KURZ ? ' (' + text.length.toLocaleString('de-DE') + ' Zeichen)' : '')), pre);
    if(text.length > AUSGABE_KURZ){
      const ganz = d().el('button', 'hs-knopf hs-klein', 'ganz anzeigen'); ganz.type = 'button';
      ganz.onclick = ()=>{ pre.textContent = text; ganz.remove(); };
      body.append(ganz);
    }
  }

  function denkZeile(text){
    const row = d().el('details', 'hs-denken');
    const sum = d().el('summary', null, text);
    row.append(sum, d().el('pre', 'hs-pre hs-denken-text', ''));
    return row;
  }


  const karteKarte = (...x)=>root.sedraHarness.karte.karteKarte(...x);        // karte.js: die Freigabe-Karte (HS-22)
  const diffAnsicht = (...x)=>root.sedraHarness.karte.diffAnsicht(...x);

  // ---- eine Ansicht je Reiter
  function ansicht(S, id){
    if(String(id).startsWith('diff:')) return diffAnsicht(S, id);
    if(String(id).startsWith('aufgaben:')) return root.sedraHarness.aufgabe.ansicht(S, id);          // aufgabe.js (Stufe 3)
    if(String(id).startsWith('lauf:')) return root.sedraHarness.lauf.ansicht(S, id);                 // lauf.js (Stufe 3)
    if(String(id).startsWith('app:')) return root.sedraHarness.app.ansicht(S, id);                   // app.js (Stufe 4): ein Werkzeug des Vertrags
    if(String(id).startsWith('einstellungen:')) return root.sedraHarness.einstellungen.ansicht(S, id);   // einstellungen.js (Stufe 5, HS-42)
    const box = d().el('div', 'hs-verlauf');
    const liste = d().el('div', 'hs-liste');
    box.append(liste);
    box.addEventListener('click', e=>{
      const pf = e.target.closest && e.target.closest('.hs-wz-pfad');
      if(pf){ e.preventDefault(); e.stopPropagation(); root.sedraHarness.vorschau.oeffnen(S, a, pf.dataset.pfad); }
    });
    const a = {
      id, box, S, eintraege: 0, antwortId: null, abbruch: null, block: null, wartet: false,
      leer(){ return this.eintraege === 0 && !this.antwortId && !this.wartet; },
      laeuft(){ return !!this.antwortId; },
      nachUnten(){ requestAnimationFrame(()=>{ box.scrollTop = box.scrollHeight; }); },
      abbauen(){ if(this.abbruch) this.abbruch.abort(); },
      zeigeLeer(){
        liste.replaceChildren();
        if(this.leer()) liste.append(startbild(S));
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

      async laden(){
        if(!ID.test(this.id)){ this.zeigeLeer(); return; }
        let s;
        try{ s = await S.api('/api/harness/sitzungen/' + this.id); }
        catch(err){ this.zeigeLeer(); this.notiz('Sitzung nicht lesbar: ' + err.message, 'bad'); return; }
        liste.replaceChildren();
        this.eintraege = 0;
        let block = null, letzte = null;
        const entschieden = {};
        (s.eintraege || []).forEach(e=>{ if(e.typ === 'karte' && e.entscheidung) entschieden[e.karte_id] = e; });
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
          else if(e.typ === 'modell'){
            if(!block){ block = this.neu(d().el('div', 'hs-antwort')); this.eintraege++; }
            if(e.denken_zeichen) block.prepend(denkZeile('Dachte nach · ' + e.denken_zeichen.toLocaleString('de-DE') + ' Zeichen (nicht gespeichert)'));
            if(e.zurueckgehalten) block.append(d().el('div', 'hs-zurueck', e.zurueckgehalten));
            else if(e.text) block.append(md().render(e.text));
            ende(block, e);
            block = null;
          }
        }
        if(letzte) root.sedraHarness.vorschau.beruehrt(S, this, letzte.name, letzte.args, letzte.status);          // Stufe 6: ein geöffneter Reiter zeigt die zuletzt berührte Datei
        if(s.kaputt) this.notiz(s.kaputt + ' Zeile(n) der Sitzungsdatei waren nicht lesbar und fehlen hier.', 'warn');
        if(s.laeuft) this.strom(s.laeuft, 0);
        else this.zeigeLeerWennNoetig();
        this.nachUnten();
      },
      zeigeLeerWennNoetig(){ if(this.leer()) this.zeigeLeer(); else S.leerGeaendert(this); },

      // ---- senden: ein Entwurf wird mit der ersten Nachricht zur Sitzung
      async senden(text, projekt, vorlage){
        if(this.antwortId) return false;
        if(this.ladung) await this.ladung;
        if(!ID.test(this.id) && !S.modell){          // HS-53: ohne Modell keine leere Sitzungsdatei anlegen (der Server prüft trotzdem)
          await S.modellLaden();
          if(!S.modell){ this.notiz('Kein Modell geladen – wähle unten ein Modell und klicke „Laden“.', 'warn'); root.sedraHarness.eingabe.modellMenue(S, true); return false; }
        }
        this.wartet = true;
        let blase = null;
        try{
          if(!ID.test(this.id)){
            const kopf = await S.api('/api/harness/sitzungen', {method: 'POST', body: {projekt, vorlage: vorlage || undefined}});
            const alt = this.id;
            this.id = kopf.id;
            root.sedraHarness.reiter.umbenennen(S, alt, kopf.id);
          }
          // erst die Nachricht zeichnen, dann senden: die Antwort kann über den Ereignisstrom schneller da sein als die HTTP-Antwort
          blase = this.captain(text);
          const out = await S.api('/api/harness/sitzungen/' + this.id + '/nachricht', {method: 'POST', body: {text}});
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
        try{ await S.api('/api/harness/antworten/' + this.antwortId + '/stopp', {method: 'POST', body: {}}); }
        catch(err){ S.hinweis('Stopp fehlgeschlagen: ' + err.message, 'bad'); }
      },

      // ---- der Strom einer Antwort
      async strom(aid, ab){
        if(this.gestreamt && this.gestreamt.has(aid)) return;     // dieselbe Antwort nur einmal: Bus-Ereignis und HTTP-Antwort kommen beide
        this.antwortId = aid;
        (this.gestreamt = this.gestreamt || new Set()).add(aid);
        this._seit = performance.now();          // die Taskleiste zeigt, wie lange die Antwort läuft
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
        const res = await fetch('/api/harness/antworten/' + aid + '/strom', {signal: this.abbruch.signal,
          headers: {'X-GUPPI-Token': token(), 'X-SEDRA-Shell': 'harness', 'Last-Event-ID': String(z.letzte)}});
        if(!res.ok){ const e = new Error('HTTP ' + res.status); e.status = res.status; throw e; }
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let puffer = '';
        for(;;){
          const {value, done} = await reader.read();
          if(done) break;
          puffer += dec.decode(value, {stream: true});
          let at;
          while((at = puffer.indexOf('\n\n')) >= 0){
            const roh = puffer.slice(0, at); puffer = puffer.slice(at + 2);
            const ev = {};
            roh.split('\n').forEach(l=>{ if(!l || l[0] === ':') return; const i = l.indexOf(': '); if(i > 0) ev[l.slice(0, i)] = l.slice(i + 2); });
            if(!ev.event) continue;
            let daten = {};
            try{ daten = JSON.parse(ev.data || '{}'); }catch(_e){}
            z.letzte = Number(ev.id) || z.letzte;
            this.ereignis(ev.event, daten, z, block);
            if(ev.event === 'ende'){ z.fertig = true; this.abbruch.abort(); return; }
          }
        }
      },

      ereignis(name, x, z, block){
        const unten = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
        if(name === 'zug.start'){ z.seg = null; z.roh = ''; }
        else if(name === 'denken'){
          if(!z.denken){ z.denken = denkZeile('Denkt nach …'); block.insertBefore(z.denken, block.firstChild); z.denkenAb = x.t || 0; }
          if(x.stueck){ z.denkenText += x.stueck; z.denken.querySelector('pre').textContent = z.denkenText; }
          const s = Math.max(0, (x.t || 0) - (z.denkenAb || 0));
          z.denken.querySelector('summary').textContent = (x.verborgen ? 'Denkt nach (scharfer Modus: Inhalt erst nach dem Urteil)' : 'Denkt nach · ' + s.toFixed(1).replace('.', ',') + ' s');
        }
        else if(name === 'text.ungeprueft'){
          if(!z.seg){ z.seg = d().el('div', 'hs-text hs-ungeprueft'); z.seg.title = 'ungeprüft: der Inhaltsschutz urteilt nach dem Zug'; block.append(z.seg); z.roh = ''; }
          if(!z.erstesWort){ z.erstesWort = performance.now(); block.dataset.erstesWortT = String(x.t); }
          z.roh += x.stueck || '';
          z.seg.textContent = z.roh;
        }
        else if(name === 'text.geprueft'){
          const text = typeof x.text === 'string' ? x.text : z.roh;
          if(text.trim()){
            const fertig = md().render(text);
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
          const row = werkzeugZeile(x.name, x.kurz, x.args);
          z.werkzeuge[x.aufruf_id] = row; z.seg = null; (z.args || (z.args = {}))[x.aufruf_id] = {name: x.name, args: x.args};
          block.append(row);
        }
        else if(name === 'werkzeug.ende'){
          const row = z.werkzeuge[x.aufruf_id];
          if(row) werkzeugEnde(row, x.status, x.dauer_s, x.ergebnis !== undefined ? x.ergebnis : x.kurz, x.stufe, x.regel);
          const w = (z.args || {})[x.aufruf_id];
          if(w) root.sedraHarness.vorschau.beruehrt(S, this, w.name, w.args, x.status);          // Stufe 6: die Vorschau folgt der Datei
        }
        else if(name === 'karte'){ block.append(karteKarte(S, this, x, null)); z.seg = null; root.sedraHarness.vorschau.karte(S, this, x); }
        else if(name === 'kontext'){ block.dataset.kontext = x.belegt + '/' + x.fenster; }
        else if(name === 'fehler'){ block.append(d().el('div', 'hs-zurueck bad', 'Fehler: ' + (x.grund || ''))); }
        else if(name === 'ende'){
          if(z.seg){ z.seg.classList.remove('hs-ungeprueft'); z.seg = null; }
          if(z.denken && z.denkenText === '' && !z.denken.querySelector('summary').textContent.startsWith('Denkt nach (')) z.denken.querySelector('summary').textContent = 'Dachte nach';
          else if(z.denken) z.denken.querySelector('summary').textContent = z.denken.querySelector('summary').textContent.replace('Denkt', 'Dachte');
          ende(block, x);
        }
        if(unten) this.nachUnten();
      }
    };
    if(ID.test(id)) a.ladung = a.laden(); else a.zeigeLeer();        // `ladung`: senden wartet darauf – sonst räumt die Ladung die gerade gezeichnete Nachricht wieder weg
    return a;
  }

  function kurz(args){
    if(args === undefined || args === null) return '';
    const t = JSON.stringify(args);
    return t === '{}' ? '' : (t.length > 120 ? t.slice(0, 119) + '…' : t);
  }

  // Ein anderer Weg hat eine Antwort beendet (z. B. ein zweites Fenster): die Ansicht ohne eigenen Strom liest neu
  // Die Antwort, die diese Ansicht selbst gestreamt hat, steht schon da – nicht neu laden (sonst klappen geöffnete Zeilen wieder zu)
  function fertigGemeldet(S, sid, aid){
    const a = S.ansichten.get(sid);
    if(a && !a.laeuft() && !(aid && a.gestreamt && a.gestreamt.has(aid))) a.laden();
  }

  root.sedraHarness = root.sedraHarness || {};
  // Eine Antwort läuft, die diese Ansicht nicht selbst gestartet hat (z. B. Freigabe im Posteingang): den Strom anhängen
  function laeuftGemeldet(S, sid, aid){
    const a = S.ansichten.get(sid);
    if(a && a.strom && !a.laeuft() && aid && !(a.gestreamt && a.gestreamt.has(aid))) a.strom(aid, 0);
  }

  root.sedraHarness.verlauf = {ansicht, fertigGemeldet, laeuftGemeldet, drache};
})();
