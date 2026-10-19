// Models window: model hints, chat model picker, running processes, switches, model list.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

// Short plain-language notes per model: what it is good for and what to watch out for (keyed by the model key of the recipe).
const MODEL_HINTS = {
  'qwen3-coder-30b-a3b': {good:'Code schreiben und reparieren', note:'Erste Wahl für Programmieraufgaben; groß (16 GB), braucht viel Arbeitsspeicher.'},
  'gpt-oss-20b': {good:'Gründliches Planen und Nachdenken', note:'Denkt vor der Antwort, deshalb etwas langsamer beim ersten Wort; gut bei komplexen Aufgaben und Prüfungen.'},
  'google/gemma-4-12b-qat': {good:'Allgemeine Fragen, Erklärungen, Gegenprüfen', note:'Flott und vielseitig; prüft Code von anderen Modellen unabhängig. Selten kommen Aussetzer mit Zeichensalat vor.'},
  'qwen3.5-9b-mtp': {good:'Kurze Fragen, schnelle Entwürfe', note:'Klein und schnell (6 GB); für große Aufgaben zu schwach.'},
  'deepseek-r1-0528-qwen3-8b': {good:'Logik und Schritt-für-Schritt-Rechnen', note:'Klein (5 GB), denkt Schritte laut durch; Antworten werden dadurch lang.'},
  'qwen3-14b': {good:'Mittelgroßer Allrounder', note:'Gute Balance aus Tempo und Qualität bei kleinem Kontext.'},
  'qwen3.6-35b-a3b': {good:'Höchste Qualität bei schweren Aufgaben', note:'Sehr groß (18 GB): füllt die Grafikkarte fast ganz, anderes bitte beenden.'}
};

let chatModelList = [];

// A recipe without a model entry (fresh package, nothing configured yet) is shown by its recipe id, never as "null".
function modelName(r){ return (r && (r.model || r.id)) || '?'; }

// Plain-language reason for the errors a model load can end with.
function explainModelError(message){
  const m = String(message||'');
  if(m.includes('hardware_profile_changed')) return 'Das Hardware-Profil passt nicht mehr zu diesem PC (meist nach einem Treiber-Update). Es ist kein Speicherproblem. Binde das Profil neu: hardware-rebind in der Konsole.';
  if(m.includes('hardware_pressure')) return 'Nicht genug freier Grafikspeicher für dieses Modell. Beende andere Programme, die die Grafikkarte nutzen, oder wähle ein kleineres Modell.';
  if(m.startsWith('gpu_lease_busy')){ const p = m.split(':'); return 'Die Grafikkarte ist gerade von "'+(p[1]||'jemand anderem')+'" belegt'+(p[2]?' ('+p[2]+')':'')+'. Warte, bis der Lauf fertig ist, oder beende ihn im Fenster Modelle.'; }
  if(m.includes('port_in_use')) return 'Auf dem Port läuft schon ein anderer Server. Beende ihn im Fenster Modelle unter "Läuft gerade".';
  if(m.includes('model_loader_unavailable')) return 'Das automatische Laden ist ausgeschaltet (Schalter im Fenster Modelle).';
  return m;
}

function modelHintText(r){
  const h = MODEL_HINTS[r.model];
  if(!h) return (r.roles||[]).slice(0,3).join(', ')||'';
  return 'Gut für: '+h.good+'. '+h.note+(r.size_gb?' ('+r.size_gb+' GB)':'');
}

function updateChatModelHint(){
  const sel = document.getElementById('chatModel'), hint = document.getElementById('chatModelHint');
  const r = chatModelList.find(x=>x.id===sel.value);
  hint.textContent = r ? modelHintText(r)+(r.loaded?'':' · wird beim Auswählen geladen') : 'Kein Modell geladen: Der Chat plant dann nur. Wähle ein Modell, um mit ihm zu schreiben.';
}

