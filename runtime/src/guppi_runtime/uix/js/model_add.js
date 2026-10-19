// "Neues Modell" in the Modelle window (Captain 2026-10-14): pick a GGUF file with the PC's own dialog or from the model folder, read what the
// file says, adjust id / roles / context, approve the recipe once, then load and test it. State lives in modelAdd so the 8-second refresh
// of the window can redraw the section without losing the Captain's choices.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

const MODEL_ROLES = [['coder','Coder'],['planner','Planer'],['reviewer','Prüfer'],['tester','Tester'],['documentation','Doku'],['verifier','Verifizierer']];

let modelAdd = {open:false, step:'pick', path:'', browse:null, browsePath:'', view:null, error:'', busy:false, roles:['coder','planner','reviewer','tester'], recipeId:'', context:null, test:null};

function openModelAdd(){ modelAdd.open = true; modelAdd.step = 'pick'; modelAdd.error = ''; openModels(); if(!modelAdd.browse) modelAddBrowse(''); }

async function modelAddPick(){
  modelAdd.busy = true; modelAdd.error = ''; refreshModels();
  try{
    const out = await api('/api/model/pick',{method:'POST',body:'{}'});
    if(out.picked){ modelAdd.path = out.path; await modelAddInspect(); return; }
    if(out.reason === 'no_dialog') modelAdd.error = 'Auf diesem PC gibt es keinen Dateidialog; bitte unten aus dem Modellordner wählen oder den Pfad eingeben.';
    else if(out.reason !== 'cancelled') modelAdd.error = 'Der Dateidialog ging nicht: '+out.reason;
  }catch(err){ modelAdd.error = err.message; }
  modelAdd.busy = false; refreshModels();
}

async function modelAddBrowse(sub){
  modelAdd.busy = true; modelAdd.error = '';
  try{ modelAdd.browse = await api('/api/model/browse',{method:'POST',body:JSON.stringify({path:sub||''})}); modelAdd.browsePath = sub||''; }
  catch(err){ modelAdd.error = 'Ordner nicht lesbar: '+err.message; }
  modelAdd.busy = false; refreshModels();
}

async function modelAddInspect(){
  modelAdd.busy = true; modelAdd.error = ''; refreshModels();
  try{
    const body = {path: modelAdd.path, roles: modelAdd.roles};
    if(modelAdd.recipeId) body.recipe_id = modelAdd.recipeId;
    if(modelAdd.context) body.context_recommended = modelAdd.context;
    modelAdd.view = await api('/api/model/inspect',{method:'POST',body:JSON.stringify(body)});
    modelAdd.recipeId = modelAdd.view.recipe.id; modelAdd.context = modelAdd.view.recipe.profile.context.recommended; modelAdd.step = 'inspect';
  }catch(err){ modelAdd.error = explainAddError(err.message); modelAdd.view = null; }
  modelAdd.busy = false; refreshModels();
}

function explainAddError(m){
  if(m.includes('valid_gguf_model_required')) return 'Das ist keine GGUF-Datei (Endung .gguf) oder sie fehlt.';
  if(m.includes('gguf_magic_missing')) return 'Die Datei beginnt nicht wie eine GGUF-Datei; vermutlich unvollständig heruntergeladen.';
  if(m.includes('recipe_id_taken')) return 'Diese Rezept-ID gibt es schon; bitte eine andere wählen.';
  if(m.includes('recipe_id_invalid')) return 'Rezept-ID: kleinbuchstaben.kleinbuchstaben, z. B. coder.local_mein_modell';
  if(m.includes('absolute_path_required')) return 'Bitte den vollständigen Pfad zur GGUF-Datei angeben (z. B. D:\\Modelle\\x.gguf).';
  if(m.includes('path_not_found')) return 'Datei nicht gefunden.';
  return m;
}

async function modelAddRequest(){
  modelAdd.busy = true; modelAdd.error = ''; refreshModels();
  try{
    const body = {path: modelAdd.path, roles: modelAdd.roles, recipe_id: modelAdd.recipeId, context_recommended: modelAdd.context};
    pendingChange = Object.assign({kind:'model_add'}, await api('/api/model/add/request',{method:'POST',body:JSON.stringify(body)}));
    modelAdd.step = 'gate';
  }catch(err){ modelAdd.error = explainAddError(err.message); }
  modelAdd.busy = false; refreshModels();
}

function modelAddReset(){ modelAdd = Object.assign(modelAdd, {open:false, step:'pick', path:'', view:null, error:'', busy:false, recipeId:'', context:null, test:null}); refreshModels(); }

