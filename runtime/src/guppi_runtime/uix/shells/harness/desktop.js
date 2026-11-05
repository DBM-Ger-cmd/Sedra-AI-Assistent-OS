// Harness-Shell – die Wahl des Captains für Start-Menü und Taskleiste (Desktop Builder, 05.11.2026). Rein und klein: der Zustand (`S._desktop`, aus GET /api/harness/desktop), das Anlegen
// über die Vorgabe der Shell (Start-Menü: ausblenden und Gruppe; Taskleiste: ausblenden und Reihenfolge) und das Speichern (POST /api/harness/desktop). Leer heißt: die Vorgabe der Shell.
// Der Desktop Builder (builder.js) bearbeitet, was hier liegt; startmenue.js und taskleiste.js rufen `startKonfig` und `zellenAnwenden`.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const LEER = ()=>({start: {ausblenden: [], zuordnung: {}}, zellen: {ausblenden: [], reihenfolge: []}, marke: {name: '', akzent: '', logo: '', schrift: ''}, startseite: {ort: '', titel: '', text: ''},
                         layout: {start: {}, zeile: {reihenfolge: [], ausblenden: []}, werkzeuge: {reihenfolge: [], ausblenden: []}, menue: {reihenfolge: [], ausblenden: []}, blick: {reihenfolge: [], ausblenden: []},
                                   zonen: {seite: {platz: 'links', breite: 0}, taskleiste: {platz: 'unten'}, eingabe: {platz: 'unten', breite: 0}}},
                         profil: null, profile: []});
  // Schriftfamilien ohne Nachladen aus dem Netz (der Server kennt dieselben Namen); leer = die Schrift der Shell
  const SCHRIFTEN = {serif: 'Georgia,"Times New Roman",serif', mono: 'Consolas,"Courier New",monospace', humanist: '"Trebuchet MS","Gill Sans",Verdana,sans-serif', breit: 'Verdana,Tahoma,"Segoe UI",sans-serif'};
  const SCHRIFT_NAMEN = {serif: 'Serif (Georgia)', mono: 'Technisch (Consolas)', humanist: 'Freundlich (Trebuchet)', breit: 'Breit (Verdana)'};
  // Grundfunktionen (ENTWURF_APPS_MODELL §2.2a): Posteingang, Aufgaben und die Zelle Freigaben lassen sich nie ausblenden – dasselbe prüft der Server
  const GRUND_START = ['decisions', 'tasks'], GRUND_ZELLEN = ['decisions'];
  // Die Zellen der Taskleiste in der Vorgabe-Reihenfolge: Schlüssel (= data-zelle) und Name für den Desktop Builder
  const ZELLEN = [['decisions', 'Freigaben'], ['token', 'Token'], ['model', 'Modell'], ['temp', 'Temperatur'], ['vram', 'Grafikspeicher (VRAM)'], ['ram', 'Arbeitsspeicher (RAM)'],
                  ['server', 'Modellserver'], ['scheduler', 'Scheduler'], ['state', 'Zustand']];

  const wahl = S=>S._desktop || (S._desktop = LEER());

  // Die Konfiguration des Start-Menüs mit der Wahl darüber: ausgeblendete Apps kommen dazu, eine gewählte Gruppe gilt vor der Vorgabe.
  function startKonfig(S, konfig){
    const w = wahl(S).start;
    if(!konfig || (!w.ausblenden.length && !Object.keys(w.zuordnung).length)) return konfig;
    return Object.assign({}, konfig, {ausblenden: (konfig.ausblenden || []).concat(w.ausblenden), zuordnung: Object.assign({}, konfig.zuordnung, w.zuordnung)});
  }

  // Die Zellen der Taskleiste (DOM-Knoten mit dataset.zelle): ausgeblendete fallen weg, die übrigen folgen der gewählten Reihenfolge (nicht genannte behalten ihren Platz dahinter).
  function zellenAnwenden(S, knoten){
    const z = wahl(S).zellen;
    const aus = new Set(z.ausblenden);
    const rest = knoten.filter(k=>!aus.has(k.dataset && k.dataset.zelle));
    if(!z.reihenfolge.length) return rest;
    const platz = k=>{ const i = z.reihenfolge.indexOf(k.dataset && k.dataset.zelle); return i < 0 ? 1000 : i; };
    return rest.map((k, i)=>[k, i]).sort((a, b)=>platz(a[0]) - platz(b[0]) || a[1] - b[1]).map(x=>x[0]);
  }

  // Die Marke des Auftraggebers: Name im Titel des Fensters, Akzentfarbe über der Vorgabe (leer = Vorgabe der Shell)
  function markeAnwenden(S){
    const m = wahl(S).marke || {};
    if(typeof document === 'undefined') return;
    if(S._titelVorgabe === undefined) S._titelVorgabe = document.title;
    document.title = m.name || S._titelVorgabe;
    const r = document.documentElement.style;
    if(m.akzent) r.setProperty('--accent', m.akzent); else r.removeProperty('--accent');
    if(m.schrift && SCHRIFTEN[m.schrift]) r.setProperty('--font', SCHRIFTEN[m.schrift]); else r.removeProperty('--font');
  }

  // Die Begrüßung der leeren Sitzung (verlauf.js `startbild`): Logo, Titel und Text des Profils; ohne Wahl die Vorgabe der Shell
  function begruessung(S){
    const w = wahl(S), m = w.marke || {}, s = w.startseite || {};
    return {logo: m.logo || '', titel: s.titel || m.name || 'SEDRA', text: s.text || '', marke: m.name || ''};
  }

  // Die Startseite: liegt beim Start nur ein neuer Entwurf offen, kommt die gewählte App nach vorn (offene Reiter des Captains bleiben, wie sie waren)
  function startseiteOeffnen(S){
    const H = root.sedraHarness, ort = (wahl(S).startseite || {}).ort;
    if(!ort || S._startseiteOffen || !H.app || !H.reiter) return false;
    S._startseiteOffen = true;
    const liste = H.reiter.liste(S);
    if(liste.length > 1 || (liste[0] && !String(liste[0]).startsWith('neu-'))) return false;
    if(ort === 'builder'){ H.builder.oeffnen(S); return true; }
    const p = (root.sedraPlaces && root.sedraPlaces.PLACES || []).find(x=>x.id === ort);
    if(!p) return false;
    H.app.oeffnen(S, p);
    return true;
  }

  function neuZeichnen(S){
    const H = root.sedraHarness;
    markeAnwenden(S);
    if(H.bausteine){ H.bausteine.zonenAnwenden(S); H.bausteine.anwenden(S); if(S._start && S._start.el) H.bausteine.menueAnwenden(S, S._start.el); }        // Baukasten: Leisten im Eingabebereich und Abschnitte des Start-Menüs
    if(S.ansichten && S.ansichten.forEach) S.ansichten.forEach(a=>{ if(a && a.zeigeLeer && a.leer && a.leer()) a.zeigeLeer(); });       // leere Sitzungen zeigen Logo und Begrüßung des Profils
    if(H.startmenue && S._start) { try{ H.startmenue.bauen(S); }catch(_e){ /* das Menü baut sich beim nächsten Öffnen neu */ } }
    if(H.taskleiste && S._leiste){ S._leiste.zuletzt = 0; H.taskleiste.status(S); }
  }

  async function laden(S){
    try{ S._desktop = Object.assign(LEER(), await S.api('/api/harness/desktop')); }
    catch(_e){ S._desktop = S._desktop || LEER(); }
    neuZeichnen(S);
    return S._desktop;
  }

  // teil: {start: {...}} und/oder {zellen: {...}}; null setzt den Teil auf die Vorgabe zurück
  async function speichern(S, teil){
    const out = await S.api('/api/harness/desktop', {method: 'POST', body: teil});
    S._desktop = Object.assign(LEER(), out);
    neuZeichnen(S);
    return S._desktop;
  }

  root.sedraHarness = root.sedraHarness || {};
  // Profil-Aktionen: profil_speichern {id, name, auftraggeber?, beschreibung?} · profil_anwenden {id} · profil_loeschen {id} · profil_importieren {profil}
  async function aktion(S, body){
    const out = await S.api('/api/harness/desktop', {method: 'POST', body});
    S._desktop = Object.assign(LEER(), out);
    neuZeichnen(S);
    return S._desktop;
  }

  // Die Auswahl „Profil“ für das Start-Menü: Vorgabe der Shell, eine eigene Wahl oder eines der gespeicherten Profile; null, wenn es keine Profile gibt
  function profilWahl(S, danach){
    const w = wahl(S);
    if(!w.profile.length) return null;
    const sel = document.createElement('select'); sel.className = 'hs-projektwahl hs-start-profil'; sel.setAttribute('aria-label', 'Profil der Oberfläche');
    const eigen = !w.profil && (w.start.ausblenden.length || Object.keys(w.start.zuordnung).length || w.zellen.ausblenden.length || w.zellen.reihenfolge.length || w.marke.name || w.marke.akzent);
    [['', eigen ? 'Profil: eigene Wahl' : 'Profil: Vorgabe der Shell']].concat(w.profile.map(p=>[p.id, 'Profil: ' + p.name])).forEach(([wert, text])=>{ const o = document.createElement('option'); o.value = wert; o.textContent = text; sel.append(o); });
    sel.value = w.profil || '';
    sel.onchange = async()=>{
      try{
        if(sel.value) await aktion(S, {aktion: 'profil_anwenden', id: sel.value}); else await speichern(S, {start: null, zellen: null, marke: null});
        if(danach) danach();
      }catch(err){ S.hinweis('Profil nicht gewechselt: ' + err.message, 'warn'); sel.value = w.profil || ''; }
    };
    return sel;
  }

  root.sedraHarness.desktop = {SCHRIFTEN, SCHRIFT_NAMEN, begruessung, startseiteOeffnen, profilWahl, ZELLEN, GRUND_START, GRUND_ZELLEN, wahl, startKonfig, zellenAnwenden, markeAnwenden, laden, speichern, aktion, LEER};
})();