async function refreshChatModels(){
  const sel = document.getElementById('chatModel');
  if(!sel || modelsBusy || document.activeElement === sel) return;
  let v;
  try{ v = await api('/api/models'); }catch(err){ return; }
  chatModelList = v.recipes.filter(r=>r.provider==='llama-cpp-server' && r.enabled);
  sel.replaceChildren();
  const none = el('option',null,'Kein Modell (nur planen)'); none.value = ''; sel.append(none);
  chatModelList.forEach(r=>{ const o = el('option',null,modelName(r)+(r.loaded?' · geladen':'')); o.value = r.id; sel.append(o); });
  const loaded = chatModelList.find(r=>r.loaded);
  sel.value = loaded ? loaded.id : '';
  updateChatModelHint();
}

async function chooseChatModel(){
  const sel = document.getElementById('chatModel');
  const r = chatModelList.find(x=>x.id===sel.value);
  const current = chatModelList.find(x=>x.loaded);
  if((r && r.loaded) || (!r && !current)){ updateChatModelHint(); return; }
  const question = r ? (modelName(r)+' laden?'+(current?'\n\n'+modelName(current)+' wird dafür entladen.':'')+'\n\n'+modelHintText(r)) : modelName(current)+' entladen? Der Chat plant dann nur.';
  if(!confirm(question)){ await refreshChatModels(); return; }
  modelsBusy = true; sel.disabled = true;
  const note = addGuppiBlock(); note.textContent = r ? 'Lade '+modelName(r)+' ...' : 'Entlade '+modelName(current)+' ...';
  try{
    if(r) await api('/api/model/load',{method:'POST',body:JSON.stringify({recipe_id:r.id})});
    else await api('/api/model/unload',{method:'POST',body:'{}'});
    note.textContent = r ? modelName(r)+' ist geladen und antwortet jetzt im Chat.' : 'Kein Modell mehr geladen.';
  }catch(err){
    note.textContent = 'Das hat nicht geklappt: '+explainModelError(err.message);
    attachErrorDetails(note, err.message);
  }
  modelsBusy = false; sel.disabled = false;
  await refreshChatModels();
  if(document.getElementById('modelWindow').classList.contains('active')) refreshModels();
}

let modelsBusy = false, modelsTimer = null;

async function openModels(){
  showWindow('modelWindow');
  await refreshModels();
  if(!modelsTimer) modelsTimer = setInterval(()=>{
    const w = document.getElementById('modelWindow');
    if(w.classList.contains('active') && w.classList.contains('focused') && !document.hidden && !modelViewBusy()) refreshModels();
  }, 8000);
}

// Runs a model action, shows progress in place of the list and then the new state.
async function modelAction(label, path, body){
  if(modelsBusy) return;
  modelsBusy = true;
  const box = document.getElementById('modelBody');
  box.dataset.html = '';
  box.replaceChildren(el('div','mnote',label+' ... das kann bei großen Modellen mehrere Minuten dauern. Bitte nicht schließen.'));
  try{
    await api(path,{method:'POST',body:JSON.stringify(body)});
  }catch(err){
    modelsBusy = false;
    await refreshModels();
    box.prepend(el('div','mnote mbad','Fehlgeschlagen: '+explainModelError(err.message)));
    box.dataset.html = '';
    return;
  }
  modelsBusy = false;
  await refreshModels();
}

