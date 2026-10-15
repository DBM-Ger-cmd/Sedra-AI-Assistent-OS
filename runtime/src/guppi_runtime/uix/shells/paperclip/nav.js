// Paperclip-Shell – die Navigation links (Entwurf D, Spec §5.1).
// Firmenwörter für dieselben Objekte: „Posteingang“ ist die Entscheidungsliste, „Issues“ sind Aufgaben, „Ziele“ Vorhaben.
// Die Shell benennt um, sie baut nichts nach – jede Zeile ist ein Objekt, das ein vorhandenes Werkzeug zeichnet.
// Der Badge am Posteingang kommt aus GET /api/decisions, derselben Route wie überall (Regel 2: keine Zahl ohne Quelle).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const NAV = [
    {section: null},
    {label: 'Dashboard', object: {type: 'dashboard', id: 'start', title: 'Dashboard'}},
    {label: 'Posteingang', object: {type: 'decision', id: 'alle', title: 'Posteingang', collection: true}, badge: 'decisions'},
    {label: 'Issues', object: {type: 'task', id: 'alle', title: 'Issues', collection: true}},
    {label: 'Ziele', object: {type: 'intent', id: 'alle', title: 'Ziele', collection: true}},
    {label: 'Agenten', object: {type: 'agent', id: 'alle', title: 'Agenten', collection: true}},
    {label: 'Routinen', object: {type: 'routine', id: 'alle', title: 'Routinen', collection: true}},
    {label: 'Kosten', object: {type: 'meter', id: 'meter', title: 'Kosten'}},
    {section: 'Werkzeuge'},
    {label: 'Werkstatt (Modelle)', object: {type: 'model', id: 'alle', title: 'Werkstatt', collection: true}},
    {label: 'Bibliothek', object: {type: 'skill', id: 'own', title: 'Bibliothek'}},
    {label: 'Logbuch', object: {type: 'logbook', id: 'audit', title: 'Logbuch'}},
    {label: 'Module', object: {type: 'module', id: 'alle', title: 'Module', collection: true}},
    {section: 'Projekt'},
    {label: 'Dateien', object: {type: 'project', id: 'projekt', title: 'Projekt'}},
    {label: 'Modus und Grenzen', object: {type: 'boundary', id: 'projekt', title: 'Modus und Grenzen'}},
    {label: 'Maschinenraum', object: {type: 'machine', id: 'machine', title: 'Maschinenraum'}}
  ];

  // Welche Zeile zu einer Seite leuchtet (rein)
  function activeIndex(nav, object){
    if(!object) return -1;
    const key = object.type + ':' + object.id;
    return nav.findIndex(n=>n.object && (n.object.type + ':' + n.object.id) === key);
  }

  function makeNav(host, shell){
    const rows = [];

    function build(){
      host.replaceChildren();
      const company = d().el('div', 'pc-company');
      company.append(d().el('i', 'pc-mark'), d().el('span', null, 'SEDRA'));
      host.append(company);
      NAV.forEach((n, i)=>{
        if(n.section !== undefined){ if(n.section) host.append(d().el('small', 'pc-nav-section', n.section)); rows[i] = null; return; }
        const row = d().el('div', 'pc-nav-row');
        row.append(d().el('span', null, n.label));
        if(n.badge){ const b = d().el('span', 'pc-badge'); b.hidden = true; row.append(b); row.badge = b; }
        d().clickable(row, ()=>shell.openObject(n.object));
        host.append(row);
        rows[i] = row;
      });
    }

    function mark(object){
      const at = activeIndex(NAV, object);
      rows.forEach((row, i)=>{ if(row) row.classList.toggle('on', i === at); });
    }

    async function refresh(){
      let view = null;
      try{ view = await shell.api('/api/decisions'); }catch(_e){ return; }
      const n = ((view || {}).summary || {}).count || ((view || {}).items || []).length || 0;
      rows.forEach(row=>{ if(row && row.badge){ row.badge.textContent = String(n); row.badge.hidden = !n; } });
      return n;
    }

    return {build, mark, refresh, NAV};
  }

  root.sedraPcNav = {makeNav, activeIndex, NAV};
  if(typeof module !== 'undefined' && module.exports) module.exports = {activeIndex, NAV};
})();
