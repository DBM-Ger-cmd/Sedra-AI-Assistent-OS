// Paperclip-Shell – die Seiten und ihr Verlauf (Entwurf D, Spec §5.2).
//
// Vier Arten (Spec 4, D4.1):
//   dashboard   eine Komposition: vier Karten, in jeder ein Werkzeug zu einer anderen Sammlung
//   collection  eine Sammlung („alle Aufgaben“): das Werkstück-Werkzeug, volle Breite
//   object      ein einzelnes Objekt: Werkstück links, Nachweise als Karten in der Seitenleiste rechts
//   window      ein einzelner Agent: keine Seite – die Shell öffnet sein Fenster im Stapel (windows.js), die Seite bleibt stehen
// Wer ein Objekt zeichnet, sagt die Registrierung über das ganze Objekt (`forObject`, Nachtrag N1), nicht nur über den Typ.
// Die Shell schreibt keine Zahl und keinen Inhalt selbst. Sie gibt Container und ruft `unmount`, wenn die Seite wechselt.
// `pageFor`, `pushHistory` und `DASHBOARD` sind rein und werden mit node geprüft.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const DASHBOARD = {type: 'dashboard', id: 'start', title: 'Dashboard'};
  // Die vier Karten des Dashboards: Objekte, keine Werkzeugnamen – wer sie zeichnet, sagt die Registrierung
  // Build 24 (Ticket B6-G-06): die Hinweise sagen, was die Karte ist, nicht wer der Nutzer ist. Das KI GateWay bleibt in seiner
  // eigenen Oberfläche (Klaus 15.10. 19:34).
  // 19.10.2026: die Ziele zuerst – ein Ziel ist ein Vorhaben mit Stufen (Werkflow), die Firma arbeitet daran entlang
  const CARDS = [
    {object: {type: 'intent', id: 'alle', title: 'Ziele', collection: true, kompakt: true}, title: 'Ziele', hint: 'Vorhaben mit Stufen – jede Stufe wird eine Aufgabe (Issue); neue Ziele unter „Ziele“', wide: true},
    {object: {type: 'decision', id: 'alle', title: 'Posteingang', collection: true}, title: 'Posteingang', hint: 'Freigaben und Grenzen – jede Antwort hier ist ein Audit-Ereignis'},
    {object: {type: 'agent', id: 'alle', title: 'Organigramm', collection: true, kompakt: true}, title: 'Organigramm', hint: 'das Team: Vorgesetzte, Rolle, Budget'},
    // Issues: der Desk-Typ `issue`, sobald ein Werkzeug ihn zeichnet; bis dahin die Missionen (nav.js, issuesTarget)
    {object: {type: 'task', id: 'alle', title: 'Issues', collection: true}, issues: true, title: 'Issues', hint: 'die Aufgaben des Teams', wide: true}
  ];
  const MAX_HISTORY = 40;

  // Welche Art Seite ein Objekt bekommt (rein)
  function pageFor(object){
    if(!object || !object.type) return {kind: 'dashboard', object: DASHBOARD};
    if(object.type === 'dashboard') return {kind: 'dashboard', object: DASHBOARD};
    if(object.collection || object.id === 'alle') return {kind: 'collection', object};
    if(object.type === 'agent') return {kind: 'window', object};       // agent:alle und agent:rollen sind oben schon Sammlungen
    return {kind: 'object', object};
  }

  // Der Verlauf: dieselbe Seite nicht zweimal hintereinander, nie länger als MAX_HISTORY (rein).
  // Die Ansicht gehört zum Schlüssel (N5): der Wechsel Liste/Board ist einen Schritt zurück wert.
  // Härtung 30.10. (HU-S6): nur saubere Seiten aus dem Browser-Speicher (bekannte Felder, Typ nach Muster, ID Text oder Zahl)
  function sanitizeHistory(raw){
    if(!Array.isArray(raw)) return [];
    const text = v=>typeof v === 'string' || typeof v === 'number';
    return raw.filter(o=>o && typeof o === 'object' && typeof o.type === 'string' && /^[a-z][a-z0-9_-]{0,30}$/.test(o.type) && text(o.id))
      .map(o=>{ const n = {type: o.type, id: o.id}; ['title', 'ansicht', 'view'].forEach(f=>{ if(text(o[f])) n[f] = o[f]; }); if(typeof o.collection === 'boolean') n.collection = o.collection; return n; })
      .slice(-MAX_HISTORY);
  }

  function pushHistory(history, object){
    const key = o=>o.type + ':' + o.id + (o.view ? ':' + o.view : '');
    const last = history[history.length - 1];
    if(last && key(last) === key(object)) return history;
    return history.concat([object]).slice(-MAX_HISTORY);
  }

  function makePages(host, shell){
    let history = [];
    let mounted = [];                 // die Werkzeuge der aktuellen Seite
    let current = null;

    function load(){
      try{ history = sanitizeHistory(JSON.parse(localStorage.getItem('sedra.paperclip.history') || '[]')); }      // Härtung 30.10. (HU-S6)
      catch(_e){ history = []; }
    }
    function save(){
      try{ localStorage.setItem('sedra.paperclip.history', JSON.stringify(history)); }catch(_e){}
    }

    function clear(){
      mounted.forEach(s=>root.sedraLifecycle.unmountTool(s, shell.onProblem));
      mounted = [];
      host.replaceChildren();
    }

    // Ein Container für ein Werkzeug, mit Kontext – der eine Weg, wie ein Werkzeug auf eine Seite kommt
    function mountInto(container, manifest, object){
      const slot = d().el('div', 'pc-tool');
      slot.dataset.tool = manifest.id;
      container.append(slot);
      const ctx = shell.ctx.makeContext(manifest, object, shell.shellApi);
      const state = root.sedraLifecycle.mountTool(shell.ctx.tools.mod(manifest.id), slot, ctx, shell.onProblem);
      mounted.push(state);
      return state;
    }

    function card(title, hint, wide){
      const box = d().el('section', 'pc-card' + (wide ? ' wide' : ''));
      const head = d().el('h3');
      head.append(d().el('span', null, title));
      if(hint) head.append(d().el('small', null, hint));
      box.append(head);
      return box;
    }

    function dashboard(){
      const grid = d().el('div', 'pc-grid');
      // Kennzahlen: die Instrumente, dieselben wie in der Leiste des Cockpits – nur als Kacheln
      const kpis = d().el('div', 'pc-kpis');
      shell.ctx.tools.byKind('instrument').forEach(manifest=>{
        const tile = d().el('div', 'pc-kpi');
        tile.dataset.tool = manifest.id;
        kpis.append(tile);
        const ctx = shell.ctx.makeContext(manifest, null, shell.shellApi);
        const state = root.sedraLifecycle.mountTool(shell.ctx.tools.mod(manifest.id), tile, ctx, shell.onProblem);
        mounted.push(state);
        shell.instruments.push({manifest, mod: shell.ctx.tools.mod(manifest.id), state});
      });
      grid.append(kpis);
      CARDS.forEach(c=>{
        const box = card(c.title, c.hint, c.wide);
        const object = c.issues ? Object.assign({}, root.sedraPcNav.issuesTarget(shell.ctx.tools), {kompakt: true}) : c.object;
        const tools = shell.ctx.tools.forObject(object).filter(m=>m.slot !== 'nachweis');
        if(!tools.length) box.append(d().empty('Kein Werkzeug zeichnet „' + object.type + '“.'));
        else mountInto(box, tools[0], object);
        grid.append(box);
      });
      host.append(grid);
    }

    function collection(object){
      const tools = shell.ctx.tools.forObject(object).filter(m=>m.slot !== 'nachweis');
      const box = d().el('div', 'pc-single');
      if(!tools.length) box.append(d().empty('Für „' + (object.title || object.type) + '“ gibt es noch kein Werkzeug. Sobald eines gebaut ist, steht es hier – ohne eine Zeile an dieser Shell.'));
      else tools.forEach(m=>mountInto(box, m, object));
      host.append(box);
    }

    function single(object){
      const all = shell.ctx.tools.forObject(object);
      const main = all.filter(m=>m.slot !== 'nachweis'), side = all.filter(m=>m.slot === 'nachweis');
      const layout = d().el('div', 'pc-object' + (side.length ? ' with-side' : ''));
      const left = d().el('div', 'pc-main');
      if(!main.length) left.append(d().empty('Kein Werkzeug zeichnet „' + object.type + '“.'));
      main.forEach(m=>mountInto(left, m, object));
      layout.append(left);
      if(side.length){
        const right = d().el('aside', 'pc-side'); right.dataset.slot = 'nachweis';
        side.forEach(m=>{
          const box = card(m.name || m.id, '');
          mountInto(box, m, object);
          right.append(box);
        });
        layout.append(right);
      }
      host.append(layout);
    }

    function open(object, options){
      const page = pageFor(object);
      if(page.kind === 'window') return shell.windows.open(page.object);      // keine Seite: das Fenster im Stapel, die Seite bleibt
      clear();
      shell.instruments.length = 0;
      current = page;
      if(page.kind === 'dashboard') dashboard();
      else if(page.kind === 'collection') collection(page.object);
      else single(page.object);
      if(!(options && options.silent)){ history = pushHistory(history, page.object); save(); }
      shell.onPage(page, history);
      // die Verbenzeile erst, wenn gezeichnet ist (Fund aus Build 8) – und nur, wenn die Seite dann noch vorn ist: eine langsame
      // Seite (Kosten) setzte sonst die Markierung der Navigation zurück, nachdem schon die nächste offen war (26.10.2026)
      Promise.all(mounted.map(s=>s.ready)).then(()=>{ if(current === page) shell.onPage(page, history); }).catch(()=>{});
      return page;
    }

    function back(){
      if(history.length < 2) return open(DASHBOARD);
      history = history.slice(0, -1);
      save();
      return open(history[history.length - 1], {silent: true});
    }

    function restore(){
      load();
      history = history.filter(o=>o && pageFor(o).kind !== 'window');    // ein Fenster ist keine Seite
      if(!history.length) return false;
      open(history[history.length - 1], {silent: true});
      return true;
    }

    // die Handlungen der Seite: die Verben des Werkstücks (nicht der Nachweise, nicht der Kacheln)
    function actions(){
      if(!current || current.kind === 'dashboard') return [];
      const out = [];
      mounted.forEach(s=>{ if(s.el.classList.contains('pc-tool') && !s.el.closest('.pc-side')) root.sedraLifecycle.actionsOf(s).forEach(a=>out.push(a)); });
      return out;
    }

    return {open, back, restore, actions, current: ()=>current, history: ()=>history.slice(), DASHBOARD};
  }

  root.sedraPcPages = {makePages, pageFor, pushHistory, DASHBOARD, CARDS, MAX_HISTORY};
  if(typeof module !== 'undefined' && module.exports) module.exports = {sanitizeHistory, pageFor, pushHistory, DASHBOARD, CARDS, MAX_HISTORY};
})();
