// Harness-Shell – die Seiten der Einstellungen im Stil der Windows-Einstellungen (Captain 03.11.2026, Referenzbilder): Startseite mit Kacheln und Stand,
// Gruppenseiten als Liste von Reihen (Symbol, Titel, Satz, Pfeil), Suche über alle Punkte. Rein darstellend: die Punkte selbst zeichnet einstellungen.js.
// Daten nur lesend (/api/strip, /api/cloud, S.tokenStand); ein Schlüssel oder ein Token steht nie auf diesen Seiten. Daten werden nie zu HTML.
// Alle festen Beschriftungen laufen über t() (strings_de.js / strings_en.js).
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const H = ()=>root.sedraHarness;
  const ZULETZT_KEY = 'sedra.harness.einstellungen.zuletzt';
  const ZULETZT_MAX = 4;
  const T = (k, ...a) => (root.t ? root.t(k, ...a) : k);
  const SYMBOL = {start: '⌂', allgemein: '◐', agent: '✦', sprache: '♪', integrationen: '⇄', modelle: '◆', system: '⚙'};
  // Symbol, Titel-Key und Satz-Key je Punkt – aufgelöst per T() beim Zeichnen
  const PUNKT = {
    'allgemein/darstellung': ['◐', 'es_klar_nacht_titel', 'es_klar_nacht_satz'],
    'allgemein/benachrichtigungen': ['⚑', 'es_benachrichtigungen_titel', 'es_benachrichtigungen_satz'],
    'allgemein/sprache': ['A', 'es_sprache_titel', 'es_sprache_satz'],
    'agent/vorlagen': ['▤', 'es_agent_vorlagen_titel', 'es_agent_vorlagen_satz'],
    'agent/freigabe': ['⛨', 'es_agent_freigabe_titel', 'es_agent_freigabe_satz'],
    'agent/grenzen': ['↻', 'es_agent_grenzen_titel', 'es_agent_grenzen_satz'],
    'agent/token': ['◎', 'es_agent_token_titel', 'es_agent_token_satz'],
    'sprache/rekorder': ['●', 'es_sprache_rekorder_titel', 'es_sprache_rekorder_satz'],
    'sprache/quelle': ['♪', 'es_sprache_quelle_titel', 'es_sprache_quelle_satz'],
    'integrationen/mcp': ['⇄', 'es_integrationen_mcp_titel', 'es_integrationen_mcp_satz'],
    'integrationen/gateway': ['⛨', 'es_integrationen_gateway_titel', 'es_integrationen_gateway_satz'],
    'integrationen/cloud': ['☁', 'es_integrationen_cloud_titel', 'es_integrationen_cloud_satz'],
    'integrationen/hilfswerkzeuge': ['⚒', 'es_integrationen_hilfswerkzeuge_titel', 'es_integrationen_hilfswerkzeuge_satz'],
    'modelle/bibliothek': ['▣', 'es_modelle_bibliothek_titel', 'es_modelle_bibliothek_satz'],
    'modelle/werkstatt': ['◆', 'es_modelle_werkstatt_titel', 'es_modelle_werkstatt_satz'],
    'modelle/slots': ['▦', 'es_modelle_slots_titel', 'es_modelle_slots_satz'],
    'modelle/laufzeit': ['⚙', 'es_modelle_laufzeit_titel', 'es_modelle_laufzeit_satz'],
    'system/schalter': ['⏻', 'es_system_schalter_titel', 'es_system_schalter_satz'],
    'system/grenzen': ['⊘', 'es_system_grenzen_titel', 'es_system_grenzen_satz'],
    'system/module': ['▦', 'es_system_module_titel', 'es_system_module_satz'],
    'system/audit': ['☰', 'es_system_audit_titel', 'es_system_audit_satz'],
    'system/info': ['ⓘ', 'es_system_info_titel', 'es_system_info_satz']
  };
  const punktVon = id=>PUNKT[id] || ['•', '', ''];
  const symbolVon = id=>punktVon(id)[0];
  const titelVonPunkt = id=>T(punktVon(id)[1]);
  const satzVon = id=>T(punktVon(id)[2]);

  // zuletzt geöffnete Punkte (nur im Browser, nur die IDs)
  function zuletzt(){ try{ const a = JSON.parse(localStorage.getItem(ZULETZT_KEY) || '[]'); return Array.isArray(a) ? a.filter(x=>typeof x === 'string') : []; }catch(_e){ return []; } }
  function zuletztMerken(id){
    if(!PUNKT[id]) return;
    try{ localStorage.setItem(ZULETZT_KEY, JSON.stringify([id].concat(zuletzt().filter(x=>x !== id)).slice(0, ZULETZT_MAX))); }catch(_e){}
  }

  // eine Reihe wie in den Windows-Einstellungen: Symbol, Titel mit Satz, Pfeil
  function reihe(symbol, titel, satz, tun){
    const b = d().el('button', 'hs-einst-reihe'); b.type = 'button';
    const text = d().el('span', 'hs-einst-reihe-text'); text.append(d().el('b', null, titel), d().el('small', 'hs-leise', satz || ''));
    b.append(d().el('span', 'hs-einst-reihe-symbol', symbol), text, d().el('span', 'hs-einst-pfeil', '›'));
    b.onclick = tun;
    return b;
  }
  function kachel(titel, satz){
    const k = d().el('section', 'hs-einst-kachel');
    k.append(d().el('h3', 'hs-einst-kachel-titel', titel));
    if(satz) k.append(d().el('p', 'hs-leise hs-einst-kachel-satz', satz));
    return k;
  }
  function wert(label, text, ton){
    const z = d().el('div', 'hs-einst-wertzeile');
    z.append(d().el('span', 'hs-leise', label), d().el('b', 'hs-einst-wert' + (ton ? ' ' + ton : ''), text));
    return z;
  }

  function gruppenseite(S, seite, gruppe, gehe){
    seite.append(d().el('h2', 'hs-einst-titel', typeof gruppe.titel === 'function' ? gruppe.titel() : gruppe.titel));
    const liste = d().el('div', 'hs-einst-reihen');
    Object.keys(gruppe.punkte).forEach(pid=>{
      const id = gruppe.id + '/' + pid;
      const r = reihe(symbolVon(id), titelVonPunkt(id), satzVon(id), ()=>gehe(id));
      r.dataset.punkt = id; liste.append(r);
    });
    seite.append(liste);
  }

  // die Startseite: oben der Stand in einer Zeile, darunter links zuletzt benutzt und Modelle, rechts die Kacheln KI-Labor, Token und Freigaben
  function startseite(S, seite, gruppen, gehe){
    seite.append(d().el('h2', 'hs-einst-titel', T('es_startseite')));
    const kopf = d().el('div', 'hs-einst-gerat');
    const name = d().el('div', 'hs-einst-gerat-name'); name.append(d().el('b', null, 'One Sedra'), d().el('small', 'hs-leise', T('es_captain') + ' · ' + (S.modell ? T('es_modell') + ' ' + (S.modell.name || S.modell) : T('es_kein_modell_geladen'))));
    const chips = d().el('div', 'hs-einst-chips');
    kopf.append(name, chips);
    seite.append(kopf);

    const raster = d().el('div', 'hs-einst-startraster');
    const links = d().el('div', 'hs-einst-spalte'), rechts = d().el('div', 'hs-einst-spalte');
    raster.append(links, rechts); seite.append(raster);

    // Empfohlen: zuletzt geöffnet, aufgefüllt mit den Punkten, die man am häufigsten braucht
    const empf = kachel(T('es_empfohlen'), T('es_empfohlen_satz'));
    const liste = d().el('div', 'hs-einst-reihen eng');
    const ids = zuletzt().concat(['agent/freigabe', 'agent/token', 'modelle/werkstatt', 'integrationen/cloud']).filter((x, i, a)=>PUNKT[x] && a.indexOf(x) === i).slice(0, 3);
    ids.forEach(id=>{
      const g = gruppen.find(x=>x.id === id.split('/')[0]); if(!g || !g.punkte[id.split('/')[1]]) return;
      const r = reihe(symbolVon(id), titelVonPunkt(id), g.titel, ()=>gehe(id)); r.dataset.punkt = id; liste.append(r);
    });
    empf.append(liste); links.append(empf);

    const modelle = kachel(T('es_lokale_modelle'), T('es_lokale_modelle_satz'));
    const mWerte = d().el('div', 'hs-einst-werte'); modelle.append(mWerte, d().button(T('es_werkstatt_oeffnen'), ()=>gehe('modelle/werkstatt')));
    links.append(modelle);

    const labor = kachel(T('es_ki_labor'), T('es_ki_labor_satz'));
    const lWerte = d().el('div', 'hs-einst-werte'); labor.append(lWerte, d().button(T('es_ki_labor_oeffnen'), ()=>gehe('integrationen/cloud')));
    rechts.append(labor);

    const token = kachel(T('es_sedra_token'), T('es_sedra_token_satz'));
    const tWerte = d().el('div', 'hs-einst-werte'); token.append(tWerte, d().button(T('es_sedra_token_oeffnen'), ()=>root.sedraHarness.tokenseite.oeffnen(S)));
    rechts.append(token);

    // Daten: alles lesend, jede Kachel für sich – fällt eine aus, bleiben die anderen
    const zahl = n=>Number(n || 0).toLocaleString('de-DE');
    const heute = ()=>{
      const t = S.tokenStand && S.tokenStand.heute;
      tWerte.replaceChildren(...(t ? [wert(T('es_antworten'), zahl(t.antworten)), wert(T('es_eingehend'), zahl(t.ein)), wert(T('es_erzeugt'), zahl(t.aus)), wert(T('es_tempo'), t.tok_s ? t.tok_s + ' Token/s' : '–')] : [wert(T('es_stand'), T('es_noch_nicht_geladen'))]));
    };
    heute();
    if(S.tokenLaden) Promise.resolve(S.tokenLaden()).then(heute, ()=>{});
    S.api('/api/strip').then(v=>{
      const g = k=>(v && v[k]) || {};
      mWerte.replaceChildren(wert(T('es_modell'), String(g('model').value ?? '–'), g('model').tone), wert(T('es_gpu'), String(g('gpu').value ?? '–'), g('gpu').tone), wert(T('es_ram'), String(g('ram').value ?? '–'), g('ram').tone), wert(T('es_modellserver'), String(g('server').value ?? '–'), g('server').tone));
      [['decisions', T('es_freigaben')], ['state', T('es_zustand')], ['scheduler', T('es_scheduler')]].forEach(([k, label])=>{
        if(!g(k).value && g(k).value !== 0) return;
        const c = d().el('div', 'hs-einst-chip ' + (g(k).tone || 'off')); c.append(d().el('b', null, label), d().el('small', 'hs-leise', String(g(k).value))); chips.append(c);
      });
    }).catch(err=>mWerte.replaceChildren(wert(T('es_stand'), T('es_nicht_lesbar') + ': ' + err.message, 'bad')));
    S.api('/api/cloud').then(c=>{
      const p = c.providers || [], bereit = p.filter(x=>x.status === 'bereit').length;
      lWerte.replaceChildren(wert(T('es_cloud'), c.enabled ? T('es_eingeschaltet') : T('es_aus'), c.enabled ? 'ok' : ''), wert(T('es_anbieter_bereit'), bereit + ' ' + T('es_von') + ' ' + p.length), wert(T('es_im_server_aktiv'), (c.live || []).join(', ') || T('es_keiner')));
    }).catch(err=>lWerte.replaceChildren(wert(T('es_stand'), T('es_nicht_lesbar') + ': ' + err.message, 'bad')));
  }

  // Suche über Titel, Satz und Gruppe aller Punkte
  function suchen(gruppen, text){
    const q = String(text || '').toLowerCase().trim();
    if(!q) return [];
    const out = [];
    gruppen.forEach(g=>Object.keys(g.punkte).forEach(pid=>{
      const id = g.id + '/' + pid, titel = titelVonPunkt(id);
      if((titel + ' ' + satzVon(id) + ' ' + g.titel).toLowerCase().indexOf(q) >= 0) out.push({id, titel, gruppe: g.titel});
    }));
    return out;
  }
  function trefferSeite(seite, gruppen, text, gehe){
    seite.append(d().el('h2', 'hs-einst-titel', T('es_suche') + text));
    const liste = d().el('div', 'hs-einst-reihen');
    const t = suchen(gruppen, text);
    t.forEach(x=>{ const r = reihe(symbolVon(x.id), x.titel, x.gruppe + ' · ' + satzVon(x.id), ()=>gehe(x.id)); r.dataset.punkt = x.id; liste.append(r); });
    if(!t.length) liste.append(d().el('div', 'hs-app-satz', T('es_keine_einstellung_gefunden')));
    seite.append(liste);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.einstSeiten = {SYMBOL, PUNKT, symbolVon, satzVon, zuletzt, zuletztMerken, reihe, gruppenseite, startseite, suchen, trefferSeite};
  if(typeof module !== 'undefined' && module.exports) module.exports = {PUNKT, SYMBOL, suchen};
})();
