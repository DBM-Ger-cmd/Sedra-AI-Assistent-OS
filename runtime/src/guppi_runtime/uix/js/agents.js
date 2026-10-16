// Agent Manager window "Besatzung" (read-only): imported templates, assignments of the fake runtime, what needs attention.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.
// It only reads /api/agents. It has no button that starts, restarts or approves anything: those run through the Core and the Captain's gates.

const AGENT_TABS = [['org','Organigramm'],['overview','Übersicht'],['crew','Besatzung'],['crews','Crews'],['templates','Templates'],['missions','Missionen'],['attention','Aufmerksamkeit']];
const AGENT_STATES = {prepared:'… vorbereitet', running:'▶ läuft', succeeded:'✔ erfolgreich', failed:'✖ fehlgeschlagen (Ausgang bekannt)', in_doubt:'⚠ Ausgang ungewiss – Reconciliation erforderlich'};

let agentTab = 'org', agentView = null, agentSeenAt = null, agentError = null, agentsTimer = null;

function agentStateText(state){ return AGENT_STATES[state] || state; }

function agentTable(headers, rows){
  const t = el('table','agent-table'), head = el('tr');
  headers.forEach(h=>{ const c = el('th',null,h); c.scope = 'col'; head.append(c); });
  t.append(head);
  rows.forEach(r=>{ const tr = el('tr'); r.forEach(v=>tr.append(el('td',null,v === null || v === undefined ? '–' : String(v)))); t.append(tr); });
  return t;
}

function agentAttention(v){
  const items = [];
  (v.assignments||[]).filter(a=>a.state==='in_doubt').forEach(a=>items.push(['⚠ Ausgang ungewiss – Reconciliation erforderlich', a.assignment_id+' · '+a.agent_ref+' · Mission '+a.mission_id, 'Letzte bekannte Wirkung: '+(a.detail||'keine Angabe')]));
  (v.assignments||[]).filter(a=>a.state==='failed').forEach(a=>items.push(['✖ Fehlgeschlagen (Ausgang bekannt)', a.assignment_id+' · '+a.agent_ref, a.detail||'']));
  (v.templates||[]).filter(t=>!t.ok).forEach(t=>items.push(['⛔ Template abgelehnt', t.ref, 'Befunde: '+(t.problems||[]).join(', ')]));
  return items;
}

