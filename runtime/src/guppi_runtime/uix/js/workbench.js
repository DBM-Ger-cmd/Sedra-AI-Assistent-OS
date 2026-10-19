// Werkstatt rail at the top of the Modelle window: Modell → Teststrecke → bereit. Every step shows its state in one line and exactly one
// next action; the sections below stay as they are, the rail only points at them. workbenchModel() is pure (views in, steps out).
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

// steps: [{id, title, state: 'done'|'active'|'open'|'fail', text, action: {label, id}}]
function workbenchModel(v, switches, quick, std){
  const recipes = (v && v.recipes) || [], srv = (v && v.server) || {};
  const loaded = recipes.find(r=>r.loaded), usable = recipes.filter(r=>r.model && r.enabled && r.provider === 'llama-cpp-server');
  const loaderSwitch = ((switches && switches.items) || []).find(s=>s.section === 'model_loader' && s.key === 'enabled');
  const loaderOn = !!(v && v.loader_enabled), switchOn = loaderSwitch ? loaderSwitch.value === true : null;
  const steps = [];
  // 1 Modell
  if(loaded || srv.running){
    steps.push({id:'model', title:'1 · Modell', state:'done', text:(loaded ? modelName(loaded) : srv.model||'Modell')+' ist geladen'+(srv.context ? ' · Kontext '+srv.context : ''), action:{label:'Wechseln', id:'models'}});
  } else if(!loaderOn && switchOn){
    steps.push({id:'model', title:'1 · Modell', state:'active', text:'Der Schalter „Modelle automatisch laden“ steht auf an, gilt aber erst nach dem Neustart der Oberfläche. Bis dahin scheitert Laden.', action:{label:'Schalter ansehen', id:'switches'}});
  } else if(!loaderOn){
    steps.push({id:'model', title:'1 · Modell', state:'active', text:'Laden ist ausgeschaltet (Schalter „Modelle automatisch laden“).', action:{label:'Einschalten', id:'switches'}});
  } else if(usable.length){
    steps.push({id:'model', title:'1 · Modell', state:'active', text:usable.length === 1 ? modelName(usable[0])+' ist eingerichtet, aber nicht geladen.' : usable.length+' Modelle eingerichtet, keins geladen.', action:{label:'Laden: '+modelName(usable[0]), id:'load', recipe:usable[0].id}});
  } else {
    steps.push({id:'model', title:'1 · Modell', state:'active', text:'Noch kein Modell mit Datei eingerichtet.', action:{label:'Neues Modell hinzufügen', id:'model_add'}});
  }
  const ready = steps[0].state === 'done';
  // 2 Teststrecke
  const quickOk = quick && quick.status === 'completed' && (!loaded || quick.recipe_id === loaded.id);
  const stdDone = std && std.state === 'fertig' && std.result && (!loaded || std.recipe_id === loaded.id);
  const stdRun = std && std.state === 'läuft';
  if(!ready) steps.push({id:'test', title:'2 · Teststrecke', state:'open', text:'Erst ein Modell laden.', action:null});
  else if(stdRun) steps.push({id:'test', title:'2 · Teststrecke', state:'active', text:'Standardtest läuft ('+(std.duration||'')+').', action:{label:'Fortschritt', id:'std'}});
  else if(stdDone){
    const rec = (std.result.recommendation||{}).context;
    steps.push({id:'test', title:'2 · Teststrecke', state:'done', text:'Standardtest fertig'+(rec ? ' · empfohlener Kontext '+rec : '')+(quickOk && quick.tokens_per_s ? ' · Kurztest '+quick.tokens_per_s+' Token/s' : ''), action:{label:'Ergebnis', id:'std'}});
  } else if(quickOk) steps.push({id:'test', title:'2 · Teststrecke', state:'done', text:'Kurztest bestanden: '+quick.seconds+' s'+(quick.tokens_per_s ? ' · '+quick.tokens_per_s+' Token/s' : '')+'. Der Standardtest findet den besten Kontext.', action:{label:'Standardtest', id:'std'}});
  else steps.push({id:'test', title:'2 · Teststrecke', state:'active', text:'Noch nicht getestet. Der Kurztest dauert Sekunden, der Standardtest ab 5 Minuten.', action:{label:'Kurztest', id:'quick', recipe: loaded ? loaded.id : null}});
  // 3 bereit
  if(ready) steps.push({id:'go', title:'3 · Bereit', state:(quickOk || stdDone) ? 'done' : 'active', text:(loaded ? modelName(loaded) : 'Das Modell')+' antwortet im Chat und plant Karten.', action:{label:'Mit SEDRA sprechen', id:'chat'}});
  else steps.push({id:'go', title:'3 · Bereit', state:'open', text:'Ohne Modell plant der Chat nur.', action:null});
  return steps;
}

function workbenchAction(a, v){
  if(!a) return;
  if(a.id === 'load') return modelAction('Lade '+a.recipe, '/api/model/load', {recipe_id:a.recipe});
  if(a.id === 'quick'){ const b = document.activeElement; return modelTest(a.recipe, b && b.tagName === 'BUTTON' ? b : el('button')); }
  if(a.id === 'std') return openModelsAt('Teststrecke');
  if(a.id === 'switches') return openModelsAt('Schalter');
  if(a.id === 'models') return openModelsAt('Modelle');
  if(a.id === 'model_add') return openModelAdd();
  if(a.id === 'chat') return openGuppi();
}

async function renderWorkbench(box, v){
  let switches = null;
  try{ switches = await api('/api/switches'); }catch(err){ switches = null; }
  const steps = workbenchModel(v, switches, modelAdd.test, modelStdState);
  const rail = el('div','wb-rail');
  steps.forEach(s=>{
    const c = el('div','wb-step '+s.state);
    c.append(el('b',null,s.title), el('span',null,s.text));
    if(s.action){ const b = el('button', s.state === 'active' ? 'action' : 'tool', s.action.label); b.onclick = ()=>workbenchAction(s.action, v); c.append(b); }
    rail.append(c);
  });
  box.append(rail);
}
