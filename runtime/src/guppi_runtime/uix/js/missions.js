// Missions: list, plan card, run and gates in the chat, bridge, mission workflow, code candidates.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

async function refreshMissions(){
  try{
    const missions=await api('/api/missions');
    const box=document.getElementById('missionList');
    if(!box) return;
    if(!missions.length){box.innerHTML='<div class="mission"><span>Noch keine Mission</span><span class="badge">LEER</span></div>';return;}
    box.innerHTML=missions.slice(-6).reverse().map(m=>
      '<div class="mission"><span>'+escapeHtml((m.intent||m.objective||m.mission_id).slice(0,70))+'</span><span class="badge">'+escapeHtml(m.phase||'')+'</span></div>'
    ).join('');
  }catch(err){console.warn(err);}
}

async function loadMissionsIntoChat(){
  openGuppi();
  try{
    const missions=await api('/api/missions');
    const chat=document.getElementById('chat');
    const lines=missions.length?missions.slice(-8).reverse().map(m=>'• '+escapeHtml(String(m.mission_id))+' · '+escapeHtml(String(m.phase))+' · '+escapeHtml(String(m.intent||m.objective||''))).join('<br>'):'Noch keine Missionen vorhanden.';
    chat.insertAdjacentHTML('beforeend','<div class="msg"><div class="av"></div><div class="bub"><b>GUPPI:</b> Aktuelle Missionen:<br>'+lines+'</div></div>');
  }catch(err){console.warn(err);}
}

function phaseBadge(phase){
  const bad = ['FAILED'].includes(phase), ok = ['COMPLETE','READY'].includes(phase);
  return el('span','phase'+(bad?' bad':ok?'':' warn'), phase||'?');
}

// Mission card: plan, phase, result, open gates; rebuilt from the mission record after every action.
// While `running` (the run call has not returned yet) the card shows the live phase and offers no second run.
function renderMission(body, m, running){
  const mid = m.identity.mission_id, phase = (m.lifecycle||{}).phase, plan = m.plan||{};
  const pending = (m.human_gates||{}).pending||[];
  const res = (m.result && m.result.qualification !== 'PENDING') ? m.result : null;   // READY missions carry a PENDING placeholder
  body.replaceChildren();
  const head = el('div'); head.append(el('span',null,'Mission '), el('b',null,mid+' '), phaseBadge(phase));
  if(running) head.append(el('span','phase warn','läuft … '+((m.lifecycle||{}).status||'')));
  body.append(head);
  const steps = plan.steps||[];
  if(steps.length){
    const ol = el('ol'); steps.forEach(st=>ol.append(el('li',null,(st.description||st.action||st.id)+(st.action?' ('+st.action+')':''))));
    body.append(ol);
  }
  body.append(renderSeaChart(m));      // where the mission is: harbour → steps → destination, barrier at an open gate
  const skills = (plan.selected_skills||[]).join(', ')||'keine', tools = (plan.selected_tools||[]).join(', ')||'keine';
  body.append(el('div','muted','Skills: '+skills+' · Tools: '+tools+' · Risiko: '+((plan.risk||{}).level||(m.risk||{}).level||'?')));
  const gaps = (m.capability_gaps||plan.capability_gaps||[]);
  if(gaps.length) body.append(el('div','muted','Offene Lücken: '+gaps.map(g=>g.type).join(', ')));
  if(res){
    const r = el('div','card');
    r.append(el('b',null,'Ergebnis: '), el('span',null,(res.kind||'Ergebnis')+' · '+(res.qualification||'')+' · '+(res.tests_executed?'Tests ausgeführt':'keine Tests ausgeführt')+' · '+(res.accepted?'akzeptiert':'nicht akzeptiert')));
    body.append(r);
  }
  pending.forEach(g=>{
    const box = el('div','gate'); const rq = g.request||{};
    box.append(el('b',null,'Freigabe nötig: '+(rq.exact_action||'Aktion')));
    if((rq.targets||[]).length) box.append(el('div',null,'Ziel: '+rq.targets.join(', ')));
    if((rq.risks||[]).length) box.append(el('div',null,'Risiken: '+rq.risks.join(', ')));
    box.append(el('div','muted','Rücknahme möglich: '+(rq.rollback_available?'ja':'nein')+' · gilt nur einmal'));
    box.append(chatButton('Ablehnen', async()=>{
      await api('/api/mission/reject',{method:'POST',body:JSON.stringify({mission_id:mid,gate_id:g.gate_id})});
      await refreshMissionCard(body, mid);
    }));
    box.append(chatButton('Genau diese Aktion einmal freigeben', async()=>{
      if(!confirm('Diese Aktion einmal freigeben?\n'+JSON.stringify(rq,null,2))) throw new Error('Nicht freigegeben.');
      await api('/api/mission/approve',{method:'POST',body:JSON.stringify({mission_id:mid,gate_id:g.gate_id})});
      await refreshMissionCard(body, mid);
    }));
    body.append(box);
  });
  const row = el('div','row');
  if(!running && !pending.length && !['COMPLETE','FAILED'].includes(phase)){
    row.append(chatButton(phase==='READY'?'Ausführen':'Weiter ausführen', ()=>runMissionLive(body, mid)));
  }
  row.append(chatButton('Details', ()=>missionWorkflow(mid)));
  body.append(row);
  document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
}

