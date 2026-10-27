// Minimal-Shell – die Menüleiste (Entwurf E, Spec §1.1).
// Links die Menüs, rechts die Instrumente. Die Instrumente sind Werkzeuge der Art `instrument` und bekommen hier dieselbe
// Zelle und dieselbe Lesung aus `GET /api/strip` wie in der Leiste des Cockpits – ohne dass an ihnen etwas geändert wurde.
// Das Menü „Werkzeuge“ hat ein Suchfeld und ist zugleich das, was Strg+K öffnet: E erbt die Palette des Cockpits nicht.
// Build 19 (PC-Test 15.10.: „ich sehe nicht, wie ich wieder auf die Haupt-Shell zurückkomme“): ganz links ein Haus-Knopf zur
// Übersicht der Oberflächen, und das Menü „SEDRA“ mit allen Oberflächen. Die Übersicht gilt nur für diesen Lauf (wie
// `START_SEDRA` ohne Argument) – die gewählte Oberfläche in uix.yaml bleibt; eine andere Oberfläche nehmen ist eine Wahl.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Die Orte kommen aus dem Vertrag (ui/places.js) – dieselben Wörter, dieselben Objekte wie im Cockpit.
  const places = ()=>root.sedraPlaces.PLACES;

  // Was im Suchfeld zu „werkst“ passt: erst die Treffer der Ortskunde, sonst alles
  function match(text){
    const q = String(text || '').trim();
    if(!q) return places();
    const hits = root.sedraPlaces.matchPlaces(q);
    return hits.length ? hits : [];
  }

  function makeMenubar(host, shell){
    const cells = [];
    let leiste = null;
    let openMenu = null;

    function closeMenu(){
      if(openMenu){ openMenu.remove(); openMenu = null; }
    }

    function dropdown(anchor, build){
      closeMenu();
      const box = d().el('div', 'sh-min-menu');
      build(box, ()=>closeMenu());
      const r = anchor.getBoundingClientRect();
      box.style.left = Math.max(6, Math.min(r.left, window.innerWidth - 300)) + 'px';
      box.style.top = (r.bottom + 2) + 'px';
      document.body.append(box);
      openMenu = box;
      setTimeout(()=>{
        const away = e=>{ if(!box.contains(e.target)){ closeMenu(); document.removeEventListener('mousedown', away); } };
        document.addEventListener('mousedown', away);
      }, 0);
      return box;
    }

    function item(box, label, hint, fn){
      const row = d().el('div', 'sh-min-menu-item');
      row.append(d().el('b', null, label));
      if(hint) row.append(d().el('small', null, hint));
      d().clickable(row, ()=>{ closeMenu(); fn(); });
      box.append(row);
      return row;
    }

    // SEDRA: die Oberflächen – zurück zur Übersicht, oder gleich in eine andere
    async function goOverview(){
      await shell.api('/api/uix/shell', {method: 'POST', body: {shell: 'start', nur_jetzt: true}});
      shell.shellApi.reload();
    }

    async function sedraMenu(box){
      item(box, 'Übersicht der Oberflächen', 'alle Oberflächen – die Wahl bleibt, bis du eine andere nimmst', ()=>goOverview());
      let view = null;
      try{ view = await shell.api('/api/uix/modules'); }
      catch(err){ item(box, 'Oberflächen nicht lesbar', err.message, ()=>{}); return; }
      (view.shells || []).filter(s=>s.id !== 'start' && s.id !== 'minimal').forEach(s=>{
        item(box, 'Wechseln zu ' + s.name, s.description || '', async()=>{
          await shell.api('/api/uix/shell', {method: 'POST', body: {shell: s.id}});
          shell.shellApi.reload();
        });
      });
    }

    // Ablage: anlegen. Dieselben Wege wie „＋ Neu“ im Cockpit (Regel 8), nur als Menü.
    function fileMenu(box){
      item(box, 'Vorhaben', 'der Satz, um den es geht – SEDRA macht Aufgaben daraus',
           ()=>shell.openObject({type: 'intent', id: 'alle', title: 'Vorhaben', collection: true}));
      item(box, 'Projekt', 'einen Ordner als Projekt anlegen', ()=>shell.openObject({type: 'project', id: 'neu', title: 'Neues Projekt'}));
      item(box, 'Modell hinzufügen', 'GGUF wählen, Rezept prüfen, laden', ()=>shell.openObject({type: 'model', id: 'neu', title: 'Modell hinzufügen'}));
    }

    // Aufgabe: die Verben des Fensters, das vorn steht – dieselben, die auch im Fenster unten stehen.
    function taskMenu(box){
      const front = shell.windows.front();
      if(!front){ item(box, 'Kein Fenster vorn', '', ()=>{}); return; }
      const win = shell.windows.windows.get(front.type + ':' + front.id);
      const actions = win ? root.sedraLifecycle.actionsOf(win.state) : [];
      if(!actions.length){ item(box, 'Nichts zu tun', front.title || front.type, ()=>{}); return; }
      actions.forEach(a=>item(box, a.label, front.title || '', ()=>Promise.resolve(a.run()).catch(e=>shell.onProblem('Handlung', e))));
    }

    // Werkzeuge: alle Orte mit Suchfeld. Das ist auch, was Strg+K öffnet.
    function placesMenu(box, close){
      const input = d().el('input');
      input.placeholder = 'Ort suchen – Enter öffnet';
      input.setAttribute('aria-label', 'Ort suchen');
      const list = d().el('div', 'sh-min-menu-list');
      const draw = ()=>{
        list.replaceChildren();
        match(input.value).slice(0, 10).forEach(place=>{
          const row = d().el('div', 'sh-min-menu-item');
          row.append(d().el('b', null, place.label), d().el('small', null, place.hint || ''));
          d().clickable(row, ()=>{ close(); shell.openObject(place.object); });
          list.append(row);
        });
      };
      input.oninput = draw;
      input.onkeydown = e=>{
        if(e.key === 'Enter'){ const first = match(input.value)[0]; if(first){ close(); shell.openObject(first.object); } }
        else if(e.key === 'Escape') close();
      };
      box.append(input, list);
      draw();
      setTimeout(()=>input.focus(), 0);
    }

    // Fenster: was offen ist, und ein Weg, aufzuräumen.
    function windowMenu(box){
      const list = shell.windows.list().filter(o=>o.type !== 'talk');
      if(!list.length) item(box, 'Kein Fenster offen', 'das Gespräch bleibt immer', ()=>{});
      list.forEach(o=>item(box, o.title || o.type, o.type, ()=>shell.openObject(o)));
      if(list.length > 1) item(box, 'Alle schließen', 'bis auf das Gespräch', ()=>shell.windows.closeAll());
      const front = shell.windows.front();
      if(front && front.type !== 'talk') item(box, 'An die Ablage heften', (front.title || front.type) + ' – als Feld unten', ()=>shell.shelf.pin(front));
      item(box, 'Feld in der Ablage anlegen …', 'Ort, Fenster oder Auftrag an SEDRA, mit Bildzeichen', ()=>shell.shelf.pin(null));
    }

    function helpMenu(box){
      item(box, 'Strg+K', 'Orte durchsuchen und öffnen', ()=>openPlaces());
      item(box, 'Enter im Gespräch', 'sendet – das Gesprächsfenster lässt sich nicht schließen', ()=>{});
      item(box, 'Diese Shell', 'Minimal (E): freie Fenster statt Reiter, dieselben Werkzeuge', ()=>{});
      item(box, 'Ablage', '„Neu“ legt ein Feld an · Rechtsklick auf ein Feld: verschieben, ändern, entfernen', ()=>{});
      item(box, 'Zurück zur Übersicht', 'das Haus ganz links oben', ()=>goOverview());
    }

    const MENUS = [['Ablage', fileMenu], ['Aufgabe', taskMenu], ['Werkzeuge', placesMenu], ['Fenster', windowMenu], ['Hilfe', helpMenu]];
    let placesAnchor = null;

    function openPlaces(){ if(placesAnchor) dropdown(placesAnchor, placesMenu); }

    // Ein kleines Menü an einer Stelle (Rechtsklick auf ein Feld der Ablage): [[Beschriftung, fn], …]
    function popup(anchor, rows){
      const box = dropdown(anchor, ()=>{});
      rows.forEach(([label, fn])=>item(box, label, '', ()=>Promise.resolve(fn()).catch(e=>shell.onProblem('Ablage', e))));
      const r = anchor.getBoundingClientRect();
      box.style.top = Math.max(32, r.top - box.offsetHeight - 6) + 'px';
      return box;
    }

    function build(){
      host.replaceChildren();
      const home = d().el('span', 'sh-min-home');
      home.title = 'Zur Übersicht der Oberflächen';
      home.setAttribute('aria-label', 'Zur Übersicht der Oberflächen');
      home.append(root.sedraMinIcons.iconEl('haus', 16));
      d().clickable(home, ()=>goOverview().catch(e=>shell.onProblem('Übersicht', e)));
      const name = d().el('span', 'sh-min-menu-name sh-min-brand');
      name.append(d().el('span', 'sh-min-mark'), d().el('b', null, 'SEDRA'));
      d().clickable(name, ()=>dropdown(name, box=>{ sedraMenu(box).catch(e=>shell.onProblem('Oberflächen', e)); }));
      host.append(home, name);
      MENUS.forEach(([label, build])=>{
        const entry = d().el('span', 'sh-min-menu-name', label);
        d().clickable(entry, ()=>dropdown(entry, build));
        host.append(entry);
        if(label === 'Werkzeuge') placesAnchor = entry;
      });
      host.append(d().el('span', 'sh-min-spacer'));

      // rechts: die Instrumente – Werkzeuge wie alle anderen (Regel 11)
      cells.length = 0;
      shell.ctx.tools.byKind('instrument').forEach(manifest=>{
        const cell = d().el('div', 'sh-min-gauge');
        cell.dataset.tool = manifest.id;
        host.append(cell);
        const mod = shell.ctx.tools.mod(manifest.id);
        const state = root.sedraLifecycle.mountTool(mod, cell, shell.ctx.makeContext(manifest, null, shell.shellApi), shell.onProblem);
        cells.push({manifest, mod, state, cell});
      });
      // Stufe 6: ruhige Instrumente wandern in „Weitere +n“ (ui/leiste.js)
      leiste = root.sedraLeiste ? root.sedraLeiste.makeLeiste(host, ()=>cells.map(c=>({el: c.cell, id: c.manifest.id, order: c.manifest.order})), 'sh-min-gauge') : null;
    }

    async function refresh(){
      if(!cells.length) build();
      let reading;
      try{ reading = await shell.api('/api/strip'); }
      catch(err){
        cells.forEach(c=>{ if(c.mod.update) try{ c.mod.update(null, err.message); }catch(_e){} });
        return;
      }
      cells.forEach(c=>{
        if(!c.mod.update) return;
        try{ c.mod.update(reading, null); }
        catch(err){ shell.onProblem('Instrument ' + c.manifest.id, err); }
      });
      if(leiste) leiste.ordnen();
    }

    return {build, refresh, cells, openPlaces, closeMenu, popup, goOverview, isOpen: ()=>!!openMenu};
  }

  root.sedraMinMenubar = {makeMenubar, match};
})();