// What runs on the PC right now (SEDRA's llama-servers, runs, jobs) and the way to stop it.
async function renderRunning(box){
  box.append(el('h3',null,'Läuft gerade'));
  let p;
  try{ p = await api('/api/processes'); }
  catch(err){ box.append(el('div','mnote mbad','Prozesse nicht lesbar: '+err.message)); return; }
  if(p.note) box.append(el('div','mnote',p.note));
  if(p.vram_used_gb !== null) box.append(el('div','mnote','GPU-Speicher belegt: '+p.vram_used_gb+' GB'));
  if(p.mismatch){
    const want = p.expected.map(e=>e.purpose+': '+e.model).join(', ');
    box.append(el('div','mnote mbad','Auf der GPU läuft '+p.servers.map(s=>s.alias).join(', ')+', das aktive Profil erwartet aber '+want+'. Beende das laufende Modell, wenn es nicht zur Aufgabe passt, und lade dann das passende.'));
  }
  const stopBtn = (label, pid, question)=>{
    const b = el('button','action',label);
    b.onclick = async()=>{
      if(!confirm(question)) return;
      b.disabled = true;
      try{ await api('/api/process/stop',{method:'POST',body:JSON.stringify({pid, confirm:true})}); }catch(e){ alert(e.message); }
      refreshModels();
    };
    return b;
  };
  p.servers.forEach(s=>{
    const c = el('div','mcard loaded'); const info = el('div');
    info.append(el('b',null,'llama-server: '+s.alias+(s.ours?' (diese Oberfläche)':'')));
    info.append(el('small',null,'PID '+s.pid+' · Port '+s.port+' · Kontext '+s.context+' · seit '+String(s.started||'').replace('T',' ')));
    if(!s.ours) info.append(el('small',null,'Gestartet von: '+(s.parent||'unbekannt')));
    c.append(info);
    c.append(stopBtn(s.ours?'Entladen':'Beenden', s.pid, 'Modell '+s.alias+' (PID '+s.pid+') beenden?'+(s.ours?'':'\n\nGestartet von: '+(s.parent||'unbekannt')+'\nEin laufender Auftrag dieses Prozesses bricht dann ab.')));
    box.append(c);
  });
  p.runs.forEach(r=>{
    const c = el('div','mcard'); const info = el('div');
    info.append(el('b',null,'SEDRA-Lauf (PID '+r.pid+')'));
    info.append(el('small',null,r.cmd+' · seit '+String(r.started||'').replace('T',' ')));
    c.append(info);
    c.append(stopBtn('Lauf abbrechen', r.pid, 'Lauf abbrechen?\n\n'+r.cmd+'\n\nDie Modelle, die dieser Lauf gestartet hat, werden ebenfalls beendet.'));
    box.append(c);
  });
  p.jobs.forEach(j=>{
    const c = el('div','mcard'); const info = el('div');
    info.append(el('b',null,'Job '+j.job_id+' · '+j.state));
    info.append(el('small',null,(j.role||'')+' · '+(j.kind||'')+' · Versuche: '+(j.attempts??'?')));
    c.append(info);
    const b = el('button','action','Job abbrechen');
    b.onclick = async()=>{
      if(!confirm('Job '+j.job_id+' ('+j.state+') abbrechen?')) return;
      b.disabled = true;
      try{ await api('/api/job/cancel',{method:'POST',body:JSON.stringify({job_id:j.job_id})}); }catch(e){ alert(e.message); }
      refreshModels();
    };
    c.append(b);
    box.append(c);
  });
  if(!p.servers.length && !p.runs.length && !p.jobs.length) box.append(el('div','mnote','Nichts läuft.'));
}

// Machine-local switches. A change is a request with a Captain gate: exact change shown, approved once, applied at the next start.
const SWITCH_LABELS = {
  'job_supervisor.enabled':'Job-Überwachung', 'context_manager.enabled':'Kontext-Verwaltung', 'resource_scheduler.enabled':'Ressourcenplanung (GPU-Reservierungen)',
  'model_loader.enabled':'Modelle automatisch laden', 'model_loader.evict_idle_models':'Ungenutzte Modelle bei Platzmangel entladen',
  'llama_server.enabled':'Eigener llama-server', 'llama_server.mtp':'MTP-Beschleunigung (llama-server)', 'token_policy.enabled':'Token-Richtlinie'
};

let pendingChange = null;     // {kind: 'switch' | 'routing', mission_id, gate, binding}: a request waiting for the Captain's decision

