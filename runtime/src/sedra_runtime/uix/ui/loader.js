// UI contract 1.0 – the loader (SHELL_WERKZEUG_VERTRAG_v1 §4, §6).
// Reads /uix/manifest, loads the files of the active shell and of every usable tool, builds the registry the shell asks
// ("who handles a task?"), connects the one event stream to the bus, and starts the shell. Nothing is bundled: these are
// classic <script> and <link> elements, added in order, so a broken module is a named error and not a blank screen.
// Classic script: defines window.sedraLoader; desk.html calls boot().

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  // Der Kern-Zugang des Loaders: beim Laden übernommen, danach ist die globale Kopie weg (Stufe A)
  const kern = root.sedraApi;
  delete root.sedraApi;

  function addScript(src){
    return new Promise((ok, bad)=>{
      const s = document.createElement('script');
      s.src = src; s.async = false;
      s.onload = ()=>ok(src);
      s.onerror = ()=>bad(new Error('Datei lädt nicht: ' + src));
      document.head.append(s);
    });
  }

  function addStyle(href){
    const l = document.createElement('link');
    l.rel = 'stylesheet'; l.href = href;
    document.head.append(l);
  }

  // Nachtrag N1 (Spec 4, G2-S4-03): ein Eintrag in `handles` ist der Typ (alle Objekte des Typs, wie bisher) oder trägt einen Zusatz:
  //   typ:alle  nur die Sammlung (ID `alle`)
  //   typ:*     jedes Einzelobjekt (weder ID `alle` noch `collection: true`)
  //   typ:<id>  genau dieses Objekt (z. B. agent:rollen)
  // Rein, node prüft es. Ein Manifest ohne Zusatz behält seine Bedeutung.
  function handleType(entry){
    const s = String(entry || '');
    const at = s.indexOf(':');
    return at < 0 ? s : s.slice(0, at);
  }

  function handlesMatch(entry, object){
    if(typeof entry !== 'string' || !object || !object.type) return false;
    const at = entry.indexOf(':');
    if((at < 0 ? entry : entry.slice(0, at)) !== object.type) return false;
    if(at < 0) return true;
    const want = entry.slice(at + 1);
    const id = object.id === undefined || object.id === null ? '' : String(object.id);
    if(want === 'alle') return id === 'alle';
    if(want === '*') return id !== 'alle' && !object.collection;
    return id === want;
  }

  // the registry a shell gets: which tool draws which object type, which instruments sit in the strip
  function makeRegistry(entries){
    const byId = new Map(entries.map(e=>[e.manifest.id, e]));
    const objectTools = ()=>entries.filter(e=>e.manifest.kind === 'object');
    return {
      get: id=>(byId.get(id) || {}).mod,
      manifest: id=>(byId.get(id) || {}).manifest,
      all: ()=>entries.map(e=>e.manifest),
      byKind: kind=>entries.filter(e=>e.manifest.kind === kind).map(e=>e.manifest),
      // ohne Objekt: jedes Werkzeug, das den Typ in irgendeiner Form handelt
      for: type=>objectTools().filter(e=>(e.manifest.handles || []).some(h=>handleType(h) === type)).map(e=>e.manifest),
      // mit Objekt (N1): nur die Werkzeuge, deren Eintrag zu genau diesem Objekt passt
      forObject: object=>objectTools().filter(e=>(e.manifest.handles || []).some(h=>handlesMatch(h, object))).map(e=>e.manifest),
      mod: id=>(byId.get(id) || {}).mod
    };
  }

  // the context one tool instance gets (§4): its own api(), its own bus, the object it draws, and the two things the shell offers it
  // what a shell must hand every tool (§4): a way to open, to notify, to decide. A shell that hands something else breaks every
  // tool silently – the Cockpit did exactly that for two builds (dock.js passed its api function). So the loader checks.
  const SHELL_API = ['open', 'notify', 'decide'];
  function checkShellApi(shell, manifest, say){
    const missing = SHELL_API.filter(name=>!shell || typeof shell[name] !== 'function');
    if(missing.length && say) say('Shell', new Error('Die Shell gibt dem Werkzeug ' + manifest.id + ' keine vollständige Shell-API: ' + missing.join(', ') + ' fehlt'));
    return !missing.length;
  }

  function makeContext(manifest, object, bus, shell, say, registry){
    checkShellApi(shell, manifest, say);
    // Freigaben erteilt nur der Kern (Entscheidung 2026-10-19): ein Werkzeug außerhalb des Pakets bekommt die Shell ohne decide
    const shellFuer = manifest.trust === 'CORE' ? shell : Object.freeze(Object.assign({}, shell, {decide: ()=>{ throw new Error('Freigaben erteilt nur der Kern, nicht ein Modul.'); }}));
    const ctx = {object: object || null, api: kern.forModule({kind: 'tool', id: manifest.id}),
                 bus: null, tokens: getComputedStyle(document.documentElement), shell: shellFuer, manifest, _offs: []};     // Härtung 30.10. (HU-L16): die Sperre gilt wirklich
    const own = bus.forModule((manifest.events || {}).emits || []);
    ctx.bus = {emit: own.emit, on: (name, fn)=>{ const off = own.on(name, fn); ctx._offs.push(off); return off; }};
    // Vertrag 1.1 (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §3, §10.3): drei Gedächtnisse je Werkzeug und Objekt. Sitzung und Ablage nur, wenn
    // das Manifest sie nennt – sonst eine Attrappe, die nichts behält. Das Werkzeug fragt nie, wo es läuft.
    const L = root.sedraLifecycle, g = L.gedaechtnisVon(manifest);
    ctx.memo = L.memoFuer(manifest.id, object);
    ctx.sitzung = L.sitzungFuer(manifest.id, object, g.indexOf('sitzung') >= 0, undefined, say);
    ctx.ablage = L.ablageFuer(manifest.id, object, g.indexOf('ablage') >= 0, ctx.api);
    // Vertrag Nachtrag N9 (Härtung E4, 30.10.): ein Werkzeug bettet ein anderes nur über die Laufzeit ein – mit dessen eigener
    // Kennung (API-Allowlist, emits) und eigenem Gedächtnis; abgebaut mit dem Einbettenden. Kein `root.sedra.tools.get` mehr.
    ctx._eingebettet = [];
    ctx.einbetten = (id, el, objekt)=>{
      if(!registry) throw new Error('einbetten_ohne_laufzeit');
      const man = registry.all().find(t=>t.id === id);
      if(!man || man.kind === 'instrument' || man.trust !== 'CORE') throw new Error('einbetten_unbekannt:' + id);   // nur Paket-Werkzeuge; Nicht-CORE laufen im Rahmen
      const st = L.mountTool(registry.mod(id), el, makeContext(man, objekt === undefined ? object : objekt, bus, shell, say, registry), say);
      ctx._eingebettet.push(st);
      return {state: st, abbauen(){ const i = ctx._eingebettet.indexOf(st); if(i >= 0) ctx._eingebettet.splice(i, 1); L.unmountTool(st, say); }};
    };
    return ctx;
  }

  // the server's stream into the bus: every tool hears the same events, nobody polls (§10.4)
  function connectEvents(bus, onState){
    let source = null, tries = 0;
    function open(){
      source = kern.events();
      Object.keys(root.sedraBus.EVENTS).forEach(name=>{
        source.addEventListener(name, e=>{
          let data = {};
          try{ data = JSON.parse(e.data || '{}'); }catch(_err){}
          bus.emit(name, data);
        });
      });
      source.onopen = ()=>{ tries = 0; if(onState) onState('verbunden'); };
      source.onerror = ()=>{
        if(onState) onState('getrennt');
        source.close();
        tries += 1;
        if(!geschlossen) timer = setTimeout(open, Math.min(30000, 1000 * Math.pow(2, Math.min(tries, 5))));      // the server may be restarting: back off, keep trying
      };
    }
    let timer = null, geschlossen = false;                 // Härtung 30.10. (HU-L13): closeEvents räumt auch den geplanten Neuaufbau
    open();
    return ()=>{ geschlossen = true; if(timer) clearTimeout(timer); if(source) source.close(); };
  }

  async function boot(onProblem){
    const say = onProblem || ((where, err)=>console.warn('[uix]', where, err));
    const bus = root.sedraBus.makeBus((name, why)=>say('Bus', new Error(name + ': ' + why)));
    const manifest = await kern.api('/uix/manifest');
    if(!manifest || typeof manifest !== 'object') throw new Error('Das Manifest der Oberfläche ist nicht lesbar – uix.yaml prüfen.');
    if(!manifest.shell) throw new Error('Keine Shell verfügbar: ' + ((manifest.rejected || []).map(r=>r.id + ' (' + (r.reasons || []).join(', ') + ')').join('; ') || 'uix.yaml prüfen'));
    if(!Array.isArray(manifest.tools)) throw new Error('Das Manifest nennt keine Werkzeuge – uix.yaml prüfen.');     // Härtung 30.10. (HU-L14): ein deutscher Satz statt TypeError
    (manifest.rejected || []).forEach(r=>say('Modul abgelehnt', new Error(r.kind + ' ' + r.id + ': ' + (r.reasons || []).join(', '))));

    // Stufe C: die Brücke zum Rahmen. Werkzeuge außerhalb des Pakets (nicht CORE) laufen in einem abgeschotteten iframe;
    // ihr Code kommt nie in diese Seite. Der Stellvertreter hier hält nur das Manifest und hängt den Rahmen ein.
    const bruecke = root.sedraBruecke.makeBruecke({kern, shell: null, bus, onProblem: (id, err)=>say('Rahmen ' + id, err instanceof Error ? err : new Error(String(err)))});
    root.sedraBruecke.einhaengen(bruecke);
    function frameMod(t){
      return {
        id: t.id, frame: true,
        mount(){}, unmount(){}, actions(){ return []; },
        mountFrame(el, ctx){
          const fenster = document.createElement('iframe');
          fenster.setAttribute('sandbox', 'allow-scripts');
          fenster.className = 'sx-rahmen';
          fenster.title = t.name || t.id;
          fenster.src = '/uix/frame/' + encodeURIComponent(t.id);
          el.replaceChildren(fenster);
          bruecke.register(fenster.contentWindow, t, ctx.shell);
          return {id: t.id, el, ctx, mod: this, mounted: true, ready: Promise.resolve(), abbau(){ bruecke.abmelden(fenster.contentWindow); }};
        }
      };
    }

    const entries = [];
    for(const t of manifest.tools){
      if(t.trust !== 'CORE'){ entries.push({manifest: t, mod: frameMod(t)}); continue; }
      try{
        (t.css || []).forEach(addStyle);
        for(const js of (t.js || [])) await addScript(js);
        const mod = root.sedra.tools.get(t.id);
        if(!mod) throw new Error('registerTool wurde nicht aufgerufen');
        entries.push({manifest: t, mod});
      }catch(err){ say('Werkzeug ' + t.id, err); }
    }
    manifest.shell.css.forEach(addStyle);
    for(const js of manifest.shell.js) await addScript(js);
    // eine Shell aus Vorgabe hat keinen eigenen Code: der Rahmen (ui/frame.js) registriert sie aus dem Manifest
    if(manifest.shell.frame && root.sedraFrame && !root.sedra.shells.get(manifest.shell.id)) root.sedraFrame.register(manifest.shell);
    const shellMod = root.sedra.shells.get(manifest.shell.id);
    if(!shellMod) throw new Error('Die Shell ' + manifest.shell.id + ' hat sich nicht registriert.');

    const registry = makeRegistry(entries);
    const ctx = {api: kern.forModule({kind: 'shell', id: manifest.shell.id}), bus, tools: registry, manifest,
                 makeContext: (m, object, shell)=>makeContext(m, object, bus, shell, say, registry), onProblem: say};
    await shellMod.start(ctx);
    // B6-G-04: der Umschalter gehört zur Seite – in jeder Shell derselbe Weg zur Übersicht, in eine andere Oberfläche, zu Darstellung und Schrift
    if(root.sedraWechsel) try{ root.sedraWechsel.mount(manifest); }catch(err){ say('Umschalter', err); }
    ctx.closeEvents = connectEvents(bus, state=>bus.emit('system.state', {state}));
    return ctx;
  }

  root.sedraLoader = {boot, makeRegistry, makeContext, connectEvents, checkShellApi, SHELL_API, handlesMatch, handleType};
  if(typeof module !== 'undefined' && module.exports) module.exports = {checkShellApi, SHELL_API, handlesMatch, handleType, makeRegistry};
})();
