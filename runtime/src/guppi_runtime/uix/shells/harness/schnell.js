// Harness-Shell – der Aufnahme-Knopf der Taskleiste (Captain 04.11.2026): „🎙 Aufnehmen“ steht immer sichtbar in der Taskleiste; ein Klick startet die Sprachaufnahme (PC-Ton als Standard, wie im Werkzeug
// „Rekorder“: POST /api/sprache/kern/start). Während der Aufnahme wird der Knopf rot und zeigt die Zeit („● 0:42 Stopp“); ein Klick beendet und sichert sie. Pause, Abspielen und die
// Abschrift bleiben in der App Rekorder (Rechtsklick oder Umschalt+Klick auf den Knopf öffnet sie). Der Übersetzer bleibt eine App (Start → Übersetzer).
// Kein Dauer-Abruf (HS-52a): der Stand wird mit dem Status der Taskleiste gelesen; nur die Sekundenanzeige tickt, solange eine Aufnahme läuft und der Tab sichtbar ist.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const zeit = s=>{ s = Math.max(0, Math.round(Number(s) || 0)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
  function st(S){ return S._schnell || (S._schnell = {aufnahme: null, gelesen: 0, knopf: null, takt: null}); }
  const aktiv = a=>!!a && (a.status === 'laeuft' || a.status === 'pause');
  const laeuft = S=>aktiv(st(S).aufnahme);
  function sekunden(S){
    const x = st(S), a = x.aufnahme;
    if(!aktiv(a)) return 0;
    return Number(a.sekunden || 0) + (a.status === 'laeuft' ? (performance.now() - x.gelesen) / 1000 : 0);
  }

  function anzeigen(S){
    const x = st(S), k = x.knopf; if(!k) return;
    const an = laeuft(S), pause = an && x.aufnahme.status === 'pause';
    k.classList.toggle('rec', an && !pause); k.classList.toggle('pause', pause);
    k.replaceChildren(d().el('span', 'hs-rec-punkt', an ? (pause ? '❚❚' : '●') : '🎙'),
                      d().el('b', null, an ? zeit(sekunden(S)) : 'Aufnehmen'),
                      d().el('small', null, an ? 'Stopp' : ''));
    k.title = an ? 'Es wird aufgenommen' + (pause ? ' (Pause)' : '') + ' – Klick beendet und sichert die Aufnahme im Projekt'
                 : 'Sprachaufnahme starten (PC-Ton, Standard) – Umschalt+Klick öffnet den Rekorder';
    k.setAttribute('aria-pressed', an ? 'true' : 'false');
    takt(S);
  }

  // Stand der Aufnahme im Kern lesen (fällt der Aufruf aus, bleibt der alte Stand) – wird nie abgelehnt
  function lesen(S){
    return S.api('/api/sprache/kern/stand').then(a=>{ const x = st(S); x.aufnahme = a; x.gelesen = performance.now(); anzeigen(S); }).catch(()=>{});
  }

  // Sekundenanzeige: nur solange eine Aufnahme läuft und der Tab sichtbar ist
  function takt(S){
    const x = st(S);
    if(x.takt){ clearTimeout(x.takt); x.takt = null; }
    if(!laeuft(S) || document.hidden || x.aufnahme.status === 'pause') return;
    x.takt = setTimeout(()=>{
      x.takt = null;
      const b = x.knopf && x.knopf.querySelector('b'); if(b && laeuft(S)) b.textContent = zeit(sekunden(S));
      takt(S);
    }, 1000);
  }

  async function umschalten(S){
    const x = st(S), an = laeuft(S);
    x.knopf.disabled = true;
    try{
      if(an){
        const a = await S.api('/api/sprache/kern/stopp', {method: 'POST', body: {}});
        S.hinweis('Aufnahme gesichert: „' + (a.titel || 'Aufnahme') + '“ · ' + zeit(a.dauer) + ' – in der App Rekorder ansehen und abschreiben.');
      }else{
        await S.api('/api/sprache/kern/start', {method: 'POST', body: {titel: '', sprache: 'de'}});
      }
    }catch(err){ S.hinweis((an ? 'Nicht gesichert: ' : 'Keine Aufnahme: ') + (err && err.message || err), 'warn'); }
    x.knopf.disabled = false;
    await lesen(S);
  }

  // der feste Knopf der Taskleiste (einmal gebaut, danach nur beschriftet)
  function knopf(S){
    const k = d().el('button', 'hs-rec'); k.type = 'button';
    st(S).knopf = k;
    k.onclick = e=>{
      if(e.shiftKey){ const o = (root.sedraPlaces.PLACES || []).find(p=>p.id === 'aufnahme'); if(o) root.sedraHarness.app.oeffnen(S, o); return; }
      umschalten(S);
    };
    k.oncontextmenu = e=>{ e.preventDefault(); const o = (root.sedraPlaces.PLACES || []).find(p=>p.id === 'aufnahme'); if(o) root.sedraHarness.app.oeffnen(S, o); };
    anzeigen(S);
    lesen(S);
    return k;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.schnell = {knopf, anzeigen, lesen, laeuft, takt, zeit};
})();