// after the Captain approved and the recipe was written: the new recipe shows up in the list below with "Laden", then "Testen"
function modelAddApplied(recipeId){ modelAdd.step = 'done'; modelAdd.doneId = recipeId; }

async function modelTest(recipeId, button){
  button.disabled = true; button.textContent = 'Testet …';
  let out;
  try{ out = await api('/api/model/test',{method:'POST',body:JSON.stringify({recipe_id:recipeId})}); }
  catch(err){ out = {status:'failed', message: explainModelError(err.message)}; }
  modelAdd.test = Object.assign({recipe_id: recipeId}, out);
  refreshModels();
}

function renderModelTest(box, recipeId){
  const t = modelAdd.test; if(!t || t.recipe_id !== recipeId) return;
  const c = el('div','mnote'+(t.status==='completed'?'':' mbad'));
  if(t.status === 'completed'){
    c.append(el('b',null,'Test bestanden: '), el('span',null,t.seconds+' s'+(t.completion_tokens?' · '+t.completion_tokens+' Token'+(t.tokens_per_s?' · '+t.tokens_per_s+' Token/s':''):'')+(t.numbers_ok?' · Zahlenfolge korrekt':' · Zahlenfolge fehlt')));
    const q = el('div','diag-out'); q.textContent = t.reply; c.append(q);
  } else c.append(el('b',null,'Test fehlgeschlagen: '), el('span',null,t.message||t.status));
  box.append(c);
}

