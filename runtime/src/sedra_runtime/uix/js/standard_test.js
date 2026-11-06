// Standardtest in the Modelle window: pick the duration and the criteria, run it on the loaded model, read the result, and turn the
// recommended context into a change request (the Captain approves it like any other change). Classic script; load order in retro_desktop.html.

const STD_DURATIONS = [['schnell','Schnell · 5 Min.'],['standard','Standard · 15 Min.'],['langzeit','Langzeit · 90 Min.']];
const STD_CRITERIA = [['stabilitaet','Stabilität (Fehler, Abbrüche)'],['tokens','Token-Geschwindigkeit'],['lesen_schreiben','Lesen und Schreiben (Textverarbeitung)'],['coder','Coder-Leistung (kleine Programmieraufgaben)']];
let stdTestPick = {duration:'schnell', criteria:['stabilitaet','tokens']};
let stdTestTimer = null;

function renderStandardTest(box){
  if(!modelStdState) pollStandardTest();      // first view after a page load: ask the server whether a test is running or has a result
  box.append(el('h3',null,'Teststrecke: Standardtest'));
  box.append(el('div','mnote','Findet heraus, mit welchem Kontext das geladene Modell am besten läuft. Du wählst Dauer und Kriterien. Das Modell wird dafür mehrfach neu geladen; danach steht es wieder mit dem Kontext, der übrig bleibt. Die Empfehlung wird nur als Freigabe angelegt.'));
  const card = el('div','mcard'); const body = el('div'); body.style.flex = '1';
  const dur = el('select'); STD_DURATIONS.forEach(([v,label])=>{ const o = el('option',null,label); o.value = v; dur.append(o); });
  dur.value = stdTestPick.duration; dur.onchange = ()=>{ stdTestPick.duration = dur.value; };
  body.append(el('b',null,'Dauer'), dur);
  const crit = el('div'); crit.style.cssText = 'display:flex;flex-direction:column;gap:4px;margin:6px 0';
  STD_CRITERIA.forEach(([v,label])=>{ const lab = el('label'); const cb = el('input'); cb.type = 'checkbox'; cb.checked = stdTestPick.criteria.includes(v);
    cb.onchange = ()=>{ stdTestPick.criteria = STD_CRITERIA.map(x=>x[0]).filter(x=> x===v ? cb.checked : stdTestPick.criteria.includes(x)); }; lab.append(cb, ' '+label); crit.append(lab); });
  body.append(el('b',null,'Kriterien'), crit);
  const st = modelStdState || {state:'bereit'};
  if(st.state === 'läuft') body.append(el('div','mnote thinking','Läuft: Kontext '+((st.progress||[]).slice(-1)[0]||{}).context+' ('+(((st.progress||[]).slice(-1)[0]||{}).state||'')+') · Dauer '+(st.duration||'')));
  if(st.state === 'fehler') body.append(el('div','mnote mbad','Der Standardtest ist fehlgeschlagen: '+(st.error||'unbekannt')+'.'));
  if(st.state === 'fertig' && st.result) body.append(renderStdResult(st.result));
  const go = el('button','action', st.state==='läuft' ? 'Läuft …' : 'Standardtest starten');
  go.disabled = st.state === 'läuft' || !stdTestPick.criteria.length;
  go.onclick = startStandardTest;
  body.append(el('div','row',''), go);
  card.append(body); box.append(card);
  if(st.state === 'läuft' && !stdTestTimer) stdTestTimer = setInterval(pollStandardTest, 5000);
  if(st.state !== 'läuft' && stdTestTimer){ clearInterval(stdTestTimer); stdTestTimer = null; }
}

let modelStdState = null;

async function pollStandardTest(){
  try{ modelStdState = await api('/api/standard-test'); }catch(err){ return; }
  if(modelStdState.state !== 'läuft'){ clearInterval(stdTestTimer); stdTestTimer = null; }
  refreshModels();
}

async function startStandardTest(){
  try{
    modelStdState = await api('/api/standard-test/start',{method:'POST',body:JSON.stringify({duration:stdTestPick.duration, criteria:stdTestPick.criteria})});
    if(!stdTestTimer) stdTestTimer = setInterval(pollStandardTest, 5000);
  }catch(err){ modelStdState = {state:'fehler', error: explainModelError(err.message)}; }
  refreshModels();
}

function renderStdResult(out){
  const wrap = el('div','mcard'); wrap.style.display = 'block';
  wrap.append(el('b',null,'Ergebnis · '+(out.recipe_id||'')));
  const rows = (out.results||[]).map(r=>{
    if(r.status !== 'ok') return 'Kontext '+r.context+': nicht geladen';
    const parts = ['Kontext '+r.context];
    if(r.tokens_per_s != null) parts.push(r.tokens_per_s+' Token/s');
    if(r.read_per_s != null) parts.push(r.read_per_s+' Token/s lesen');
    if(r.coder_pass != null) parts.push('Coder '+Math.round(r.coder_pass*100)+' %');
    parts.push(r.stable ? 'stabil' : 'instabil ('+r.errors+' Fehler)');
    return parts.join(' · ');
  });
  rows.forEach(t=>wrap.append(el('div','muted',t)));
  const rec = out.recommendation || {};
  if(rec.context){
    wrap.append(el('div','mnote','Empfehlung: Kontext '+rec.context+' ('+(rec.reason||'')+')'));
    const b = el('button','action','Empfehlung als Freigabe anlegen');
    b.onclick = ()=>requestStdRecommendation(out.recipe_id, rec.context, b);
    wrap.append(b);
  } else wrap.append(el('div','mnote mbad', rec.reason || 'Keine Empfehlung.'));
  return wrap;
}

async function requestStdRecommendation(recipeId, context, button){
  button.disabled = true;
  try{
    pendingChange = Object.assign({kind:'routing'}, await api('/api/routing-config/request',{method:'POST',body:JSON.stringify({recipe_id:recipeId, field:'context_recommended', value:Number(context)})}));
  }catch(err){ alert(err.message); }
  refreshModels();
}
