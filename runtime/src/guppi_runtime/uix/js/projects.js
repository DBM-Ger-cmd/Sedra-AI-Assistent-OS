// Projects: active project, desktop folders, project window with its files.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

let activeProject = null;

let activeProjectId = null;

function setActiveProject(name, id){
  activeProject = name || null;
  activeProjectId = id || null;
  updatePlaceholder();
}

// Project files: folders and files of the opened project, read-only; a file opens in the processing window.
let projectDir = '';

async function loadProjectFiles(sub){
  projectDir = sub || '';
  const grid = document.getElementById('fileGrid'), crumb = document.getElementById('fileCrumb');
  grid.replaceChildren(); crumb.replaceChildren();
  if(!activeProjectId){ grid.append(el('div','muted','Kein Projekt gewählt.')); return; }
  let out;
  try{ out = await api('/api/project/files',{method:'POST',body:JSON.stringify({project_id:activeProjectId, path:projectDir})}); }
  catch(err){ grid.append(el('div','muted','Dateien nicht lesbar: '+err.message)); return; }
  const parts = projectDir ? projectDir.split('/') : [];
  const root = el('a',null,activeProject||'Projekt'); root.onclick = ()=>loadProjectFiles('');
  crumb.append(root);
  parts.forEach((p,i)=>{ crumb.append(' / '); const a = el('a',null,p); a.onclick = ()=>loadProjectFiles(parts.slice(0,i+1).join('/')); crumb.append(a); });
  if(!out.entries.length) grid.append(el('div','muted','Dieser Ordner ist leer.'));
  out.entries.forEach(e=>{
    const card = el('div','file-card'); card.append(el('div','file-ico'+(e.type==='dir'?' dir':'')));
    card.append(el('div','name',e.name));
    if(e.type==='file') card.append(el('small',null,formatBytes(e.size||0)));
    card.onclick = ()=> e.type==='dir' ? loadProjectFiles((projectDir?projectDir+'/':'')+e.name) : openProjectFile((projectDir?projectDir+'/':'')+e.name);
    grid.append(card);
  });
  if(out.truncated) grid.append(el('div','muted','Weitere Einträge werden nicht angezeigt.'));
}

async function openProjectFile(path){
  let out;
  try{ out = await api('/api/project/file',{method:'POST',body:JSON.stringify({project_id:activeProjectId, path})}); }
  catch(err){ alert('Datei nicht lesbar: '+err.message); return; }
  showProcessor('Datei – '+path, '<b>Projekt:</b> '+escapeHtml(activeProject||'')+'<br><b>Datei:</b> '+escapeHtml(path)+(out.bytes!==undefined?'<br><b>Größe:</b> '+formatBytes(out.bytes):''), preview=>{
    if(out.binary || out.too_large){
      preview.innerHTML = '<div class="file-placeholder"><div class="big">📄</div><b>'+escapeHtml(path.split('/').pop())+'</b><div style="margin-top:8px;color:#68798b;font-size:12px">'+(out.binary?'Binärdatei, keine Textvorschau':'Datei ist größer als 100 KB, keine Vorschau')+'</div></div>';
      return;
    }
    const pre = document.createElement('pre'); pre.textContent = out.content; preview.appendChild(pre);
  });
}

function openProject(name, desc, status){
  document.getElementById('projectName').textContent = name;
  document.getElementById('projectDesc').textContent = desc;
  document.getElementById('projectStatus').textContent = status;
  document.getElementById('projectTitleBar').textContent = name + ' – Projekt';
  showWindow('projectWindow');
  document.getElementById('startMenu').classList.remove('active');
  refreshMissions();
  loadProjectFiles('');
}

let reviewedCandidatePlan=null;

function actionButton(label,fn){const b=document.createElement('button');b.className='action';b.textContent=label;b.onclick=()=>Promise.resolve(fn()).catch(e=>alert(e.message));return b;}

function showData(title,data){showProcessor(title,'<b>Runtime-Daten</b>',p=>{const pre=document.createElement('pre');pre.textContent=JSON.stringify(data,null,2);p.appendChild(pre);});}

async function createProject(){
 const name=prompt('Projektname');if(!name)return;
 try{ await api('/api/project/create',{method:'POST',body:JSON.stringify({name})}); await refreshProjects(); }
 catch(err){ uiError('Neues Projekt', err); }
}

async function refreshProjects(){
 const records=await api('/api/projects');const area=document.getElementById('realProjects');area.replaceChildren();
 records.forEach(project=>{
  const icon=el('div','desktop-icon'); icon.setAttribute('role','button'); icon.tabIndex=0; icon.title=project.display_name+' – Doppelklick oder Enter öffnet das Projekt';
  icon.append(el('div','folder'), el('div',null,project.display_name));
  attachIconDrag(icon,'project:'+project.project_id);
  icon.ondblclick=()=>openRegisteredProject(project);
  icon.onclick=()=>{ area.querySelectorAll('.desktop-icon.selected').forEach(i=>i.classList.remove('selected')); icon.classList.add('selected'); };
  icon.onkeydown=e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); openRegisteredProject(project); } };
  area.appendChild(icon);
 });
 area.appendChild(actionButton('Neues Projekt',createProject));
}

function openRegisteredProject(p){setActiveProject(p.display_name,p.project_id);openProject(p.display_name,p.workspace_path,'ACTIVE');}

// "Projekte" in the taskbar and the start menu: the folders are on the desktop (top left); point there instead of a blocking dialog.
async function openProjectRegistry(){
 try{ await refreshProjects(); }catch(err){ uiError('Projekte', err); return; }
 document.getElementById('startMenu').classList.remove('active');
 const icons=[...document.querySelectorAll('#realProjects .desktop-icon')];
 icons.forEach(i=>{ i.classList.add('selected'); setTimeout(()=>i.classList.remove('selected'),2500); });
 document.getElementById('desktopGuppiBubble').textContent = icons.length
  ? icons.length+' Projektordner liegen oben links auf dem Desktop. Doppelklick öffnet ein Projekt; die Ordner liegen im verwalteten GUPPI-Arbeitsbereich.'
  : 'Noch kein Projekt. „Neues Projekt“ oben links legt einen Ordner im verwalteten GUPPI-Arbeitsbereich an.';
}
