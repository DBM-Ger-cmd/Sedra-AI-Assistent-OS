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
  const EINSTELLUNGEN = {id: 'einstellungen', label: 'Einstellungen', hint: 'Startseite, Allgemein, Agent, Sprache, Integrationen, Modelle, System', symbol: '⚙', gruppe: 'system', fest: true, werkzeuge: []};
  // Captain 03.11.2026: „Token und Gespräch“ bleibt in den Einstellungen und ist im Start-Menü unter Sedra Token nur verlinkt (`fest` nennt den Punkt)
  const TOKEN_GESPRAECH = {id: 'token-gespraech', label: 'Token und Gespräch', hint: 'Verbrauch, Denken, Antwortbudget, Länge des Verlaufs', symbol: '◎', gruppe: 'token', fest: 'agent/token', words: ['token', 'gespräch', 'gespraech', 'denken', 'budget'], werkzeuge: []};
  const FEST = {system: [EINSTELLUNGEN], token: [TOKEN_GESPRAECH]};          // feste Einträge je Gruppe – kein Ort, kein Werkzeug: die Shell trägt sie ein
  const FESTE = [EINSTELLUNGEN, TOKEN_GESPRAECH];

  function stand(S){ return S._start || (S._start = {offen: false, konfig: null, konfigFehler: null, zuletzt: [], liste: null, module: null, wartet: null, offene: new Set()}); }

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
    blickLaden(S);
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
    if(app.fest){ root.sedraHarness.einstellungen.oeffnen(S, app.fest === true ? undefined : app.fest); return; }
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
    const abschnitt = (titel, apps, klasse)=>{
      if(!apps.length) return;
      const box = d().el('section', 'hs-start-gruppe');
      box.append(d().el('div', 'hs-ueber', titel));
      const raster = d().el('div', 'hs-start-raster' + (klasse ? ' ' + klasse : ''));
      apps.forEach(a=>{ st.sichtbar.push(a); raster.append(appKnopf(S, a, nr++)); });
      box.append(raster); inhalt.append(box);
    };
    // Kategorie als Kachel: Kopf (Symbol, Titel, Anzahl) und eine kleine Vorschau der ersten Apps; „+N weitere“ klappt die Kachel auf.
    // Alle Apps stehen im DOM (die versteckten nur mit hidden), die Pfeiltasten gehen über die sichtbaren.
    const VORSCHAU = 4;
    const kachel = (g, apps)=>{
      if(!apps.length) return null;
      const offen = st.offene.has(g.id);
      const box = d().el('section', 'hs-start-kachel' + (offen ? ' offen' : '')); box.dataset.gruppe = g.id;
      const umschalten = ()=>{ offen ? st.offene.delete(g.id) : st.offene.add(g.id); zeichnen(S); };
      const kopf = d().el('button', 'hs-start-kachel-kopf'); kopf.type = 'button'; kopf.setAttribute('aria-expanded', offen ? 'true' : 'false');
      kopf.append(d().el('span', 'hs-start-symbol', g.symbol || '▤'), d().el('span', 'hs-start-kachel-titel', g.titel), d().el('small', 'hs-leise', String(apps.length)));
      kopf.onclick = umschalten;
      const liste = d().el('div', 'hs-start-kachel-liste');
      apps.forEach((a, i)=>{
        const zeigen = offen || i < VORSCHAU;
        const k = appKnopf(S, a, zeigen ? nr++ : -1);
        if(zeigen) st.sichtbar.push(a); else k.hidden = true;
        liste.append(k);
      });
      box.append(kopf, liste);
      if(apps.length > VORSCHAU){
        const mehr = d().el('button', 'hs-start-mehr', offen ? 'weniger' : '+' + (apps.length - VORSCHAU) + ' weitere'); mehr.type = 'button'; mehr.onclick = umschalten;
        box.append(mehr);
      }
      return box;
    };
    if(st.konfigFehler) inhalt.append(d().el('div', 'hs-app-satz warn', st.konfigFehler));
    if(q){
      const ql = q.toLowerCase();
      const treffer = L().suchen(st.liste, q).concat(FESTE.filter(f=>[f.label].concat(f.words || []).some(w=>String(w).toLowerCase().startsWith(ql))));
      if(!treffer.length) inhalt.append(d().el('div', 'hs-app-satz', 'Keine App zu „' + q + '“. Strg+K sucht Orte und Befehle.'));
      abschnitt('Treffer', treffer);
    }else{
      abschnitt('Zuletzt benutzt', st.liste.zuletzt, 'zuletzt');
      inhalt.append(blick(S));
      // die Gruppen in der Reihenfolge der Datei; System und Sedra Token gibt es auch ohne Ort, sie tragen feste Einträge
      const jeId = {};
      st.liste.gruppen.forEach(g=>{ jeId[g.id] = g; });
      const reihe = (st.konfig && st.konfig.gruppen) || L().GRUPPEN, sym = (st.konfig && st.konfig.symbole) || L().SYMBOLE;
      const gruppen = reihe.filter(id=>jeId[id] || FEST[id]).map(id=>jeId[id] || {id, titel: L().TITEL[id], symbol: sym[id], apps: []});
      const kacheln = d().el('div', 'hs-start-kacheln');
      gruppen.forEach(g=>{ const k = kachel(g, g.apps.concat(FEST[g.id] || [])); if(k) kacheln.append(k); });
      inhalt.append(kacheln);
      if(!st.liste.apps.length) inhalt.append(d().el('div', 'hs-app-satz', 'Kein Werkzeug geladen – das Werkzeug „Module“ sagt, warum.'));
    }
    if(st.wahl >= st.sichtbar.length) st.wahl = Math.max(0, st.sichtbar.length - 1);
    inhalt.querySelectorAll('.hs-start-app').forEach(k=>k.classList.toggle('wahl', Number(k.dataset.nr) === st.wahl));
    fuss(S);
  }

  // „Auf einen Blick“ (Captain 03.11.2026): kleine Apps mit den wichtigsten Werten – KI-Labor, Sedra Token, Hardware, Modelle. Nur lesend; ein Klick öffnet die App.
  const BLICK = [
    {ort: 'labor', titel: 'KI-Labor', symbol: '☁', werte: b=>b.labor ? [['Cloud', b.labor.enabled ? 'an' : 'aus', b.labor.enabled ? 'ok' : ''], ['Anbieter bereit', b.labor.bereit + ' von ' + b.labor.gesamt], ['Aktiv', b.labor.live || 'keiner']] : null},
    {ort: 'meter', titel: 'Sedra Token', symbol: '◎', werte: b=>b.token ? [['Antworten heute', String(b.token.antworten)], ['Eingehend ↑', zahl(b.token.ein)], ['Erzeugt ↓', zahl(b.token.aus)]] : null},
    {ort: 'hardware', titel: 'Hardware', symbol: '▦', werte: b=>b.strip ? [['GPU', wertVon(b.strip.gpu), tonVon(b.strip.gpu)], ['RAM', wertVon(b.strip.ram), tonVon(b.strip.ram)]] : null},
    {ort: 'models', titel: 'Modelle', symbol: '◆', werte: b=>b.strip ? [['Modell', wertVon(b.strip.model), tonVon(b.strip.model)], ['Server', wertVon(b.strip.server), tonVon(b.strip.server)]] : null}
  ];
  const zahl = n=>Number(n || 0).toLocaleString('de-DE');
  const wertVon = g=>String((g && g.value !== undefined && g.value !== null) ? g.value : '–');
  const tonVon = g=>(g && g.tone && g.tone !== 'off') ? g.tone : '';

  function blick(S){
    const st = stand(S);
    const box = d().el('section', 'hs-start-blick'); box.setAttribute('aria-label', 'Auf einen Blick');
    BLICK.forEach(k=>{
      const ort = (root.sedraPlaces.PLACES || []).find(p=>p.id === k.ort);
      if(!ort) return;
      const b = d().el('button', 'hs-start-blick-kachel'); b.type = 'button'; b.dataset.blick = k.ort;
      b.append(d().el('span', 'hs-start-blick-kopf'), d().el('span', 'hs-start-blick-werte'));
      b.firstChild.append(d().el('span', 'hs-start-symbol', k.symbol), d().el('b', null, k.titel));
      const werte = k.werte(st.blick || {});
      const ziel = b.lastChild;
      (werte || [['Stand', 'wird geladen …']]).forEach(([label, wert, ton])=>{ const z = d().el('span', 'hs-start-blick-zeile'); z.append(d().el('small', 'hs-leise', label), d().el('b', ton ? 'hs-start-ton ' + ton : null, wert)); ziel.append(z); });
      b.onclick = ()=>{ schliessen(S); root.sedraHarness.app.oeffnen(S, ort); benutzt(S, {id: ort.id}); };
      box.append(b);
    });
    return box;
  }

  // beim Öffnen des Menüs lesen (nichts wird gepollt); jede Quelle für sich, fällt eine aus, bleiben die anderen
  function blickLaden(S){
    const st = stand(S);
    st.blick = st.blick || {};
    const neu = ()=>{ if(st.offen && !st.el.suche.value.trim()) zeichnen(S); };
    const heute = ()=>{ const t = S.tokenStand && S.tokenStand.heute; if(t) st.blick.token = t; };
    heute();
    if(S.tokenLaden) Promise.resolve(S.tokenLaden()).then(()=>{ heute(); neu(); }, ()=>{});
    S.api('/api/strip').then(v=>{ st.blick.strip = v || {}; neu(); }).catch(()=>{});
    S.api('/api/cloud').then(c=>{
      const p = c.providers || [];
      st.blick.labor = {enabled: !!c.enabled, bereit: p.filter(x=>x.status === 'bereit').length, gesamt: p.length, live: (c.live || []).join(', ')};
      neu();
    }).catch(()=>{});
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
