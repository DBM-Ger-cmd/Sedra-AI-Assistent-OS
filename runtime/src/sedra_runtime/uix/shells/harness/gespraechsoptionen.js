// Harness-Shell – aufklappbare Optionen zur Gesprächsführung unter dem Schild im Eingabefeld (Captain 03.11.2026): ein Klick auf „⛨ … gibt frei“ klappt ein kleines Feld auf mit
// den Wahlen, die man mitten im Gespräch braucht – Denken eingrenzen, ob die Gedanken ans Modell zurückgehen, Antwortbudget, Länge des Verlaufs. Die Werte sind dieselben Vorgaben
// wie auf der Seite „Token und Gespräch“ (Einstellungen → Agent), gelesen und geschrieben über /api/harness/vorgaben; die Listen kommen aus tokenseite.js, damit es nur eine Quelle gibt.
// Eine Wahl gilt ab der nächsten Nachricht. Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const SPAR_SCHLUESSEL = ['denken', 'antwort_budget', 'verlauf_laenge'];

  // reine Beschreibung der Zeilen: [{schluessel, titel, hilfe, wahl: [[wert, name, text]]}] – aus der Seite „Token und Gespräch“
  function zeilen(){
    const T = root.sedraHarness && root.sedraHarness.tokenseite;
    if(!T) return [];
    const spar = T.SPAREN.filter(z=>SPAR_SCHLUESSEL.indexOf(z[0]) >= 0).map(([schluessel, titel, wahl, hilfe])=>({schluessel, titel, hilfe, wahl}));
    const gedanken = {schluessel: 'gedanken_zurueck', titel: 'Gedanken ans Modell zurücksenden', wahl: T.GEDANKEN,
                      hilfe: 'Sedra speichert die Gedanken immer und zeigt sie dir aufklappbar. Hier wählst du, wie viel davon beim nächsten Mal wieder an das Modell geht (mehr kostet Token).'};
    const wissen = {schluessel: 'wissen_zuerst', titel: 'Wissen zuerst', wahl: [['an', 'an', ''], ['aus', 'aus', '']],
                    hilfe: 'An: vor jeder Frage sucht Sedra im Wissen und gibt die Fundstellen mit (SPEC_WISSEN_KERN_v1). Aus: das Modell sucht nur, wenn es selbst wissen_suchen ruft.'};
    return [spar[0], gedanken, ...spar.slice(1), wissen].filter(Boolean);
  }

  // das Feld: { el, umschalten(knopf) }
  function panel(S){
    const el = d().el('div', 'hs-optionen'); el.hidden = true; el.setAttribute('role', 'group'); el.setAttribute('aria-label', 'Optionen zur Gesprächsführung');
    const meld = d().el('small', 'hs-leise', '');
    const selects = {};
    const aufbauen = ()=>{
      el.replaceChildren(d().el('b', null, 'Gesprächsführung'), d().el('small', 'hs-leise', 'Gilt ab der nächsten Nachricht. Mehr dazu und der Verbrauch: „Token und Gespräch“.'));
      zeilen().forEach(z=>{
        const zeile = d().el('label', 'hs-opt-zeile');
        const sel = d().el('select', 'hs-projektwahl'); sel.setAttribute('aria-label', z.titel);
        z.wahl.forEach(([wert, name])=>{ const o = document.createElement('option'); o.value = wert; o.textContent = name; sel.append(o); });
        sel.title = z.hilfe;
        sel.onchange = async()=>{
          try{ await S.api('/api/harness/vorgaben', {method: 'POST', body: {[z.schluessel]: sel.value}}); meld.textContent = z.titel + ': gespeichert.'; }
          catch(err){ meld.textContent = 'Nicht gespeichert: ' + err.message; laden(); }
        };
        selects[z.schluessel] = sel;
        zeile.append(d().el('span', 'hs-leise', z.titel), sel);
        el.append(zeile);
      });
      const mehr = d().el('button', 'hs-knopf hs-klein', 'Alle Optionen …'); mehr.type = 'button';
      mehr.onclick = ()=>{ el.hidden = true; root.sedraHarness.tokenseite.oeffnen(S, 'gespraech'); };
      el.append(mehr, meld);
    };
    function laden(){
      S.api('/api/harness/vorgaben').then(v=>Object.keys(selects).forEach(k=>{ if(v[k] !== undefined && v[k] !== null) selects[k].value = String(v[k]); })).catch(()=>{});
    }
    return {
      el,
      umschalten(knopf){
        el.hidden = !el.hidden;
        if(knopf) knopf.setAttribute('aria-expanded', el.hidden ? 'false' : 'true');
        if(!el.hidden){ aufbauen(); laden(); }
      },
      schliessen(knopf){ el.hidden = true; if(knopf) knopf.setAttribute('aria-expanded', 'false'); }
    };
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.gespraechsoptionen = {panel, zeilen};
})();
