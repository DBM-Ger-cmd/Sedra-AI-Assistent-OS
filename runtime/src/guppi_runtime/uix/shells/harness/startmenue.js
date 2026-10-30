// Harness-Shell Stufe 4 – das Start-Menü (SPEC_HARNESS_SHELL_v1 HS-30, HS-40, HS-41; G2 Stufe 4 §3.3, §4; G3 N4).
//
// Öffnet über den Knopf „Start“ in der Taskleiste, Alt+S (Haken in ui/wechsel.js, Vertrag N3) und `/start` in der Eingabe; schließt mit Esc,
// Klick außerhalb und mit jeder Auswahl. Oben die Suche (Fokus beim Öffnen; Pfeile/Enter wie die Palette), darunter „Zuletzt benutzt“
// (aus `uix.shelf.harness` – auf dem Rechner, nicht im Browser, D-S7), die Gruppen aus start_gruppen.json, unten die Oberflächen
// (Wechsel über sedraWechsel – derselbe Code, derselbe Audit-Eintrag) und Darstellung · Schrift. Die Liste selbst baut startliste.js (rein).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const L = ()=>root.sedraStartliste;
  const KONFIG_URL = '/uix/shells/harness/start_gruppen.json';
  const SCHUB_MS = 2000;
  // Stufe 5 (G2 §3.1): fester Eintrag in der Gruppe System – kein Ort, kein Werkzeug: die Shell trägt ihn ein
  const EINSTELLUNGEN = {id: 'einstellungen', label: 'Einstellungen', hint: 'Allgemein, Agent, Sprache, Integrationen, Modelle, System', symbol: '⚙', gruppe: 'system', fest: true, werkzeuge: []};

  function stand(S){ return S._start || (S._start = {offen: false, konfig: null, konfigFehler: null, zuletzt: [], liste: null, module: null, wartet: null}); }

  async function laden(S){
    const st = stand(S);
    try{
      const res = await fetch(KONFIG_URL, {cache: 'no-store'});
      if(!res.ok) throw new Error('HTTP ' + res.status);
      st.konfig = L().zuordnungPruefen(await res.json()); st.konfigFehler = null;
    }catch(err){ st.konfig = L().zuordnungPruefen({}); st.konfigFehler = 'start_gruppen.json: ' + err.message + ' – alles steht unter „Arbeit“.'; }
    try{ st.module = await S.api('/api/uix/modules'); }catch(err){ st.module = {tools: [], shells: []}; st.moduleFehler = err.message; }
    try{
      const ablage = ((await S.api('/api/uix/shelf')).shelf || {}).harness || [];
      st.zuletzt = ablage.filter(e=>e.kind === 'place').map(e=>e.place);
    }catch(_err){ st.zuletzt = []; }
    bauen(S);
  }

  function bauen(S){
    const st = stand(S);
    const werkzeuge = (st.module && st.module.tools) || [];
    st.liste = L().bauen(root.sedraPlaces.PLACES, werkzeuge, o=>S.ctx.tools.forObject(o), st.konfig, st.zuletzt);
    return st.liste;
  }

  // „zuletzt benutzt“ nachführen und gebündelt auf den Rechner schreiben (kein Gate, Audit wie jede Ablage)
  function benutzt(S, app){
    const st = stand(S);
    st.zuletzt = L().zuletztNach(st.zuletzt, app.id, st.liste ? st.liste.zuletzt_max : 6);
    bauen(S);
    if(st.wartet) return;
    st.wartet = setTimeout(()=>{
      st.wartet = null;
      S.api('/api/uix/shelf', {method: 'POST', body: {shell: 'harness', items: L().alsAblage(st.liste, st.zuletzt)}}).catch(err=>S.hinweis('„Zuletzt benutzt“ nicht gemerkt: ' + err.message, 'warn'));
    }, SCHUB_MS);
  }

  // ---- das Menü
  function mount(S){
    const st = stand(S);
    const panel = d().el('div', 'hs-start-menue'); panel.hidden = true;
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Start-Menü');
    const suche = d().el('input', 'hs-start-suche'); suche.type = 'search'; suche.placeholder = 'App suchen … (Strg+K sucht einen Ort)';
    suche.setAttribute('aria-label', 'App suchen');
    const inhalt = d().el('div', 'hs-start-inhalt');
    const fuss = d().el('div', 'hs-start-fuss');
    panel.append(suche, inhalt, fuss);
    document.getElementById('sedra-root').append(panel);
    st.el = {panel, suche, inhalt, fuss};
    suche.oninput = ()=>zeichnen(S);
    suche.onkeydown = e=>tasten(S, e);
    document.addEventListener('click', e=>{ if(st.offen && !panel.contains(e.target) && !(e.target.closest && e.target.closest('.hs-start-knopf'))) schliessen(S); });
    document.addEventListener('keydown', e=>{ if(e.key === 'Escape' && st.offen){ e.preventDefault(); schliessen(S); } });
    if(root.sedraWechsel && root.sedraWechsel.menueHaken) root.sedraWechsel.menueHaken(()=>umschalten(S));
    laden(S);
  }

  function oeffnen(S){
    const st = stand(S); if(!st.el) return;
    st.offen = true; st.el.panel.hidden = false; st.el.suche.value = ''; st.wahl = 0;
    zeichnen(S);
    st.el.suche.focus();
    const knopf = document.querySelector('.hs-start-knopf'); if(knopf) knopf.setAttribute('aria-expanded', 'true');
  }
  function schliessen(S){
    const st = stand(S); if(!st.el) return;
    st.offen = false; st.el.panel.hidden = true;
    const knopf = document.querySelector('.hs-start-knopf'); if(knopf){ knopf.setAttribute('aria-expanded', 'false'); knopf.focus(); }
  }
  function umschalten(S){ stand(S).offen ? schliessen(S) : oeffnen(S); }

  function appKnopf(S, app, nr){
    const st = stand(S);
    const k = d().el('button', 'hs-start-app' + (nr === st.wahl ? ' wahl' : '')); k.type = 'button'; k.dataset.app = app.id; k.dataset.nr = nr;
    k.append(d().el('span', 'hs-start-symbol', app.symbol || '▤'), d().el('span', 'hs-start-name', app.label));
    if(app.hint) k.append(d().el('small', 'hs-leise', app.hint));
    k.title = app.label + (app.hint ? ' – ' + app.hint : '') + ' · Werkzeug: ' + (app.werkzeuge || []).join(', ');
    k.onclick = ()=>waehlen(S, app);
    return k;
  }

  function waehlen(S, app){
    schliessen(S);
    if(app.fest){ root.sedraHarness.einstellungen.oeffnen(S); return; }
    root.sedraHarness.app.oeffnen(S, app);
    benutzt(S, app);
  }

  function zeichnen(S){
    const st = stand(S); if(!st.el || !st.liste) return;
    const q = st.el.suche.value.trim();
    const inhalt = st.el.inhalt;
    inhalt.replaceChildren();
    let nr = 0;
    st.sichtbar = [];
    const abschnitt = (titel, apps)=>{
      if(!apps.length) return;
      const box = d().el('section', 'hs-start-gruppe');
      box.append(d().el('div', 'hs-ueber', titel));
      const raster = d().el('div', 'hs-start-raster');
      apps.forEach(a=>{ st.sichtbar.push(a); raster.append(appKnopf(S, a, nr++)); });
      box.append(raster); inhalt.append(box);
    };
    if(st.konfigFehler) inhalt.append(d().el('div', 'hs-app-satz warn', st.konfigFehler));
    if(q){
      const treffer = L().suchen(st.liste, q).concat('einstellungen'.startsWith(q.toLowerCase()) ? [EINSTELLUNGEN] : []);
      if(!treffer.length) inhalt.append(d().el('div', 'hs-app-satz', 'Keine App zu „' + q + '“. Strg+K sucht Orte und Befehle.'));
      abschnitt('Treffer', treffer);
    }else{
      abschnitt('Zuletzt benutzt', st.liste.zuletzt);
      const gruppen = st.liste.gruppen.some(g=>g.id === 'system') ? st.liste.gruppen : st.liste.gruppen.concat([{id: 'system', titel: 'System', symbol: '⚙', apps: []}]);
      gruppen.forEach(g=>abschnitt(g.symbol + ' ' + g.titel, g.id === 'system' ? g.apps.concat([EINSTELLUNGEN]) : g.apps));
      if(!st.liste.apps.length) inhalt.append(d().el('div', 'hs-app-satz', 'Kein Werkzeug geladen – das Werkzeug „Module“ sagt, warum.'));
    }
    if(st.wahl >= st.sichtbar.length) st.wahl = Math.max(0, st.sichtbar.length - 1);
    inhalt.querySelectorAll('.hs-start-app').forEach(k=>k.classList.toggle('wahl', Number(k.dataset.nr) === st.wahl));
    fuss(S);
  }

  // Oberflächen (HS-41) und Darstellung · Schrift – unten, einmal gezeichnet, Wechsel über sedraWechsel
  function fuss(S){
    const st = stand(S);
    const f = st.el.fuss; f.replaceChildren();
    const shells = ((st.module && st.module.shells) || []).filter(s=>s.id !== 'start' && s.id !== 'harness');
    const zeile = d().el('div', 'hs-start-oberflaechen'); zeile.setAttribute('role', 'group'); zeile.setAttribute('aria-label', 'Oberflächen');
    zeile.append(d().el('span', 'hs-ueber', 'Oberflächen'));
    shells.forEach(s=>{
      const k = d().el('button', 'hs-start-shell'); k.type = 'button'; k.dataset.shell = s.id;
      if(s.preview){ const img = d().el('img', 'hs-start-bild'); img.src = '/uix/shells/' + s.id + '/preview.png'; img.alt = ''; k.append(img); }
      k.append(d().el('span', null, s.name || s.id));
      if(s.default) k.append(d().el('small', 'hs-leise', 'Standard'));
      k.title = 'Wechseln zu ' + (s.name || s.id) + (s.description ? ' – ' + s.description : '') + ' · offene Apps gehen mit';
      k.onclick = ()=>{ schliessen(S); root.sedraWechsel.wechseln({shell: s.id}).catch(err=>S.hinweis('Wechsel nicht möglich: ' + err.message, 'warn')); };
      zeile.append(k);
    });
    if(!shells.length) zeile.append(d().el('small', 'hs-leise', st.moduleFehler ? 'Oberflächen nicht lesbar: ' + st.moduleFehler : 'keine andere Oberfläche im Paket'));
    const look = d().el('div', 'hs-start-look');
    const seg = (titel, optionen, aktuell, tun)=>{
      const g = d().el('span', 'hs-start-seg'); g.setAttribute('role', 'group'); g.setAttribute('aria-label', titel);
      g.append(d().el('small', 'hs-leise', titel));
      optionen.forEach(([id, label])=>{
        const b = d().el('button', 'hs-start-seg-btn' + (id === aktuell ? ' on' : ''), label); b.type = 'button'; b.setAttribute('aria-pressed', id === aktuell ? 'true' : 'false');
        b.onclick = ()=>{ tun(id); fuss(S); };
        g.append(b);
      });
      return g;
    };
    look.append(seg('Darstellung', [['klar', 'Klar'], ['nacht', 'Nacht']], document.documentElement.dataset.theme || 'nacht', v=>root.sedraBoot.setTheme(v)),
                seg('Schrift', [['normal', 'Normal'], ['gross', 'Groß']], document.documentElement.dataset.scale || 'normal', v=>root.sedraWechsel.setScale(v)));
    const leeren = d().el('button', 'hs-start-leeren', 'Gedächtnis leeren'); leeren.type = 'button';
    leeren.title = 'offene Apps, Ablage der Werkzeuge, Gesprächsverlauf – zweimal klicken';
    let scharf = null;
    leeren.onclick = e=>{
      e.stopPropagation();
      if(!scharf){ leeren.textContent = 'Wirklich leeren? Noch einmal klicken'; scharf = setTimeout(()=>{ scharf = null; leeren.textContent = 'Gedächtnis leeren'; }, 5000); return; }
      clearTimeout(scharf); scharf = null;
      root.sedraWechsel.leeren().then(()=>{ leeren.textContent = 'Gedächtnis geleert'; }).catch(err=>{ leeren.textContent = 'Nicht geleert: ' + err.message; });
    };
    look.append(leeren);
    f.append(zeile, look);
  }

  function tasten(S, e){
    const st = stand(S);
    const n = (st.sichtbar || []).length;
    if(e.key === 'ArrowDown' || e.key === 'ArrowRight'){ e.preventDefault(); st.wahl = n ? (st.wahl + 1) % n : 0; zeichnen(S); }
    else if(e.key === 'ArrowUp' || e.key === 'ArrowLeft'){ e.preventDefault(); st.wahl = n ? (st.wahl - 1 + n) % n : 0; zeichnen(S); }
    else if(e.key === 'Enter'){ e.preventDefault(); const a = (st.sichtbar || [])[st.wahl]; if(a) waehlen(S, a); }
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.startmenue = {mount, oeffnen, schliessen, umschalten, laden, zeichnen, waehlen, benutzt, bauen, KONFIG_URL};
})();
