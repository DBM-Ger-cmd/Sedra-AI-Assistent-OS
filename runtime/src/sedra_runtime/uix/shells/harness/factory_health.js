// Karte „Factory Health“ im Status Dashboard der App Factory Studio (F3-01, F301-13): Registry und Evidence Store erreichbar, Zahlen je Quelle,
// aus GET /api/uix/factory/health (nur lesen). Offene Gates zeigt die Zelle „Offene Gates“ daneben. Text nur mit textContent.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  function zeile(name, ok, text){
    const z = d().el('div', 'hs-fs-health-zeile'); z.dataset.quelle = name;
    z.append(d().el('span', 'hs-fs-ampel ' + (ok ? 'ok' : 'bad'), ok ? '●' : '○'), d().el('b', null, ' ' + name), d().el('span', 'hs-leise', ' · ' + text));
    return z;
  }
  function zeilen(h){
    const reg = h.registry || {}, ev = h.evidence || {};
    const zustaende = reg.zustaende ? Object.keys(reg.zustaende).map(k=>k + ' ' + reg.zustaende[k]).join(', ') : '';
    const letzter = ev.letzter_lauf ? ' · letzter Lauf ' + String(ev.letzter_lauf).slice(0, 16).replace('T', ' ') : '';
    return [
      zeile('Registry', !!reg.erreichbar, reg.erreichbar ? reg.typen + ' Typen' + (zustaende ? ' (' + zustaende + ')' : '') + ' · Gate freigegeben: ' + (reg.gate_freigegeben || 0) : (reg.grund || 'nicht erreichbar')),
      zeile('Evidence Store', !!ev.erreichbar, ev.erreichbar ? ev.runs + ' Läufe · ' + ev.benchmarks + ' Benchmarks · ' + ev.gate_evidence + ' Gate-Nachweise' + letzter : (ev.grund || 'nicht erreichbar'))];
  }

  function flaeche(S){
    const verben = d().el('div', 'hs-fs-verben'), koerper = d().el('div', 'hs-fs-health');
    let tot = false;
    async function zeichnen(){
      let h, fehler = null;
      try{ h = await S.api('/api/uix/factory/health'); }catch(e){ fehler = e && e.message ? e.message : String(e); }
      if(tot) return;
      koerper.replaceChildren(...(fehler ? [d().el('div', 'hs-leise hs-fs-satz', 'Health nicht lesbar: ' + fehler)] : zeilen(h)));
    }
    return {verben, koerper, zeichnen, abbauen(){ tot = true; }};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.factory_health = {flaeche, zeilen};
})();
