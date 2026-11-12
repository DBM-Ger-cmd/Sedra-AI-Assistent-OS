// Harness-Shell: die App „Team“ (A3 Paperclip als App, SPEC_APP_TEAM_v1) – Überblick · Issues · Vorhaben · Organigramm · Routinen · Kosten in einem App-Reiter.
//
// Die Werkzeuge des Teams (board, intent, org, routines, meter, decisions) bleiben, was sie sind; hier hängt sie niemand neu zusammen. Jede Zelle bekommt ihre Fläche über
// denselben Weg wie jeder App-Reiter (`app.flaeche(S, objekt)`), kein zweiter Einhängeweg. Neu gegenüber der alten Shell „paperclip“:
//   - der Überblick zeigt Posteingang, Issues, Organigramm und Kosten zugleich (mehrere Werkzeuge auf einer Fläche, TM-10);
//   - ein Modus wird beim ersten Öffnen eingehängt und beim Wechsel nur versteckt – Eingaben und Ansichten bleiben (TM-20);
//   - der zuletzt aktive Modus wird je Browser gemerkt, nie ein Inhalt (TM-21).
// Nicht gebaut: der Agentenfenster-Stapel am rechten Rand und Hinweise auf `agent.changed`/`budget.warning` (die Werkzeuge frischen sich selbst auf).
// Text nur mit textContent, Farben nur über Tokens, keine Takte.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const KEY = 'sedra.harness.team.modus';
  const OBJEKT = {type: 'team', id: 'app', title: 'Team'};

  const POSTEINGANG = {type: 'decision', id: 'alle', title: 'Posteingang', collection: true};
  const ISSUES = {type: 'issue', id: 'alle', title: 'Issues', collection: true};
  const VORHABEN = {type: 'intent', id: 'alle', title: 'Vorhaben', collection: true};
  const ORGANIGRAMM = {type: 'agent', id: 'alle', title: 'Organigramm', collection: true};
  const ROUTINEN = {type: 'routine', id: 'alle', title: 'Routinen', collection: true};
  const KOSTEN = {type: 'meter', id: 'meter', title: 'Sedra Token'};

  const MODI = [
    {id: 'ueberblick', label: 'Überblick', zellen: [POSTEINGANG, ISSUES, ORGANIGRAMM, KOSTEN]},
    {id: 'issues', label: 'Issues', zellen: [ISSUES]},
    {id: 'vorhaben', label: 'Vorhaben', zellen: [VORHABEN]},
    {id: 'organigramm', label: 'Organigramm', zellen: [ORGANIGRAMM]},
    {id: 'routinen', label: 'Routinen', zellen: [ROUTINEN]},
    {id: 'kosten', label: 'Kosten', zellen: [KOSTEN]}
  ];

  // rein
  function modusWahl(gemerkt){ return MODI.some(m=>m.id === gemerkt) ? gemerkt : MODI[0].id; }
  function lesen(){ try{ return modusWahl(localStorage.getItem(KEY)); }catch(_e){ return MODI[0].id; } }
  function merken(id){ try{ localStorage.setItem(KEY, id); }catch(_e){} }

  // Die Ansicht: Reiter und ein Fensterchen je Modus, im Überblick ein Raster aus Zellen. Rückgabe {abbauen, zeichnen, zeigen, modus}.
  function ansicht(S, box, kopfFlaeche){
    const A = root.sedraHarness.app;
    kopfFlaeche.koerper.hidden = true; kopfFlaeche.verben.hidden = true;           // die Fläche des Platzhalter-Werkzeugs „team“ bleibt leer
    const leiste = d().el('div', 'hs-app-reiter'); leiste.setAttribute('role', 'tablist');
    const buehne = d().el('div', 'hs-tm-buehne');
    box.append(leiste, buehne);
    const zustand = {modus: lesen(), felder: {}, knoepfe: {}};

    const aktiv = ()=>zustand.felder[zustand.modus];
    const zeichnen = ()=>{ const f = aktiv(); if(f) f.flaechen.forEach(x=>x.zeichnen()); };
    function einhaengen(modus){
      const pane = d().el('div', 'hs-tm-pane' + (modus.zellen.length > 1 ? ' raster' : '')); pane.dataset.modus = modus.id;
      const flaechen = modus.zellen.map(objekt=>{
        const flaeche = A.flaeche(S, objekt);
        const zelle = d().el('section', 'hs-tm-zelle'); zelle.dataset.zelle = objekt.type;
        if(modus.zellen.length > 1) zelle.append(d().el('h3', 'hs-tm-zellenkopf', objekt.title));
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
        const f = zustand.felder[m.id]; if(f) f.pane.hidden = m.id !== modus.id;           // verstecken, nicht aushängen (TM-20)
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
      abbauen(){                                                       // beim Schließen des Reiters werden alle eingehängten Zellen ausgehängt
        Object.values(zustand.felder).forEach(f=>f.flaechen.forEach(x=>{ try{ x.abbauen(); }catch(_e){} }));
        zustand.felder = {};
      }
    };
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.team = {MODI, KEY, OBJEKT, modusWahl, ansicht};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.team;
})();
