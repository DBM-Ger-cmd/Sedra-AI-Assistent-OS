// Chat window: greeting, history, model answers, sending, new chat.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

let greetedProject;

function updatePlaceholder(){
  document.getElementById('msgInput').placeholder = activeProject ? 'Auftrag für dieses Projekt eingeben ...' : 'Auftrag eingeben ...';
}

function greetingHtml(){
  return activeProject
    ? 'Projekt <b>' + escapeHtml(activeProject) + '</b> ausgewählt. Woran möchtest du als Nächstes arbeiten?'
    : 'Noch kein Projekt gewählt. Du kannst trotzdem schreiben; für Projektaufträge öffne einen Projektordner per Doppelklick.';
}

function addGuppiMessage(html){
  const chat = document.getElementById('chat');
  chat.insertAdjacentHTML('beforeend','<div class="msg"><div class="av"></div><div class="bub"><b>SEDRA:</b> ' + html + '</div></div>');
  chat.scrollTop = chat.scrollHeight;
}

function focusInput(){
  const input = document.getElementById('msgInput');
  if(input) input.focus();
}

// The app window may take focus only after the page loaded; focus again then, without taking it from another field.
function refocusInput(){
  const win = document.getElementById('guppiWindow');
  const a = document.activeElement;
  if(win && win.classList.contains('focused') && (!a || a === document.body)) focusInput();      // only when SEDRA is the front window (the Deck has its own input)
}

function initChat(prefix){
  greetedProject = activeProject;
  chatHistory.length = 0; chatSessionMission = null;
  updatePlaceholder();
  document.getElementById('chat').innerHTML = '';
  addGuppiMessage((prefix ? prefix + ' ' : '') + greetingHtml());
}

function openGuppi(){
  showWindow('guppiWindow');
  // keep the history; greet again only when the project changed since the last greeting
  if(greetedProject !== activeProject){ greetedProject = activeProject; addGuppiMessage(greetingHtml()); }
  document.getElementById('startMenu').classList.remove('active');
  focusInput();
}

// A SEDRA message whose body is built with DOM calls (no HTML from mission data); returns the body element.
function addGuppiBlock(){
  const chat = document.getElementById('chat');
  const msg = el('div','msg'), bub = el('div','bub');
  msg.append(el('div','av'), bub);
  bub.append(el('b',null,'SEDRA: '));
  const body = el('span'); bub.append(body);
  chat.append(msg);
  chat.scrollTop = chat.scrollHeight;
  return body;
}

// An error of the shell itself (not of the runtime): one message in the chat with the details, never a silent failure.
function uiError(where, err){
  const msg = err && err.message ? err.message : String(err);
  console.warn('[uix]', where, err);
  try{
    const body = addGuppiBlock();
    body.append(el('span',null,(where ? where+': ' : 'Fehler in der Oberfläche: ')+msg+' '));
    attachErrorDetails(body, msg);
  }catch(_e){ /* the chat is not there yet: the console entry stays */ }
}

function chatButton(label, fn){
  const b = el('button','action',label);
  b.onclick = ()=>{ b.disabled = true; Promise.resolve(fn()).catch(e=>{ b.disabled = false; alert(e.message); }); };
  return b;
}

const chatHistory = [];

// Files and folders attached to the next message (read-only; the server re-reads them when the message is sent).
let attachments = [];

function renderAttachments(){
  const bar = document.getElementById('attachBar');
  const form = bar.querySelector('.attach-form');
  bar.replaceChildren(...attachments.map((p,i)=>{
    const chip = el('span','chip', p.split(/[\\/]/).filter(Boolean).pop()+' ✕');
    chip.title = p+' – klicken zum Entfernen';
    chip.onclick = ()=>{ attachments.splice(i,1); renderAttachments(); };
    return chip;
  }));
  if(form) bar.append(form);
}