// The one request that waits for the Captain: exact change, approve once or reject. Used for switches and for routing settings.
function renderPendingChange(box, kind){
  if(!pendingChange || pendingChange.kind !== kind) return;
  const p = pendingChange, b = p.binding;
  const what = b.describe || (b.section+'.'+b.key+' → '+(b.new?'an':'aus'));
  const applyPath = p.kind === 'routing' ? '/api/routing-config/apply' : p.kind === 'model_add' ? '/api/model/add/apply' : '/api/switch/apply';
  const c = el('div','mcard'); const info = el('div');
  info.append(el('b',null,'Freigabe nötig: '+what));
  info.append(el('small',null,(p.kind === 'model_add' ? 'sofort nutzbar' : 'wirkt erst nach dem Neustart der Oberfläche')+' · die Datei wird vorher gesichert (Rücknahme: Wert zurückstellen oder Sicherung einspielen)'));
  if(p.kind === 'model_add' && b.block){ const det = el('details'); det.append(el('summary',null,'Genau dieser Block')); const pre = el('pre','diag-out'); pre.textContent = b.block; det.append(pre); info.append(det); }
  c.append(info);
  const row = el('div');
  const ok = el('button','action','Freigeben und anwenden');
  ok.onclick = async()=>{
    ok.disabled = true;
    try{
      await api('/api/mission/approve',{method:'POST',body:JSON.stringify({mission_id:p.mission_id,gate_id:p.gate.gate_id})});
      const done = await api(applyPath,{method:'POST',body:JSON.stringify({mission_id:p.mission_id})});
      pendingChange = null;
      if(p.kind === 'model_add') modelAddApplied(done.recipe_id);
    }catch(e){ alert(e.message); }
    refreshModels();
  };
  const no = el('button','action','Ablehnen'); no.style.marginLeft = '6px';
  no.onclick = async()=>{
    try{ await api('/api/mission/reject',{method:'POST',body:JSON.stringify({mission_id:p.mission_id,gate_id:p.gate.gate_id})}); }catch(e){ alert(e.message); }
    pendingChange = null; refreshModels();
  };
  row.append(ok,no); c.append(row);
  box.append(c);
}

// Settings of the Captain's own model recipes (local_config/role_routing.yaml): a few fields, each change behind a gate.
async function renderRoutingConfig(box){
  box.append(el('h3',null,'Modell-Einstellungen'));
  let v;
  try{ v = await api('/api/routing-config'); }
  catch(err){ box.append(el('div','mnote mbad','Einstellungen nicht lesbar: '+err.message)); return; }
  box.append(el('div','mnote','Grafikkarte (VRAM) ist schnell, aber klein (12 GB); Arbeitsspeicher (RAM) ist größer, aber langsamer. '
    +'Größerer Kontext braucht mehr VRAM. „Experten im Arbeitsspeicher" verschiebt Teile eines MoE-Modells vom VRAM in den RAM: mehr = weniger VRAM, aber langsamer. '
    +'KV-Cache q8_0 spart VRAM, ist aber ungenauer (bei gpt-oss über ca. 40k Tokens fehlerhaft). Änderungen gelten ab dem nächsten Start.'
    +(v.restart_needed?' Es gibt Änderungen, die noch auf den Neustart warten.':'')));
  renderPendingChange(box, 'routing');
  if(!v.recipes.length) box.append(el('div','mnote','Keine eigenen Rezepte: die Datei local_config/role_routing.yaml fehlt oder enthält keine Einträge (siehe docs/BETRIEB.md).'));
  const request = async(recipe_id, field, value)=>{
    try{ pendingChange = Object.assign({kind:'routing'}, await api('/api/routing-config/request',{method:'POST',body:JSON.stringify({recipe_id, field, value})})); }
    catch(e){ alert(e.message); }
    refreshModels();
  };
  v.recipes.forEach(r=>{
    const c = el('div','mcard'+(r.enabled?' loaded':''));
    const info = el('div');
    info.append(el('b',null,r.id+(r.enabled?'':' · deaktiviert')));
    info.append(el('small',null,(r.model||'')+' · Kontext '+(r.context_recommended||'–')+(r.n_cpu_moe!==null&&r.n_cpu_moe!==undefined?' · Experten im RAM '+r.n_cpu_moe:'')+(r.kv_cache_type?' · KV '+r.kv_cache_type:'')));
    c.append(info);
    const controls = el('div'); controls.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;align-items:center;justify-content:flex-end';
    const toggle = el('button','action', r.enabled?'Deaktivieren':'Aktivieren');
    toggle.title = 'Ob dieses Modell ausgewählt und geladen werden darf';
    toggle.onclick = ()=>request(r.id,'enabled',!r.enabled);
    controls.append(toggle);
    if(r.context_tiers.length && r.context_recommended){
      const sel = el('select'); sel.title = 'Standard-Kontext: so viel Text sieht das Modell auf einmal';
      r.context_tiers.forEach(t=>{ const o = el('option',null,'Kontext '+t); o.value = String(t); sel.append(o); });
      sel.value = String(r.context_recommended);
      sel.onchange = ()=>{ const val = Number(sel.value); if(val !== r.context_recommended) request(r.id,'context_recommended',val); };
      controls.append(sel);
    }
    if(r.n_cpu_moe !== null && r.n_cpu_moe !== undefined){
      const num = el('input'); num.type = 'number'; num.min = '0'; num.max = '48'; num.value = String(r.n_cpu_moe); num.style.width = '60px';
      num.title = 'Experten-Schichten im Arbeitsspeicher (0 bis 48)';
      const set = el('button','action','Setzen');
      set.onclick = ()=>{ const val = Number(num.value); if(Number.isInteger(val) && val !== r.n_cpu_moe) request(r.id,'n_cpu_moe',val); };
      controls.append(num,set);
    }
    if(r.kv_cache_type){
      const kv = el('select'); kv.title = 'Genauigkeit des Gedächtnisses (KV-Cache)';
      ['f16','q8_0'].forEach(t=>{ const o = el('option',null,'KV '+t); o.value = t; kv.append(o); });
      kv.value = r.kv_cache_type;
      kv.onchange = ()=>{ if(kv.value !== r.kv_cache_type) request(r.id,'kv_cache_type',kv.value); };
      controls.append(kv);
    }
    c.append(controls);
    box.append(c);
  });
}

