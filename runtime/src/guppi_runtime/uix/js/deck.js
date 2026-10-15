// Deck: the start window. One sentence about the state, one input ("Was willst du tun?"), three columns:
// what waits for the Captain (gates and open change requests), what is in work (cards), who and what is on board (model, crew, budget).
// Read-only apart from the input, which goes through runCommand() (command.js). Every row opens the window where the action is.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

let deckTimer = null, deckLast = null;

// one sentence, from the pieces that are there; a missing piece never hides the others
function deckSentence(st, models, gates, missionsRunning){
  const parts = [];
  if(!st) parts.push('Keine Verbindung zur Runtime.');
  else parts.push('SEDRA ist '+st.system_state+'.');
  const srv = models && models.server;
  if(models) parts.push(srv && srv.running ? (srv.model||'Ein Modell')+' läuft'+(srv.context ? ' mit Kontext '+srv.context : '')+'.' : 'Kein Modell geladen.');
  if(gates) parts.push(gates === 1 ? 'Eine Freigabe wartet auf dich.' : gates+' Freigaben warten auf dich.');
  else if(missionsRunning) parts.push(missionsRunning === 1 ? 'Eine Karte ist in Arbeit.' : missionsRunning+' Karten sind in Arbeit.');
  else if(st) parts.push('Nichts wartet.');
  return parts.join(' ');
}

// the next sensible steps as chips, from the state (no model → load one; no project → make one; gates → look at them)
function deckChips(st, models, gates, projects){
  const chips = [];
  const loaded = models && models.recipes && models.recipes.some(r=>r.loaded);
  const withModel = models && models.recipes && models.recipes.filter(r=>r.model && r.enabled && r.provider === 'llama-cpp-server');
  if(gates) chips.push(['Freigaben ansehen', ()=>openBridge()]);
  if(models && !loaded) chips.push(withModel && withModel.length ? ['Modell laden', ()=>openModels()] : ['Neues Modell hinzufügen', ()=>openModelAdd()]);
  if(models && loaded) chips.push(['Teststrecke', ()=>openModelsAt('Teststrecke')]);
  if(projects && !projects.length) chips.push(['Neues Projekt anlegen', ()=>createProject()]);
  chips.push(['Mit GUPPI sprechen', ()=>openGuppi()]);
  if(loaded) chips.push(['Als Karte planen …', ()=>{ const i = document.getElementById('deckInput'); i.value = '/plan '; i.focus(); }]);
  return chips.slice(0, 4);
}

function deckColumn(title, count){
  const col = el('section','deck-col');
  const h = el('h3',null,title); if(count !== undefined) h.append(el('span','deck-count',String(count)));
  col.append(h);
  return col;
}

function deckRow(title, sub, onclick, tone){
  const r = el('div','deck-row'+(tone ? ' '+tone : ''));
  r.append(el('b',null,title)); if(sub) r.append(el('small',null,sub));
  if(onclick){ r.setAttribute('role','button'); r.tabIndex = 0; r.onclick = onclick; r.onkeydown = e=>{ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); onclick(); } }; }
  return r;
}

