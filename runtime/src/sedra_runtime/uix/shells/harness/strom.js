// Harness-Shell – der Strom-Leser (V8, 1.11.2026): SSE-Zerlegung und die Deutung der Ereignisse, ohne DOM, damit `node` sie prüfen kann
// (tests/test_uix_harness_strom_leser.py). verlauf.js ruft `lesen` (fetch + zerlegen) und zeichnet; hier steht, was ein Ereignis bedeutet.
// Der Strom: `id: n\nevent: name\ndata: {json}\n\n` je Ereignis (harness/strom.py sse()); Kommentarzeilen beginnen mit „:“ (Herzschlag).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;

  // ---- rein: einen Puffer in fertige Ereignisse und den Rest zerlegen
  function zerlegen(puffer){
    const ereignisse = [];
    let at;
    while((at = puffer.indexOf('\n\n')) >= 0){
      const roh = puffer.slice(0, at); puffer = puffer.slice(at + 2);
      const ev = {};
      roh.split('\n').forEach(l=>{ if(!l || l[0] === ':') return; const i = l.indexOf(': '); if(i > 0) ev[l.slice(0, i)] = l.slice(i + 2); });
      if(!ev.event) continue;
      let daten = {};
      try{ daten = JSON.parse(ev.data || '{}'); }catch(_e){ daten = {}; }
      ereignisse.push({id: Number(ev.id) || null, event: ev.event, daten});
    }
    return {ereignisse, rest: puffer};
  }

  // ---- rein: die Phase einer laufenden Antwort für die Zeitlinie (V3) – oder undefined, wenn das Ereignis sie nicht ändert
  function phaseFuer(name, x){
    if(name === 'zug.start') return 'denkt';
    if(name === 'text.ungeprueft') return 'schreibt';
    if(name === 'werkzeug.start') return 'Werkzeug ' + ((x && x.name) || '');
    if(name === 'karte') return 'wartet auf Freigabe';
    if(name === 'ende') return null;
    return undefined;
  }

  // ---- rein: Dauer als Text
  function dauerText(sekunden){
    if(typeof sekunden !== 'number' || !(sekunden >= 0)) return '';
    return sekunden < 1 ? Math.round(sekunden * 1000) + ' ms' : sekunden.toFixed(1).replace('.', ',') + ' s';
  }

  // ---- rein: der Text der Denkzeile
  function denkText(x, ab){
    if(x && x.verborgen) return 'Denkt nach (scharfer Modus: Inhalt erst nach dem Urteil)';
    const s = Math.max(0, ((x && x.t) || 0) - (ab || 0));
    return 'Denkt nach · ' + s.toFixed(1).replace('.', ',') + ' s';
  }

  // ---- mit Netz: den Strom einer Antwort ab `z.letzte` lesen; je Ereignis `aufEreignis(name, daten)`; endet mit `ende` (true) oder wenn der Server schließt (false).
  async function lesen(aid, z, aufEreignis, kopf, abbruch){
    const res = await fetch('/api/harness/antworten/' + aid + '/strom', {signal: abbruch.signal, headers: Object.assign({'Last-Event-ID': String(z.letzte || 0)}, kopf || {})});
    if(!res.ok){ const e = new Error('HTTP ' + res.status); e.status = res.status; throw e; }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let puffer = '';
    for(;;){
      const {value, done} = await reader.read();
      if(done) break;
      puffer += dec.decode(value, {stream: true});
      const aus = zerlegen(puffer); puffer = aus.rest;
      for(const ev of aus.ereignisse){
        if(ev.id) z.letzte = ev.id;
        aufEreignis(ev.event, ev.daten);
        if(ev.event === 'ende'){ z.fertig = true; abbruch.abort(); return true; }
      }
    }
    return false;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.strom = {zerlegen, phaseFuer, dauerText, denkText, lesen};
})();
