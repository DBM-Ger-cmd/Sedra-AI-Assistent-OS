// Harness-Shell – die Seiten der Einstellungen im Stil der Windows-Einstellungen (Captain 03.11.2026, Referenzbilder): Startseite mit Kacheln und Stand,
// Gruppenseiten als Liste von Reihen (Symbol, Titel, Satz, Pfeil), Suche über alle Punkte. Rein darstellend: die Punkte selbst zeichnet einstellungen.js.
// Daten nur lesend (/api/strip, /api/cloud, S.tokenStand); ein Schlüssel oder ein Token steht nie auf diesen Seiten. Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const H = ()=>root.sedraHarness;
  const ZULETZT_KEY = 'sedra.harness.einstellungen.zuletzt';
  const ZULETZT_MAX = 4;
  const SYMBOL = {start: '⌂', allgemein: '◐', agent: '✦', sprache: '♪', integrationen: '⇄', modelle: '◆', system: '⚙'};
  // Symbol und ein Satz je Punkt – das, was in der Reihe unter dem Titel steht
  const PUNKT = {
    'allgemein/darstellung': ['◐', 'Klar oder Nacht, Schriftgröße'],
    'allgemein/benachrichtigungen': ['⚑', 'Hinweis im Browser und Blinken in der Taskleiste, wenn eine Freigabe wartet'],
    'allgemein/sprache': ['A', 'Sprache der Oberfläche'],
    'agent/vorlagen': ['▤', 'Bauagent, Vorarbeiter, Modellierer, Prüfer, MasterChat'],
    'agent/freigabe': ['⛨', 'Katalog der Regeln und Erlaubnisse dieser Sitzungen'],
    'agent/grenzen': ['↻', 'Züge der Schleife je Vorlage (Antrag mit Gate)'],
    'agent/token': ['◎', 'Verweis auf die App Sedra Token: Verbrauch, Denken, Antwortbudget, Gedächtnis'],
    'sprache/rekorder': ['●', 'Aufnehmen, abspielen, Sprache zu Text'],
    'sprache/quelle': ['♪', 'Welcher Anbieter Sprache zu Text liefert'],
    'integrationen/mcp': ['⇄', 'Clients, Port und Alter der Datei – nie der Token'],
    'integrationen/gateway': ['⛨', 'KI GateWay mit Guard und Inhaltsschutz: Anfrage prüfen, Entwurf, Prüfung'],
    'integrationen/cloud': ['☁', 'KI-Labor: Anbieter, Schlüssel, Modelle, Tests'],
    'modelle/bibliothek': ['▣', 'Skills ansehen und schreiben'],
    'modelle/werkstatt': ['◆', 'Modelle laden, Rezepte, Teststrecke'],
    'modelle/slots': ['▦', 'Belegte Plätze und Warteschlange'],
    'modelle/laufzeit': ['⚙', 'Geladene Instanzen, Server, Kontext'],
    'system/schalter': ['⏻', 'Schalter aus local_switches (Antrag mit Gate)'],
    'system/grenzen': ['⊘', 'Projekt, Netz, Löschen, Kosten'],
    'system/module': ['▦', 'Shell, Werkzeuge, Vorlagen'],
    'system/audit': ['☰', 'Audit-Kette und Verlauf']
  };
  const symbolVon = id=>(PUNKT[id] || ['•', ''])[0];
  const satzVon = id=>(PUNKT[id] || ['', ''])[1];

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
    seite.append(d().el('h2', 'hs-einst-titel', gruppe.titel));
    const liste = d().el('div', 'hs-einst-reihen');
    Object.keys(gruppe.punkte).forEach(pid=>{
      const id = gruppe.id + '/' + pid;
      const r = reihe(symbolVon(id), gruppe.punkte[pid].titel, satzVon(id), ()=>gehe(id));
      r.dataset.punkt = id; liste.append(r);
    });
    seite.append(liste);
  }

  // die Startseite: oben der Stand in einer Zeile, darunter links zuletzt benutzt und Modelle, rechts die Kacheln KI-Labor, Token und Freigaben
  function startseite(S, seite, gruppen, gehe){
    seite.append(d().el('h2', 'hs-einst-titel', 'Startseite'));
    const kopf = d().el('div', 'hs-einst-gerat');
    const name = d().el('div', 'hs-einst-gerat-name'); name.append(d().el('b', null, 'SEDRA · Harness'), d().el('small', 'hs-leise', 'Captain · ' + (S.modell ? 'Modell ' + (S.modell.name || S.modell) : 'kein Modell geladen')));
    const chips = d().el('div', 'hs-einst-chips');
    kopf.append(name, chips);
    seite.append(kopf);

    const raster = d().el('div', 'hs-einst-startraster');
    const links = d().el('div', 'hs-einst-spalte'), rechts = d().el('div', 'hs-einst-spalte');
    raster.append(links, rechts); seite.append(raster);

    // Empfohlen: zuletzt geöffnet, aufgefüllt mit den Punkten, die man am häufigsten braucht
    const empf = kachel('Empfohlene Einstellungen', 'Zuletzt und häufig verwendet');
    const liste = d().el('div', 'hs-einst-reihen eng');
    const ids = zuletzt().concat(['agent/freigabe', 'agent/token', 'modelle/werkstatt', 'integrationen/cloud']).filter((x, i, a)=>PUNKT[x] && a.indexOf(x) === i).slice(0, 3);
    ids.forEach(id=>{
      const g = gruppen.find(x=>x.id === id.split('/')[0]); if(!g || !g.punkte[id.split('/')[1]]) return;
      const r = reihe(symbolVon(id), g.punkte[id.split('/')[1]].titel, g.titel, ()=>gehe(id)); r.dataset.punkt = id; liste.append(r);
    });
    empf.append(liste); links.append(empf);

    const modelle = kachel('Lokale Modelle', 'Stand dieses Rechners');
    const mWerte = d().el('div', 'hs-einst-werte'); modelle.append(mWerte, d().button('Werkstatt öffnen', ()=>gehe('modelle/werkstatt')));
    links.append(modelle);

    const labor = kachel('KI-Labor', 'Cloud-Anbieter, Schlüssel, Modelle');
    const lWerte = d().el('div', 'hs-einst-werte'); labor.append(lWerte, d().button('KI-Labor öffnen', ()=>gehe('integrationen/cloud')));
    rechts.append(labor);

    const token = kachel('Sedra Token', 'Verbrauch heute');
    const tWerte = d().el('div', 'hs-einst-werte'); token.append(tWerte, d().button('Sedra Token öffnen', ()=>root.sedraHarness.tokenseite.oeffnen(S)));
    rechts.append(token);

    // Daten: alles lesend, jede Kachel für sich – fällt eine aus, bleiben die anderen
    const zahl = n=>Number(n || 0).toLocaleString('de-DE');
    const heute = ()=>{
      const t = S.tokenStand && S.tokenStand.heute;
      tWerte.replaceChildren(...(t ? [wert('Antworten', zahl(t.antworten)), wert('Eingehend ↑', zahl(t.ein)), wert('Erzeugt ↓', zahl(t.aus)), wert('Tempo', t.tok_s ? t.tok_s + ' Token/s' : '–')] : [wert('Stand', 'noch nicht geladen')]));
    };
    heute();
    if(S.tokenLaden) Promise.resolve(S.tokenLaden()).then(heute, ()=>{});
    S.api('/api/strip').then(v=>{
      const g = k=>(v && v[k]) || {};
      mWerte.replaceChildren(wert('Modell', String(g('model').value ?? '–'), g('model').tone), wert('GPU', String(g('gpu').value ?? '–'), g('gpu').tone), wert('RAM', String(g('ram').value ?? '–'), g('ram').tone), wert('Modellserver', String(g('server').value ?? '–'), g('server').tone));
      [['decisions', 'Freigaben'], ['state', 'Zustand'], ['scheduler', 'Scheduler']].forEach(([k, label])=>{
        if(!g(k).value && g(k).value !== 0) return;
        const c = d().el('div', 'hs-einst-chip ' + (g(k).tone || 'off')); c.append(d().el('b', null, label), d().el('small', 'hs-leise', String(g(k).value))); chips.append(c);
      });
    }).catch(err=>mWerte.replaceChildren(wert('Stand', 'nicht lesbar: ' + err.message, 'bad')));
    S.api('/api/cloud').then(c=>{
      const p = c.providers || [], bereit = p.filter(x=>x.status === 'bereit').length;
      lWerte.replaceChildren(wert('Cloud', c.enabled ? 'eingeschaltet' : 'aus', c.enabled ? 'ok' : ''), wert('Anbieter bereit', bereit + ' von ' + p.length), wert('Im Server aktiv', (c.live || []).join(', ') || 'keiner'));
    }).catch(err=>lWerte.replaceChildren(wert('Stand', 'nicht lesbar: ' + err.message, 'bad')));
  }

  // Suche über Titel, Satz und Gruppe aller Punkte
  function suchen(gruppen, text){
    const q = String(text || '').toLowerCase().trim();
    if(!q) return [];
    const out = [];
    gruppen.forEach(g=>Object.keys(g.punkte).forEach(pid=>{
      const id = g.id + '/' + pid, titel = g.punkte[pid].titel;
      if((titel + ' ' + satzVon(id) + ' ' + g.titel).toLowerCase().indexOf(q) >= 0) out.push({id, titel, gruppe: g.titel});
    }));
    return out;
  }
  function trefferSeite(seite, gruppen, text, gehe){
    seite.append(d().el('h2', 'hs-einst-titel', 'Suche: ' + text));
    const liste = d().el('div', 'hs-einst-reihen');
    const t = suchen(gruppen, text);
    t.forEach(x=>{ const r = reihe(symbolVon(x.id), x.titel, x.gruppe + ' · ' + satzVon(x.id), ()=>gehe(x.id)); r.dataset.punkt = x.id; liste.append(r); });
    if(!t.length) liste.append(d().el('div', 'hs-app-satz', 'Keine Einstellung gefunden.'));
    seite.append(liste);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.einstSeiten = {SYMBOL, PUNKT, symbolVon, satzVon, zuletzt, zuletztMerken, reihe, gruppenseite, startseite, suchen, trefferSeite};
  if(typeof module !== 'undefined' && module.exports) module.exports = {PUNKT, SYMBOL, suchen};
})();
