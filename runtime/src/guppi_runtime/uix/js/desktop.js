// Desktop shell: windows (show, close, minimize, maximize, taskbar), start menu, processing window, clipboard and file picking, clock.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

let zTop = 20;

function windowTitle(el){ const s = el.querySelector('.titlebar span'); return s ? s.textContent : el.id; }

// a div that acts as a button gets a tab stop, a role and Enter/Space as click
function makeKeyboardButton(b){
  if(!b.hasAttribute('tabindex')) b.tabIndex = 0;
  if(!b.getAttribute('role')) b.setAttribute('role','button');
  b.addEventListener('keydown', e=>{ if(e.key==='Enter' || e.key===' '){ e.preventDefault(); b.click(); } });
}

function showWindow(id){
  const el = document.getElementById(id);
  el.classList.remove('minimized');
  el.classList.add('active');
  bringToFront(el);
}

function closeWindow(id){
  const el = document.getElementById(id);
  el.classList.remove('active','minimized','maximized','focused');
  setMaxIcon(el);
  focusTopWindow();
  syncTaskbar();
}

const REDUCED_MOTION = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function minimizeWindow(id){
  const el = document.getElementById(id);
  const finish = ()=>{
    el.classList.remove('active','focused','minimizing');
    el.classList.add('minimized');
    focusTopWindow();
    syncTaskbar();
  };
  if(REDUCED_MOTION || el.classList.contains('minimizing')){ finish(); return; }
  el.classList.add('minimizing');                       // shrink towards the taskbar, then hide (160 ms, see desktop.css)
  let done = false;
  const once = ()=>{ if(done) return; done = true; el.removeEventListener('animationend', once); finish(); };
  el.addEventListener('animationend', once);
  setTimeout(once, 260);
}

function setMaxIcon(el){
  const b = el.querySelector('.ctrl[title="Maximieren"], .ctrl[title="Wiederherstellen"]');
  if(!b) return;
  const on = el.classList.contains('maximized');
  b.textContent = on ? '\u2750' : '\u25a1'; b.title = on ? 'Wiederherstellen' : 'Maximieren';
}

function toggleMaximize(id){
  const el = document.getElementById(id);
  el.classList.toggle('maximized');
  setMaxIcon(el);
  bringToFront(el);
}

// the visible window with the highest stacking order gets the focus (after a close or minimize)
function focusTopWindow(){
  const open = [...document.querySelectorAll('.window.active')].sort((a,b)=>(+a.style.zIndex||0)-(+b.style.zIndex||0));
  if(open.length) bringToFront(open[open.length-1]); else syncTaskbar();
}

// One button per open or minimized window. A launcher (the fixed buttons on the left) hides while its window is open,
// so a window never has two buttons and the tray with state and clock stays on screen.
function syncTaskbar(){
  const box = document.getElementById('taskWindows');
  if(!box) return;
  box.replaceChildren();
  document.querySelectorAll('.window').forEach(el=>{
    const open = el.classList.contains('active') || el.classList.contains('minimized');
    document.querySelectorAll('.taskbtn.launcher[data-window="'+el.id+'"]').forEach(l=>l.classList.toggle('open', open));
    if(!open) return;
    const b = document.createElement('div');
    b.className = 'taskbtn' + (el.classList.contains('focused') ? ' on' : '');
    b.textContent = windowTitle(el).replace(/^SEDRA /,'');
    b.title = windowTitle(el) + (el.classList.contains('minimized') ? ' – wiederherstellen' : el.classList.contains('focused') ? ' – minimieren' : ' – in den Vordergrund');
    b.onclick = ()=>{
      if(el.classList.contains('minimized')) showWindow(el.id);
      else if(el.classList.contains('focused')) minimizeWindow(el.id);
      else bringToFront(el);
    };
    makeKeyboardButton(b);
    box.appendChild(b);
  });
}

function bringToFront(el){
  document.querySelectorAll('.window').forEach(w=>w.classList.remove('focused'));
  el.style.zIndex = ++zTop;
  el.classList.add('focused');
  syncTaskbar();
}

function toggleStart(){
  document.getElementById('startMenu').classList.toggle('active');
}

function showProcessor(title, meta, renderer){
  document.getElementById('processorTitle').textContent = title;
  document.getElementById('processorMeta').innerHTML = meta;
  const preview = document.getElementById('processorPreview');
  preview.innerHTML = '';
  preview.style.display = '';
  renderer(preview);
  showWindow('processorWindow');
  hideContext();
}

