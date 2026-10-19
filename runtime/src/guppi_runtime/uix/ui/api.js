// UI contract 1.0 – the one way to the runtime (SHELL_WERKZEUG_VERTRAG_v1 §2, §6).
// A tool never calls fetch itself: it uses the ctx.api() the shell hands it, which adds the module header the server checks
// against the manifest's allowlist. Errors arrive in German, as sentences the Captain can act on.
// Classic script: it defines window.sedraApi; load order is set in desk.html. The loader takes this object at start and removes
// the global copy, so no module can reach the runtime with the Captain's rights (Stufe A, Entscheidung 2026-10-19).
// Honest limit: code on the same page can still read the token from the address; the real boundary is isolation (Stufe C).

(function(){
  const TOKEN = decodeURIComponent((location.hash || '').replace(/^#/, ''));

  function message(res, data){
    if(data && data.message && res.status === 403 && data.error === 'tool_route_not_allowed') return data.message;
    if(res.status === 403) return 'Zugriff verweigert (Token oder Herkunft stimmt nicht; Fenster über START_SEDRA.bat öffnen).';
    if(res.status === 404) return 'Diesen Weg gibt es nicht: ' + res.url.replace(location.origin, '');
    return (data && data.message) || ('HTTP ' + res.status);
  }

  // one call; `module` is {kind:'tool'|'shell', id} and sets the header the allowlist is checked against
  async function call(path, options, module){
    const headers = Object.assign({'X-GUPPI-Token': TOKEN}, options.headers || {});
    if(module && module.id) headers[module.kind === 'shell' ? 'X-SEDRA-Shell' : 'X-SEDRA-Tool'] = module.id;
    if(options.body !== undefined && typeof options.body !== 'string'){ options = Object.assign({}, options, {body: JSON.stringify(options.body)}); }
    if(options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    let res;
    try{ res = await fetch(path, Object.assign({}, options, {headers})); }
    catch(_err){ throw new Error('Keine Verbindung zur Runtime (Server beendet oder Fenster neu starten).'); }
    const data = await res.json().catch(()=>({}));
    if(!res.ok) throw new Error(message(res, data));
    return data;
  }

  // the api() a module gets: api(path) reads, api(path,{method:'POST',body:{…}}) writes
  function forModule(module){
    const fn = (path, options)=>call(path, options || {}, module);
    fn.module = module || null;
    return fn;
  }

  // Der Event-Strom braucht den Token in der Adresse. Modulen gibt es nur das Ergebnis, nicht den Token.
  function events(){ return new EventSource('/api/events?token=' + encodeURIComponent(TOKEN)); }

  window.sedraApi = {forModule, api: forModule(null), events};
})();
