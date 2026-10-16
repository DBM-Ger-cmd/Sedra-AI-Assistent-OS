// Paperclip-Shell – die Navigation links (Entwurf D, Spec §5.1).
// Firmenwörter für dieselben Objekte: „Posteingang“ ist die Entscheidungsliste, „Issues“ sind Aufgaben, „Ziele“ Vorhaben.
// Die Shell benennt um, sie baut nichts nach – jede Zeile ist ein Objekt, das ein vorhandenes Werkzeug zeichnet.
// Der Badge am Posteingang kommt aus GET /api/decisions, derselben Route wie überall (Regel 2: keine Zahl ohne Quelle).
// Build 24 (Ticket B6-G-06): „Routinen“ ist weg – kein Eintrag ohne Werkzeug dahinter. Das KI GateWay bleibt in seiner eigenen
// Oberfläche (Klaus 15.10. 19:34); hier ist es über das Suchfeld (Strg+K) und den Umschalter erreichbar.

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

  // Die Zahl des Badges aus GET /api/decisions (rein): Posteingang = offene Entscheidungen
  function badgeCounts(decisions){
    const n = ((decisions || {}).summary || {}).count || ((decisions || {}).items || []).length || 0;
    return {decisions: n};
  }

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
        if(n.badge){ const b = d().el('span', 'pc-badge'); b.hidden = true; b.dataset.badge = n.badge; row.append(b); row.badge = b; }
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
      const counts = badgeCounts(await shell.api('/api/decisions').catch(()=>null));
      rows.forEach(row=>{
        if(!row || !row.badge) return;
        const n = counts[row.badge.dataset.badge] || 0;
        row.badge.textContent = String(n); row.badge.hidden = !n;
      });
      return counts;
    }

    return {build, mark, refresh, NAV};
  }

  root.sedraPcNav = {makeNav, activeIndex, badgeCounts, NAV};
  if(typeof module !== 'undefined' && module.exports) module.exports = {activeIndex, badgeCounts, NAV};
})();
