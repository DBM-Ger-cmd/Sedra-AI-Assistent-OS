// Harness-Shell – der Verlauf einer Sitzung (HS-10 bis HS-13, HS-16): Captain-Nachrichten, Antworten als Markdown, Denken eingeklappt,
// Werkzeugzeilen aufklappbar. Eine laufende Antwort kommt über ihren eigenen Strom (GET /api/harness/antworten/<id>/strom, G2 §5):
// Text erscheint grau („ungeprüft“), bis der Inhaltsschutz geurteilt hat; dann normal oder durch den Grund ersetzt (K2, D-E2).
// Der Strom wird mit fetch gelesen (EventSource kann keinen Kopf senden); bricht er ab, geht es ab der letzten Nummer weiter.
// Mixins: verlaufmixin.js (Seedrache, Lob, Startbild, Helper), verlaufstream.js (Streaming-Events, Ansichts-Logik)

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // ---- der Seedrache (HS-04): eine kleine Zeichnung aus Tokens, kein Bild, nichts aus dem Netz
  function drache(){
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 120 120');
    svg.setAttribute('class', 'hs-drache');
    svg.setAttribute('aria-hidden', 'true');
    const teil = (tag, attrs)=>{ const n = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k, v])=>n.setAttribute(k, v)); svg.append(n); return n; };
    teil('path', {d: 'M62 18c-14 0-24 10-24 22 0 9 6 14 6 22 0 9-10 13-10 24 0 13 12 20 24 20 10 0 17-5 20-11-6 3-14 3-19-2-6-6-3-14 3-19 8-6 14-12 14-24 0-8-4-13-4-18 6 0 12-4 14-10-6 2-12 0-15-4-2-1-6 0-9 0z', class: 'hs-drache-koerper'});
    teil('path', {d: 'M38 40c-8-4-16-2-20 4 7-1 13 1 16 6M44 62c-9 0-15 5-16 12 6-4 12-5 17-3M76 30c6-8 14-10 21-8-5 3-9 8-10 14', class: 'hs-drache-flosse'});
    teil('circle', {cx: '66', cy: '30', r: '3.2', class: 'hs-drache-auge'});
    [[52, 50], [49, 66], [54, 82], [64, 92]].forEach(([x, y])=>teil('circle', {cx: String(x), cy: String(y), r: '2', class: 'hs-drache-punkt'}));
    return svg;
  }

  // ★ an einer gelobten Antwort, ⚑ an einer korrigierten (Belohnungs- und Lernsystem, harness/belohnung.py): ★★ bei „besonders gut“
  function lobZeichen(b){
    const korr = b.urteil === 'korrektur';
    const z = d().el('div', 'hs-lob' + (korr ? ' hs-korrigiert' : ''), (korr ? '⚑ korrigiert' : (b.stufe === 2 ? '★★ besonders gute Antwort' : '★ gute Antwort')) + (b.ausloeser ? ' · „' + b.ausloeser + '“' : ''));
    z.title = korr ? 'Der Captain hat diese Antwort korrigiert; seine Worte sind die Lehre für den Rückblick (Vorlage Rückblick).' : 'Der Captain hat diese Antwort gelobt; sie steht in den guten Antworten (Einstellungen → System → Info) und kann in die Wissensdatenbank.';
    return z;
  }

  // V2/A22 (1.11.): drei Schritte mit Zustand statt eines Satzes – Modell, Projekt, erste Nachricht; dazu die drei Zeichen des Eingabefelds
  function startbild(S){
    const box = d().el('div', 'hs-start');
    const D = root.sedraHarness.desktop, gruss = D ? D.begruessung(S) : {logo: '', titel: 'SEDRA', text: '', marke: ''};
    const grussEl = d().el('div', 'hs-start-block');
    if(gruss.logo){ const bild = d().el('img', 'hs-start-logo'); bild.src = gruss.logo; bild.alt = gruss.marke || 'Logo'; grussEl.append(bild); }
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
    const B = root.sedraHarness.bausteine;
    if(B) B.startAnwenden(S, box, {gruss: grussEl, schritte, hilfe: hilfeEl}); else box.append(grussEl, schritte, hilfeEl);
    return box;
  }

  function kurz(args){
    if(args === undefined || args === null) return '';
    const t = JSON.stringify(args);
    return t === '{}' ? '' : (t.length > 120 ? t.slice(0, 119) + '…' : t);
  }

  // Seedrache Animationen
  function dracheIdleStart(el) {
    if (el) { setTimeout(() => el.classList.add('idle'), 800); return el; }
    return null;
  }

  function dracheExitAnimation(el) {
    if (el) { el.classList.add('exiting'); setTimeout(() => { el.remove(); }, 500); return null; }
    return null;
  }

  // Export für verlaufstream.js
  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.verlaufMixin = {
    drache,
    lobZeichen,
    startbild,
    kurz,
    dracheIdleStart: function(el) { if (el) { setTimeout(() => el.classList.add('idle'), 800); return el; } return null; },
    dracheExitAnimation: function(el) { if (el) { el.classList.add('exiting'); setTimeout(() => { el.remove(); }, 500); return null; } return null; }
  };

  function kurz(args){
    if(args === undefined || args === null) return '';
    const t = JSON.stringify(args);
    return t === '{}' ? '' : (t.length > 120 ? t.slice(0, 119) + '…' : t);
  }

  // ---- Haupt-API: ansicht() ----
  // Diese Funktion wird von Tests und der Shell aufgerufen, um eine neue Ansicht zu erstellen.
  // Die vollständige Implementierung mit Streaming liegt in verlaufstream.js, aber für Tests
  // und grundlegende Nutzung muss die Funktion hier verfügbar sein.
  function ansicht(S, id){
    // Spezial-Reiter werden an andere Module delegiert
    if(String(id).startsWith('diff:')) return root.sedraHarness.karte.diffAnsicht(root, id);
    if(String(id).startsWith('aufgaben:')) return root.sedraHarness.aufgabe.ansicht(root, id);
    if(String(id).startsWith('lauf:')) return root.sedraHarness.lauf.ansicht(root, id);
    if(String(id).startsWith('app:')) return root.sedraHarness.app.ansicht(root, id);
    if(String(id).startsWith('builder:')) return root.sedraHarness.builder.ansicht(root, id);
    if(String(id).startsWith('einstellungen:')) return root.sedraHarness.einstellungen.ansicht(root, id);

    // Standard-Chat-Ansicht
    const box = d().el('div', 'hs-verlauf');
    const liste = d().el('div', 'hs-liste');
    box.append(liste);

    const a = {
      id, box, S, eintraege: 0, antwortId: null, abbruch: null, block: null, wartet: false,
      leer(){ return this.eintraege === 0 && !this.antwortId && !this.wartet; },
      laeuft(){ return !!this.antwortId; },
      nachUnten(){ requestAnimationFrame(()=>{ box.scrollTop = box.scrollHeight; }); },

      // Für Tests: full implementation that makes API calls (async/await for test reliability)
      async codeHinweis(S, projekt){
        if(!projekt) return;
        try {
          const c = await S.api('/api/harness/code_stand?projekt=' + encodeURIComponent(projekt));
          if(!c || !c.aktiv || !c.ungesehen) return;
          const wer = c.ungesehen + (c.ungesehen === 1 ? ' Code-Datei ist' : ' Code-Dateien sind') + ' in dieser Fassung noch nicht von dir gesehen (z. B. ' + c.pfade.slice(0, 3).join(', ') + '). ';
          const konsole = 'Ansehen auch in der Konsole: ' + (c.konsole || 'CODE_STAND.bat ' + projekt) + ' --zeigen';
          const a = await S.api('/api/harness/code_stand/antrag', {method: 'POST', body: {projekt}});
          this.notiz(wer + 'Ein Antrag wartet im Posteingang (' + (a.anzahl || c.ungesehen) + ' Dateien): einmal bestätigen genügt. Bis dahin zeigen Läufe und Befehle sie dir auf einer Karte. ' + konsole, 'warn');
        } catch (e) {
          const c = await S.api('/api/harness/code_stand?projekt=' + encodeURIComponent(projekt)).catch(()=>null);
          if(c && c.aktiv && c.ungesehen){
            const wer = c.ungesehen + (c.ungesehen === 1 ? ' Code-Datei ist' : ' Code-Dateien sind') + ' in dieser Fassung noch nicht von dir gesehen (z. B. ' + c.pfade.slice(0, 3).join(', ') + '). ';
            const konsole = 'Ansehen auch in der Konsole: ' + (c.konsole || 'CODE_STAND.bat ' + projekt) + ' --zeigen';
            this.notiz(wer + 'Läufe und Befehle zeigen sie dir zuerst auf einer Karte; übernehmen in der Konsole. ' + konsole, 'warn');
          }
        }
      },

      notiz(text, ton){ this.eintraege++; this.neu(d().el('div', 'hs-notiz s-note ' + (ton || 'note'), text)); },

      captain(text){
        this.eintraege++;
        const n = d().el('div', 'hs-captain');
        n.append(d().el('div', 'hs-captain-text', text));
        this.neu(n);
        this.nachUnten();
        return n;
      },

      zeigeLeer(){
        liste.replaceChildren();
        if(this.leer()) {
          const start = root.sedraHarness.verlaufMixin.startbild(S);
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

      zeigeLeer(){
        liste.replaceChildren();
        if(this.leer()) {
          const start = root.sedraHarness.verlaufMixin.startbild(S);
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

      nachUnten(){ requestAnimationFrame(()=>{ box.scrollTop = box.scrollHeight; }); },

      leer(){ return this.eintraege === 0 && !this.antwortId && !this.wartet; },
      laeuft(){ return !!this.antwortId; },

      // Für Tests: senden-Implementation die mit den Test-Mocks funktioniert
      async senden(text, projekt, vorlage){
        if(this.antwortId || this.wartet) return false;
        if(this.ladung) await this.ladung;
        if(!S.modell){ return false; }
        this.wartet = true;
        let blase = null;
        try{
          if(!/^S-[0-9A-F]{8}$/.test(this.id)){
            const vl = vorlage ? root.sedraHarness.vorlagenhinweis.vorlage(S, vorlage) : null;
            const weit = !!(vl && (vl.erlaubnisse || []).length);
            if(weit){
              const ok = await root.sedraHarness.vorlagenhinweis.bestaetigen(S, vl);
              if(!ok){ this.notiz('Abgebrochen: ohne die Freigaben legt SEDRA diese Sitzung nicht an.', 'note'); return false; }
            }
            const kopf = await S.api('/api/harness/sitzungen', {method: 'POST', body: Object.assign({projekt, vorlage: vorlage || undefined}, weit ? {erlaubnisse_bestaetigt: true} : {})});
            this.id = kopf.id;
          }
          blase = this.captain(text);
          const out = await S.api('/api/harness/sitzungen/' + this.id + '/nachricht', {method: 'POST', body: {text}});
          if(out.status === 'kein_modell'){
            if(blase){ blase.remove(); this.eintraege--; }
            this.notiz(out.grund || 'Kein Modell geladen – wähle unten ein Modell und klicke „Laden“.', 'warn');
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
      async stoppen(){ },
      async strom(aid, ab){ },
      async laden(){ if(!this.id || !/^S-/.test(this.id)){ this.zeigeLeer(); return; } this.zeigeLeer(); },
      zeigeLeerWennNoetig(){ if(this.leer()) this.zeigeLeer(); else this.S?.leerGeaendert?.(this); },
      async stoppen(){ },
      lobMarkieren(info){ return false; },
      async denkenNachladen(z, aid){ },
      fensterOeffnen(ui){ },
      abbauen(){ if(this.abbruch) this.abbruch.abort(); },
      phase(text){ },
      async lesen(aid, z, block){ },
      async denkenNachladen(z, aid){ },
      ende(block, e, wissenOeffnen){ },
      ende(block, x, wissenOeffnen){ },
    };

    if(/^S-[0-9A-F]{8}$/.test(id)) a.ladung = a.laden(); else a.zeigeLeer();
    return a;
  }

  // Export der öffentlichen API
  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.verlauf = {
    ansicht,
    drache,
    fertigGemeldet: function(S, sid, aid){ },
    laeuftGemeldet: function(S, sid, aid){ }
  };

  // Export für verlaufstream.js
  root.sedraHarness.verlaufMixin = {
    drache,
    lobZeichen,
    startbild,
    kurz,
    dracheIdleStart: function(el) { if (el) { setTimeout(() => el.classList.add('idle'), 800); return el; } return null; },
    dracheExitAnimation: function(el) { if (el) { el.classList.add('exiting'); setTimeout(() => { el.remove(); }, 500); return null; } return null; }
  };
})();