// Minimal-Shell – die Fenster (Entwurf E, SHELL_WERKZEUG_VERTRAG_v1 §4, Spec §1).
// Ein Fenster gehört zu genau einem Objekt. Der Inhalt kommt von den Werkzeugen, die diesen Typ zeichnen: zuerst das
// `inhalt`-Werkzeug, dahinter die `nachweis`-Werkzeuge als Umschalter – immer nur eines gemountet. Beim Umschalten wird das
// alte `unmount`-et, nicht versteckt: das ist die härtere Prüfung für den Vertrag.
//
// Die Shell greift nie in ein Werkzeug hinein (kein `refresh()` von außen). Nach einer Handlung frischt sie nur die Verbenzeile
// auf; die Daten holt sich jedes Werkzeug selbst, wenn das Ereignis über den Bus kommt.
// Die Geometrie ist rein und wird mit node geprüft: `placeBox` und `clampBox` kennen kein DOM.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const MIN_W = 320, MIN_H = 200, BAR_H = 28, SHELF_H = 86, MAX_RESTORE = 48;

  // Wo ein neues Fenster aufgeht: versetzt zum vorigen, aber nie aus dem Bild (rein)
  function placeBox(index, screen){
    const step = 28 * (index % 7);
    const w = Math.min(760, Math.max(MIN_W, Math.round(screen.w * 0.54)));
    const h = Math.min(560, Math.max(MIN_H, Math.round(screen.h * 0.62)));
    return clampBox({x: 60 + step, y: BAR_H + 14 + step, w, h}, screen);
  }

  // Ein Fenster bleibt im Bild: nie unter der Menüleiste, nie hinter der Ablage, nie breiter als der Bildschirm (rein)
  function clampBox(box, screen){
    const top = BAR_H + 4;
    const w = Math.max(MIN_W, Math.min(Math.round(box.w), Math.max(MIN_W, screen.w - 16)));
    const h = Math.max(MIN_H, Math.min(Math.round(box.h), Math.max(MIN_H, screen.h - top - SHELF_H)));
    return {w, h,
            x: Math.max(8, Math.min(Math.round(box.x), Math.max(8, screen.w - w - 8))),
            y: Math.max(top, Math.min(Math.round(box.y), Math.max(top, screen.h - h - SHELF_H)))};
  }

  // Werkstück zuerst, Nachweise dahinter – dieselbe Ordnung wie die zwei Spalten des Cockpits. Eine Sammlung („alle Aufgaben“)
  // bekommt keine Nachweise: „Live“ und „Kosten“ einer Liste gibt es nicht (Regel aus Build 8). Rein, mit node geprüft.
  function orderTools(manifests, object){
    const rank = m=>(m.slot === 'nachweis' ? 1 : 0);
    const useful = (object && object.collection) ? manifests.filter(m=>m.slot !== 'nachweis') : manifests;
    return useful.slice().sort((a, b)=>rank(a) - rank(b) || (a.order || 0) - (b.order || 0) || a.id.localeCompare(b.id));
  }

  function key(object){ return object.type + ':' + object.id; }

  function makeWindows(host, shell){
    const open = new Map();                       // key -> Fenster
    let top = 10, restoring = false;

    // Das gemerkte Layout wird **beim Bauen** gelesen, nicht erst beim Wiederherstellen: das Gesprächsfenster geht vorher auf,
    // und sein `save()` hätte den Stand sonst überschrieben, bevor ihn jemand liest (gefunden in der Abnahme von Shell E).
    const stored = (()=>{
      try{ const raw = JSON.parse(localStorage.getItem('sedra.minimal.windows') || '[]'); return Array.isArray(raw) ? raw : []; }
      catch(_e){ return []; }
    })();

    function screen(){ return {w: window.innerWidth, h: window.innerHeight}; }

    function save(){
      if(restoring) return;                       // während des Wiederherstellens wird nichts geschrieben
      const layout = [...open.values()].filter(w=>w.closable).map(w=>({object: w.object, box: w.box}));
      try{ localStorage.setItem('sedra.minimal.windows', JSON.stringify(layout)); }catch(_e){}
    }

    function restore(){
      if(!stored.length) return false;
      restoring = true;
      // Es kommt alles zurück, was offen war: ein Schreibtisch, der beim Neuladen heimlich Fenster schluckt, lügt über den
      // eigenen Zustand. MAX_RESTORE ist nur die Sperre gegen eine kaputte Datei.
      try{ stored.slice(0, MAX_RESTORE).forEach(entry=>{ if(entry && entry.object) openObject(entry.object, {box: entry.box}); }); }
      finally{ restoring = false; }
      save();
      return [...open.values()].some(w=>w.closable);
    }

    function focus(win){
      top += 1;
      win.el.style.zIndex = String(top);
      [...open.values()].forEach(w=>w.el.classList.toggle('on', w === win));
      shell.onWindowFocus(win.object);
    }

    function close(win){
      if(!win.closable) return;                   // das Gespräch bleibt: eine Shell ohne Eingabefeld gibt es nicht (Regel 1)
      unmountActive(win);
      win.el.remove();
      open.delete(key(win.object));
      save();
      shell.onWindowFocus(([...open.values()].pop() || {}).object || null);
    }

    function unmountActive(win){
      if(win.state) root.sedraLifecycle.unmountTool(win.state, shell.onProblem);
      win.state = null;
    }

    // Ziehen an der Titelleiste, Ziehen an der Ecke – mehr Fensterverwaltung braucht diese Shell nicht.
    function grip(win, node, mode){
      node.addEventListener('mousedown', start=>{
        if(start.button !== 0 || start.target.closest('button, [role="button"]')) return;
        start.preventDefault();
        focus(win);
        const from = {x: start.clientX, y: start.clientY, box: Object.assign({}, win.box)};
        const move = e=>{
          const dx = e.clientX - from.x, dy = e.clientY - from.y;
          win.box = clampBox(mode === 'move'
            ? {x: from.box.x + dx, y: from.box.y + dy, w: from.box.w, h: from.box.h}
            : {x: from.box.x, y: from.box.y, w: from.box.w + dx, h: from.box.h + dy}, screen());
          apply(win);
        };
        const stop = ()=>{ document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', stop); save(); };
        document.addEventListener('mousemove', move);
        document.addEventListener('mouseup', stop);
      });
    }

    function apply(win){
      win.el.style.left = win.box.x + 'px';
      win.el.style.top = win.box.y + 'px';
      win.el.style.width = win.box.w + 'px';
      win.el.style.height = win.box.h + 'px';
    }

    function buildSegments(win, manifests){
      const bar = d().el('div', 'sh-min-seg');
      win.segments = manifests.map(manifest=>{
        const tab = d().el('span', 'sh-min-seg-item', manifest.name || manifest.id);
        tab.dataset.tool = manifest.id;
        d().clickable(tab, ()=>show(win, manifest.id));
        bar.append(tab);
        return {manifest, tab};
      });
      return bar;
    }

    function show(win, toolId){
      const found = win.segments.find(s=>s.manifest.id === toolId) || win.segments[0];
      if(!found) return;
      unmountActive(win);
      win.body.replaceChildren();
      win.active = found.manifest.id;
      win.segments.forEach(s=>s.tab.classList.toggle('on', s === found));
      const slot = d().el('div', 'sh-min-tool');
      slot.dataset.tool = found.manifest.id;
      win.body.append(slot);
      const ctx = shell.ctx.makeContext(found.manifest, win.object, shell.shellApi);
      win.state = root.sedraLifecycle.mountTool(shell.ctx.tools.mod(found.manifest.id), slot, ctx, shell.onProblem);
      win.state.ready.then(()=>verbs(win)).catch(()=>verbs(win));
    }

    // Die Handlungen des Objekts, unten im Fenster – erst fragen, wenn das Werkzeug gezeichnet hat (Fund aus Build 8).
    function verbs(win){
      if(!win.state) return;
      win.verbs.replaceChildren();
      root.sedraLifecycle.actionsOf(win.state).forEach(action=>{
        win.verbs.append(d().button(action.label, async()=>{ await action.run(); verbs(win); }));
      });
    }

    function openObject(object, options){
      if(!object || !object.type || !object.id) return null;
      const opts = options || {};
      const existing = open.get(key(object));
      if(existing){ focus(existing); return existing; }
      // Normalerweise fragt die Shell die Registrierung, wer den Typ zeichnet. Das Gespräch ist der eine Fall, den der
      // Vertrag selbst benennt (kind: panel): dafür darf die Shell ein Werkzeug mitgeben.
      const manifests = orderTools(opts.manifests || shell.ctx.tools.forObject(object), object);     // N1: zu genau diesem Objekt
      const win = {object, box: clampBox(opts.box || placeBox(open.size, screen()), screen()),
                   segments: [], state: null, closable: opts.closable !== false};

      win.el = d().el('div', 'sh-min-win');
      win.el.dataset.object = key(object);
      const bar = d().el('div', 'sh-min-bar');
      if(win.closable){
        const dot = d().el('span', 'sh-min-close');
        dot.title = 'Fenster schließen';
        d().clickable(dot, ()=>close(win));
        bar.append(dot);
      }
      bar.append(d().el('b', null, object.title || object.type), d().el('small', null, object.type));
      win.body = d().el('div', 'sh-min-body');
      win.verbs = d().el('div', 'sh-min-verbs'); win.verbs.dataset.verbs = '';     // Vertragsmarke für die Abnahme
      const corner = d().el('div', 'sh-min-corner');
      win.el.append(bar);
      if(manifests.length > 1) win.el.append(buildSegments(win, manifests));
      else win.segments = manifests.map(manifest=>({manifest, tab: d().el('span')}));
      win.el.append(win.body, win.verbs, corner);
      host.append(win.el);
      apply(win);
      grip(win, bar, 'move');
      if(win.closable) grip(win, corner, 'resize');
      open.set(key(object), win);

      if(!manifests.length) win.body.append(d().empty('Kein Werkzeug zeichnet „' + object.type + '“.'));
      else show(win, manifests[0].id);
      focus(win);
      save();
      return win;
    }

    // Nach einem Ereignis: nur die Verbenzeile. Die Daten holt sich jedes Werkzeug selbst – es hört denselben Bus.
    function refreshVerbs(){ open.forEach(win=>verbs(win)); }
    function list(){ return [...open.values()].map(w=>w.object); }
    function front(){ const last = [...open.values()].sort((a, b)=>Number(a.el.style.zIndex) - Number(b.el.style.zIndex)).pop(); return last ? last.object : null; }

    function closeAll(){ [...open.values()].filter(w=>w.closable).forEach(close); }

    return {open: openObject, close, closeAll, list, front, restore, save, refreshVerbs, focus, windows: open};
  }

  root.sedraMinWindows = {makeWindows, placeBox, clampBox, orderTools, MIN_W, MIN_H, BAR_H, SHELF_H};
  if(typeof module !== 'undefined' && module.exports) module.exports = {placeBox, clampBox, orderTools, MIN_W, MIN_H, BAR_H, SHELF_H};
})();
