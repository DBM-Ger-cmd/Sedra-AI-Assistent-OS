// Harness-Shell: die App „Übersicht“ (A3 Cockpit als App, SPEC_APP_UEBERSICHT_v1) – der Baum der Gesamtlage: alle Apps nach Gruppen, klappbar, mit Zustand je Zeile.
//
// Die Übersicht ist Navigation und sonst nichts: eine Zeile öffnet die App über denselben Weg wie das Start-Menü (`app.oeffnen`), sie zeichnet nie selbst ein Werkstück.
// Die Zeilen kommen aus der Liste des Start-Menüs (`S._start.liste`, dieselbe Quelle, dieselben Gruppen, dieselben Namen); den Zustand holt sie aus vorhandenen Routen
// (`/api/missions`, `/api/models`). Eine zugeklappte Gruppe sagt „⚠ n wartet“, was wartet, verschwindet nicht (wie im Baum der alten Shell „cockpit“).
// `modell`, `zustandAus`, `sichtbar` und `lesen` sind rein (Daten rein, Zeilen raus), `node` prüft sie ohne Browser. Gemerkt werden nur Gruppennamen (`sedra.harness.uebersicht.baum`).
// Text nur mit textContent, Farben nur über Tokens, kein Takt.
// Nicht gebaut: Zustand für alle anderen Orte, Strg+K-Palette, Dock (zwei Werkzeuge nebeneinander), Ziehen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const KEY = 'sedra.harness.uebersicht.baum';
  const VORGABE = ['arbeit', 'modelle'];                       // beim ersten Öffnen offen
  const OBJEKT = {type: 'uebersicht', id: 'app', title: 'Übersicht'};

  // der Zustand je Ort (rein): {ort-id: {note, ton}}; ton 'warn' zählt als „wartet“
  function zustandAus(daten){
    const z = {};
    const missions = Array.isArray(daten && daten.missions) ? daten.missions : [];
    const offen = missions.filter(m=>m.offen !== undefined ? m.offen : (m.status || '') === 'active');
    const wartet = offen.filter(m=>(m.pending_gates || 0) > 0).length;
    z.tasks = {note: offen.length ? offen.length + ' offen' + (wartet ? ' · ' + wartet + ' wartet auf dich' : '') : 'nichts offen', ton: wartet ? 'warn' : ''};
    const server = (daten && daten.models && daten.models.server) || null;
    if(server) z.models = {note: server.running ? (server.model ? server.model + ' geladen' : 'Modell geladen') : 'keins geladen', ton: server.running ? 'ok' : ''};
    return z;
  }

  // die Zeilen (rein): Kopf je Gruppe mit der Zahl wartender Zeilen, darunter eine Zeile je App
  function modell(liste, zustand){
    const rows = [];
    ((liste && liste.gruppen) || []).forEach(g=>{
      const apps = (g.apps || []).map(a=>({kind: 'row', gruppe: g.id, app: a, title: a.label, note: (zustand && zustand[a.id] && zustand[a.id].note) || a.hint || '',
                                           tone: (zustand && zustand[a.id] && zustand[a.id].ton) || '', schluessel: 'a:' + a.id}));
      rows.push({kind: 'head', gruppe: g.id, title: g.titel, symbol: g.symbol || '', schluessel: 'g:' + g.id, wartet: apps.filter(r=>r.tone === 'warn').length, anzahl: apps.length});
      apps.forEach(r=>rows.push(r));
    });
    return rows;
  }

  // zugeklappte Gruppen zeigen nur den Kopf (rein)
  function sichtbar(rows, offen){
    const auf = offen instanceof Set ? offen : new Set(offen || []);
    return rows.filter(r=>r.kind === 'head' || auf.has(r.gruppe));
  }

  // der gemerkte Zustand (rein): kaputt oder fremd → die Vorgabe
  function lesen(roh){
    try{
      const v = JSON.parse(roh);
      if(v && Array.isArray(v.offen) && v.offen.every(x=>typeof x === 'string' && x.length <= 40)) return v.offen.slice(0, 40);
    }catch(_e){}
    return VORGABE.slice();
  }

  // Die Ansicht. Rückgabe {abbauen, zeichnen, aktualisieren, rows}.
  function ansicht(S, box, kopfFlaeche){
    kopfFlaeche.koerper.hidden = true; kopfFlaeche.verben.hidden = true;           // die Fläche des Platzhalter-Werkzeugs „uebersicht“ bleibt leer
    const buehne = d().el('div', 'hs-ue-buehne');
    const leiste = d().el('div', 'hs-ue-leiste');
    const neu = d().el('button', 'hs-ue-neu', 'Aktualisieren'); neu.type = 'button';
    const hinweis = d().el('span', 'hs-ue-hinweis', '');
    leiste.append(neu, hinweis);
    const baum = d().el('div', 'hs-ue-baum'); baum.setAttribute('role', 'tree'); baum.setAttribute('aria-label', 'Übersicht');
    buehne.append(leiste, baum); box.append(buehne);
    let zu = false, zustand = {}, fokus = null;
    const offen = new Set(lesen((()=>{ try{ return localStorage.getItem(KEY); }catch(_e){ return null; } })()));
    const merken = ()=>{ try{ localStorage.setItem(KEY, JSON.stringify({v: 1, offen: [...offen]})); }catch(_e){} };
    const liste = ()=>(S._start && S._start.liste) || null;
    const zeilen = ()=>modell(liste(), zustand);

    function umschalten(gruppe){ offen.has(gruppe) ? offen.delete(gruppe) : offen.add(gruppe); fokus = 'g:' + gruppe; merken(); zeichnen(); }

    function tasten(e, alle, i, r, auf){
      const geh = n=>{ if(n){ e.preventDefault(); fokus = n.dataset.key; alle.forEach(x=>{ x.tabIndex = x === n ? 0 : -1; }); n.focus(); } };
      const kopf = r.kind === 'head';
      if(e.key === 'ArrowDown') geh(alle[i + 1]);
      else if(e.key === 'ArrowUp') geh(alle[i - 1]);
      else if(e.key === 'Home') geh(alle[0]);
      else if(e.key === 'End') geh(alle[alle.length - 1]);
      else if(e.key === 'ArrowRight' && kopf){ e.preventDefault(); if(!auf) umschalten(r.gruppe); else geh(alle[i + 1]); }
      else if(e.key === 'ArrowLeft'){
        if(kopf && auf){ e.preventDefault(); umschalten(r.gruppe); }
        else geh(baum.querySelector('[data-key="g:' + r.gruppe + '"]'));
      }else if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); alle[i].click(); }
    }

    function zeichnen(){
      if(zu) return;
      const war = baum.contains(document.activeElement) && document.activeElement.dataset ? document.activeElement.dataset.key : null;
      const rows = zeilen();
      if(!rows.length){ baum.replaceChildren(d().el('div', 'hs-ue-leer', 'Die Liste der Apps ist noch nicht geladen.')); return; }
      const elemente = [];
      let gruppeBox = null;
      const kinder = [];
      sichtbar(rows, offen).forEach(r=>{
        const kopf = r.kind === 'head', auf = kopf && offen.has(r.gruppe);
        const z = d().el('div', 'hs-ue-zeile' + (kopf ? ' kopf' : '') + (r.tone ? ' ' + r.tone : ''));
        z.dataset.key = r.schluessel; z.dataset.gruppe = r.gruppe; z.tabIndex = -1; z.setAttribute('role', 'treeitem');
        if(kopf){
          z.setAttribute('aria-expanded', auf ? 'true' : 'false');
          z.append(d().el('span', 'hs-ue-titel', (auf ? '▾ ' : '▸ ') + (r.symbol ? r.symbol + ' ' : '') + r.title));
          const note = !auf && r.wartet ? '⚠ ' + r.wartet + ' wartet' : r.anzahl + (r.anzahl === 1 ? ' App' : ' Apps');
          z.append(d().el('small', 'hs-ue-note' + (!auf && r.wartet ? ' warn' : ''), note));
          z.onclick = ()=>umschalten(r.gruppe);
          gruppeBox = d().el('div', 'hs-ue-gruppe'); gruppeBox.setAttribute('role', 'group');
          kinder.push(z, gruppeBox);
        }else{
          z.append(d().el('span', 'hs-ue-titel', r.title));
          if(r.note) z.append(d().el('small', 'hs-ue-note', r.note));
          z.onclick = ()=>{ fokus = r.schluessel; root.sedraHarness.app.oeffnen(S, r.app); };      // Navigation: dieselbe Tür wie das Start-Menü
          (gruppeBox || baum).append(z);
        }
        elemente.push({z, r, auf});
      });
      baum.replaceChildren(...kinder);
      const alle = elemente.map(x=>x.z);
      elemente.forEach((x, i)=>{ x.z.onkeydown = e=>tasten(e, alle, i, x.r, x.auf); });
      const ziel = alle.find(x=>x.dataset.key === (war || fokus)) || alle[0];
      if(ziel){ ziel.tabIndex = 0; if(war) ziel.focus(); }
    }

    async function aktualisieren(){
      hinweis.textContent = '';
      const holen = pfad=>S.api(pfad).catch(()=>null);
      const [missions, models] = await Promise.all([holen('/api/missions'), holen('/api/models')]);
      if(zu) return;
      zustand = zustandAus({missions: Array.isArray(missions) ? missions : [], models: models || {}});
      if(missions === null && models === null) hinweis.textContent = 'Zustand nicht erreichbar – die Zeilen zeigen nur ihren Hinweis.';
      zeichnen();
    }
    neu.onclick = aktualisieren;
    zeichnen(); aktualisieren();
    return {zeichnen, aktualisieren, rows: zeilen, abbauen(){ zu = true; baum.replaceChildren(); }};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.uebersicht = {KEY, VORGABE, OBJEKT, zustandAus, modell, sichtbar, lesen, ansicht};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.uebersicht;
})();
