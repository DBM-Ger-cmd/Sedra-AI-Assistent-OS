// Harness-Shell – der Drache lebt (Captain 16.11.2026): ein kleiner Drache in der Taskleiste zeigt den echten Zustand der Arbeit.
// Die Bewegung ist an Tatsachen gebunden, nichts wird vorgespielt: „denken“ nur, wenn das Modell nachdenkt (Phase „denkt“ aus verlauf.js),
// „schreiben“ nur bei Antwort oder Werkzeug, „warten“ bei laufender Anfrage ohne erste Regung oder bei offener Freigabe, „fertig“ und „fehler“
// als kurzer Anstoß, sobald der Server eine Antwort oder einen Lauf meldet. Ruhe ist die einzige Bewegung ohne Anlass (langsames Atmen).
// Die Taskleiste bleibt flüssig: nur CSS-Bewegung auf Transform und Opacity, kein Zeitgeber, der dauernd läuft; die Zustandsprüfung
// hängt an den vorhandenen Aufrufen der Taskleiste. Keine Bewegung bei „reduzierter Bewegung“ des Systems; abschalten ganz über
// localStorage `sedra.harness.lebendig` = `aus` (dann verschwindet der Drache aus der Taskleiste). Nur lesen, nichts entscheiden.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  root.sedraHarness = root.sedraHarness || {};
  const KEY = 'sedra.harness.lebendig';
  const BLITZ_MS = 1800;                                  // wie lange „fertig“ oder „fehler“ nachklingt
  const STIMMUNGEN = ['ruhe', 'warten', 'denken', 'schreiben', 'fertig', 'fehler'];
  const T = k=>(root.t ? root.t(k) : k);
  const aus = ()=>{ try{ return localStorage.getItem(KEY) === 'aus'; }catch(_e){ return false; } };

  // Der Zustand aus Tatsachen. Rein: läuft auch unter node (test_uix_leben).
  // z: {laeuft, phase (Text der Zeitlinie oder null), wartet (offene Freigabe), flash: {art, bis}|null, jetzt}
  function stimmung(z){
    if(z.flash && z.flash.bis > z.jetzt) return z.flash.art;          // ein gerade beendeter Lauf klingt kurz nach
    if(z.wartet) return 'warten';                                    // eine Freigabe wartet auf den Captain
    if(z.laeuft){
      const p = String(z.phase || '');
      if(p === 'denkt' || p.startsWith('fasst')) return 'denken';
      if(p === 'schreibt' || p.startsWith('Werkzeug')) return 'schreiben';
      return 'warten';                                               // Anfrage gesendet, das Modell hat noch nichts gemeldet
    }
    return 'ruhe';
  }

  // Die Lage der Shell: läuft irgendeine Antwort (die erste mit Phase gewinnt), wartet eine Freigabe, gibt es einen Blitz?
  function lage(S){
    let laeuft = false, phase = null;
    if(S.ansichten && S.ansichten.values){
      for(const a of S.ansichten.values()){
        if(!a || !a.laeuft || !a.laeuft()) continue;
        if(!laeuft || (!phase && a._phase)){ laeuft = true; phase = a._phase ? a._phase.text : null; }
      }
    }
    return {laeuft, phase, wartet: (S.entscheidungen || []).length > 0, flash: S._leben ? S._leben.flash : null, jetzt: Date.now()};
  }

  // Der Drache für die Taskleiste: ein SVG aus denselben Teilen wie der Startbild-Drache (verlauf.js), eigene Klasse ohne dessen Einblendung.
  // Der Begleiter am Rand zeigt das echte 3D-Modell (buehne3d.js standbild); die Taskleiste bleibt bei der kleinen Zeichnung.
  const WINKEL = {ruhe: -0.3, warten: -0.1, denken: -0.6, schreiben: 0.0, fertig: -0.3, fehler: -0.5};
  const svgDrache = ()=>{
    const z = root.sedraHarness.verlauf && root.sedraHarness.verlauf.drache ? root.sedraHarness.verlauf.drache() : null;
    if(z){ z.setAttribute('class', 'hs-leben-drache'); z.setAttribute('aria-hidden', 'true'); }
    return z;
  };
  function knopf(S, rand){
    const el = document.createElement('span'); el.className = 'hs-leben' + (rand ? ' hs-randdrache' : ''); el.setAttribute('role', 'img'); el.dataset.stimmung = 'ruhe';
    const B3 = root.sedraHarness.buehne3d;
    if(rand && B3 && B3.standbild){
      const c = document.createElement('canvas'); c.className = 'hs-leben-drache hs-leben-3d'; c.setAttribute('aria-hidden', 'true'); el.append(c);
    } else { const z = svgDrache(); if(z) el.append(z); }
    el.append(document.createElement('span')); el.lastChild.className = 'hs-leben-wort';      // das kurze Wort neben dem Drachen (nur bei Tätigkeit)
    el.hidden = aus();
    return el;
  }

  // Das 3D-Standbild neu zeichnen – nur bei einer Zustandsänderung. Gibt es kein WebGL2 oder kein Modell, steht die kleine Zeichnung dort.
  function bild3d(el, s){
    const c = el.querySelector('.hs-leben-3d'), B3 = root.sedraHarness.buehne3d;
    if(!c || !B3 || !B3.standbild) return;
    B3.standbild(c, WINKEL[s] || 0).then(ok=>{
      if(ok) return;
      const z = svgDrache(); if(z && c.isConnected) c.replaceWith(z);
    });
  }

  // Den Drachen auf den jetzigen Zustand stellen. Ändert nur das Attribut, wenn es sich ändert.
  function zeichnen(S){
    const teile = [S._leiste && S._leiste.drache, S._leben && S._leben.rand].filter(Boolean);
    if(!teile.length) return;
    const s = stimmung(lage(S)), text = T('lb_' + s), kurz = s === 'ruhe' ? '' : T('lw_' + s);
    teile.forEach(el=>{
      el.hidden = aus();
      if(el.hidden) return;
      if(el.dataset.stimmung !== s){ el.dataset.stimmung = s; if(el.classList.contains('hs-randdrache')) bild3d(el, s); }
      if(el.getAttribute('aria-label') !== text){ el.setAttribute('aria-label', text); el.title = text; }
      const wort = el.querySelector('.hs-leben-wort');
      if(wort && wort.textContent !== kurz) wort.textContent = kurz;
    });
  }

  function blitz(S, art){
    if(!S._leben) S._leben = {flash: null, uhr: 0};
    S._leben.flash = {art, bis: Date.now() + BLITZ_MS};
    clearTimeout(S._leben.uhr); S._leben.uhr = setTimeout(()=>zeichnen(S), BLITZ_MS + 50);     // danach zurück in den Ruhezustand, auch ohne neues Ereignis
    zeichnen(S);
  }

  // Die Ereignisse, die den Zustand ändern: Antwort fertig oder abgebrochen, Lauf beendet, Freigabe da oder beantwortet.
  function mount(S){
    S._leben = {flash: null, uhr: 0, rand: null};
    const shell = document.querySelector('.hs');
    if(shell){                                                         // der kleine Begleiter am rechten Rand: sitzt über der Arbeit, nimmt keine Klicks
      const rand = knopf(S, true); shell.append(rand); S._leben.rand = rand; bild3d(rand, 'ruhe');
    }
    const bus = S.ctx && S.ctx.bus; if(!bus){ zeichnen(S); return; }
    const nach = ()=>setTimeout(()=>zeichnen(S), 30);
    bus.on('harness.antwort', e=>{ if(e && e.zustand === 'fertig') blitz(S, e.ende === 'fehler' ? 'fehler' : 'fertig'); else nach(); });
    bus.on('harness.lauf', e=>{ if(e && e.zustand === 'ende') blitz(S, e.status === 'ok' ? 'fertig' : 'fehler'); else nach(); });
    ['decision.pending', 'decision.answered'].forEach(n=>bus.on(n, nach));
  }

  root.sedraHarness.leben = {mount, knopf, zeichnen, stimmung, STIMMUNGEN, KEY, BLITZ_MS};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.leben;
})();