function renderAgents(){
  const box = document.getElementById('agentBody');
  if(!box) return;
  box.replaceChildren();
  const real = agentView && agentView.demo === false;
  box.append(el('div','agent-demo', real ? 'Echte Läufe: mindestens eine Zuweisung läuft auf der DevVM (Zustand siehe Reiter Missionen); Zuweisungen mit Demo-Markierung stammen von der Fake-Runtime. Alle Templates sind UNVERIFIED (ungeprüft) und haben keine Rechte.' : 'DEMO · Fake-Runtime: es laufen keine echten Agenten. Alle Templates sind UNVERIFIED (ungeprüft) und haben keine Rechte.'));
  const bar = el('div','agent-tabs');
  AGENT_TABS.forEach(([id,label])=>{
    const b = el('button','tool',label); b.setAttribute('aria-pressed', id===agentTab ? 'true' : 'false');
    if(id===agentTab) b.classList.add('on');
    b.onclick = ()=>{ agentTab = id; renderAgents(); };
    bar.append(b);
  });
  box.append(bar);
  const v = agentView;
  const stale = el('small','agent-stale', agentError ? 'Keine Verbindung zur Runtime – angezeigter Stand von '+(agentSeenAt||'unbekannt')+' ist veraltet ('+agentError+').' : (agentSeenAt ? 'Datenstand: beobachtet um '+agentSeenAt+' · Quelle: SEDRA-Runtime' : ''));
  if(!v){ box.append(el('div','muted','Daten werden geladen ...'), stale); return; }
  const body = el('div','agent-panel');
  if(agentTab === 'org'){
    renderOrgChart(body).catch(err=>body.append(el('div','mnote mbad','Organigramm nicht lesbar: '+err.message)));      // async, fills the panel when the views are in
  } else if(agentTab === 'overview'){
    const states = {}; (v.assignments||[]).forEach(a=>{ states[a.state] = (states[a.state]||0)+1; });
    const ok = (v.templates||[]).filter(t=>t.ok).length, bad = (v.templates||[]).length - ok, att = agentAttention(v).length;
    body.append(agentTable(['Bereich','Stand'], [
      ['Templates', (v.templates||[]).length+' ('+ok+' ohne Befund, '+bad+' abgelehnt) – alle ungeprüft'],
      ['Crews', (v.crews||[]).length ? (v.crews.length+' Vorlage(n); Zusammenstellung über die Kommandozeile (plan), sie empfiehlt nur') : 'keine'],
      ['Besatzung (Instanzen)', (v.instances||[]).length ? (v.instances.length+' ('+v.instances.filter(i=>i.qualification==='VERIFIED').length+' VERIFIED, '+v.instances.filter(i=>i.admission).length+' mit Zulassung)') : 'noch keine – Einstellung erfolgt über ein Gate des Captains'],
      ['Zuweisungen', (v.assignments||[]).length ? Object.entries(states).map(([s,n])=>agentStateText(s)+': '+n).join(' · ') : 'keine'],
      ['Aufmerksamkeit', att ? att+' Punkt(e), siehe Reiter Aufmerksamkeit' : 'nichts offen'],
      ['Ressourcen', 'noch nicht angebunden (Fake-Ports)']]));
  } else if(agentTab === 'crew'){
    const crew = v.instances||[];
    body.append(crew.length ? agentTable(['Instanz','Template','Stufe','Zulassung','Status','Abnahme (Suite)','Prüfung','Läufe'], crew.map(i=>[i.instance_id, i.template_ref, i.qualification, i.revoked ? '⛔ widerrufen' : (i.admission ? '✔ gültig' : '– keine'), i.lifecycle, i.suite ? (i.suite_passed+'/'+i.suite_total+' · '+i.suite) : 'nicht gelaufen', i.review||'–', i.successes+'/'+i.runs])) : el('div','muted','Noch keine Agenteninstanzen an Bord. Ein Template wird nur über ein Gate des Captains zur Instanz (UNVERIFIED, ohne Zulassung); dieses Fenster stellt nur dar.'));
  } else if(agentTab === 'crews'){
    body.append((v.crews||[]).length ? agentTable(['Crew','Zweck','Slots','Schritte','Prüfung der Vorlage'], v.crews.map(c=>[c.ref, c.purpose, c.slots, c.steps, (c.problems||[]).length ? '⛔ '+c.problems.join(', ') : '✔ ohne Befund'])) : el('div','muted','Keine Crew-Vorlagen importiert.'));
  } else if(agentTab === 'templates'){
    body.append((v.templates||[]).length ? agentTable(['Template','Rolle','Vertrauen','Prüfung der Vorlage'], v.templates.map(t=>[t.ref, t.role, t.trust+' (ungeprüft)', t.ok ? '✔ ohne Befund' : '⛔ '+(t.problems||[]).join(', ')])) : el('div','muted','Keine Templates importiert.'));
  } else if(agentTab === 'missions'){
    body.append((v.assignments||[]).length ? agentTable(['Zuweisung','Agent','Mission','Lauf','Zustand'], v.assignments.map(a=>[a.assignment_id, a.agent_ref, a.mission_id, a.run_id, (a.demo ? 'DEMO · ' : 'echt · ')+agentStateText(a.state)])) : el('div','muted','Keine Zuweisungen.'));
  } else {
    const items = agentAttention(v);
    if(!items.length) body.append(el('div','muted','Nichts offen.'));
    items.forEach(([what, who, more])=>{ const c = el('div','mcard'), info = el('div'); info.append(el('b',null,what), el('small',null,who), el('small',null,more)); c.append(info); body.append(c); });
    if(items.length) body.append(el('small','muted','Es gibt bewusst keine Schaltfläche „erneut starten“: ein ungewisser Lauf wird nur durch den Core abgeglichen.'));
  }
  box.append(body, stale);
}

async function refreshAgents(){
  try{
    agentView = await api('/api/agents');
    agentSeenAt = new Date().toLocaleTimeString('de-DE');
    agentError = null;
  }catch(err){ agentError = err.message; }
  renderAgents();
}

async function openAgents(){
  showWindow('agentWindow');
  await refreshAgents();
  if(!agentsTimer) agentsTimer = setInterval(()=>{
    const w = document.getElementById('agentWindow');
    if(w.classList.contains('active') && w.classList.contains('focused') && !document.hidden) refreshAgents();
  }, 8000);
}