function buildDeck(box, d){
  const st = d.status.ok ? d.status.v : null, models = d.models.ok ? d.models.v : null, missions = d.missions.ok ? d.missions.v : [];
  const agents = d.agents.ok ? d.agents.v : null, meter = d.meter.ok ? d.meter.v : null, projects = d.projects.ok ? d.projects.v : null;
  const groups = bridgeGroups(missions), running = groups[1][1], done = groups[2][1], failed = groups[3][1];
  const requests = (models && models.open_requests) || [], requestIds = new Set(requests.map(r=>r.mission_id));
  const waiting = groups[0][1].filter(m=>!requestIds.has(m.mission_id));          // a change request is shown once, as a request
  const gates = waiting.reduce((n,m)=>n + (m.pending_gates||0), 0);

  box.append(el('div','deck-sentence', deckSentence(st, models, gates + requests.length, running.length)));
  const form = el('div','deck-ask');
  const input = el('input'); input.id = 'deckInput'; input.placeholder = 'Was willst du tun? – z. B. „neues Modell“, „Erkläre mir die Schalter“, „Baue einen Parser für …“';
  input.setAttribute('aria-label','Kommando');
  const go = el('button','send','Los'); go.onclick = ()=>{ const t = input.value.trim(); if(!t) return; input.value = ''; runCommand(t); };
  input.onkeydown = e=>{ if(e.key === 'Enter'){ e.preventDefault(); go.click(); } };
  form.append(input, go); box.append(form);
  const chips = el('div','deck-chips');
  deckChips(st, models, gates + requests.length, projects).forEach(([label, fn])=>{ const b = el('button','tool',label); b.onclick = fn; chips.append(b); });
  chips.append(el('small','muted','Strg+K öffnet das Kommando von überall · /plan für einen Auftrag'));
  box.append(chips);

  const cols = el('div','deck-cols');
  const c1 = deckColumn('Wartet auf dich', waiting.length + requests.length);
  if(!waiting.length && !requests.length) c1.append(el('div','muted','Nichts. Freigaben erscheinen hier zuerst.'));
  waiting.slice(0, 8).forEach(m=>c1.append(deckGateRow(m)));
  requests.forEach(r=>c1.append(deckRequestRow(r)));
  if(failed.length) failed.slice(0, 3).forEach(m=>c1.append(deckRow(String(m.intent||m.mission_id).slice(0, 80), 'fehlgeschlagen · Ursache im Logbuch', ()=>missionWorkflow(m.mission_id), 'bad')));

  const c2 = deckColumn('In Arbeit', running.length);
  if(!running.length) c2.append(el('div','muted','Keine Karte in Arbeit. Ein Auftrag im Kommando oder /plan legt eine an.'));
  running.slice(0, 8).forEach(m=>{
    const r = deckRow(String(m.intent||m.objective||m.mission_id).slice(0, 80), (PHASE_LABEL[m.phase]||m.phase||'?')+' · '+m.mission_id+(m.steps && m.steps.length ? ' · Schritt '+Math.min(m.steps_done + 1, m.steps.length)+' von '+m.steps.length : ''), ()=>missionWorkflow(m.mission_id));
    if(m.steps && m.steps.length) r.append(renderSeaChart(deckChartRecord(m)));
    c2.append(r);
  });
  if(done.length){ c2.append(el('div','deck-sub','Zuletzt fertig')); done.slice(0, 3).forEach(m=>c2.append(deckRow(String(m.intent||m.mission_id).slice(0, 80), 'fertig · '+m.mission_id, ()=>missionWorkflow(m.mission_id), 'ok'))); }

  const c3 = deckColumn('Besatzung und Maschine');
  const srv = models && models.server, loaded = models && models.recipes && models.recipes.find(r=>r.loaded);
  c3.append(deckRow('Modell', !models ? 'nicht lesbar' : (srv && srv.running) ? (loaded ? modelName(loaded) : srv.model)+(srv.context ? ' · Kontext '+srv.context : '') : 'keins geladen – Werkstatt öffnen', ()=>openModels(), models && srv && srv.running ? 'ok' : 'warn'));
  if(models && models.profiles) c3.append(deckRow('Modellkombination', models.profiles.active || '–', ()=>openModelsAt('Modellkombination')));
  if(agents){
    const inst = agents.instances||[], runs = (agents.assignments||[]).filter(a=>a.state === 'running').length;
    c3.append(deckRow('Besatzung', (inst.length ? inst.length+' Agent'+(inst.length===1?'':'en')+' an Bord' : 'noch keine Agenten an Bord')+(runs ? ' · '+runs+' läuft' : ''), ()=>openAgents()));
  }
  const today = meter && meter.tokens && meter.tokens.ranges && meter.tokens.ranges.today;
  if(today) c3.append(deckRow('Token heute', meterNumber(today.tokens)+' ('+today.runs+' Läufe)', ()=>openMeter()));
  if(st){
    const dev = st.development_environment || {};
    c3.append(deckRow('Entwicklungsumgebung', dev.execution_ready ? 'bereit' : 'blockiert ('+(dev.blockers||[]).length+')', ()=>openDevEnv(), dev.execution_ready ? 'ok' : 'warn'));
    c3.append(deckRow('Runtime', st.system_state+' · '+(st.capability_router||{}).skills+' Skills', ()=>openMachineRoom()));
  }
  if(projects) c3.append(deckRow('Projekte', projects.length ? projects.length+' registriert'+(activeProject ? ' · aktiv: '+activeProject : '') : 'noch keins', ()=>openProjectRegistry()));
  cols.append(c1, c2, c3); box.append(cols);
}

async function refreshDeck(){
  const live = document.getElementById('deckBody');
  if(!live) return;
  const typing = document.activeElement && document.activeElement.id === 'deckInput' && document.activeElement.value;
  if(typing) return;                                                        // never redraw under the Captain's hands
  const get = (p, ms)=>Promise.race([api(p).then(v=>({ok:true, v}), e=>({ok:false, e:e.message})), new Promise(res=>setTimeout(()=>res({ok:false, e:'Zeitlimit'}), ms || 8000))]);
  const [status, models, missions, agents, meter, projects] = await Promise.all([get('/api/status'), get('/api/models'), get('/api/missions'), get('/api/agents', 4000), get('/api/meter', 4000), get('/api/projects')]);
  const box = el('div');
  try{ buildDeck(box, {status, models, missions, agents, meter, projects}); }
  catch(err){ box.append(el('div','mnote mbad','Deck nicht darstellbar: '+err.message)); }
  if(deckLast === box.innerHTML) return;
  const hadFocus = document.activeElement && document.activeElement.id === 'deckInput';
  live.replaceChildren(...box.childNodes); deckLast = live.innerHTML;
  if(hadFocus) document.getElementById('deckInput').focus();
}

async function openDeck(){
  showWindow('deckWindow');
  await refreshDeck();
  const i = document.getElementById('deckInput'); if(i) i.focus();
  if(!deckTimer) deckTimer = setInterval(()=>{
    const w = document.getElementById('deckWindow');
    if(w.classList.contains('active') && !document.hidden) refreshDeck();
  }, 5000);
}

