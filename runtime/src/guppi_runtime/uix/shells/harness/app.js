// Harness-Shell Stufe 4 – der App-Reiter (SPEC_HARNESS_SHELL_v1 HS-40 „eine App öffnet als Reiter“; G2 Stufe 4 §3.4; G3 N5).
//
// Ein Werkzeug des Vertrags in einem Reiter `app:<typ>:<id>[:<ansicht>]`. Eingehängt wird genau so wie im Cockpit und in Minimal:
// `ctx.tools.forObject(objekt)` → je Werkzeug `ctx.makeContext(manifest, objekt, shellApi)` → `sedraLifecycle.mountTool(...)`;
// beim Schließen `unmountTool`. Kein zweiter Weg. `inhalt`-Werkzeuge stehen in der Fläche, `nachweis`-Werkzeuge in einer
// zuklappbaren rechten Spalte (D-S5, Vorgabe zu). Der Reiter meldet sein Objekt an `sedraStand` (§10.2), damit Cockpit, Minimal und
// Paperclip es beim Wechsel übernehmen. Höchstens 8 App-Reiter (D-S6): der älteste nicht aktive geht zu, und die Shell sagt es.
// Ein Werkzeug, das beim Einhängen wirft, ist ein Satz im Reiter – die Shell läuft weiter (onProblem). Die Werkbank-Zeile (Regel 3:
// was das Objekt in seinem Zustand kann) kommt aus `sedraLifecycle.actionsOf` der eingehängten Werkzeuge – wie im Cockpit und in Minimal.
// Stufe 5: `flaeche(S, objekt, nur)` ist der wiederverwendbare Teil – die Einstellungen (einstellungen.js) hängen ihre Werkzeuge damit ein.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const L = ()=>root.sedraLifecycle;
  const MAX = 8;
  const NACHWEIS_KEY = 'sedra.harness.app.nachweis';

  function apps(S){ return S._apps || (S._apps = new Map()); }

  function reiterId(objekt){
    const view = objekt.view || objekt.ansicht;
    return 'app:' + objekt.type + ':' + objekt.id + (view ? ':' + view : '');
  }

  function objektVon(S, id){
    const a = apps(S).get(id);
    if(a) return a.objekt;
    const teile = String(id).split(':');                            // app:typ:id[:ansicht] – auch ohne Eintrag lesbar (Stand-Übernahme)
    if(teile.length < 3 || teile[0] !== 'app') return null;
    const o = {type: teile[1], id: teile[2], title: teile[2]};
    if(teile[3]) o.view = teile[3];
    return o;
  }

  function titel(S, id){
    const a = apps(S).get(id);
    return (a && a.titel) || ((objektVon(S, id) || {}).title) || 'App';
  }

  function liste(S){ return root.sedraHarness.reiter.liste(S).filter(id=>String(id).startsWith('app:')); }

  // ---- öffnen: ort = {label?, gruppe?, symbol?, object: {type, id, title?, view?, collection?}}
  function oeffnen(S, ort){
    const objekt = Object.assign({}, ort.object || ort);
    if(!objekt.type || !objekt.id) return null;
    if(!objekt.title) objekt.title = ort.label || objekt.type;
    const id = reiterId(objekt);
    const R = root.sedraHarness.reiter;
    if(!apps(S).has(id)) apps(S).set(id, {objekt, titel: ort.label || objekt.title, gruppe: ort.gruppe || null, symbol: ort.symbol || null, seit: Date.now()});
    if(R.liste(S).indexOf(id) < 0){
      const offen = liste(S);
      if(offen.length >= MAX){
        const aktiv = R.aktiv(S);
        const aelteste = offen.filter(x=>x !== aktiv).sort((a, b)=>(apps(S).get(a) || {}).seit - (apps(S).get(b) || {}).seit)[0];
        if(aelteste){
          const name = titel(S, aelteste);
          R.schliessen(S, aelteste);
          S.hinweis('Höchstens ' + MAX + ' Apps zugleich – „' + name + '“ wurde geschlossen.', 'note');
        }
      }
    }
    R.aktivieren(S, id);
    melden(S);
    return id;
  }

  // ---- Werkzeuge eines Objekts in eine Fläche hängen (Stufe 5, G3 N5: auch die Einstellungen rufen das – ein Code, kein Nachbau).
  // `nur`: Werkzeug-IDs, auf die die Fläche beschränkt ist (die Einstellungen zeigen je Punkt ein Werkzeug). Rückgabe: {koerper, verben, mounts, abbauen, zeichnen, leer}.
  function flaeche(S, objekt, nur){
    const verben = d().el('div', 'hs-app-verben'); verben.dataset.verbs = '';        // Werkbank-Zeile (Vertragsmarke)
    const inhalt = d().el('div', 'hs-app-inhalt'); inhalt.dataset.slot = 'inhalt';
    const nachweis = d().el('aside', 'hs-app-nachweis'); nachweis.setAttribute('aria-label', 'Nachweise'); nachweis.dataset.slot = 'nachweis';   // Vertragsmarken (uix_check)
    const koerper = d().el('div', 'hs-app-koerper');
    koerper.append(inhalt, nachweis);
    const mounts = [];
    const werkzeuge = (S.ctx.tools.forObject(objekt) || []).filter(m=>m.kind !== 'instrument' && (!nur || nur.indexOf(m.id) >= 0));
    const links = werkzeuge.filter(m=>(m.slot || 'inhalt') !== 'nachweis');
    const rechts = werkzeuge.filter(m=>m.slot === 'nachweis');
    const f = {koerper, verben, inhalt, nachweis, mounts, werkzeuge, links, rechts, leer: !werkzeuge.length,
               abbauen(){ mounts.splice(0).forEach(e=>{ try{ L().unmountTool(e, S.ctx.onProblem); }catch(_err){} }); }};
    if(!werkzeuge.length){
      inhalt.append(d().el('div', 'hs-app-satz', 'Für „' + objekt.type + '“ ist kein Werkzeug geladen. Das Werkzeug „Module“ zeigt, was fehlt.'));
      f.zeichnen = ()=>{}; verben.hidden = true;
      return f;
    }
    const verbenZeichnen = ()=>{
      const alle = [];
      mounts.forEach(e=>L().actionsOf(e).forEach(x=>alle.push(x)));
      verben.replaceChildren(...alle.map(x=>{ const b = d().el('button', 'hs-app-verb', x.label); b.type = 'button'; b.onclick = ()=>Promise.resolve(x.run()).then(verbenZeichnen, verbenZeichnen); return b; }));
      verben.hidden = !alle.length;
    };
    f.zeichnen = verbenZeichnen;
    const einhaengen = (manifest, ziel)=>{
      const slot = d().el('div', 'hs-app-werkzeug'); slot.dataset.tool = manifest.id;
      ziel.append(slot);
      try{
        const ctx = S.ctx.makeContext(manifest, objekt, S.shellApi);
        const e = L().mountTool(S.ctx.tools.mod(manifest.id), slot, ctx, S.ctx.onProblem);
        e.manifest = manifest; mounts.push(e);
        if(e.ready && e.ready.then) e.ready.then(verbenZeichnen, verbenZeichnen); else verbenZeichnen();     // erst fragen, wenn das Werkzeug gezeichnet hat
      }catch(err){
        slot.replaceChildren(d().el('div', 'hs-app-satz warn', 'Das Werkzeug „' + (manifest.name || manifest.id) + '“ ließ sich nicht öffnen: ' + (err && err.message ? err.message : String(err))));
        if(S.ctx.onProblem) S.ctx.onProblem('App ' + manifest.id, err);
      }
    };
    links.forEach(m=>einhaengen(m, inhalt));
    rechts.forEach(m=>einhaengen(m, nachweis));
    verbenZeichnen();
    return f;
  }

  // ---- die Ansicht (S.zeigen → verlauf.ansicht → hier): Werkzeuge einhängen
  function ansicht(S, id){
    const eintrag = apps(S).get(id) || {objekt: objektVon(S, id), titel: titel(S, id), seit: Date.now()};
    apps(S).set(id, eintrag);
    const objekt = eintrag.objekt;
    const box = d().el('div', 'hs-verlauf hs-app-box');
    const kopf = d().el('div', 'hs-app-kopf');
    const f = flaeche(S, objekt);
    box.append(kopf, f.verben, f.koerper);
    const a = {id, box, S, objekt, mounts: f.mounts, leer: ()=>false, laeuft: ()=>false, nachUnten(){}, stoppen(){}, senden: async ()=>false, abbauen: f.abbauen, verben: f.zeichnen};
    kopf.append(d().el('b', 'hs-app-titel', eintrag.titel), d().el('code', 'hs-app-objekt', objekt.type + ' · ' + objekt.id + (objekt.view ? ' · ' + objekt.view : '')));
    if(f.rechts.length){
      const knopf = d().el('button', 'hs-app-nachweis-knopf', 'Nachweise (' + f.rechts.length + ')'); knopf.type = 'button';
      knopf.setAttribute('aria-expanded', 'false');
      const setzen = auf=>{ box.classList.toggle('nachweis-auf', auf); knopf.setAttribute('aria-expanded', auf ? 'true' : 'false'); merken(id, auf); };
      knopf.onclick = ()=>setzen(!box.classList.contains('nachweis-auf'));
      kopf.append(knopf);
      setzen(gemerkt(id));
    }
    return a;
  }

  function gemerkt(id){
    try{ return !!(JSON.parse(localStorage.getItem(NACHWEIS_KEY) || '{}') || {})[id]; }catch(_e){ return false; }
  }
  function merken(id, auf){
    try{
      const alle = JSON.parse(localStorage.getItem(NACHWEIS_KEY) || '{}') || {};
      if(auf) alle[id] = 1; else delete alle[id];
      localStorage.setItem(NACHWEIS_KEY, JSON.stringify(alle));
    }catch(_e){}
  }

  // ---- Schließen (reiter.schliessen → S.verwerfen → ansicht.abbauen); hier nur der Stand
  function geschlossen(S, id){
    const a = apps(S).get(id);
    if(a && S.melder){ S.melder.geschlossen(a.objekt); }
    apps(S).delete(id);
    if(S.ctx && a) try{ S.ctx.bus.emit('object.close', {type: a.objekt.type, id: a.objekt.id}); }catch(_e){}
    melden(S);
  }

  // ---- Arbeitsstand (§10.2): offen sind die App-Objekte, vorn das aktive
  function melden(S){
    if(!S.melder) return;
    const offen = liste(S).map(id=>objektVon(S, id)).filter(Boolean);
    const aktiv = root.sedraHarness.reiter.aktiv(S);
    const vorn = aktiv && String(aktiv).startsWith('app:') ? root.sedraStand.schluessel(objektVon(S, aktiv)) : null;
    S.melder.offen(offen, vorn);
  }

  // beim Start: was eine andere Oberfläche offen hatte (§10.4), höchstens MAX, nur mit Werkzeug
  async function uebernehmen(S){
    if(!S.melder) return 0;
    const stand = await S.melder.holen();
    const offen = liste(S).map(id=>objektVon(S, id)).filter(Boolean);
    const mit = root.sedraStand.uebernahme(stand, offen, o=>o.type !== 'talk' && S.ctx.tools.forObject(o).length > 0);
    const neu = mit.neu.slice(0, Math.max(0, MAX - offen.length));
    const aktiv = root.sedraHarness.reiter.aktiv(S);
    neu.forEach(o=>oeffnen(S, {object: o, label: o.title}));
    if(aktiv && !(mit.vorn && neu.some(o=>root.sedraStand.schluessel(o) === mit.vorn))) root.sedraHarness.reiter.aktivieren(S, aktiv);   // die Sitzung bleibt vorn, außer eine App war vorn
    if(mit.von && mit.von !== 'harness' && neu.length) S.hinweis('Aus der Oberfläche „' + mit.von + '“ mitgenommen: ' + neu.length + (neu.length === 1 ? ' App.' : ' Apps.'), 'note');
    return neu.length;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.app = {MAX, reiterId, objektVon, titel, liste, oeffnen, ansicht, flaeche, geschlossen, melden, uebernehmen, KEY: NACHWEIS_KEY};
})();
