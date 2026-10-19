// Chat diagnosis: the state bar (/api/diagnose), chat commands (/status, /fehler, /rebind, /modelle, /log, /hilfe) and the details under an error.
// Classic script; uses slashCommand, rowsText and worstState of diag_panel.js (built by SEDRA). Reads only, except `/rebind ja`, which the Captain types or confirms himself.

let diagTimer = null;

async function refreshDiag(){
  const box = document.getElementById('diagRows'), button = document.getElementById('diagBtn');
  if(!box) return;
  try{
    const view = await api('/api/diagnose');
    box.replaceChildren(...view.rows.map(r=>{
      const row = el('div','diag-row '+r.state);
      row.append(el('span','diag-dot'), el('b',null,r.label+': '), el('span',null,r.detail));
      return row;
    }));
    button.className = 'tool diag-'+worstState(view.rows);
    button.title = rowsText(view.rows).join('\n');
  }catch(err){
    box.replaceChildren(el('div','muted','Keine Verbindung zur Runtime: '+err.message));
  }
}

function toggleDiag(){
  const pane = document.getElementById('diagPane');
  const open = pane.classList.toggle('open');
  if(open){
    refreshDiag();
    if(!diagTimer) diagTimer = setInterval(()=>{ if(pane.classList.contains('open') && !document.hidden) refreshDiag(); }, 10000);
  }
}

async function runDiagCommand(text, parsed){
  const body = addGuppiBlock(); body.textContent = '...';
  try{
    const out = await api('/api/diagnose/command',{method:'POST',body:JSON.stringify({text})});
    body.replaceChildren(el('b',null,'/'+out.command+' ('+out.at+')'), el('pre','diag-out',out.lines.join('\n')));
    if(parsed.cmd === 'rebind' && !parsed.confirm && out.lines.some(l=>l.includes('/rebind ja'))){
      const row = el('div','row'); row.append(chatButton('Jetzt binden', ()=>runDiagCommand('/rebind ja', {cmd:'rebind', confirm:true}))); body.append(row);
    }
  }catch(err){
    body.replaceChildren(el('span',null,'Der Befehl ging nicht: '+err.message));
    attachErrorDetails(body, err.message);
  }
  document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
  refreshDiag();
}

// Under an error: what it means, what to do, the raw text and a copy button.
async function attachErrorDetails(target, raw){
  try{
    const e = await api('/api/diagnose/explain',{method:'POST',body:JSON.stringify({text:String(raw)})});
    const details = el('details','diag-details'), copy = el('button','action','Kopieren');
    details.append(el('summary',null,'Details: '+e.title), el('div',null,e.hint||''), el('pre','diag-out',String(raw)));
    copy.onclick = ()=>{ if(navigator.clipboard) navigator.clipboard.writeText(String(raw)+'\n'+(e.hint||'')); };
    details.append(copy);
    target.append(details);
  }catch(_err){ /* the plain error text stays */ }
}
