// UI contract 1.1 – registration and lifecycle (SHELL_WERKZEUG_VERTRAG_v1 §4; Vertrag 1.1: SPEC_DOCK_OHNE_NEUAUFBAU_v1 §3, §9, §10).
// A tool file does one thing when it loads: sedra.registerTool({...}). A shell file: sedra.registerShell({...}). Nothing else
// happens at load time, so the loader decides when a module is mounted and the Captain's screen never depends on script order.
// Classic script: defines window.sedra (the registry) and window.sedraLifecycle (mount/unmount, pure checks for node).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const tools = new Map(), shells = new Map();

  // '' when the module keeps the contract, otherwise the reason (pure – node tests this)
  function checkModule(mod, kind){
    if(!mod || typeof mod !== 'object') return 'Modul muss ein Objekt sein';
    if(typeof mod.id !== 'string' || !/^[a-z0-9-]{2,40}$/.test(mod.id)) return 'id fehlt oder ist ungültig';
    if(kind === 'tool'){
      if(typeof mod.mount !== 'function') return 'mount(el, ctx) fehlt';
      if(typeof mod.unmount !== 'function') return 'unmount() fehlt';
      if(mod.actions !== undefined && typeof mod.actions !== 'function') return 'actions muss eine Funktion sein';
    }else if(typeof mod.start !== 'function') return 'start(ctx) fehlt';
    return '';
  }

  function registerTool(mod){
    const bad = checkModule(mod, 'tool');
    if(bad) throw new Error('Werkzeug ' + (mod && mod.id || '?') + ': ' + bad);
    tools.set(mod.id, mod);
    return mod;
  }

  function registerShell(mod){
    const bad = checkModule(mod, 'shell');
    if(bad) throw new Error('Shell ' + (mod && mod.id || '?') + ': ' + bad);
    shells.set(mod.id, mod);
    return mod;
  }

  // One living instance of a tool in one container. The shell holds it; the tool itself knows nothing about docks or windows.
  function mountTool(mod, el, ctx, onError){
    // Stufe C: ein Werkzeug im Rahmen wird nicht in der Seite gezeichnet, sondern vom Stellvertreter eingehängt
    if(mod && mod.frame && typeof mod.mountFrame === 'function'){
      try{ return mod.mountFrame(el, ctx, onError); }
      catch(err){ onError && onError(mod.id, err); return {id: mod.id, el, ctx, mod, mounted: false, ready: Promise.resolve()}; }
    }
    const state = {id: mod.id, el, ctx, mod, mounted: false, ready: Promise.resolve()};
    try{
      const out = mod.mount(el, ctx);
      state.mounted = true;
      // `ready` ist erfüllt, sobald das Werkzeug zum ersten Mal gezeichnet hat. Die Shell braucht das: vorher weiß ein Werkzeug
      // noch nicht, welche Handlungen sein Objekt anbietet – eine Werkbank-Zeile, die zu früh fragt, bleibt leer.
      if(out && typeof out.then === 'function') state.ready = out.catch(err=>{ onError && onError(mod.id, err); });
    }catch(err){
      onError && onError(mod.id, err);
      // Härtung 30.10. (HU-L10): ein Werkzeug, das beim Einhängen wirft, hat vielleicht schon Bus-Abos – die sterben mit ihm, nicht erst mit der Seite
      (ctx && ctx._offs || []).splice(0).forEach(off=>{ try{ off(); }catch(_e){} });
      try{ el.replaceChildren(); }catch(_e){}
    }
    // Vertrag 1.1 §3.3: die Scrollposition kommt zurück, sobald das Werkzeug gezeichnet hat – ohne dass es etwas dafür tun muss
    if(ctx && ctx.memo) state.ready = state.ready.then(()=>scrollZurueck(el, ctx.memo.get(SCROLL)));
    return state;
  }

  // Nachtrag N2 (Spec 4, G2-S4-04): `unmount(el)` und `actions(el)` bekommen den Container, den `mount` bekam. Ein Werkzeug mit
  // mehreren Instanzen (eine je Container, z. B. ein Fenster je Agent) findet so die richtige; eines mit einer Instanz ignoriert es.
  function unmountTool(state, onError){
    if(!state || !state.mounted) return;
    state.mounted = false;
    const c = state.ctx || {};
    if(c.memo) try{ c.memo.set(SCROLL, scrollStand(state.el)); }catch(_e){}         // Vertrag 1.1 §3.3
    if(c.ablage && c.ablage.flush) try{ c.ablage.flush(); ablagen.delete(c.ablage); }catch(_e){}   // was noch offen ist, geht jetzt zum Server
    if(typeof state.abbau === 'function'){ try{ state.abbau(); }catch(_e){} }     // Stufe C: den Rahmen abmelden
    (c._eingebettet || []).splice(0).forEach(st=>unmountTool(st, onError));       // N9: eingebettete Werkzeuge gehen mit dem Einbettenden
    try{ state.mod.unmount(state.el); }
    catch(err){ onError && onError(state.id, err); }
    try{ state.el.replaceChildren(); }catch(_e){}
    (state.ctx && state.ctx._offs || []).forEach(off=>{ try{ off(); }catch(_e){} });
  }

  // the actions of a tool in its current state, as the Werkbank row shows them (Cockpit rule 3)
  function actionsOf(state){
    if(!state || !state.mod.actions) return [];
    let list;
    try{ list = state.mod.actions(state.el); }catch(_e){ return []; }
    // Härtung 30.10. (HU-T8): eine Handlung, die scheitert, sagt es dem Captain über die Shell (notify) – vorher verschluckten
    // Werkbank-Zeilen ohne eigene Fehleranzeige (Harness, Rahmen) die Ablehnung; `run` bleibt für die Shell ein Promise ohne Fehler
    const melden = (label, err)=>{ try{ const sh = state.ctx && state.ctx.shell; if(sh && sh.notify) sh.notify('„' + label + '“ fehlgeschlagen: ' + (err && err.message || err), 'warn'); }catch(_e){} };
    return (Array.isArray(list) ? list : []).filter(a=>a && typeof a.label === 'string' && typeof a.run === 'function')
      .map(a=>Object.assign({}, a, {run: ()=>{ let p; try{ p = Promise.resolve(a.run()); }catch(err){ p = Promise.reject(err); } return p.catch(err=>{ melden(a.label, err); }); }}));
  }

  // ==== Vertrag 1.1: drei Gedächtnisse (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §3) =============================================
  // ctx.memo     – im Speicher der Seite, je Werkzeug und Objekt; übersteht Abbau und Einhängen, nicht das Neuladen. Darf alles.
  // ctx.sitzung  – sessionStorage, nur mit `gedaechtnis: sitzung`; übersteht Neuladen und Shell-Wechsel. Nur Zustand der Ansicht.
  // ctx.ablage   – im Speicher der Runtime, nur mit `gedaechtnis: ablage`; übersteht Neuladen, Shell-Wechsel, zweiten Reiter. Auch Inhalt.
  const SCROLL = '__scroll';
  const SITZUNG_PREFIX = 'sedra.memo.';
  const SITZUNG_EINTRAG = 4 * 1024, SITZUNG_GESAMT = 64 * 1024;
  const memos = new Map();                       // 'werkzeug|typ:id' -> Map(name -> Wert)

  // der Schlüssel eines Objekts, wie der Server ihn kennt (`typ:id`); ein Werkzeug ohne Objekt (Instrument, Gespräch) hat `panel:<id>`
  function objektSchluessel(object, toolId){
    if(object && object.type && object.id !== undefined && object.id !== null) return String(object.type) + ':' + String(object.id);
    return 'panel:' + String(toolId || 'ohne');
  }

  function memoFuer(toolId, object){
    const key = String(toolId) + '|' + objektSchluessel(object, toolId);
    return {
      get(name, vorgabe){ const m = memos.get(key); return m && m.has(name) ? m.get(name) : vorgabe; },
      set(name, wert){ if(!memos.has(key)) memos.set(key, new Map()); memos.get(key).set(name, wert); },
      clear(){ memos.delete(key); }
    };
  }

  function speicherDerSitzung(){
    try{ return typeof sessionStorage !== 'undefined' ? sessionStorage : null; }catch(_e){ return null; }
  }

  // Wer `gedaechtnis: sitzung` nicht im Manifest hat, bekommt eine Attrappe: sie nimmt alles an und behält nichts.
  const ATTRAPPE = Object.freeze({get: (_n, vorgabe)=>vorgabe, set(){}, clear(){}, aktiv: false});

  function sitzungFuer(toolId, object, erlaubt, speicher, sagen){
    if(!erlaubt) return ATTRAPPE;
    const store = speicher === undefined ? speicherDerSitzung() : speicher;
    const key = SITZUNG_PREFIX + String(toolId) + '|' + objektSchluessel(object, toolId);
    const lesen = ()=>{
      try{ const raw = store && store.getItem(key); const v = raw ? JSON.parse(raw) : {}; return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; }
      catch(_e){ return {}; }               // kaputtes JSON, privater Modus: so tun, als wäre nichts da
    };
    const gesamt = ohne=>{
      let n = 0;
      try{ for(let i = 0; i < store.length; i++){ const k = store.key(i); if(k && k.indexOf(SITZUNG_PREFIX) === 0 && k !== ohne) n += k.length + String(store.getItem(k) || '').length; } }
      catch(_e){}
      return n;
    };
    return {
      aktiv: !!store,
      get(name, vorgabe){ const v = lesen(); return Object.prototype.hasOwnProperty.call(v, name) ? v[name] : vorgabe; },
      set(name, wert){
        if(!store) return;
        const v = lesen(); v[name] = wert;
        let text;
        try{ text = JSON.stringify(v); }catch(_e){ if(sagen) sagen(toolId, new Error('Sitzung: nur JSON-Werte erlaubt')); return; }
        if(text.length > SITZUNG_EINTRAG || gesamt(key) + key.length + text.length > SITZUNG_GESAMT){
          if(sagen) sagen(toolId, new Error('Sitzung: Grenze erreicht (4 KB je Objekt, 64 KB gesamt) – nicht gespeichert'));
          return;
        }
        try{ store.setItem(key, text); }catch(_e){ if(sagen) sagen(toolId, new Error('Sitzung: der Browser nimmt nichts mehr an')); }
      },
      clear(){ try{ store && store.removeItem(key); }catch(_e){} }
    };
  }

  // ctx.ablage: get() lädt einmal vom Server, set() schreibt gebündelt (höchstens einmal je Sekunde), flush() sofort.
  const ablagen = new Set();                     // jede lebende Ablage: vor einem Shell-Wechsel schreibt sie, was offen ist
  function ablagenSchreiben(){ return Promise.all(Array.from(ablagen).map(a=>a.flush())); }
  const ABLAGE_ATTRAPPE = Object.freeze({get: async(_n, vorgabe)=>vorgabe, set(){}, clear(){}, flush(){}, aktiv: false});

  function ablageFuer(toolId, object, erlaubt, api, uhr){
    if(!erlaubt || typeof api !== 'function') return ABLAGE_ATTRAPPE;
    const objekt = objektSchluessel(object, toolId);
    if(objekt.indexOf('panel:') === 0) return ABLAGE_ATTRAPPE;      // ohne Objekt keine Ablage: der Server kennt nur Objekte
    const t = uhr || {setTimeout: (f, ms)=>setTimeout(f, ms), clearTimeout: id=>clearTimeout(id)};
    let werte = null, laden = null, offen = null, zeit = null, geladen = false;
    const holen = ()=>{
      if(geladen) return Promise.resolve(werte);
      if(!laden) laden = api('/api/ablage/lesen', {method: 'POST', body: {objekt}})
        .then(r=>{ werte = Object.assign({}, (r && r.werte) || {}, werte || {}); zeit = r && r.zeit; geladen = true; return werte; },
              ()=>{ werte = werte || {}; geladen = true; return werte; });            // keine Verbindung: leer weiter, nie ein Fehler im Werkzeug
      return laden;
    };
    const schreiben = ()=>{
      offen = null;
      // Härtung 30.10. (HU-L4): der Server ersetzt die Werte – also erst die vorhandenen holen, dann die eigenen darüberlegen
      return holen().then(()=>api('/api/ablage/schreiben', {method: 'POST', body: {objekt, werte: werte || {}}})).catch(()=>{});
    };
    const ablage = {
      aktiv: true,
      async get(name, vorgabe){ const v = await holen(); return Object.prototype.hasOwnProperty.call(v, name) ? v[name] : vorgabe; },
      async zeit(){ await holen(); return zeit; },
      set(name, wert){
        werte = werte || {}; werte[name] = wert;
        if(offen === null) offen = t.setTimeout(schreiben, 1000);
      },
      clear(){ werte = {}; geladen = true; if(offen !== null){ t.clearTimeout(offen); } return schreiben(); },
      flush(){ if(offen !== null){ t.clearTimeout(offen); return schreiben(); } return Promise.resolve(); }
    };
    ablagen.add(ablage);
    return ablage;
  }

  // Beim Schließen eines Objekts (§9.3): Memo und Sitzung aller Werkzeuge an diesem Objekt vergessen
  function memoVergessen(object, speicher){
    const objekt = objektSchluessel(object);
    Array.from(memos.keys()).forEach(k=>{ if(k.slice(k.indexOf('|') + 1) === objekt) memos.delete(k); });
    const store = speicher === undefined ? speicherDerSitzung() : speicher;
    try{
      const weg = [];
      for(let i = 0; store && i < store.length; i++){ const k = store.key(i); if(k && k.indexOf(SITZUNG_PREFIX) === 0 && k.slice(k.indexOf('|') + 1) === objekt) weg.push(k); }
      weg.forEach(k=>store.removeItem(k));
    }catch(_e){}
  }

  // „Gedächtnis leeren“ im Umschalter (§10.5): alles, was im Browser liegt
  function gedaechtnisLeeren(speicher){
    memos.clear();
    const store = speicher === undefined ? speicherDerSitzung() : speicher;
    try{
      const weg = [];
      for(let i = 0; store && i < store.length; i++){ const k = store.key(i); if(k && k.indexOf(SITZUNG_PREFIX) === 0) weg.push(k); }
      weg.forEach(k=>store.removeItem(k));
    }catch(_e){}
  }

  function gedaechtnisVon(manifest){
    const g = (manifest && manifest.gedaechtnis) || [];
    return Array.isArray(g) ? g : [g];
  }
  function istMehrfach(manifest){ return !!manifest && manifest.instanzen === 'viele'; }

  // ---- Scrollposition (§3.3): der Container und der nächste rollende Vorfahr
  function rollenderVorfahr(el){
    let n = el && el.parentElement;
    while(n){ if(n.scrollHeight > n.clientHeight + 1 && n.scrollTop !== undefined) return n; n = n.parentElement; }
    return null;
  }
  function scrollStand(el){
    if(!el) return null;
    const vorfahr = rollenderVorfahr(el);
    return {selbst: el.scrollTop || 0, vorfahr: vorfahr ? vorfahr.scrollTop || 0 : 0};
  }
  function scrollZurueck(el, stand){
    if(!el || !stand) return;
    const setzen = ()=>{
      try{ if(stand.selbst) el.scrollTop = stand.selbst; }catch(_e){}
      const vorfahr = stand.vorfahr ? (rollenderVorfahr(el) || el.parentElement) : null;
      try{ if(vorfahr) vorfahr.scrollTop = stand.vorfahr; }catch(_e){}
    };
    if(typeof requestAnimationFrame === 'function') requestAnimationFrame(setzen); else setzen();
  }

  // ---- Versteckt halten (§3.5, §9.4): nur für `instanzen: viele`; die freiwilligen Haken hidden(el) / shown(el)
  function bereitHalten(state){
    if(!state || !state.mounted || state.versteckt) return;
    state.versteckt = true;
    if(state.el) state.el.hidden = true;
    if(state.mod && typeof state.mod.hidden === 'function') try{ state.mod.hidden(state.el); }catch(_e){}
  }
  function zeigen(state){
    if(!state || !state.mounted || !state.versteckt) return;
    state.versteckt = false;
    if(state.el) state.el.hidden = false;
    if(state.mod && typeof state.mod.shown === 'function') try{ state.mod.shown(state.el); }catch(_e){}
  }

  // ---- Bündeln (§9.5): viele Anstöße in kurzer Zeit → ein Aufruf am Ende des Fensters; `jetzt()` ruft sofort
  function buendeln(fn, ms, uhr){
    const t = uhr || {setTimeout: (f, d)=>setTimeout(f, d), clearTimeout: id=>clearTimeout(id)};
    let wartet = null, argsZuletzt = [];
    const los = ()=>{ wartet = null; try{ return fn.apply(null, argsZuletzt); }catch(_e){ return undefined; } };
    const b = function(){ argsZuletzt = Array.from(arguments); if(wartet === null) wartet = t.setTimeout(los, ms === undefined ? 500 : ms); };
    b.jetzt = function(){ if(wartet !== null) t.clearTimeout(wartet); argsZuletzt = Array.from(arguments).length ? Array.from(arguments) : argsZuletzt; return los(); };
    b.wartet = ()=>wartet !== null;
    return b;
  }

  root.sedra = {registerTool, registerShell, tools, shells};
  root.sedraLifecycle = {checkModule, mountTool, unmountTool, actionsOf, tools, shells,
                         objektSchluessel, memoFuer, sitzungFuer, ablageFuer, memoVergessen, gedaechtnisLeeren, gedaechtnisVon,
                         istMehrfach, bereitHalten, zeigen, buendeln, scrollStand, ablagenSchreiben, VERSION: '1.1'};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraLifecycle;
})();
