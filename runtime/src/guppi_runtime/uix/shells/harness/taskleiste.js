// Harness-Shell – die Taskleiste (HS-30 bis HS-33): links „Start“, in der Mitte die offenen Sitzungen und die Läufe der Harness – laufende mit Fortschritt
// oder Zeit –, rechts der Status aus /api/strip (Freigaben „n · beim Vorarbeiter m“, Modell, GPU, Zustand) und die Uhr.
// Benachrichtigung (HS-33): Endet ein Lauf oder wartet eine Freigabe, blinkt der Knopf einmal und bleibt markiert, bis er angeklickt wird.
// Gemerkt wird nur, was schon gesehen wurde (IDs in localStorage `sedra.harness.gesehen`), nie Inhalt. Kein Polling: der Status frischt bei Ereignissen auf,
// höchstens alle 2 s (HS-52); nur die Uhr tickt.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const ABSTAND_MS = 2000;
  const GESEHEN_KEY = 'sedra.harness.gesehen';
  const GESEHEN_MAX = 300;
  const ZELLEN = [['decisions', 'Freigaben'], ['model', 'Modell'], ['gpu', 'GPU'], ['state', 'Zustand']];
  const ENDE_ICON = {ok: '✓', fehler: '✗', gestoppt: '■', abgebrochen: '■', verloren: '?', zeitlimit: '⏱'};

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

  // ---- gesehen: was der Captain schon angeklickt hat (nur IDs)
  function gesehenMenge(S){
    if(S._gesehen) return S._gesehen;
    let roh = null;
    try{ roh = localStorage.getItem(GESEHEN_KEY); }catch(_e){}
    S._gesehen = new Set(roh ? (JSON.parse(roh) || []) : []);
    S._gesehenNeu = roh === null;               // erster Start: was schon da ist, gilt als gesehen
    return S._gesehen;
  }

  function gesehenSpeichern(S){
    try{ localStorage.setItem(GESEHEN_KEY, JSON.stringify([...gesehenMenge(S)].slice(-GESEHEN_MAX))); }catch(_e){}
  }

  function gesehen(S, key){
    const g = gesehenMenge(S);
    if(g.has(key)) return;
    g.add(key); gesehenSpeichern(S);
    zeichnen(S);
  }

  function alsGesehenStarten(S){
    gesehenMenge(S);
    if(!S._gesehenNeu) return;
    S._gesehenNeu = false;
    (S.laeufe || []).filter(l=>l.status !== 'laeuft').forEach(l=>S._gesehen.add('lauf:' + l.id));
    (S.entscheidungen || []).forEach(x=>S._gesehen.add('frg:' + x.id));
    gesehenSpeichern(S);
  }

  // ---- blinken: einmal, danach nur noch die Markierung
  function blinken(S, key){
    (S._blinken || (S._blinken = new Set())).add(key);
    zeichnen(S);
    setTimeout(()=>{ S._blinken.delete(key); zeichnen(S); }, 1600);
  }

  function pruefe(S, key){ return S._blinken && S._blinken.has(key); }

  // ---- Läufe
  function laufName(l){
    const p = l.fortschritt && l.fortschritt.prozent;
    if(l.status === 'laeuft'){
      return l.name + ' ' + (p !== null && p !== undefined ? p + ' %' : dauer(Date.now() - Date.parse(l.gestartet || new Date().toISOString())));
    }
    return l.name + ' ' + (ENDE_ICON[l.status] || l.status);
  }

  function laufKnopf(S, l, aktiv){
    const key = 'lauf:' + l.id;
    const neu = l.status !== 'laeuft' && !gesehenMenge(S).has(key);
    const k = d().el('button', 'hs-app lauf' + (key === aktiv ? ' on' : '') + (l.status === 'laeuft' ? ' laeuft' : '') + (neu ? ' neu' : '') + (pruefe(S, key) ? ' blinkt' : ''));
    k.type = 'button'; k.dataset.lauf = l.id;
    k.append(d().el('span', 'hs-app-icon', l.status === 'laeuft' ? '●' : (ENDE_ICON[l.status] || '■')), d().el('span', 'hs-app-name', laufName(l)));
    if(l.status === 'laeuft' && l.modell_weg) k.append(d().el('small', 'hs-leise', 'Modell belegt'));
    k.title = l.name + ' (' + l.id + ') – ' + l.status + ((l.fortschritt && l.fortschritt.text) ? ' · ' + l.fortschritt.text : '') + (neu ? ' · beendet, noch nicht angesehen' : '');
    k.onclick = ()=>{ gesehen(S, key); root.sedraHarness.reiter.oeffnen(S, key); };
    return k;
  }

  // die Mitte: jeder offene Reiter ein Knopf; laufende Antworten zeigen ihre Zeit (HS-31); dazu die Läufe
  function zeichnen(S){
    const l = S._leiste; if(!l) return;
    const reiter = root.sedraHarness.reiter;
    const aktiv = reiter.aktiv(S);
    const wartet = new Set((S.entscheidungen || []).filter(x=>!gesehenMenge(S).has('frg:' + x.id)).map(x=>(String(x.note || '').match(/Sitzung (S-[0-9A-F]{8})/) || [])[1]).filter(Boolean));
    const offeneLaeufe = new Set(reiter.liste(S).filter(id=>String(id).startsWith('lauf:')));
    const knoepfe = reiter.liste(S).filter(id=>!String(id).startsWith('lauf:')).map(id=>{
      const a = S.ansichten.get(id);
      const s = S.sitzung(id);
      const laeuft = (a && a.laeuft()) || (s && s.laeuft);
      const neu = wartet.has(id);
      const knopf = d().el('button', 'hs-app' + (id === aktiv ? ' on' : '') + (laeuft ? ' laeuft' : '') + (neu ? ' neu' : '') + (pruefe(S, 'sitzung:' + id) ? ' blinkt' : ''));
      knopf.type = 'button';
      knopf.dataset.reiter = id;
      const name = String(id).startsWith('diff:') ? 'Diff ' + id.slice(5) : (String(id).startsWith('aufgaben:') ? 'Aufgaben' : ((s && s.titel) || (/^S-/.test(id) ? 'Ohne Titel' : 'Neue Sitzung')));
      const vorarbeiter = S.vorarbeiter && Object.values(S.vorarbeiter).some(v=>v.sitzung_id === id);
      knopf.append(d().el('span', 'hs-app-icon', laeuft ? '●' : (String(id).startsWith('aufgaben:') ? '⛨' : (vorarbeiter ? '⚑' : '💬'))), d().el('span', 'hs-app-name', name));
      if(laeuft && a && a.block) knopf.append(d().el('small', 'hs-leise', dauer(performance.now() - (a._seit || (a._seit = performance.now())))));
      else if(a) a._seit = null;
      if(neu) knopf.append(d().el('small', 'hs-leise', 'wartet auf Freigabe'));
      knopf.title = name + (laeuft ? ' – Antwort läuft' : '') + (neu ? ' – eine Freigabe wartet' : '');
      knopf.onclick = ()=>{
        (S.entscheidungen || []).filter(x=>String(x.note || '').includes(id)).forEach(x=>gesehenMenge(S).add('frg:' + x.id));
        gesehenSpeichern(S);
        reiter.aktivieren(S, id);
      };
      return knopf;
    });
    const laeufe = (S.laeufe || []).filter(x=>x.status === 'laeuft' || offeneLaeufe.has('lauf:' + x.id) || !gesehenMenge(S).has('lauf:' + x.id))
                                   .map(x=>laufKnopf(S, x, aktiv));
    l.mitte.replaceChildren(...knoepfe, ...laeufe);
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
        let wert = String(g.value === undefined || g.value === null ? '–' : g.value);
        if(k === 'decisions') wert = freigabenZelle(S, zelle, g, wert);
        zelle.append(d().el('small', null, label), d().el('b', null, wert));
        return zelle;
      }));
    }).catch(err=>{
      l.status.replaceChildren(d().el('span', 'hs-zelle warn', 'Status nicht lesbar'));
      l.status.title = err.message;
    });
  }

  // HS-32/HS-33: „Freigaben n · beim Vorarbeiter m“; neue, noch nicht angesehene Freigaben markieren die Zelle, ein Klick öffnet, was wartet
  function freigabenZelle(S, zelle, g, wert){
    const alle = S.entscheidungen || [];
    const beim = alle.filter(x=>String(x.note || '').includes('beim Vorarbeiter')).length;
    const neu = alle.filter(x=>!gesehenMenge(S).has('frg:' + x.id));
    if(beim) wert = String(Math.max(0, Number(g.value || 0) - beim)) + ' · beim Vorarbeiter ' + beim;
    if(neu.length) zelle.classList.add('neu');
    if(pruefe(S, 'freigaben')) zelle.classList.add('blinkt');
    zelle.tabIndex = 0; zelle.setAttribute('role', 'button');
    zelle.title = 'Freigaben: ' + (g.hint || '') + (beim ? ' – ' + beim + ' beim Vorarbeiter' : '') + ' – Klick öffnet, was wartet';
    const oeffnen = ()=>{
      alle.forEach(x=>gesehenMenge(S).add('frg:' + x.id)); gesehenSpeichern(S);
      const aufgabe = alle.find(x=>x.kind === 'harness_aufgabe');
      const sitzung = alle.map(x=>(String(x.note || '').match(/Sitzung (S-[0-9A-F]{8})/) || [])[1]).find(Boolean);
      if(aufgabe) root.sedraHarness.reiter.oeffnen(S, 'aufgaben:');
      else if(sitzung) root.sedraHarness.reiter.oeffnen(S, sitzung);
      else S.hinweis(alle.length ? 'Diese Freigaben stehen im Posteingang des Cockpits (Start unten links).' : 'Nichts wartet.');
      zeichnen(S); status(S);
    };
    zelle.onclick = oeffnen;
    zelle.onkeydown = e=>{ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); oeffnen(); } };
    return wert;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.taskleiste = {mount, zeichnen, status, gesehen, blinken, alsGesehenStarten, laufName, KEY: GESEHEN_KEY};
})();
