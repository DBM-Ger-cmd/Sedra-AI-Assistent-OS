// Runtime status in the taskbar, development environment, hardware window, machine room and logbook.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

let runtimeOnline = null;

// The Guppy is the ambient status: 'idle' (nothing runs), 'busy' (a model is loaded or loading), plus a bubble with the number of open gates;
// 'offline' when the runtime does not answer. Read-only: it only looks at /api/models and /api/missions after /api/status succeeded.
function setGuppyMood(mood, gates){
  const fig = document.getElementById('guppyFigure'), badge = document.getElementById('guppyBadge');
  if(!fig) return;
  fig.classList.remove('idle','busy','offline','gate');
  fig.classList.add(mood);
  if(gates > 0 && mood !== 'offline'){ fig.classList.add('gate'); badge.textContent = String(gates); badge.title = gates + (gates === 1 ? ' offene Freigabe' : ' offene Freigaben') + ' – Brücke öffnen'; }
  fig.title = mood === 'offline' ? 'SEDRA: keine Verbindung zur Runtime' : mood === 'busy' ? 'SEDRA: ein Modell arbeitet' : 'SEDRA: bereit';
}

async function refreshGuppyMood(){
  const get = p=>api(p).then(v=>({ok:true,v}),()=>({ok:false}));
  const [models, missions] = await Promise.all([get('/api/models'), get('/api/missions')]);
  const busy = (typeof modelsBusy !== 'undefined' && modelsBusy) || (models.ok && models.v.server && models.v.server.running);
  const gates = missions.ok ? missions.v.reduce((n,m)=>n + (m.pending_gates||0), 0) : 0;
  setGuppyMood(busy ? 'busy' : 'idle', gates);
}

function setOnline(flag){
  const before = runtimeOnline;
  runtimeOnline = flag;
  if(flag === before) return;
  if(flag && before === false) addGuppiMessage('Verbindung zur Runtime wiederhergestellt.');
  if(!flag){
    const body = addGuppiBlock();
    body.append(el('span',null,'Keine Verbindung zur Runtime. Ich versuche es alle 15 Sekunden erneut. '), chatButton('Jetzt verbinden', refreshRuntimeStatus));
  }
}

async function refreshRuntimeStatus(){
  try{
    const st=await api('/api/status');
    setOnline(true);
    refreshChatModels();
    refreshGuppyMood();
    document.getElementById('runtimeState').textContent='SEDRA '+st.system_state;
    document.getElementById('runtimeSkills').textContent=st.capability_router.skills+' Skills';
    const dev=st.development_environment || {};
    document.getElementById('devEnvTray').textContent=dev.execution_ready?'Entwicklung READY':'Entwicklung BLOCKED';
    document.getElementById('projectDevEnvState').textContent=dev.execution_ready?'bereit':'blockiert';
    document.getElementById('projectVmState').textContent=(dev.blockers||[]).includes('target_boundary_acceptance_pending')?'nicht qualifiziert':'qualifiziert';
    document.getElementById('projectContextState').textContent='Runtime verbunden';
    const blockers=(dev.blockers||[]);
    document.getElementById('desktopGuppiBubble').textContent =
      'Hallo Captain. SEDRA ist '+st.system_state+'. '+st.capability_router.skills+' Skills geladen. '+
      (dev.execution_ready?'Die Entwicklungsumgebung ist ausführungsbereit.':'Die Entwicklungsumgebung hat '+blockers.length+' offene technische Blocker.');
  }catch(err){
    setOnline(false);
    setGuppyMood('offline', 0);
    document.getElementById('runtimeState').textContent='SEDRA OFFLINE';
    document.getElementById('projectVmState').textContent='unbekannt';
    document.getElementById('projectContextState').textContent='keine Verbindung';
    document.getElementById('desktopGuppiBubble').textContent='Keine Verbindung zur SEDRA-Runtime: '+err.message;
  }
}

