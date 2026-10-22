// Paperclip-Shell – die Navigation links (Entwurf D, Spec §5.1; Spec 4 D4.1).
// Firmenwörter für dieselben Objekte: „Posteingang“ ist die Entscheidungsliste, „Issues“ sind Aufgaben, „Ziele“ Vorhaben.
// Die Shell benennt um, sie baut nichts nach – jede Zeile ist ein Objekt; wer es zeichnet, sagt die Registrierung.
// Der Badge am Posteingang kommt aus GET /api/decisions, derselben Route wie überall (Regel 2: keine Zahl ohne Quelle).
// Spec 4 (G2-S4-01): Abschnitte Arbeit, Team, Betrieb. Einträge bleiben stehen, auch wenn ihr Werkzeug noch fehlt oder die
// Orchestrierung aus ist – die Seite sagt dann, warum sie leer ist (UIX-02, UIX-10). Das ersetzt die Regel aus Build 24
// („kein Eintrag ohne Werkzeug“) für Routinen. Das KI GateWay bleibt in seiner eigenen Oberfläche (Klaus 15.10. 19:34).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // Issues sind der Desk-Typ `issue`, sobald ihn ein Werkzeug zeichnet; bis dahin die Missionen (G1-S4-06, D4.1)
  const ISSUES = {type: 'issue', id: 'alle', title: 'Issues', collection: true};
  const ISSUES_ERSATZ = {type: 'task', id: 'alle', title: 'Issues', collection: true};

  const NAV = [
    {section: null},
    {label: 'Dashboard', object: {type: 'dashboard', id: 'start', title: 'Dashboard'}},
    {label: 'Posteingang', object: {type: 'decision', id: 'alle', title: 'Posteingang', collection: true}, badge: 'decisions'},
    {section: 'Arbeit'},
    {label: 'Issues', object: ISSUES, issues: true},
    {label: 'Ziele', object: {type: 'intent', id: 'alle', title: 'Ziele', collection: true}},
    {label: 'Routinen', object: {type: 'routine', id: 'alle', title: 'Routinen', collection: true}},
    {section: 'Team'},
    {label: 'Organigramm', object: {type: 'agent', id: 'alle', title: 'Organigramm', collection: true}},
    {label: 'Agenten', object: {type: 'agent', id: 'rollen', title: 'Agenten', collection: true}},
    {section: 'Betrieb'},
    {label: 'Kosten', object: {type: 'meter', id: 'meter', title: 'Kosten'}},
    {label: 'Modelle und Slots', object: {type: 'model', id: 'alle', title: 'Modelle und Slots', collection: true}},
    {label: 'KI-Labor', object: {type: 'labor', id: 'labor', title: 'KI-Labor'}},
    {section: 'Assistenten'},     // 19.10.2026: die Arbeitsumgebung der KI-Assistenten – im Gespräch Ziele und Aufträge festlegen
    {label: 'Planungstisch', object: {type: 'planung', id: 'tisch', title: 'Planungstisch'}},
    {label: 'Rekorder', object: {type: 'aufnahme', id: 'rekorder', title: 'Rekorder'}},      // Kern Sprache (19.10.): aufnehmen, Sprache → Text
    {section: 'Werkzeuge'},       // die Werkstatt steht jetzt unter „Modelle und Slots“ (derselbe Ort hat nur eine Zeile)
    {label: 'Bibliothek', object: {type: 'skill', id: 'own', title: 'Bibliothek'}},
    {label: 'Logbuch', object: {type: 'logbook', id: 'audit', title: 'Logbuch'}},
    {label: 'Wissen', object: {type: 'wissen', id: 'speicher', title: 'Wissen'}},      // Spec 7 (D7.9, G2-S7-u): der Wissensspeicher
    {label: 'Module', object: {type: 'module', id: 'alle', title: 'Module', collection: true}},
    {section: 'Projekt'},
    {label: 'Dateien', object: {type: 'project', id: 'projekt', title: 'Projekt'}},
    {label: 'Modus und Grenzen', object: {type: 'boundary', id: 'projekt', title: 'Modus und Grenzen'}},
    {label: 'Maschinenraum', object: {type: 'machine', id: 'machine', title: 'Maschinenraum'}}
  ];

  // Welches Objekt „Issues“ öffnet (rein): `issue:alle`, wenn ein Werkstück-Werkzeug es zeichnet, sonst die Missionen
  function issuesTarget(tools){
    const drawn = tools && typeof tools.forObject === 'function' ? tools.forObject(ISSUES).filter(m=>m.slot !== 'nachweis') : [];
    return drawn.length ? ISSUES : ISSUES_ERSATZ;
  }

  // Das Objekt einer Zeile (oder Karte) in dieser Registrierung (rein)
  function target(entry, tools){
    return entry.issues ? issuesTarget(tools) : entry.object;
  }

  // Die Zahl des Badges aus GET /api/decisions (rein): Posteingang = offene Entscheidungen
  function badgeCounts(decisions){
    const n = ((decisions || {}).summary || {}).count || ((decisions || {}).items || []).length || 0;
    return {decisions: n};
  }

  // Welche Zeile zu einer Seite leuchtet (rein). Die Ansicht (`view`) zählt nicht; „Issues“ leuchtet für beide Ziele.
  function activeIndex(nav, object){
    if(!object) return -1;
    const key = o=>o.type + ':' + o.id;
    return nav.findIndex(n=>n.object && (key(n.object) === key(object) || (n.issues && key(ISSUES_ERSATZ) === key(object))));
  }

  // Ereignisse kommen in Schüben: ein Lesen läuft, ein weiteres wird gemerkt – kein Zeitgeber, keine Schlange (D4.6, rein)
  function coalesce(fn){
    let running = null, again = false;
    function run(){
      if(running){ again = true; return running; }
      running = Promise.resolve().then(fn).finally(()=>{
        running = null;
        if(again){ again = false; run(); }
      });
      return running;
    }
    return run;
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
        d().clickable(row, ()=>shell.openObject(target(n, shell.ctx.tools)));
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

  root.sedraPcNav = {makeNav, activeIndex, badgeCounts, issuesTarget, target, coalesce, NAV, ISSUES, ISSUES_ERSATZ};
  if(typeof module !== 'undefined' && module.exports) module.exports = {activeIndex, badgeCounts, issuesTarget, target, coalesce, NAV, ISSUES, ISSUES_ERSATZ};
})();
