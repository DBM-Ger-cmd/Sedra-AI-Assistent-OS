// UI contract 1.0 – the few helpers every module may use (and none that reach outside a container).
// Runtime data never becomes HTML here: el() and text() set textContent, so a file name with '<' in it stays a file name.
// Classic script: defines window.sedraDom; the pure parts (fmt*) are tested with node.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const hasDoc = typeof document !== 'undefined';

  function el(tag, cls, text){
    const e = document.createElement(tag);
    if(cls) e.className = cls;
    if(text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }

  // a row that behaves like a button for mouse and keyboard (the tree, the decision list, every clickable line)
  function clickable(node, fn){
    node.setAttribute('role', 'button');
    node.tabIndex = 0;
    node.onclick = fn;
    node.onkeydown = e=>{ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); fn(e); } };
    return node;
  }

  // Vertrag 1.1 (SPEC_WERKZEUG_WISSEN_v2 §3.9): ein Knopf sendet kein Formular ab, außer er sagt es ({absenden: true}).
  // Vorher war jeder Knopf in einem <form> ein Absende-Knopf: Enter löste den ersten aus – im Stufen-Formular „Abbrechen“ und danach
  // trotzdem das Absenden (im Browser nachgestellt 26.10.2026).
  function button(label, fn, cls, opts){
    const b = el('button', 's-btn' + (cls ? ' ' + cls : ''), label);
    b.type = opts && opts.absenden ? 'submit' : 'button';
    b.onclick = async e=>{
      e.stopPropagation(); b.disabled = true;
      try{ await fn(e); }
      catch(err){
        const note = el('small', 's-note bad', 'Fehlgeschlagen: ' + (err && err.message ? err.message : err));
        b.after(note); setTimeout(()=>note.remove(), 8000);
      }
      finally{ b.disabled = false; }
    };
    return b;
  }

  function fmtNumber(n){
    if(n === null || n === undefined || n === '') return '–';
    const v = Number(n);
    return isNaN(v) ? String(n) : v.toLocaleString('de-DE');
  }

  function fmtBytes(bytes){
    if(!bytes && bytes !== 0) return '–';
    if(bytes < 1024) return bytes + ' B';
    if(bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function fmtTime(iso){
    if(!iso) return '';
    const d = new Date(iso);
    return isNaN(d.getTime()) ? String(iso).slice(0, 16).replace('T', ' ') : d.toLocaleString('de-DE', {dateStyle: 'short', timeStyle: 'short'});
  }

  // "vor 3 Minuten" for a log line; seconds are noise, days are enough
  function fmtAgo(iso, now){
    if(!iso) return '';
    const t = new Date(iso).getTime();
    if(isNaN(t)) return '';
    const s = Math.max(0, Math.round(((now || Date.now()) - t) / 1000));
    if(s < 60) return 'gerade eben';
    if(s < 3600) return 'vor ' + Math.round(s / 60) + ' Min';
    if(s < 86400) return 'vor ' + Math.round(s / 3600) + ' Std';
    return 'vor ' + Math.round(s / 86400) + ' Tagen';
  }

  function fmtDuration(seconds){
    if(seconds === null || seconds === undefined) return '–';
    const s = Math.round(Number(seconds) || 0);
    if(s < 60) return s + ' s';
    const m = Math.floor(s / 60);
    return m < 60 ? m + ' Min ' + (s % 60) + ' s' : Math.floor(m / 60) + ' Std ' + (m % 60) + ' Min';
  }

  // one short sentence for an empty container – a tool says what would be here, never nothing
  function empty(text){ return el('div', 's-empty', text); }

  const dom = {el, clickable, button, empty, fmtNumber, fmtBytes, fmtTime, fmtAgo, fmtDuration};
  root.sedraDom = hasDoc ? dom : {fmtNumber, fmtBytes, fmtTime, fmtAgo, fmtDuration};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraDom;
})();