async function refreshMissionCard(body, mid){
  const m = await api('/api/mission/details',{method:'POST',body:JSON.stringify({mission_id:mid})});
  renderMission(body, m);
  refreshMissions();
}

const MISSION_POLL_MS = 3000;

// Run a mission and keep the card alive meanwhile: every 3 s the record is read again and the card redrawn with the
// current phase (the brain saves the mission after every step), so a long run is visible instead of a frozen button.
// Reading never changes anything; when the run call returns, the card is drawn once more from the final record.
async function runMissionLive(body, mid){
  let done = false;
  const live = (async()=>{
    while(!done){
      await new Promise(r=>setTimeout(r, MISSION_POLL_MS));
      if(done) return;
      try{ renderMission(body, await api('/api/mission/details',{method:'POST',body:JSON.stringify({mission_id:mid})}), true); }
      catch(_err){ /* the next poll or the final refresh shows the state */ }
    }
  })();
  try{
    renderMission(body, await api('/api/mission/details',{method:'POST',body:JSON.stringify({mission_id:mid})}), true);
    await api('/api/mission/run',{method:'POST',body:JSON.stringify({mission_id:mid,max_steps:20})});
  }finally{
    done = true; await live;
    await refreshMissionCard(body, mid);
  }
}

// Plan card for a message: only when the Captain asks for it (button, "/plan ...") or no model can answer.
function planCard(text){
  const body = addGuppiBlock(); body.textContent = 'Plane ...';
  return api('/api/chat',{method:'POST',body:JSON.stringify({intent:text, objective:text, mission_class:'S1',project_id:activeProjectId})})
    .then(out=>refreshMissionCard(body, out.mission.mission_id))
    .catch(err=>{ body.replaceChildren(el('span',null,'Runtime-Fehler: '+err.message)); });
}

async function openBridge(){
 let missions;
 try{ missions=await api('/api/missions'); }
 catch(err){ uiError('Brücke', err); return; }
 showProcessor('Brücke – Missionen','<b>Auftrag, Plan, Tests und Entscheidungen</b>',preview=>{
  const stations=el('div','toolbar'); stations.setAttribute('aria-label','Stationen');
  [['Besatzung',openAgents],['Entwicklung',openDevEnv],['Modelle',openModels],['Hardware',openHardware],['Maschinenraum',openMachineRoom],['Logbuch',openLogbook]].forEach(([label,fn])=>{ const b=el('button','tool',label); b.onclick=()=>fn(); stations.append(b); });
  preview.appendChild(stations);
  preview.appendChild(el('div','muted','Oben steht, was auf dich wartet. Ein Klick auf eine Karte öffnet sie.'));
  if(!missions.length){ preview.appendChild(el('div','muted','Noch keine Missionen.')); return; }
  bridgeGroups(missions).forEach(([title,list])=>{
   if(!list.length) return;
   preview.appendChild(el('h4',null,title+' ('+list.length+')'));
   list.slice(0,20).forEach(m=>preview.appendChild(bridgeCard(m)));
  });
 });
}

