// UI contract 1.0 – registration and lifecycle (SHELL_WERKZEUG_VERTRAG_v1 §4).
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
    }catch(err){ onError && onError(mod.id, err); }
    return state;
  }

  function unmountTool(state, onError){
    if(!state || !state.mounted) return;
    state.mounted = false;
    if(typeof state.abbau === 'function'){ try{ state.abbau(); }catch(_e){} }     // Stufe C: den Rahmen abmelden
    try{ state.mod.unmount(); }
    catch(err){ onError && onError(state.id, err); }
    try{ state.el.replaceChildren(); }catch(_e){}
    (state.ctx && state.ctx._offs || []).forEach(off=>{ try{ off(); }catch(_e){} });
  }

  // the actions of a tool in its current state, as the Werkbank row shows them (Cockpit rule 3)
  function actionsOf(state){
    if(!state || !state.mod.actions) return [];
    let list;
    try{ list = state.mod.actions(); }catch(_e){ return []; }
    return (Array.isArray(list) ? list : []).filter(a=>a && typeof a.label === 'string' && typeof a.run === 'function');
  }

  root.sedra = {registerTool, registerShell, tools, shells};
  root.sedraLifecycle = {checkModule, mountTool, unmountTool, actionsOf, tools, shells};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraLifecycle;
})();
