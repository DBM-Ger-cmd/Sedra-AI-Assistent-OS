// Cockpit shell – the tree (COCKPIT_MODUL_v1 §1: Projekt, Vorhaben/Aufgaben, Werkstatt, Besatzung, Bibliothek, System).
// It is navigation, nothing else: a row sends object.open and the dock decides what to draw. The tree never draws an object itself.
// treeModel() and sichtbar() are pure (data in, rows out) so node can judge them without a browser.
// Build 24 (Ticket B6-G-06, Klaus 15.10.2026): die Zeile „Routinen – noch nicht gebaut“ ist weg – kein Eintrag ohne Werkzeug dahinter
// (Nachtkette bleibt OPEN im Register). Das KI GateWay steht links im Baum mit seinen Ansichten (Captain-Entscheidung 19.10.2026, ersetzt Klaus 19:34).
// SPEC_COCKPIT_BAUM_v1 (Captain 26.10.2026, T1–T5): Wissen in der Bibliothek, „Gespräch unten“ entfällt, Sprache als Untergruppe der
// Werkstatt; jede Gruppe klappt (gemerkt in localStorage `sedra.cockpit.baum`, nur Namen), eine zugeklappte Gruppe sagt „⚠ n wartet“;
// nichts verschwindet still („… n weitere“), keine Missions-ID als Titel; Tastatur wie ein Baum (Pfeile, Pos1/Ende, roving tabindex).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const SPEICHER = 'sedra.cockpit.baum';
  const OFFEN_VORGABE = ['KI GateWay', 'Vorhaben', 'Aufgaben'];          // T4: beim ersten Start offen
  const MAX_VORHABEN = 8, MAX_AUFGABEN = 12;

  // der Satz zum Wissen unter der Zeile (rein): „hybrid · 85 % · 2 Vorschläge“, „nur Volltext“, „ausgeschaltet“
  function wissenNote(w){
    const st = w && w.stand;
    if(!w || w.state === 'aus' || !st) return {note: 'ausgeschaltet', tone: ''};
    const offen = st.vorschlaege_offen || 0;
    const teil = st.modus === 'hybrid' ? 'hybrid · ' + Math.round((st.abdeckung || 0) * 100) + ' %' : 'nur Volltext';
    return {note: teil + (offen ? ' · ' + offen + (offen === 1 ? ' Vorschlag' : ' Vorschläge') : ''), tone: offen ? 'warn' : ''};
  }

  // the rows of the tree from what the runtime says; every row carries the object it opens and its group
  function treeModel(data){
    const missions = data.missions || [], models = data.models || {}, library = data.library || {}, agents = data.agents || {};
    const project = data.project || {};
    const rows = [];
    let gruppe = '';
    const head = (title, note, schluessel)=>{ gruppe = schluessel || title; rows.push({kind: 'head', title, note: note || '', gruppe, schluessel: 'g:' + gruppe}); };
    const row = (title, object, note, tone, parent)=>rows.push({kind: 'row', title, object, note: note || '', tone: tone || '', parent: parent || '', gruppe, schluessel: keyOf(object)});
    const group = (title, note)=>rows.push({kind: 'group', title, note: note || '', gruppe, schluessel: 'g:' + title});
    // Eine Sammlung ist kein Werkstück: sie bekommt keine Nachweise daneben (siehe dock.js).
    const many = (title, object, note, tone)=>row(title, Object.assign({collection: true}, object), note, tone);
    const mehr = (n, object)=>rows.push({kind: 'row', title: '… ' + n + ' weitere', object: Object.assign({collection: true}, object), note: 'alle zeigen', tone: 'mehr',
                                         parent: '', gruppe, schluessel: 'mehr:' + object.type});

    // Das KI GateWay im Menü links: jede Ansicht ist ein Eintrag. Das Fenster bleibt eins; die Ansicht steht im Objekt.
    head('KI GateWay', 'Anfragen · Schutz');
    const gateway = (title, ansicht, note)=>row(title, {type: 'gateway', id: 'alle', title: 'KI GateWay · ' + title, collection: true, ansicht, imBaum: true}, note || '');
    gateway('Überblick', 'uebersicht', 'Stationen und was wartet');
    gateway('Vorgänge', 'vorgaenge', 'Anfragen anlegen und prüfen');
    gateway('Dateien', 'dateien', 'Originale und Fassungen');
    gateway('Regeln', 'regeln', 'Regelbuch und Schärfe');
    gateway('Selbst ausprobieren', 'ausprobieren', 'Text prüfen, Übung, Frage');
    gateway('Verlauf', 'verlauf', 'Vorgänge und Schutz heute');

    head('Projekt ' + (project.name || '–'), '', 'Projekt');
    row('Dateien', {type: 'project', id: project.id || project.name || 'projekt', title: 'Projekt ' + (project.name || '')}, project.path || '');

    // Vorhaben und Aufgaben sind zweierlei (Regel 8): das Vorhaben ist der Satz, die Aufgabe ist die Arbeit daraus.
    const intents = data.intents || [];
    head('Vorhaben', intents.length ? String(intents.length) : '');
    many('Alle Vorhaben', {type: 'intent', id: 'alle', title: 'Vorhaben'}, intents.length ? '' : 'noch keins – „＋ Neu“');
    intents.slice(0, MAX_VORHABEN).forEach(v=>row(v.title || 'Vorhaben ohne Titel', {type: 'intent', id: v.id, title: v.title || 'Vorhaben'}, v.state,
                                                  v.state === 'wartet auf dich' ? 'warn' : ''));
    if(intents.length > MAX_VORHABEN) mehr(intents.length - MAX_VORHABEN, {type: 'intent', id: 'alle', title: 'Vorhaben'});

    const open = missions.filter(m => (m.status || '') === 'active');
    head('Aufgaben', open.length ? open.length + ' offen' : '');
    if(!open.length) rows.push({kind: 'note', title: 'Nichts offen. Im Gespräch sagen, was gebaut werden soll.', gruppe});
    open.slice(0, MAX_AUFGABEN).forEach(m=>{
      const waits = (m.pending_gates || 0) > 0;
      const titel = String(m.intent || m.objective || '').trim() || 'Aufgabe ohne Titel';   // Regel 6: die Missions-ID gehört dem Logbuch
      row(titel.slice(0, 60), {type: 'task', id: m.mission_id, title: titel.slice(0, 40)},
          waits ? 'wartet auf dich' : (m.steps && m.steps.length ? 'Schritt ' + Math.min((m.steps_done || 0) + 1, m.steps.length) + ' von ' + m.steps.length : (m.phase || '')),
          waits ? 'warn' : '');
    });
    if(open.length > MAX_AUFGABEN) mehr(open.length - MAX_AUFGABEN, {type: 'task', id: 'alle', title: 'Aufgaben'});

    head('Werkstatt');
    const loaded = (models.recipes || []).find(r=>r.loaded);
    many('Modelle', {type: 'model', id: 'alle', title: 'Werkstatt'}, (models.recipes || []).length + (loaded ? ' · ' + loaded.id + ' geladen' : ' · keins geladen'), loaded ? 'ok' : '');
    row('Modell hinzufügen', {type: 'model', id: 'neu', title: 'Neues Modell'}, 'GGUF wählen, Rezept prüfen, Freigabe');
    row('Teststrecke', {type: 'model', id: 'teststrecke', title: 'Teststrecke'}, loaded ? 'Standardtest für ' + loaded.id : 'braucht ein geladenes Modell');
    row('KI Labor', {type: 'labor', id: 'ki', title: 'KI Labor'}, 'Anbieter, Modelle, Tests');
    row('Master-Chat', {type: 'entwurf', id: 'chat', title: 'Master-Chat · großes Gespräch'}, 'Gespräch mit vielen Berechtigungen, Befehle und Vorschau');   // Name nach Captain-Entscheidung 20.10.2026
    row('Läufe', {type: 'labor', id: 'laeufe', title: 'KI Labor · Läufe'}, 'Protokolle der Modellläufe');
    group('Sprache', 'Rekorder · Transkripte');                                                       // T2
    row('Rekorder', {type: 'aufnahme', id: 'rekorder', title: 'Rekorder'}, 'aufnehmen, Sprache → Text', '', 'Sprache');
    row('Transkripte', {type: 'transkript', id: 'alle', title: 'Transkripte'}, 'suchen, prüfen, Erkenntnisse', '', 'Sprache');

    head('Besatzung');
    const instances = (agents.instances || []).length;
    many('Rollen und Agenten', {type: 'agent', id: 'alle', title: 'Besatzung'}, instances ? instances + ' an Bord' : 'Rollen aus den Rezepten');

    head('Bibliothek');
    const w = wissenNote(data.wissen);                                                                 // T5
    row('Wissen', {type: 'wissen', id: 'speicher', title: 'Wissen'}, w.note, w.tone);
    if(data.wissensbasis) row('Wissens-Shell öffnen', {type: 'shell', id: 'wissensbasis', title: 'Wissensbasis'}, 'die Oberfläche nur für das Wissen – nimmt mit, was offen ist');
    const eigene = (library.custom || []).length, faehig = (library.own || []).length;
    row('Eigene', {type: 'skill', id: 'eigene', title: 'Bibliothek · Eigene'}, eigene ? eigene + ' eigene' : 'keine eigenen');
    row('Fähigkeiten', {type: 'skill', id: 'own', title: 'Bibliothek'}, faehig + (faehig === 1 ? ' Fähigkeit' : ' Fähigkeiten'));

    head('System');
    // Einstellungen: Hardware und Maschinenraum liegen in einer Untergruppe, die man aufklappt
    group('Einstellungen', 'Hardware · Maschinenraum');
    row('Hardware', {type: 'hardware', id: 'hardware', title: 'Hardware'}, 'GPU, Speicher, Engine', '', 'Einstellungen');
    row('Maschinenraum', {type: 'machine', id: 'machine', title: 'Maschinenraum'}, 'Prozesse, Sperren, Dienste', '', 'Einstellungen');
    row('Module', {type: 'module', id: 'alle', title: 'Module', collection: true}, (data.tools || 0) ? (data.tools + ' Werkzeuge') : '');
    row('Modus und Grenzen', {type: 'boundary', id: 'projekt', title: 'Modus und Grenzen'},
        (data.boundaries || {}).confirmed === false ? 'nicht bestätigt' : ((data.boundaries || {}).mode || ''),
        (data.boundaries || {}).confirmed === false ? 'warn' : '');
    row('Logbuch', {type: 'logbook', id: 'audit', title: 'Logbuch'}, 'jedes Ereignis, mit Prüfsumme');
    row('Guppy-Meter', {type: 'meter', id: 'meter', title: 'Guppy-Meter'}, 'Token, Zeilen, Kosten');

    // §3.2: was wartet, darf nicht zugeklappt verschwinden – Köpfe und Untergruppen zählen ihre wartenden Zeilen
    rows.forEach(h=>{
      if(h.kind === 'head') h.wartet = rows.filter(r=>r.kind === 'row' && r.gruppe === h.gruppe && r.tone === 'warn').length;
      if(h.kind === 'group') h.wartet = rows.filter(r=>r.kind === 'row' && r.parent === h.title && r.tone === 'warn').length;
    });
    return rows;
  }

  // der Schlüssel einer Zeile: Objekt und – falls da – seine Ansicht (das GateWay hat mehrere Einträge)
  function keyOf(object){ return object.type + ':' + object.id + (object.ansicht ? ':' + object.ansicht : ''); }

  // welche Zeilen man sieht (rein): eine zugeklappte Gruppe zeigt nur ihren Kopf
  function sichtbar(rows, offen){
    const auf = offen instanceof Set ? offen : new Set(offen || []);
    return rows.filter(r=>r.kind === 'head' || (auf.has(r.gruppe) && (!r.parent || auf.has(r.parent))));
  }

  // der gemerkte Zustand (rein): kaputt oder fremd → die Vorgabe aus T4
  function zustandLesen(roh){
    try{
      const v = JSON.parse(roh);
      if(v && Array.isArray(v.offen) && v.offen.every(x=>typeof x === 'string' && x.length <= 40)) return {offen: v.offen.slice(0, 40), aus: v.aus === true};
    }catch(_e){}
    return {offen: OFFEN_VORGABE.slice(), aus: false};
  }

  function makeTree(host, shell){
    let rows = [], current = null, fokus = null;
    let z = zustandLesen((()=>{ try{ return localStorage.getItem(SPEICHER); }catch(_e){ return null; } })());
    const offen = new Set(z.offen);
    const merken = ()=>{ try{ localStorage.setItem(SPEICHER, JSON.stringify({v: 1, offen: [...offen], aus: !!z.aus})); }catch(_e){} };
    const umschalten = name=>{ offen.has(name) ? offen.delete(name) : offen.add(name); fokus = 'g:' + name; merken(); render(); };

    function zeile(r){
      if(r.kind === 'note') return d().el('div', 'tr-empty', r.title);
      const istKopf = r.kind === 'head' || r.kind === 'group';
      const name = r.kind === 'head' ? r.gruppe : r.title;
      const auf = istKopf && offen.has(name);
      const line = d().el('div', istKopf ? (r.kind === 'head' ? 'tr-row tr-head' : 'tr-row tr-group') : 'tr-row' + (r.schluessel === current ? ' on' : '') + (r.tone ? ' ' + r.tone : ''));
      line.dataset.key = r.schluessel; line.dataset.gruppe = r.gruppe;
      line.setAttribute('role', 'treeitem'); line.tabIndex = -1;
      if(istKopf){
        line.setAttribute('aria-expanded', auf ? 'true' : 'false');
        line.append(d().el('span', 'tr-title', (auf ? '▾ ' : '▸ ') + r.title));
        const note = !auf && r.wartet ? '⚠ ' + r.wartet + ' wartet' : r.note;
        if(note) line.append(d().el('small', 'tr-note' + (!auf && r.wartet ? ' warn' : ''), note));
        line.onclick = ()=>umschalten(name);
      }else{
        if(r.parent) line.style.paddingLeft = '1.4em';
        line.append(d().el('span', 'tr-title', r.title));
        if(r.note) line.append(d().el('small', 'tr-note', r.note));
        line.onclick = ()=>{ fokus = r.schluessel; if(r.object.type !== 'shell') current = r.schluessel; shell.openObject(r.object); render(); };
      }
      line.onkeydown = e=>tasten(e, r, line, auf, name);
      return line;
    }

    // §3.5: ↑/↓ Zeile, → öffnet bzw. springt hinein, ← schließt bzw. springt zum Kopf, Enter/Leertaste, Pos1/Ende
    function tasten(e, r, line, auf, name){
      const alle = [...host.querySelectorAll('[role=treeitem]')], i = alle.indexOf(line);
      const geh = n=>{ if(n){ e.preventDefault(); fokus = n.dataset.key; alle.forEach(x=>{ x.tabIndex = x === n ? 0 : -1; }); n.focus(); } };
      const istKopf = r.kind !== 'row';
      if(e.key === 'ArrowDown') geh(alle[i + 1]);
      else if(e.key === 'ArrowUp') geh(alle[i - 1]);
      else if(e.key === 'Home') geh(alle[0]);
      else if(e.key === 'End') geh(alle[alle.length - 1]);
      else if(e.key === 'ArrowRight' && istKopf){ e.preventDefault(); if(!auf) umschalten(name); else geh(alle[i + 1]); }
      else if(e.key === 'ArrowLeft'){
        if(istKopf && auf){ e.preventDefault(); umschalten(name); }
        else geh(host.querySelector('[data-key="g:' + (r.parent || r.gruppe) + '"]') || (r.kind === 'group' ? host.querySelector('[data-key="g:' + r.gruppe + '"]') : null));
      }else if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); line.onclick(); }
    }

    function render(){
      const war = host.contains(document.activeElement) && document.activeElement.dataset ? document.activeElement.dataset.key : null;
      const box = d().el('div', 'tr-list'); box.setAttribute('role', 'tree'); box.setAttribute('aria-label', 'Navigation');
      let gruppeBox = null;
      sichtbar(rows, offen).forEach(r=>{
        if(r.kind === 'head'){ box.append(zeile(r)); gruppeBox = d().el('div', 'tr-gruppe'); gruppeBox.setAttribute('role', 'group'); box.append(gruppeBox); return; }
        (gruppeBox || box).append(zeile(r));
      });
      if(root.sedraWechsel && root.sedraWechsel.menuWahl) box.append(root.sedraWechsel.menuWahl());
      host.replaceChildren(box);
      // roving tabindex: nur eine Zeile ist per Tab erreichbar – die zuletzt benutzte, sonst die markierte, sonst die erste
      const alle = [...box.querySelectorAll('[role=treeitem]')];
      const ziel = alle.find(x=>x.dataset.key === (war || fokus)) || alle.find(x=>x.dataset.key === current) || alle[0];
      if(ziel){ ziel.tabIndex = 0; if(war) ziel.focus(); }
      const on = box.querySelector('.tr-row.on');
      if(on && on.scrollIntoView && !war) on.scrollIntoView({block: 'nearest'});
    }

    async function refresh(){
      const api = shell.api;
      const [missions, models, library, agents, status, intents, boundaries, wissen] = await Promise.all([
        api('/api/missions').catch(()=>[]), api('/api/models').catch(()=>({})),
        api('/api/library').catch(()=>({})), api('/api/agents').catch(()=>({})), api('/api/status').catch(()=>({})),
        api('/api/objects', {method: 'POST', body: {type: 'intent'}}).then(v=>v.items || []).catch(()=>[]),
        api('/api/boundaries').catch(()=>({})),
        api('/api/objects', {method: 'POST', body: {type: 'wissen', id: 'speicher'}}).catch(()=>null)
      ]);
      const project = (status.project || {});
      const m = shell.ctx.manifest || {};
      rows = treeModel({missions, models, library, agents, intents, boundaries, wissen,
                        wissensbasis: (m.shells || []).some(s=>(s.id || s) === 'wissensbasis'),
                        tools: (m.tools || []).length,     // steht schon im Manifest – keine zweite Route dafür
                        project: {name: project.name, path: project.path, id: project.name}});
      render();
    }

    function mark(object){ current = object ? keyOf(object) : null; render(); }

    // Strg+B (§3.6): der Baum blendet sich aus und ein; der Zustand steht neben den offenen Gruppen
    function ausblenden(an){ z.aus = an === undefined ? !z.aus : !!an; merken(); return z.aus; }

    return {refresh, render, mark, rows: ()=>rows, ausblenden, ausgeblendet: ()=>!!z.aus};
  }

  root.sedraTree = {treeModel, makeTree, sichtbar, zustandLesen, wissenNote, keyOf, OFFEN_VORGABE};
  if(typeof module !== 'undefined' && module.exports) module.exports = {treeModel, sichtbar, zustandLesen, wissenNote, keyOf};
})();
