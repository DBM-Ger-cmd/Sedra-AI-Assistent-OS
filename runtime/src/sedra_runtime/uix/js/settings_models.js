// API und Modelle – der Modellkatalog (Vorbild: die Modellseite von build.nvidia.com).
// Die Liste kommt live vom Anbieter, auf Klick. Ohne Abfrage zeigt NVIDIA einen Vorschlag: einen Schnappschuss der Seite vom
// 16.10.2026, ausdrücklich nicht live geprüft. „Als Standard nehmen“ schreibt in die Einstellungen; wirksam nach dem nächsten Start.
// Classic script: uses settingsState, fetchModels, refreshSettings and api from settings.js.

const NVIDIA_SNAPSHOT_IDS = [
  'deepseek-ai/deepseek-v4.1-flash', 'google/diffusiongemma-26b-a4b-it', 'google/gemma-4-31b-it', 'meta/muse-glimmer-30b',
  'nvidia/cosmos3-nano', 'nvidia/cosmos3-nano-reasoner', 'nvidia/ising-calibration-1.5-31b', 'nvidia/kumo-tabular',
  'nvidia/kumo-relational', 'nvidia/nemotron-3-embed-1b', 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
  'nvidia/nemotron-3-ultra-550b-a55b', 'nvidia/nemotron-3.5-content-safety', 'nvidia/nemotron-3.5-lightning-30b-a3b',
  'nvidia/nemotron-3.5-super-vl-120b-a12b', 'nvidia/riva-translate-4b-instruct-v2', 'poolside/laguna-xs-2.1',
  'stepfun-ai/step-5-preview', 'z-ai/glm-5-3', 'z-ai/glm-5-3-flash', 'resemble-ai/chatterbox-multilingual'
];

function modelsTabBar(){
  const bar = settingsEl('div', null, 'settings-tabs');
  [['anbieter', 'Anbieter und Schlüssel'], ['modelle', 'Modelle']].forEach(([id, label])=>{
    const b = settingsEl('button', label, id === settingsState.tab ? 'tool p' : 'tool');
    b.type = 'button';
    b.onclick = ()=>{ settingsState.tab = id; renderSettings(); };
    bar.append(b);
  });
  return bar;
}

function renderModels(body, d){
  const providers = d.providers || [];
  const pid = settingsState.modelsProvider || (providers.find(p=>p.key !== 'fehlt') || providers[0] || {}).id;
  settingsState.modelsProvider = pid;
  const prov = providers.find(p=>p.id === pid) || {};
  body.append(settingsEl('p', 'Welche Modelle ein Anbieter für deinen Schlüssel anbietet, fragt SEDRA beim Anbieter ab (auf Klick). Gewählt wird hier das Standardmodell; wirksam nach dem nächsten Start.', 'mnote'));

  const bar = settingsEl('div', null, 'mcat-bar');
  const pick = settingsEl('select');
  providers.forEach(p=>{ const o = document.createElement('option'); o.value = p.id; o.textContent = p.id + ' · ' + p.status; pick.append(o); });
  pick.value = pid;
  pick.onchange = ()=>{ settingsState.modelsProvider = pick.value; renderSettings(); };
  const load = settingsEl('button', 'Modelle abfragen', 'tool'); load.type = 'button';
  load.onclick = ()=>fetchModels(pid);
  const search = settingsEl('input'); search.type = 'search'; search.placeholder = 'Modell suchen …';
  search.value = settingsState.modelsQuery || ''; search.oninput = ()=>{ settingsState.modelsQuery = search.value; renderSettings(); };
  bar.append(pick, load, search);
  body.append(bar);

  const live = ((settingsState.models || {})[pid]) || null;
  const list = live || (pid === 'nvidia' ? NVIDIA_SNAPSHOT_IDS : []);
  const source = live ? 'vom Anbieter abgefragt' : (pid === 'nvidia' ? 'Vorschlag von der NVIDIA-Seite (16.10.2026), nicht live geprüft' : 'noch nicht abgefragt – „Modelle abfragen“');
  body.append(settingsEl('div', prov.key === 'fehlt' ? 'Ohne Schlüssel kann SEDRA nichts abfragen. Den Schlüssel trägst du unter „Anbieter und Schlüssel“ ein.' : source, 'mnote ' + (live ? 'ok' : 'warn')));

  const q = (settingsState.modelsQuery || '').trim().toLowerCase();
  const shown = list.filter(id=>!q || id.toLowerCase().includes(q));
  const grid = settingsEl('div', null, 'mcat-grid');
  shown.forEach(id=>grid.append(modelCard(pid, id, prov, !!live)));
  body.append(grid);
  if(!shown.length) body.append(settingsEl('div', list.length ? 'Kein Modell passt zur Suche.' : '', 'mnote'));
}

function modelCard(pid, id, prov, isLive){
  const slash = id.indexOf('/');
  const publisher = slash > 0 ? id.slice(0, slash) : '';
  const name = slash > 0 ? id.slice(slash + 1) : id;
  const card = settingsEl('div', null, 'mcat-card' + (prov.default_model === id ? ' is-default' : ''));
  card.append(settingsEl('div', publisher, 'mcat-pub'), settingsEl('div', name, 'mcat-name'));
  const badges = settingsEl('div');
  if(prov.default_model === id) badges.append(settingsEl('span', 'Standard', 'mcat-badge ok'));
  badges.append(settingsEl('span', isLive ? 'vom Anbieter' : 'Vorschlag', 'mcat-badge'));
  card.append(badges);
  const take = settingsEl('button', prov.default_model === id ? 'Ist der Standard' : 'Als Standard nehmen', 'tool');
  take.type = 'button';
  take.disabled = prov.default_model === id;
  take.onclick = ()=>setDefaultModel(pid, id);
  card.append(take);
  return card;
}

async function setDefaultModel(pid, id){
  const d = settingsState.data || {};
  const providers = {};
  providers[pid] = {default_model: id};
  try{
    await api('/api/cloud/save', {method: 'POST', body: JSON.stringify({enabled: !!d.enabled, providers})});
    settingsState.msg = id + ' ist jetzt das Standardmodell von ' + pid + '. Wirksam nach dem nächsten Start.';
  }catch(err){ settingsState.msg = 'Nicht gespeichert: ' + err.message; }
  await refreshSettings();
}
