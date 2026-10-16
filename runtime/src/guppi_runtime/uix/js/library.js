// Bibliothek window: three shelves – SEDRA's own capabilities (read-only), the imported libraries (read-only, copy as template),
// the Captain's own skills (edit behind a gate). Left the shelf and the list, right the reader or the editor.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

let lib = {view:null, shelf:'eigene', query:'', hits:[], open:null, page:null, edit:null, gate:null, error:'', busy:false};

const LIB_SHELF_LABEL = {eigene:'Eigene', core:'Core', full:'Alle Domänen', own:'SEDRA-Fähigkeiten'};

async function openLibrary(){
  showWindow('libraryWindow');
  await refreshLibrary();
}

async function refreshLibrary(){
  try{ lib.view = await api('/api/library'); lib.error = ''; }
  catch(err){ lib.error = err.message; }
  if(lib.shelf !== 'own') await libSearch();
  else renderLibrary();
}

async function libSearch(){
  if(lib.shelf === 'own'){ renderLibrary(); return; }
  try{ const out = await api('/api/library/search',{method:'POST',body:JSON.stringify({library:lib.shelf, query:lib.query, limit:50})}); lib.hits = out.hits; lib.error = ''; }
  catch(err){ lib.hits = []; lib.error = err.message; }
  renderLibrary();
}

async function libOpen(id, start){
  lib.edit = null;
  try{ lib.page = await api('/api/library/read',{method:'POST',body:JSON.stringify({library:lib.shelf, id, start: start||1})}); lib.open = id; lib.error = ''; }
  catch(err){ lib.error = err.message; }
  renderLibrary();
}

// the editor: a new skill from the template, an own skill's text, or a library skill copied as a template
async function libEdit(id, fromLibrary){
  let text = (lib.view && lib.view.template || '').replace(/\{id\}/g, id || 'mein-skill').replace(/\{title\}/g, id || 'Mein Skill');
  if(id && fromLibrary){
    try{ text = (await api('/api/library/text',{method:'POST',body:JSON.stringify({library:fromLibrary, id})})).text; }
    catch(err){ lib.error = err.message; renderLibrary(); return; }
  }
  lib.edit = {id: fromLibrary && fromLibrary !== 'eigene' ? '' : (id || ''), text, source: fromLibrary || null};
  lib.page = null; lib.open = null;
  if(lib.shelf !== 'eigene'){ lib.shelf = 'eigene'; await libSearch(); } else renderLibrary();      // the list on the left follows the shelf
  const t = document.getElementById('libEditor'); if(t) t.focus();
}

async function libRequest(deleteIt){
  const idInput = document.getElementById('libEditId'), editor = document.getElementById('libEditor');
  const id = (idInput ? idInput.value : lib.edit.id).trim().toLowerCase(), text = deleteIt ? '' : editor.value;
  lib.busy = true; renderLibrary();
  try{ lib.gate = await api('/api/library/custom/request',{method:'POST',body:JSON.stringify({id, text})}); lib.error = ''; }
  catch(err){ lib.error = explainLibError(err.message); }
  lib.busy = false; renderLibrary();
}

function explainLibError(m){
  const s = String(m||'');
  if(s.includes('skill_id_invalid')) return 'Die Kennung braucht 2–60 Zeichen: Kleinbuchstaben, Ziffern, Bindestrich (z. B. „review-checkliste“).';
  if(s.includes('frontmatter_name_and_description_required')) return 'Der Text beginnt mit einem Kopf zwischen zwei „---“-Zeilen, der name: und description: enthält; über die Beschreibung findet der Coder den Skill.';
  if(s.includes('skill_text_flagged')) return 'Der Text enthält Muster, die die Bibliothek nicht aufnimmt (Anweisungen an den Agenten statt an die Arbeit: Regeln umgehen, vor dem Captain verbergen, Daten senden, heruntergeladenen Code ausführen): '+s.split(':')[1];
  if(s.includes('nothing_changed')) return 'Nichts geändert.';
  if(s.includes('skill_too_large')) return 'Zu groß (höchstens 200 kB).';
  if(s.includes('skill_body_empty')) return 'Der Skill braucht einen Text unter dem Kopf.';
  if(s.includes('file_changed_repeat_request')) return 'Die Datei hat sich seit der Anfrage geändert; bitte neu anfordern.';
  return s;
}

async function libApply(approve){
  const g = lib.gate; if(!g) return;
  lib.busy = true; renderLibrary();
  try{
    if(approve){
      await api('/api/mission/approve',{method:'POST',body:JSON.stringify({mission_id:g.mission_id, gate_id:g.gate.gate_id})});
      await api('/api/library/custom/apply',{method:'POST',body:JSON.stringify({mission_id:g.mission_id})});
      lib.edit = null; lib.open = null; lib.page = null;
    } else await api('/api/mission/reject',{method:'POST',body:JSON.stringify({mission_id:g.mission_id, gate_id:g.gate.gate_id})});
    lib.gate = null; lib.error = '';
  }catch(err){ lib.error = explainLibError(err.message); }
  lib.busy = false;
  await refreshLibrary();
}

