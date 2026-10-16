// Cockpit shell – the tree (COCKPIT_MODUL_v1 §1: Projekt, Vorhaben/Aufgaben, Werkstatt, Besatzung, Bibliothek, System).
// It is navigation, nothing else: a row sends object.open and the dock decides what to draw. The tree never draws an object itself.
// treeModel() is pure (data in, rows out) so node can judge it without a browser.
// Build 24 (Ticket B6-G-06, Klaus 15.10.2026): die Zeile „Routinen – noch nicht gebaut“ ist weg – kein Eintrag ohne Werkzeug dahinter
// (Nachtkette bleibt OPEN im Register). Das KI GateWay bleibt in seiner eigenen Oberfläche (Klaus 19:34); erreichbar über Strg+K und den Umschalter.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // the rows of the tree from what the runtime says; every row carries the object it opens
  function treeModel(data){
    const missions = data.missions || [], models = data.models || {}, library = data.library || {}, agents = data.agents || {};
    const project = data.project || {};
    const rows = [];
    const head = (title, note)=>rows.push({kind: 'head', title, note: note || ''});
    const row = (title, object, note, tone, parent)=>rows.push({kind: 'row', title, object, note: note || '', tone: tone || '', parent: parent || ''});
    const group = (title, note)=>rows.push({kind: 'group', title, note: note || ''});
    // Eine Sammlung ist kein Werkstück: sie bekommt keine Nachweise daneben (siehe dock.js).
    const many = (title, object, note, tone)=>row(title, Object.assign({collection: true}, object), note, tone);

    head('Projekt ' + (project.name || '–'));
    row('Dateien', {type: 'project', id: project.id || project.name || 'projekt', title: 'Projekt ' + (project.name || '')}, project.path || '');

    // Vorhaben und Aufgaben sind zweierlei (Regel 8): das Vorhaben ist der Satz, die Aufgabe ist die Arbeit daraus.
    const intents = data.intents || [];
    head('Vorhaben', intents.length ? String(intents.length) : '');
    many('Alle Vorhaben', {type: 'intent', id: 'alle', title: 'Vorhaben'}, intents.length ? '' : 'noch keins – „＋ Neu“');
    intents.slice(0, 8).forEach(v=>row(v.title, {type: 'intent', id: v.id, title: v.title}, v.state,
                                       v.state === 'wartet auf dich' ? 'warn' : ''));

    const open = missions.filter(m => (m.status || '') === 'active');
    head('Aufgaben', open.length ? open.length + ' offen' : '');
    if(!open.length) rows.push({kind: 'note', title: 'Nichts offen. Im Gespräch sagen, was gebaut werden soll.'});
    open.slice(0, 12).forEach(m=>{
      const waits = (m.pending_gates || 0) > 0;
      row(String(m.intent || m.objective || m.mission_id).slice(0, 60),
          {type: 'task', id: m.mission_id, title: String(m.intent || m.mission_id).slice(0, 40)},
          waits ? 'wartet auf dich' : (m.steps && m.steps.length ? 'Schritt ' + Math.min((m.steps_done || 0) + 1, m.steps.length) + ' von ' + m.steps.length : (m.phase || '')),
          waits ? 'warn' : '');
    });

    head('Werkstatt');
    row('Master-Chat', {type: 'talk', id: 'master', title: 'Master-Chat'}, 'das Gespräch unten');
    const loaded = (models.recipes || []).find(r=>r.loaded);
    many('Modelle', {type: 'model', id: 'alle', title: 'Werkstatt'}, (models.recipes || []).length + (loaded ? ' · ' + loaded.id + ' geladen' : ' · keins geladen'), loaded ? 'ok' : '');
    row('Modell hinzufügen', {type: 'model', id: 'neu', title: 'Neues Modell'}, 'GGUF wählen, Rezept prüfen, Freigabe');
    row('Teststrecke', {type: 'model', id: 'teststrecke', title: 'Teststrecke'}, loaded ? 'Standardtest für ' + loaded.id : 'braucht ein geladenes Modell');
    row('KI Labor', {type: 'labor', id: 'ki', title: 'KI Labor'}, 'Anbieter, Modelle, Tests');
    row('Läufe', {type: 'labor', id: 'laeufe', title: 'KI Labor · Läufe'}, 'Protokolle der Modellläufe');

    head('Besatzung');
    const instances = (agents.instances || []).length;
    many('Rollen und Agenten', {type: 'agent', id: 'alle', title: 'Besatzung'}, instances ? instances + ' an Bord' : 'Rollen aus den Rezepten');

    head('Bibliothek');
    row('Eigene', {type: 'skill', id: 'eigene', title: 'Bibliothek · Eigene'}, String((library.custom || []).length));
    row('Fähigkeiten', {type: 'skill', id: 'own', title: 'Bibliothek'}, String((library.own || []).length));

    head('System');
    // Einstellungen: API, Hardware und Maschinenraum liegen in einer Untergruppe, die man aufklappt
    group('Einstellungen', 'Hardware · Maschinenraum');
    row('Hardware', {type: 'hardware', id: 'hardware', title: 'Hardware'}, '', '', 'Einstellungen');
    row('Maschinenraum', {type: 'machine', id: 'machine', title: 'Maschinenraum'}, '', '', 'Einstellungen');
    row('Module', {type: 'module', id: 'alle', title: 'Module', collection: true},
        (data.tools || 0) ? (data.tools + ' Werkzeuge') : '');
    row('Modus und Grenzen', {type: 'boundary', id: 'projekt', title: 'Modus und Grenzen'},
        (data.boundaries || {}).confirmed === false ? 'nicht bestätigt' : ((data.boundaries || {}).mode || ''),
        (data.boundaries || {}).confirmed === false ? 'warn' : '');
    row('Logbuch', {type: 'logbook', id: 'audit', title: 'Logbuch'}, '');
    row('Guppy-Meter', {type: 'meter', id: 'meter', title: 'Guppy-Meter'}, '');
    return rows;
  }

  function makeTree(host, shell){
    let rows = [], current = null;

    // Untergruppen (z. B. System · Einstellungen): der Gruppenkopf klappt auf und zu; eine Zeile mit `parent` sieht man nur offen.
    const opened = new Set();

    function render(){
      const box = d().el('div', 'tr-list');
      rows.forEach(r=>{
        if(r.kind === 'head'){
          const h = d().el('h4', 's-head', r.title);
          if(r.note) h.append(d().el('span', 'tr-note', ' ' + r.note));
          box.append(h); return;
        }
        if(r.kind === 'note'){ box.append(d().el('div', 'tr-empty', r.title)); return; }
        if(r.kind === 'group'){
          const isOpen = opened.has(r.title);
          const toggle = d().el('div', 'tr-row tr-group');
          toggle.append(d().el('span', 'tr-title', (isOpen ? '▾ ' : '▸ ') + r.title));
          if(r.note) toggle.append(d().el('small', 'tr-note', r.note));
          d().clickable(toggle, ()=>{ isOpen ? opened.delete(r.title) : opened.add(r.title); render(); });
          box.append(toggle);
          return;
        }
        if(r.parent && !opened.has(r.parent)) return;
        const key = r.object.type + ':' + r.object.id;
        const line = d().el('div', 'tr-row' + (key === current ? ' on' : '') + (r.tone ? ' ' + r.tone : ''));
        if(r.parent) line.style.paddingLeft = '1.4em';
        line.append(d().el('span', 'tr-title', r.title));
        if(r.note) line.append(d().el('small', 'tr-note', r.note));
        d().clickable(line, ()=>{ current = key; shell.openObject(r.object); render(); });
        box.append(line);
      });
      host.replaceChildren(box);
    }

    async function refresh(){
      const api = shell.api;
      const [missions, models, library, agents, status, intents, boundaries] = await Promise.all([
        api('/api/missions').catch(()=>[]), api('/api/models').catch(()=>({})),
        api('/api/library').catch(()=>({})), api('/api/agents').catch(()=>({})), api('/api/status').catch(()=>({})),
        api('/api/objects', {method: 'POST', body: {type: 'intent'}}).then(v=>v.items || []).catch(()=>[]),
        api('/api/boundaries').catch(()=>({}))
      ]);
      const project = (status.project || {});
      rows = treeModel({missions, models, library, agents, intents, boundaries,
                        tools: ((shell.ctx.manifest || {}).tools || []).length,     // steht schon im Manifest – keine zweite Route dafür
                        project: {name: project.name, path: project.path, id: project.name}});
      render();
    }

    function mark(object){ current = object ? object.type + ':' + object.id : null; render(); }

    return {refresh, render, mark};
  }

  root.sedraTree = {treeModel, makeTree};
  if(typeof module !== 'undefined' && module.exports) module.exports = {treeModel};
})();
