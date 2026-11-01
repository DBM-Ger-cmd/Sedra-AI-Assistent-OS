// Harness-Shell – Modell laden, wechseln und entladen direkt im Eingabebereich (Stufe 6, HS-80/HS-81): statt eines Verweises („Start → Modelle → Werkstatt“) steht dort, wo es fehlt,
// die Handlung selbst: Rezept wählen, „Laden“. Dieselben Wege wie die Werkstatt (GET /api/models, POST /api/model/load, POST /api/model/unload); Gates, Speicherprüfung und Fehlertexte
// kommen vom Server und werden unverändert angezeigt. Ein Ladevorgang kann Minuten dauern: der Knopf zeigt „lädt …“, nichts anderes wird blockiert.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const GRUND = {
    hardware_pressure: 'Zu wenig freier Arbeits- oder Grafikspeicher für dieses Rezept. Andere Programme beenden oder ein kleineres Rezept wählen.',
    gpu_lease_busy: 'Die Grafikkarte ist gerade belegt (Lauf oder anderer Dienst).',
    model_loader_unavailable: 'Das Laden von Modellen ist in dieser Installation ausgeschaltet.'
  };
  // Die Auswahl der Aufteilung als ein Satz (DR-06): „lädt mit 30 Lagen im RAM, 32 768 Kontext, ≈ 9,8 GB VRAM, 10,9 GB RAM“.
  function auswahlText(a){
    if(!a || typeof a.lagen !== 'number') return '';
    const zahl = (x, n)=>Number(x).toLocaleString('de-DE', {maximumFractionDigits: n});
    return 'mit ' + a.lagen + ' Lagen im RAM, ' + zahl(a.kontext, 0) + ' Kontext, ≈ ' + zahl(a.vram_gb, 1) + ' GB VRAM, ' + zahl(a.ram_gb, 1) + ' GB RAM'
      + (a.tokens_s ? ', ≈ ' + zahl(a.tokens_s, 0) + ' Token/s' : '') + (a.quelle === 'gemessen' ? ' (gemessene Werte)' : '');
  }

  // Die Gründe des Routers als Sätze (P2 V1); Gründe mit Zahlen (dynamische Rezepte) stehen schon als Satz da.
  const GRUENDE = {host_ram_below_minimum: 'zu wenig Arbeitsspeicher auf diesem Rechner', host_vram_below_minimum: 'zu wenig Grafikspeicher auf diesem Rechner',
    hardware_incompatible: 'passt nicht zu dieser Hardware', context_capacity: 'das Kontextfenster reicht nicht', slots_not_measured: 'Slots nicht gemessen',
    recipe_disabled: 'Rezept ausgeschaltet', provider_unavailable: 'der Server ist nicht erreichbar', provider_cooldown: 'der Server erholt sich gerade',
    location_not_local: 'kein lokales Modell', hardware_profile_changed: 'die Hardware hat sich geändert – Rezepte neu prüfen'};
  function grundtext(g){
    const s = String(g || '');
    if(/GB/.test(s)) return s;
    const k = Object.keys(GRUENDE).find(k=>s.startsWith(k));
    return k ? GRUENDE[k] : (s || 'passt nicht');
  }

  function fehlertext(err){
    const m = String((err && err.message) || err || '');
    const nenner = m.match(/recipe_not_usable:[a-z_]+:(.+)$/);                  // der Server nennt bei dynamischen Rezepten die Zahlen: genau diesen Satz zeigen
    if(nenner && /GB/.test(nenner[1])) return nenner[1];
    const treffer = Object.keys(GRUND).find(k=>m.includes(k));
    return treffer ? GRUND[treffer] + ' (' + m + ')' : m;
  }

  // Die Steuerung: Rezeptwahl, Laden/Wechseln, Entladen, Zustand. `nachher` läuft nach Erfolg (Anzeige auffrischen).
  function steuerung(S, nachher){
    const box = d().el('div', 'hs-modell-steuer');
    const wahl = d().el('select', 'hs-projektwahl'); wahl.setAttribute('aria-label', 'Modell-Rezept');
    const laden = d().el('button', 'hs-senden p', 'Laden'); laden.type = 'button';
    const weg = d().el('button', 'hs-knopf', 'Entladen'); weg.type = 'button';
    const stand = d().el('span', 'hs-leise hs-modell-stand', ''); stand.setAttribute('role', 'status');
    const merken = d().el('button', 'hs-knopf hs-vorgabe-knopf', 'Als Vorgabe merken'); merken.type = 'button'; merken.title = 'Dieses Rezept ist dann der Standard (und wird beim Senden geladen, wenn der Katalog es erlaubt)';
    merken.onclick = ()=>root.sedraHarness.projekt.setzen(S, {rezept_standard: wahl.value || null}, merken).then(auffrischen);
    let geladen = null;
    box.append(wahl, laden, weg, merken, stand);
    wahl.addEventListener('change', ()=>{ merken.hidden = !wahl.value || (S.vorgaben && S.vorgaben.rezept_standard) === wahl.value; });

    // P2 V1 (1.11.): „Passt das Modell?“ – je Rezept Name, Bedarf gegen freien Speicher und ein Urteil, vom Server mit derselben Prüfung wie beim Laden
    const zahl = (x, n)=>Number(x).toLocaleString('de-DE', {maximumFractionDigits: n});
    const urteil = m=>{
      if(m.passt === true) return '✓ passt' + (m.bedarf_vram_gb ? ' · ≈ ' + zahl(m.bedarf_vram_gb, 1) + ' GB VRAM' : '') + (m.auswahl && typeof m.auswahl.lagen === 'number' ? ', ' + m.auswahl.lagen + ' Lagen im RAM' : '');
      if(m.passt === false) return '✗ ' + grundtext(m.grund);
      return '';
    };
    async function auffrischen(){
      try{
        const v = await S.api('/api/harness/modelle');
        const rezepte = v.modelle || [];
        geladen = rezepte.find(r=>r.geladen) || null;
        const vorher = wahl.value;
        wahl.replaceChildren(...rezepte.map(r=>{
          const o = document.createElement('option'); o.value = r.id;
          o.textContent = (r.modell || r.id) + (r.groesse_gb ? ' · ' + zahl(r.groesse_gb, 1) + ' GB' : '') + ' · ' + urteil(r) + (r.geladen ? ' (geladen)' : '');
          o.title = r.id + (r.grund ? ' – ' + r.grund : '') + (r.gemessen ? ' – gemessene Werte' : '');
          o.dataset.passt = r.passt === true ? 'ja' : r.passt === false ? 'nein' : '';
          return o;
        }));
        const vorgabe = S.vorgaben && S.vorgaben.rezept_standard;                                   // P0 M3: die Vorgabe vor „zuletzt“
        const erstes = rezepte.find(r=>r.passt) || rezepte[0];
        wahl.value = rezepte.some(r=>r.id === vorher) ? vorher : (geladen ? geladen.id : (rezepte.some(r=>r.id === vorgabe) ? vorgabe : (erstes ? erstes.id : '')));
        merken.hidden = !wahl.value || vorgabe === wahl.value;
        laden.disabled = !wahl.value;
        laden.textContent = geladen ? 'Wechseln' : 'Laden';
        weg.hidden = !geladen;
        stand.classList.remove('bad');
        const frei = v.frei_vram_gb !== null && v.frei_vram_gb !== undefined ? 'frei: ' + zahl(v.frei_vram_gb, 1) + ' GB VRAM' + (v.frei_ram_gb ? ', ' + zahl(v.frei_ram_gb, 1) + ' GB RAM' : '') : '';
        if(!rezepte.length){
          stand.textContent = 'Keine Rezepte vorhanden – ';
          const w = d().el('button', 'hs-knopf', 'Werkstatt öffnen'); w.type = 'button'; w.onclick = ()=>root.sedraHarness.einstellungen.oeffnen(S, 'modelle/werkstatt');
          stand.append(w);
        }else stand.textContent = frei;
      }catch(err){ stand.textContent = 'Rezepte nicht lesbar: ' + err.message; laden.disabled = true; }
    }

    async function tun(pfad, body, text){
      laden.disabled = weg.disabled = wahl.disabled = true;
      stand.textContent = text;
      try{
        const out = await S.api(pfad, {method: 'POST', body});
        stand.textContent = '';
        const satz = auswahlText(out && out.auswahl);
        if(satz) S.hinweis('Modell geladen ' + satz + '.');
        await S.modellLaden();
        if(nachher) nachher(out);
      }catch(err){ stand.textContent = fehlertext(err); stand.classList.add('bad'); }
      finally{ wahl.disabled = false; laden.disabled = !wahl.value; weg.disabled = false; await auffrischen(); }
    }
    laden.onclick = ()=>{ stand.classList.remove('bad'); tun('/api/model/load', {recipe_id: wahl.value}, 'lädt … das kann einige Minuten dauern'); };
    weg.onclick = ()=>{ stand.classList.remove('bad'); tun('/api/model/unload', {}, 'entlädt …'); };
    auffrischen();
    return Object.assign(box, {auffrischen});
  }

  // 1.11. (Captain, Anmerkung am Eingabebereich): die Modellsteuerung steht nicht mehr als Streifen über dem Eingabefeld und hängt auch nicht an der
  // Werkstatt, sondern öffnet als kleines Fenster über der Statusleiste (Klick auf „Modell“ unten, auf den Modell-Chip im Eingabefeld oder auf
  // „Modell wählen“ der Erststart-Anleitung). Dieselbe Steuerung, dieselben Wege; nach Erfolg schließt es.
  function schliessen(S){
    const p = S._modellMenue;
    if(p){ p.remove(); S._modellMenue = null; }
    if(S._modellMenueAb){ S._modellMenueAb(); S._modellMenueAb = null; }
  }
  function menue(S, an){
    const offen = !!(S._modellMenue && S._modellMenue.isConnected);
    if(an === false || (an === undefined && offen)){ schliessen(S); return; }
    if(offen){ const wahl = S._modellMenue.querySelector('select'); if(wahl) wahl.focus(); return; }
    const p = d().el('div', 'hs-modell-menue'); p.setAttribute('role', 'dialog'); p.setAttribute('aria-label', 'Modell');
    const kopf = d().el('div', 'hs-modell-text', S.modell ? 'Geladen: ' + S.modell.name + '.' : 'Kein Modell geladen.');
    const zu = d().el('button', 'hs-rund hs-modell-zu', '×'); zu.type = 'button'; zu.setAttribute('aria-label', 'Schließen'); zu.onclick = ()=>schliessen(S);
    p.append(kopf, zu, steuerung(S, ()=>{ schliessen(S); if(root.sedraHarness.eingabe) root.sedraHarness.eingabe.modellZeigen(S); }));
    document.body.append(p); S._modellMenue = p;
    const taste = e=>{ if(e.key === 'Escape') schliessen(S); };
    const aussen = e=>{ if(!p.contains(e.target) && !(e.target.closest && e.target.closest('[data-zelle=model],[data-zelle=server],.hs-modell,.hs-erststart'))) schliessen(S); };
    document.addEventListener('keydown', taste); document.addEventListener('mousedown', aussen);
    S._modellMenueAb = ()=>{ document.removeEventListener('keydown', taste); document.removeEventListener('mousedown', aussen); };
    const wahl = p.querySelector('select'); if(wahl) wahl.focus();
  }

  // P0 M2 (1.11., E-A7): Modell beim Senden selbst laden – nur wenn der Server es erlaubt (Katalog `modell_laden` frei für das Standard-Rezept).
  // `melden(text, art)` schreibt in die Sitzung („lädt Modell …“). Gibt true zurück, wenn danach ein Modell geladen ist.
  async function autoLaden(S, melden){
    let v;
    try{ v = await S.api('/api/harness/vorgaben'); }catch(_e){ return false; }
    if(!v || !v.auto_laden || !v.auto_laden.rezept) return false;
    const rezept = v.auto_laden.rezept;
    melden('Lade Modell „' + rezept + '“ … das kann einige Minuten dauern (Regel ' + (v.auto_laden.regel || 'Katalog') + ').', 'info');
    const t0 = Date.now();
    try{
      const out = await S.api('/api/model/load', {method: 'POST', body: {recipe_id: rezept}});
      await S.modellLaden();
      const s = Math.round((Date.now() - t0) / 1000);
      const satz = auswahlText(out && out.auswahl);
      melden('Modell geladen nach ' + s + ' s' + (satz ? ' ' + satz : '') + '.', 'ok');
      return !!S.modell;
    }catch(err){ melden('Modell nicht geladen: ' + fehlertext(err), 'bad'); return false; }
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.modell = {steuerung, menue, schliessen, fehlertext, auswahlText, autoLaden, grundtext};
})();
