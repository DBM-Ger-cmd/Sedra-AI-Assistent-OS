// Paperclip-Shell – der Fensterstapel (Spec 4, D4.1, G2-S4-02).
//
// Ein Agent ist keine Seite, sondern ein Fenster rechts neben der Seite (Zone `pc-stack`): mehrere zugleich, jedes mit seinem
// eigenen Gespräch. Höchstens MAX_OPEN Fenster sind offen; ein weiteres verkleinert das älteste zur Reiterleiste – geschlossen
// wird nur auf Wunsch. Die Shell merkt sich nur, welche Agenten offen sind (`sedra.paperclip.windows`); den Inhalt liest das
// Werkzeug vom Server. Wer ein Fenster zeichnet, sagt die Registrierung (`forObject`, z. B. ein Werkzeug mit `agent:*`) –
// die Shell kennt es nicht beim Namen. Jedes Fenster ist eine eigene Instanz im eigenen Container (Nachtrag N2).
// `openWindow`, `closeWindow`, `toggleWindow` sind rein und werden mit node geprüft.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const MAX_OPEN = 4;
  const STORE = 'sedra.paperclip.windows';

  // Die Liste läuft vom ältesten zum jüngsten Fenster; `small` heißt: in der Reiterleiste
  function limit(list, max){
    let open = list.filter(w=>!w.small).length;
    return list.map(w=>{
      if(w.small || open <= max) return w;
      open -= 1;
      return Object.assign({}, w, {small: true});
    });
  }

  // Öffnen oder nach vorn holen (rein): das Fenster ist danach das jüngste und offen
  function openWindow(list, object, max){
    if(!object || !object.id) return list;
    const id = String(object.id);
    const old = list.find(w=>w.id === id);
    const entry = {id, title: String(object.title || (old && old.title) || id), small: false};
    return limit(list.filter(w=>w.id !== id).concat([entry]), max || MAX_OPEN);
  }

  function closeWindow(list, id){
    return list.filter(w=>w.id !== String(id));
  }

  // Verkleinern oder wieder öffnen (rein); wieder offen heißt auch: nach vorn
  function toggleWindow(list, id, max){
    const w = list.find(x=>x.id === String(id));
    if(!w) return list;
    if(w.small) return openWindow(list, w, max);
    return list.map(x=>x.id === w.id ? Object.assign({}, x, {small: true}) : x);
  }

  // Was im Browser stand, geprüft: nur {id, title, small}, höchstens MAX_OPEN offen
  function sanitize(raw){
    if(!Array.isArray(raw)) return [];
    const seen = new Set();
    const out = raw.filter(w=>w && typeof w.id === 'string' && w.id && !seen.has(w.id) && seen.add(w.id))
                   .map(w=>({id: w.id, title: typeof w.title === 'string' && w.title ? w.title : w.id, small: !!w.small}));
    return limit(out, MAX_OPEN);
  }

  function makeWindows(host, shell){
    let list = [];
    const views = new Map();            // id -> {box, body, verbs, states, object}
    const tabs = d().el('div', 'pc-tabs');

    function load(){
      try{ list = sanitize(JSON.parse(localStorage.getItem(STORE) || '[]')); }catch(_e){ list = []; }
    }
    function save(){
      try{ localStorage.setItem(STORE, JSON.stringify(list)); }catch(_e){}
    }

    function objectOf(w){ return {type: 'agent', id: w.id, title: w.title}; }

    function build(w){
      const object = objectOf(w);
      const box = d().el('section', 'pc-win');
      box.dataset.agent = w.id;
      const head = d().el('header', 'pc-win-head');
      head.append(d().el('b', null, w.title));
      const verbs = d().el('div', 'pc-win-verbs');
      const small = d().button('▾', ()=>toggle(w.id), 'pc-win-btn');
      small.title = 'Verkleinern'; small.setAttribute('aria-label', 'Verkleinern');
      const close = d().button('✕', ()=>closeById(w.id), 'pc-win-btn');
      close.title = 'Schließen'; close.setAttribute('aria-label', 'Schließen');
      head.append(verbs, small, close);
      const body = d().el('div', 'pc-win-body');
      box.append(head, body);
      const tools = shell.ctx.tools.forObject(object).filter(m=>m.slot !== 'nachweis');
      const states = [];
      if(!tools.length) body.append(d().empty('Für einen einzelnen Agenten gibt es noch kein Werkzeug. Sobald das Agentenfenster gebaut ist, steht hier das Gespräch – ohne eine Zeile an dieser Shell.'));
      tools.forEach(m=>{
        const slot = d().el('div', 'pc-tool');
        slot.dataset.tool = m.id;
        body.append(slot);
        states.push(root.sedraLifecycle.mountTool(shell.ctx.tools.mod(m.id), slot, shell.ctx.makeContext(m, object, shell.shellApi), shell.onProblem));
      });
      const view = {box, body, verbs, states, object};
      Promise.all(states.map(s=>s.ready)).then(()=>drawVerbs(view)).catch(()=>{});
      return view;
    }

    // die Verben eines Fensters stehen im Fenster, nicht in der Kopfzeile der Seite
    function drawVerbs(view){
      view.verbs.replaceChildren();
      view.states.forEach(s=>root.sedraLifecycle.actionsOf(s).forEach(a=>{
        view.verbs.append(d().button(a.label, async()=>{ await a.run(); drawVerbs(view); }));
      }));
    }

    function drop(id){
      const view = views.get(id);
      if(!view) return;
      view.states.forEach(s=>root.sedraLifecycle.unmountTool(s, shell.onProblem));
      view.box.remove();
      views.delete(id);
    }

    // Der Stapel zeigt die offenen Fenster, das jüngste oben; darunter die Reiterleiste der verkleinerten
    function render(focusId){
      const ids = new Set(list.map(w=>w.id));
      Array.from(views.keys()).forEach(id=>{ if(!ids.has(id)) drop(id); });
      const open = list.filter(w=>!w.small).reverse();
      open.forEach(w=>{ if(!views.has(w.id)) views.set(w.id, build(w)); });
      host.replaceChildren(...open.map(w=>views.get(w.id).box), tabs);
      list.filter(w=>w.small).forEach(w=>{ if(views.has(w.id)) views.get(w.id).box.hidden = true; });
      open.forEach(w=>{ const v = views.get(w.id); v.box.hidden = false; v.box.classList.toggle('on', w.id === focusId); });
      tabs.replaceChildren();
      list.filter(w=>w.small).forEach(w=>{
        const tab = d().el('div', 'pc-tab');
        tab.append(d().el('span', null, w.title), d().el('i', null, '▴'));
        tab.title = w.title + ' öffnen';
        d().clickable(tab, ()=>open1(objectOf(w)));
        tabs.append(tab);
      });
      tabs.hidden = !tabs.childElementCount;
      host.hidden = !list.length;
    }

    function open1(object){
      list = openWindow(list, object, MAX_OPEN);
      save(); render(String(object.id));
      const view = views.get(String(object.id));
      if(view && view.box.scrollIntoView) view.box.scrollIntoView({block: 'nearest'});
      return {kind: 'window', object};
    }
    function toggle(id){ list = toggleWindow(list, id, MAX_OPEN); save(); render(id); }
    function closeById(id){ list = closeWindow(list, id); save(); render(); }

    function restore(){ load(); render(); return list.length; }
    function refreshVerbs(){ views.forEach(drawVerbs); }

    return {open: open1, close: closeById, toggle, restore, refreshVerbs, list: ()=>list.slice(), MAX_OPEN};
  }

  root.sedraPcWindows = {makeWindows, openWindow, closeWindow, toggleWindow, sanitize, MAX_OPEN, STORE};
  if(typeof module !== 'undefined' && module.exports) module.exports = {openWindow, closeWindow, toggleWindow, sanitize, MAX_OPEN, STORE};
})();
