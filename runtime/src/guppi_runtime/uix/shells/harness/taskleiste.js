// Harness-Shell – die Taskleiste (HS-30 bis HS-33): links „Start“ (öffnet das Start-Menü, Stufe 4), in der Mitte die Läufe (die offenen Sitzungen und Apps stehen in der Reiterleiste, ihr Zustand im Reiter)
// der Harness – laufende mit Fortschritt oder Zeit –, rechts der Statusbereich aus /api/strip (HS-32: Freigaben „n · beim Vorarbeiter m“, Modell, GPU mit
// Temperatur, RAM, Modellserver, Scheduler, Zustand) und die Uhr. Zellen ohne Wert werden ausgeblendet, nicht leer gezeigt; ein Klick öffnet die App dazu (G2 §5).
// Benachrichtigung (HS-33): Endet ein Lauf oder wartet eine Freigabe, blinkt der Knopf einmal und bleibt markiert, bis er angeklickt wird.
// Gemerkt wird nur, was schon gesehen wurde (IDs in localStorage `sedra.harness.gesehen`), nie Inhalt. Kein Dauer-Abruf im Hintergrund: der Status frischt bei Ereignissen auf,
// höchstens alle 2 s (HS-52); die Uhr tickt, alle 15 s bei sichtbarem Tab auch der Status (A7, HS-52a).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const ABSTAND_MS = 2000;
  const GESEHEN_KEY = 'sedra.harness.gesehen';
  const GESEHEN_MAX = 300;
  // Zelle → Beschriftung und die App, die ein Klick öffnet (Ort-ID aus ui/places.js)
  const ZELLEN = [['decisions', 'Freigaben', null], ['model', 'Modell', 'models'], ['gpu', 'GPU · RAM', 'hardware'],
                  ['server', 'Modellserver', 'models'], ['scheduler', 'Scheduler', 'slots'], ['state', 'Zustand', 'machine']];
  // GPU und RAM sind eine Zelle (beide öffneten dieselbe App; Captain 03.11.2026): „40 °C · 1.5/12 GB · RAM 15.4/31 GB“, der strengere Ton, beide Hinweise
  const TON_RANG = {off: 0, ok: 1, warn: 2, bad: 3};
  function zusammen(v){
    const g = v.gpu, r = v.ram;
    if(!g && !r) return v;
    const wert = x=>x && x.value !== undefined && x.value !== null ? String(x.value) : null;
    const teile = [wert(g), wert(r) ? 'RAM ' + wert(r) : null].filter(Boolean);
    const ton = [g, r].filter(Boolean).map(x=>x.tone || 'off').reduce((a, b)=>(TON_RANG[b] || 0) > (TON_RANG[a] || 0) ? b : a, 'off');
    const hint = [g && g.hint, r && r.hint ? 'RAM: ' + r.hint : null].filter(Boolean).join(' · ');
    return Object.assign({}, v, {gpu: {value: teile.join(' · ') || '–', tone: ton, hint}});
  }
  const ENDE_ICON = {ok: '✓', fehler: '✗', gestoppt: '■', abgebrochen: '■', verloren: '?', zeitlimit: '⏱'};

  function mount(S){
    const bar = S.el.taskleiste;
    const start = d().el('button', 'hs-start-knopf', 'Start'); start.type = 'button';
    start.title = 'Start-Menü: Apps, Oberflächen, Darstellung und Schrift (Alt+S)';
    start.setAttribute('aria-haspopup', 'dialog'); start.setAttribute('aria-expanded', 'false');
    start.onclick = e=>{ e.stopPropagation(); root.sedraHarness.startmenue.umschalten(S); };
    const mitte = d().el('div', 'hs-apps');
    const status = d().el('div', 'hs-status');
    const uhr = d().el('span', 'hs-uhr');
    bar.append(start, mitte, status, uhr);
    S._leiste = {mitte, status, uhr, zuletzt: 0, wartet: null};
    const ticken = ()=>{ uhr.textContent = new Date().toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'}); };
    ticken();
    setInterval(()=>{ ticken(); zeichnen(S); if(!document.hidden) root.sedraHarness.taskleiste.status(S); }, 15000);      // A7 (1.11.): Statuszellen frischen auch während langer Antworten auf (HS-52: höchstens alle 2 s bleibt)
  }

  function dauer(ms){
    const s = Math.max(0, Math.round(ms / 1000));
    return s < 60 ? s + ' s' : Math.floor(s / 60) + ' min';
  }

  // ---- gesehen: was der Captain schon angeklickt hat (nur IDs)
  function gesehenMenge(S){
    if(S._gesehen) return S._gesehen;
    let roh = null, liste = [];
    try{ roh = localStorage.getItem(GESEHEN_KEY); liste = roh ? (JSON.parse(roh) || []) : []; }catch(_e){ liste = []; }     // Härtung 30.10. (HU-S9): ein kaputter Eintrag bricht die Leiste nicht
    S._gesehen = new Set(Array.isArray(liste) ? liste.filter(x=>typeof x === 'string') : []);
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
    const E = root.sedraHarness.einstellungen;
    if(E && E.meldung().blinken === false) return;                       // Stufe 5 (K9): in den Einstellungen abschaltbar
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

  // die Mitte: die Läufe; der Zustand der Reiter (Antwort läuft mit Zeit HS-31, Freigabe wartet) wird in die Reiterleiste geschrieben
  // Zustand eines Reiters für die Reiterleiste: läuft (mit Phase und Zeit), wartet auf Freigabe, blinkt bei Benachrichtigung
  function zustand(S, id){
    const a = S.ansichten.get(id), s = S.sitzung(id);
    const wartet = (S.entscheidungen || []).some(x=>!gesehenMenge(S).has('frg:' + x.id) && (x.sitzung_id === id || (String(x.note || '').match(/Sitzung (S-[0-9A-F]{8})/) || [])[1] === id));     // A18
    const laeuft = !!((a && a.laeuft()) || (s && s.laeuft));
    let text = '';
    if(laeuft && a && a.block){                                       // V3 (1.11.): Zeitlinie – was die Antwort gerade tut und seit wann
      const ph = a._phase;
      text = (ph ? ph.text + ' · ' + dauer(performance.now() - ph.seit) + ' · ' : '') + dauer(performance.now() - (a._seit || (a._seit = performance.now())));
    }
    else if(a) a._seit = null;
    if(wartet) text = 'wartet auf Freigabe';
    return {laeuft, neu: wartet, blinkt: !!pruefe(S, 'sitzung:' + id), text};
  }
  function sitzungGesehen(S, id){
    (S.entscheidungen || []).filter(x=>x.sitzung_id === id || String(x.note || '').includes(id)).forEach(x=>gesehenMenge(S).add('frg:' + x.id));
    gesehenSpeichern(S);
  }

  function zeichnen(S){
    const l = S._leiste; if(!l) return;
    const reiter = root.sedraHarness.reiter;
    const aktiv = reiter.aktiv(S);
    const offeneLaeufe = new Set(reiter.liste(S).filter(id=>String(id).startsWith('lauf:')));
    reiter.zustandAuffrischen(S);                                   // A1 (Captain 03.11.2026): die offenen Sitzungen und Apps stehen nur noch in der Reiterleiste; ihr Zustand sitzt im Reiter
    const laeufe = (S.laeufe || []).filter(x=>x.status === 'laeuft' || offeneLaeufe.has('lauf:' + x.id) || !gesehenMenge(S).has('lauf:' + x.id))
                                   .map(x=>laufKnopf(S, x, aktiv));
    l.mitte.replaceChildren(...laeufe);
    if(l.uhrSchnell) return;
    if(reiter.liste(S).some(id=>{ const a = S.ansichten.get(id); return a && a.laeuft(); })){
      l.uhrSchnell = setTimeout(()=>{ l.uhrSchnell = null; zeichnen(S); }, 1000);
    }
  }

  // Token: eingehend (was an das Modell ging – jeder Zug zählt den ganzen Verlauf neu) und erzeugt (was es geschrieben hat, Denken eingeschlossen) der aktiven Sitzung;
  // der Ton folgt dem Füllstand des Kontextfensters. Ein Klick öffnet die App „Sedra Token“.
  function zahl(n){ n = Number(n) || 0; return n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1).replace('.', ',') + 'k' : String(n); }
  function tokenZelle(S){
    const t = S.tokenStand, s = t && t.sitzung, h = t && t.heute;
    const k = s && s.kontext, pro = k && k.fenster ? Math.round(100 * k.belegt / k.fenster) : null;
    const ton = pro === null ? 'off' : pro >= 90 ? 'bad' : pro >= 80 ? 'warn' : 'ok';
    const zelle = d().el('span', 'hs-zelle ' + ton);
    zelle.dataset.zelle = 'token';
    const wert = s ? zahl(s.ein) + ' ↑ ' + zahl(s.aus) + ' ↓' : (h && h.antworten ? 'heute ' + zahl(h.ein) + ' ↑ ' + zahl(h.aus) + ' ↓' : '–');
    zelle.title = 'Token' + (s ? ' dieser Sitzung' : ' heute') + ': ↑ eingehend ' + (s ? s.ein : h ? h.ein : 0).toLocaleString('de-DE') + ' (jeder Zug zählt den Verlauf neu), ↓ erzeugt ' + (s ? s.aus : h ? h.aus : 0).toLocaleString('de-DE')
      + (s && s.tok_s ? ' · Ø ' + String(s.tok_s).replace('.', ',') + ' Token/s' : '') + (pro !== null ? ' · Kontext ' + pro + ' %' : '') + ' – Klick: App Sedra Token (Verbrauch, Kosten, Gespräch)';
    zelle.tabIndex = 0; zelle.setAttribute('role', 'button');
    const oeffnen = ()=>root.sedraHarness.tokenseite.oeffnen(S);
    zelle.onclick = oeffnen;
    zelle.onkeydown = e=>{ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); oeffnen(); } };
    zelle.append(d().el('small', null, 'Token'), d().el('b', null, wert));
    return zelle;
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
    S.api('/api/strip').then(roh=>{
      S.strip = roh;                                                                             // die Kacheln des Start-Menüs nehmen dasselbe Ergebnis (HS-52a): eine Abfrage für beide
      const sm = root.sedraHarness.startmenue; if(sm && sm.stripNeu) sm.stripNeu(S, roh);
      const v = zusammen(roh);
      // HS-32: eine Zelle ohne Wert (– und Ton off) wird ausgeblendet – kleine Bildschirme, Stick an fremdem PC
      const da = ZELLEN.filter(([k])=>v[k] && !(String(v[k].value ?? '–') === '–' && (v[k].tone || 'off') === 'off'));
      const zellen = da.map(([k, label, ort])=>{
        const g = v[k];
        const zelle = d().el('span', 'hs-zelle ' + (g.tone || 'off'));
        zelle.dataset.zelle = k;
        zelle.title = label + ': ' + (g.hint || '');
        let wert = String(g.value === undefined || g.value === null ? '–' : g.value);
        if(k === 'decisions') wert = freigabenZelle(S, zelle, g, wert);
        else if(ort){
          const modellzelle = k === 'model' || k === 'server';
          zelle.tabIndex = 0; zelle.setAttribute('role', 'button'); zelle.title += modellzelle ? (k === 'server' ? ' – Klick: Modell-Menü, unten der Modellserver (Sedra-Modell-Router) starten, beenden, Optionen' : ' – Klick: Modell laden, wechseln oder entladen; unten der Modellserver') : ' – Klick öffnet die App';
          const oeffnen = ()=>{
            if(k === 'state'){ root.sedraHarness.einstellungen.oeffnen(S, 'system'); return; }          // Stufe 5 (D-U6): Zustand → Einstellungen (System)
            if(modellzelle){ root.sedraHarness.modell.menue(S); return; }                                // 1.11. (Captain): die Modellsteuerung hängt an der Statusleiste, nicht an der Werkstatt
            const o = root.sedraPlaces.PLACES.find(p=>p.id === ort); if(o) root.sedraHarness.app.oeffnen(S, o);
          };
          zelle.onclick = oeffnen;
          zelle.onkeydown = e=>{ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); oeffnen(); } };
        }
        zelle.append(d().el('small', null, label), d().el('b', null, wert));
        return zelle;
      });
      zellen.splice(Math.min(1, zellen.length), 0, tokenZelle(S));            // 02.11.2026: Token gleich hinter den Freigaben, vor Modell und GPU
      l.status.replaceChildren(...zellen);
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
    zelle.title = 'Freigaben: ' + (g.hint || '') + (beim ? ' – ' + beim + ' beim Vorarbeiter' : '') + ' – Klick öffnet den Posteingang bzw. die Stelle, an der es wartet';
    const oeffnen = ()=>{
      alle.forEach(x=>gesehenMenge(S).add('frg:' + x.id)); gesehenSpeichern(S);
      const aufgabe = alle.find(x=>x.kind === 'harness_aufgabe');
      const sitzung = alle.map(x=>x.sitzung_id || (String(x.note || '').match(/Sitzung (S-[0-9A-F]{8})/) || [])[1]).find(Boolean);     // A18
      if(aufgabe) root.sedraHarness.reiter.oeffnen(S, 'aufgaben:');
      else if(sitzung) root.sedraHarness.reiter.oeffnen(S, sitzung);
      else if(alle.length) root.sedraHarness.app.oeffnen(S, {object: {type: 'decision', id: 'alle', title: 'Posteingang', collection: true}, label: 'Posteingang'});   // Stufe 4: der Posteingang als App
      else S.hinweis('Nichts wartet.');
      zeichnen(S); status(S);
    };
    zelle.onclick = oeffnen;
    zelle.onkeydown = e=>{ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); oeffnen(); } };
    return wert;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.taskleiste = {mount, zeichnen, zustand, sitzungGesehen, status, gesehen, blinken, alsGesehenStarten, laufName, KEY: GESEHEN_KEY};
})();
