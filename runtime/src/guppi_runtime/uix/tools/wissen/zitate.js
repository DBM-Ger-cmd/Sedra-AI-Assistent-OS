// Werkzeug „Wissen“ – die reinen Teile neben tool.js (Spec 7, D7.6/D7.9): Zitat-IDs `[W…]` im Text finden, Fehlercodes des
// Servers als deutsche Sätze, die Stufe eines Formulars prüfen. Daten rein, Daten raus; nur `zitatKnoten` baut DOM aus `ui/dom.js`.
// Kein Zeitgeber, keine Verbindung nach außen. Wird vor tool.js geladen (tool.yaml, entry.js).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const ZITAT = /\[(W[0-9a-f]{10,16})\]/g;                     // wie wissen/ausgabe.py ZITAT_MUSTER
  const SAETZE = {
    unknown_object_type: 'Der Wissensspeicher ist ausgeschaltet.',
    object_not_found: 'Dieses Objekt gibt es nicht mehr; die Ansicht wird neu gelesen.',
    unknown_verb: 'Dieses Verb kennt der Server nicht.',
    tool_route_not_allowed: 'Diese Route ist für das Werkzeug nicht freigegeben.',
    bad_request: 'Die Anfrage war unvollständig.'
  };

  // Ein Text als Folge von Stücken: {text} und {id} für jedes Zitat [W…] (rein)
  function zitatTeile(text){
    const s = String(text === null || text === undefined ? '' : text), out = [];
    let last = 0, m;
    ZITAT.lastIndex = 0;
    while((m = ZITAT.exec(s))){
      if(m.index > last) out.push({text: s.slice(last, m.index)});
      out.push({id: m[1]});
      last = m.index + m[0].length;
    }
    if(last < s.length) out.push({text: s.slice(last)});
    return out;
  }

  // Der Text als Knoten im Container `node`: jedes Zitat ein Verweis (Maus und Tastatur), `onId(id)` zeigt den Treffer
  function zitatKnoten(node, text, onId){
    const d = root.sedraDom;
    zitatTeile(text).forEach(teil=>{
      if(teil.id === undefined){ node.append(teil.text); return; }
      const a = d.el('span', 't-wissen-zitat', '[' + teil.id + ']');
      a.title = 'Treffer ' + teil.id + ' zeigen';
      d.clickable(a, e=>{ if(e && e.stopPropagation) e.stopPropagation(); onId(teil.id); });
      node.append(a);
    });
    return node;
  }

  // Ein Fehler aus ctx.api() als Satz: bekannte Codes übersetzt, Sätze des Servers bleiben, Rest unverändert (rein)
  function fehlerSatz(err){
    const m = String(err && err.message !== undefined ? err.message : (err || '')).trim();
    if(!m) return 'Unbekannter Fehler.';
    const code = m.split(/[\s:]/)[0];
    return SAETZE[code] ? SAETZE[code] + ' (' + code + ')' : m;
  }

  // Die Stufe aus einem Formular: ganze Zahl 0–6; `mindestens` gilt für „Stufe heraufsetzen“ (nur enger) (rein)
  function stufePruefen(wert, mindestens){
    const s = String(wert === null || wert === undefined ? '' : wert).trim();
    if(!/^\d+$/.test(s)) return {ok: false, satz: 'Die Stufe muss eine ganze Zahl von 0 bis 6 sein.'};
    const n = Number(s);
    if(n > 6) return {ok: false, satz: 'Die Stufe muss eine ganze Zahl von 0 bis 6 sein.'};
    if(mindestens !== undefined && mindestens !== null && n <= mindestens) return {ok: false, satz: 'Heraufsetzen heißt enger: die Stufe muss höher als ' + mindestens + ' sein.'};
    return {ok: true, stufe: n};
  }

  root.sedraWissenZitate = {zitatTeile, zitatKnoten, fehlerSatz, stufePruefen};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraWissenZitate;
})();