async function refreshDevEnvironment(){
  try{
    const d=await api('/api/dev-environment');
    const doc=d.doctor||{};
    const ready=!!doc.execution_ready, state=document.getElementById('devDoctorState'), badge=document.getElementById('devReadyBadge');
    state.textContent=ready?'READY':'BLOCKED'; state.className=ready?'ok':'bad';      // green only when it is really ready
    badge.classList.toggle('bad',!ready);
    document.getElementById('devBackend').textContent=d.technical_backend||doc.backend||'sandbox';
    document.getElementById('devNetwork').textContent=doc.network||'unbekannt';
    document.getElementById('devExecution').textContent=doc.execution_ready?'technisch bereit; Freigabe nötig':'gesperrt';
    badge.textContent=ready?'● AUSFÜHRUNGSBEREIT':'● TECHNISCH BLOCKIERT';
    document.getElementById('devRuntimeDetails').innerHTML =
      '<div class="dev-row"><span>Backend</span><span>'+escapeHtml(doc.backend||'–')+'</span></div>'+
      '<div class="dev-row"><span>SDK-Version</span><span>'+escapeHtml(String(doc.sdk_version||'nicht installiert'))+'</span></div>'+
      '<div class="dev-row"><span>VM-Grenze getestet</span><span>'+(doc.vm_boundary_tested?'ja':'nein')+'</span></div>'+
      '<div class="dev-row"><span>Unsicherer Host-Fallback</span><span>'+(doc.unsafe_host_fallback?'JA':'nein')+'</span></div>';
    const blockers=doc.blockers||[];
    document.getElementById('devBlockers').innerHTML = blockers.length ? blockers.map(b=>
      '<div class="dev-row"><span>'+escapeHtml(b)+'</span><span>OFFEN</span></div>').join('') :
      '<div class="dev-row"><span>Keine Blocker</span><span class="ok">OK</span></div>';
    const hist=d.history||[];
    document.getElementById('devHistory').innerHTML = hist.length ? hist.slice(-8).reverse().map(h=>
      '<div class="dev-row"><span>'+escapeHtml(String(h.operation||h.action||h.status||'Lauf'))+'</span><span>'+escapeHtml(String(h.status||''))+'</span></div>').join('') :
      '<div class="dev-row"><span>Noch keine Ausführung</span><span>–</span></div>';
  }catch(err){
    document.getElementById('devReadyBadge').textContent='● STATUSFEHLER'; document.getElementById('devReadyBadge').classList.add('bad');
    document.getElementById('devBlockers').innerHTML='<div class="dev-row"><span>'+escapeHtml(err.message)+'</span><span>FEHLER</span></div>';
  }
}

// The Hardware Manager dashboard (read-only) in its own window; the frame loads once and refreshes itself.
function openHardware(){
  const frame = document.getElementById('hardwareFrame');
  if(!frame.getAttribute('src')) frame.src = '/hardware#' + encodeURIComponent(API_TOKEN);
  showWindow('hardwareWindow');
}

async function openMachineRoom(){
  const get = p=>api(p).then(v=>({ok:true,v}),e=>({ok:false,e:e.message}));
  const [st,res,rout,ctx] = await Promise.all([get('/api/status'),get('/api/resources'),get('/api/routing'),get('/api/context')]);
  const stv = st.ok?st.v:{}; const dev = stv.development_environment||{};
  const meta = st.ok ? '<b>Control Master / Runtime</b><br>System: '+escapeHtml(stv.system_state)+'<br>Tools: '+Object.keys(stv.tools||{}).length : '<b>Runtime nicht erreichbar</b><br>'+escapeHtml(st.e);
  showProcessor('Maschinenraum – Live Status', meta, preview=>{
    const grid = el('div','mr-grid');
    const card = (title, wide)=>{ const c = el('div','mr-card'+(wide?' wide':'')); c.append(el('h4',null,title)); grid.append(c); return c; };
    const line = (c,k,v)=>{ const l = el('div','line'); l.append(el('span',null,k), el('span',null,String(v))); c.append(l); };
    const tag = (c,text,kind)=>{ let t = c.querySelector('.tags'); if(!t){ t = el('div','tags'); c.append(t); } t.append(el('span','tag'+(kind?' '+kind:''),text)); };
    const missing = (c,r)=>c.append(el('div','muted','nicht verfügbar: '+r.e));

    const sys = card('System');
    if(st.ok){
      sys.append(el('div','big',stv.system_state));
      const tools = Object.values(stv.tools||{}), bad = tools.filter(t=>t.healthy===false).length;
      line(sys,'Skills',(stv.capability_router||{}).skills??'–'); line(sys,'Tools',tools.length-bad+' von '+tools.length+' gesund');
      line(sys,'Projekt',(stv.project||{}).name||'–');
    } else missing(sys,st);

    const hw = card('Hardware');
    if(st.ok){
      hw.append(el('div','big',(stv.hardware||{}).hardware_class||'unbekannt'));
      const rp = stv.recommended_model_profile||{};
      if(rp.model) line(hw,'Empfohlenes Modell',rp.model+(rp.quantization?' · '+rp.quantization:''));
      if(rp.context) line(hw,'Kontext',(rp.context.recommended||'–')+' / max '+(rp.context.maximum||'–'));
      line(hw,'Hardware-Profil',((stv.hardware_manager||{}).profile_state||{}).profile_id||'–');
      const b = el('button','action','Hardware-Details'); b.onclick = openHardware; b.style.marginTop = '6px'; hw.append(b);
    } else missing(hw,st);

    const mem = card('GPU und Arbeitsspeicher');
    if(res.ok && res.v.headroom){
      const h = res.v.headroom;
      (h.gpus||[]).forEach((g,i)=>line(mem,'GPU '+(i+1)+' frei',(g.free_gb??'–')+' GB'));
      line(mem,'RAM frei',(h.ram_free_gb??'–')+' GB'); line(mem,'VRAM-Reserve',(res.v.vram_reserve_gb??'–')+' GB');
      line(mem,'Reservierungen',(res.v.reservations||[]).length);
    } else if(res.ok) mem.append(el('div','muted','Ressourcenplanung ist aus.')); else missing(mem,res);

    const route = card('Modelle und Routing');
    if(rout.ok){
      route.append(el('div','big',rout.v.enabled?'aktiv':'aus'));
      line(route,'Cloud',(rout.v.policy||{}).cloud_allowed?'erlaubt':'gesperrt');
      const ph = rout.v.provider_health||{}, names = Object.keys(ph);
      if(!names.length) line(route,'Anbieter-Zustand','keine Meldungen');
      names.forEach(n=>{ const state = ph[n].effective_state||ph[n].state||'?'; line(route,n,state); });
      const enabled = (rout.v.capabilities||[]).filter(c=>c.enabled).length;
      line(route,'Rezepte aktiv',enabled+' von '+(rout.v.capabilities||[]).length);
      const add = el('button','action','Neues Modell …'); add.style.marginTop = '6px'; add.title = 'GGUF-Datei wählen, Rezept prüfen, freigeben, laden, testen'; add.onclick = openModelAdd; route.append(add);
    } else missing(route,rout);

    const de = card('Entwicklungsumgebung');
    if(st.ok){
      de.append(el('div','big',dev.execution_ready?'bereit':'blockiert'));
      line(de,'Backend',dev.backend||'–'); line(de,'Netzwerk',dev.network||'–');
      (dev.blockers||[]).forEach(bk=>tag(de,bk,'bad'));
      if(!(dev.blockers||[]).length) tag(de,'keine Blocker');
    } else missing(de,st);

    const cx = card('Kontext');
    if(ctx.ok){ cx.append(el('div','big',ctx.v.enabled?'aktiv':'aus')); line(cx,'Gemessene Läufe',(ctx.v.jobs||[]).length); } else missing(cx,ctx);

    const tl = card('Tools',true);
    if(st.ok){ Object.entries(stv.tools||{}).forEach(([k,t])=>tag(tl,k+(t.version?' '+t.version:''),t.healthy===false?'bad':(t.enabled===false?'warn':''))); }
    else missing(tl,st);

    preview.appendChild(grid);
  });
}

