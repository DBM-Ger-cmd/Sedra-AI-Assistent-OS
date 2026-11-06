// Verankerter Dialog für Knoten-/Modulkonfiguration. Liegt innerhalb der Zeichenfläche, schließt mit Escape,
// gibt den Fokus an den Auslöser zurück. Besitzt keinen Zustand außerhalb seines Containers.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  // Berechnet die Lage eines Dialogs so, dass er vollständig im Host bleibt (reine Funktion, testbar).
  function place(host, size, anchor){
    const gap = 12, x = anchor ? anchor.x + anchor.w + gap : (host.w - size.w) / 2, y = anchor ? anchor.y - 20 : (host.h - size.h) / 2;
    const left = Math.max(gap, Math.min(x, host.w - size.w - gap));
    const flipped = anchor && x + size.w > host.w - gap ? Math.max(gap, anchor.x - size.w - gap) : left;
    return {left: Math.round(flipped), top: Math.round(Math.max(gap, Math.min(y, host.h - size.h - gap)))};
  }
  function open(options){
    const host = options.host, opener = document.activeElement;
    const dlg = document.createElement('section');
    dlg.className = 't-wf-dialog'; dlg.setAttribute('role', 'dialog'); dlg.setAttribute('aria-modal', 'false');
    const title = document.createElement('h3'); title.id = 'wf-dlg-' + Math.random().toString(16).slice(2); title.textContent = options.title;
    dlg.setAttribute('aria-labelledby', title.id);
    const close = document.createElement('button'); close.type = 'button'; close.textContent = '✕'; close.setAttribute('aria-label', 'Schließen');
    const head = document.createElement('div'); head.className = 't-wf-dialog-head'; head.append(title, close);
    const body = document.createElement('div'); body.className = 't-wf-dialog-body';
    if(options.body) body.append(options.body);
    dlg.append(head, body); host.append(dlg);
    const hostBox = {w: host.clientWidth || 800, h: host.clientHeight || 500};
    const at = place(hostBox, {w: dlg.offsetWidth || 320, h: dlg.offsetHeight || 260}, options.anchor);
    dlg.style.left = at.left + 'px'; dlg.style.top = at.top + 'px';
    let closed = false;
    function shut(){
      if(closed) return; closed = true; dlg.remove();
      if(opener && opener.isConnected && opener.focus) opener.focus();
      if(options.onClose) options.onClose();
    }
    close.onclick = shut;
    dlg.addEventListener('keydown', event=>{if(event.key === 'Escape'){event.stopPropagation();shut();}});
    const first = dlg.querySelector('input,select,textarea,button:not([aria-label="Schließen"])') || close; first.focus();
    return {el: dlg, body, close: shut};
  }
  root.sedraWorkflowDialog = {open, place};
})();
