// Vertragscode (ui/): Zitate [W…], Fehlersätze und Stufenprüfung des Wissens – vorher tools/wissen/zitate.js; seit Härtung E4 (30.10.)
// liegt es in ui/, weil Gespräch (talk) und Fundstelle es ebenso brauchen (Vertrag §2: keine Querimporte zwischen Werkzeugen).
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

  // ---- SPEC_WERKZEUG_WISSEN_v2: Klartext statt interner Namen (rein)
  // die Art einer Quelle, wie der Captain sie nennt (Adapter → Wort)
  const ART = {markdown: 'Doku', text: 'Text', logbuch: 'Logbuch', knowledge: 'Speicher', arbeitsumfeld: 'Arbeitsumfeld', gateway: 'GateWay', vorschlag: 'Vorschläge', notizen: 'Notizen'};
  function artText(adapter){ return ART[adapter] || String(adapter || '–'); }

  // wer eine Quelle lesen darf – die Stufen aus config/permission_levels.yaml in einem Satz (Antrag Schritt 3, Stufen-Auswahl)
  const STUFEN = ['jeder Agent, auch nur lesend', 'Agenten, die das Projekt lesen dürfen', '… die in der Entwicklungsumgebung schreiben dürfen',
                  '… die Tests ausführen dürfen', '… die das Projekt ändern dürfen', '… die das System ändern dürfen', 'nur du (Captain)'];
  function stufeText(n){ return STUFEN[n] === undefined ? 'Stufe ' + n : 'Stufe ' + n + ' – ' + STUFEN[n]; }

  // ein Text als Stücke mit markierten Suchwörtern: [{text, mark}] (rein); Wörter unter 3 Zeichen markieren zu viel
  function hervorheben(text, woerter){
    const s = String(text === null || text === undefined ? '' : text);
    const ws = (woerter || []).map(w=>String(w || '').trim()).filter(w=>w.length >= 3)
      .map(w=>w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    if(!ws.length) return s ? [{text: s, mark: false}] : [];
    const re = new RegExp('(' + ws.join('|') + ')', 'gi');
    const out = [];
    let last = 0, m;
    while((m = re.exec(s))){
      if(m.index > last) out.push({text: s.slice(last, m.index), mark: false});
      out.push({text: m[0], mark: true});
      last = m.index + m[0].length;
      if(m[0].length === 0) re.lastIndex += 1;
    }
    if(last < s.length) out.push({text: s.slice(last), mark: false});
    return out;
  }

  // Relevanz eines Treffers im Verhältnis zum besten der Liste, 0–1 (rein); der beste ist immer 1
  function relevanz(punkte, bester){
    const p = Number(punkte) || 0, b = Number(bester) || 0;
    if(b <= 0) return 0;
    return Math.max(0, Math.min(1, p / b));
  }

  root.sedraWissenZitate = {zitatTeile, zitatKnoten, fehlerSatz, stufePruefen, artText, stufeText, hervorheben, relevanz, STUFEN, ART};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraWissenZitate;
})();
