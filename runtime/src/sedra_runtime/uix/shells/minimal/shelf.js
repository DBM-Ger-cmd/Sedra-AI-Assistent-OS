// Minimal-Shell – die Ablage unten und die Entscheidungskarte rechts oben (Entwurf E, Spec §1.1; Build 19).
//
// Die Ablage öffnet Fenster; ein Punkt unter einem Feld heißt „dieses Fenster ist offen“. Seit Build 19 (Captain 15.10.:
// „man sollte selber unten weitere Aufgaben und Icons dazu anlegen können“) gehört sie dem Captain: Felder mit Bildzeichen,
// „＋“ legt eines an (ein Ort, das Fenster vorn, oder ein Auftrag an SEDRA), Rechtsklick verschiebt, benennt um, entfernt.
// Gemerkt wird sie in uix.yaml über `POST /api/uix/shelf` – nicht im Browser, denn SEDRA startet jedes Mal auf einem anderen
// Port, und der Browser-Speicher gehört dem Port. Ein Auftrag führt nichts aus: er geht als Satz ins Gespräch.
//
// Die Karte zeigt, was wartet, und antwortet über `POST /api/decisions/answer` – dieselbe Route wie jeder Knopf in einem
// Werkzeug. Sie ist kein zweiter Ort für Entscheidungen, sondern derselbe Ort an anderer Stelle (Regel 2).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Die Vorgabe, solange der Captain nichts eigenes gespeichert hat
  const SHELF = [
    {kind: 'object', label: 'Aufgaben', icon: 'aufgaben', object: {type: 'task', id: 'alle', title: 'Aufgaben', collection: true}},
    {kind: 'object', label: 'Vorhaben', icon: 'vorhaben', object: {type: 'intent', id: 'alle', title: 'Vorhaben', collection: true}},
    {kind: 'object', label: 'Projekt', icon: 'projekt', object: {type: 'project', id: 'projekt', title: 'Projekt'}},
    {kind: 'object', label: 'Werkstatt', icon: 'werkstatt', object: {type: 'model', id: 'alle', title: 'Werkstatt'}},
    {kind: 'object', label: 'Besatzung', icon: 'besatzung', object: {type: 'agent', id: 'alle', title: 'Besatzung'}},
    {kind: 'object', label: 'Bibliothek', icon: 'bibliothek', object: {type: 'skill', id: 'own', title: 'Bibliothek'}},
    {kind: 'object', label: 'Logbuch', icon: 'logbuch', object: {type: 'logbook', id: 'audit', title: 'Logbuch'}},
    {kind: 'place', label: 'Maschine', icon: 'maschine', place: 'machine'}
  ];

  // Was ein Feld öffnet: das Objekt (bei einem Ort aus der Ortskunde des Vertrags) – oder null bei einem Auftrag (rein)
  function resolve(entry, places){
    if(!entry) return null;
    if(entry.kind === 'object') return entry.object || null;
    if(entry.kind === 'place'){
      const p = (places || []).find(x=>x.id === entry.place);
      return p ? p.object : null;
    }
    return null;
  }

  // Welche Felder einen Punkt tragen (rein)
  function openMarks(shelf, openObjects, places){
    const keys = new Set((openObjects || []).map(o=>o.type + ':' + o.id));
    return shelf.map(e=>{
      const o = e.kind ? resolve(e, places) : e;      // ein nacktes Objekt (alte Form) zählt selbst
      return !!o && keys.has(o.type + ':' + o.id);
    });
  }

  // Ein Feld verschieben: neue Liste, die alte bleibt (rein)
  function move(items, index, by){
    const to = index + by;
    if(index < 0 || index >= items.length || to < 0 || to >= items.length) return items.slice();
    const out = items.slice();
    const [it] = out.splice(index, 1);
    out.splice(to, 0, it);
    return out;
  }

  function makeShelf(host, shell){
    let items = SHELF.slice(), own = false, fields = [];
    const places = ()=>(root.sedraPlaces && root.sedraPlaces.PLACES) || [];

    async function load(){
      try{
        const view = await shell.api('/api/uix/shelf');
        const mine = (view.shelf || {}).minimal;
        if(Array.isArray(mine) && mine.length){ items = mine; own = true; }
      }catch(err){ shell.onProblem('Ablage', err); }
      draw();
    }

    async function save(next, said){
      const out = await shell.api('/api/uix/shelf', {method: 'POST', body: {shell: 'minimal', items: next}});
      items = out.items && out.items.length ? out.items : SHELF.slice();
      own = !!(out.items && out.items.length);
      draw();
      if(said) shell.notify(said);
    }

    async function reset(){
      const out = await shell.api('/api/uix/shelf', {method: 'POST', body: {shell: 'minimal', items: null}});
      items = SHELF.slice(); own = false; draw();
      shell.notify('Ablage zurückgesetzt – es gilt wieder die Vorgabe.' + (out.status ? '' : ''));
    }

    function use(entry){
      if(entry.kind === 'auftrag'){ shell.sendToTalk(entry.text); return; }
      const object = resolve(entry, places());
      if(object) shell.openObject(object);
      else shell.notify('Diesen Ort kennt die Oberfläche nicht mehr: ' + (entry.place || entry.label), 'warn');
    }

    function draw(){
      host.replaceChildren();
      fields = items.map((entry, i)=>{
        const field = d().el('div', 'sh-min-app' + (entry.kind === 'auftrag' ? ' order' : ''));
        const object = resolve(entry, places());
        if(object) field.dataset.object = object.type + ':' + object.id;
        field.title = entry.kind === 'auftrag' ? 'Auftrag an SEDRA: ' + entry.text : entry.label + ' öffnen · Rechtsklick: anpassen';
        field.append(root.sedraMinIcons.iconEl(entry.icon || root.sedraMinIcons.typeIcon(object && object.type)), d().el('span', null, entry.label));
        d().clickable(field, ()=>use(entry));
        field.oncontextmenu = e=>{ e.preventDefault(); menuFor(field, i); };
        host.append(field);
        return field;
      });
      const add = d().el('div', 'sh-min-app add');
      add.title = 'Eigenes Feld anlegen: Ort, Fenster oder Auftrag an SEDRA';
      add.append(root.sedraMinIcons.iconEl('plus'), d().el('span', null, 'Neu'));
      d().clickable(add, ()=>edit(null));
      host.append(add);
      mark();
    }

    function menuFor(field, i){
      const rows = [
        ['Nach links', ()=>save(move(items, i, -1))],
        ['Nach rechts', ()=>save(move(items, i, 1))],
        ['Ändern …', ()=>edit(i)],
        ['Entfernen', ()=>save(items.filter((_e, k)=>k !== i), '„' + items[i].label + '“ ist aus der Ablage entfernt.')]
      ];
      if(own) rows.push(['Ablage zurücksetzen', ()=>reset()]);
      shell.menubar.popup(field, rows);
    }

    function edit(i){
      root.sedraMinShelfEdit.open(host, shell, {
        entry: i === null ? null : items[i],
        front: shell.windows.front(),
        done: entry=>{
          const next = items.slice();
          if(i === null) next.push(entry); else next[i] = entry;
          return save(next, i === null ? '„' + entry.label + '“ liegt jetzt in der Ablage.' : '„' + entry.label + '“ ist geändert.');
        }
      });
    }

    function mark(){
      openMarks(items, shell.windows.list(), places()).forEach((on, i)=>fields[i] && fields[i].classList.toggle('on', on));
    }

    function pin(object){
      if(!object || object.type === 'talk') return;
      edit(null);
      root.sedraMinShelfEdit.prefill({kind: 'object', object, label: String(object.title || object.id).slice(0, 24)});
    }

    draw();
    return {mark, load, pin, reset, items: ()=>items.slice(), get fields(){ return fields; }};
  }

  function makeNote(host, shell){
    const box = d().el('div', 'sh-min-note');
    box.hidden = true;
    host.append(box);

    async function refresh(){
      let view;
      try{ view = await shell.api('/api/decisions'); }
      catch(err){ shell.onProblem('Entscheidungen', err); return; }
      const items = (view.items || []);
      box.replaceChildren();
      box.hidden = !items.length;
      if(!items.length) return;
      const first = items[0];
      box.append(d().el('b', null, first.title || 'Entscheidung'));
      box.append(d().el('small', null, first.describe || ''));
      const row = d().el('div', 'sh-min-note-ways');
      (first.ways || []).forEach(way=>{
        row.append(d().button(wayLabel(way), async()=>{
          await shell.decide(first.id, way);
          await refresh();
        }, way === (first.ways || [])[0] ? 'p' : ''));
      });
      box.append(row);
      if(items.length > 1){
        const more = d().el('small', 'sh-min-note-more', 'und ' + (items.length - 1) + ' weitere – im Fenster „Entscheidungen“');
        d().clickable(more, ()=>shell.openObject({type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true}));
        box.append(more);
      }
    }

    return {refresh, box};
  }

  // Die Wege heißen beim Captain wie im Cockpit – ein Wort, kein Code
  function wayLabel(way){
    return {einmal: 'Einmal öffnen', aendern: 'Grenze ändern …', ablehnen: 'Ablehnen',
            freigeben: 'Freigeben', freigeben_und_anwenden: 'Freigeben und anwenden'}[way] || way;
  }

  root.sedraMinShelf = {makeShelf, makeNote, openMarks, wayLabel, resolve, move, SHELF};
  if(typeof module !== 'undefined' && module.exports) module.exports = {openMarks, wayLabel, resolve, move, SHELF};
})();
