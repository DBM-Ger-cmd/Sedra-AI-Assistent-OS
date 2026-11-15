// Harness-Shell – die Delegations-Karte im Gespräch (SPEC_DELEGATION_IM_GESPRAECH_v1 §3.4, T6; DG-10, DG-11, DG-12).
// Der Server meldet den Stand einer Delegation auf dem Bus (`harness.team`): je Helfer Rolle, Auftrag in einem Satz, Zustand, Züge,
// Token, Dauer. Die Karte steht im Verlauf der Hauptsitzung und ändert sich an Ort und Stelle; in der Taskleiste steht, solange
// Helfer arbeiten, „Team a/n“. Hier wird nichts entschieden: „Freigabe ansehen“ öffnet den Posteingang, entschieden wird nur auf der
// Karte der Freigabe (DG-11). Anhalten geht an POST /api/harness/team/<T-…>/stopp (DG-09).
// `zeilen`, `kopf` und `dauer` sind rein (Stand rein, Anzeige raus), node prüft sie ohne Browser. Text nur mit textContent.
// Nicht gebaut: eine beendete Delegation erscheint nach dem Neuladen der Seite nicht wieder als Karte (die Helfer-Sitzungen bleiben
// in der Seitenleiste); ist der Reiter der Hauptsitzung zu, gibt es keine Karte, nur die Zelle der Taskleiste.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  root.sedraHarness = root.sedraHarness || {};
  const T = k=>(root.t ? root.t(k) : k);
  const mit = (text, werte)=>Object.keys(werte).reduce((s, k)=>s.split('{' + k + '}').join(String(werte[k])), text);
  const TON = {wartet: 'still', laeuft: 'aktiv', freigabe: 'warn', fertig: 'ok', gescheitert: 'bad', angehalten: 'still'};
  const OFFEN = ['wartet', 'laeuft', 'freigabe'];

  function dauer(sekunden){
    const s = Math.max(0, Math.round(Number(sekunden) || 0));
    return s < 60 ? s + ' s' : Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0') + ' min';
  }

  // Je Helfer eine Anzeigezeile (DG-10).
  function zeilen(stand){
    return ((stand && stand.helfer) || []).map(h=>{
      const token = h.token || {};
      return {nr: h.nr, sitzung_id: h.sitzung_id || null, rolle: h.rolle, auftrag: h.auftrag_kurz || '', zustand: h.zustand, ton: TON[h.zustand] || 'still',
              text: T('dg_z_' + h.zustand), grund: h.zustand === 'gescheitert' ? (h.grund || '') : '',
              messung: [h.zuege === 1 ? T('dg_zug') : mit(T('dg_zuege'), {n: h.zuege || 0}), mit(T('dg_token'), {n: (Number(token.ein) || 0) + (Number(token.aus) || 0)}), dauer(h.sekunden)].join(' · '),
              anhalten: OFFEN.includes(h.zustand), freigabe: h.zustand === 'freigabe', verlauf: !!h.sitzung_id};
    });
  }

  function kopf(stand){
    const helfer = (stand && stand.helfer) || [], aktiv = helfer.filter(h=>OFFEN.includes(h.zustand)).length;
    return {titel: mit(T('dg_titel'), {n: helfer.length}), aktiv, gesamt: helfer.length, fertig: !aktiv,
            lage: aktiv ? mit(T('dg_aktiv'), {a: aktiv, n: helfer.length}) : T('dg_abgeschlossen')};
  }

  async function stoppen(S, stand, sitzungId){
    try{ await S.api('/api/harness/team/' + stand.delegation + '/stopp', {method: 'POST', body: {sitzung_id: sitzungId || null}}); }
    catch(err){ S.hinweis(T('dg_stopp_fehler') + err.message, 'warn'); }
  }

  function knopf(text, klasse, tun, name){
    const k = document.createElement('button'); k.type = 'button'; k.className = 'hs-knopf hs-klein' + (klasse ? ' ' + klasse : ''); k.textContent = text;
    if(name) k.setAttribute('aria-label', name);
    k.onclick = tun;
    return k;
  }

  function zeichnen(S, el, stand){
    const k = kopf(stand);
    el.classList.toggle('fertig', k.fertig);
    const oben = document.createElement('div'); oben.className = 'hs-team-kopf';
    const titel = document.createElement('b'); titel.textContent = k.titel;
    const lage = document.createElement('span'); lage.className = 'hs-leise'; lage.textContent = k.lage;
    oben.append(titel, lage);
    if(!k.fertig) oben.append(knopf(T('dg_alle_anhalten'), 'warn', ()=>stoppen(S, stand, null)));
    const liste = document.createElement('ol'); liste.className = 'hs-team-liste';
    zeilen(stand).forEach(z=>{
      const li = document.createElement('li'); li.className = 'hs-team-zeile ' + z.ton; li.dataset.zustand = z.zustand; li.dataset.nr = String(z.nr);
      const punkt = document.createElement('span'); punkt.className = 'hs-team-punkt'; punkt.setAttribute('aria-hidden', 'true');
      const mitte = document.createElement('div'); mitte.className = 'hs-team-mitte';
      const erste = document.createElement('div'); erste.className = 'hs-team-erste';
      const rolle = document.createElement('b'); rolle.textContent = z.rolle;
      const zustand = document.createElement('span'); zustand.className = 'hs-team-zustand'; zustand.textContent = z.text + (z.grund ? ' – ' + z.grund : '');
      erste.append(rolle, zustand);
      const auftrag = document.createElement('div'); auftrag.className = 'hs-team-auftrag'; auftrag.textContent = z.auftrag;
      const messung = document.createElement('small'); messung.className = 'hs-leise'; messung.textContent = z.messung;
      mitte.append(erste, auftrag, messung);
      const tun = document.createElement('div'); tun.className = 'hs-team-tun';
      if(z.freigabe) tun.append(knopf(T('dg_freigabe'), 'on', ()=>S.shellApi.decide(), T('dg_freigabe') + ': ' + z.rolle));
      if(z.verlauf) tun.append(knopf(T('dg_verlauf'), '', ()=>root.sedraHarness.reiter.oeffnen(S, z.sitzung_id), T('dg_verlauf') + ': ' + z.rolle));
      if(z.anhalten) tun.append(knopf(T('dg_anhalten'), '', ()=>stoppen(S, stand, z.sitzung_id), T('dg_anhalten') + ': ' + z.rolle));
      li.append(punkt, mitte, tun);
      liste.append(li);
    });
    el.replaceChildren(oben, liste);
  }

  // Die Zelle der Taskleiste: nur solange Helfer arbeiten (DG-12).
  function zelle(S){
    const leiste = S.el && S.el.taskleiste; if(!leiste) return;
    const staende = Object.values((S._team && S._team.staende) || {}).map(kopf).filter(k=>!k.fertig);
    let el = leiste.querySelector('.hs-team-zelle');
    if(!staende.length){ if(el) el.remove(); return; }
    if(!el){ el = document.createElement('span'); el.className = 'hs-team-zelle'; el.setAttribute('role', 'status'); el.title = T('dg_zelle_titel'); }
    el.textContent = mit(T('dg_zelle'), {a: staende.reduce((n, k)=>n + k.aktiv, 0), n: staende.reduce((n, k)=>n + k.gesamt, 0)});
    if(!el.isConnected) leiste.append(el);
  }

  // Ein Stand kommt vom Bus (oder beim Start von GET /api/harness/team): Karte anlegen oder an Ort und Stelle neu zeichnen.
  function melden(S, stand){
    if(!stand || !stand.delegation) return;
    const t = S._team || (S._team = {staende: {}, karten: {}});
    t.staende[stand.delegation] = stand;
    let el = t.karten[stand.delegation];
    if(!el || !el.isConnected){
      const ansicht = S.ansichten && S.ansichten.get(stand.eltern);
      if(ansicht && ansicht.neu){
        el = document.createElement('section'); el.className = 'hs-team'; el.dataset.delegation = stand.delegation; el.setAttribute('aria-label', T('dg_karte'));
        ansicht.neu(el); t.karten[stand.delegation] = el;
      }else el = null;
    }
    if(el) zeichnen(S, el, stand);
    zelle(S);
    if(stand.fertig) setTimeout(()=>{ if(t.staende[stand.delegation] === stand){ delete t.staende[stand.delegation]; zelle(S); } }, 4000);
  }

  function mount(S){
    S._team = {staende: {}, karten: {}};
    S.ctx.bus.on('harness.team', e=>melden(S, e));
    const TL = root.sedraHarness.taskleiste;                       // die Taskleiste zeichnet sich neu: die Zelle kommt danach wieder dazu
    if(TL && TL.zeichnen){ const alt = TL.zeichnen; TL.zeichnen = function(){ const r = alt.apply(this, arguments); zelle(S); return r; }; }
    S.api('/api/harness/team').then(out=>((out && out.laufende) || []).forEach(s=>melden(S, s))).catch(()=>{});
  }

  root.sedraHarness.delegation = {mount, melden, zeilen, kopf, dauer, zelle};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.delegation;
})();
