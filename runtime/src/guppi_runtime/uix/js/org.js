// Organigramm in the Besatzung window: who reports to whom and what each one holds – the model of an agent company (Paperclip:
// board, org chart, goals, approvals, budgets) mapped onto what SEDRA already has. Captain = board (the gates), GUPPI = the one
// agent that steers, the roles = the recipes of the routing with the model each one uses. orgModel() is pure; everything is read-only.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

const ORG_ROLE_LABELS = {planner:'Planer', coder:'Coder', reviewer:'Prüfer', tester:'Tester', verifier:'Verifizierer', documentation:'Doku', researcher:'Recherche', context_curator:'Kontext-Kurator', tool_operator:'Werkzeug-Bediener'};
const ORG_ROLE_ORDER = ['planner','coder','reviewer','tester','verifier','documentation','researcher'];

// {captain:{gates}, guppi:{state, model, context}, roles:[{role, label, recipes:[{id, model, loaded, enabled}], state, text, agents}], budget:{tokens, runs}}
function orgModel(status, models, missions, agents, meter){
  const recipes = (models && models.recipes) || [], srv = (models && models.server) || {};
  const gates = (missions||[]).reduce((n,m)=>n + (m.pending_gates||0), 0);
  const running = (missions||[]).filter(m=>!['COMPLETE','FAILED'].includes(m.phase) && !(m.pending_gates > 0)).length;
  const loaded = recipes.find(r=>r.loaded);
  const byRole = {};
  recipes.filter(r=>r.enabled).forEach(r=>(r.roles||[]).forEach(role=>{ (byRole[role] = byRole[role] || []).push(r); }));
  const templates = (agents && agents.templates) || [], instances = (agents && agents.instances) || [];
  const roleOf = {}; templates.forEach(t=>{ roleOf[t.ref] = t.role; });
  const roles = Object.keys(byRole).sort((a,b)=>(ORG_ROLE_ORDER.indexOf(a) + 100) % 100 - (ORG_ROLE_ORDER.indexOf(b) + 100) % 100 || a.localeCompare(b)).map(role=>{
    const rs = byRole[role], onGpu = rs.find(r=>r.loaded), withFile = rs.filter(r=>r.model);
    const crew = instances.filter(i=>roleOf[i.template_ref] === role);
    let state = 'warn', text;
    if(onGpu){ state = 'ok'; text = modelName(onGpu)+' geladen'; }
    else if(withFile.length){ text = withFile.length === 1 ? modelName(withFile[0])+' (nicht geladen)' : withFile.length+' Modelle, keins geladen'; }
    else { state = 'bad'; text = 'kein Modell eingetragen'; }
    return {role, label: ORG_ROLE_LABELS[role] || role, recipes: rs.map(r=>({id:r.id, model:r.model, loaded:!!r.loaded, enabled:!!r.enabled})), state, text, agents: crew.length};
  });
  return {captain:{gates, running}, guppi:{state: status ? status.system_state : 'offline', model: srv.running ? (loaded ? modelName(loaded) : srv.model) : null, context: srv.context || null, skills: status ? (status.capability_router||{}).skills : null},
          roles, budget: meter && meter.tokens && meter.tokens.ranges ? {tokens: meter.tokens.ranges.today.tokens, runs: meter.tokens.ranges.today.runs} : null, instances: instances.length};
}

function orgNode(cls, title, lines, pill){
  const n = el('div','org-node'+(cls ? ' '+cls : ''));
  n.append(el('b',null,title));
  lines.forEach(l=>n.append(el('small',null,l)));
  if(pill) n.append(el('span','pill '+pill.tone, pill.text));
  return n;
}

async function renderOrgChart(body){
  const get = p=>api(p).then(v=>({ok:true, v}), e=>({ok:false, e:e.message}));
  const [st, mo, mi, ag, me] = await Promise.all([get('/api/status'), get('/api/models'), get('/api/missions'), get('/api/agents'), get('/api/meter')]);
  const o = orgModel(st.ok ? st.v : null, mo.ok ? mo.v : null, mi.ok ? mi.v : [], ag.ok ? ag.v : null, me.ok ? me.v : null);
  const wrap = el('div','org');
  const cap = orgNode('captain', 'Captain (du)', ['entscheidet jede Freigabe – kein Agent handelt ohne sie', o.captain.gates ? (o.captain.gates === 1 ? 'eine Freigabe wartet' : o.captain.gates+' Freigaben warten') : 'nichts wartet'], o.captain.gates ? {tone:'warn', text:'Freigaben offen'} : {tone:'ok', text:'frei'});
  cap.setAttribute('role','button'); cap.tabIndex = 0; cap.onclick = ()=>openBridge(); cap.style.cursor = 'pointer';
  wrap.append(cap, el('div','org-link'));
  const g = orgNode('guppi', 'GUPPI · Steuermann', [o.guppi.model ? 'spricht mit '+o.guppi.model+(o.guppi.context ? ' · Kontext '+o.guppi.context : '') : 'kein Modell geladen – plant nur', (o.guppi.skills !== null ? o.guppi.skills+' Skills · ' : '')+(o.captain.running ? o.captain.running+' Karte(n) in Arbeit' : 'keine Karte in Arbeit')], {tone: o.guppi.state === 'offline' ? 'bad' : o.guppi.model ? 'ok' : 'warn', text: o.guppi.state});
  g.setAttribute('role','button'); g.tabIndex = 0; g.onclick = ()=>openGuppi(); g.style.cursor = 'pointer';
  wrap.append(g, el('div','org-link'));
  const roles = el('div','org-roles');
  if(!o.roles.length) roles.append(el('div','muted','Keine Rollen: die Routing-Konfiguration hat kein aktives Rezept. Werkstatt → Neues Modell.'));
  o.roles.forEach(r=>{
    const n = orgNode('', r.label, [r.text, r.recipes.map(x=>x.id).join(', '), r.agents ? r.agents+' Agent'+(r.agents === 1 ? '' : 'en')+' mit dieser Rolle' : 'Rolle wird vom Modell ausgefüllt, kein eigener Agent'], {tone:r.state, text: r.state === 'ok' ? 'einsatzbereit' : r.state === 'warn' ? 'Modell laden' : 'kein Modell'});
    n.setAttribute('role','button'); n.tabIndex = 0; n.style.cursor = 'pointer'; n.onclick = ()=>openModelsAt('Modelle');
    roles.append(n);
  });
  wrap.append(roles);
  const budget = o.budget ? 'Budget: '+meterNumber(o.budget.tokens)+' Token heute in '+o.budget.runs+' Läufen (Guppy-Meter). ' : '';
  wrap.append(el('div','org-note', budget+'Alle Rollen teilen sich eine Grafikkarte und arbeiten nacheinander; ein Agent bekommt erst durch ein Gate des Captains eine Instanz und eine Zulassung. '+(o.instances ? o.instances+' Instanz(en) an Bord.' : 'Noch keine Instanzen an Bord.')));
  body.append(wrap);
}
