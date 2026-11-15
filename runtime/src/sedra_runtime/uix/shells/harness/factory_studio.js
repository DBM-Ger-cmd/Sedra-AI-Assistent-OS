// Harness-Shell: die App „Factory Studio“ (F3-01, erste lesende Stufe) – Project Browser und Status Dashboard in einem App-Reiter.
//
// Die zugrundeliegenden Werkzeuge (files für Projekte, decisions für offene Gates, meter für Health) bleiben, was sie sind;
// jede Zelle bekommt ihre Fläche über denselben Weg wie jeder App-Reiter (`app.flaeche(S, objekt)`), kein zweiter Einhängeweg.
// Ein Modus wird beim ersten Öffnen eingehängt und beim Wechsel nur versteckt. Der zuletzt aktive Modus wird je Browser gemerkt.
// Text nur mit textContent, Farben nur über Tokens, kein Takt. Eigene Texte einsprachig deutsch.
// Keine Schreibaktionen, kein Gate Panel, kein Start eines Builds (erste Stufe nur lesend).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const KEY = 'sedra.harness.factory_studio.modus';
  const OBJEKT = {type: 'factory-studio', id: 'app', title: 'Factory Studio'};

  const PROJEKT = {type: 'project', id: 'projekt', title: 'Projekte'};
  const GATES = {type: 'decision', id: 'alle', title: 'Offene Gates', collection: true};
  const METER = {type: 'meter', id: 'meter', title: 'Sedra Token'};

  // Zellen mit `eigene` sind eigene Lese-Ansichten dieser App (shells/harness/factory_*.js, Routen /api/uix/factory/*), alle anderen Zellen hängen ein Werkzeug ein.
  const HEALTH = {type: 'factory-health', id: 'health', title: 'Factory Health', eigene: 'factory_health'};
  const TYPEN = {type: 'factory-typen', id: 'typen', title: 'Factory-Typen', eigene: 'factory_typen'};
  const LAEUFE = {type: 'factory-laeufe', id: 'laeufe', title: 'Läufe und Benchmarks', eigene: 'factory_laeufe'};

  const MODI = [
    {id: 'projektbrowser', label: 'Projekt Browser', zellen: [PROJEKT]},
    {id: 'statusdashboard', label: 'Status Dashboard', zellen: [GATES, METER, HEALTH]},
    {id: 'typen', label: 'Typen', zellen: [TYPEN]},
    {id: 'laeufe', label: 'Läufe', zellen: [LAEUFE]}
  ];

  // rein
  function modusWahl(gemerkt){ return MODI.some(m=>m.id === gemerkt) ? gemerkt : MODI[0].id; }
  function lesen(){ try{ return modusWahl(localStorage.getItem(KEY)); }catch(_e){ return MODI[0].id; } }
  function merken(id){ try{ localStorage.setItem(KEY, id); }catch(_e){} }

  // Die Ansicht: Reiter und ein Fensterchen je Modus. Rückgabe {abbauen, zeichnen, zeigen, modus}.
  function ansicht(S, box, kopfFlaeche){
    const A = root.sedraHarness.app;
    kopfFlaeche.koerper.hidden = true; kopfFlaeche.verben.hidden = true;           // die Fläche des Platzhalter-Werkzeugs bleibt leer
    const leiste = d().el('div', 'hs-app-reiter'); leiste.setAttribute('role', 'tablist');
    const buehne = d().el('div', 'hs-fs-buehne');
    box.append(leiste, buehne);
    const zustand = {modus: lesen(), felder: {}, knoepfe: {}};

    const aktiv = ()=>zustand.felder[zustand.modus];
    const zeichnen = ()=>{ const f = aktiv(); if(f) f.flaechen.forEach(x=>x.zeichnen()); };
    function einhaengen(modus){
      const pane = d().el('div', 'hs-fs-pane' + (modus.zellen.length > 1 ? ' raster' : '')); pane.dataset.modus = modus.id;
      const flaechen = modus.zellen.map(objekt=>{
        const eigene = objekt.eigene && root.sedraHarness[objekt.eigene];
        const flaeche = eigene ? eigene.flaeche(S) : A.flaeche(S, objekt);
        const zelle = d().el('section', 'hs-fs-zelle'); zelle.dataset.zelle = objekt.type;
        if(modus.zellen.length > 1) zelle.append(d().el('h3', 'hs-fs-zellenkopf', objekt.title));
        zelle.append(flaeche.verben, flaeche.koerper);
        pane.append(zelle);
        return flaeche;
      });
      buehne.append(pane);
      zustand.felder[modus.id] = {pane, flaechen};
    }
    function zeigen(id){
      const modus = MODI.find(m=>m.id === id) || MODI[0];
      zustand.modus = modus.id; merken(modus.id);
      if(!zustand.felder[modus.id]) einhaengen(modus);
      MODI.forEach(m=>{
        const f = zustand.felder[m.id]; if(f) f.pane.hidden = m.id !== modus.id;           // verstecken, nicht aushängen
        const on = m.id === modus.id; zustand.knoepfe[m.id].classList.toggle('on', on); zustand.knoepfe[m.id].setAttribute('aria-selected', on ? 'true' : 'false');
      });
      zeichnen();
    }
    MODI.forEach(m=>{
      const b = d().el('button', 'hs-app-reiter-knopf', m.label); b.type = 'button'; b.setAttribute('role', 'tab'); b.dataset.modus = m.id;
      b.onclick = ()=>zeigen(m.id);
      zustand.knoepfe[m.id] = b; leiste.append(b);
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
  root.sedraHarness.factory_studio = {MODI, KEY, OBJEKT, modusWahl, ansicht};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.factory_studio;
})();
