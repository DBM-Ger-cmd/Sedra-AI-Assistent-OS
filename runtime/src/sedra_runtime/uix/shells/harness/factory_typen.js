// Ansicht „Typen“ der App Factory Studio (F3-01): der Katalog der registrierten Factory-Typen aus GET /api/uix/factory/typen (nur lesen).
// Grundlage: Entwurf von Pi (A-020). Rückgabe wie eine App-Fläche: {verben, koerper, zeichnen, abbauen}. Text nur mit textContent.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Eine ehrliche Meldung zu `quelle` (fehlt/fehler sind normale Zustände, kein Absturz).
  function quelleSatz(daten){
    if(!daten || daten.quelle === 'ok') return null;
    return (daten.quelle === 'fehler' ? 'Quelle nicht lesbar: ' : 'Quelle fehlt: ') + (daten.grund || 'ohne Angabe');
  }

  function zeile(t){
    const z = d().el('div', 'hs-zelle hs-fs-typ'); z.dataset.typ = t.typ_id;
    z.append(d().el('b', null, t.typ_id), d().el('span', null, ' · ' + (t.name || '–')),
             d().el('small', 'hs-leise', ' ' + (t.zustand || '–') + ' · Gate: ' + (t.gate_freigabe ? 'freigegeben' : 'nicht freigegeben')),
             d().el('small', 'hs-leise', ' · Funktionen: ' + (t.funktionen && t.funktionen.length ? t.funktionen.join(', ') : '–')));
    return z;
  }

  function flaeche(S){
    const verben = d().el('div', 'hs-fs-verben'), koerper = d().el('div', 'hs-fs-typen');
    let tot = false;
    function zeigen(daten, fehler){
      if(tot) return;
      const satz = fehler ? 'Quelle nicht erreichbar: ' + fehler : quelleSatz(daten);
      if(satz) return koerper.replaceChildren(d().el('div', 'hs-leise hs-fs-satz', satz));
      const typen = daten.typen || [];
      koerper.replaceChildren(...(typen.length ? typen.map(zeile) : [d().el('div', 'hs-leise hs-fs-satz', 'Keine Factory-Typen registriert.')]));
    }
    function zeichnen(){
      return S.api('/api/uix/factory/typen').then(x=>zeigen(x), e=>zeigen(null, e && e.message ? e.message : String(e)));
    }
    return {verben, koerper, zeichnen, abbauen(){ tot = true; }};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.factory_typen = {flaeche, quelleSatz, zeile};
})();
