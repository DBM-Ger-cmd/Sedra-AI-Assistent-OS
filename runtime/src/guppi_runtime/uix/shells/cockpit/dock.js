// Cockpit shell – the dock (COCKPIT_MODUL_v1 §3a: a small system of its own, part of the shell, replaceable; no tool knows it).
// Tabs per object, split left/right or top/bottom, drag a tab to another group, layout as JSON in this browser. No popout.
// A group holds panes; a pane is one object with the tools that handle it. The dock gives a container and asks for nothing else.
// Classic script: part of the cockpit shell; registerShell lives in shell.js.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // ---- the pure part (node tests it): a layout is a tree of groups; panes carry {type, id, title}
  function newLayout(){ return {kind: 'group', id: 'g1', panes: [], active: null}; }

  function eachGroup(node, fn){
    if(!node) return;
    if(node.kind === 'group'){ fn(node); return; }
    (node.children || []).forEach(c=>eachGroup(c, fn));
  }

  function findGroup(node, id){
    let found = null;
    eachGroup(node, g=>{ if(g.id === id) found = g; });
    return found;
  }

  function firstGroup(node){
    let found = null;
    eachGroup(node, g=>{ if(!found) found = g; });
    return found;
  }

  function paneKey(object){ return object.type + ':' + object.id; }

  // put an object into a group; an object that is already open is only brought to the front (rule 4: tabs carry names)
  function addPane(layout, object, groupId){
    const key = paneKey(object);
    let where = null;
    eachGroup(layout, g=>{ if(!where && (g.panes || []).some(p=>p.key === key)) where = g; });
    if(where){ where.active = key; return {group: where, created: false}; }
    const group = (groupId && findGroup(layout, groupId)) || firstGroup(layout);
    // ansicht: welche Ansicht eines Werkzeugs gezeigt wird (das GateWay im Baum); imBaum: das Menü steht schon im Baum
    group.panes.push({key, object: {type: object.type, id: object.id, title: object.title || object.id, collection: !!object.collection,
                                    ansicht: object.ansicht || undefined, imBaum: !!object.imBaum || undefined}});
    group.active = key;
    return {group, created: true};
  }

  function removePane(layout, key){
    let gone = null;
    eachGroup(layout, g=>{
      const i = (g.panes || []).findIndex(p=>p.key === key);
      if(i < 0) return;
      gone = g.panes.splice(i, 1)[0];
      if(g.active === key) g.active = (g.panes[i] || g.panes[i - 1] || {}).key || null;
    });
    return gone;
  }

  // a split: the group becomes a row (or column) with itself and a new empty group next to it
  function splitGroup(layout, groupId, direction, nextId){
    const target = findGroup(layout, groupId);
    if(!target) return layout;
    const moved = {kind: 'group', id: target.id, panes: target.panes, active: target.active};
    const fresh = {kind: 'group', id: nextId, panes: [], active: null};
    const split = {kind: 'split', direction, children: [moved, fresh]};
    if(layout === target) return split;
    eachSplit(layout, s=>{
      const i = s.children.indexOf(target);
      if(i >= 0) s.children[i] = split;
    });
    return layout;
  }

  function eachSplit(node, fn){
    if(!node || node.kind !== 'split') return;
    fn(node);
    node.children.forEach(c=>eachSplit(c, fn));
  }

  // a group that lost its last pane disappears, unless it is the only one left
  function prune(layout){
    if(layout.kind !== 'split') return layout;
    layout.children = layout.children.map(prune).filter(c=>c.kind === 'split' || (c.panes || []).length);
    if(!layout.children.length) return newLayout();
    return layout.children.length === 1 ? layout.children[0] : layout;
  }

  function movePane(layout, key, toGroupId){
    const pane = removePane(layout, key);
    const target = findGroup(layout, toGroupId);
    if(!pane || !target) return false;
    target.panes.push(pane);
    target.active = key;
    return true;
  }

  const pure = {newLayout, addPane, removePane, splitGroup, movePane, prune, findGroup, firstGroup, paneKey, eachGroup};

  // ---- the browser part
  function makeDock(host, shell){
    const state = {layout: newLayout(), mounted: new Map(), nextId: 2};     // key -> [{tool, state}]
    const saveKey = 'sedra.cockpit.layout';

    function save(){
      try{ localStorage.setItem(saveKey, JSON.stringify({layout: strip(state.layout), v: 1})); }catch(_e){}
    }

    // what is remembered: which objects were open where, never the data inside them
    function strip(node){
      if(node.kind === 'split') return {kind: 'split', direction: node.direction, children: node.children.map(strip)};
      return {kind: 'group', id: node.id, active: node.active, panes: (node.panes || []).map(p=>({key: p.key, object: p.object}))};
    }

    function restore(){
      let saved = null;
      try{ saved = JSON.parse(localStorage.getItem(saveKey) || 'null'); }catch(_e){}
      if(!saved || !saved.layout) return false;
      state.layout = saved.layout;
      let max = 1;
      eachGroup(state.layout, g=>{ max = Math.max(max, parseInt(String(g.id).replace('g', ''), 10) || 1); });
      state.nextId = max + 1;
      return true;
    }

    function open(object, groupId){
      // Dasselbe Objekt, andere Ansicht (z. B. das GateWay im Baum): das Fenster bleibt, die Ansicht wird neu gezeichnet
      const key = paneKey(object);
      let alt = null;
      eachGroup(state.layout, g=>(g.panes || []).forEach(p=>{ if(p.key === key) alt = p; }));
      if(alt && object.ansicht !== undefined && alt.object.ansicht !== object.ansicht){
        unmountPane(key);
        alt.object = Object.assign({}, alt.object, {ansicht: object.ansicht, imBaum: !!object.imBaum || undefined, title: object.title || alt.object.title});
      }
      const {group} = addPane(state.layout, object, groupId);
      render();
      save();
      return group;
    }

    function close(key){
      unmountPane(key);
      removePane(state.layout, key);
      state.layout = prune(state.layout);
      render(); save();
    }

    function unmountPane(key){
      (state.mounted.get(key) || []).forEach(entry=>root.sedraLifecycle.unmountTool(entry, shell.onProblem));
      state.mounted.delete(key);
    }

    function activeObject(){
      const g = firstActiveGroup();
      const pane = g && (g.panes || []).find(p=>p.key === g.active);
      return pane ? pane.object : null;
    }

    function firstActiveGroup(){
      let g = findGroup(state.layout, state.focusGroup) || firstGroup(state.layout);
      return g;
    }

    // the tools that draw this object, in the order of the manifest
    function toolsFor(object){
      const list = shell.ctx.tools.for(object.type);
      return list.length ? list : [];
    }

    // Werkstück links, Nachweise rechts (COCKPIT_MODUL_v1 §1). Welches Werkzeug wohin gehört, sagt sein Manifest (`slot`);
    // ein Werkzeug ohne Angabe ist Inhalt. Gibt es keine Nachweise, bleibt es bei einer Spalte – keine leere Hälfte.
    function renderPaneBody(box, pane){
      const tools = toolsFor(pane.object);
      if(!tools.length){
        box.append(d().empty('Für „' + pane.object.type + '“ ist kein Werkzeug installiert. In der Bibliothek steht, was es gibt.'));
        return;
      }
      const content = tools.filter(t=>(t.slot || 'inhalt') !== 'nachweis');
      // Nachweise gehören an ein Werkstück, nicht an eine Liste: eine Sammlung („alle Aufgaben“) trägt `collection` und bekommt keine.
      // Das GateWay hat seinen Nachweis im Menü links (Schutz-Ansichten), daneben keine zweite Spalte.
      const evidence = (pane.object.collection || pane.object.type === 'gateway') ? [] : tools.filter(t=>(t.slot || 'inhalt') === 'nachweis');
      let left = box, right = null;
      if(content.length && evidence.length){
        const split = d().el('div', 'dk-pane');
        left = d().el('div', 'dk-pane-col');
        right = d().el('div', 'dk-pane-col dk-pane-evidence'); right.dataset.slot = 'nachweis';     // Vertragsmarke für die Abnahme jeder Shell
        split.append(left, right);
        box.append(split);
      }
      const entries = [];
      const mount = (manifest, host)=>{
        const slot = d().el('div', 'dk-tool');
        slot.dataset.tool = manifest.id;
        host.append(slot);
        // `shell.shellApi`, nicht `shell.api`: bis zum 15.10.2026 bekam jedes Werkzeug an der Werkbank die api-Funktion der Shell
        // als „Shell“ – `ctx.shell.open()` war damit in jedem Reiter tot, ohne dass ein Test es sah. Der Loader prüft das jetzt.
        const ctx = shell.ctx.makeContext(manifest, pane.object, shell.shellApi);
        entries.push(root.sedraLifecycle.mountTool(shell.ctx.tools.mod(manifest.id), slot, ctx, shell.onProblem));
      };
      content.forEach(m=>mount(m, left));
      evidence.forEach(m=>mount(m, right || box));
      state.mounted.set(pane.key, entries);
      // Die Verben erst zeigen, wenn die Werkzeuge gezeichnet haben – sonst fragt die Zeile, bevor es etwas zu antworten gibt.
      Promise.all(entries.map(e=>e.ready)).then(()=>{ if(state.mounted.get(pane.key) === entries) refreshVerbs(); });
    }

    // One rule, so nothing is mounted twice: every redraw unmounts what lives in the dock and mounts the visible panes again.
    // A tool therefore has to survive being unmounted – which is exactly what the contract asks of it (§4) and what uix_check measures.
    // the state line and the verbs; a tool that offers none keeps the row empty rather than showing something borrowed
    // Die Zeile trägt die Handlungen des Werkstücks (Regel 3) – nicht die Hausarbeiten der Nachweise, die ihre eigenen Knöpfe haben.
    function renderVerbs(host, pane){
      const entries = (state.mounted.get(pane.key) || []).filter(e=>((shell.ctx.tools.manifest(e.id) || {}).slot || 'inhalt') !== 'nachweis');
      const actions = [];
      entries.forEach(entry=>root.sedraLifecycle.actionsOf(entry).forEach(a=>actions.push(a)));
      host.replaceChildren(d().el('small', 's-muted', pane.object.title));
      actions.forEach((a, i)=>{
        const b = d().button(a.label, ()=>Promise.resolve(a.run()), i === 0 && actions.length > 1 ? 'p' : '');
        if(i === 0) b.style.marginLeft = 'auto';
        host.append(b);
      });
    }

    function render(){
      Array.from(state.mounted.keys()).forEach(unmountPane);
      host.replaceChildren(renderNode(state.layout));
      shell.onDockChanged && shell.onDockChanged(activeObject());
    }

    function renderNode(node){
      if(node.kind === 'split'){
        const box = d().el('div', 'dk-split dk-' + node.direction);
        node.children.forEach(c=>box.append(renderNode(c)));
        return box;
      }
      return renderGroup(node);
    }

    function renderGroup(group){
      const box = d().el('div', 'dk-group');
      const bar = d().el('div', 'dk-tabs');
      (group.panes || []).forEach(pane=>{
        const tab = d().el('div', 'dk-tab' + (pane.key === group.active ? ' on' : ''));
        tab.draggable = true;
        tab.append(d().el('span', null, pane.object.title));
        tab.title = pane.object.title;                       // der volle Name, wenn der Reiter ihn kürzt
        tab.onauxclick = e=>{ if(e.button === 1){ e.preventDefault(); close(pane.key); } };   // mittlere Maustaste schließt, wie im Browser
        const x = d().el('button', 'dk-x', '✕');
        x.title = 'Schließen'; x.setAttribute('aria-label', 'Reiter schließen: ' + pane.object.title);
        x.onclick = e=>{ e.stopPropagation(); close(pane.key); };
        tab.append(x);
        d().clickable(tab, ()=>{ group.active = pane.key; state.focusGroup = group.id; render(); save(); });
        tab.ondragstart = e=>{ e.dataTransfer.setData('text/sedra-pane', pane.key); e.dataTransfer.effectAllowed = 'move'; };
        bar.append(tab);
      });
      // „＋ Neu“ und „Teilen“ scrollen nicht mit: sie gehören zur Werkbank, nicht zur Reihe der Reiter.
      const fixed = d().el('div', 'dk-bar-fixed');
      const plus = d().el('button', 's-btn dk-new', '＋ Neu ▾');
      plus.title = 'Vorhaben · Projekt · Datei öffnen · Modell hinzufügen';
      plus.onclick = e=>{ e.stopPropagation(); shell.openNew(plus); };
      fixed.append(plus);
      const split = d().el('button', 'dk-split-btn', '⊞');
      split.title = 'Teilen: der Reiter bekommt eine zweite Spalte';
      split.setAttribute('aria-label', 'Werkbank teilen');
      split.onclick = ()=>{ state.layout = splitGroup(state.layout, group.id, 'row', 'g' + state.nextId++); render(); save(); };
      fixed.append(split);
      // viele Reiter: das Rad rollt die Reihe waagerecht, statt die Seite zu verbreitern
      bar.onwheel = e=>{ if(bar.scrollWidth > bar.clientWidth && !e.shiftKey){ bar.scrollLeft += e.deltaY; e.preventDefault(); } };
      const barRow = d().el('div', 'dk-bar');
      barRow.append(bar, fixed);
      box.append(barRow);

      // the Werkbank row: what this object can do in its current state (rule 3) – the tools say it, the dock only shows it
      const verbs = d().el('div', 'dk-verbs'); verbs.dataset.verbs = '';
      box.append(verbs);

      const body = d().el('div', 'dk-body');
      bar.ondragover = e=>{ e.preventDefault(); bar.classList.add('drop'); };
      bar.ondragleave = ()=>bar.classList.remove('drop');
      bar.ondrop = e=>{
        e.preventDefault(); bar.classList.remove('drop');
        const key = e.dataTransfer.getData('text/sedra-pane');
        if(!key) return;
        unmountPane(key);
        if(movePane(state.layout, key, group.id)){ state.layout = prune(state.layout); render(); save(); }
      };
      const pane = (group.panes || []).find(p=>p.key === group.active);
      if(!pane){
        verbs.remove();
        body.append(d().empty('Nichts offen. Im Baum links ein Vorhaben, eine Aufgabe oder eine Datei wählen – oder ＋ Neu.'));
      }else{
        renderPaneBody(body, pane);
        renderVerbs(verbs, pane);
      }
      box.append(body);
      box.onmousedown = ()=>{ state.focusGroup = group.id; };
      return box;
    }

    // Nach einem Ereignis zeichnet sich ein Werkzeug selbst neu (es hört auf den Bus); hier geht es nur um die Zeile darüber,
    // weil sich mit dem Zustand des Objekts auch ändert, was man mit ihm tun kann.
    function refreshVerbs(){
      const group = firstActiveGroup();
      const pane = group && (group.panes || []).find(p=>p.key === group.active);
      const row = host.querySelector('.dk-group .dk-verbs');
      if(pane && row) renderVerbs(row, pane);
    }

    function refresh(){ render(); }

    return {open, close, render, refresh, refreshVerbs, restore, save, activeObject, state,
            openKeys: ()=>{ const keys = []; eachGroup(state.layout, g=>(g.panes || []).forEach(p=>keys.push(p.key))); return keys; }};
  }

  root.sedraDock = Object.assign({makeDock}, pure);
  if(typeof module !== 'undefined' && module.exports) module.exports = pure;
})();