function libCard(title, sub, onclick, on){
  const c = el('div','deck-row'+(on ? ' ok' : '')); c.setAttribute('role','button'); c.tabIndex = 0;
  c.append(el('b',null,title)); if(sub) c.append(el('small',null,sub));
  c.onclick = onclick; c.onkeydown = e=>{ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); onclick(); } };
  return c;
}

function renderLibrary(){
  const box = document.getElementById('libraryBody'); if(!box) return;
  box.replaceChildren();
  const v = lib.view;
  if(!v){ box.append(el('div','mnote'+(lib.error?' mbad':''), lib.error ? 'Bibliothek nicht lesbar: '+lib.error : 'Bibliothek wird geladen ...')); return; }
  const side = el('aside','lib-side'), main = el('section','lib-main');
  // shelves
  const shelves = el('div','agent-tabs');
  const names = [...v.libraries.map(l=>l.name), 'own'];
  names.forEach(n=>{
    const l = v.libraries.find(x=>x.name === n);
    const b = el('button','tool'+(lib.shelf === n ? ' on' : ''), (LIB_SHELF_LABEL[n]||n)+' · '+(n === 'own' ? v.own.length : l.count));
    b.title = n === 'own' ? 'Die Fähigkeiten der Runtime (skill.yaml), Vertrag der Runtime, hier nur lesbar' : (l.note||'')+(l.available ? '' : ' – '+l.hint);
    b.setAttribute('aria-pressed', lib.shelf === n ? 'true' : 'false');
    b.onclick = ()=>{ lib.shelf = n; lib.open = null; lib.page = null; lib.edit = null; libSearch(); };
    shelves.append(b);
  });
  side.append(shelves);
  if(lib.shelf !== 'own'){
    const q = el('input'); q.className = 'lib-search'; q.placeholder = 'Suchen (z. B. review, tests, api) …'; q.value = lib.query; q.setAttribute('aria-label','Skills durchsuchen');
    q.oninput = ()=>{ lib.query = q.value; clearTimeout(lib.timer); lib.timer = setTimeout(libSearch, 250); };
    side.append(q);
  }
  const list = el('div','lib-list');
  if(lib.shelf === 'own'){
    v.own.forEach(s=>list.append(libCard(s.name, (s.description||'').slice(0,120)+' · v'+(s.version||'?'), ()=>{ lib.open = s.id; lib.page = {own:s}; lib.edit = null; renderLibrary(); }, lib.open === s.id)));
  } else {
    const shelf = v.libraries.find(x=>x.name === lib.shelf);
    if(shelf && !shelf.available) list.append(el('div','mnote mbad', shelf.hint));
    if(lib.shelf === 'eigene'){ const add = el('button','action','Neuer Skill …'); add.onclick = ()=>libEdit('', null); list.append(add); }
    if(!lib.hits.length && shelf && shelf.available) list.append(el('div','muted', lib.query ? 'Kein Treffer.' : (lib.shelf === 'eigene' ? 'Noch kein eigener Skill. „Neuer Skill“ beginnt mit einer Vorlage; aus Core oder Alle Domänen lässt sich jeder Skill „Als Vorlage kopieren“.' : 'Leer.')));
    lib.hits.forEach(h=>list.append(libCard(h.name, (h.description||'').slice(0,140)+(h.lines ? ' · '+h.lines+' Zeilen' : ''), ()=>libOpen(h.id), lib.open === h.id)));
  }
  side.append(list);
  // right side: editor, gate, reader or empty state
  if(lib.error) main.append(el('div','mnote mbad', lib.error));
  if(lib.gate) main.append(renderLibGate());
  else if(lib.edit) main.append(renderLibEditor());
  else if(lib.page && lib.page.own) main.append(renderOwnSkill(lib.page.own));
  else if(lib.page) main.append(renderLibReader());
  else { const e = el('div','cc-empty'); e.append(el('h2',null,'Bibliothek'), el('div',null,'Links ein Regal wählen und einen Skill anklicken. Eigene Skills kannst du hier schreiben; jede Änderung braucht deine Freigabe und wird vorher gesichert.')); main.append(e); }
  box.append(side, main);
}

function renderOwnSkill(s){
  const w = el('div','lib-reader');
  w.append(el('h3',null,s.name+' · v'+(s.version||'?')), el('div','mnote',s.description||''));
  const t = agentTable(['Feld','Wert'], [['Kennung', s.id], ['Fähigkeiten', (s.capabilities||[]).join(', ')], ['Auslöser', (s.triggers||[]).join(', ')], ['Werkzeuge', (s.tool_hints||[]).join(', ')], ['Guard', s.guard||'–']]);
  w.append(t, el('div','mnote','Eine Fähigkeit der Runtime (skills/<id>/skill.yaml): sie ist Teil des Vertrags zwischen Core und Skill und wird hier nicht bearbeitet. Was der Coder nachschlägt, steht in den Regalen links.'));
  return w;
}

