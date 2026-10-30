// Harness-Shell Stufe 5 – die Einstellungen (SPEC_HARNESS_SHELL_v1 HS-42; G2 Stufe 5 §3, D-U1 bis D-U7; G3 N5).
//
// Ein Reiter `einstellungen:` (höchstens einer; `einstellungen:<gruppe>/<punkt>` wählt den Punkt). Links die Navigation (sechs Gruppen),
// rechts die Fläche. Die meisten Punkte sind **vorhandene Werkzeuge**, eingehängt über `app.flaeche` (derselbe Code wie der App-Reiter:
// forObject → makeContext → mountTool, Werkbank-Zeile) – kein Nachbau (D-U1). Eigene Flächen gibt es nur für Darstellung,
// Benachrichtigungen (K9), Sprache, Vorlagen, Freigabe-Modus (→ katalog_editor.js), Grenzen (Antrag mit Gate, D-U4), Quelle, MCP,
// Laufzeit und Schalter (Antrag mit Gate, wie im Werkzeug Modelle). Nichts hier schreibt ohne Gate auf den Rechner (§3.2); im Browser
// bleibt nur der gewählte Punkt und die Wahl der Benachrichtigung (Komfort).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const H = ()=>root.sedraHarness;
  const KEY = 'sedra.harness.einstellungen';
  const MELDE_KEY = 'sedra.harness.benachrichtigung';
  const ID = 'einstellungen:';
  const W = (ort, nur, titel)=>({art: 'werkzeug', ort, nur, titel});
  const E = (flaeche, titel)=>({art: 'eigen', flaeche, titel});
  // G2 §3.1 – sechs Gruppen, 21 Punkte; `ort` ist die ID aus ui/places.js (dasselbe Objekt wie im Start-Menü)
  const GRUPPEN = [
    {id: 'allgemein', titel: 'Allgemein', punkte: {darstellung: E('darstellung', 'Darstellung'), benachrichtigungen: E('benachrichtigungen', 'Benachrichtigungen'), sprache: E('sprache', 'Sprache der Oberfläche')}},
    {id: 'agent', titel: 'Agent', punkte: {vorlagen: E('vorlagen', 'Vorlagen'), freigabe: E('freigabe', 'Freigabe-Modus'), grenzen: E('grenzen', 'Grenzen der Schleife')}},
    {id: 'sprache', titel: 'Sprache', punkte: {rekorder: W('aufnahme', ['rekorder'], 'Rekorder'), quelle: E('quelle', 'Quelle')}},
    {id: 'integrationen', titel: 'Integrationen', punkte: {mcp: E('mcp', 'MCP'), gateway: W('gateway', ['gateway', 'schutz'], 'KI GateWay'), cloud: W('labor', ['labor'], 'Cloud')}},
    {id: 'modelle', titel: 'Lokale Modelle', punkte: {bibliothek: W('library', ['library'], 'Bibliothek'), werkstatt: W('models', ['workshop'], 'Rezepte / Werkstatt'), slots: W('slots', ['slots'], 'Slots'), laufzeit: E('laufzeit', 'Geladene Instanzen · Laufzeit')}},
    {id: 'system', titel: 'System', punkte: {schutz: W('gateway', ['schutz'], 'Guard / Inhaltsschutz'), schalter: E('schalter', 'Schalter'), grenzen: W('boundary', ['boundaries'], 'Modus und Grenzen'), module: W('modules', ['modules'], 'Module'), audit: W('logbook', ['logbook'], 'Audit')}}
  ];

  function stand(S){ return S._einst || (S._einst = {wahl: null, ansicht: null}); }
  function gemerkt(){ try{ return localStorage.getItem(KEY) || ''; }catch(_e){ return ''; } }
  function merken(punkt){ try{ localStorage.setItem(KEY, punkt); }catch(_e){} }
  function zerlegen(punkt){
    const [g, p] = String(punkt || '').split('/');
    const gruppe = GRUPPEN.find(x=>x.id === g) || GRUPPEN[0];
    const pid = gruppe.punkte[p] ? p : Object.keys(gruppe.punkte)[0];
    return {gruppe, pid, punkt: gruppe.punkte[pid], id: gruppe.id + '/' + pid};
  }

  // ---- öffnen: Seitenleiste, Start-Menü (System → Einstellungen), /einstellungen, Zelle Zustand (D-U6), Reiter-ID mit Punkt
  function oeffnen(S, punkt){
    const st = stand(S);
    const wahl = zerlegen(punkt || st.wahl || gemerkt() || 'allgemein/darstellung').id;
    st.wahl = wahl; merken(wahl);
    H().reiter.aktivieren(S, ID);
    if(st.ansicht) st.ansicht.zeigen(wahl);
    return ID;
  }
  function istReiter(id){ return String(id).startsWith(ID); }

  // ---- die Ansicht (S.zeigen → verlauf.ansicht → hier)
  function ansicht(S, id){
    const st = stand(S);
    const box = d().el('div', 'hs-verlauf hs-einst');
    const nav = d().el('nav', 'hs-einst-nav'); nav.setAttribute('aria-label', 'Einstellungen');
    const flaeche = d().el('section', 'hs-einst-flaeche');
    box.append(nav, flaeche);
    let offen = null;
    const a = {id, box, S, leer: ()=>false, laeuft: ()=>false, nachUnten(){}, stoppen(){}, senden: async ()=>false,
               abbauen(){ if(offen && offen.abbauen) offen.abbauen(); offen = null; st.ansicht = null; },
               zeigen(punkt){
                 const w = zerlegen(punkt); st.wahl = w.id; merken(w.id);
                 if(offen && offen.abbauen) offen.abbauen();
                 flaeche.replaceChildren();
                 const kopf = d().el('div', 'hs-einst-kopf'); kopf.append(d().el('small', 'hs-leise', w.gruppe.titel), d().el('b', null, w.punkt.titel));
                 flaeche.append(kopf);
                 offen = w.punkt.art === 'werkzeug' ? werkzeug(S, flaeche, w.punkt) : eigen(S, flaeche, w.punkt);
                 navZeichnen();
               }};
    const navZeichnen = ()=>{
      nav.replaceChildren(...GRUPPEN.map(g=>{
        const sec = d().el('section', 'hs-einst-gruppe'); sec.append(d().el('div', 'hs-ueber', g.titel));
        Object.keys(g.punkte).forEach(pid=>{
          const k = d().el('button', 'hs-einst-punkt' + (st.wahl === g.id + '/' + pid ? ' on' : ''), g.punkte[pid].titel); k.type = 'button';
          k.dataset.punkt = g.id + '/' + pid; k.setAttribute('aria-current', st.wahl === g.id + '/' + pid ? 'page' : 'false');
          k.onclick = ()=>a.zeigen(g.id + '/' + pid);
          sec.append(k);
        });
        return sec;
      }));
    };
    st.ansicht = a;
    const start = id.length > ID.length ? id.slice(ID.length) : null;
    a.zeigen(start || st.wahl || gemerkt() || 'allgemein/darstellung');
    return a;
  }

  // Ein Werkzeug des Vertrags – das Objekt des Ortes aus places.js, eingehängt wie im App-Reiter (nur die genannten Werkzeuge)
  function werkzeug(S, flaeche, punkt){
    const ort = root.sedraPlaces.PLACES.find(p=>p.id === punkt.ort);
    if(!ort){ flaeche.append(d().el('div', 'hs-app-satz warn', 'Der Ort „' + punkt.ort + '“ ist nicht bekannt.')); return null; }
    const f = H().app.flaeche(S, Object.assign({}, ort.object), punkt.nur);
    const box = d().el('div', 'hs-app-box hs-einst-werkzeug' + (f.rechts.length ? ' nachweis-auf' : '') + (f.rechts.length && !f.links.length ? ' nur-nachweis' : ''));
    box.append(f.verben, f.koerper);
    flaeche.append(box);
    return f;
  }

  // ---- eigene Flächen
  const FLAECHEN = {darstellung, benachrichtigungen, sprache, vorlagen, freigabe, grenzen, quelle, mcp, laufzeit, schalter};
  function eigen(S, flaeche, punkt){
    const box = d().el('div', 'hs-einst-eigen'); box.dataset.flaeche = punkt.flaeche;
    flaeche.append(box);
    const r = {abbauen(){}};
    try{ const out = FLAECHEN[punkt.flaeche](S, box); if(out && out.abbauen) r.abbauen = out.abbauen; }
    catch(err){ box.append(d().el('div', 'hs-app-satz warn', 'Die Fläche ließ sich nicht zeichnen: ' + err.message)); }
    return r;
  }
  function zeile(box, label, wert, hinweis){
    const z = d().el('div', 'hs-einst-zeile'); z.append(d().el('span', 'hs-einst-label', label), d().el('span', 'hs-einst-wert', wert));
    if(hinweis) z.append(d().el('small', 'hs-leise', hinweis));
    box.append(z); return z;
  }
  function seg(box, titel, optionen, aktuell, tun){
    const g = d().el('div', 'hs-einst-zeile'); g.setAttribute('role', 'group'); g.setAttribute('aria-label', titel);
    g.append(d().el('span', 'hs-einst-label', titel));
    const knoepfe = d().el('span', 'hs-start-seg');
    optionen.forEach(([id, label])=>{
      const b = d().el('button', 'hs-start-seg-btn' + (id === aktuell ? ' on' : ''), label); b.type = 'button'; b.setAttribute('aria-pressed', id === aktuell ? 'true' : 'false');
      b.onclick = ()=>{ tun(id); knoepfe.querySelectorAll('button').forEach(x=>{ const on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-pressed', on ? 'true' : 'false'); }); };
      knoepfe.append(b);
    });
    g.append(knoepfe); box.append(g);
  }
  function antraege(S, box, kind, text){                 // §3.2: offene Anträge stehen im Posteingang und als Hinweis auf der Seite
    const satz = d().el('div', 'hs-app-satz hs-einst-antrag'); satz.hidden = true; box.append(satz);
    const laden = ()=>S.api('/api/decisions').then(e=>{
      const offen = (e.items || []).filter(x=>x.kind === 'request:' + kind);
      satz.hidden = !offen.length;
      satz.textContent = offen.length ? offen.length + (offen.length === 1 ? ' Antrag offen – ' : ' Anträge offen – ') + text + ' Entscheidung im Posteingang (Freigaben).' : '';
    }).catch(()=>{});
    laden();
    return laden;
  }

  function darstellung(S, box){
    seg(box, 'Darstellung', [['klar', 'Klar'], ['nacht', 'Nacht']], document.documentElement.dataset.theme || 'nacht', v=>root.sedraBoot.setTheme(v));
    seg(box, 'Schrift', [['normal', 'Normal'], ['gross', 'Groß']], document.documentElement.dataset.scale || 'normal', v=>root.sedraWechsel.setScale(v));
    const k = d().button('Start-Menü: Oberflächen und Gedächtnis', ()=>H().startmenue.oeffnen(S));
    box.append(k, d().el('div', 'hs-app-satz', 'Dieselben Schalter wie im Start-Menü – gemerkt im Browser, nicht auf dem Rechner.'));
  }

  // K9 (D-U7): Browser-Hinweis „SEDRA: eine Freigabe wartet“, wenn das Fenster nicht vorn ist; Erlaubnis nur nach Klick; nie der Karteninhalt
  function meldung(){ try{ return Object.assign({browser: false, blinken: true}, JSON.parse(localStorage.getItem(MELDE_KEY) || '{}')); }catch(_e){ return {browser: false, blinken: true}; } }
  function meldungSetzen(teil){ try{ localStorage.setItem(MELDE_KEY, JSON.stringify(Object.assign(meldung(), teil))); }catch(_e){} }
  function benachrichtigen(S){
    const m = meldung();
    if(!m.browser || typeof Notification === 'undefined' || Notification.permission !== 'granted') return false;
    if(document.visibilityState === 'visible' && document.hasFocus()) return false;
    try{ const n = new Notification('SEDRA: eine Freigabe wartet', {body: 'Im Posteingang der Harness-Shell.', tag: 'sedra-freigabe'}); n.onclick = ()=>{ root.focus(); n.close(); }; return true; }
    catch(_e){ return false; }
  }
  function benachrichtigungen(S, box){
    const m = meldung();
    const erlaubnis = ()=>typeof Notification === 'undefined' ? 'vom Browser nicht unterstützt' : Notification.permission;
    const z = d().el('div', 'hs-einst-zeile');
    const sch = d().el('input'); sch.type = 'checkbox'; sch.checked = !!m.browser; sch.id = 'hs-einst-melden';
    const lab = d().el('label', 'hs-einst-label', 'Browser-Hinweis, wenn eine Freigabe wartet und das Fenster nicht vorn ist'); lab.htmlFor = sch.id;
    const st = d().el('small', 'hs-leise', 'Erlaubnis: ' + erlaubnis());
    sch.onchange = async ()=>{
      if(sch.checked && typeof Notification !== 'undefined' && Notification.permission === 'default'){
        try{ await Notification.requestPermission(); }catch(_e){}                   // nur nach Klick (K9)
      }
      meldungSetzen({browser: sch.checked}); st.textContent = 'Erlaubnis: ' + erlaubnis();
      if(sch.checked && typeof Notification !== 'undefined' && Notification.permission !== 'granted') S.hinweis('Der Browser hat die Benachrichtigung nicht erlaubt.', 'warn');
    };
    z.append(sch, lab, st); box.append(z);
    const z2 = d().el('div', 'hs-einst-zeile');
    const bl = d().el('input'); bl.type = 'checkbox'; bl.checked = m.blinken !== false; bl.id = 'hs-einst-blinken';
    const lab2 = d().el('label', 'hs-einst-label', 'Neue Freigaben blinken in der Taskleiste (HS-33)'); lab2.htmlFor = bl.id;
    bl.onchange = ()=>meldungSetzen({blinken: bl.checked});
    z2.append(bl, lab2); box.append(z2);
    box.append(d().el('div', 'hs-app-satz', 'Der Hinweis sagt nur „eine Freigabe wartet“ – nie, worum es geht. Gemerkt je Browser.'));
  }

  function sprache(S, box){ zeile(box, 'Sprache der Oberfläche', 'Deutsch', 'Es gibt keine zweite.'); }

  function vorlagen(S, box){
    (S.vorlagen || []).forEach(v=>{
      const k = d().el('details', 'hs-einst-karte'); const s = d().el('summary'); s.append(d().el('b', null, v.name || v.id), d().el('small', 'hs-leise', ' · ' + v.id + ' · ' + (v.quelle === 'local_config' ? 'Datei des Captains' : 'Repo')));
      k.append(s);
      if(v.fehler){ k.append(d().el('div', 'hs-app-satz warn', v.fehler)); box.append(k); return; }
      zeile(k, 'Beschreibung', v.beschreibung || '–'); zeile(k, 'Werkzeuge', (v.werkzeuge || []).join(', ') || '–');
      zeile(k, 'Rechte', Object.keys(v.rechte || {}).filter(r=>v.rechte[r]).join(', ') || 'keine'); zeile(k, 'Modell', v.modell || 'das geladene'); zeile(k, 'max_zuege', String(v.max_zuege));
      box.append(k);
    });
    if(!(S.vorlagen || []).length) box.append(d().el('div', 'hs-app-satz', 'Keine Vorlage gefunden (runtime/config/harness_vorlagen).'));
    box.append(d().el('div', 'hs-app-satz', 'Der Systemtext (.md) liegt neben der Vorlage; die Grenzen stehen unter „Grenzen der Schleife“.'));
  }

  function freigabe(S, box){ return H().katalogEditor.flaeche(S, box); }

  // D-U4: max_zuege je Vorlage → Antrag mit Gate; max_tokens/temperature nur Anzeige
  function grenzen(S, box){
    const nach = antraege(S, box, 'harness_vorlage', 'die Kopie der Vorlage entsteht erst mit der');
    (S.vorlagen || []).filter(v=>!v.fehler).forEach(v=>{
      const z = d().el('div', 'hs-einst-zeile'); z.dataset.vorlage = v.id;
      const feld = d().el('input', 'hs-einst-zahl'); feld.type = 'number'; feld.min = 4; feld.max = 40; feld.value = v.max_zuege; feld.setAttribute('aria-label', 'max_zuege ' + v.id);
      const k = d().button('Antrag stellen', async ()=>{
        const n = Number(feld.value);
        if(!Number.isInteger(n) || n < 4 || n > 40){ S.hinweis('max_zuege: 4 bis 40.', 'warn'); return; }
        await S.api('/api/harness/vorlagen/grenzen', {method: 'POST', body: {vorlage: v.id, max_zuege: n}});
        S.hinweis('Antrag gestellt – Freigabe im Posteingang.'); nach();
      });
      z.append(d().el('span', 'hs-einst-label', (v.name || v.id) + ' · max_zuege'), feld, d().el('small', 'hs-leise', v.quelle === 'local_config' ? 'Kopie des Captains' : 'Repo'), k);
      box.append(z);
    });
    zeile(box, 'max_tokens · temperature', 'aus dem Code der Schleife', 'Messwerte der Modelle, keine Einstellung des Captains (K4).');
  }

  function quelle(S, box){
    S.api('/api/sprache/status').then(st=>{
      const p = st.stt || {};
      zeile(box, 'Sprache → Text', p.name || p.provider || p.id || (p.vorhanden === false ? 'kein Provider' : '–'), p.grund || p.hinweis || '');
      zeile(box, 'Sprachen', (st.sprachen || []).join(', ') || '–'); zeile(box, 'Läuft', (st.laeuft || []).join(', ') || 'nichts');
      box.append(d().el('div', 'hs-app-satz', 'Eine Wahl der Quelle gibt es im Kern nicht (K8) – nur die Anzeige.'));
    }).catch(err=>box.append(d().el('div', 'hs-app-satz warn', 'Sprache: ' + err.message)));
  }

  function mcp(S, box){
    S.api('/api/uix/clients').then(out=>{
      Object.keys(out.clients || {}).forEach(c=>{
        const i = out.clients[c];
        zeile(box, c.toUpperCase(), i.vorhanden ? 'vorhanden · Port ' + i.port + ' · PID ' + i.pid : 'keine Datei', i.vorhanden && i.zeit ? 'seit ' + d().fmtTime(new Date(i.zeit * 1000).toISOString()) + ' · ' + i.schutz : '');
      });
      zeile(box, 'Ordner', out.ordner || '–', 'der Token steht nur in der Datei, nie hier');
      box.append(d().el('div', 'hs-app-satz', 'Aufruf: python -m guppi_runtime.desk_mcp (Client „mcp“), die CLI nimmt „cli“. Zu konfigurieren gibt es nichts (K7).'));
    }).catch(err=>box.append(d().el('div', 'hs-app-satz warn', 'Clients: ' + err.message)));
  }

  function laufzeit(S, box){
    S.api('/api/models').then(m=>{
      const s = m.server || {};
      zeile(box, 'Modellserver', s.running ? 'läuft · ' + (s.model || '?') : 'aus', s.endpoint || '');
      zeile(box, 'Kontext', s.context ? d().fmtNumber(s.context) + ' Token' : '–'); zeile(box, 'Slots', s.slots !== undefined ? String(s.slots) : '–');
      zeile(box, 'Engine', s.engine_build || '–', s.engine_check && s.engine_check !== 'ok' ? 'Prüfung: ' + s.engine_check : (s.engine_check ? 'Prüfung ok' : ''));
      const geladen = (m.recipes || []).filter(r=>r.loaded);
      zeile(box, 'Geladene Rezepte', geladen.map(r=>r.id).join(', ') || 'keines');
      if(m.lease) zeile(box, 'GPU-Lease', (m.lease.owner || '?') + (m.lease.purpose ? ' · ' + m.lease.purpose : ''), m.lease.stale ? 'veraltet' : '');
    }).catch(err=>box.append(d().el('div', 'hs-app-satz warn', 'Modelle: ' + err.message)));
  }

  // K5: dieselben zwei Wege wie im Werkzeug Modelle – switch_request legt den Antrag an, das Gate entscheidet der Captain
  function schalter(S, box){
    const nach = antraege(S, box, 'switch', 'wirkt erst nach Neustart der Oberfläche;');
    S.api('/api/switches').then(v=>{
      if(v.error) box.append(d().el('div', 'hs-app-satz warn', 'Schalter: ' + v.error));
      if(v.restart_needed) box.append(d().el('div', 'hs-app-satz warn', 'Ein Schalter wurde geändert – wirkt erst nach Neustart der SEDRA-Oberfläche.'));
      (v.items || []).forEach(it=>{
        const z = d().el('div', 'hs-einst-zeile'); z.dataset.schalter = it.section + '.' + it.key;
        const k = d().button(it.value ? 'Ausschalten beantragen' : 'Einschalten beantragen', async ()=>{
          await S.api('/api/switch/request', {method: 'POST', body: {section: it.section, key: it.key, value: !it.value}});
          S.hinweis('Antrag gestellt – Freigabe im Posteingang.'); nach();
        });
        z.append(d().el('span', 'hs-einst-label', it.section + '.' + it.key), d().el('b', 'hs-einst-wert', it.value === null || it.value === undefined ? '–' : (it.value ? 'an' : 'aus')), k);
        box.append(z);
      });
      if(!(v.items || []).length) box.append(d().el('div', 'hs-app-satz', 'Keine Schalter freigegeben (local_switches.ALLOWED).'));
    }).catch(err=>box.append(d().el('div', 'hs-app-satz warn', 'Schalter: ' + err.message)));
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.einstellungen = {ID, GRUPPEN, oeffnen, ansicht, istReiter, zerlegen, meldung, meldungSetzen, benachrichtigen, KEY, MELDE_KEY};
})();
