// Harness-Shell – der Verlauf einer Sitzung (HS-10 bis HS-13, HS-16): Captain-Nachrichten, Antworten als Markdown, Denken eingeklappt,
// Werkzeugzeilen aufklappbar. Eine laufende Antwort kommt über ihren eigenen Strom (GET /api/harness/antworten/<id>/strom, G2 §5):
// Text erscheint grau („ungeprüft“), bis der Inhaltsschutz geurteilt hat; dann normal oder durch den Grund ersetzt (K2, D-E2).
// Der Strom wird mit fetch gelesen (EventSource kann keinen Kopf senden); bricht er ab, geht es ab der letzten Nummer weiter.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const md = ()=>root.sedraHarness.markdown;
  const Z = ()=>root.sedraHarness.zeilen;              // zeilen.js (1.11., A20/V8): Werkzeugzeile, Denkzeile, Fuß
  const werkzeugZeile = (...x)=>Z().werkzeugZeile(...x), werkzeugEnde = (...x)=>Z().werkzeugEnde(...x), denkZeile = (...x)=>Z().denkZeile(...x), ende = (...x)=>Z().ende(...x);
  const ID = root.sedraHarness.reiter.ID;           // A19: eine Quelle für die Sitzungs-ID (reiter.js)
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

  // V2/A22 (1.11.): drei Schritte mit Zustand statt eines Satzes – Modell, Projekt, erste Nachricht; dazu die drei Zeichen des Eingabefelds
  function startbild(S){
    const box = d().el('div', 'hs-start');
    const D = root.sedraHarness.desktop, gruss = D ? D.begruessung(S) : {logo: '', titel: 'SEDRA', text: '', marke: ''};
    const grussEl = d().el('div', 'hs-start-block');                                          // Baustein „gruss“ (bausteine.js): Logo, Titel, Text
    if(gruss.logo){ const bild = d().el('img', 'hs-start-logo'); bild.src = gruss.logo; bild.alt = gruss.marke || 'Logo'; grussEl.append(bild); }       // Logo des Profils statt des Drachen (nur eine Daten-Adresse, vom Server geprüft)
    else grussEl.append(drache());
    grussEl.append(d().el('h1', 'hs-start-titel', gruss.titel));
    if(gruss.text) grussEl.append(d().el('p', 'hs-start-gruss', gruss.text));
    const schritte = d().el('ol', 'hs-start-schritte');
    const e = S._eingabe || {};
    const modell = !!S.modell, projekt = !!(e.projekt && e.projekt.value), vorlage = e.vorlage && e.vorlage.value;
    const modellName = S.modell && (S.modell.name || S.modell);
    const schritt = (ok, text, tun)=>{
      const li = d().el('li', 'hs-start-schritt' + (ok ? ' ok' : ''));
      li.append(d().el('span', 'hs-start-haken', ok ? '✓' : '○'), d().el('span', null, text));
      if(!ok && tun){ const k = d().el('button', 'hs-knopf hs-klein', tun[0]); k.type = 'button'; k.onclick = tun[1]; li.append(k); }
      return li;
    };
    schritte.append(schritt(modell, modell ? 'Modell geladen: ' + modellName : 'Ein Modell laden', ['Modell wählen', ()=>root.sedraHarness.eingabe.modellMenue(S, true)]),
                    schritt(projekt, 'Projekt: ' + ((S.projekte || []).find(p=>p.id === (e.projekt || {}).value) || {}).name + (vorlage ? ' · Vorlage ' + vorlage : ''), null),
                    schritt(false, 'Die erste Nachricht schreiben – unten im Feld', ['Ins Feld', ()=>root.sedraHarness.eingabe.fokus(S)]));
    const hilfeEl = d().el('p', 'hs-start-text', 'Im Feld: „+“ hängt eine Datei an, „@“ nennt eine Datei, „/“ gibt Befehle. Die Antwort streamt; jeder Werkzeugaufruf steht sichtbar im Verlauf, und was ändert, fragt vorher.');
    const B = root.sedraHarness.bausteine;                                                      // Baukasten: Wahl des Profils auf dem Raster, sonst untereinander wie bisher
    if(B) B.startAnwenden(S, box, {gruss: grussEl, schritte, hilfe: hilfeEl}); else box.append(grussEl, schritte, hilfeEl);
    return box;
  }

  const karteKarte = (...x)=>root.sedraHarness.karte.karteKarte(...x);        // karte.js: die Freigabe-Karte (HS-22)
  const diffAnsicht = (...x)=>root.sedraHarness.karte.diffAnsicht(...x);

  // ---- eine Ansicht je Reiter
  function ansicht(S, id){
    if(String(id).startsWith('diff:')) return diffAnsicht(S, id);
    if(String(id).startsWith('aufgaben:')) return root.sedraHarness.aufgabe.ansicht(S, id);          // aufgabe.js (Stufe 3)
    if(String(id).startsWith('lauf:')) return root.sedraHarness.lauf.ansicht(S, id);                 // lauf.js (Stufe 3)
    if(String(id).startsWith('app:')) return root.sedraHarness.app.ansicht(S, id);                   // app.js (Stufe 4): ein Werkzeug des Vertrags
    if(String(id).startsWith('builder:')) return root.sedraHarness.builder.ansicht(S, id);                  // builder.js (Desktop Builder)
    if(String(id).startsWith('einstellungen:')) return root.sedraHarness.einstellungen.ansicht(S, id);   // einstellungen.js (Stufe 5, HS-42)
    const box = d().el('div', 'hs-verlauf');
    const liste = d().el('div', 'hs-liste');
    box.append(liste);
    box.addEventListener('click', e=>{
      const pf = e.target.closest && e.target.closest('.hs-wz-pfad');
      if(pf){ e.preventDefault(); e.stopPropagation(); root.sedraHarness.vorschau.oeffnen(S, a, pf.dataset.pfad); return; }
      const sum = e.target.closest && e.target.closest('.hs-wz > summary');          // Eingabe und Ausgabe stehen in der Vorschau (unterer Teil), wenn sie offen ist
      if(sum && root.sedraHarness.vorschau.werkzeug(S, a, sum.parentNode)) e.preventDefault();
    });
    const a = {
      id, box, S, eintraege: 0, antwortId: null, abbruch: null, block: null, wartet: false,
      leer(){ return this.eintraege === 0 && !this.antwortId && !this.wartet; },
      laeuft(){ return !!this.antwortId; },
      nachUnten(){ requestAnimationFrame(()=>{ box.scrollTop = box.scrollHeight; }); },
      // Das gespeicherte Denken einer fertigen Antwort in ihre Zeile holen (der scharfe Modus streamt es nicht; Sedra speichert es trotzdem, bis 20 000 Zeichen, ungeprüft markiert)
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
        }catch(_e){ /* die Zeile bleibt, wie sie ist; nach dem Neuladen steht das Denken da */ }
      },
      // app_oeffnen (Kern: harness/werkzeuge.py): der Ort kommt aus derselben Liste wie Start-Menü und Chat (ui/places.js); ohne Treffer sagt die Shell es, statt still nichts zu tun
      fensterOeffnen(ui){
        const ort = (root.sedraPlaces && root.sedraPlaces.PLACES || []).find(p=>p.id === ui.oeffnen);
        if(ort) root.sedraHarness.app.oeffnen(S, ort);
        else S.hinweis('Das Fenster „' + (ui.titel || ui.oeffnen) + '“ gibt es in dieser Oberfläche nicht.', 'note');
      },
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
      // G4 (SPEC_APPS_v1, G4-17): liegt Code im Projekt, den der Captain nicht gesehen hat, sagt es die neue Sitzung gleich – Läufe und Befehle brauchen dann seine Karte
      codeHinweis(S, projekt){
        if(!projekt) return;
        S.api('/api/harness/code_stand?projekt=' + encodeURIComponent(projekt)).then(c=>{
          if(!c || !c.aktiv || !c.ungesehen) return;
          const wer = c.ungesehen + (c.ungesehen === 1 ? ' Code-Datei ist' : ' Code-Dateien sind') + ' in dieser Fassung noch nicht von dir gesehen (z. B. ' + c.pfade.slice(0, 3).join(', ') + '). ';
          const konsole = 'Ansehen auch in der Konsole: ' + (c.konsole || 'CODE_STAND.bat ' + projekt) + ' --zeigen';
          // 04.11.2026: ein Antrag im Posteingang – einmal bestätigen genügt; ohne Antrag bleibt es bei der Karte vor Läufen und Befehlen
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
          else if(e.typ === 'zusammenfassung'){                     // von Sedra erstellt: das frühere Gespräch in Stichpunkten, aufklappbar
            const det = d().el('details', 'hs-zusammenfassung');
            det.append(d().el('summary', null, (e.art === 'auszug' ? 'Früheres Gespräch als Auszug ohne Modell (' : 'Früheres Gespräch zusammengefasst (') + (e.nachrichten || '?') + ' Nachrichten) – steht im Systemprompt'), d().el('pre', 'hs-pre', e.text || ''));
            this.neu(det); block = null;
          }
          else if(e.typ === 'modell'){
            if(!block){ block = this.neu(d().el('div', 'hs-antwort')); this.eintraege++; }
            if(Array.isArray(e.kontext) && e.kontext[1]) S.kontextStand = {sitzung: this.id, belegt: e.kontext[0], fenster: e.kontext[1]};      // Füllstand der letzten Antwort
            if(e.denken_zeichen){                                   // der von Sedra gespeicherte Anfang des Denkens (bis 20 000 Zeichen, je Zug getrennt) steht aufklappbar in der Zeile; ans Modell geht er nie zurück
              const dz = denkZeile('Dachte nach · ' + e.denken_zeichen.toLocaleString('de-DE') + ' Zeichen' + (e.denken_text ? (e.denken_text.length < e.denken_zeichen ? ' (Anfang gespeichert)' : '') + (e.denken_ungeprueft ? ' · ungeprüft' : '') : ' (nicht gespeichert – ältere Antwort, vor dem Speichern der Gedanken)'));
              if(e.denken_text){ dz.querySelector('pre').textContent = e.denken_text; if(e.denken_ungeprueft) dz.querySelector('pre').classList.add('hs-ungeprueft'); }
              block.prepend(dz);
            }
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
        if(this.antwortId || this.wartet) return false;        // A15: auch während POST sitzungen läuft, nicht zweimal
        if(this.ladung) await this.ladung;
        if(!S.modell){          // HS-53: ohne Modell keine leere Sitzungsdatei anlegen (der Server prüft trotzdem); P0 M2: selbst laden, wenn der Katalog es erlaubt
          await S.modellLaden();
          if(!S.modell){ this.wartet = true; try{ await root.sedraHarness.modell.autoLaden(S, (t, art)=>this.notiz(t, art)); }finally{ this.wartet = false; } }
          if(!S.modell){ this.notiz('Kein Modell geladen – wähle unten ein Modell und klicke „Laden“.', 'warn'); root.sedraHarness.eingabe.modellMenue(S, true); return false; }
        }
        this.wartet = true;
        let blase = null;
        try{
          if(!ID.test(this.id)){
            const vl = vorlage ? root.sedraHarness.vorlagenhinweis.vorlage(S, vorlage) : null;
            const weit = !!(vl && (vl.erlaubnisse || []).length);                       // weitreichende Freigaben: erst das ausdrückliche Ja des Captains (MasterChat)
            if(weit && !(await root.sedraHarness.vorlagenhinweis.bestaetigen(S, vl))){ this.notiz('Abgebrochen: ohne die Freigaben legt SEDRA diese Sitzung nicht an.', 'note'); return false; }
            const kopf = await S.api('/api/harness/sitzungen', {method: 'POST', body: Object.assign({projekt, vorlage: vorlage || undefined}, weit ? {erlaubnisse_bestaetigt: true} : {})});
            const alt = this.id;
            this.id = kopf.id;
            root.sedraHarness.reiter.umbenennen(S, alt, kopf.id);
            this.codeHinweis(S, projekt);
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
        this.phase('Stopp angefordert – endet mit dem nächsten Schritt des Modells');     // A30 (1.11.): während das Modell den Prompt verarbeitet, passiert sichtbar sonst nichts
        if(this.block) this.block.append(d().el('div', 'hs-notiz s-note warn', 'Stopp angefordert … das Modell hört beim nächsten Schritt auf (bei langer Prompt-Verarbeitung kann das dauern).'));
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

      async lesen(aid, z, block){                     // V8 (1.11.): Zerlegen und Deuten in strom.js (rein, mit node geprüft); hier nur zeichnen
        this.abbruch = new AbortController();
        await root.sedraHarness.strom.lesen(aid, z, (name, daten)=>this.ereignis(name, daten, z, block), {'X-GUPPI-Token': token(), 'X-SEDRA-Shell': 'harness'}, this.abbruch);
      },

      phase(text){ this._phase = text ? {text, seit: performance.now()} : null; root.sedraHarness.taskleiste.zeichnen(S); },     // V3 (1.11.): Zeitlinie in der Taskleiste
      ereignis(name, x, z, block){
        const unten = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
        if(name === 'zug.start'){ z.seg = null; z.roh = ''; this.phase('denkt'); }
        else if(name === 'denken'){
          if(!z.denken){ z.denken = denkZeile('Denkt nach …'); block.insertBefore(z.denken, block.firstChild); z.denkenAb = x.t || 0; }
          if(x.stueck){ z.denkenText += x.stueck; z.denken.querySelector('pre').textContent = z.denkenText; }
          z.denken.querySelector('summary').textContent = root.sedraHarness.strom.denkText(x, z.denkenAb);
        }
        else if(name === 'text.ungeprueft'){
          if(!z.seg){ z.seg = d().el('div', 'hs-text hs-ungeprueft'); z.seg.title = 'ungeprüft: der Inhaltsschutz urteilt nach dem Zug'; block.append(z.seg); z.roh = ''; }
          if(!z.erstesWort){ z.erstesWort = performance.now(); block.dataset.erstesWortT = String(x.t); this.phase('schreibt'); }
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
          this.phase('Werkzeug ' + (x.name || ''));
          const row = werkzeugZeile(x.name, x.kurz, x.args);
          z.werkzeuge[x.aufruf_id] = row; z.seg = null; (z.args || (z.args = {}))[x.aufruf_id] = {name: x.name, args: x.args};
          block.append(row);
        }
        else if(name === 'werkzeug.ende'){
          const row = z.werkzeuge[x.aufruf_id];
          if(row) werkzeugEnde(row, x.status, x.dauer_s, x.ergebnis !== undefined ? x.ergebnis : x.kurz, x.stufe, x.regel);
          const w = (z.args || {})[x.aufruf_id];
          if(w) root.sedraHarness.vorschau.beruehrt(S, this, w.name, w.args, x.status);          // Stufe 6: die Vorschau folgt der Datei
          if(x.ui && x.ui.verknuepfungen) S.freigabenLaden();                                      // verknuepfung_anlegen: die Seitenleiste zeigt den neuen Knopf
          if(x.ui && x.ui.oeffnen) this.fensterOeffnen(x.ui);                                      // app_oeffnen: die Shell öffnet das Fenster (nur live, nie beim Laden des Verlaufs)
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
        else if(name === 'fehler'){                                   // V9 (1.11.): die Fehlerzeile zeigt den Weg zum Logbuch (Audit), nicht nur den Typnamen
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
          if(z.denken && z.denkenText === '') this.denkenNachladen(z, this.antwortId);        // scharfer Modus: live bleibt das Denken verborgen, nach dem Ende steht es (ungeprüft) in der Zeile
          ende(block, x);
          S.tokenLaden();                                              // Verbrauch aktualisieren
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