// Brücke: the cards sorted by what the Captain has to do first. Open gates come first, then running, done and failed.
function bridgeGroups(missions){
 const waiting=[], running=[], done=[], failed=[];
 missions.slice().reverse().forEach(m=>{
  if((m.pending_gates||0)>0) waiting.push(m);
  else if(m.phase==='FAILED') failed.push(m);
  else if(m.phase==='COMPLETE') done.push(m);
  else running.push(m);
 });
 return [['Wartet auf deine Freigabe',waiting],['In Arbeit',running],['Abgeschlossen',done],['Fehlgeschlagen',failed]];
}

const PHASE_LABEL={NEW:'neu',READY:'bereit',CANDIDATE_REVIEW:'Prüfung',COMPLETE:'fertig',FAILED:'fehlgeschlagen'};

// One card in the Brücke: the intent in plain words, its state, and the next step in one line.
function bridgeCard(m){
 const btn=el('div','mcard');
 btn.setAttribute('role','button'); btn.tabIndex=0;
 btn.style.cssText='display:block;cursor:pointer;';
 const title=String(m.intent||m.objective||m.mission_id);
 btn.append(el('b',null,title.slice(0,90)));
 const pending=m.pending_gates||0;
 if(pending>0) btn.style.borderColor='var(--warn-line)';
 const next=pending>0?'Nächster Schritt: Freigabe im Fenster der Karte geben':m.phase==='FAILED'?'Nächster Schritt: Ursache im Logbuch ansehen':m.phase==='COMPLETE'?'Nichts zu tun':'Läuft; keine Aktion nötig';
 btn.append(el('small',null,(PHASE_LABEL[m.phase]||m.phase||'?')+' · '+m.mission_id+' · '+next));
 btn.onclick=()=>missionWorkflow(m.mission_id);
 return btn;
}

function candidateSteps(m){
 const ex=m.execution||{}, phase=(m.lifecycle||{}).phase, test=ex.candidate_test, acc=ex.candidate_acceptance;
 if(!test && !acc && phase!=='CANDIDATE_REVIEW') return null;
 const t=test?String(test.status||''):'';
 const steps=[
  ['Kandidat','done'],
  ['Test',t==='FINISHED'?'done':t==='FAILED'?'fail':t?'active':'open'],
  ['Übernahme',phase==='COMPLETE'?'done':acc?'active':'open'],
  ['Abschluss',phase==='COMPLETE'?'done':phase==='FAILED'?'fail':'open']];
 const bar=el('div','steps');
 steps.forEach(([label,state])=>bar.append(el('span','step '+state,label)));
 return bar;
}

// Readable head of a mission (what, phase, plan, result) so the raw data stays folded away.
function missionSummary(m){
 const c=el('div','mcard'), info=el('div'), lc=m.lifecycle||{}, plan=m.plan||{}, id=m.identity||{};
 const head=el('div'); head.append(el('b',null,String((m.captain_intent||{}).original||(m.objective||{}).current||id.mission_id||'')), phaseBadge(lc.phase)); info.append(head);
 info.append(el('small',null,'Klasse '+(id.mission_class||'?')+' · Risiko '+((plan.risk||{}).level||(m.risk||{}).level||'?')+' · Status '+(lc.status||'?')+(id.created_at?' · angelegt '+String(id.created_at).slice(0,16).replace('T',' '):'')));
 const steps=plan.steps||[];
 if(steps.length){ const ol=el('ol'); ol.style.margin='6px 0 0 18px'; ol.style.paddingLeft='0'; steps.forEach(st=>ol.append(el('li',null,(st.description||st.action||st.id)+(st.action?' ('+st.action+')':'')))); info.append(ol); }
 else info.append(el('small',null,'Noch kein Plan.'));
 const res=(m.result&&m.result.qualification!=='PENDING')?m.result:null;
 if(res) info.append(el('small',null,'Ergebnis: '+(res.kind||'Ergebnis')+' · '+(res.qualification||'')+' · '+(res.accepted?'akzeptiert':'nicht akzeptiert')));
 const q=((m.context||{}).unresolved_questions||[]);
 if(q.length) info.append(el('small',null,'Offene Fragen: '+q.map(x=>typeof x==='string'?x:(x.question||x.text||JSON.stringify(x))).join(' · ')));
 c.append(info); c.style.alignItems='flex-start'; c.style.width='100%';
 return c;
}

