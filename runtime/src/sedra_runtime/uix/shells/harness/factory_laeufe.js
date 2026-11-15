// Ansicht „Läufe“ der App Factory Studio (F3-01, Execution View F301-10/12): die letzten Läufe aus GET /api/uix/factory/runs und die gespeicherten
// Benchmarks aus GET /api/uix/factory/benchmarks (nur lesen; kein Start, kein Abbruch). Text nur mit textContent.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const T = ()=>root.sedraHarness.factory_typen;

  function dauer(ms){ return ms == null ? '–' : ms < 1000 ? ms + ' ms' : (ms / 1000).toFixed(1) + ' s'; }
  function zeit(iso){ const t = String(iso || ''); return t.length >= 16 ? t.slice(0, 10) + ' ' + t.slice(11, 16) : '–'; }

  function laufZeile(r){
    const z = d().el('div', 'hs-zelle hs-fs-lauf' + (r.erfolg ? ' ok' : ' bad')); z.dataset.run = r.run_id;
    z.append(d().el('b', null, r.name || r.run_id), d().el('span', null, ' · ' + r.typ_id + ' · ' + r.build_type),
             d().el('small', 'hs-leise', ' ' + (r.erfolg ? 'erfolgreich' : 'fehlgeschlagen') + ' · ' + zeit(r.gestartet) + ' · ' + dauer(r.dauer_ms) + ' · ' + (r.artefakte || 0) + ' Artefakte'));
    if(r.fehler) z.append(d().el('small', 'hs-fs-fehler', ' Fehler: ' + r.fehler));
    return z;
  }
  function benchZeile(b){
    const z = d().el('div', 'hs-zelle hs-fs-benchmark'); z.dataset.benchmark = b.benchmark_id;
    z.append(d().el('b', null, b.typ_id + (b.variante ? ' · ' + b.variante : '')),
             d().el('small', 'hs-leise', ' Punkte ' + (b.punkte == null ? '–' : b.punkte) + ' · ' + (b.laeufe == null ? '–' : b.laeufe) + ' Läufe · ' + zeit(b.angelegt)));
    return z;
  }

  function flaeche(S){
    const verben = d().el('div', 'hs-fs-verben'), koerper = d().el('div', 'hs-fs-laeufe');
    let tot = false;
    function abschnitt(titel, daten, fehler, zeilen, leer){
      const kopf = d().el('h3', 'hs-fs-zellenkopf', titel);
      const satz = fehler ? 'Quelle nicht erreichbar: ' + fehler : T().quelleSatz(daten);
      if(satz) return [kopf, d().el('div', 'hs-leise hs-fs-satz', satz)];
      return [kopf, ...(zeilen.length ? zeilen : [d().el('div', 'hs-leise hs-fs-satz', leer)])];
    }
    async function holen(pfad){
      try{ return [await S.api(pfad), null]; }catch(e){ return [null, e && e.message ? e.message : String(e)]; }
    }
    async function zeichnen(){
      const [runs, runFehler] = await holen('/api/uix/factory/runs');
      const [bench, benchFehler] = await holen('/api/uix/factory/benchmarks');
      if(tot) return;
      koerper.replaceChildren(
        ...abschnitt('Letzte Läufe', runs, runFehler, runs && runs.runs ? runs.runs.map(laufZeile) : [], 'Noch keine Läufe im Evidence Store.'),
        ...abschnitt('Benchmarks', bench, benchFehler, bench && bench.benchmarks ? bench.benchmarks.map(benchZeile) : [], 'Noch keine Benchmarks gespeichert.'));
    }
    return {verben, koerper, zeichnen, abbauen(){ tot = true; }};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.factory_laeufe = {flaeche, laufZeile, benchZeile, dauer};
})();
