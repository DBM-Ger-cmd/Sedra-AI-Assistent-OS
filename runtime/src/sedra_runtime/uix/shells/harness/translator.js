// Harness-Shell: die App „Translator“ (SPEC_APP_TRANSLATOR_v1, A3 Schritt 1 bis 4) – vier Modi in einem App-Reiter: Übersetzen · News · Aufnahme · Transkript.
//
// Die vier Werkzeuge bleiben, was sie sind; hier hängt sie niemand neu zusammen. Jeder Modus bekommt seine Fläche über denselben Weg wie jeder App-Reiter
// (`app.flaeche(S, objekt)` → `ctx.tools.forObject` und den Einhängeweg der Werkzeuge), kein zweiter Einhängeweg. Neu gegenüber der alten Shell „fisch“ (B5):
//   - ein Modus wird beim ersten Öffnen eingehängt und beim Wechsel nur versteckt – Eingaben und Ergebnisse bleiben (TR-20);
//   - die „Wolke“ (ein Feld über den Reitern) gibt den Satz als `frage` an den aktiven Modus (TR-11); Strg+K fokussiert sie, solange der Reiter vorn ist (TR-12);
//   - der zuletzt aktive Modus wird je Browser gemerkt, nie ein Text (TR-21);
//   - ein `open` auf einen der vier Objekttypen (Transkript → „An den Übersetzer“, Rekorder → „Transkript öffnen“) kommt im offenen Translator an,
//     auch wenn der Modus schon eingehängt ist: nur dieser Modus wird neu eingehängt, die anderen behalten ihren Zustand (TR-30, TR-32, TR-E3).
// Die Liste der Modi ist die der Shell `fisch` (ein Test hält beide gleich). Text nur mit textContent, Farben nur über Tokens.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const KEY = 'sedra.harness.translator.modus';
  const OBJEKT = {type: 'translator', id: 'app', title: 'Translator'};

  const MODI = [
    {id: 'uebersetzen', label: 'Übersetzen', object: {type: 'uebersetzung', id: 'wolke', title: 'Übersetzen'},
     platzhalter: 'Was soll der Translator für eine andere Rolle neu formulieren?'},
    {id: 'news', label: 'News', object: {type: 'nachrichten', id: 'brief', title: 'Nachrichten'},
     platzhalter: 'Wofür interessierst du dich heute? (wird zu den Interessen des Briefs)'},
    {id: 'aufnahme', label: 'Aufnahme', object: {type: 'aufnahme', id: 'rekorder', title: 'Rekorder'},
     platzhalter: 'Ein Titel für die nächste Aufnahme – Enter trägt ihn in den Rekorder ein'},
    {id: 'transkript', label: 'Transkript', object: {type: 'transkript', id: 'alle', title: 'Transkripte'},
     platzhalter: 'Wonach soll der Translator im Transkript suchen?'}
  ];

  // rein
  function modusFuer(typ){ return MODI.find(m=>m.object.type === typ) || null; }
  function modusWahl(gemerkt){ return MODI.some(m=>m.id === gemerkt) ? gemerkt : MODI[0].id; }
  function lesen(){ try{ return modusWahl(localStorage.getItem(KEY)); }catch(_e){ return MODI[0].id; } }
  function merken(id){ try{ localStorage.setItem(KEY, id); }catch(_e){} }
  function reiterId(){ return root.sedraHarness.app.reiterId(OBJEKT); }
  function offen(S){ return root.sedraHarness.app.liste(S).indexOf(reiterId()) >= 0; }

  // Die Ansicht: Wolke, Reiter, ein Fensterchen je Modus. Rückgabe {abbauen, zeichnen, zeigen, uebergeben}.
  function ansicht(S, box, kopfFlaeche){
    const A = root.sedraHarness.app;
    kopfFlaeche.koerper.hidden = true; kopfFlaeche.verben.hidden = true;           // die Fläche des Platzhalter-Werkzeugs „translator“ bleibt leer
    const wolke = d().el('textarea', 'hs-tr-wolke'); wolke.rows = 2; wolke.setAttribute('aria-label', 'Wolke – Satz für den aktiven Modus');
    const leiste = d().el('div', 'hs-app-reiter'); leiste.setAttribute('role', 'tablist');
    const buehne = d().el('div', 'hs-tr-buehne');
    box.append(wolke, leiste, buehne);
    const zustand = {modus: lesen(), felder: {}, knoepfe: {}};

    const aktiv = ()=>zustand.felder[zustand.modus];
    const zeichnen = ()=>{ const f = aktiv(); if(f) f.flaeche.zeichnen(); };
    function einhaengen(modus, objekt){
      const alt = zustand.felder[modus.id];
      if(alt){ alt.flaeche.abbauen(); alt.pane.remove(); }
      const pane = d().el('div', 'hs-tr-pane'); pane.dataset.modus = modus.id;
      const flaeche = A.flaeche(S, objekt);
      pane.append(flaeche.verben, flaeche.koerper);
      buehne.append(pane);
      zustand.felder[modus.id] = {pane, flaeche, objekt};
    }
    function zeigen(id, objekt){
      const modus = MODI.find(m=>m.id === id) || MODI[0];
      zustand.modus = modus.id; merken(modus.id);
      if(objekt || !zustand.felder[modus.id]) einhaengen(modus, objekt || Object.assign({}, modus.object));
      MODI.forEach(m=>{
        const f = zustand.felder[m.id]; if(f) f.pane.hidden = m.id !== modus.id;           // verstecken, nicht aushängen (TR-20)
        const on = m.id === modus.id; zustand.knoepfe[m.id].classList.toggle('on', on); zustand.knoepfe[m.id].setAttribute('aria-selected', on ? 'true' : 'false');
      });
      wolke.placeholder = modus.platzhalter;
      zeichnen();
    }
    MODI.forEach(m=>{
      const b = d().el('button', 'hs-app-reiter-knopf', m.label); b.type = 'button'; b.setAttribute('role', 'tab'); b.dataset.modus = m.id;
      b.onclick = ()=>zeigen(m.id);
      zustand.knoepfe[m.id] = b; leiste.append(b);
    });

    // Wolke (TR-11): Enter sendet, Umschalt+Enter ist ein Zeilenumbruch; der Satz geht als `frage` an den aktiven Modus
    function senden(){
      const text = wolke.value.trim(); if(!text) return;
      wolke.value = '';
      const modus = MODI.find(m=>m.id === zustand.modus);
      if(modus.id === 'aufnahme'){                                  // der Satz wird der Titel im ersten Feld, das Pult bleibt (nichts wird neu eingehängt)
        const feld = aktiv() && aktiv().pane.querySelector('input'); if(feld){ feld.value = text; feld.focus(); }
        return;
      }
      zeigen(modus.id, Object.assign({}, modus.object, {frage: text}));
    }
    wolke.addEventListener('keydown', e=>{ if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); senden(); } });

    // Strg+K (TR-12): nur solange dieser Reiter vorn ist; sonst bleibt es, was One Sedra festlegt
    const taste = e=>{
      if(!((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K'))) return;
      if(root.sedraHarness.reiter.aktiv(S) !== reiterId() || !box.isConnected) return;
      e.preventDefault(); e.stopPropagation(); wolke.focus();
    };
    document.addEventListener('keydown', taste, true);

    zeigen(zustand.modus);
    return {
      zeichnen,
      zeigen,
      // ein open auf einen Objekttyp eines Modus (TR-30/32): Modus vorn, dort das neue Objekt eingehängt
      uebergeben(objekt){ const m = modusFuer(objekt.type); if(!m) return false; zeigen(m.id, Object.assign({}, objekt)); return true; },
      modus: ()=>zustand.modus,
      abbauen(){                                                       // beim Schließen des Reiters werden alle eingehängten Modi ausgehängt
        document.removeEventListener('keydown', taste, true);
        Object.values(zustand.felder).forEach(f=>{ try{ f.flaeche.abbauen(); }catch(_e){} });
        zustand.felder = {};
      }
    };
  }

  // Aus app.oeffnen: ist der Translator offen und gehört das Objekt zu einem Modus, geht es dorthin. Rückgabe: die Reiter-ID, sonst null.
  function uebergeben(S, objekt){
    if(!objekt || !modusFuer(objekt.type) || !offen(S)) return null;
    const t = S._translatorAnsicht;
    if(!t || !t.uebergeben(objekt)) return null;
    const id = reiterId();
    root.sedraHarness.reiter.aktivieren(S, id);
    return id;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.translator = {MODI, KEY, OBJEKT, modusFuer, modusWahl, ansicht, uebergeben, reiterId, offen};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.translator;
})();