async function missionWorkflow(mid){
 const m=await api('/api/mission/details',{method:'POST',body:JSON.stringify({mission_id:mid})});
 showProcessor('Mission '+mid,'<b>Plan und Entscheidungen prüfen, danach ausdrücklich ausführen</b>',preview=>{
  preview.appendChild(missionSummary(m));
  preview.appendChild(renderSeaChart(m));
  const bar=candidateSteps(m);if(bar)preview.appendChild(bar);
  const pre=document.createElement('pre');pre.textContent=JSON.stringify({intent:m.captain_intent,phase:m.lifecycle,plan:m.plan,result:m.result,tests:m.execution.candidate_test,acceptance:m.execution.candidate_acceptance,questions:m.context.unresolved_questions},null,2);const raw=document.createElement('details');raw.append(el('summary',null,'Rohdaten'),pre);preview.appendChild(raw);
  const phase=(m.lifecycle||{}).phase, open=(m.human_gates||{}).pending||[];
  if(!open.length && !['COMPLETE','FAILED'].includes(phase))      // same rule as the chat card: nothing to run while a gate waits or the mission is over
   preview.appendChild(actionButton(phase==='READY'?'Mission ausführen':'Mission weiter ausführen',async()=>{
    const note=el('div','muted','Mission läuft … die Ansicht wird nach dem Lauf neu aufgebaut.'); preview.prepend(note);
    try{ await api('/api/mission/run',{method:'POST',body:JSON.stringify({mission_id:mid,max_steps:20})}); } finally{ await missionWorkflow(mid); }
   }));
  else if(open.length) preview.appendChild(el('div','muted','Diese Mission wartet auf deine Entscheidung (unten).'));
  const candidate=async(operation,plan)=>{const result=await api('/api/candidate',{method:'POST',body:JSON.stringify({mission_id:mid,operation,plan})});showData('Kandidaten-Ergebnis',result);return result;};
  preview.appendChild(actionButton('Kandidat testen',()=>candidate('test')));
  preview.appendChild(actionButton('Testergebnis unabhängig prüfen',()=>candidate('test-verify')));
  ['accept','rollback'].forEach(op=>preview.appendChild(actionButton(op==='accept'?'Übernahme vorbereiten':'Rücknahme vorbereiten',async()=>{
   const result=await candidate(op+'-preview');if(result.plan){reviewedCandidatePlan={mid,operation:op,plan:result.plan};
    const box=document.getElementById('processorPreview');box.appendChild(actionButton('Prüfplan zur Freigabe vorlegen',async()=>{const out=await candidate(op,result.plan);if(out.gate)await missionWorkflow(mid);}));}
  })));
  if(reviewedCandidatePlan&&reviewedCandidatePlan.mid===mid)preview.appendChild(actionButton('Freigegebenen Prüfplan anwenden',()=>candidate(reviewedCandidatePlan.operation,reviewedCandidatePlan.plan)));
  m.human_gates.pending.forEach(g=>{
   const detail=document.createElement('pre');detail.textContent=JSON.stringify(g.request,null,2);preview.appendChild(detail);
   preview.appendChild(actionButton('Genau diese Aktion einmal freigeben',async()=>{
    if(!confirm('Diese Aktion einmal freigeben?\n'+JSON.stringify(g.request,null,2)))return;
    await api('/api/mission/approve',{method:'POST',body:JSON.stringify({mission_id:mid,gate_id:g.gate_id})});await missionWorkflow(mid);
   }));
  });
 });
}

async function requestCodeCandidate(){
 if(!activeProjectId){alert('Zuerst einen registrierten Projektordner öffnen.');return;}
 const intent=prompt('Welche Codeänderung soll GUPPI als Kandidat entwickeln?');if(!intent)return;
 const selection=prompt('Ausgewählte relative Dateien, durch Komma getrennt. Tests müssen mit ausgewählt sein, wenn sie im Gast laufen sollen.');if(!selection)return;
 const files=selection.split(',').map(x=>x.trim()).filter(Boolean);
 const out=await api('/api/code/generate',{method:'POST',body:JSON.stringify({project_id:activeProjectId,intent,files})});showData('Codekandidat – noch nicht getestet',out);
}
