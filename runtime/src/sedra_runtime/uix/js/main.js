// Start-up: event bindings and first calls. Runs last, after every other script is loaded.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

restoreTheme();                                       // first: a remembered Erscheinungsbild, before anything is drawn

window.addEventListener('load', ()=>{ setTimeout(refocusInput, 300); });

// nothing fails silently: an uncaught error or a rejected promise of the shell shows up in the chat (hardening 2026-10-14)
window.addEventListener('error', e=>{ uiError('Fehler in der Oberfläche', e.error || new Error(e.message)); });
window.addEventListener('unhandledrejection', e=>{ e.preventDefault(); uiError('Fehler in der Oberfläche', e.reason); });

window.addEventListener('focus', refocusInput);

const MIN_W = 320, MIN_H = 200;

function deskBox(){ return document.getElementById('desktop').getBoundingClientRect(); }

// leave the maximized state and put the window under the pointer (like a desktop OS does when a maximized window is dragged by its title)
function restoreForDrag(w, e){
  const before = w.getBoundingClientRect();
  const ratio = (e.clientX - before.left) / Math.max(1, before.width);
  w.classList.remove('maximized'); setMaxIcon(w);
  const r = w.getBoundingClientRect(), desk = deskBox();
  w.style.right = 'auto';
  w.style.left = Math.max(0, e.clientX - desk.left - r.width * ratio)+'px';
  w.style.top = Math.max(0, e.clientY - desk.top - 14)+'px';
}

function startMove(w, e){
  if(e.button!==0 || e.target.closest('.controls')) return;
  const startX = e.clientX, startY = e.clientY, wasMax = w.classList.contains('maximized');
  let dx = 0, dy = 0, started = !wasMax;
  const begin = ev=>{
    if(wasMax) restoreForDrag(w, ev);
    const desk = deskBox(), r = w.getBoundingClientRect();
    dx = ev.clientX - r.left; dy = ev.clientY - r.top;
    w.style.left = (r.left - desk.left)+'px'; w.style.top = (r.top - desk.top)+'px'; w.style.right = 'auto';
    started = true;
  };
  if(!wasMax) begin(e);
  const move = ev=>{
    if(!started){ if(Math.abs(ev.clientX-startX) + Math.abs(ev.clientY-startY) < 5) return; begin(ev); }
    const desk = deskBox();
    w.style.left = Math.max(0, Math.min(ev.clientX - dx - desk.left, desk.width - 80))+'px';
    w.style.top = Math.max(0, Math.min(ev.clientY - dy - desk.top, desk.height - 70))+'px';
  };
  const up = ()=>{ document.removeEventListener('mousemove',move); document.removeEventListener('mouseup',up); };
  document.addEventListener('mousemove',move); document.addEventListener('mouseup',up);
  e.preventDefault();
}

// eight edge/corner handles; the window grows or shrinks with the pointer (never below MIN_W x MIN_H, never out of the desktop)
function startResize(w, edge, e){
  if(e.button!==0 || w.classList.contains('maximized')) return;
  const desk = deskBox(), r = w.getBoundingClientRect();
  const box = {l: r.left - desk.left, t: r.top - desk.top, w: r.width, h: r.height};
  w.style.left = box.l+'px'; w.style.top = box.t+'px'; w.style.right = 'auto';
  w.style.width = box.w+'px'; w.style.height = box.h+'px';
  const sx = e.clientX, sy = e.clientY;
  const move = ev=>{
    let l = box.l, t = box.t, ww = box.w, hh = box.h; const mx = ev.clientX - sx, my = ev.clientY - sy;
    if(edge.includes('e')) ww = Math.min(Math.max(MIN_W, box.w + mx), desk.width - l);
    if(edge.includes('s')) hh = Math.min(Math.max(MIN_H, box.h + my), desk.height - t);
    if(edge.includes('w')){ const nl = Math.min(Math.max(0, box.l + mx), box.l + box.w - MIN_W); ww = box.w + (box.l - nl); l = nl; }
    if(edge.includes('n')){ const nt = Math.min(Math.max(0, box.t + my), box.t + box.h - MIN_H); hh = box.h + (box.t - nt); t = nt; }
    w.style.left = l+'px'; w.style.top = t+'px'; w.style.width = ww+'px'; w.style.height = hh+'px';
  };
  const up = ()=>{ document.removeEventListener('mousemove',move); document.removeEventListener('mouseup',up); };
  document.addEventListener('mousemove',move); document.addEventListener('mouseup',up);
  e.preventDefault(); e.stopPropagation();
}