async function renderSwitches(box){
  box.append(el('h3',null,'Schalter'));
  let v;
  try{ v = await api('/api/switches'); }
  catch(err){ box.append(el('div','mnote mbad','Schalter nicht lesbar: '+err.message)); return; }
  if(v.error) box.append(el('div','mnote mbad','Die Schalterdatei ist fehlerhaft und wird nicht angewendet: '+v.error));
  box.append(el('div','mnote','Änderungen brauchen deine Freigabe und gelten ab dem nächsten Start der Oberfläche.'+(v.restart_needed?' Es gibt Änderungen, die noch auf den Neustart warten.':'')));
  renderPendingChange(box, 'switch');
  v.items.forEach(it=>{
    const id = it.section+'.'+it.key;
    const c = el('div','mcard'+(it.value===true?' loaded':'')); const info = el('div');
    info.append(el('b',null,SWITCH_LABELS[id]||id));
    info.append(el('small',null,id+' · '+(it.value===null?'nicht gesetzt (Standard)':(it.value?'an':'aus'))));
    c.append(info);
    const b = el('button','action', it.value===true?'Ausschalten':'Einschalten');
    b.onclick = async()=>{
      b.disabled = true;
      try{ pendingChange = Object.assign({kind:'switch'}, await api('/api/switch/request',{method:'POST',body:JSON.stringify({section:it.section,key:it.key,value:it.value!==true})})); }
      catch(e){ alert(e.message); }
      refreshModels();
    };
    c.append(b);
    box.append(c);
  });
}

// The view is built off screen and swapped in only when it differs: no empty flash, no jump to the top, no lost focus (Captain 2026-10-06).
async function refreshModels(){
  const live = document.getElementById('modelBody');
  const box = document.createElement('div');
  let v;
  try{ v = await api('/api/models'); }
  catch(err){ live.replaceChildren(el('div','mnote mbad','Modelle nicht verfügbar: '+err.message)); return; }
  try{ await buildModels(box, v); }
  finally{ swapModelView(live, box); }
}

