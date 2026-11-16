// Harness-Shell – der Drache als Avatar mit Hilfestellungen (UIX nächste Stufe, Baustein F, Captain 15.11.2026).
// Ein Hinweis ist ein Satz und höchstens ein Knopf, neben dem Bedienelement, um das es geht. Fliegt der Drache (buehne3d.js, Wahl
// „hintergrund“), landet er daneben; sonst steht die Sprechblase allein. Der Avatar liest nur den Zustand der Shell: er erteilt nichts,
// startet nichts und beantwortet keine Freigabe – der Knopf öffnet nur die Stelle, an der der Captain selbst handelt.
// Regeln: nie mehr als ein Hinweis; ein geschlossener Hinweis kommt in diesem Fenster nicht wieder (eine neue Freigabe schon);
// er nimmt den Fokus nicht weg; Esc im Hinweis schließt ihn. Abschalten: localStorage `sedra.harness.avatar` = `aus`.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  root.sedraHarness = root.sedraHarness || {};
  const KEY = 'sedra.harness.avatar';
  const WARTEN_MS = 1200, BREITE = 300, RAND = 12;
  const T = k=>(root.t ? root.t(k) : k);
  const mit = (text, werte)=>Object.keys(werte).reduce((s, k)=>s.split('{' + k + '}').join(String(werte[k])), text);
  const aus = ()=>{ try{ return localStorage.getItem(KEY) === 'aus'; }catch(_e){ return false; } };

  // Die Anlässe in der Reihenfolge ihres Rangs. Rein: aus dem Zustand wird ein Hinweis oder nichts (test_uix_avatar über node).
  // zustand: {freigaben, lauf: {name, ok}|null, modell, leer}
  function anlass(z){
    if(z.freigaben > 0) return {id: 'freigabe:' + z.freigaben, text: mit(T(z.freigaben === 1 ? 'av_freigabe_eine' : 'av_freigabe_viele'), {n: z.freigaben}), knopf: T('av_freigabe_knopf'), tun: 'freigaben', anker: '[data-zelle="decisions"]'};
    if(z.lauf) return {id: 'lauf:' + z.lauf.id, text: mit(T(z.lauf.ok ? 'av_lauf_ok' : 'av_lauf_fehler'), {name: z.lauf.name}), knopf: '', tun: '', anker: '.hs-taskleiste', ton: z.lauf.ok ? '' : 'warn'};
    if(!z.modell) return {id: 'modell', text: T('av_modell'), knopf: T('av_modell_knopf'), tun: 'modell', anker: '.hs-eingabe-zeile'};
    if(z.leer) return {id: 'erste', text: T('av_erste'), knopf: T('av_erste_knopf'), tun: 'feld', anker: '.hs-eingabe-zeile'};
    return null;
  }

  // Wo die Sprechblase steht: über dem Anker, wenn dort Platz ist, sonst darunter; nie über den Fensterrand.
  function platz(anker, fenster, hoehe){
    const wunsch = anker.width > BREITE * 2 ? anker.right - BREITE : anker.left + anker.width / 2 - BREITE / 2;       // breiter Anker (das Eingabefeld): rechtsbündig darüber
    const links = Math.max(RAND, Math.min(wunsch, fenster.breite - BREITE - RAND));
    const oben = anker.top - hoehe - RAND >= RAND ? anker.top - hoehe - RAND : Math.min(anker.bottom + RAND, fenster.hoehe - hoehe - RAND);
    return {links, oben};
  }

  function zustand(S){
    const start = document.querySelector('.hs-flaeche .hs-start');
    return {freigaben: (S.entscheidungen || []).length, lauf: S._avatarLauf || null, modell: !!S.modell, leer: !!(start && start.offsetParent)};
  }

  function schliessen(S, merken){
    const a = S._avatar; if(!a || !a.el) return;
    if(merken && a.hinweis) a.zu.add(a.hinweis.id);
    if(a.hinweis && a.hinweis.id.startsWith('lauf:')) S._avatarLauf = null;
    a.el.remove(); a.el = null; a.hinweis = null;
    if(root.sedraHarness.buehne3d) root.sedraHarness.buehne3d.abheben();
  }

  function tun(S, was){
    const H = root.sedraHarness;
    if(was === 'freigaben') S.shellApi.decide();
    else if(was === 'modell') H.eingabe.modellMenue(S, true);
    else if(was === 'feld') H.eingabe.fokus(S);
  }

  function zeigen(S, h){
    const a = S._avatar, anker = document.querySelector(h.anker);
    if(!anker) return;
    const el = document.createElement('div'); el.className = 'hs-avatar' + (h.ton ? ' ' + h.ton : ''); el.setAttribute('role', 'status'); el.setAttribute('aria-live', 'polite');
    const text = document.createElement('span'); text.className = 'hs-avatar-text'; text.textContent = h.text;
    const zeile = document.createElement('div'); zeile.className = 'hs-avatar-zeile';
    if(h.knopf){
      const k = document.createElement('button'); k.type = 'button'; k.className = 'hs-knopf hs-klein hs-avatar-knopf'; k.textContent = h.knopf;
      k.onclick = ()=>{ schliessen(S, true); tun(S, h.tun); };
      zeile.append(k);
    }
    const zu = document.createElement('button'); zu.type = 'button'; zu.className = 'hs-avatar-zu'; zu.textContent = '×'; zu.setAttribute('aria-label', T('av_schliessen'));
    zu.onclick = ()=>schliessen(S, true);
    el.addEventListener('keydown', e=>{ if(e.key === 'Escape'){ e.stopPropagation(); schliessen(S, true); } });
    el.append(text, zeile, zu);
    document.querySelector('.hs').append(el);
    const p = platz(anker.getBoundingClientRect(), {breite: root.innerWidth, hoehe: root.innerHeight}, el.offsetHeight);
    el.style.left = p.links + 'px'; el.style.top = p.oben + 'px';
    a.el = el; a.hinweis = h;
    const B = root.sedraHarness.buehne3d;                   // der Drache setzt sich an die linke obere Ecke der Sprechblase
    if(B && B.landen(p.links + 70, p.oben - 24)) el.classList.add('mit-drache');
  }

  // Den Zustand ansehen und den passenden Hinweis zeigen, tauschen oder wegnehmen.
  function pruefen(S){
    const a = S._avatar; if(!a) return;
    if(aus()){ schliessen(S, false); return; }
    const h = anlass(zustand(S));
    if(a.hinweis && (!h || h.id !== a.hinweis.id)) schliessen(S, false);
    if(h && !a.el && !a.zu.has(h.id)) zeigen(S, h);
  }

  function mount(S){
    S._avatar = {el: null, hinweis: null, zu: new Set(), uhr: 0};
    const bald = ()=>{ clearTimeout(S._avatar.uhr); S._avatar.uhr = setTimeout(()=>pruefen(S), WARTEN_MS); };
    const bus = S.ctx.bus;
    ['model.changed', 'decision.pending', 'decision.answered', 'harness.antwort', 'harness.sitzung', 'harness.aufgabe'].forEach(n=>bus.on(n, bald));
    bus.on('harness.lauf', e=>{ if(e && e.zustand === 'ende'){ S._avatarLauf = {id: e.id, name: e.name || e.lauf || '', ok: e.status === 'ok'}; bald(); } });
    root.addEventListener('resize', ()=>{ if(S._avatar.el){ schliessen(S, false); bald(); } });
    const leer = S.leerGeaendert;                              // eine Sitzung wird leer oder bekommt ihre erste Nachricht
    S.leerGeaendert = function(ansicht){ const r = leer.apply(this, arguments); bald(); return r; };
    setTimeout(()=>pruefen(S), WARTEN_MS * 2);
  }

  root.sedraHarness.avatar = {mount, pruefen, schliessen, anlass, platz, KEY};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.avatar;
})();