function renderLibReader(){
  const p = lib.page, w = el('div','lib-reader');
  const head = el('div','lib-head'); head.append(el('h3',null,p.name));
  const acts = el('div');
  if(p.editable){ const e = el('button','action','Bearbeiten'); e.onclick = ()=>libEdit(p.id, 'eigene'); acts.append(e); }
  else { const c = el('button','tool','Als Vorlage kopieren'); c.title = 'Der Text wird in einen neuen eigenen Skill übernommen; das Original bleibt unverändert'; c.onclick = ()=>libEdit(p.id, lib.shelf); acts.append(c); }
  head.append(acts); w.append(head);
  w.append(el('div','mnote',(p.description||'')+(p.source ? ' · Quelle: '+p.source : '')+(p.license ? ' · Lizenz: '+p.license : '')+' · '+p.total+' Zeilen'));
  const pre = el('pre','lib-text'); pre.textContent = p.page; w.append(pre);
  const nav = el('div','row');
  nav.append(el('small','muted','Zeilen '+p.first+'–'+p.last+' von '+p.total+' '));
  if(p.first > 1){ const b = el('button','tool','Zurück'); b.onclick = ()=>libOpen(p.id, Math.max(1, p.first - 120)); nav.append(b); }
  if(p.last < p.total){ const b = el('button','tool','Weiter'); b.onclick = ()=>libOpen(p.id, p.last + 1); nav.append(b); }
  (p.references||[]).forEach(r=>{ const b = el('button','tool',r); b.title = 'Begleitdatei'; b.onclick = async()=>{ try{ lib.page = Object.assign({}, await api('/api/library/read',{method:'POST',body:JSON.stringify({library:lib.shelf, id:p.id, reference:r})}), {references:p.references}); }catch(err){ lib.error = err.message; } renderLibrary(); }; nav.append(b); });
  w.append(nav);
  return w;
}

function renderLibEditor(){
  const e = lib.edit, w = el('div','lib-reader');
  w.append(el('h3',null, e.id ? 'Eigenen Skill bearbeiten: '+e.id : 'Neuer eigener Skill'));
  if(e.source && e.source !== 'eigene') w.append(el('div','mnote','Vorlage aus „'+(LIB_SHELF_LABEL[e.source]||e.source)+'“. Gib eine eigene Kennung; der Text liegt dann unter local_config/skill_library/skills/<kennung>/SKILL.md.'));
  const row = el('div','row'); const lab = el('label',null,'Kennung '); const idIn = el('input'); idIn.id = 'libEditId'; idIn.value = e.id; idIn.placeholder = 'z. B. review-checkliste'; idIn.disabled = !!(e.id && e.source === 'eigene'); idIn.setAttribute('aria-label','Kennung');
  lab.append(idIn); row.append(lab); w.append(row);
  const ta = el('textarea','lib-editor'); ta.id = 'libEditor'; ta.value = e.text; ta.spellcheck = false; ta.setAttribute('aria-label','Skill-Text (Markdown)');
  w.append(ta);
  const acts = el('div','row');
  const ok = el('button','action','Zur Freigabe'); ok.disabled = lib.busy; ok.onclick = ()=>libRequest(false); acts.append(ok);
  const cancel = el('button','tool','Verwerfen'); cancel.onclick = ()=>{ lib.edit = null; renderLibrary(); }; acts.append(cancel);
  if(e.id && e.source === 'eigene'){ const del = el('button','tool','Löschen …'); del.onclick = ()=>{ if(confirm('Skill '+e.id+' löschen? Der Ordner wird nur beiseitegelegt (.bak).')) libRequest(true); }; acts.append(del); }
  w.append(acts, el('div','mnote','Kopf: name und description zwischen „---“-Zeilen; darunter Markdown. Der Coder liest den Text als Nachschlagewerk, nichts daraus wird ausgeführt. Geschrieben wird erst nach deiner Freigabe, mit Sicherung.'));
  return w;
}

function renderLibGate(){
  const g = lib.gate, b = g.binding, w = el('div','lib-reader');
  w.append(el('h3',null,'Freigabe nötig: '+b.describe));
  w.append(el('div','mnote', b.delete ? 'Der Ordner wird beiseitegelegt (.bak-<datum>-uix), nichts wird endgültig gelöscht.' : 'Die Datei local_config/skill_library/skills/'+b.skill_id+'/SKILL.md wird geschrieben; eine bestehende Fassung wird vorher gesichert.'));
  if(!b.delete){ const det = el('details'); det.append(el('summary',null,'Genau dieser Text ('+(b.text.split('\n').length)+' Zeilen)')); const pre = el('pre','lib-text'); pre.textContent = b.text; det.append(pre); w.append(det); }
  const acts = el('div','row');
  const ok = el('button','action','Freigeben und schreiben'); ok.disabled = lib.busy; ok.onclick = ()=>libApply(true); acts.append(ok);
  const no = el('button','tool','Ablehnen'); no.disabled = lib.busy; no.onclick = ()=>libApply(false); acts.append(no);
  w.append(acts);
  return w;
}
