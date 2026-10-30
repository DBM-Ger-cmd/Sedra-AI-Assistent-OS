// Harness-Shell Stufe 4 – die App-Liste des Start-Menüs (SPEC_HARNESS_SHELL_v1 HS-40; G2 Stufe 4 §3.1/§3.2; G3 N3).
//
// Rein: kein DOM, kein window-Zugriff, keine Anfrage – `node` prüft es (tests/test_uix_harness_start.py). Eine App ist ein **Ort**
// (ui/places.js), zu dem mindestens ein geladenes Werkzeug zeichnet (UIX-10: was kein Werkzeug hat, steht nicht im Menü).
// Werkzeuge vom Typ object/panel, zu denen kein Ort führt, bekommen einen Ort aus ihrem ersten Objekttyp (`id: alle`).
// Nie im Menü: Instrumente (HS-43) und das Gespräch (`talk`) – das ist in der Harness die Mitte, keine App.
// Gruppe: Manifest-Feld `gruppe` (Vertrag N2) > Zuordnung der Datei (Ort-ID, dann Objekttyp) > `arbeit`; „Prüfung“ nur, wenn ein
// Werkzeug `zweck: pruefung` dabei ist (das Gateway lädt es nur mit dem Schalter `entwicklung`, die Shell prüft den Schalter nicht).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const GRUPPEN = ['arbeit', 'modelle', 'wissen', 'system', 'pruefung'];
  const TITEL = {arbeit: 'Arbeit', modelle: 'Modelle', wissen: 'Wissen', system: 'System', pruefung: 'Prüfung'};
  const SYMBOLE = {arbeit: '▤', modelle: '◆', wissen: '▣', system: '⚙', pruefung: '✓'};
  const NIE = ['talk'];

  // Die Zuordnung aus start_gruppen.json – geprüft; kaputt ist ein Fehler mit Satz, kein leeres Menü
  function zuordnungPruefen(roh){
    if(!roh || typeof roh !== 'object' || Array.isArray(roh)) throw new Error('start_gruppen: kein Objekt');
    const z = roh.zuordnung || {};
    if(typeof z !== 'object' || Array.isArray(z)) throw new Error('start_gruppen: zuordnung muss ein Objekt sein');
    Object.keys(z).forEach(k=>{ if(GRUPPEN.indexOf(z[k]) < 0) throw new Error('start_gruppen: unbekannte Gruppe „' + z[k] + '“ für „' + k + '“'); });
    const gruppen = Array.isArray(roh.gruppen) && roh.gruppen.length ? roh.gruppen : GRUPPEN;
    gruppen.forEach(g=>{ if(GRUPPEN.indexOf(g) < 0) throw new Error('start_gruppen: unbekannte Gruppe „' + g + '“'); });
    const max = Number.isInteger(roh.zuletzt_max) && roh.zuletzt_max >= 0 ? roh.zuletzt_max : 6;
    return {gruppen, zuordnung: z, symbole: Object.assign({}, SYMBOLE, roh.symbole && typeof roh.symbole === 'object' ? roh.symbole : {}), zuletzt_max: max};
  }

  function gruppeVon(ort, werkzeuge, zuordnung){
    const mitFeld = werkzeuge.find(w=>w && w.gruppe);
    if(mitFeld) return mitFeld.gruppe;
    if(zuordnung[ort.id]) return zuordnung[ort.id];
    const typ = ort.object && ort.object.type;
    if(typ && zuordnung[typ]) return zuordnung[typ];
    return 'arbeit';
  }

  // orte: ui/places.js PLACES; werkzeuge: /api/uix/modules tools (id, kind, handles, zweck, gruppe, name, description, enabled);
  // zeichnet(objekt) -> [manifest …] (ctx.tools.forObject); zuordnung: aus start_gruppen.json; zuletzt: [ort-id …]
  function bauen(orte, werkzeuge, zeichnet, konfig, zuletzt){
    const k = zuordnungPruefen(konfig || {});
    const geladen = (werkzeuge || []).filter(w=>w && w.enabled !== false);
    const apps = [];
    const bekannt = new Set();
    (orte || []).forEach(ort=>{
      if(!ort || !ort.object || NIE.indexOf(ort.object.type) >= 0) return;
      const zeichner = (zeichnet(ort.object) || []).filter(w=>w && w.kind !== 'instrument');
      if(!zeichner.length) return;
      bekannt.add(ort.object.type);
      const pruefung = zeichner.every(w=>w.zweck === 'pruefung');     // nur ein reiner Prüf-Ort landet unter „Prüfung“ – Aufgaben bleiben Aufgaben, auch wenn eine Probe sie mitzeichnet
      apps.push({id: ort.id, label: ort.label, hint: ort.hint || '', words: ort.words || [], object: ort.object,
                 gruppe: pruefung ? 'pruefung' : gruppeVon(ort, zeichner, k.zuordnung), werkzeuge: zeichner.map(w=>w.id)});
    });
    // Werkzeuge ohne Ort: ein eigener Ort aus dem ersten Objekttyp (UIX-10: nichts fehlt, auch ein eigener Typ nicht)
    geladen.forEach(w=>{
      if(['object', 'panel'].indexOf(w.kind) < 0) return;
      const typ = ((w.handles || [])[0] || '').split(':')[0];
      if(!typ || NIE.indexOf(typ) >= 0 || bekannt.has(typ)) return;
      bekannt.add(typ);
      apps.push({id: 'werkzeug-' + w.id, label: w.name || w.id, hint: w.description || '', words: [String(w.name || w.id).toLowerCase()],
                 object: {type: typ, id: 'alle', title: w.name || w.id},
                 gruppe: w.zweck === 'pruefung' ? 'pruefung' : (w.gruppe || k.zuordnung[typ] || 'arbeit'), werkzeuge: [w.id]});
    });
    apps.forEach(a=>{ a.symbol = k.symbole[a.gruppe] || SYMBOLE.arbeit; });
    const gruppen = k.gruppen.map(g=>({id: g, titel: TITEL[g], symbol: k.symbole[g], apps: apps.filter(a=>a.gruppe === g)})).filter(g=>g.apps.length);
    const jeId = {};
    apps.forEach(a=>{ jeId[a.id] = a; });
    const letzte = (zuletzt || []).map(id=>jeId[id]).filter(Boolean).slice(0, k.zuletzt_max);
    return {gruppen, zuletzt: letzte, apps, zuletzt_max: k.zuletzt_max};
  }

  function normalize(text){
    return String(text || '').toLowerCase().replace(/[„“"'.,!?;:()]+/g, ' ').replace(/\s+/g, ' ').trim();
  }

  // Suche wie Strg+K: Treffer auf Name, Hinweis und Suchwörter; Reihenfolge nach Güte, dann nach dem Menü (stabil)
  function suchen(liste, text){
    const q = normalize(text);
    if(!q) return [];
    const out = [];
    (liste.apps || []).forEach((a, i)=>{
      let best = 0;
      (a.words || []).forEach(w=>{
        if(q === w) best = Math.max(best, 100 + w.length);
        else if(w.startsWith(q)) best = Math.max(best, 50 + q.length);
        else if(w.indexOf(q) >= 0) best = Math.max(best, 20 + q.length);
      });
      const label = normalize(a.label), hint = normalize(a.hint);
      if(label.startsWith(q)) best = Math.max(best, 60 + q.length);
      else if(label.split(' ').some(w=>w.startsWith(q))) best = Math.max(best, 30 + q.length);
      else if(hint.startsWith(q) || hint.split(' ').some(w=>w.startsWith(q))) best = Math.max(best, 10 + q.length);     // Wortanfang, nicht mitten im Wort („rag“ trifft nicht „Frage“)
      if(best) out.push({app: a, score: best, i});
    });
    return out.sort((a, b)=>b.score - a.score || a.i - b.i).map(x=>x.app);
  }

  // „zuletzt benutzt“ nachführen: neueste zuerst, ohne Doppel, höchstens max
  function zuletztNach(zuletzt, id, max){
    return [id].concat((zuletzt || []).filter(x=>x !== id)).slice(0, max);
  }

  // Einträge für /api/uix/shelf (kind place, label ≤ 24 Zeichen, icon aus der Gruppe)
  function alsAblage(liste, zuletzt){
    const jeId = {};
    (liste.apps || []).forEach(a=>{ jeId[a.id] = a; });
    return (zuletzt || []).map(id=>jeId[id]).filter(Boolean).map(a=>({kind: 'place', label: String(a.label).slice(0, 24), icon: a.gruppe, place: a.id}));
  }

  const api = {GRUPPEN, TITEL, SYMBOLE, zuordnungPruefen, bauen, suchen, zuletztNach, alsAblage, normalize};
  root.sedraStartliste = api;
  if(typeof module !== 'undefined' && module.exports) module.exports = api;
})();