document.querySelectorAll('.window').forEach(w=>{
  w.addEventListener('mousedown',()=>{ if(!w.classList.contains('focused')) bringToFront(w); });
  const bar = w.querySelector('.titlebar');
  bar.addEventListener('mousedown',e=>startMove(w,e));
  bar.addEventListener('dblclick',e=>{ if(!e.target.closest('.controls')) toggleMaximize(w.id); });
  ['n','s','e','w','ne','nw','se','sw'].forEach(edge=>{
    const h = document.createElement('div'); h.className = 'rz rz-'+edge;
    h.addEventListener('mousedown',e=>startResize(w,edge,e)); w.appendChild(h);
  });
  setMaxIcon(w);
});

// a window must stay reachable when the browser window gets smaller
window.addEventListener('resize',()=>{
  const desk = deskBox();
  document.querySelectorAll('.window:not(.maximized)').forEach(w=>{
    if(!w.style.left) return;
    const r = w.getBoundingClientRect();
    w.style.left = Math.max(0, Math.min(r.left - desk.left, desk.width - 80))+'px';
    w.style.top = Math.max(0, Math.min(r.top - desk.top, desk.height - 70))+'px';
  });
});

document.getElementById('desktop').addEventListener('contextmenu', function(e){
  if(e.target.closest('.window') || e.target.closest('.taskbar') || e.target.closest('.startmenu')) return;
  e.preventDefault();
  const menu=document.getElementById('desktopContext');
  const maxX=window.innerWidth-menu.offsetWidth-8;
  const maxY=window.innerHeight-menu.offsetHeight-46;
  menu.style.left=Math.max(4,Math.min(e.clientX,maxX))+'px';
  menu.style.top=Math.max(4,Math.min(e.clientY,maxY))+'px';
  menu.classList.add('active');
});

// a click outside closes the context menu and the start menu (the start button itself toggles it)
document.addEventListener('click', function(e){
  if(!e.target.closest('#desktopContext')) hideContext();
  if(!e.target.closest('#startMenu') && !e.target.closest('.start')) document.getElementById('startMenu').classList.remove('active');
});

// Escape closes menus and the Kommando; a window stays open (closing is a deliberate click). Strg+K opens the Kommando from everywhere.
document.addEventListener('keydown', function(e){
  if((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K')){ e.preventDefault(); togglePalette(); return; }
  if(e.key !== 'Escape') return;
  hideContext(); closePalette();
  document.getElementById('startMenu').classList.remove('active');
});

updateClock();

setInterval(updateClock,1000);

refreshRuntimeStatus();

refreshMissions();

setInterval(refreshRuntimeStatus,15000);

initChat();

openDeck();                                           // the start window: state, Kommando, what waits and what runs

document.getElementById('chatModel').addEventListener('change', chooseChatModel);

document.getElementById('chatModel').addEventListener('change', updateChatModelHint);

document.getElementById('msgInput').addEventListener('keydown',e=>{if(e.key==='Enter')sendMessage()});

document.querySelectorAll('button.action:not([onclick]),button.tool:not([onclick]),.menuitem:not([onclick]),.ctx-item:not([onclick])').forEach(b=>{b.hidden=true;});

// the div-buttons of the shell (window controls, start menu, context menu, taskbar) work with the keyboard: Tab, Enter, Space
document.querySelectorAll('.ctrl,.menuitem,.ctx-item,.taskbtn,.start').forEach(makeKeyboardButton);

ccInit();

attachIconDrag(document.getElementById('agentsIcon'),'agents');

attachIconDrag(document.getElementById('cardsIcon'),'cards');

document.querySelector('#projectWindow .project-main').appendChild(actionButton('Codekandidat mit lokalem Modell entwerfen',requestCodeCandidate));

refreshProjects().catch(e=>console.warn(e.message));
