// Harness-Shell – die Taskleiste (HS-30, HS-31 Teil, HS-32 Teil): links „Start“ (in Stufe 1 nur die Liste der Oberflächen, über das
// Menü des Umschalters), in der Mitte die offenen Sitzungen – laufende mit Zeit –, rechts der Status aus /api/strip (Freigaben, Modell,
// GPU, Zustand) und die Uhr. Kein Polling: der Status frischt bei Ereignissen auf, höchstens alle 2 s (HS-52); nur die Uhr tickt.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const ABSTAND_MS = 2000;
  const ZELLEN = [['decisions', 'Freigaben'], ['model', 'Modell'], ['gpu', 'GPU'], ['state', 'Zustand']];

  function mount(S){
    const bar = S.el.taskleiste;
    const start = d().el('button', 'hs-start-knopf', 'Start'); start.type = 'button';
    start.title = 'Oberflächen, Darstellung und Schrift (Start-Menü mit Apps kommt in Stufe 4)';
    start.onclick = ()=>{
      const chip = document.querySelector('.sx-umschalter');
      if(chip) chip.click(); else S.hinweis('Die Liste der Oberflächen ist auf dieser Seite nicht da.', 'warn');
    };
    const mitte = d().el('div', 'hs-apps');
    const status = d().el('div', 'hs-status');
    const uhr = d().el('span', 'hs-uhr');
    bar.append(start, mitte, status, uhr);
    S._leiste = {mitte, status, uhr, zuletzt: 0, wartet: null};
    const ticken = ()=>{ uhr.textContent = new Date().toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'}); };
    ticken();
    setInterval(()=>{ ticken(); zeichnen(S); }, 15000);
  }

  function dauer(ms){
    const s = Math.max(0, Math.round(ms / 1000));
    return s < 60 ? s + ' s' : Math.floor(s / 60) + ' min';
  }

  // die Mitte: jeder offene Reiter ein Knopf; laufende Antworten zeigen ihre Zeit (HS-31, Teil Sitzungen)
  function zeichnen(S){
    const l = S._leiste; if(!l) return;
    const reiter = root.sedraHarness.reiter;
    const aktiv = reiter.aktiv(S);
    l.mitte.replaceChildren(...reiter.liste(S).map(id=>{
      const a = S.ansichten.get(id);
      const s = S.sitzung(id);
      const laeuft = (a && a.laeuft()) || (s && s.laeuft);
      const knopf = d().el('button', 'hs-app' + (id === aktiv ? ' on' : '') + (laeuft ? ' laeuft' : ''));
      knopf.type = 'button';
      knopf.dataset.reiter = id;
      const name = String(id).startsWith('diff:') ? 'Diff ' + id.slice(5) : (String(id).startsWith('aufgaben:') ? 'Aufgaben' : ((s && s.titel) || (/^S-/.test(id) ? 'Ohne Titel' : 'Neue Sitzung')));
      const vorarbeiter = S.vorarbeiter && Object.values(S.vorarbeiter).some(v=>v.sitzung_id === id);
      knopf.append(d().el('span', 'hs-app-icon', laeuft ? '●' : (String(id).startsWith('aufgaben:') ? '⛨' : (vorarbeiter ? '⚑' : '💬'))), d().el('span', 'hs-app-name', name));
      if(laeuft && a && a.block) knopf.append(d().el('small', 'hs-leise', dauer(performance.now() - (a._seit || (a._seit = performance.now())))));
      else if(a) a._seit = null;
      knopf.title = name + (laeuft ? ' – Antwort läuft' : '');
      knopf.onclick = ()=>reiter.aktivieren(S, id);
      return knopf;
    }));
    if(l.uhrSchnell) return;
    if(reiter.liste(S).some(id=>{ const a = S.ansichten.get(id); return a && a.laeuft(); })){
      l.uhrSchnell = setTimeout(()=>{ l.uhrSchnell = null; zeichnen(S); }, 1000);
    }
  }

  // rechts: der Status aus /api/strip, höchstens alle 2 s
  function status(S){
    const l = S._leiste; if(!l) return;
    const jetzt = Date.now();
    if(jetzt - l.zuletzt < ABSTAND_MS){
      if(!l.wartet) l.wartet = setTimeout(()=>{ l.wartet = null; status(S); }, ABSTAND_MS - (jetzt - l.zuletzt));
      return;
    }
    l.zuletzt = jetzt;
    S.api('/api/strip').then(v=>{
      l.status.replaceChildren(...ZELLEN.filter(([k])=>v[k]).map(([k, label])=>{
        const g = v[k];
        const zelle = d().el('span', 'hs-zelle ' + (g.tone || 'off'));
        zelle.dataset.zelle = k;
        zelle.title = label + ': ' + (g.hint || '');
        zelle.append(d().el('small', null, label), d().el('b', null, String(g.value === undefined || g.value === null ? '–' : g.value)));
        return zelle;
      }));
    }).catch(err=>{
      l.status.replaceChildren(d().el('span', 'hs-zelle warn', 'Status nicht lesbar'));
      l.status.title = err.message;
    });
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.taskleiste = {mount, zeichnen, status};
})();
