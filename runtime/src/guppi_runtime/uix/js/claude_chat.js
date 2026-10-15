// GUPPI Chat window in the style of the Claude Desktop app: session list on the left, conversation on the right.
// Classic script (shares the page's global scope). Sessions live in this browser (localStorage); answers come from /api/chat/reply (text only, nothing is executed).

const CC_KEY = 'guppi.cchat.v1';
let ccSessions = [], ccCurrent = null, ccBusy = false;

function ccLoad(){ try{ ccSessions = JSON.parse(localStorage.getItem(CC_KEY)) || []; }catch(e){ ccSessions = []; } }
function ccSave(){ try{ localStorage.setItem(CC_KEY, JSON.stringify(ccSessions.slice(0,100))); }catch(e){} }
function ccSession(){ return ccSessions.find(s=>s.id===ccCurrent); }

// Small markdown subset: fenced code, inline code, bold, paragraphs. Everything is escaped first.
function ccMarkdown(text){
  const parts = escapeHtml(text).split(/```[^\n]*\n?/);
  return parts.map((p,i)=> i%2 ? '<pre><code>'+p+'</code></pre>'
    : p.split(/\n{2,}/).filter(x=>x.trim()).map(x=>'<p>'+x.replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>').replace(/\n/g,'<br>')+'</p>').join('')).join('');
}

function ccRenderList(){
  const box = document.getElementById('ccList'), q = document.getElementById('ccSearch').value.toLowerCase();
  box.replaceChildren();
  const today = new Date().toDateString(), week = Date.now()-7*864e5;
  let last = '';
  ccSessions.filter(s=>!q || s.title.toLowerCase().includes(q) || s.messages.some(m=>m.content.toLowerCase().includes(q))).forEach(s=>{
    const g = new Date(s.updated).toDateString()===today ? 'Heute' : s.updated>week ? 'Letzte 7 Tage' : 'Älter';
    if(g!==last){ box.append(el('div','cc-group',g)); last = g; }
    const it = el('div','cc-item'+(s.id===ccCurrent?' on':'')), t = el('span',null,s.title), x = el('i',null,'✕');
    x.title = 'Chat löschen'; x.onclick = e=>{ e.stopPropagation(); ccDelete(s.id); };
    it.onclick = ()=>{ ccCurrent = s.id; ccRender(); }; it.append(t,x); box.append(it);
  });
}

function ccRender(){
  ccRenderList();
  const box = document.getElementById('ccMsgs'), s = ccSession();
  box.replaceChildren();
  if(!s || !s.messages.length){
    const e = el('div','cc-empty'); e.append(el('h2',null,'Wie kann GUPPI helfen?'), el('div',null,'Die Antworten kommen vom lokalen Modell, es wird nichts ausgeführt.')); box.append(e); return;
  }
  s.messages.forEach(m=>ccBubble(m));
  box.scrollTop = box.scrollHeight;
}

function ccBubble(m){
  const box = document.getElementById('ccMsgs'), d = el('div', m.role==='user' ? 'cc-u' : 'cc-a');
  if(m.role==='user') d.textContent = m.content; else { d.innerHTML = ccMarkdown(m.content); if(m.model) d.append(el('div','cc-meta',m.model)); }
  box.append(d); box.scrollTop = box.scrollHeight; return d;
}

function ccNew(){ ccCurrent = null; ccRender(); document.getElementById('ccInput').focus(); }
function ccDelete(id){ ccSessions = ccSessions.filter(s=>s.id!==id); if(ccCurrent===id) ccCurrent = null; ccSave(); ccRender(); }

async function ccSend(){
  const input = document.getElementById('ccInput'), text = input.value.trim();
  if(!text || ccBusy) return;
  let s = ccSession();
  if(!s){ s = {id:String(Date.now()), title:text.slice(0,40), updated:Date.now(), messages:[]}; ccSessions.unshift(s); ccCurrent = s.id; }
  input.value = ''; ccBusy = true; document.getElementById('ccSend').disabled = true;
  const history = s.messages.slice(-8).map(m=>({role:m.role, content:m.content}));
  s.messages.push({role:'user', content:text}); s.updated = Date.now(); ccSave(); ccRender();
  const wait = el('div','cc-a cc-think','Denkt nach ...'); document.getElementById('ccMsgs').append(wait);
  document.getElementById('ccMsgs').scrollTop = 1e9;
  let reply, model = '';
  try{
    const out = await api('/api/chat/reply',{method:'POST',body:JSON.stringify({mission_id:'', text, history, attachments:[]})});
    if(out.status === 'completed'){ reply = out.reply; model = out.model||''; }
    else reply = out.status === 'no_model' ? 'Kein Modell geladen. Im Fenster „Modelle“ eines laden.' : 'Das Modell hat nicht geantwortet: '+(out.message||'');
  }catch(err){ reply = 'Fehler: '+err.message; }
  s.messages.push({role:'assistant', content:reply, model}); s.updated = Date.now();
  ccSessions.sort((a,b)=>b.updated-a.updated); ccSave();
  ccBusy = false; document.getElementById('ccSend').disabled = false; ccRender(); input.focus();
}

function ccFillModels(){
  const sel = document.getElementById('ccModel'), src = document.getElementById('chatModel');
  sel.replaceChildren(...Array.from(src.options).map(o=>{ const n = el('option',null,o.textContent); n.value = o.value; return n; }));
  sel.value = src.value;
}

function openCChat(){
  showWindow('cchatWindow');
  ccFillModels(); ccRender();
  document.getElementById('ccInput').focus();
}

// Event bindings and the first load run from main.js (top-level code that runs at load time belongs only there).
function ccInit(){
  document.getElementById('ccInput').addEventListener('keydown', e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); ccSend(); } });
  document.getElementById('ccModel').addEventListener('change', e=>{ const src = document.getElementById('chatModel'); src.value = e.target.value; src.dispatchEvent(new Event('change')); });
  ccLoad();
}
