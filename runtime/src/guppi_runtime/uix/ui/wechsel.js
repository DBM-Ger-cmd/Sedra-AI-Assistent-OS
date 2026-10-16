// UI contract 1.0 – der Umschalter (Ticket B6-G-04, Klaus 15.10.2026): in **jeder** Shell derselbe kleine Knopf unten rechts.
// Er öffnet ein Menü mit der Übersicht der Oberflächen, dem Wechsel in eine andere, der Darstellung (Klar/Nacht) und der
// Schriftgröße (Normal/Groß). Er gehört zur Seite, nicht zur Shell: der Loader hängt ihn nach dem Start der Shell an, eine Shell
// kann ihn nicht abschalten, und er spricht über sedraApi.api (die Seite selbst, Token-geprüft) – nur zwei Routen:
// GET /api/uix/modules und POST /api/uix/shell. Nichts läuft ohne Klick; der Wechsel lädt die Seite neu, wie im Werkzeug Module.
// Tastatur: Alt+S öffnet und schließt das Menü, Esc schließt. Die Wahl von Darstellung und Schrift bleibt im Browser (Anzeige-Komfort).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const SCALES = ['normal', 'gross'];
  const SCALE_KEY = 'sedra.scale';

  // rein: die Einträge des Menüs aus der Modulliste (node prüft das ohne Browser)
  function entries(shells, current){
    const out = [{kind: 'overview', label: 'Übersicht der Oberflächen', hint: 'alle Oberflächen; die gewählte bleibt eingetragen'}];
    (shells || []).filter(s=>s.id !== 'start' && s.id !== current).forEach(s=>out.push({kind: 'shell', id: s.id, label: 'Wechseln zu ' + s.name, hint: s.description || ''}));
    return out;
  }

  function setScale(name){
    const scale = SCALES.indexOf(name) >= 0 ? name : 'normal';
    document.documentElement.dataset.scale = scale;
    try{ localStorage.setItem(SCALE_KEY, scale); }catch(_e){}
    return scale;
  }

  function restoreScale(){
    let stored = null;
    try{ stored = localStorage.getItem(SCALE_KEY); }catch(_e){}
    document.documentElement.dataset.scale = SCALES.indexOf(stored) >= 0 ? stored : 'normal';
  }

  function mount(manifest){
    if(typeof document === 'undefined' || !manifest || !manifest.shell || manifest.shell.id === 'start') return null;
    if(document.querySelector('.sx-chip')) return null;
    const api = root.sedraApi.api;
    const el = (tag, cls, text)=>{ const n = document.createElement(tag); if(cls) n.className = cls; if(text != null) n.textContent = text; return n; };

    const chip = el('button', 'sx-chip'); chip.type = 'button'; chip.title = 'Oberfläche wechseln (Alt+S)';
    chip.setAttribute('aria-label', 'SEDRA – Oberfläche wechseln, Darstellung, Schrift'); chip.setAttribute('aria-haspopup', 'menu'); chip.setAttribute('aria-expanded', 'false');
    chip.append(el('span', 'sx-chip-mark', 'S'), el('span', 'sx-chip-text', manifest.shell.name || manifest.shell.id));

    const panel = el('div', 'sx-panel'); panel.setAttribute('role', 'menu'); panel.hidden = true;
    const head = el('div', 'sx-head'); head.append(el('b', null, 'SEDRA'), el('small', null, 'Oberfläche: ' + (manifest.shell.name || manifest.shell.id)));
    const list = el('div', 'sx-list');
    const look = el('div', 'sx-look');
    const foot = el('small', 'sx-foot', 'Alt+S öffnet dieses Menü · Esc schließt · Strg+K sucht einen Ort');
    panel.append(head, list, look, foot);

    function row(label, hint, fn){
      const r = el('button', 'sx-item'); r.type = 'button'; r.setAttribute('role', 'menuitem');
      r.append(el('b', null, label)); if(hint) r.append(el('small', null, hint));
      r.addEventListener('click', ()=>{ close(); Promise.resolve(fn()).catch(err=>{ if(root.sedraBoot && root.sedraBoot.note) root.sedraBoot.note('Umschalter', err); }); });
      return r;
    }
    function segment(title, options, current, onPick){
      const box = el('div', 'sx-seg'); box.append(el('small', null, title));
      const group = el('div', 'sx-seg-group'); group.setAttribute('role', 'group'); group.setAttribute('aria-label', title);
      options.forEach(([id, label])=>{
        const b = el('button', 'sx-seg-btn' + (id === current ? ' on' : ''), label); b.type = 'button'; b.dataset.value = id; b.setAttribute('aria-pressed', id === current ? 'true' : 'false');
        b.addEventListener('click', ()=>{ onPick(id); group.querySelectorAll('.sx-seg-btn').forEach(x=>{ x.classList.toggle('on', x.dataset.value === id); x.setAttribute('aria-pressed', x.dataset.value === id ? 'true' : 'false'); }); });
        group.append(b);
      });
      box.append(group); return box;
    }

    async function fill(){
      list.replaceChildren();
      let shells = [];
      try{ shells = (await api('/api/uix/modules')).shells || []; }
      catch(err){ list.append(el('div', 'sx-note', 'Oberflächen nicht lesbar: ' + err.message)); }
      entries(shells, manifest.shell.id).forEach(e=>{
        if(e.kind === 'overview') list.append(row(e.label, e.hint, async()=>{ await api('/api/uix/shell', {method: 'POST', body: {shell: 'start', nur_jetzt: true}}); location.reload(); }));
        else list.append(row(e.label, e.hint, async()=>{ await api('/api/uix/shell', {method: 'POST', body: {shell: e.id}}); location.reload(); }));
      });
      look.replaceChildren(
        segment('Darstellung', [['klar', 'Klar'], ['nacht', 'Nacht']], document.documentElement.dataset.theme || 'klar', v=>root.sedraBoot.setTheme(v)),
        segment('Schrift', [['normal', 'Normal'], ['gross', 'Groß']], document.documentElement.dataset.scale || 'normal', v=>setScale(v)));
    }
    function open(){ panel.hidden = false; chip.setAttribute('aria-expanded', 'true'); fill().then(()=>{ const first = panel.querySelector('.sx-item'); if(first) first.focus(); }); }
    function close(){ panel.hidden = true; chip.setAttribute('aria-expanded', 'false'); }
    function toggle(){ panel.hidden ? open() : close(); }

    chip.addEventListener('click', toggle);
    document.addEventListener('keydown', e=>{
      if(e.altKey && !e.ctrlKey && !e.metaKey && (e.key === 's' || e.key === 'S')){ e.preventDefault(); toggle(); }
      else if(e.key === 'Escape' && !panel.hidden){ close(); chip.focus(); }
    });
    document.addEventListener('click', e=>{ if(!panel.hidden && !panel.contains(e.target) && e.target !== chip && !chip.contains(e.target)) close(); });

    const host = el('div', 'sx-host'); host.append(panel, chip);
    document.body.append(host);
    return {chip, panel, open, close, fill};
  }

  root.sedraWechsel = {mount, entries, setScale, restoreScale, scales: SCALES};
  if(typeof module !== 'undefined' && module.exports) module.exports = {entries, scales: SCALES};
})();