// A small input in the attach bar instead of a prompt() dialog: Enter attaches, Escape closes.
function attachPath(){
  const bar = document.getElementById('attachBar');
  let form = bar.querySelector('.attach-form');
  if(form){ form.querySelector('input').focus(); return; }
  form = el('span','attach-form');
  const input = el('input'); input.placeholder = 'Vollständiger Pfad einer Datei oder eines Ordners (nur lesen), z. B. D:\\Modelle'; input.setAttribute('aria-label','Pfad zum Anhängen');
  const ok = el('button','action','Anhängen'), cancel = el('button','tool','Abbrechen');
  const close = ()=>{ form.remove(); focusInput(); };
  const submit = async()=>{
    const raw = input.value.trim(); if(!raw) return;
    ok.disabled = true;
    try{
      if(attachments.length >= 5) throw new Error('Höchstens 5 Anhänge pro Nachricht.');
      const info = await api('/api/chat/attach',{method:'POST',body:JSON.stringify({path:raw})});
      if(!attachments.includes(info.path)) attachments.push(info.path);
      close(); renderAttachments();
    }catch(err){ ok.disabled = false; input.setCustomValidity(''); addGuppiMessage('Anhängen nicht möglich: '+escapeHtml(err.message)); input.focus(); }
  };
  ok.onclick = submit; cancel.onclick = close;
  input.addEventListener('keydown', e=>{ if(e.key === 'Enter'){ e.preventDefault(); submit(); } if(e.key === 'Escape') close(); });
  form.append(input, ok, cancel); bar.append(form); input.focus();
}

function attachmentNote(list){
  return list && list.length ? '\n\nAngehängt:\n'+list.join('\n') : '';
}

let chatSessionMission = null;

async function askModel(body, text, attached=[]){
  try{
    const out = await api('/api/chat/reply',{method:'POST',body:JSON.stringify({mission_id:chatSessionMission||'', text, history:chatHistory.slice(0,-1), attachments:attached})});
    body.replaceChildren(); body.classList.remove('thinking');      // the 'Denkt nach' pulse stays until the answer is here
    if(out.status === 'completed'){
      chatSessionMission = out.mission_id;
      body.append(el('span',null,out.reply));
      if(out.truncated) body.append(el('div','muted','Die Antwort wurde gekürzt (Token-Grenze).'));
      body.append(el('div','muted','Antwort von '+out.model+' – nur Text, es wurde nichts ausgeführt.'));
      const row = el('div','row');
      row.append(chatButton('Als Auftrag planen', ()=>planCard(text+attachmentNote(attached))));
      body.append(row);
      chatHistory.push({role:'assistant', content:out.reply});
      return;
    }
    chatHistory.pop(); body.classList.remove('thinking');
    if(out.status === 'no_model'){
      body.append(el('span',null,'Kein Modell geladen, deshalb nur ein Plan. '));
      body.append(chatButton('Modelle öffnen', openModels));
      await planCard(text+attachmentNote(attached));
    }else{
      body.append(el('span',null,'Das Modell hat nicht geantwortet: '+out.message+' '));
      attachErrorDetails(body, out.message);
      body.append(chatButton('Als Auftrag planen', ()=>planCard(text+attachmentNote(attached))));
    }
  }catch(err){
    chatHistory.pop();
    body.classList.remove('thinking');
    body.replaceChildren(el('span',null,'Fehler: '+err.message+' '));
    attachErrorDetails(body, err.message);
    body.append(chatButton('Erneut senden', async()=>{ body.closest('.msg').remove(); await sendText(text, false, attached); }));
  }
}

function sendMessage(){
  const input = document.getElementById('msgInput');
  const text = input.value.trim();
  if(!text) return;
  input.value='';
  const sent = attachments; attachments = []; renderAttachments();
  sendText(text, true, sent);
}

function sendText(text, echo, attached=[]){
  const chat = document.getElementById('chat');
  if(echo) chat.insertAdjacentHTML('beforeend','<div class="msg"><div class="av" style="background:linear-gradient(180deg,#b7caff,#6f8fdc);border-color:#4d66a4"></div><div class="bub"><b>Du:</b> '+escapeHtml(text)+(attached.length?'<div class="muted">Angehängt: '+attached.map(escapeHtml).join(', ')+'</div>':'')+'</div></div>');
  chat.scrollTop = chat.scrollHeight;
  const diag = slashCommand(text);
  if(diag) return runDiagCommand(text, diag);      // /status, /fehler, /rebind ... (diag.js); /plan is not one of them
  const plan = text.match(/^\/plan\s+([\s\S]+)/i);
  if(plan) return planCard(plan[1].trim()+attachmentNote(attached));      // explicit order: straight to a plan
  const body = addGuppiBlock(); body.textContent = 'Denkt nach'; body.classList.add('thinking');
  chatHistory.push({role:'user', content:text});
  return askModel(body, text, attached);
}

function newChat(){
  showWindow('guppiWindow');
  initChat('Neuer Chat gestartet.');      // the one place that clears the history on purpose
  hideContext();
  focusInput();
}