async function openLogbook(){
  const get = p=>api(p).then(v=>({ok:true,v}),e=>({ok:false,e:e.message}));
  const [ms,sup,aud] = await Promise.all([get('/api/missions'),get('/api/supervisor'),get('/api/audit')]);
  const counts = sup.ok&&sup.v.counts ? Object.entries(sup.v.counts).map(([k,n])=>escapeHtml(k)+': '+n).join('<br>') : 'keine Job-Daten';
  const chain = aud.ok ? (aud.v.chain_ok?'<span class="ok">intakt</span>':'<b style="color:#a13b32">GEBROCHEN</b>') : 'nicht verfügbar';
  showProcessor('Logbuch','<b>Missionen:</b> '+(ms.ok?ms.v.length:'–')+'<br><b>Audit-Kette:</b> '+chain+'<br><b>Jobs</b><br>'+counts, preview=>{
    if(aud.ok&&aud.v.events.length) preview.appendChild(actionButton('Audit-Ereignisse ('+aud.v.events.length+' neueste)',()=>showData('Audit-Ereignisse'+(aud.v.chain_ok?'':' – KETTE GEBROCHEN'),aud.v.events.slice().reverse())));
    if(!ms.ok){preview.appendChild(el('div',null,'Missionen nicht verfügbar: '+ms.e));return;}
    if(!ms.v.length){preview.appendChild(el('div',null,'Noch keine Missionen.'));return;}
    ms.v.slice(-30).reverse().forEach(m=>preview.appendChild(actionButton((m.created_at||'').slice(0,16).replace('T',' ')+' · '+m.mission_id+' · '+m.phase+' · '+String(m.intent||'').slice(0,60),()=>missionWorkflow(m.mission_id))));
  });
}

function openDevEnv(){
  const projectLabel = activeProject || 'kein Projekt gewählt';
  document.getElementById('devProjectName').textContent = projectLabel;
  document.getElementById('devTitleBar').textContent = 'Entwicklungsumgebung – ' + projectLabel;
  document.getElementById('devDescription').textContent =
    'Runtime-gebundener Status für ' + projectLabel + '. Technischer Backend-Name bleibt sandbox.';
  showWindow('devWindow');
  hideContext();
  refreshDevEnvironment();
}
