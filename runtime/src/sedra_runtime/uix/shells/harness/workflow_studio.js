// Harness-Shell: die App „Workflow Studio“ – aufgebaut wie die Vorlage SEDRA Workflow Studio v1.7: links die Navigation mit den Gruppen,
// rechts die Fläche, Startseite ist der Leitstand.
//
// Die Werkzeuge (workflow, scenario, live, decision, project, gateway, slots, hardware) bleiben, was sie sind; jede Zelle bekommt ihre
// Fläche über denselben Weg wie jeder App-Reiter (`app.flaeche(S, objekt)`). Die Factory-Läufe sind die Lese-Ansicht der App Factory Studio (`eigene`).
// Der Workflow-Katalog und der Leitstand zählen echte gespeicherte Workflows und ihre offenen Angaben; sie erfinden keine Zahlen.
// Der Startassistent füllt die offenen Angaben jedes gespeicherten Workflows aus und speichert sie als neue Revision. „Starten“ wechselt in „Live & Debugger“.
// Der Notaus (STOPP) sitzt oben im „Live & Debugger“ und ruft dieselben Verben wie der Editor (`fabrik_stopp`, `fabrik_status`, `fabrik_freigeben`).
// Das Design wählt dieselben Erscheinungsbilder und denselben Speicherplatz (`sedra.theme`) wie der Rest von SEDRA.
// Ein Modus wird beim ersten Öffnen eingehängt und beim Wechsel nur versteckt. Der zuletzt aktive Modus wird je Browser gemerkt.
// Text nur mit textContent, Farben nur über Tokens, keine Takte außer dem Notaus-Stand (alle 4 Sekunden, wie im Editor). Eigene Texte einsprachig deutsch.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const G = root.sedraHarness.workflow_studio_geteilt;
  const AS = root.sedraHarness.workflow_studio_assist;
  const LV = root.sedraHarness.workflow_studio_live;
  const luecken = G.luecken, workflowsZaehlen = G.workflowsZaehlen;
  const baueKatalog = AS.baueKatalog, baueAssistent = AS.baueAssistent;
  const baueNotaus = LV.baueNotaus, baueLauf = LV.baueLauf, baueLaeufe = LV.baueLaeufe;
  const KEY = 'sedra.harness.workflow_studio.modus';
  const OBJEKT = {type: 'workflow-studio', id: 'app', title: 'Workflow Studio'};
  const THEME_KEY = 'sedra.theme';

  const N8N = {type: 'workflow', id: 'alle', title: 'n8n Workflows', collection: true};
  const SZENARIO = {type: 'scenario', id: 'alle', title: 'Szenario Studio', collection: true};
  const PROJEKT = {type: 'project', id: 'projekt', title: 'Projekte'};
  const FREIGABEN = {type: 'decision', id: 'alle', title: 'Freigaben', collection: true};
  const LIVE = {type: 'task', id: 'alle', title: 'Live', collection: true};
  const LAEUFE = {type: 'factory-laeufe', id: 'laeufe', title: 'Factory-Läufe', eigene: 'factory_laeufe'};
  const VERBINDUNGEN = {type: 'gateway', id: 'alle', title: 'KI GateWay', collection: true};
  const MODELLE = {type: 'model', id: 'alle', title: 'Modelle und Slots', collection: true};
  const HARDWARE = {type: 'hardware', id: 'hardware', title: 'Hardware'};

  // Die Modi, in der Reihenfolge der Navigation. `gruppe` ordnet sie ein, so wie die Vorlage ihre Gruppen zeigt.
  // `katalog`, `assistent`, `design`, `notaus` sind Flächen, die die App selbst baut; `zellen` sind die Werkzeuge, die sie einhängt.
  const MODI = [
    {id: 'leitstand', label: 'Startseite / Leitstand', gruppe: 'Leitstand', zellen: [FREIGABEN, LIVE], kpi: true},
    {id: 'katalog', label: 'Workflow-Katalog', gruppe: 'Direkt arbeiten', zellen: [], katalog: true},
    {id: 'n8n', label: 'n8n Workflows', gruppe: 'Direkt arbeiten', zellen: [N8N]},
    {id: 'startassistent', label: 'Startassistent', gruppe: 'Direkt arbeiten', zellen: [], assistent: true},
    {id: 'live', label: 'Live & Debugger', gruppe: 'Direkt arbeiten', zellen: [LIVE], notaus: true},
    {id: 'szenario', label: 'Szenario Studio', gruppe: 'Direkt arbeiten', zellen: [SZENARIO]},
    {id: 'factory', label: 'Factory', gruppe: 'Vorbereitung', zellen: [PROJEKT, LAEUFE]},
    {id: 'freigaben', label: 'Freigaben', gruppe: 'Prüfen und verbessern', zellen: [FREIGABEN]},
    {id: 'verbindungen', label: 'Verbindungen', gruppe: 'Plattform & Design', zellen: [VERBINDUNGEN]},
    {id: 'modelle', label: 'Modelle und Slots', gruppe: 'Plattform & Design', zellen: [MODELLE]},
    {id: 'hardware', label: 'Hardware', gruppe: 'Plattform & Design', zellen: [HARDWARE]},
    {id: 'design', label: 'Design', gruppe: 'Plattform & Design', zellen: [], design: true}
  ];
  const GRUPPEN = ['Leitstand', 'Direkt arbeiten', 'Vorbereitung', 'Prüfen und verbessern', 'Plattform & Design'];

  // Die Erscheinungsbilder, wie sie in js/theme.js stehen (gleicher Schlüssel im Browser).
  const THEMES = [['retro', 'Retro', 'Das SEDRA-Deck, wie du es kennst'], ['klar', 'Klar', 'Hell und ruhig, flache Flächen'], ['nacht', 'Nacht', 'Dunkel; passt zum Hardware-Fenster']];


  // rein
  function modusWahl(gemerkt){ return MODI.some(m=>m.id === gemerkt) ? gemerkt : MODI[0].id; }
  function lesen(){ try{ return modusWahl(localStorage.getItem(KEY)); }catch(_e){ return MODI[0].id; } }
  function merken(id){ try{ localStorage.setItem(KEY, id); }catch(_e){} }
  // Der Leitstand nach der Vorlage: Kontext, Arbeitslage, „Was liegt an?“, Kennzahlen und „Jetzt wichtig“. Alle Zahlen stammen aus den
  // gespeicherten Workflows und dem Fabrik-Stand; was nicht lädt, steht ehrlich als nicht geladen da.
  function baueLeitstand(api, zumModus, zumAssistent){
    const box = d().el('div', 'hs-ws-leitstand');
    const aktion = (text, fn)=>{ const b = d().el('button', 'hs-ws-knopf', text); b.type = 'button'; b.onclick = fn; return b; };
    const chips = d().el('div', 'hs-ws-chips');
    const bannerText = d().el('span', '', 'Lade die gespeicherten Workflows …');
    const banner = d().el('div', 'hs-ws-banner'); banner.append(d().el('b', '', 'SEDRA – Arbeitslage'), bannerText);
    const kpiWerte = ['Gespeicherte Workflows', 'Ausführbar', 'Mit offenen Angaben', 'Fabrik'].map(titel=>{
      const k = d().el('div', 'hs-ws-kennzahl'); const w = d().el('b', 'hs-ws-kennzahl-wert', '…');
      k.append(d().el('span', 'hs-ws-kennzahl-titel', titel), w); return {k, w};
    });
    const kennzahlen = d().el('div', 'hs-ws-kennzahlen'); kpiWerte.forEach(x=>kennzahlen.append(x.k));
    const wichtigListe = d().el('div', 'hs-ws-liste');
    const wichtig = d().el('div', 'hs-ws-karte hs-ws-wichtig'); wichtig.append(d().el('h4', 'hs-ws-karten-titel', 'Jetzt wichtig'),
      d().el('p', 'hs-ws-hinweis', 'Workflows mit offenen Angaben, die meisten zuerst.'), wichtigListe,
      d().el('p', 'hs-ws-hinweis hs-ws-fuss', 'Echte Zahlen aus den gespeicherten Workflows. Keine Simulation.'));
    const was = d().el('div', 'hs-ws-karte hs-ws-was');
    was.append(d().el('h4', 'hs-ws-karten-titel', 'Dein nächster Schritt'), d().el('p', 'hs-ws-hinweis', 'Erst Entscheidungen und Störungen, dann laufende Arbeit.'));
    const wege = d().el('div', 'hs-ws-wege');
    [['Workflow-Katalog', 'Alle gespeicherten Workflows', 'katalog'], ['Startassistent', 'Offene Angaben ausfüllen, Lauf starten', 'startassistent'],
     ['Live & Debugger', 'Läufe verfolgen, Notaus', 'live'], ['Freigaben', 'Entscheidungen des Captains', 'freigaben']].forEach(([t, h, id])=>{
      const k = d().el('button', 'hs-ws-weg'); k.type = 'button'; k.onclick = ()=>zumModus(id);
      k.append(d().el('b', '', t), d().el('span', '', h)); wege.append(k);
    });
    was.append(wege);
    const kopf = d().el('div', 'hs-ws-leitkopf'); const titelbox = d().el('div', 'hs-ws-titelbox');
    titelbox.append(d().el('p', 'hs-ws-kicker', 'SEDRA / WORKFLOW STUDIO'), d().el('h3', 'hs-ws-leit-titel', 'Startseite / Leitstand')); kopf.append(titelbox, chips);
    const spalten = d().el('div', 'hs-ws-spalten'); spalten.append(wichtig, was);
    box.append(kopf, banner, kennzahlen, spalten);
    workflowsZaehlen(api).then(liste=>{
      const laufbar = liste.filter(w=>w.laufbar).length, offen = liste.filter(w=>w.offen > 0).length;
      kpiWerte[0].w.textContent = String(liste.length); kpiWerte[1].w.textContent = String(laufbar); kpiWerte[2].w.textContent = String(offen);
      chips.replaceChildren(...['Workflows: ' + liste.length, 'Ausführbar: ' + laufbar, 'Offene Angaben: ' + offen].map(t=>d().el('span', 'hs-ws-chip', t)));
      bannerText.textContent = !liste.length ? 'Noch kein Workflow gespeichert.'
        : (offen ? offen + ' Workflow(s) mit offenen Angaben. ' : 'Alle gespeicherten Workflows sind vollständig beschrieben. ') + laufbar + ' ausführbar.';
      kpiWerte[2].k.classList.toggle('warn', offen > 0); kennzahlen.dataset.geladen = '1';
      const mitOffen = liste.filter(w=>w.offen > 0).sort((x, y)=>y.offen - x.offen);
      wichtigListe.replaceChildren(...mitOffen.slice(0, 8).map(w=>{
        const z = d().el('div', 'hs-ws-liste-zeile'); const t = d().el('span', 'hs-ws-liste-titel', w.title); t.title = w.title;
        z.append(t, d().el('span', 'hs-ws-pille', w.offen + ' offen'), aktion('Öffnen', ()=>zumAssistent(w.id))); return z;
      }));
      if(mitOffen.length > 8) wichtigListe.append(d().el('p', 'hs-ws-hinweis', '+ ' + (mitOffen.length - 8) + ' weitere im Workflow-Katalog.'));
      if(!wichtigListe.childNodes.length) wichtigListe.append(d().el('p', 'hs-ws-hinweis', 'Nichts Dringendes.'));
    }).catch(err=>{ bannerText.textContent = 'Workflows nicht geladen: ' + (err.message || err); kpiWerte.forEach(x=>{ x.w.textContent = '–'; }); });
    api('/api/actions', {method: 'POST', body: {type: 'workflow', id: null, verb: 'fabrik_status', args: {}}})
      .then(out=>{ const r = out.result || out; kpiWerte[3].w.textContent = r.angehalten ? 'angehalten' : 'läuft'; })
      .catch(()=>{ kpiWerte[3].w.textContent = '–'; });
    return {box, abbauen(){ box.replaceChildren(); }};
  }

  // Die Darstellung: dieselben Erscheinungsbilder und derselbe Speicherplatz wie in js/theme.js.
  function baueDesign(){
    const box = d().el('div', 'hs-ws-katalog');
    box.append(d().el('p', 'hs-ws-hinweis', 'Erscheinungsbild der Oberfläche. Die Wahl gilt für den Browser und bleibt beim Neuladen erhalten.'));
    const reihe = d().el('div', 'hs-ws-knoepfe');
    const aktuell = ()=>{ try{ return document.documentElement.dataset.theme || 'retro'; }catch(_e){ return 'retro'; } };
    const knoepfe = THEMES.map(([id, label, hinweis])=>{
      const b = d().el('button', 'hs-ws-knopf', label); b.type = 'button'; b.title = hinweis; b.dataset.theme = id;
      b.onclick = ()=>{
        if(id === 'retro') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = id;
        try{ if(id === 'retro') localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, id); }catch(_e){ /* privates Fenster: die Wahl hält bis zum Neuladen */ }
        markieren();
      };
      reihe.append(b); return b;
    });
    function markieren(){ knoepfe.forEach(b=>{ const on = b.dataset.theme === aktuell(); b.classList.toggle('primary', on); b.setAttribute('aria-pressed', on ? 'true' : 'false'); }); }
    markieren();
    box.append(reihe);
    return {box, abbauen(){ box.replaceChildren(); }};
  }

  // Die Ansicht: Navigation links, je Modus ein Fensterchen rechts. Rückgabe {abbauen, zeichnen, zeigen, modus}.
  function ansicht(S, box, kopfFlaeche){
    const A = root.sedraHarness.app;
    // Die API des Werkzeugs „Workflow Studio“ (sein Manifest nennt die Routen /api/objects und /api/actions), nicht die der Shell.
    const api = (pfad, optionen)=>S.ctx.api(pfad, optionen);          // die Routen /api/objects und /api/actions stehen in der Liste der Shell (shell.yaml)
    kopfFlaeche.koerper.hidden = true; kopfFlaeche.verben.hidden = true;           // die Fläche des Platzhalter-Werkzeugs bleibt leer
    const layout = d().el('div', 'hs-ws-layout');
    const nav = d().el('nav', 'hs-ws-nav'); nav.setAttribute('aria-label', 'Workflow Studio');
    nav.append(d().el('div', 'hs-ws-marke', 'SEDRA · WORKFLOW STUDIO'));
    const buehne = d().el('section', 'hs-ws-buehne');
    layout.append(nav, buehne);
    box.append(layout);
    const zustand = {modus: lesen(), felder: {}, knoepfe: {}, kontext: null, lauf: null};

    const aktiv = ()=>zustand.felder[zustand.modus];
    const zeichnen = ()=>{ const f = aktiv(); if(f) f.flaechen.forEach(x=>x.zeichnen()); };
    function einhaengen(modus){
      if(modus.assistent || modus.katalog || modus.design){
        const teil = modus.assistent
          ? baueAssistent(api, rec=>{ zustand.kontext = rec; if(zustand.lauf) zustand.lauf.setze(rec); zeigen('live'); })
          : modus.design ? baueDesign()
          : baueKatalog(api, id=>{ zeigen('startassistent'); const s = zustand.felder.startassistent; if(s && s.teil) s.teil.oeffne(id); });
        const pane = d().el('div', 'hs-ws-pane'); pane.dataset.modus = modus.id; pane.append(teil.box);
        buehne.append(pane);
        zustand.felder[modus.id] = {pane, teil, flaechen: [{zeichnen(){}, abbauen(){ teil.abbauen(); }}]};
        return;
      }
      const pane = d().el('div', 'hs-ws-pane' + (modus.zellen.length > 1 ? ' raster' : '')); pane.dataset.modus = modus.id;
      const extra = [];
      if(modus.kpi){
        const lt = baueLeitstand(api, id=>zeigen(id), id=>{ zeigen('startassistent'); const s = zustand.felder.startassistent; if(s && s.teil) s.teil.oeffne(id); });
        pane.append(lt.box); extra.push({zeichnen(){}, abbauen(){ lt.abbauen(); }});
      }
      if(modus.notaus){
        const n = baueNotaus(api); pane.append(n.box); extra.push({zeichnen(){}, abbauen(){ n.abbauen(); }});
        const l = baueLauf(api); pane.append(l.box); extra.push({zeichnen(){}, abbauen(){ l.abbauen(); }});
        zustand.lauf = l; l.setze(zustand.kontext);                 // zeigt den zuletzt gestarteten Workflow, falls vorhanden
        const la = baueLaeufe(api); pane.append(la.box); extra.push({zeichnen(){}, abbauen(){ la.abbauen(); }});
        zustand.frisch = (zustand.frisch || []).concat([n.aktualisieren, la.aktualisieren]);     // beim Anzeigen frisch lesen, kein Takt
      }
      const flaechen = modus.zellen.map(objekt=>{
        const eigene = objekt.eigene && root.sedraHarness[objekt.eigene];
        const flaeche = eigene ? eigene.flaeche(S) : A.flaeche(S, objekt);
        const zelle = d().el('section', 'hs-ws-zelle'); zelle.dataset.zelle = objekt.type;
        if(modus.zellen.length > 1) zelle.append(d().el('h3', 'hs-ws-zellenkopf', objekt.title));
        zelle.append(flaeche.verben, flaeche.koerper);
        pane.append(zelle);
        return flaeche;
      });
      buehne.append(pane);
      zustand.felder[modus.id] = {pane, flaechen: extra.concat(flaechen)};
    }
    function zeigen(id){
      const modus = MODI.find(m=>m.id === id) || MODI[0];
      zustand.modus = modus.id; merken(modus.id);
      if(!zustand.felder[modus.id]) einhaengen(modus);
      MODI.forEach(m=>{
        const f = zustand.felder[m.id]; if(f) f.pane.hidden = m.id !== modus.id;           // verstecken, nicht aushängen
        const on = m.id === modus.id; const k = zustand.knoepfe[m.id];
        if(!k) return;
        k.classList.toggle('on', on); k.setAttribute('aria-current', on ? 'page' : 'false');
      });
      if(modus.notaus && zustand.frisch) zustand.frisch.forEach(f=>{ try{ f(); }catch(_e){} });   // Notaus und Läufe beim Anzeigen frisch lesen
      zeichnen();
    }
    GRUPPEN.forEach(g=>{
      const eintraege = MODI.filter(m=>m.gruppe === g); if(!eintraege.length) return;
      const abschnitt = d().el('div', 'hs-ws-gruppe');
      abschnitt.append(d().el('h4', 'hs-ws-gruppen-titel', g));
      eintraege.forEach(m=>{
        const b = d().el('button', 'hs-ws-nav-knopf', m.label); b.type = 'button'; b.dataset.modus = m.id;
        b.onclick = ()=>zeigen(m.id);
        zustand.knoepfe[m.id] = b; abschnitt.append(b);
      });
      nav.append(abschnitt);
    });
    zeigen(zustand.modus);
    return {
      zeichnen,
      zeigen,
      modus: ()=>zustand.modus,
      abbauen(){
        Object.values(zustand.felder).forEach(f=>f.flaechen.forEach(x=>{ try{ x.abbauen(); }catch(_e){} }));
        zustand.felder = {};
      }
    };
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.workflow_studio = {MODI, GRUPPEN, KEY, OBJEKT, modusWahl, luecken, ansicht};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.workflow_studio;
})();