function renderModelAdd(box){
  const head = el('h3',null,'Neues Modell');
  box.append(head);
  if(!modelAdd.open){
    const b = el('button','action','Neues Modell hinzufügen …'); b.title = 'GGUF-Datei wählen, Rezept prüfen, freigeben, laden, testen';
    b.onclick = ()=>{ modelAdd.open = true; modelAdd.step = 'pick'; refreshModels(); if(!modelAdd.browse) modelAddBrowse(''); };
    box.append(b); return;
  }
  const card = el('div','mcard add-card'); const body = el('div'); body.style.flex = '1';
  if(modelAdd.error) body.append(el('div','mnote mbad', modelAdd.error));
  if(modelAdd.busy) body.append(el('div','mnote thinking','Bitte warten'));
  if(modelAdd.step === 'pick'){
    body.append(el('div','mnote','Schritt 1 von 3: GGUF-Datei wählen. Der Dialog öffnet sich auf diesem PC (Explorer bzw. Finder); alternativ aus dem Modellordner wählen oder den Pfad eingeben.'));
    const row = el('div','row');
    const pick = el('button','action','Datei wählen …'); pick.disabled = modelAdd.busy; pick.onclick = modelAddPick; row.append(pick);
    const input = el('input'); input.placeholder = 'oder vollständiger Pfad zur .gguf-Datei'; input.value = modelAdd.path; input.style.cssText = 'flex:1;min-width:240px;border:1px solid var(--line);border-radius:3px;padding:5px 7px';
    input.oninput = ()=>{ modelAdd.path = input.value; };
    input.onkeydown = e=>{ if(e.key === 'Enter' && modelAdd.path.trim()) modelAddInspect(); };
    const go = el('button','tool','Prüfen'); go.onclick = ()=>{ if(modelAdd.path.trim()) modelAddInspect(); };
    row.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;align-items:center'; row.append(input, go); body.append(row);
    const br = modelAdd.browse;
    if(br){
      if(!br.root) body.append(el('div','mnote', br.note||'Kein Modellordner eingetragen.'));
      else{
        const crumb = el('div','crumb'); const rootA = el('a',null,'Modellordner'); rootA.onclick = ()=>modelAddBrowse(''); crumb.append(rootA);
        const parts = br.path ? br.path.split('/') : [];
        parts.forEach((p,i)=>{ crumb.append(' / '); const a = el('a',null,p); a.onclick = ()=>modelAddBrowse(parts.slice(0,i+1).join('/')); crumb.append(a); });
        body.append(crumb);
        const list = el('div','file-grid');
        br.entries.forEach(e=>{
          const c = el('div','file-card'); c.append(el('div','file-ico'+(e.type==='dir'?' dir':'')), el('div','name',e.name));
          if(e.type==='file') c.append(el('small',null,(e.size_gb??'?')+' GB'));
          c.onclick = ()=>{ if(e.type==='dir') modelAddBrowse((br.path?br.path+'/':'')+e.name); else { modelAdd.path = e.path; modelAddInspect(); } };
          list.append(c);
        });
        if(!br.entries.length) list.append(el('div','muted','Hier liegen keine .gguf-Dateien.'));
        body.append(list);
      }
    }
  } else if(modelAdd.step === 'inspect' && modelAdd.view){
    const v = modelAdd.view, info = v.info, r = v.recipe;
    body.append(el('div','mnote','Schritt 2 von 3: Rezept prüfen. Alles unten kommt aus der Datei selbst; Kontext und Rollen kannst du ändern, der Rest später im Abschnitt Modell-Einstellungen.'));
    const facts = el('div','mr-grid'); const fc = el('div','mr-card'); fc.append(el('h4',null,info.name||'Modell'));
    [['Datei', info.path],['Architektur', info.architecture+(info.expert_count?' · MoE mit '+info.expert_count+' Experten':'')],['Quantisierung', info.quantization||'?'],['Größe', info.size_gb+' GB'],['Kontext laut Datei', info.context_length||'unbekannt'],['Schichten', info.block_count||'?']]
      .forEach(([k,val])=>{ const l = el('div','line'); l.append(el('span',null,k), el('span',null,String(val))); fc.append(l); });
    facts.append(fc); body.append(facts);
    if(!v.in_models_root && v.models_root) body.append(el('div','mnote mbad','Hinweis: Die Datei liegt außerhalb des Modellordners ('+v.models_root+'). Das geht, aber die Modell-Quarantäne (model-remove) kennt sie dann nicht.'));
    const form = el('div'); form.style.cssText = 'display:grid;grid-template-columns:140px 1fr;gap:6px 10px;align-items:center;margin:8px 0';
    const idIn = el('input'); idIn.value = modelAdd.recipeId; idIn.style.cssText = 'border:1px solid var(--line);border-radius:3px;padding:4px 6px'; idIn.onchange = ()=>{ modelAdd.recipeId = idIn.value.trim(); };
    form.append(el('b',null,'Rezept-ID'), idIn);
    const rolesBox = el('div'); rolesBox.style.cssText = 'display:flex;gap:10px;flex-wrap:wrap';
    MODEL_ROLES.forEach(([id,label])=>{ const lab = el('label'); const cb = el('input'); cb.type = 'checkbox'; cb.checked = modelAdd.roles.includes(id);
      cb.onchange = ()=>{ modelAdd.roles = MODEL_ROLES.map(x=>x[0]).filter(x=> x===id ? cb.checked : modelAdd.roles.includes(x)); }; lab.append(cb, ' '+label); rolesBox.append(lab); });
    form.append(el('b',null,'Rollen'), rolesBox);
    const ctx = el('select'); r.profile.context.tiers.forEach(t=>{ const o = el('option',null,'Kontext '+t+(t===r.profile.context.maximum?' (Maximum der Datei)':'')); o.value = String(t); ctx.append(o); });
    ctx.value = String(modelAdd.context); ctx.onchange = ()=>{ modelAdd.context = Number(ctx.value); };
    form.append(el('b',null,'Standard-Kontext'), ctx);
    body.append(form);
    const det = el('details'); det.append(el('summary',null,'Rezept, wie es in '+v.overlay+' geschrieben wird')); const pre = el('pre','diag-out'); pre.textContent = v.yaml; det.append(pre); body.append(det);
    const row = el('div','row');
    const again = el('button','tool','Neu berechnen'); again.onclick = modelAddInspect;
    const back = el('button','tool','Andere Datei'); back.onclick = ()=>{ modelAdd.step = 'pick'; modelAdd.view = null; refreshModels(); };
    const req = el('button','action','Rezept anlegen (Freigabe)'); req.disabled = modelAdd.busy || !modelAdd.roles.length; req.onclick = modelAddRequest;
    row.append(req, again, back); body.append(row);
  } else if(modelAdd.step === 'gate'){
    body.append(el('div','mnote','Schritt 3 von 3: Freigabe. Genau dieser Block wird geschrieben, nichts sonst. Nach der Freigabe erscheint das Modell unten in der Liste mit „Laden“, danach „Testen“.'));
    renderPendingChange(body, 'model_add');
    if(!pendingChange) body.append(el('div','mnote','Keine offene Anfrage mehr.'));
  } else if(modelAdd.step === 'done'){
    body.append(el('div','mnote','Rezept '+(modelAdd.doneId||'')+' ist angelegt und sofort nutzbar. Unten in der Liste: „Laden“, danach „Testen“ (eine kurze Antwort mit Zeit und Token/s).'));
  }
  const close = el('button','tool','Schließen'); close.onclick = modelAddReset;
  card.append(body, close); box.append(card);
}
