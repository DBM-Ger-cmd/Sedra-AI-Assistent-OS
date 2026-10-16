// Einstellungen: API-Einstellungen für Cloud-Modelle (Captain-Wunsch 16.10.2026). Standard: alles aus.
// Ein Schlüssel wird nie angezeigt: die Oberfläche sieht nur den Zustand (umgebung · gespeichert · fehlt).
// Speichern ist der Klick des Captains; die Einstellungen wirken nach dem nächsten Start.
// Classic script: shares the page's global scope with the other files in uix/js.

const settingsState = {data: null, error: '', msg: '', busy: false};

async function openSettings(){
  showWindow('settingsWindow');
  await refreshSettings();
}

async function refreshSettings(){
  try{ settingsState.data = await api('/api/cloud'); settingsState.error = ''; }
  catch(err){ settingsState.error = err.message; }
  renderSettings();
}

function settingsEl(tag, text, cls){
  const node = document.createElement(tag);
  if(text !== undefined && text !== null) node.textContent = text;
  if(cls) node.className = cls;
  return node;
}

const KEY_STATE_TEXT = {
  umgebung: 'Schlüssel: aus der Umgebungsvariable (wird nicht angezeigt)',
  gespeichert: 'Schlüssel: verschlüsselt gespeichert (Windows-Benutzer)',
  fehlt: 'Schlüssel: fehlt'
};

function renderSettings(){
  const body = document.getElementById('settingsBody');
  if(!body) return;
  body.replaceChildren();
  if(settingsState.error){ body.append(settingsEl('div', 'Einstellungen nicht lesbar: ' + settingsState.error, 'mnote mbad')); return; }
  const d = settingsState.data;
  if(!d){ body.append(settingsEl('div', 'Einstellungen werden geladen ...')); return; }

  body.append(settingsEl('h3', 'API-Einstellungen (Cloud-Modelle)'));
  body.append(settingsEl('p', 'Standard: aus. Was den Rechner verlässt, prüft der Inhaltsschutz bei jedem Aufruf. Personenbezug wird vor dem Versand pseudonymisiert und anonymisiert. Gesperrte Kategorien bleiben lokal. Änderungen wirken nach dem nächsten Start.', 'mnote'));

  const master = document.createElement('label');
  const masterBox = settingsEl('input'); masterBox.type = 'checkbox'; masterBox.id = 'cloudMaster'; masterBox.checked = !!d.enabled;
  master.append(masterBox, ' Cloud-Modelle insgesamt einschalten');
  body.append(master);

  for(const p of d.providers){
    const box = settingsEl('fieldset', null, 'cloud-provider');
    box.dataset.provider = p.id;
    box.append(settingsEl('legend', p.id + ' (' + (p.kind === 'anthropic' ? 'Anthropic Messages API' : 'OpenAI-kompatibel') + ')'));

    const on = document.createElement('label');
    const onBox = settingsEl('input'); onBox.type = 'checkbox'; onBox.className = 'cp-enabled'; onBox.checked = !!p.enabled;
    on.append(onBox, ' Anbieter aktiv');
    box.append(on);

    const model = settingsEl('input'); model.type = 'text'; model.className = 'cp-model'; model.value = p.default_model || '';
    model.placeholder = 'Modellname des Anbieters'; model.maxLength = 120;
    box.append(settingsEl('label', 'Modell'), model);

    const url = settingsEl('input'); url.type = 'text'; url.className = 'cp-url'; url.value = p.base_url; url.maxLength = 200;
    box.append(settingsEl('label', 'Adresse (https)'), url);

    box.append(settingsEl('div', KEY_STATE_TEXT[p.key] || '', 'mnote'));
    if(p.key_store_available){
      const pw = settingsEl('input'); pw.type = 'password'; pw.className = 'cp-key'; pw.autocomplete = 'off'; pw.placeholder = 'Neuer API-Schlüssel';
      const save = settingsEl('button', 'Schlüssel speichern', 'tool'); save.type = 'button';
      save.onclick = ()=>saveKey(p.id, pw.value);
      const del = settingsEl('button', 'Schlüssel löschen', 'tool'); del.type = 'button';
      del.onclick = ()=>clearKey(p.id);
      box.append(pw, save, del);
    } else {
      box.append(settingsEl('div', 'Die verschlüsselte Ablage läuft nur unter Windows. Hier bleibt die Umgebungsvariable GUPPI_SECRET_' + p.id.toUpperCase().replace(/-/g, '_') + '_API_KEY.', 'mnote'));
    }
    body.append(box);
  }

  const row = settingsEl('div', null, 'settings-row');
  const saveAll = settingsEl('button', 'Einstellungen speichern', 'tool'); saveAll.type = 'button';
  saveAll.disabled = settingsState.busy;
  saveAll.onclick = saveSettings;
  row.append(saveAll);
  body.append(row);
  body.append(settingsEl('div', settingsState.msg, 'mnote'));
}

function collectSettings(){
  const providers = {};
  document.querySelectorAll('#settingsBody .cloud-provider').forEach(box=>{
    providers[box.dataset.provider] = {
      enabled: box.querySelector('.cp-enabled').checked,
      default_model: box.querySelector('.cp-model').value.trim() || null,
      base_url: box.querySelector('.cp-url').value.trim()
    };
  });
  return {enabled: document.getElementById('cloudMaster').checked, providers};
}

async function saveSettings(){
  settingsState.busy = true; settingsState.msg = '';
  try{
    await api('/api/cloud/save', {method: 'POST', body: JSON.stringify(collectSettings())});
    settingsState.msg = 'Gespeichert. Wirkt nach dem nächsten Start der Oberfläche.';
  }catch(err){ settingsState.msg = 'Nicht gespeichert: ' + err.message; }
  settingsState.busy = false;
  await refreshSettings();
}

async function saveKey(provider, value){
  settingsState.msg = '';
  try{
    await api('/api/cloud/key', {method: 'POST', body: JSON.stringify({provider, value})});
    settingsState.msg = 'Schlüssel für ' + provider + ' verschlüsselt gespeichert. Wirkt nach dem nächsten Start.';
  }catch(err){ settingsState.msg = 'Schlüssel nicht gespeichert: ' + err.message; }
  await refreshSettings();
}

async function clearKey(provider){
  settingsState.msg = '';
  try{
    await api('/api/cloud/key', {method: 'POST', body: JSON.stringify({provider, clear: true})});
    settingsState.msg = 'Schlüssel für ' + provider + ' gelöscht.';
  }catch(err){ settingsState.msg = 'Nicht gelöscht: ' + err.message; }
  await refreshSettings();
}