function swapModelView(live, box){
  if(live.dataset.html === box.innerHTML && live.childElementCount) return;      // nothing changed
  const top = live.scrollTop;
  live.replaceChildren(...box.childNodes);
  live.dataset.html = live.innerHTML;
  live.scrollTop = top;
}

// the user is typing or choosing in the model window: do not redraw under their hands
function modelViewBusy(){
  const live = document.getElementById('modelBody'), a = document.activeElement;
  return modelsBusy || (a && live.contains(a) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName));
}

async function buildModels(box, v){
  // a change the chat proposed (open_requests) waits here for the Captain, like one requested from this window
  if(!pendingChange && v.open_requests && v.open_requests.length) pendingChange = v.open_requests[0];
  // GPU / server state
  const srv = v.server||{};
  const lease = v.lease ? ('GPU-Sperre: '+v.lease.owner+(v.lease.mine?' (diese Oberfläche)':'')+' – '+v.lease.purpose+(v.lease.stale?' (veraltet)':'')) : 'GPU-Sperre: frei';
  const running = srv.running ? ('läuft: '+srv.model+(srv.context?' · Kontext '+srv.context:'')) : 'kein Modell geladen';
  await renderWorkbench(box, v);
  box.append(el('h3',null,'Zustand'));
  box.append(el('div','mnote','Server: '+running+' · '+lease+(v.loader_enabled?'':' · Laden ist in den Schaltern ausgeschaltet')));
  renderModelAdd(box);
  await renderRunning(box);
  // profile
  if(v.profiles && Object.keys(v.profiles.items||{}).length){
    box.append(el('h3',null,'Modellkombination'));
    Object.entries(v.profiles.items).forEach(([name,p])=>{
      const active = name === v.profiles.active;
      const c = el('div','mcard'+(active?' loaded':''));
      const info = el('div'); info.append(el('b',null,name+(active?' (aktiv)':'')));
      info.append(el('small',null,'Coder: '+(p.coder||[]).join(', ')+' · Verifier: '+(p.verifier||[]).join(', ')));
      if(p.description) info.append(el('small',null,p.description.slice(0,200)));
      c.append(info);
      if(!active){
        const b = el('button','action','Aktivieren');
        b.onclick = async()=>{ b.disabled = true; try{ await api('/api/routing-profile',{method:'POST',body:JSON.stringify({name})}); }catch(e){ alert(e.message); } refreshModels(); };
        c.append(b);
      }
      box.append(c);
    });
  }
  await renderSwitches(box);
  await renderRoutingConfig(box);
  renderStandardTest(box);
  // recipes
  box.append(el('h3',null,'Modelle'));
  if(!v.recipes.length) box.append(el('div','mnote','Keine Modelle in der Routing-Konfiguration.'));
  v.recipes.forEach(r=>{
    const c = el('div','mcard'+(r.loaded?' loaded':''));
    const info = el('div'); info.append(el('b',null,r.id+(r.loaded?' · geladen':'')));
    info.append(el('small',null,(r.model||'kein Modell eingetragen')+' · '+(r.roles||[]).join('/')+' · '+(r.size_gb?r.size_gb+' GB · ':'')+(r.context_recommended?'Kontext '+r.context_recommended+' · ':'')+r.provider+(r.enabled?'':' · deaktiviert')));
    c.append(info);
    if(r.provider === 'llama-cpp-server' && r.enabled){
      const btns = el('div'); btns.style.cssText = 'display:flex;gap:6px';
      if(r.loaded){ const t = el('button','tool','Testen'); t.title = 'Eine kurze Frage an das geladene Modell: Antwort, Sekunden, Token/s'; t.onclick = ()=>modelTest(r.id, t); btns.append(t); }
      const b = el('button','action', r.loaded?'Entladen':'Laden');
      b.onclick = ()=> r.loaded ? modelAction('Entlade '+r.id,'/api/model/unload',{}) : modelAction('Lade '+r.id,'/api/model/load',{recipe_id:r.id});
      btns.append(b); c.append(btns);
    }
    box.append(c);
    renderModelTest(box, r.id);
  });
}