// the compact mission of /api/missions as the record chartModel() reads (plan steps, done results, pending gates)
function deckChartRecord(m){
  return {lifecycle:{phase:m.phase}, plan:{steps:(m.steps||[]).map((d,i)=>({id:String(i+1), description:d}))},
          execution:{results:new Array(m.steps_done||0).fill(1)}, human_gates:{pending:new Array(m.pending_gates||0).fill({})}};
}

// a card that waits for the Captain: each gate with action, targets and risks, approve or reject right here (Freigabe-Leiste, G5/G7)
function deckGateRow(m){
  const r = el('div','deck-row warn');
  r.append(el('b',null,String(m.intent||m.objective||m.mission_id).slice(0, 80)));
  r.append(el('small',null,(PHASE_LABEL[m.phase]||m.phase||'?')+' · '+m.mission_id));
  (m.gates||[]).forEach(g=>{
    const box = el('div','deck-gate');
    box.append(el('div',null,'Freigabe: '+(g.action||'Aktion')+((g.targets||[]).length ? ' → '+g.targets.join(', ') : '')));
    if((g.risks||[]).length) box.append(el('small',null,'Risiken: '+g.risks.join(', ')));
    box.append(el('small',null,'gilt nur einmal · Rücknahme '+(g.rollback ? 'möglich' : 'nicht möglich')));
    const row = el('div','row');
    row.append(deckButton('Freigeben', 'action', async()=>{
      if(!confirm('Genau diese Aktion einmal freigeben?\n\n'+(g.action||'')+'\n'+(g.targets||[]).join(', '))) return;
      await api('/api/mission/approve',{method:'POST',body:JSON.stringify({mission_id:m.mission_id, gate_id:g.gate_id})});
      deckLast = null; await refreshDeck();
    }));
    row.append(deckButton('Ablehnen', 'tool', async()=>{
      await api('/api/mission/reject',{method:'POST',body:JSON.stringify({mission_id:m.mission_id, gate_id:g.gate_id})});
      deckLast = null; await refreshDeck();
    }));
    row.append(deckButton('Karte öffnen', 'tool', ()=>missionWorkflow(m.mission_id)));
    box.append(row); r.append(box);
  });
  if(!(m.gates||[]).length) r.append(deckButton('Karte öffnen', 'tool', ()=>missionWorkflow(m.mission_id)));
  return r;
}

const DECK_APPLY = {switch:'/api/switch/apply', routing:'/api/routing-config/apply', model_add:'/api/model/add/apply', skill:'/api/library/custom/apply'};

// a change request from the chat, the Werkstatt or the Bibliothek: approve and apply in one go, or reject
function deckRequestRow(req){
  const b = req.binding||{}, r = el('div','deck-row warn');
  r.append(el('b',null,b.describe || (req.kind === 'switch' ? 'Schalter umstellen' : req.kind === 'skill' ? 'Eigenen Skill schreiben' : 'Modell-Einstellung ändern')));
  r.append(el('small',null,{switch:'Schalter · gilt nach dem Neustart der Oberfläche', routing:'Modell-Einstellung · gilt nach dem Neustart', model_add:'Neues Modell · sofort nutzbar', skill:'Bibliothek · die Datei wird vorher gesichert'}[req.kind] || req.kind));
  const row = el('div','row');
  row.append(deckButton('Freigeben und anwenden', 'action', async()=>{
    await api('/api/mission/approve',{method:'POST',body:JSON.stringify({mission_id:req.mission_id, gate_id:req.gate.gate_id})});
    await api(DECK_APPLY[req.kind],{method:'POST',body:JSON.stringify({mission_id:req.mission_id})});
    if(typeof pendingChange !== 'undefined' && pendingChange && pendingChange.mission_id === req.mission_id) pendingChange = null;
    deckLast = null; await refreshDeck();
  }));
  row.append(deckButton('Ablehnen', 'tool', async()=>{
    await api('/api/mission/reject',{method:'POST',body:JSON.stringify({mission_id:req.mission_id, gate_id:req.gate.gate_id})});
    if(typeof pendingChange !== 'undefined' && pendingChange && pendingChange.mission_id === req.mission_id) pendingChange = null;
    deckLast = null; await refreshDeck();
  }));
  if(b.block || b.text){ const det = el('details'); det.append(el('summary',null,'Genau dieser Text')); const pre = el('pre','diag-out'); pre.textContent = b.block || b.text; det.append(pre); r.append(det); }
  r.append(row);
  return r;
}

// a button in a Deck row: the row's own click must not fire, an error shows in the row instead of vanishing
function deckButton(label, cls, fn){
  const b = el('button', cls, label);
  b.onclick = async e=>{
    e.stopPropagation(); b.disabled = true;
    try{ await fn(); }catch(err){ b.disabled = false; const note = el('small','deck-err','Fehlgeschlagen: '+err.message); b.after(note); setTimeout(()=>note.remove(), 8000); }
  };
  return b;
}
