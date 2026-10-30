// Harness-Shell Stufe 5 – Prüfung eines Katalog-Entwurfs (SPEC_HARNESS_SHELL_v1 HS-42; G2 Stufe 5 §4.2/§4.3; G3 N4).
//
// Rein: kein DOM, kein window-Zugriff, keine Anfrage – `node` prüft es (tests/test_uix_harness_einstellungen.py). Der Editor zeigt die
// Befunde live, bevor er einen Antrag stellt; **gültig** macht den Entwurf erst der Server (`harness/katalog.py: pruefe_entwurf`,
// dieselben Regeln, 400 mit Satz). Hier steht, was der Captain vor dem Antrag sehen soll: Fehler (der Antrag kann nicht gestellt
// werden), Lockerungen gegen die Vorlage (rot, D-U3), weite Muster (rot), Diff gegen den Stand und eine YAML-Vorschau.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const STUFEN = ['frei', 'vorarbeiter', 'captain', 'verboten'];
  const DATEI_WERKZEUGE = ['datei_lesen', 'dateien_auflisten', 'suchen', 'datei_schreiben', 'datei_aendern'];
  const WERKZEUGE = DATEI_WERKZEUGE.concat(['befehl', 'lauf_starten', 'lauf_stoppen', 'modell_laden', 'modell_entladen']);
  const ID = /^[a-z0-9][a-z0-9-]{0,47}$/;
  const WEIT = /^(\*\*|\*|\*\*\/\*|\.|\/|\*\*\/\*\*)$/;
  const rang = s=>STUFEN.indexOf(s);
  const liste = v=>Array.isArray(v) ? v.slice() : (v === undefined || v === null || v === '' ? [] : [v]);
  const gleich = (a, b)=>JSON.stringify(norm(a)) === JSON.stringify(norm(b));

  // Eine Regel in der Form, die der Server zurückgibt (Listen als Listen, Text getrimmt) – ohne Prüfung
  function norm(r){
    r = r || {};
    return {id: String(r.id === undefined || r.id === null ? '' : r.id).trim(), werkzeug: liste(r.werkzeug).map(String), muster: liste(r.muster).map(String),
            stufe: String(r.stufe || ''), begruendung: String(r.begruendung || '').trim()};
  }

  // Fehler, die der Server genauso melden würde (Reihenfolge und Wortlaut angelehnt an katalog.pruefen) – je Regel, mit Index
  function fehler(entwurf){
    const out = [], ids = {};
    if(!Array.isArray(entwurf) || !entwurf.length) return [{regel: null, satz: 'regeln_fehlen: mindestens eine Regel'}];
    entwurf.forEach((roh, i)=>{
      const r = norm(roh), n = i + 1, wo = r.id || ('Regel ' + n);
      if(!ID.test(r.id)) out.push({regel: n, id: r.id, satz: wo + ': ID ungültig – kleine Buchstaben, Ziffern und Bindestrich'});
      else if(ids[r.id]) out.push({regel: n, id: r.id, satz: wo + ': ID doppelt'});
      ids[r.id] = true;
      if(!r.werkzeug.length || r.werkzeug.some(w=>w !== '*' && WERKZEUGE.indexOf(w) < 0))
        out.push({regel: n, id: r.id, satz: wo + ': Werkzeug unbekannt – erlaubt ' + WERKZEUGE.join(', ') + ' oder *'});
      if(!r.muster.length || r.muster.some(m=>!m.trim())) out.push({regel: n, id: r.id, satz: wo + ': Muster fehlt'});
      const dateiRegel = r.werkzeug.some(w=>w === '*' || DATEI_WERKZEUGE.indexOf(w) >= 0) && !(r.werkzeug.length === 1 && r.werkzeug[0] === 'befehl');
      if(dateiRegel && r.muster.some(m=>m.replace(/\\/g, '/').split('/').indexOf('..') >= 0 || /^([A-Za-z]:|\/)/.test(m)))
        out.push({regel: n, id: r.id, satz: wo + ': Dateimuster relativ zur Projektwurzel, ohne „..“'});
      if(STUFEN.indexOf(r.stufe) < 0) out.push({regel: n, id: r.id, satz: wo + ': Stufe unbekannt – ' + STUFEN.join(', ')});
      if(!r.begruendung) out.push({regel: n, id: r.id, satz: wo + ': Begründung fehlt – jede Regel sagt, warum'});
    });
    return out;
  }

  // Diff gegen den Stand (was gerade gilt): neu, geändert, entfernt – je ID
  function diff(stand, entwurf){
    const alt = {}, neu = {};
    (stand || []).forEach(r=>{ const n = norm(r); alt[n.id] = n; });
    (entwurf || []).forEach(r=>{ const n = norm(r); neu[n.id] = n; });
    return {neu: Object.keys(neu).filter(id=>!alt[id]).sort(), entfernt: Object.keys(alt).filter(id=>!neu[id]).sort(),
            geaendert: Object.keys(neu).filter(id=>alt[id] && !gleich(alt[id], neu[id])).sort()};
  }

  // Befunde (keine Fehler): weite Muster (nur in Regeln, die nicht genau so in der Vorlage stehen – die Vorlage selbst ist geprüft),
  // Lockerung einer Vorlage-Regel, gesperrte verbotene Vorlage-Regel geändert/entfernt
  function befunde(entwurf, vorlage){
    const out = [], vor = {}, neu = {};
    (vorlage || []).forEach(r=>{ const n = norm(r); vor[n.id] = n; });
    (entwurf || []).forEach(r=>{ const n = norm(r); neu[n.id] = n; });
    (entwurf || []).forEach((roh, i)=>{
      const r = norm(roh), v = vor[r.id];
      if(!(v && gleich(v, r))) r.muster.forEach(m=>{ if(WEIT.test(m.trim())) out.push({art: 'weit', regel: i + 1, id: r.id, satz: 'weites Muster: „' + r.id + '“ trifft mit „' + m + '“ alles (' + r.werkzeug.join(', ') + ')'}); });
      if(v && v.stufe === 'verboten' && !gleich(v, r)) out.push({art: 'gesperrt', regel: i + 1, id: r.id, satz: 'Regel „' + r.id + '“ ist in der Vorlage verboten und gesperrt (D-U3)'});
      else if(v && rang(r.stufe) >= 0 && rang(r.stufe) < rang(v.stufe)) out.push({art: 'lockerung', regel: i + 1, id: r.id, satz: 'Lockerung: „' + r.id + '“ der Vorlage von ' + v.stufe + ' auf ' + r.stufe});
    });
    Object.keys(vor).forEach(id=>{ if(vor[id].stufe === 'verboten' && !neu[id]) out.push({art: 'gesperrt', regel: null, id, satz: 'Vorlage-Regel „' + id + '“ (verboten) fehlt im Entwurf'}); });
    return out;
  }

  // Alles auf einmal: darf der Antrag gestellt werden? (keine Fehler, keine gesperrte Regel verändert, etwas geändert)
  function pruefen(stand, entwurf, vorlage){
    const f = fehler(entwurf), b = befunde(entwurf, vorlage), d = diff(stand, entwurf);
    const leer = !d.neu.length && !d.geaendert.length && !d.entfernt.length;
    const gesperrt = b.some(x=>x.art === 'gesperrt');
    return {fehler: f, befunde: b, diff: d, unveraendert: leer, antragMoeglich: !f.length && !gesperrt && !leer, rot: b.filter(x=>x.art !== 'gesperrt').length};
  }

  function yamlText(s){
    s = String(s);
    return /^[A-Za-z0-9_\-./*]+$/.test(s) && !/^[-*]/.test(s) ? s : "'" + s.replace(/'/g, "''") + "'";
  }

  // Vorschau der Datei, wie der Server sie schreiben würde (dieselbe Form wie die Vorlage; nicht die Datei selbst)
  function alsYamlVorschau(entwurf){
    const zeilen = ['freigabe_katalog:', '  version: 1', '  regeln:'];
    (entwurf || []).forEach(roh=>{
      const r = norm(roh);
      zeilen.push('    - id: ' + yamlText(r.id));
      zeilen.push('      werkzeug: [' + r.werkzeug.map(yamlText).join(', ') + ']');
      zeilen.push('      muster: [' + r.muster.map(yamlText).join(', ') + ']');
      zeilen.push('      stufe: ' + yamlText(r.stufe));
      zeilen.push('      begruendung: ' + yamlText(r.begruendung));
    });
    return zeilen.join('\n') + '\n';
  }

  const api = {STUFEN, WERKZEUGE, DATEI_WERKZEUGE, norm, fehler, diff, befunde, pruefen, alsYamlVorschau};
  root.sedraKatalogPruefung = api;
  if(typeof module !== 'undefined' && module.exports) module.exports = api;
})();
