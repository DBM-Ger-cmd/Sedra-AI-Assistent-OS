// verlaufmixin.js – Mixin für verlauf.js (Seedrache, Lob, Startbild, Helper)
// Ausgelagert aus verlauf.js um Zeilenlimit (400) einzuhalten
// Einbindung: VOR verlauf.js in desk.html

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // ---- der Seedrache (HS-04): eine kleine Zeichnung aus Tokens, kein Bild, nichts aus dem Netz
  function drache(){
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 120 120');
    svg.setAttribute('class', 'hs-drache');
    svg.setAttribute('aria-hidden', 'true');
    const teil = (tag, attrs)=>{ const n = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k, v])=>n.setAttribute(k, v)); svg.append(n); return n; };
    teil('path', {d: 'M62 18c-14 0-24 10-24 22 0 9 6 14 6 22 0 9-10 13-10 24 0 13 12 20 24 20 10 0 17-5 20-11-6 3-14 3-19-2-6-6-3-14 3-19 8-6 14-12 14-24 0-8-4-13-4-18 6 0 12-4 14-10-6 2-12 0-15-4-2-1-6 0-9 0z', class: 'hs-drache-koerper'});
    teil('path', {d: 'M38 40c-8-4-16-2-20 4 7-1 13 1 16 6M44 62c-9 0-15 5-16 12 6-4 12-5 17-3M76 30c6-8 14-10 21-8-5 3-9 8-10 14', class: 'hs-drache-flosse'});
    teil('circle', {cx: '66', cy: '30', r: '3.2', class: 'hs-drache-auge'});
    [[52, 50], [49, 66], [54, 82], [64, 92]].forEach(([x, y])=>teil('circle', {cx: String(x), cy: String(y), r: '2', class: 'hs-drache-punkt'}));
    return svg;
  }

  // ★ an einer gelobten Antwort, ⚑ an einer korrigierten (Belohnungs- und Lernsystem, harness/belohnung.py): ★★ bei „besonders gut“
  function lobZeichen(b){
    const korr = b.urteil === 'korrektur';
    const z = d().el('div', 'hs-lob' + (korr ? ' hs-korrigiert' : ''), (korr ? '⚑ korrigiert' : (b.stufe === 2 ? '★★ besonders gute Antwort' : '★ gute Antwort')) + (b.ausloeser ? ' · „' + b.ausloeser + '“' : ''));
    z.title = korr ? 'Der Captain hat diese Antwort korrigiert; seine Worte sind die Lehre für den Rückblick (Vorlage Rückblick).' : 'Der Captain hat diese Antwort gelobt; sie steht in den guten Antworten (Einstellungen → System → Info) und kann in die Wissensdatenbank.';
    return z;
  }

  // V2/A22 (1.11.): drei Schritte mit Zustand statt eines Satzes – Modell, Projekt, erste Nachricht; dazu die drei Zeichen des Eingabefelds
  function startbild(S){
    const box = d().el('div', 'hs-start');
    const D = root.sedraHarness.desktop, gruss = D ? D.begruessung(S) : {logo: '', titel: 'SEDRA', text: '', marke: ''};
    const grussEl = d().el('div', 'hs-start-block');                                          // Baustein „gruss“ (bausteine.js): Logo, Titel, Text
    if(gruss.logo){ const bild = d().el('img', 'hs-start-logo'); bild.src = gruss.logo; bild.alt = gruss.marke || 'Logo'; grussEl.append(bild); }       // Logo des Profils statt des Drachen (nur eine Daten-Adresse, vom Server geprüft)
    else grussEl.append(drache());
    grussEl.append(d().el('h1', 'hs-start-titel', gruss.titel));
    if(gruss.text) grussEl.append(d().el('p', 'hs-start-gruss', gruss.text));
    const schritte = d().el('ol', 'hs-start-schritte');
    const e = S._eingabe || {};
    const modell = !!S.modell, projekt = !!(e.projekt && e.projekt.value), vorlage = e.vorlage && e.vorlage.value;
    const modellName = S.modell && (S.modell.name || S.modell);
    const schritt = (ok, text, tun)=>{
      const li = d().el('li', 'hs-start-schritt' + (ok ? ' ok' : ''));
      li.append(d().el('span', 'hs-start-haken', ok ? '✓' : '○'), d().el('span', null, text));
      if(!ok && tun){ const k = d().el('button', 'hs-knopf hs-klein', tun[0]); k.type = 'button'; k.onclick = tun[1]; li.append(k); }
      return li;
    };
    schritte.append(schritt(modell, modell ? 'Modell geladen: ' + modellName : 'Ein Modell laden', ['Modell wählen', ()=>root.sedraHarness.eingabe.modellMenue(S, true)]),
                    schritt(projekt, 'Projekt: ' + ((S.projekte || []).find(p=>p.id === (e.projekt || {}).value) || {}).name + (vorlage ? ' · Vorlage ' + vorlage : ''), null),
                    schritt(false, 'Die erste Nachricht schreiben – unten im Feld', ['Ins Feld', ()=>root.sedraHarness.eingabe.fokus(S)]));
    const hilfeEl = d().el('p', 'hs-start-text', 'Im Feld: „+“ hängt eine Datei an, „@“ nennt eine Datei, „/“ gibt Befehle. Die Antwort streamt; jeder Werkzeugaufruf steht sichtbar im Verlauf, und was ändert, fragt vorher.');
    const B = root.sedraHarness.bausteine;                                                      // Baukasten: Wahl des Profils auf dem Raster, sonst untereinander wie bisher
    if(B) B.startAnwenden(S, box, {gruss: grussEl, schritte, hilfe: hilfeEl}); else box.append(grussEl, schritte, hilfeEl);
    return box;
  }

  function kurz(args){
    if(args === undefined || args === null) return '';
    const t = JSON.stringify(args);
    return t === '{}' ? '' : (t.length > 120 ? t.slice(0, 119) + '…' : t);
  }

  // Seedrache Animationen
  function dracheIdleStart(dracheEl) {
    if (dracheEl) {
      setTimeout(() => dracheEl.classList.add('idle'), 800);
      return dracheEl;
    }
    return null;
  }

  function dracheExitAnimation(dracheEl) {
    if (dracheEl) {
      dracheEl.classList.add('exiting');
      setTimeout(() => { dracheEl.remove(); }, 500);
      return null;
    }
    return null;
  }

  // Export
  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.verlaufMixin = {
    drache,
    lobZeichen,
    startbild,
    kurz,
    dracheIdleStart,
    dracheExitAnimation
  };
})();