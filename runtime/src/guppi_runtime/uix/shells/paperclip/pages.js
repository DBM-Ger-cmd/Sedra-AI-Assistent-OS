// Paperclip-Shell – die Seiten und ihr Verlauf (Entwurf D, Spec §5.2).
//
// Drei Arten von Seite:
//   dashboard   eine Komposition: vier Karten, in jeder ein Werkzeug zu einer anderen Sammlung
//   collection  eine Sammlung („alle Aufgaben“): das Werkstück-Werkzeug, volle Breite
//   object      ein einzelnes Objekt: Werkstück links, Nachweise als Karten in der Seitenleiste rechts
// Die Shell schreibt keine Zahl und keinen Inhalt selbst. Sie gibt Container und ruft `unmount`, wenn die Seite wechselt.
// `pageFor`, `pushHistory` und `DASHBOARD` sind rein und werden mit node geprüft.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const DASHBOARD = {type: 'dashboard', id: 'start', title: 'Dashboard'};
  // Die vier Karten des Dashboards: Objekte, keine Werkzeugnamen – wer sie zeichnet, sagt die Registrierung
  // Build 24 (Ticket B6-G-06): die Hinweise sagen, was die Karte ist, nicht wer der Nutzer ist. Das KI GateWay bleibt in seiner
  // eigenen Oberfläche (Klaus 15.10. 19:34).
  const CARDS = [
    {object: {type: 'decision', id: 'alle', title: 'Posteingang', collection: true}, title: 'Posteingang', hint: 'Freigaben und Grenzen – jede Antwort hier ist ein Audit-Ereignis'},
    {object: {type: 'agent', id: 'alle', title: 'Organigramm', collection: true}, title: 'Organigramm', hint: 'Rollen aus den Rezepten; wer gerade arbeitet'},
    {object: {type: 'task', id: 'alle', title: 'Issues', collection: true}, title: 'Issues', hint: 'dieselbe Liste wie „Aufgaben“ im Cockpit', wide: true}
  ];
  const MAX_HISTORY = 40;

  // Welche Art Seite ein Objekt bekommt (rein)
  function pageFor(object){
    if(!object || !object.type) return {kind: 'dashboard', object: DASHBOARD};
    if(object.type === 'dashboard') return {kind: 'dashboard', object: DASHBOARD};
    if(object.collection || object.id === 'alle') return {kind: 'collection', object};
    return {kind: 'object', object};
  }

  // Der Verlauf: dieselbe Seite nicht zweimal hintereinander, nie länger als MAX_HISTORY (rein)
  function pushHistory(history, object){
    const key = o=>o.type + ':' + o.id;
    const last = history[history.length - 1];
    if(last && key(last) === key(object)) return history;
    return history.concat([object]).slice(-MAX_HISTORY);
  }

  function makePages(host, shell){
    let history = [];
    let mounted = [];                 // die Werkzeuge der aktuellen Seite
    let current = null;

    function load(){
      try{ const raw = JSON.parse(localStorage.getItem('sedra.paperclip.history') || '[]'); history = Array.isArray(raw) ? raw : []; }
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
        const tools = shell.ctx.tools.for(c.object.type).filter(m=>m.slot !== 'nachweis');
        if(!tools.length) box.append(d().empty('Kein Werkzeug zeichnet „' + c.object.type + '“.'));
        else mountInto(box, tools[0], c.object);
        grid.append(box);
      });
      host.append(grid);
    }

    function collection(object){
      const tools = shell.ctx.tools.for(object.type).filter(m=>m.slot !== 'nachweis');
      const box = d().el('div', 'pc-single');
      if(!tools.length) box.append(d().empty('Für „' + (object.title || object.type) + '“ gibt es noch kein Werkzeug. Sobald eines gebaut ist, steht es hier – ohne eine Zeile an dieser Shell.'));
      else tools.forEach(m=>mountInto(box, m, object));
      host.append(box);
    }

    function single(object){
      const all = shell.ctx.tools.for(object.type);
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
      clear();
      shell.instruments.length = 0;
      current = page;
      if(page.kind === 'dashboard') dashboard();
      else if(page.kind === 'collection') collection(page.object);
      else single(page.object);
      if(!(options && options.silent)){ history = pushHistory(history, page.object); save(); }
      shell.onPage(page, history);
      // die Verbenzeile erst, wenn gezeichnet ist (Fund aus Build 8)
      Promise.all(mounted.map(s=>s.ready)).then(()=>shell.onPage(page, history)).catch(()=>{});
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
  if(typeof module !== 'undefined' && module.exports) module.exports = {pageFor, pushHistory, DASHBOARD, CARDS, MAX_HISTORY};
})();