async function pasteFromClipboard(){
  hideContext();

  if(!navigator.clipboard){
    pickFile();
    return;
  }

  try{
    if(navigator.clipboard.read){
      const items = await navigator.clipboard.read();
      if(!items.length){
        alert('Die Zwischenablage ist leer.');
        return;
      }

      for(const item of items){
        const imageType = item.types.find(t => t.startsWith('image/'));
        if(imageType){
          const blob = await item.getType(imageType);
          const url = URL.createObjectURL(blob);
          showProcessor(
            'Verarbeitung – Bild aus Zwischenablage',
            '<b>Quelle:</b> Zwischenablage<br><b>Typ:</b> '+imageType+'<br><b>Aktion:</b> Bild zur Verarbeitung bereit',
            preview=>{
              const img=document.createElement('img');
              img.src=url;
              img.alt='Bild aus Zwischenablage';
              preview.appendChild(img);
            }
          );
          return;
        }

        if(item.types.includes('text/plain')){
          const blob = await item.getType('text/plain');
          const text = await blob.text();
          showTextProcessor(text, 'Text aus Zwischenablage');
          return;
        }
      }
    }

    if(navigator.clipboard.readText){
      const text = await navigator.clipboard.readText();
      if(text){
        showTextProcessor(text, 'Text aus Zwischenablage');
        return;
      }
    }

    alert('Dieser Inhalt der Zwischenablage wird vom Browser nicht direkt bereitgestellt. Nutze "Dokument / Bild öffnen..." als Fallback.');
  }catch(err){
    alert('Der Browser hat den direkten Zugriff auf die Zwischenablage blockiert. Nutze "Dokument / Bild öffnen..." oder erlaube den Zwischenablagezugriff.');
  }
}

function showTextProcessor(text, label){
  showProcessor(
    'Verarbeitung – '+label,
    '<b>Quelle:</b> Zwischenablage<br><b>Typ:</b> Text<br><b>Zeichen:</b> '+text.length,
    preview=>{
      const pre=document.createElement('pre');
      pre.textContent=text;
      preview.appendChild(pre);
    }
  );
}

function pickFile(){
  hideContext();
  document.getElementById('fallbackFile').click();
}

function handlePickedFile(event){
  const file = event.target.files && event.target.files[0];
  if(!file) return;
  const type = file.type || 'unbekannt';

  if(type.startsWith('image/')){
    const url = URL.createObjectURL(file);
    showProcessor(
      'Verarbeitung – '+file.name,
      '<b>Datei:</b> '+escapeHtml(file.name)+'<br><b>Typ:</b> '+escapeHtml(type)+'<br><b>Größe:</b> '+formatBytes(file.size),
      preview=>{
        const img=document.createElement('img');
        img.src=url;
        img.alt=file.name;
        preview.appendChild(img);
      }
    );
  }else if(type.startsWith('text/') || /\.(txt|md|json|csv|html|js|css|py)$/i.test(file.name)){
    const reader = new FileReader();
    reader.onload = () => {
      showProcessor(
        'Verarbeitung – '+file.name,
        '<b>Datei:</b> '+escapeHtml(file.name)+'<br><b>Typ:</b> '+escapeHtml(type)+'<br><b>Größe:</b> '+formatBytes(file.size),
        preview=>{
          const pre=document.createElement('pre');
          pre.textContent=reader.result;
          preview.appendChild(pre);
        }
      );
    };
    reader.readAsText(file);
  }else{
    showProcessor(
      'Verarbeitung – '+file.name,
      '<b>Datei:</b> '+escapeHtml(file.name)+'<br><b>Typ:</b> '+escapeHtml(type)+'<br><b>Größe:</b> '+formatBytes(file.size)+'<br><br>Das Dokument wurde als Verarbeitungsobjekt geöffnet.',
      preview=>{
        preview.innerHTML='<div class="file-placeholder"><div class="big">📄</div><b>'+escapeHtml(file.name)+'</b><div style="margin-top:8px;color:#68798b;font-size:12px">'+escapeHtml(type)+'</div></div>';
      }
    );
  }
  event.target.value='';
}

function hideContext(){
  document.getElementById('desktopContext').classList.remove('active');
}

function updateClock(){
  const n=new Date();
  document.getElementById('clock').textContent=String(n.getHours()).padStart(2,'0')+':'+String(n.getMinutes()).padStart(2,'0');
}
