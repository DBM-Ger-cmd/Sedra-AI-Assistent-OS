// Desktop icons can be dragged to another place (Captain 2026-10-14). The position is a transform offset per icon, so the grid of the
// project folders does not change. Positions are kept in this browser only (localStorage, a convenience; nothing is sent to the PC).
// Classic script: shares the page's global scope; load order is set in retro_desktop.html.

const DESK_ICON_POS_KEY = 'guppi.desktopIconPos';

function loadIconPositions(){
  try{ return JSON.parse(localStorage.getItem(DESK_ICON_POS_KEY) || '{}') || {}; }
  catch(err){ return {}; }
}

function saveIconPosition(key, x, y){
  try{
    const all = loadIconPositions();
    all[key] = {x: Math.round(x), y: Math.round(y)};
    localStorage.setItem(DESK_ICON_POS_KEY, JSON.stringify(all));
  }catch(err){ /* private window or blocked storage: the icon still moves, it just is not remembered */ }
}

// Makes one desktop icon draggable. `key` names it for the saved position (e.g. 'project:<id>' or 'agents').
function attachIconDrag(icon, key){
  const saved = loadIconPositions()[key] || {x: 0, y: 0};
  icon._off = {x: saved.x, y: saved.y};
  icon.style.transform = 'translate(' + icon._off.x + 'px,' + icon._off.y + 'px)';
  let start = null, moved = false;

  icon.addEventListener('pointerdown', e => {
    if(e.button !== 0) return;
    start = {x: e.clientX, y: e.clientY, ox: icon._off.x, oy: icon._off.y};
    moved = false;
    icon.setPointerCapture(e.pointerId);
  });
  icon.addEventListener('pointermove', e => {
    if(!start) return;
    const dx = e.clientX - start.x, dy = e.clientY - start.y;
    if(!moved && Math.hypot(dx, dy) < 5) return;        // a small wiggle is still a click
    moved = true;
    icon.classList.add('dragging');
    icon._off = {x: start.ox + dx, y: start.oy + dy};
    icon.style.transform = 'translate(' + icon._off.x + 'px,' + icon._off.y + 'px)';
  });
  const end = () => {
    if(!start) return;
    if(moved){
      saveIconPosition(key, icon._off.x, icon._off.y);
      icon.dataset.justDragged = '1';
      setTimeout(() => delete icon.dataset.justDragged, 0);
    }
    start = null;
    icon.classList.remove('dragging');
  };
  icon.addEventListener('pointerup', end);
  icon.addEventListener('pointercancel', end);
  // after a drag the click that follows the release must not open the folder
  icon.addEventListener('click', e => {
    if(icon.dataset.justDragged){ e.stopImmediatePropagation(); e.preventDefault(); }
  }, true);
}
