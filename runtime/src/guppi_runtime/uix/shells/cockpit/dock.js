// Cockpit shell – the dock (COCKPIT_MODUL_v1 §3a): tabs per object, split, drag, layout as JSON in this browser; no tool knows it.
// Stufe 2 (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §4): `abgleichen()` statt Neuaufbau. Eine Gruppe behält ihre Fläche; ein Reiterwechsel hängt nur
// in dieser Gruppe ein und aus. Werkzeuge mit `instanzen: viele` bleiben versteckt eingehängt (höchstens 8), Einzelstücke bauen ab und
// holen ihren Zustand aus dem Gedächtnis (Vertrag 1.1). Ein Einzelstück zeichnet nie in zwei Gruppen zugleich (D2-3).
// Classic script: part of the cockpit shell; registerShell lives in shell.js.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const L = ()=>root.sedraLifecycle;
  const MAX_VERSTECKT = 8;

  // ---- the pure part (node tests it): a layout is a tree of groups; panes carry {type, id, title}
  function newLayout(){ return {kind: 'group', id: 'g1', panes: [], active: null}; }
  function eachGroup(node, fn){
    if(!node) return;
    if(node.kind === 'group'){ fn(node); return; }
    (node.children || []).forEach(c=>eachGroup(c, fn));
  }
  function findGroup(node, id){ let found = null; eachGroup(node, g=>{ if(g.id === id) found = g; }); return found; }
  function firstGroup(node){ let found = null; eachGroup(node, g=>{ if(!found) found = g; }); return found; }
  function paneKey(object){ return object.type + ':' + object.id; }

  // put an object into a group; an object that is already open is only brought to the front (rule 4: tabs carry names)
  function addPane(layout, object, groupId){
    const key = paneKey(object);
    let where = null;
    eachGroup(layout, g=>{ if(!where && (g.panes || []).some(p=>p.key === key)) where = g; });
    if(where){ where.active = key; return {group: where, created: false}; }
    const group = (groupId && findGroup(layout, groupId)) || firstGroup(layout);
    // ansicht: welche Ansicht eines Werkzeugs gezeigt wird (das GateWay im Baum); imBaum: das Menü steht schon im Baum; view: Ansicht (Wissen)
    group.panes.push({key, object: {type: object.type, id: object.id, title: object.title || object.id, collection: !!object.collection,
                                    ansicht: object.ansicht || undefined, imBaum: !!object.imBaum || undefined, view: object.view || undefined}});
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
  function eachSplit(node, fn){ if(!node || node.kind !== 'split') return; fn(node); node.children.forEach(c=>eachSplit(c, fn)); }
  // a split: the group becomes a row (or column) with itself and a new empty group next to it
  function splitGroup(layout, groupId, direction, nextId){
    const target = findGroup(layout, groupId);
    if(!target) return layout;
    const moved = {kind: 'group', id: target.id, panes: target.panes, active: target.active};
    const split = {kind: 'split', direction, children: [moved, {kind: 'group', id: nextId, panes: [], active: null}]};
    if(layout === target) return split;
    eachSplit(layout, s=>{ const i = s.children.indexOf(target); if(i >= 0) s.children[i] = split; });
    return layout;
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
    target.panes.push(pane); target.active = key;
    return true;
  }

  // §9.6: was aus localStorage kommt, wird geprüft – nur group/split, nur bekannte Felder, höchstens 4 Ebenen, kein Reiter doppelt.
  // Bleibt nichts Gültiges übrig: null (die Werkbank startet dann mit den Aufgaben). Rein.
  function sanitizeLayout(raw){
    const seen = new Set(), ids = new Set();
    const OBJ = ['type', 'id', 'title', 'collection', 'ansicht', 'imBaum', 'view'];
    const text = v=>typeof v === 'string' || typeof v === 'number';
    function node(n, tiefe){
      if(!n || typeof n !== 'object' || tiefe > 4) return null;
      if(n.kind === 'split'){
        if(n.direction !== 'row' && n.direction !== 'column') return null;
        const kids = (Array.isArray(n.children) ? n.children : []).map(c=>node(c, tiefe + 1)).filter(Boolean);
        if(!kids.length) return null;
        return kids.length === 1 ? kids[0] : {kind: 'split', direction: n.direction, children: kids};
      }
      if(n.kind !== 'group') return null;
      let id = typeof n.id === 'string' && /^g\d{1,4}$/.test(n.id) && !ids.has(n.id) ? n.id : null;
      if(!id){ let i = 1; while(ids.has('g' + i)) i++; id = 'g' + i; }
      ids.add(id);
      const panes = (Array.isArray(n.panes) ? n.panes : []).map(p=>{
        const o = p && p.object;
        if(!o || !text(o.type) || !text(o.id) || !/^[a-z][a-z0-9_-]{0,30}$/.test(String(o.type))) return null;
        const obj = {};
        OBJ.forEach(k=>{ if(o[k] !== undefined && o[k] !== null) obj[k] = (k === 'collection' || k === 'imBaum') ? !!o[k] : String(o[k]).slice(0, 200); });
        const key = paneKey(obj);
        if(seen.has(key)) return null;
        seen.add(key);
        return {key, object: obj};
      }).filter(Boolean);
      const active = panes.some(p=>p.key === n.active) ? n.active : (panes[0] || {}).key || null;
      return {kind: 'group', id, panes, active};
    }
    const out = node(raw, 1);
    if(!out) return null;
    let any = false; eachGroup(out, g=>{ if(g.panes.length) any = true; });
    return any ? out : null;
  }

  const pure = {newLayout, addPane, removePane, splitGroup, movePane, prune, findGroup, firstGroup, paneKey, eachGroup, sanitizeLayout, MAX_VERSTECKT};

  // ---- the browser part
  function makeDock(host, shell){
    const state = {layout: newLayout(), nextId: 2, focusGroup: null,
                   gruppen: new Map(),         // groupId -> {box, bar, tabs, verbs, body}
                   reiter: new Map(),          // paneKey -> {key, object, box, entries, gruppe, modus: live|versteckt|hinweis, zuletzt, scroll}
                   besitzer: new Map(),        // Einzelstück-Werkzeug -> paneKey, das es gerade zeichnet (D2-3)
                   zuletzt: {}, mounts: 0, frisch: new Set()};   // frisch: Reiter, die eine Ansicht ausdrücklich verlangt haben
    const saveKey = 'sedra.cockpit.layout';
    let uhr = 0; const jetzt = ()=>++uhr;

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
      const layout = saved && sanitizeLayout(saved.layout);
      if(!layout) return false;
      state.layout = layout;
      let max = 1;
      eachGroup(state.layout, g=>{ max = Math.max(max, parseInt(String(g.id).replace('g', ''), 10) || 1); });
      state.nextId = max + 1;
      return true;
    }

    // the tools that draw this object, in the order of the manifest (N1: forObject – `typ:alle`, `typ:*`, `typ:<id>` zählen)
    const toolsFor = object=>shell.ctx.tools.forObject(object) || [];
    const mehrfach = m=>L().istMehrfach(m), sig = o=>[o.ansicht || '', o.view || ''].join('|');

    // ---- ein Reiter: einhängen, verstecken, abbauen
    function einhaengen(rv){
      const pane = {object: rv.object};
      const tools = toolsFor(rv.object);
      rv.box.replaceChildren(); rv.entries = []; rv.modus = 'live';
      if(!tools.length){
        rv.box.append(d().empty('Für „' + rv.object.type + '“ ist kein Werkzeug installiert. In der Bibliothek steht, was es gibt.'));
        return;
      }
      const content = tools.filter(t=>(t.slot || 'inhalt') !== 'nachweis');
      // Nachweise gehören an ein Werkstück, nicht an eine Liste; das GateWay hat seinen Nachweis im Menü links
      const evidence = (pane.object.collection || pane.object.type === 'gateway') ? [] : tools.filter(t=>(t.slot || 'inhalt') === 'nachweis');
      let left = rv.box, right = null;
      if(content.length && evidence.length){
        const split = d().el('div', 'dk-pane');
        left = d().el('div', 'dk-pane-col');
        right = d().el('div', 'dk-pane-col dk-pane-evidence'); right.dataset.slot = 'nachweis';     // Vertragsmarke für die Abnahme jeder Shell
        split.append(left, right); rv.box.append(split);
      }
      const mount = (manifest, into)=>{
        const slot = d().el('div', 'dk-tool'); slot.dataset.tool = manifest.id; into.append(slot);
        // `shell.shellApi`, nicht `shell.api` (15.10.2026: ctx.shell.open() war in jedem Reiter tot, der Loader prüft das jetzt)
        const ctx = shell.ctx.makeContext(manifest, pane.object, shell.shellApi);
        const e = L().mountTool(shell.ctx.tools.mod(manifest.id), slot, ctx, shell.onProblem);
        e.manifest = manifest; rv.entries.push(e); state.mounts += 1;
        if(!mehrfach(manifest)) state.besitzer.set(manifest.id, rv.key);
      };
      content.forEach(m=>mount(m, left));
      evidence.forEach(m=>mount(m, right || rv.box));
      const entries = rv.entries;
      // Die Verben erst zeigen, wenn die Werkzeuge gezeichnet haben – sonst fragt die Zeile, bevor es etwas zu antworten gibt.
      Promise.all(entries.map(e=>e.ready)).then(()=>{ if(rv.entries === entries) verbenFuer(rv.gruppe); });
    }
    function abbauen(rv){
      (rv.entries || []).forEach(e=>{
        L().unmountTool(e, shell.onProblem);
        if(state.besitzer.get(e.id) === rv.key) state.besitzer.delete(e.id);
      });
      rv.entries = []; rv.box.replaceChildren();
    }
    function verstecken(rv, body){
      if(rv.modus === 'live' && rv.entries.length && rv.entries.every(e=>mehrfach(e.manifest))){
        rv.entries.forEach(e=>L().bereitHalten(e)); rv.modus = 'versteckt';
      }else if(rv.modus !== 'versteckt'){ abbauen(rv); rv.modus = 'aus'; }
      if(body && !rv.box.hidden) rv.scroll = body.scrollTop;
      rv.box.hidden = true;
    }
    // Ein Einzelstück, das ein anderer sichtbarer Reiter schon zeichnet: hier ein Hinweis statt eines toten Inhalts (D2-3)
    function konflikt(rv){
      return toolsFor(rv.object).filter(m=>!mehrfach(m)).map(m=>state.besitzer.get(m.id))
        .find(k=>k && k !== rv.key && state.reiter.has(k) && !state.reiter.get(k).box.hidden && state.reiter.get(k).modus === 'live') || null;
    }
    function hinweis(rv, anderer){
      abbauen(rv); rv.modus = 'hinweis';
      const t = (state.reiter.get(anderer) || {object: {}}).object.title || anderer;
      const box = d().el('div', 's-empty dk-hinweis');
      box.append(d().el('div', null, 'Dieses Werkzeug kann nur ein Objekt zugleich zeigen – gerade zeigt es „' + t + '“ in der anderen Gruppe.'));
      box.append(d().button('Hierher holen', ()=>{ abgleichen(rv.key); }, 'p'));
      rv.box.append(box);
    }

    function zeigen(rv, group, body, vorrang){
      if(rv.box.parentElement !== body) body.append(rv.box);
      const war = rv.box.hidden;
      rv.box.hidden = false;
      if(rv.modus === 'versteckt'){ rv.entries.forEach(e=>L().zeigen(e)); rv.modus = 'live'; }
      if(rv.modus !== 'live'){
        const anderer = konflikt(rv);
        if(anderer && !vorrang) hinweis(rv, anderer);
        else{
          if(anderer){ const a = state.reiter.get(anderer); hinweis(a, rv.key); }
          einhaengen(rv);
        }
      }
      if(war && rv.scroll !== undefined) body.scrollTop = rv.scroll;
      rv.zuletzt = jetzt(); state.zuletzt[rv.key] = rv.zuletzt;
    }

    // ---- die Fläche einer Gruppe: Reiterzeile, Handlungszeile, Inhalt – einmal gebaut, danach nur nachgeführt
    function gruppenFlaeche(group){
      let gv = state.gruppen.get(group.id);
      if(gv) return gv;
      const box = d().el('div', 'dk-group');
      const tabs = d().el('div', 'dk-tabs');
      const fixed = d().el('div', 'dk-bar-fixed');
      const plus = d().el('button', 's-btn dk-new', '＋ Neu ▾'); plus.type = 'button';
      plus.title = 'Vorhaben · Projekt · Datei öffnen · Modell hinzufügen';
      plus.onclick = e=>{ e.stopPropagation(); shell.openNew(plus); };
      const split = d().el('button', 'dk-split-btn', '⊞'); split.type = 'button';
      split.title = 'Teilen: der Reiter bekommt eine zweite Spalte'; split.setAttribute('aria-label', 'Werkbank teilen');
      split.onclick = ()=>{ state.layout = splitGroup(state.layout, group.id, 'row', 'g' + state.nextId++); abgleichen(); save(); };
      fixed.append(plus, split);
      // viele Reiter: das Rad rollt die Reihe waagerecht, statt die Seite zu verbreitern
      tabs.onwheel = e=>{ if(tabs.scrollWidth > tabs.clientWidth && !e.shiftKey){ tabs.scrollLeft += e.deltaY; e.preventDefault(); } };
      tabs.ondragover = e=>{ e.preventDefault(); tabs.classList.add('drop'); };
      tabs.ondragleave = ()=>tabs.classList.remove('drop');
      tabs.ondrop = e=>{
        e.preventDefault(); tabs.classList.remove('drop');
        const key = e.dataTransfer.getData('text/sedra-pane');
        if(key && movePane(state.layout, key, group.id)){ state.layout = prune(state.layout); state.focusGroup = group.id; abgleichen(key); save(); }
      };
      const bar = d().el('div', 'dk-bar'); bar.append(tabs, fixed);
      // the Werkbank row: what this object can do in its current state (rule 3) – the tools say it, the dock only shows it
      const verbs = d().el('div', 'dk-verbs'); verbs.dataset.verbs = '';
      const body = d().el('div', 'dk-body');
      const leer = d().empty('Nichts offen. Im Baum links ein Vorhaben, eine Aufgabe oder eine Datei wählen – oder ＋ Neu.');
      box.append(bar, verbs, body);
      box.onmousedown = ()=>{ state.focusGroup = group.id; };
      gv = {box, tabs, fixed, verbs, body, leer, id: group.id};
      state.gruppen.set(group.id, gv);
      return gv;
    }

    function reiterZeile(group, gv){
      gv.tabs.replaceChildren(...(group.panes || []).map(pane=>{
        const tab = d().el('div', 'dk-tab' + (pane.key === group.active ? ' on' : ''));
        tab.draggable = true;
        tab.append(d().el('span', null, pane.object.title));
        tab.title = pane.object.title;                       // der volle Name, wenn der Reiter ihn kürzt
        tab.onauxclick = e=>{ if(e.button === 1){ e.preventDefault(); close(pane.key); } };   // mittlere Maustaste schließt, wie im Browser
        const x = d().el('button', 'dk-x', '✕'); x.type = 'button';
        x.title = 'Schließen'; x.setAttribute('aria-label', 'Reiter schließen: ' + pane.object.title);
        x.onclick = e=>{ e.stopPropagation(); close(pane.key); };
        tab.append(x);
        d().clickable(tab, ()=>{ group.active = pane.key; state.focusGroup = group.id; abgleichen(pane.key); save(); });
        tab.ondragstart = e=>{ e.dataTransfer.setData('text/sedra-pane', pane.key); e.dataTransfer.effectAllowed = 'move'; };
        return tab;
      }));
      // „＋ Neu“ steht nur einmal, in der Gruppe ganz rechts oben (Baum-Spec §3.7)
      const gruppen = []; eachGroup(state.layout, g=>gruppen.push(g.id));
      gv.fixed.querySelector('.dk-new').hidden = gruppen[gruppen.length - 1] !== group.id;
    }

    // ---- der Abgleich: Struktur und Flächen nachführen, nur dort ein- und aushängen, wo sich der vordere Reiter geändert hat
    function abgleichen(vorrang){
      const struktur = node=>{
        if(node.kind === 'split'){
          const box = d().el('div', 'dk-split dk-' + node.direction);
          node.children.forEach(c=>box.append(struktur(c)));
          return box;
        }
        return gruppenFlaeche(node).box;
      };
      const offen = new Map();                                 // paneKey -> {pane, group}
      eachGroup(state.layout, g=>(g.panes || []).forEach(p=>offen.set(p.key, {pane: p, group: g})));
      // Reiter, die es nicht mehr gibt oder deren Ansicht sich geändert hat, abbauen
      state.reiter.forEach((rv, key)=>{
        const o = offen.get(key);
        if(!o){ abbauen(rv); rv.box.remove(); state.reiter.delete(key); return; }
        if(sig(o.pane.object) !== sig(rv.object) || state.frisch.has(key)){ abbauen(rv); rv.modus = 'aus'; }
        rv.object = o.pane.object; rv.gruppe = o.group.id;
      });
      const ids = new Set(); eachGroup(state.layout, g=>ids.add(g.id));
      state.gruppen.forEach((gv, id)=>{ if(!ids.has(id)){ gv.box.remove(); state.gruppen.delete(id); } });
      // die Struktur (Teilungen) nur neu bauen, wenn sie sich geändert hat – sonst bleiben alle Flächen, wo sie sind
      const form = JSON.stringify(state.layout, (k, v)=>k === 'panes' || k === 'active' ? undefined : v);
      if(form !== state.form || host.childNodes.length !== 1){ host.replaceChildren(struktur(state.layout)); state.form = form; }
      // erst alle nicht vorderen verstecken, dann die vorderen zeigen – so gibt ein Einzelstück frei, bevor es woanders gebraucht wird
      const vorne = [];
      eachGroup(state.layout, group=>{
        const gv = gruppenFlaeche(group);
        reiterZeile(group, gv);
        (group.panes || []).forEach(p=>{
          let rv = state.reiter.get(p.key);
          if(!rv){ rv = {key: p.key, object: p.object, box: d().el('div', 'dk-pane-box'), entries: [], gruppe: group.id, modus: 'aus'}; rv.box.hidden = true; state.reiter.set(p.key, rv); }
          if(p.key !== group.active) verstecken(rv, gv.body);
          else vorne.push([rv, group, gv]);
        });
        if(!(group.panes || []).length){ gv.body.replaceChildren(gv.leer); gv.verbs.hidden = true; }
        else{ if(gv.leer.parentElement) gv.leer.remove(); gv.verbs.hidden = false; }
      });
      vorne.sort((a, b)=>(a[0].key === vorrang) - (b[0].key === vorrang));     // der gewollte Reiter zuletzt: er bekommt das Einzelstück
      vorne.forEach(([rv, group, gv])=>zeigen(rv, group, gv.body, rv.key === vorrang));
      state.frisch.clear();
      grenzeVersteckt();
      state.gruppen.forEach(gv=>verbenFuer(gv.id));
      shell.onDockChanged && shell.onDockChanged(activeObject(), offeneObjekte(), state.zuletzt);
    }

    // höchstens MAX_VERSTECKT versteckt eingehängte Reiter; darüber baut der älteste ab (sein Zustand liegt im Gedächtnis)
    function grenzeVersteckt(){
      const versteckt = Array.from(state.reiter.values()).filter(rv=>rv.modus === 'versteckt').sort((a, b)=>(a.zuletzt || 0) - (b.zuletzt || 0));
      versteckt.slice(0, Math.max(0, versteckt.length - MAX_VERSTECKT)).forEach(rv=>{ abbauen(rv); rv.modus = 'aus'; });
    }

    // the state line and the verbs; a tool that offers none keeps the row empty rather than showing something borrowed
    // Die Zeile trägt die Handlungen des Werkstücks (Regel 3) – nicht die Hausarbeiten der Nachweise, die ihre eigenen Knöpfe haben.
    function verbenFuer(groupId){
      const gv = state.gruppen.get(groupId), group = findGroup(state.layout, groupId);
      if(!gv || !group) return;
      const rv = group.active && state.reiter.get(group.active);
      if(!rv){ gv.verbs.replaceChildren(); return; }
      const actions = [];
      (rv.entries || []).filter(e=>((e.manifest || {}).slot || 'inhalt') !== 'nachweis')
        .forEach(entry=>L().actionsOf(entry).forEach(a=>actions.push(a)));
      gv.verbs.replaceChildren(d().el('small', 's-muted', rv.object.title));
      actions.forEach((a, i)=>{
        const b = d().button(a.label, ()=>Promise.resolve(a.run()), i === 0 && actions.length > 1 ? 'p' : '');
        if(i === 0) b.style.marginLeft = 'auto';
        gv.verbs.append(b);
      });
    }

    function open(object, groupId){
      const {group, created} = addPane(state.layout, object, groupId);
      // eine ausdrücklich verlangte Ansicht (Baumzeile „Vorgänge“, Ort „Wissen · Quellen“) ist Navigation: der Reiter zeichnet neu
      if(!created && (object.ansicht !== undefined || object.view !== undefined)) state.frisch.add(paneKey(object));
      // Dasselbe Objekt, andere Ansicht (das GateWay im Baum, Wissen mit view): der Reiter bleibt, die Ansicht wird neu gezeichnet
      const pane = group.panes.find(p=>p.key === paneKey(object));
      if(pane && ((object.ansicht !== undefined && pane.object.ansicht !== object.ansicht) || (object.view !== undefined && pane.object.view !== object.view)))
        pane.object = Object.assign({}, pane.object, {ansicht: object.ansicht || pane.object.ansicht, view: object.view || pane.object.view,
                                                      imBaum: !!object.imBaum || undefined, title: object.title || pane.object.title});
      state.focusGroup = group.id;
      abgleichen(paneKey(object)); save();
      return group;
    }

    function close(key){
      const rv = state.reiter.get(key);
      const object = rv ? rv.object : null;
      removePane(state.layout, key);
      state.layout = prune(state.layout);
      abgleichen(); save();
      if(object){                                       // §9.3: Gedächtnis vergessen, den Werkzeugen und dem Arbeitsstand sagen
        L().memoVergessen(object);
        try{ shell.ctx.bus.emit('object.close', {type: object.type, id: object.id}); }catch(_e){}
        shell.onDockClosed && shell.onDockClosed(object);
      }
    }

    function activeObject(){
      const g = findGroup(state.layout, state.focusGroup) || firstGroup(state.layout);
      const pane = g && (g.panes || []).find(p=>p.key === g.active);
      return pane ? pane.object : null;
    }
    function offeneObjekte(){ const out = []; eachGroup(state.layout, g=>(g.panes || []).forEach(p=>out.push(p.object))); return out; }

    // §10.4: was eine andere Shell offen hatte, kommt dazu; was vorn lag, kommt nach vorn
    function uebernehmen(objekte, vorn){
      (objekte || []).forEach(o=>addPane(state.layout, o));
      eachGroup(state.layout, g=>{ if(vorn && (g.panes || []).some(p=>p.key === vorn)){ g.active = vorn; state.focusGroup = g.id; } });
    }

    // nach einem Ereignis zeichnet sich ein Werkzeug selbst neu (Bus); hier nur die Zeilen darüber
    function refreshVerbs(){ state.gruppen.forEach(gv=>verbenFuer(gv.id)); }

    return {open, close, render: abgleichen, refresh: abgleichen, abgleichen, refreshVerbs, restore, save, activeObject, offeneObjekte,
            uebernehmen, state, kann: o=>toolsFor(o).length > 0,
            openKeys: ()=>{ const keys = []; eachGroup(state.layout, g=>(g.panes || []).forEach(p=>keys.push(p.key))); return keys; }};
  }

  root.sedraDock = Object.assign({makeDock}, pure);
  if(typeof module !== 'undefined' && module.exports) module.exports = pure;
})();
