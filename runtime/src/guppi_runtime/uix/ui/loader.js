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

  // the registry a shell gets: which tool draws which object type, which instruments sit in the strip
  function makeRegistry(entries){
    const byId = new Map(entries.map(e=>[e.manifest.id, e]));
    return {
      get: id=>(byId.get(id) || {}).mod,
      manifest: id=>(byId.get(id) || {}).manifest,
      all: ()=>entries.map(e=>e.manifest),
      byKind: kind=>entries.filter(e=>e.manifest.kind === kind).map(e=>e.manifest),
      for: type=>entries.filter(e=>e.manifest.kind === 'object' && (e.manifest.handles || []).indexOf(type) >= 0).map(e=>e.manifest),
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

  function makeContext(manifest, object, bus, shell, say){
    checkShellApi(shell, manifest, say);
    // Freigaben erteilt nur der Kern (Entscheidung 2026-10-19): ein Werkzeug außerhalb des Pakets bekommt die Shell ohne decide
    const shellFuer = manifest.trust === 'CORE' ? shell : Object.freeze(Object.assign({}, shell, {decide: ()=>{ throw new Error('Freigaben erteilt nur der Kern, nicht ein Modul.'); }}));
    const ctx = {object: object || null, api: kern.forModule({kind: 'tool', id: manifest.id}),
                 bus: null, tokens: getComputedStyle(document.documentElement), shell, manifest, _offs: []};
    const own = bus.forModule((manifest.events || {}).emits || []);
    ctx.bus = {emit: own.emit, on: (name, fn)=>{ const off = own.on(name, fn); ctx._offs.push(off); return off; }};
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
        setTimeout(open, Math.min(30000, 1000 * Math.pow(2, Math.min(tries, 5))));      // the server may be restarting: back off, keep trying
      };
    }
    open();
    return ()=>{ if(source) source.close(); };
  }

  async function boot(onProblem){
    const say = onProblem || ((where, err)=>console.warn('[uix]', where, err));
    const bus = root.sedraBus.makeBus((name, why)=>say('Bus', new Error(name + ': ' + why)));
    const manifest = await kern.api('/uix/manifest');
    if(!manifest.shell) throw new Error('Keine Shell verfügbar: ' + ((manifest.rejected || []).map(r=>r.id + ' (' + r.reasons.join(', ') + ')').join('; ') || 'uix.yaml prüfen'));
    (manifest.rejected || []).forEach(r=>say('Modul abgelehnt', new Error(r.kind + ' ' + r.id + ': ' + r.reasons.join(', '))));

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
        t.css.forEach(addStyle);
        for(const js of t.js) await addScript(js);
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
                 makeContext: (m, object, shell)=>makeContext(m, object, bus, shell, say), onProblem: say};
    await shellMod.start(ctx);
    // B6-G-04: der Umschalter gehört zur Seite – in jeder Shell derselbe Weg zur Übersicht, in eine andere Oberfläche, zu Darstellung und Schrift
    if(root.sedraWechsel) try{ root.sedraWechsel.mount(manifest); }catch(err){ say('Umschalter', err); }
    ctx.closeEvents = connectEvents(bus, state=>bus.emit('system.state', {state}));
    return ctx;
  }

  root.sedraLoader = {boot, makeRegistry, makeContext, connectEvents, checkShellApi, SHELL_API};
  if(typeof module !== 'undefined' && module.exports) module.exports = {checkShellApi, SHELL_API};
})();
