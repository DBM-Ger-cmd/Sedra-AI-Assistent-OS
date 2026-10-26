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

  // Der Kern-Zugang wird beim Laden gemerkt; der Loader entfernt die globale Kopie danach (Stufe A)
  const CORE_API = root.sedraApi ? root.sedraApi.api : null;

  // Vertrag 1.1 (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §10.4): vor dem Neuladen meldet die Shell ihren Arbeitsstand ein letztes Mal und die
  // Werkzeuge schreiben ihre Ablage. Eine Shell hängt sich mit `sedraWechsel.beimWechsel(fn)` ein; fn darf ein Promise geben.
  // Höchstens 1,5 s warten: ein hängender Server darf den Wechsel nicht aufhalten.
  const VOR_DEM_WECHSEL = [];
  function beimWechsel(fn){ if(typeof fn === 'function') VOR_DEM_WECHSEL.push(fn); }
  function vorDemWechsel(){
    const alle = VOR_DEM_WECHSEL.concat([()=>root.sedraLifecycle && root.sedraLifecycle.ablagenSchreiben && root.sedraLifecycle.ablagenSchreiben()]).map(fn=>{ try{ return Promise.resolve(fn()).catch(()=>{}); }catch(_e){ return Promise.resolve(); } });
    return Promise.race([Promise.all(alle), new Promise(ok=>setTimeout(ok, 1500))]);
  }
  // für shellApi.reload der Shells (nach einem Wechsel im Werkzeug Module): erst melden und schreiben, dann neu laden
  function neuLaden(){ return vorDemWechsel().then(()=>location.reload()); }
  async function wechseln(body){
    await CORE_API('/api/uix/shell', {method: 'POST', body});
    await vorDemWechsel();
    location.reload();
  }

  function mount(manifest){
    if(typeof document === 'undefined' || !manifest || !manifest.shell || manifest.shell.id === 'start') return null;
    if(document.querySelector('.sx-chip')) return null;
    const api = CORE_API;
    const el = (tag, cls, text)=>{ const n = document.createElement(tag); if(cls) n.className = cls; if(text != null) n.textContent = text; return n; };

    const chip = el('button', 'sx-chip sx-umschalter'); chip.type = 'button'; chip.title = 'Oberfläche wechseln (Alt+S)';
    chip.setAttribute('aria-label', 'SEDRA – Oberfläche wechseln, Darstellung, Schrift'); chip.setAttribute('aria-haspopup', 'menu'); chip.setAttribute('aria-expanded', 'false');
    chip.append(el('span', 'sx-chip-mark', 'S'), el('span', 'sx-chip-text', manifest.shell.name || manifest.shell.id));

    const panel = el('div', 'sx-panel sx-umschalter-panel'); panel.setAttribute('role', 'menu'); panel.hidden = true;
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
        if(e.kind === 'overview') list.append(row(e.label, e.hint, ()=>wechseln({shell: 'start', nur_jetzt: true})));
        else list.append(row(e.label, e.hint, ()=>wechseln({shell: e.id})));
      });
      list.append(leerenKnopf());
      look.replaceChildren(
        segment('Darstellung', [['klar', 'Klar'], ['nacht', 'Nacht']], document.documentElement.dataset.theme || 'nacht', v=>root.sedraBoot.setTheme(v)),
        segment('Schrift', [['normal', 'Normal'], ['gross', 'Groß']], document.documentElement.dataset.scale || 'normal', v=>setScale(v)),
        segment('Menü', [['links', 'Links'], ['rechts', 'Rechts']], menuSeite(), v=>setMenuSeite(v)));
    }
    // „Gedächtnis leeren“ (§10.5): offene Objekte, Ablage der Werkzeuge, Gesprächsverlauf, Sitzung im Browser. Erst der zweite Klick
    // leert – kein confirm(), keine Seite dazwischen. Danach eine Zeile im Umschalter; das Audit bekommt nur Zahlen.
    function leerenKnopf(){
      const b = el('button', 'sx-item sx-leeren'); b.type = 'button'; b.setAttribute('role', 'menuitem');
      const titel = el('b', null, 'Gedächtnis leeren'), hint = el('small', null, 'offene Objekte, Ablage der Werkzeuge, Gesprächsverlauf');
      b.append(titel, hint);
      let scharf = null;
      b.addEventListener('click', async e=>{
        e.stopPropagation();
        if(!scharf){
          titel.textContent = 'Wirklich leeren? Noch einmal klicken';
          scharf = setTimeout(()=>{ scharf = null; titel.textContent = 'Gedächtnis leeren'; }, 5000);
          return;
        }
        clearTimeout(scharf); scharf = null;
        try{
          await api('/api/arbeitsstand/leeren', {method: 'POST', body: {}});
          if(root.sedraLifecycle && root.sedraLifecycle.gedaechtnisLeeren) root.sedraLifecycle.gedaechtnisLeeren();
          titel.textContent = 'Gedächtnis geleert'; hint.textContent = 'beim nächsten Wechsel beginnt die Oberfläche leer';
        }catch(err){ titel.textContent = 'Nicht geleert'; hint.textContent = err.message; }
      });
      return b;
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

    const rek = mountRekorder();
    const host = el('div', 'sx-host'); host.append(rek.panel, rek.chip, panel, chip);
    document.body.append(host);
    return {chip, panel, open, close, fill};
  }

  // Die Seite des Menüs: links (Standard) oder rechts. Die Wahl steht am Baum und im Umschalter; sie gilt pro Browser
  // (localStorage, nur eine Bequemlichkeit – ein Fehler dort ändert nichts am Ablauf).
  const MENU_SEITEN = ['links', 'rechts'];
  function menuSeite(){
    try{ const v = localStorage.getItem('sedra.menuSeite'); return MENU_SEITEN.indexOf(v) >= 0 ? v : 'links'; }
    catch(_err){ return 'links'; }
  }
  function setMenuSeite(v){
    if(MENU_SEITEN.indexOf(v) < 0 || typeof document === 'undefined') return;
    document.documentElement.dataset.menu = v;
    try{ localStorage.setItem('sedra.menuSeite', v); }catch(_err){}
  }
  // Auswahl „Links | Rechts“ – an beiden Stellen derselbe Baustein
  function menuWahl(){
    const box = document.createElement('div'); box.className = 'tr-menuwahl';
    const titel = document.createElement('small'); titel.textContent = 'Menü auf der Seite';
    const group = document.createElement('div'); group.className = 'sx-seg-group'; group.setAttribute('role', 'group'); group.setAttribute('aria-label', 'Menü auf der Seite');
    const aktuell = menuSeite();
    MENU_SEITEN.forEach(v=>{
      const b = document.createElement('button'); b.type = 'button'; b.dataset.value = v;
      b.className = 'sx-seg-btn' + (v === aktuell ? ' on' : ''); b.textContent = v === 'links' ? 'Links' : 'Rechts';
      b.setAttribute('aria-pressed', v === aktuell ? 'true' : 'false');
      b.addEventListener('click', ()=>{
        setMenuSeite(v);
        group.querySelectorAll('.sx-seg-btn').forEach(x=>{ const on = x.dataset.value === v; x.classList.toggle('on', on); x.setAttribute('aria-pressed', on ? 'true' : 'false'); });
      });
      group.append(b);
    });
    box.append(titel, group);
    return box;
  }
  if(typeof document !== 'undefined') setMenuSeite(menuSeite());          // beim Laden die gespeicherte Seite setzen


  // Die Rekorder-Leiste: in jeder Shell gleich. Die Aufnahme läuft im Kern; die Leiste steuert und zeigt sie. Das Pult im Translator-Modus „Aufnahme“ ist ein eigenes Werkzeug.
  // Start ist der Aufnahme-Modus der Fisch-Shell (Captain-Wunsch 20.10.2026); von dort oder aus jeder Shell über diese Leiste.
  function mountRekorder(){
    const mk = (tag, cls, text)=>{ const n = document.createElement(tag); if(cls) n.className = cls; if(text != null) n.textContent = text; return n; };
    const chip = mk('button', 'sx-chip'); chip.type = 'button'; chip.setAttribute('aria-label', 'Rekorder – Aufnahme');
    const punkt = mk('span', 'sx-chip-mark', '●'), chipText = mk('span', 'sx-chip-text', 'Rekorder');
    chip.append(punkt, chipText);
    const panel = mk('div', 'sx-panel sx-rekorder-panel'); panel.hidden = true;
    const kopf = mk('div', 'sx-rek-kopf');
    const kopfPunkt = mk('span', 'sx-rek-punkt'), kopfTitel = mk('b', null, 'Rekorder'), kopfZeit = mk('span', 'sx-rek-zeit', '00:00'), kopfStatus = mk('span', 'sx-rek-status', 'Bereit');
    kopf.append(kopfPunkt, kopfTitel, kopfStatus, kopfZeit);
    const titel = mk('input', 'sx-rek-titel'); titel.placeholder = 'Titel, z. B. Teamrunde';
    const SEGS = 16, segs = [];
    const pegel = mk('div', 'sx-rek-pegel'); pegel.setAttribute('aria-hidden', 'true');
    for(let i = 0; i < SEGS; i++){ const b = mk('span'); b.style.height = (20 + Math.round(i * 80 / (SEGS - 1))) + '%'; if(i >= SEGS * 0.75) b.classList.add('hoch'); segs.push(b); pegel.append(b); }
    // Empfindlichkeit des Pegels (nur die Anzeige; die Aufnahme bleibt unverändert). Die Wahl bleibt je Browser gemerkt.
    const EMPF_KEY = 'sedra.rekorder.empfindlichkeit';
    const empfRegler = mk('input', 'sx-rek-empf'); empfRegler.type = 'range'; empfRegler.min = '0'; empfRegler.max = '24'; empfRegler.step = '1';
    let empfStart = 12; try{ const v = Number(localStorage.getItem(EMPF_KEY)); if(v >= 0 && v <= 24) empfStart = v; }catch(_err){}
    empfRegler.value = String(empfStart); empfRegler.setAttribute('aria-label', 'Empfindlichkeit des Pegels');
    empfRegler.addEventListener('input', ()=>{ try{ localStorage.setItem(EMPF_KEY, empfRegler.value); }catch(_err){} zeigen(); });
    const empfZeile = mk('div', 'sx-rek-empfzeile'), empfText = mk('small', 'sx-rek-label', 'Empfindlichkeit');
    empfZeile.append(empfText, empfRegler);
    const info = mk('small', 'sx-foot', '');
    const zeile = mk('div', 'sx-seg-group');
    const knopf = (text, fn)=>{ const b = mk('button', 'sx-seg-btn', text); b.type = 'button'; b.addEventListener('click', fn); return b; };
    // Das Pult der Leiste steuert die Aufnahme im Kern (sprache/kern.py): der Rechner nimmt auf, nicht die Seite. Ein Shell-Wechsel
    // lädt die Seite neu; das Pult holt den Stand danach wieder ab.
    let stand = {status: 'aus', sekunden: 0}, meldung = '';
    const holen = async()=>{ try{ stand = await CORE_API('/api/sprache/kern/stand'); }catch(_err){} zeigen(); };
    const tun = async(pfad, body)=>{
      try{ return await CORE_API(pfad, {method: 'POST', body: body || {}}); }
      catch(err){ meldung = err.message; return null; }
      finally{ await holen(); }
    };
    // Ohne Titel bekommt die Aufnahme einen Namen aus dem, was gerade läuft: „Translator · Aufnahme 20.10. 12:30“
    const autoTitel = ()=>{
      const shell = ((document.querySelector('.sx-umschalter .sx-chip-text') || {}).textContent || '').trim();
      const jetzt = new Date(), z = n=>String(n).padStart(2, '0');
      return (shell ? shell + ' · ' : '') + 'Aufnahme ' + z(jetzt.getDate()) + '.' + z(jetzt.getMonth() + 1) + '. ' + z(jetzt.getHours()) + ':' + z(jetzt.getMinutes());
    };
    const starten = async()=>{
      if(stand.status !== 'aus') return;
      meldung = '';
      if(await tun('/api/sprache/kern/start', {titel: titel.value.trim() || autoTitel(), sprache: 'de'})) titel.value = '';
    };
    const pausieren = ()=>{ meldung = ''; return tun(stand.status === 'pause' ? '/api/sprache/kern/weiter' : '/api/sprache/kern/pause'); };
    const stoppen = async()=>{
      meldung = '';
      const a = await tun('/api/sprache/kern/stopp');
      if(a){ meldung = 'Gesichert: „' + a.titel + '“'; zeigen(); }
    };
    const verwerfen = async()=>{ meldung = ''; if(await tun('/api/sprache/kern/verwerfen')){ meldung = 'Verworfen – nichts gespeichert.'; zeigen(); } };
    holen();
    // Abfragen nur, solange das Pult offen ist oder eine Aufnahme läuft – sonst keine Hintergrundaufrufe
    setInterval(()=>{ if(!panel.hidden || stand.status !== 'aus') holen(); }, 1000);
    zeile.append(knopf('Start', starten), knopf('Pause', pausieren), knopf('Stopp', stoppen), knopf('Verwerfen', verwerfen));
    zeile.children[2].classList.add('stopp');
    panel.append(kopf, titel, pegel, empfZeile, zeile, info);
    const zeigen = ()=>{
      const s = stand, rec = s.status === 'laeuft', pause = s.status === 'pause', lauft = rec || pause;
      const m = Math.floor(s.sekunden || 0), zeit = String(Math.floor(m/60)).padStart(2,'0') + ':' + String(m%60).padStart(2,'0');
      chipText.textContent = lauft ? zeit : 'Rekorder';
      punkt.classList.toggle('rec', rec); punkt.classList.toggle('pause', pause);
      kopfPunkt.classList.toggle('rec', rec); kopfPunkt.classList.toggle('pause', pause);
      kopfZeit.textContent = zeit;
      kopfTitel.textContent = lauft && s.titel ? s.titel : 'Rekorder';
      kopfStatus.textContent = rec ? 'Nimmt auf' : (pause ? 'Pause' : 'Bereit');
      kopfStatus.className = 'sx-rek-status' + (rec ? ' rec' : (pause ? ' pause' : ''));
      // Pegel aus dem Kern liegt in 0..1 für −60…0 dB; der Regler hebt die Anzeige um 0…24 dB an
      const db = (s.pegel || 0) * 60 - 60 + Number(empfRegler.value);
      const n = rec ? Math.round(Math.max(0, Math.min(1, (db + 60) / 60)) * SEGS) : 0;
      segs.forEach((b, i)=>b.classList.toggle('on', i < n));
      info.textContent = lauft ? (rec ? 'Die Aufnahme läuft im Kern – ein Shell-Wechsel unterbricht sie nicht.' : 'Pause – „Weiter“ setzt fort.') : (meldung || 'Bereit. Die Aufnahme läuft im Kern am Rechner.');
      info.className = /kein_|Keine|nicht|ging|Nicht|Verwerfen/.test(info.textContent) && !lauft && meldung ? 'sx-note' : 'sx-foot';
    };
    chip.addEventListener('click', ()=>{ panel.hidden = !panel.hidden; });
    zeigen();
    return {chip, panel};
  }

  root.sedraWechsel = {mount, entries, setScale, restoreScale, scales: SCALES, menuWahl, menuSeite, setMenuSeite, MENU_SEITEN, beimWechsel, vorDemWechsel, neuLaden};
  if(typeof module !== 'undefined' && module.exports) module.exports = {entries, scales: SCALES};
})();
