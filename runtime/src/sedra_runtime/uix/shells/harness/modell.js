// Harness-Shell – Modell laden, wechseln und entladen direkt im Eingabebereich (Stufe 6, HS-80/HS-81): statt eines Verweises („Start → Modelle → Werkstatt“) steht dort, wo es fehlt,
// die Handlung selbst: Rezept wählen, „Laden“. Dieselben Wege wie die Werkstatt (GET /api/models, POST /api/model/load, POST /api/model/unload); Gates, Speicherprüfung und Fehlertexte
// kommen vom Server und werden unverändert angezeigt. Ein Ladevorgang kann Minuten dauern: der Knopf zeigt „lädt …“, nichts anderes wird blockiert.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const GRUND = {
    hardware_pressure: 'Zu wenig freier Arbeits- oder Grafikspeicher für dieses Rezept. Andere Programme beenden oder ein kleineres Rezept wählen.',
    gpu_lease_busy: 'Die Grafikkarte ist gerade belegt (Lauf oder anderer Dienst).',
    model_loader_unavailable: 'Das Laden von Modellen ist in dieser Installation ausgeschaltet.',
    external_server_unreachable: 'Der Modell-Router läuft nicht. Starte ihn (llama-server mit der Modelldatei, Port 8090) oder schalte llama_server.external in den lokalen Schaltern aus.'
  };
  // Die Auswahl der Aufteilung als ein Satz (DR-06): „lädt mit 30 Lagen im RAM, 32 768 Kontext, ≈ 9,8 GB VRAM, 10,9 GB RAM“.
  function auswahlText(a){
    if(!a || typeof a.lagen !== 'number') return '';
    const zahl = (x, n)=>Number(x).toLocaleString('de-DE', {maximumFractionDigits: n});
    return 'mit ' + a.lagen + ' Lagen im RAM, ' + zahl(a.kontext, 0) + ' Kontext, ≈ ' + zahl(a.vram_gb, 1) + ' GB VRAM, ' + zahl(a.ram_gb, 1) + ' GB RAM'
      + (a.tokens_s ? ', ≈ ' + zahl(a.tokens_s, 0) + ' Token/s' : '') + (a.quelle === 'gemessen' ? ' (gemessene Werte)' : '');
  }

  // Passte das gewählte Fenster nicht in den Speicher, lädt Sedra die nächstkleinere Stufe und sagt es (Antwort `fenster_angepasst`).
  function angepasstText(out){
    const a = out && out.fenster_angepasst; if(!a) return '';
    return 'Fenster ' + Number(a.gewuenscht).toLocaleString('de-DE') + ' passte nicht in den freien Speicher – geladen mit ' + Number(a.gewaehlt).toLocaleString('de-DE') + ' Token.';
  }

  // Die Gründe des Routers als Sätze (P2 V1); Gründe mit Zahlen (dynamische Rezepte) stehen schon als Satz da.
  const GRUENDE = {host_ram_below_minimum: 'zu wenig Arbeitsspeicher auf diesem Rechner', host_vram_below_minimum: 'zu wenig Grafikspeicher auf diesem Rechner',
    hardware_incompatible: 'passt nicht zu dieser Hardware', context_capacity: 'das Kontextfenster reicht nicht', slots_not_measured: 'Slots nicht gemessen',
    recipe_disabled: 'Rezept ausgeschaltet', provider_unavailable: 'der Server ist nicht erreichbar', provider_cooldown: 'der Server erholt sich gerade',
    vram_insufficient: 'zu wenig freier Grafikspeicher', ram_measured: 'zu wenig freier Arbeitsspeicher', ram_ledger: 'Arbeitsspeicher ist anderweitig vergeben', hardware_pressure: 'zu wenig freier Speicher',
    gpu_lease_busy: 'die Grafikkarte ist gerade belegt', job_limit: 'es laufen schon zu viele Aufträge',
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

  // Wofuer ein Fenster taugt, in Worten (die Zahl allein sagt dem Nutzer nichts): Kurztest, kleine Aufgabe, Standard, grosse Aufgabe, Bau.
  function fensterZweck(t){ t = Number(t); return t <= 8192 ? 'Kurztest' : t <= 16384 ? 'kleine Aufgabe' : t <= 32768 ? 'Standard' : t <= 65536 ? 'große Aufgabe' : 'Bau, sehr großer Auftrag'; }
  // Kurzname und feste Reihenfolge eines Rezepts in der Liste: ohne sie sähen vier Rezepte desselben Modells gleich aus. Aus der Rezept-ID und den Kanälen abgeleitet;
  // die Captain-Datei bleibt unberührt. Reihenfolge je Gruppe: Power, Team, Bau nach Kanälen aufsteigend, Standard, Rest.
  function kurzname(r){
    const id = String((r && r.id) || ''), ende = id.split('.').pop();
    const nk = ende.match(/(\d+)x(\d+)k/);
    if(/power/.test(ende)) return {name: 'Power', rang: 0};
    if(/team/.test(ende)) return {name: 'Team', rang: 1};
    if(nk) return {name: nk[1] + ' × ' + nk[2] + 'k', rang: 2 + Number(nk[1]) / 100};
    if(/gemma|verifier/.test(id)) return {name: 'Prüfer', rang: 5};
    if(/primary|e4b$|qwen35$/.test(ende)) return {name: 'Standard', rang: 3};
    const q = ende.match(/(q\d_k\w*)/i);
    if(q) return {name: q[1].toUpperCase(), rang: 4};
    return {name: ende.replace(/^local_|^llama_/, '').replace(/_/g, ' ') || id, rang: 6};
  }
  const kanaeleText = n=>Number(n) === 1 ? '1 Kanal' : n ? n + ' Kanäle' : '';
  const fensterKurz = t=>t ? 'bis ' + Math.round(Number(t) / 1024) + 'k' : '';
  // Die Zeile einer Option als reiner Text: Kurzname – Modell · Kanäle · Fenster · Urteil (Urteil vom Aufrufer, damit diese Funktion ohne Seite prüfbar bleibt).
  function optionsText(r, urteil){
    const k = kurzname(r), fenster = fensterKurz([...(r.kontexte || [])].sort((a, b)=>b - a)[0]);
    return [k.name + ' – ' + (r.modell || r.id), kanaeleText(r.slots), fenster, urteil + (r.geladen ? ' (geladen)' : '')].filter(Boolean).join(' · ');
  }
  // Reihenfolge innerhalb einer Gruppe: geladen, dann was passt, dann nach Rang, dann nach Name – gleichbleibend, unabhängig vom Speicherstand.
  function reihenfolge(a, b){
    return (b.geladen ? 1 : 0) - (a.geladen ? 1 : 0) || (b.passt === true ? 1 : 0) - (a.passt === true ? 1 : 0)
      || kurzname(a).rang - kurzname(b).rang || String(a.id).localeCompare(String(b.id));
  }
  // Reihenfolge der Gruppen in der Modellwahl nach Einsatz; unbekannte Einsätze stehen dahinter, Rezepte ohne Einsatz unter „Weitere“.
  const EINSATZ = ['Bau und Agenten', 'Prüfen', 'Schnelltest und Werkzeuge', 'Hilfsmodell'];

  // Die Steuerung: Rezeptwahl, Laden/Wechseln, Entladen, Zustand. `nachher` läuft nach Erfolg (Anzeige auffrischen).
  function steuerung(S, nachher){
    const box = d().el('div', 'hs-modell-steuer');
    const wahl = d().el('select', 'hs-projektwahl'); wahl.setAttribute('aria-label', 'Modell-Rezept');
    const fenster = d().el('select', 'hs-projektwahl hs-kontextwahl'); fenster.setAttribute('aria-label', 'Kontextfenster');
    fenster.title = 'Kontextfenster: „Auto“ startet mit dem größten Fenster, das in den Speicher passt; eine Stufe ist der Wunsch „höchstens so viel“: passt sie nicht in den Speicher, nimmt Sedra die nächstkleinere';
    const laden = d().el('button', 'hs-senden p', 'Laden'); laden.type = 'button';
    const weg = d().el('button', 'hs-knopf', 'Entladen'); weg.type = 'button';
    const stand = d().el('span', 'hs-leise hs-modell-stand', ''); stand.setAttribute('role', 'status');
    const merken = d().el('button', 'hs-knopf hs-vorgabe-knopf', 'Als Vorgabe merken'); merken.type = 'button'; merken.title = 'Dieses Rezept ist dann der Standard (und wird beim Senden geladen, wenn der Katalog es erlaubt)';
    merken.onclick = ()=>root.sedraHarness.projekt.setzen(S, {rezept_standard: wahl.value || null}, merken).then(auffrischen);
    let geladen = null;
    const beschr = d().el('div', 'hs-leise hs-modell-beschr', '');
    box.append(wahl, fenster, laden, weg, merken, stand, beschr);
    let liste = [];
    // Kontextfenster zum Rezept: „Auto“ (das größte, das passt) und die Stufen des Rezepts; ohne Stufen gibt es nur „Auto“
    function fensterFuellen(vorwahl){
      const r = liste.find(x=>x.id === wahl.value) || {};
      const stufen = r.kontexte || [];
      const ungemessen = r.kontexte_ungemessen || [];
      const zeile = (v, t, aus)=>{ const o = document.createElement('option'); o.value = v; o.textContent = t; if(aus){ o.disabled = true; o.title = 'Für dieses Fenster fehlt die Messung (gemessen bis ' + Number(r.kontext_gemessen_bis || 0).toLocaleString('de-DE') + ' Token). Messlauf starten, dann steht die Stufe hier frei.'; } return o; };
      fenster.replaceChildren(zeile('auto', 'Fenster: Auto (größtes, das passt)'),
        ...stufen.map(t=>zeile(String(t), 'Fenster: ' + Number(t).toLocaleString('de-DE') + ' · ' + fensterZweck(t))),
        ...ungemessen.map(t=>zeile(String(t), 'Fenster: ' + Number(t).toLocaleString('de-DE') + ' · ' + fensterZweck(t) + ' (nicht gemessen)', true)));
      const w = vorwahl !== undefined ? String(vorwahl) : (r.kontext_wahl !== undefined ? String(r.kontext_wahl) : 'auto');
      fenster.value = [...fenster.options].some(o=>o.value === w) ? w : 'auto';
      fenster.disabled = !stufen.length;
      beschr.textContent = (r.beschreibung || '') + (r.beschreibung && ungemessen.length ? ' ' : '') + (ungemessen.length ? 'Fenster ab ' + Number(ungemessen[0]).toLocaleString('de-DE') + ' warten auf eine Messung.' : '');
    }
    const fensterWert = ()=>fenster.value === 'auto' || !fenster.value ? 'auto' : Number(fenster.value);
    wahl.addEventListener('change', ()=>{ merken.hidden = !wahl.value || (S.vorgaben && S.vorgaben.rezept_standard) === wahl.value; fensterFuellen(); });

    // P2 V1 (1.11.): „Passt das Modell?“ – je Rezept Name, Bedarf gegen freien Speicher und ein Urteil, vom Server mit derselben Prüfung wie beim Laden
    const zahl = (x, n)=>Number(x).toLocaleString('de-DE', {maximumFractionDigits: n});
    const urteil = m=>{
      if(m.passt === true) return '✓ passt' + (m.bedarf_vram_gb ? ' · ≈ ' + zahl(m.bedarf_vram_gb, 1) + ' GB VRAM' : '') + (m.auswahl && typeof m.auswahl.lagen === 'number' ? ', ' + m.auswahl.lagen + ' Lagen im RAM' : '');
      if(m.passt === false) return '✗ passt nicht: ' + grundtext(m.grund);
      return '';
    };
    async function auffrischen(){
      if(!wahl.options.length){ stand.textContent = 'Rezepte werden gelesen …'; laden.disabled = true; }   // der Server braucht bei nicht laufendem Router einige Sekunden
      try{
        const v = await S.api('/api/harness/modelle');
        const rezepte = v.modelle || [];
        liste = rezepte;
        geladen = rezepte.find(r=>r.geladen) || null;
        const vorher = wahl.value, fensterVorher = fenster.value;
        const option = r=>{
          const o = document.createElement('option'); o.value = r.id;
          o.textContent = optionsText(r, urteil(r));
          o.title = (r.beschreibung ? r.beschreibung + ' – ' : '') + (r.groesse_gb ? zahl(r.groesse_gb, 1) + ' GB Gewichte – ' : '') + r.id + (r.grund ? ' – ' + r.grund : '') + (r.gemessen ? ' – gemessene Werte' : '');
          o.dataset.passt = r.passt === true ? 'ja' : r.passt === false ? 'nein' : '';
          return o;
        };
        const gruppen = [...EINSATZ, ...new Set(rezepte.map(r=>r.einsatz).filter(e=>e && !EINSATZ.includes(e))), ''];
        wahl.replaceChildren(...gruppen.map(g=>{
          const dazu = rezepte.filter(r=>(r.einsatz || '') === g).sort(reihenfolge); if(!dazu.length) return null;
          const og = document.createElement('optgroup'); og.label = g || 'Weitere'; og.append(...dazu.map(option)); return og;
        }).filter(Boolean));
        const vorgabe = S.vorgaben && S.vorgaben.rezept_standard;                                   // P0 M3: die Vorgabe vor „zuletzt“
        const erstes = [...rezepte].sort(reihenfolge).find(r=>r.passt) || rezepte[0];
        wahl.value = rezepte.some(r=>r.id === vorher) ? vorher : (geladen ? geladen.id : (rezepte.some(r=>r.id === vorgabe) ? vorgabe : (erstes ? erstes.id : '')));
        merken.hidden = !wahl.value || vorgabe === wahl.value;
        fensterFuellen(wahl.value === vorher && fensterVorher ? fensterVorher : undefined);
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
      laden.disabled = weg.disabled = wahl.disabled = fenster.disabled = true;
      stand.textContent = text;
      try{
        const out = await S.api(pfad, {method: 'POST', body});
        stand.textContent = '';
        const satz = auswahlText(out && out.auswahl);
        if(satz) S.hinweis('Modell geladen ' + satz + '.');
        if(angepasstText(out)) S.hinweis(angepasstText(out));
        await S.modellLaden();
        if(nachher) nachher(out);
      }catch(err){ stand.textContent = fehlertext(err); stand.classList.add('bad'); }
      finally{ wahl.disabled = false; laden.disabled = !wahl.value; weg.disabled = false; await auffrischen(); }
    }
    laden.onclick = ()=>{ stand.classList.remove('bad'); tun('/api/model/load', {recipe_id: wahl.value, kontext: fensterWert()}, 'lädt … das kann einige Minuten dauern'); };
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
    p.append(kopf, zu, steuerung(S, ()=>{ schliessen(S); if(root.sedraHarness.eingabe) root.sedraHarness.eingabe.modellZeigen(S); }), routerTeil(S));
    document.body.append(p); S._modellMenue = p;
    const taste = e=>{ if(e.key === 'Escape') schliessen(S); };
    const aussen = e=>{ if(!p.contains(e.target) && !(e.target.closest && e.target.closest('[data-zelle=model],[data-zelle=server],.hs-modell,.hs-erststart'))) schliessen(S); };
    document.addEventListener('keydown', taste); document.addEventListener('mousedown', aussen);
    S._modellMenueAb = ()=>{ document.removeEventListener('keydown', taste); document.removeEventListener('mousedown', aussen); };
    const wahl = p.querySelector('select'); if(wahl) wahl.focus();
  }

  // Abschnitt „Modellserver“ im Modell-Menü (Captain 03.11.2026: Modell und Server sind ein Menü, die Zellen „Modell“ und „Modellserver“ öffnen beide dieses): der
  // Sedra-Modell-Router – Zustand, Starten/Beenden und seine Optionen (GET/POST /api/harness/router).
  const ROUTER_FEHLER = {router_laeuft_schon: 'Der Router läuft schon.', router_fremd: 'Dieser Router wurde von einem anderen Programm gestartet (Pi, StarNet); Sedra beendet ihn nicht.',
    router_ohne_modelle: 'Es ist noch kein Modell in der Liste.', router_beendet_beim_start: 'Der Router hat sich beim Start beendet (siehe Protokoll).',
    router_start_zeitueberschreitung: 'Der Router ist nicht rechtzeitig bereit geworden (siehe Protokoll).'};
  function routerTeil(S){
    const p = d().el('div', 'hs-router-menue hs-router-teil'); p.setAttribute('role', 'group'); p.setAttribute('aria-label', 'Modellserver');
    const kopf = d().el('div', 'hs-modell-text', 'Sedra-Modell-Router');
    const zustand = d().el('div', 'hs-leise hs-router-zustand', 'liest …'); zustand.setAttribute('role', 'status');
    const knoepfe = d().el('div', 'hs-modell-steuer');
    const start = d().el('button', 'hs-senden p', 'Starten'); start.type = 'button';
    const ende = d().el('button', 'hs-knopf', 'Beenden'); ende.type = 'button';
    const auto = d().el('input'); auto.type = 'checkbox'; auto.id = 'hs-router-auto';
    const autoText = d().el('label', null, 'Automatisch starten, wenn ein Modell geladen wird'); autoText.htmlFor = 'hs-router-auto';
    const max = d().el('input', 'hs-router-zahl'); max.type = 'number'; max.min = 1; max.max = 8; max.setAttribute('aria-label', 'Gleichzeitig geladene Modelle');
    const leer = d().el('input', 'hs-router-zahl'); leer.type = 'number'; leer.min = 0; leer.max = 86400; leer.setAttribute('aria-label', 'Leerlauf in Sekunden');
    const speichern = d().el('button', 'hs-knopf', 'Optionen speichern'); speichern.type = 'button';
    const optionen = d().el('div', 'hs-modell-steuer');
    optionen.append(auto, autoText);
    const zeile2 = d().el('div', 'hs-modell-steuer');
    zeile2.append(d().el('label', 'hs-leise', 'Modelle gleichzeitig'), max, d().el('label', 'hs-leise', 'Entladen nach Leerlauf (s, 0 = nie)'), leer, speichern);
    knoepfe.append(start, ende);
    const hinweis = d().el('div', 'hs-leise hs-router-hinweis', '');
    p.append(kopf, zustand, knoepfe, optionen, zeile2, hinweis);
    const text = e=>{ const m = String((e && e.message) || e || ''); const k = Object.keys(ROUTER_FEHLER).find(k=>m.includes(k)); return k ? ROUTER_FEHLER[k] : m; };
    async function lesen(st){
      try{
        const v = st || await S.api('/api/harness/router');
        if(!v.verfuegbar){
          zustand.textContent = v.extern ? 'Sedra startet den Router nicht selbst (keine Start-Konfiguration).' : 'Der Router-Modus ist aus: Sedra startet für jedes Laden einen eigenen Modellserver.';
          knoepfe.hidden = optionen.hidden = zeile2.hidden = true; return;
        }
        zustand.textContent = (v.laeuft ? (v.eigen ? 'läuft (von Sedra gestartet)' : 'läuft (von einem anderen Programm gestartet – Sedra fasst ihn nicht an)') : 'aus') + ' · ' + v.endpoint
          + (v.modelle && v.modelle.length ? ' · ' + v.modelle.length + ' Modelle in der Liste' : '');
        start.disabled = v.laeuft; ende.disabled = !v.laeuft || !v.eigen;
        auto.checked = !!v.optionen.auto_start; max.value = v.optionen.models_max; leer.value = v.optionen.sleep_idle_s;
        hinweis.textContent = v.laeuft ? '' : 'Beim Laden eines Modells startet Sedra den Router selbst' + (v.optionen.auto_start ? '.' : ' – nicht, solange die Automatik aus ist.');
      }catch(err){ zustand.textContent = 'Zustand nicht lesbar: ' + text(err); }
    }
    async function tun(body, wort){
      start.disabled = ende.disabled = speichern.disabled = true; hinweis.classList.remove('bad'); hinweis.textContent = wort;
      try{ const v = await S.api('/api/harness/router', {method: 'POST', body}); hinweis.textContent = ''; await lesen(v); if(S.modellLaden) S.modellLaden(); }
      catch(err){ hinweis.textContent = text(err); hinweis.classList.add('bad'); await lesen(); }
      finally{ speichern.disabled = false; if(root.sedraHarness.taskleiste) root.sedraHarness.taskleiste.status(S); }
    }
    start.onclick = ()=>tun({aktion: 'starten'}, 'startet … das kann eine Minute dauern');
    ende.onclick = ()=>tun({aktion: 'beenden'}, 'beendet …');
    speichern.onclick = ()=>tun({optionen: {auto_start: auto.checked, models_max: Number(max.value), sleep_idle_s: Number(leer.value)}}, 'speichert …');
    lesen();
    return p;
  }
  function routerMenue(S){ menue(S, true); }                                 // die Zelle „Modellserver“ öffnet das Modell-Menü

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
      melden('Modell geladen nach ' + s + ' s' + (satz ? ' ' + satz : '') + '.' + (angepasstText(out) ? ' ' + angepasstText(out) : ''), 'ok');
      return !!S.modell;
    }catch(err){ melden('Modell nicht geladen: ' + fehlertext(err), 'bad'); return false; }
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.modell = {steuerung, menue, routerMenue, schliessen, fehlertext, auswahlText, autoLaden, grundtext, kurzname, optionsText, reihenfolge};
})();
