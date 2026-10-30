// Die Harness-Shell (SPEC_HARNESS_SHELL_v1, G2 §6) – Stufe 1: das Gespräch in der Mitte.
//
// Fünf Zonen (HS-01): Seitenleiste (seite.js), Reiterleiste (reiter.js), Arbeitsfläche mit dem Verlauf (verlauf.js), Eingabefeld
// (eingabe.js) und Taskleiste (taskleiste.js). Keine Instrumentenleiste, kein Baum, kein Mini-Hub: seit Stufe 4 hat die Shell
// `umschalter: menue` (Vertrag N3) – „Start“ in der Taskleiste, Alt+S und `/start` öffnen das Start-Menü (startmenue.js) mit Apps
// (app.js: Werkzeuge des Vertrags als Reiter), Oberflächen, Darstellung und Schrift; der Rekorder ist dort eine App. Stufe 5: die
// Einstellungen (einstellungen.js, HS-42) als Reiter `einstellungen:` – Werkzeuge eingehängt, Katalog-Editor (katalog_editor.js) mit Gate.
// Diese Datei hält den Zustand und verbindet die Teile; sie registriert die Shell und ist deshalb die letzte im Manifest.
// Daten kommen nur über die Wege unter /api/harness/ (harness/api.py) und /api/strip, /api/models; nichts wird gepollt außer der Uhr.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const H = root.sedraHarness;
  const d = ()=>root.sedraDom;
  const SCHMAL = 1100;                       // HS-05: darunter klappt die Seitenleiste von selbst zu

  root.sedra.registerShell({
    id: 'harness',

    async start(ctx){
      this.ctx = ctx;
      this.api = ctx.api;
      this.projekte = [];
      this.projektFehler = null;
      this.sitzungen = [];
      this.ansichten = new Map();            // Reiter-ID → Ansicht (verlauf.js)
      this.modell = null;                    // das geladene Modell oder null (HS-53)
      this.vorlagen = [];                    // Stufe 3: Vorlagen, Vorarbeiter je Projekt, Aufgaben-Freigaben
      this.vorarbeiter = {};
      this.aufgaben = [];
      this.laeufe = [];                      // Läufe der Harness (Register), für Taskleiste und Reiter „Lauf“
      this.entscheidungen = [];              // offene Harness-Freigaben (Karten und Aufgabenvorschläge)
      this.melder = root.sedraStand.makeMelder(this.api);     // Stufe 4: App-Reiter melden ihren Arbeitsstand (§10.2)
      const host = document.getElementById('sedra-root');
      host.setAttribute('aria-label', 'SEDRA Harness');
      host.classList.add('hs');
      document.body.classList.add('hs-body');
      host.replaceChildren();
      const el = this.el = {
        seite: d().el('nav', 'hs-seite'),
        haupt: d().el('div', 'hs-haupt'),
        reiter: d().el('div', 'hs-reiter'),
        flaeche: d().el('main', 'hs-flaeche'),
        eingabe: d().el('div', 'hs-eingabe'),
        taskleiste: d().el('footer', 'hs-taskleiste')
      };
      el.seite.setAttribute('aria-label', 'Sitzungen');
      el.reiter.setAttribute('role', 'tablist');
      el.flaeche.setAttribute('aria-live', 'polite');
      el.haupt.append(el.reiter, el.flaeche, el.eingabe);
      host.append(el.seite, el.haupt, el.taskleiste);

      // Die Shell-API für Werkzeuge (Vertrag §4): diese Shell hängt in Stufe 1 keine Werkzeuge ein, gibt sie aber vollständig.
      this.shellApi = {open: objekt=>{ const id = H.app.oeffnen(this, {object: objekt, label: objekt && objekt.title}); if(!id) this.hinweis('Das lässt sich nicht öffnen: kein Objekt.', 'warn'); },
                       notify: (text, tone)=>this.hinweis(text, tone), decide: ()=>H.app.oeffnen(this, {object: {type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true}, label: 'Entscheidungen'}),   // Stufe 4: der Posteingang ist eine App
                       theme: name=>root.sedraBoot.setTheme(name), reload: ()=>location.reload()};

      H.seite.mount(this);
      H.reiter.mount(this);
      H.eingabe.mount(this);
      H.taskleiste.mount(this);
      H.startmenue.mount(this);
      this.tasten();
      this.breite();
      root.addEventListener('resize', ()=>this.breite());

      ctx.bus.on('harness.sitzung', ()=>this.sitzungenLaden());
      ctx.bus.on('harness.antwort', e=>{
        this.sitzungenLaden(); H.taskleiste.zeichnen(this);
        if(e && e.zustand === 'fertig'){ H.verlauf.fertigGemeldet(this, e.sitzung_id, e.antwort_id); this.freigabenLaden(); }        // der Zähler einer Aufgabe hat sich geändert
        if(e && e.zustand === 'laeuft') H.verlauf.laeuftGemeldet(this, e.sitzung_id, e.antwort_id);
      });
      ctx.bus.on('model.changed', ()=>{ this.modellLaden(); H.taskleiste.status(this); });
      ctx.bus.on('decision.pending', ()=>{ H.taskleiste.status(this); this.freigabenLaden(); H.einstellungen.benachrichtigen(this); });   // Stufe 5 (K9): Browser-Hinweis, wenn das Fenster nicht vorn ist
      ctx.bus.on('decision.answered', e=>{
        H.taskleiste.status(this); this.freigabenLaden();
        if(e && String(e.id || '').startsWith('harness:')){ this.sitzungenLaden(); H.karte.aktualisieren(this, String(e.id).slice(8)); }
      });
      ctx.bus.on('harness.aufgabe', ()=>this.freigabenLaden());
      ctx.bus.on('harness.lauf', e=>H.lauf.melden(this, e));
      ctx.bus.on('harness.vorarbeiter', ()=>this.freigabenLaden());
      ctx.bus.on('harness.karte', e=>{ if(e && e.karte_id) H.karte.aktualisieren(this, e.karte_id); });
      ctx.bus.on('desk.error', e=>this.hinweis('Die Runtime meldet: ' + e.message, 'warn'));
      ctx.bus.on('object.open', o=>{ if(o && o.type && o.id) H.app.oeffnen(this, {object: o, label: o.title}); });    // Stufe 4: ein Werkzeug öffnet ein Objekt → App-Reiter (§5)
      root.sedraBoot.onProblem = text=>this.hinweis(text, 'warn');

      await Promise.all([this.projekteLaden(), this.sitzungenLaden(), this.modellLaden(), this.vorlagenLaden(), this.freigabenLaden(), this.laeufeLaden()]).catch(err=>ctx.onProblem('Harness', err));
      H.taskleiste.alsGesehenStarten(this);
      this._freigabenGeladen = true;
      H.reiter.wiederherstellen(this);
      H.taskleiste.status(this);
      await H.app.uebernehmen(this).catch(err=>ctx.onProblem('Apps übernehmen', err));      // §10.4: was eine andere Oberfläche offen hatte
    },

    // ---- Daten
    async projekteLaden(){
      try{
        const out = await this.api('/api/harness/projekte');
        this.projekte = out.projekte || [];
        this.projektFehler = out.fehler || null;
      }catch(err){ this.projektFehler = err.message; }
      H.seite.zeichnen(this);
      H.eingabe.projektwahl(this);
    },

    async sitzungenLaden(){
      if(this._laden) return this._laden;
      this._laden = (async ()=>{
        try{ this.sitzungen = (await this.api('/api/harness/sitzungen')).sitzungen || []; }
        catch(err){ this.hinweis('Sitzungen nicht lesbar: ' + err.message, 'warn'); }
        H.seite.zeichnen(this);
        H.reiter.titel(this);
      })();
      try{ await this._laden; } finally { this._laden = null; }
    },

    async vorlagenLaden(){
      try{ this.vorlagen = (await this.api('/api/harness/vorlagen')).vorlagen || []; }catch(_err){ this.vorlagen = []; }
      H.eingabe.vorlagenwahl(this);
    },

    // Vorarbeiter je Projekt und aktive Aufgaben: für das Schild, die Seitenleiste und den Reiter „Aufgaben“
    async freigabenLaden(){
      try{
        const [v, a, e] = await Promise.all([this.api('/api/harness/vorarbeiter'), this.api('/api/harness/aufgaben'), this.api('/api/decisions')]);
        this.vorarbeiter = v.vorarbeiter || {};
        this.aufgaben = a.aufgaben || [];
        const vorher = new Set(this.entscheidungen.map(x=>x.id));
        this.entscheidungen = (e.items || []).filter(x=>String(x.id).startsWith('harness:'));
        if(this._freigabenGeladen){               // HS-33: eine neue Freigabe lässt ihren Knopf einmal blinken und markiert ihn, bis er angeklickt wird
          this.entscheidungen.filter(x=>!vorher.has(x.id)).forEach(x=>{
            H.taskleiste.blinken(this, 'freigaben');
            const sid = (String(x.note || '').match(/Sitzung (S-[0-9A-F]{8})/) || [])[1];
            if(sid) H.taskleiste.blinken(this, 'sitzung:' + sid);
          });
        }
      }catch(_err){ /* ohne Antwort bleibt der letzte Stand */ }
      H.seite.zeichnen(this); H.eingabe.schildZeigen(this); H.taskleiste.zeichnen(this); H.taskleiste.status(this);
    },

    async laeufeLaden(){
      try{ this.laeufe = (await this.api('/api/harness/laeufe')).laeufe || []; }catch(_err){ /* der letzte Stand bleibt */ }
      H.taskleiste.zeichnen(this);
    },

    async modellLaden(){
      try{
        const v = await this.api('/api/models');
        const server = v.server || {};
        this.modell = server.running ? {name: server.model, kontext: server.context} : null;
      }catch(_err){ this.modell = null; }
      H.eingabe.modellZeigen(this);
    },

    sitzung(id){ return this.sitzungen.find(s=>s.id === id) || null; },
    projekt(id){ return this.projekte.find(p=>p.id === id) || null; },

    // ---- Ansicht
    aktive(){ return this.ansichten.get(H.reiter.aktiv(this)) || null; },

    zeigen(id){
      let a = this.ansichten.get(id);
      if(!a){ a = H.verlauf.ansicht(this, id); this.ansichten.set(id, a); }
      this.el.flaeche.replaceChildren(a.box);
      document.getElementById('sedra-root').classList.toggle('hs-leer', a.leer());
      H.eingabe.fuer(this, a);
      a.nachUnten();
    },

    verwerfen(id){
      const a = this.ansichten.get(id);
      if(a) a.abbauen();
      this.ansichten.delete(id);
    },

    leerGeaendert(a){
      if(a === this.aktive()) document.getElementById('sedra-root').classList.toggle('hs-leer', a.leer());
    },

    hinweis(text, ton){
      const box = d().el('div', 'hs-hinweis ' + (ton || 'note'), String(text || ''));
      box.setAttribute('role', 'status');
      document.body.append(box);
      setTimeout(()=>box.remove(), 6000);
    },

    // ---- Seitenleiste ein/aus (Strg+B), schmal klappt zu (HS-05)
    seiteUmschalten(an){
      const host = document.getElementById('sedra-root');
      const zu = an === undefined ? !host.classList.contains('hs-seite-zu') : !an;
      host.classList.toggle('hs-seite-zu', zu);
      this.seiteVonHand = true;
    },

    breite(){
      if(this.seiteVonHand) return;
      document.getElementById('sedra-root').classList.toggle('hs-seite-zu', root.innerWidth < SCHMAL);
    },

    tasten(){
      document.addEventListener('keydown', e=>{
        if((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'b' || e.key === 'B')){ e.preventDefault(); this.seiteUmschalten(); }
        else if(e.key === 'Escape'){ const a = this.aktive(); if(a && a.laeuft()){ e.preventDefault(); a.stoppen(); } }
      });
    }
  });
})();
