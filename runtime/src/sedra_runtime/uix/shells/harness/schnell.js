// Harness-Shell – der Aufnahme-Knopf der Taskleiste (Captain 04.11.2026): „🎙 Aufnehmen“ steht immer sichtbar in der Taskleiste; ein Klick startet die Sprachaufnahme (PC-Ton und Mikrofon in einer Spur als Standard, wie im Werkzeug
// „Rekorder“: POST /api/sprache/kern/start). Während der Aufnahme wird der Knopf rot und zeigt die Zeit („● 0:42 Stopp“); ein Klick beendet und sichert sie. Pause, Abspielen und die
// Abschrift bleiben in der App Rekorder (Rechtsklick oder Umschalt+Klick auf den Knopf öffnet sie). Der Übersetzer bleibt eine App (Start → Übersetzer).
// Kein Dauer-Abruf (HS-52a): der Stand wird mit dem Status der Taskleiste gelesen; nur die Sekundenanzeige tickt, solange eine Aufnahme läuft und der Tab sichtbar ist.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const T = root.t || (s => s);

  // Quelle des Knopfs (Captain 04.11.2026): Standard ist „beides“ (PC-Ton und Mikrofon in einer Spur); eine kleine Auswahl daneben wählt nur PC-Ton oder nur Mikrofon.
  // Die Wahl wird im Browser gemerkt (ohne Speicher bleibt es beim Standard). Nur eine abweichende Wahl geht als `quelle` an den Kern – so greift beim Standard dessen Rückfall auf das Mikrofon.
  const QUELLEN_KEYS = [['beides', 'schl_beides'], ['pc_ton', 'schl_pc_ton'], ['mikrofon', 'schl_mikro']];
  const SCHLUESSEL = 'sedra.harness.aufnahme.quelle';
  function gemerkt(){ try{ const v = localStorage.getItem(SCHLUESSEL); return QUELLEN_KEYS.some(q=>q[0] === v) ? v : 'beides'; }catch(_e){ return 'beides'; } }
  function merken(v){ try{ localStorage.setItem(SCHLUESSEL, v); }catch(_e){ /* ohne Speicher gilt die Wahl nur für diese Ansicht */ } }

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
                      d().el('b', null, an ? zeit(sekunden(S)) : T('schl_aufnehmen')),
                      d().el('small', null, an ? T('schl_stopp') : ''));
    k.title = an ? T('schl_es_wird_aufgenommen') + (pause ? ' ' + T('schl_pause') : '') + T('schl_klick_beendet')
                 : T('schl_sprachaufnahme_starten');
    k.setAttribute('aria-pressed', an ? 'true' : 'false');
    if(x.quelle) x.quelle.disabled = an;                      // während der Aufnahme bleibt die Quelle, wie sie ist
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
        S.hinweis(T('schl_aufnahme_gesichert') + ': „' + (a.titel || T('schl_aufnehmen')) + '“ · ' + zeit(a.dauer) + ' – ' + T('schl_in_app_rekorder') + '.');
      }else{
        await S.api('/api/sprache/kern/start', {method: 'POST', body: Object.assign({titel: '', sprache: 'de'}, x.quelle && x.quelle.value !== 'beides' ? {quelle: x.quelle.value} : {})});
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
    const q = d().el('select', 'hs-rec-quelle'); q.setAttribute('aria-label', 'Quelle der Aufnahme');    q.title = T('schl_quelle_standard');
    QUELLEN_KEYS.forEach(([v, k])=>{ const o = d().el('option', null, T(k)); o.value = v; q.append(o); });
    q.value = gemerkt();
    q.onchange = ()=>merken(q.value);
    st(S).quelle = q;
    const gruppe = d().el('div', 'hs-rec-gruppe'); gruppe.append(k, q);
    anzeigen(S);
    lesen(S);
    return gruppe;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.schnell = {QUELLEN_KEYS, knopf, anzeigen, lesen, laeuft, takt, zeit};
})();
