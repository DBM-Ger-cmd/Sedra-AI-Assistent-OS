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
  const luecken = G.luecken, workflowsZaehlen = G.workflowsZaehlen;
  const baueKatalog = AS.baueKatalog;
  const KEY = 'sedra.harness.workflow_studio.modus';
  const OBJEKT = {type: 'workflow-studio', id: 'app', title: 'SEDRA Workflow Studio'};
  const THEME_KEY = 'sedra.theme';

  const EDITOR = {type: 'workflow', id: 'alle', title: 'Workflow-Editor', collection: true};
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
    {id: 'editor', label: 'Arbeitsfläche', gruppe: 'Direkt arbeiten', zellen: [EDITOR]},
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
  function modusWahl(gemerkt){ if(['n8n','szenario','live','startassistent'].includes(gemerkt)) return 'editor';return MODI.some(m=>m.id === gemerkt) ? gemerkt : MODI[0].id; }
  function lesen(){ try{ return modusWahl(localStorage.getItem(KEY)); }catch(_e){ return MODI[0].id; } }
  function merken(id){ try{ localStorage.setItem(KEY, id); }catch(_e){} }
  // Der Leitstand nach der Vorlage: Kontext, Arbeitslage, „Was liegt an?“, Kennzahlen und „Jetzt wichtig“. Alle Zahlen stammen aus den
  // gespeicherten Workflows und dem Fabrik-Stand; was nicht lädt, steht ehrlich als nicht geladen da.
  function baueLeitstand(api, zumModus, zumAssistent){
    const box = d().el('div', 'hs-ws-leitstand');
    const aktion = (text, fn)=>{ const b = d().el('button', 'hs-ws-knopf', text); b.type = 'button'; b.onclick = fn; return b; };
    const bannerText = d().el('span', '', 'Lade die gespeicherten Workflows …');
    const banner = d().el('div', 'hs-ws-banner'); banner.append(d().el('b', '', 'SEDRA – Arbeitslage'), bannerText);
    const kpiWerte = ['Gespeicherte Workflows', 'Ausführbar', 'Mit offenen Angaben', 'Fabrik'].map(titel=>{
      const k = d().el('div', 'hs-ws-kennzahl'); const w = d().el('b', 'hs-ws-kennzahl-wert', '…');
      k.append(d().el('span', 'hs-ws-kennzahl-titel', titel), w); return {k, w};
    });
    const kennzahlen = d().el('div', 'hs-ws-kennzahlen'); kpiWerte.forEach(x=>kennzahlen.append(x.k));
    const wichtigListe = d().el('div', 'hs-ws-liste');
    const wichtig = d().el('div', 'hs-ws-karte'); wichtig.append(d().el('h4', 'hs-ws-karten-titel', 'Offene Vorbereitungen'), wichtigListe);
    const was = d().el('div', 'hs-ws-was');
    was.append(d().el('h4', 'hs-ws-sektion', 'Dein nächster Schritt'));
    was.append(d().el('p', 'hs-ws-hinweis', 'Workflows bearbeiten, den Start vorbereiten oder einen laufenden Prozess untersuchen.'));
    was.append(d().el('div', 'hs-ws-knoepfe'));
    was.lastChild.append(aktion('Workflows öffnen', ()=>zumModus('katalog')), aktion('Editor öffnen', ()=>zumModus('editor')), aktion('Start vorbereiten', ()=>zumModus('startassistent')), aktion('Läufe untersuchen', ()=>zumModus('live')));
    box.append(d().el('p', 'hs-ws-kicker', 'SEDRA WORKFLOW STUDIO'), d().el('h2', 'hs-ws-leit-titel', 'Deine Workflows im Blick'), banner, kennzahlen, was, d().el('div', 'hs-ws-spalten', ''));
    box.querySelector('.hs-ws-spalten').append(wichtig);
    workflowsZaehlen(api).then(liste=>{
      const laufbar = liste.filter(w=>w.laufbar).length, offen = liste.filter(w=>w.offen > 0).length;
      kpiWerte[0].w.textContent = String(liste.length); kpiWerte[1].w.textContent = String(laufbar); kpiWerte[2].w.textContent = String(offen);
      const unbekannt=liste.filter(w=>!w.geprueft).length;
      bannerText.textContent = !liste.length ? 'Noch kein Workflow gespeichert.'
        : (offen ? offen + ' Workflows mit offenen Angaben. ' : '') + laufbar + ' ausführbar.' + (unbekannt ? ' '+unbekannt+' konnten nicht geprüft werden.' : '');
      wichtigListe.replaceChildren(...liste.filter(w=>w.offen > 0).map(w=>{
        const z = d().el('div', 'hs-ws-liste-zeile'); z.append(d().el('span', '', w.title + ' · ' + w.offen + ' offen'), aktion('Öffnen', ()=>zumAssistent(w.id))); return z;
      }));
      if(!wichtigListe.childNodes.length) wichtigListe.append(d().el('p', 'hs-ws-hinweis', unbekannt ? 'Einige Workflows konnten nicht geprüft werden. Öffne den Katalog für die Einzelansicht.' : 'Keine offenen Prozessangaben in den gespeicherten Workflows.'));
    }).catch(err=>{ bannerText.textContent = 'Workflows nicht geladen: ' + (err.message || err); kpiWerte.forEach(x=>{ x.w.textContent = '–'; }); });
    api('/api/actions', {method: 'POST', body: {type: 'workflow', id: null, verb: 'fabrik_status', args: {}}})
      .then(out=>{ const r = out.result || out; kpiWerte[3].w.textContent = r.angehalten ? 'angehalten' : 'freigegeben'; })
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
    const zustand = {modus: lesen(), felder: {}, knoepfe: {}};

    const aktiv = ()=>zustand.felder[zustand.modus];
    const zeichnen = ()=>{ const f = aktiv(); if(f) f.flaechen.forEach(x=>x.zeichnen()); };
    function einhaengen(modus){
      if(modus.katalog || modus.design){
        const teil = modus.design ? baueDesign()
          : baueKatalog(api, id=>oeffneObjekt({type:'workflow',id,mode:'runs'}), id=>oeffneObjekt({type:'workflow',id:id || 'neu'}));
        const pane = d().el('div', 'hs-ws-pane'); pane.dataset.modus = modus.id; pane.append(teil.box);
        buehne.append(pane);
        zustand.felder[modus.id] = {pane, teil, flaechen: [{zeichnen(){}, abbauen(){ teil.abbauen(); }}]};
        return;
      }
      const pane = d().el('div', 'hs-ws-pane' + (modus.zellen.length > 1 ? ' raster' : '')); pane.dataset.modus = modus.id;
      if(!modus.kpi && modus.id!=='editor'){
        const seitenkopf=d().el('header','hs-ws-seitenkopf');seitenkopf.append(d().el('h2','hs-ws-leit-titel',modus.label));pane.append(seitenkopf);
      }
      const extra = [];
      if(modus.kpi){
        const lt = baueLeitstand(api, id=>zeigen(id), id=>oeffneObjekt({type:'workflow',id,mode:'runs'}));
        pane.append(lt.box); extra.push({zeichnen(){}, abbauen(){ lt.abbauen(); }});
      }
      const flaechen = modus.zellen.map(objekt=>{
        const eigene = objekt.eigene && root.sedraHarness[objekt.eigene];
        const flaeche = eigene ? eigene.flaeche(S) : A.flaeche(S, objekt);
        const zelle = d().el('section', 'hs-ws-zelle'); zelle.dataset.zelle = objekt.type;
        if(modus.zellen.length > 1) zelle.append(d().el('h3', 'hs-ws-zellenkopf', objekt.title));
        if(objekt.type !== 'project') zelle.append(flaeche.verben);
        zelle.append(flaeche.koerper);
        pane.append(zelle);
        return flaeche;
      });
      buehne.append(pane);
      zustand.felder[modus.id] = {pane, flaechen: extra.concat(flaechen)};
    }
    function zeigen(id){
      if(['live','startassistent'].includes(id)){zeigen('editor');return root.sedraWorkflowEditor.openWithin(zustand.felder.editor.pane,{id:'alle',mode:id==='live'?'live':'runs'});}
      const modus = MODI.find(m=>m.id === id) || MODI[0];
      zustand.modus = modus.id; merken(modus.id);
      const vorhanden=zustand.felder[modus.id];
      if(!zustand.felder[modus.id]) einhaengen(modus);
      MODI.forEach(m=>{
        const f = zustand.felder[m.id]; if(f) f.pane.hidden = m.id !== modus.id;           // verstecken, nicht aushängen
        const on = m.id === modus.id; const k = zustand.knoepfe[m.id];
        if(!k) return;
        k.classList.toggle('on', on); k.setAttribute('aria-current', on ? 'page' : 'false');
      });
      if(vorhanden && vorhanden.teil && vorhanden.teil.aktualisieren)vorhanden.teil.aktualisieren();
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
    async function oeffneObjekt(objekt){
      if(objekt.type==='workflow_run'){const r=await api('/api/objects',{method:'POST',body:{type:'workflow_run',id:objekt.id}});objekt={type:'workflow',id:r.workflow_id,mode:'live',runId:r.id};}
      zeigen('editor');
      const feld=zustand.felder.editor;
      if(root.sedraWorkflowEditor && root.sedraWorkflowEditor.openWithin){
        await root.sedraWorkflowEditor.openWithin(feld.pane,objekt);
      }
    }
    return {
      oeffneObjekt,
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
