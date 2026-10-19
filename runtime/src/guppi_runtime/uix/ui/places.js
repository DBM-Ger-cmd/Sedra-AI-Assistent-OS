// UI contract 1.0 – die Ortskunde (SHELL_WERKZEUG_VERTRAG_v1 §4).
//
// Welche Wörter welchen Ort meinen, und ob ein Satz Navigation, Auftrag oder Frage ist. Das stand bis zum 14.10.2026 in
// `shells/cockpit/palette.js` – und das Gespräch griff quer darauf zu. In einer anderen Shell verstummte die Navigation
// deshalb stillschweigend (gefunden beim Bau von Shell E). Es ist Vertrag, nicht Cockpit: zwei Shells und ein Werkzeug
// brauchen dieselbe Antwort auf „was meint der Captain mit ‚logbuch‘?“.
//
// Alles hier ist rein und wird mit node geprüft. Classic script: definiert window.sedraPlaces.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;

  // Die Orte: jeder ist ein Objekt, das eine Shell öffnen kann
  const PLACES = [
    {id: 'tasks',     label: 'Aufgaben',              hint: 'was läuft und was wartet',        words: ['aufgabe', 'aufgaben', 'karte', 'karten', 'mission', 'missionen'], object: {type: 'task', id: 'alle', title: 'Aufgaben', collection: true}},
    {id: 'intents',   label: 'Vorhaben',              hint: 'worum es geht – daraus werden Aufgaben', words: ['vorhaben', 'ziel', 'ziele', 'plan'],                 object: {type: 'intent', id: 'alle', title: 'Vorhaben', collection: true}},
    {id: 'boundary',  label: 'Modus und Grenzen',     hint: 'Projekt · Netz · Löschen · Kosten', words: ['modus', 'grenze', 'grenzen', 'sandbox', 'erlaubnis', 'rechte'], object: {type: 'boundary', id: 'projekt', title: 'Modus und Grenzen'}},
    {id: 'decisions', label: 'Entscheidungen',        hint: 'Freigaben und Grenzen',           words: ['entscheidung', 'entscheidungen', 'freigabe', 'freigaben', 'gate'],            object: {type: 'decision', id: 'alle', title: 'Entscheidungen', collection: true}},
    {id: 'models',    label: 'Werkstatt: Modelle',    hint: 'laden, wechseln, testen',         words: ['modell', 'modelle', 'werkstatt', 'laden', 'entladen', 'teststrecke', 'gguf'],  object: {type: 'model', id: 'alle', title: 'Werkstatt', collection: true}},
    {id: 'library',   label: 'Bibliothek',            hint: 'Skills ansehen und schreiben',    words: ['bibliothek', 'skill', 'skills', 'nachschlagen'],                              object: {type: 'skill', id: 'own', title: 'Bibliothek'}},
    {id: 'crew',      label: 'Besatzung',             hint: 'Rollen und Agenten',              words: ['besatzung', 'agent', 'agenten', 'crew', 'rollen', 'organigramm'],              object: {type: 'agent', id: 'alle', title: 'Besatzung', collection: true}},
    {id: 'meter',     label: 'Guppy-Meter',           hint: 'Token, Zeilen, Kosten',           words: ['meter', 'token', 'kosten', 'budget', 'zeilen', 'münzloch', 'muenzloch'],       object: {type: 'meter', id: 'meter', title: 'Guppy-Meter'}},
    {id: 'logbook',   label: 'Logbuch',               hint: 'Audit-Kette und Verlauf',         words: ['logbuch', 'audit', 'verlauf', 'protokoll'],                                   object: {type: 'logbook', id: 'audit', title: 'Logbuch'}},
    {id: 'hardware',  label: 'Hardware',              hint: 'GPU, Speicher, Profil',           words: ['hardware', 'gpu', 'grafikkarte', 'vram', 'speicher'],                         object: {type: 'hardware', id: 'hardware', title: 'Hardware'}},
    {id: 'machine',   label: 'Maschinenraum',         hint: 'Zustand der Runtime',             words: ['maschinenraum', 'runtime', 'system', 'status', 'entwicklungsumgebung', 'sandbox'], object: {type: 'machine', id: 'machine', title: 'Maschinenraum'}},
    {id: 'modules',   label: 'Module',                hint: 'Shell, Werkzeuge, Vorlagen',      words: ['modul', 'module', 'werkzeuge', 'shell', 'shells', 'erweiterung', 'plugin'],    object: {type: 'module', id: 'alle', title: 'Module', collection: true}},
    {id: 'gateway',   label: 'KI GateWay',            hint: 'Anfrage prüfen, Entwurf, Prüfung', words: ['gateway', 'gate', 'datenschutz', 'pseudonym', 'pseudonymisieren', 'anfrage', 'kundenanfrage'], object: {type: 'gateway', id: 'alle', title: 'KI GateWay', collection: true}},
    {id: 'project',   label: 'Projekt und Dateien',   hint: 'Dateien des Projekts',            words: ['projekt', 'projekte', 'datei', 'dateien', 'ordner'],                          object: {type: 'project', id: 'projekt', title: 'Projekt'}},
    {id: 'uebersetzung', label: 'Übersetzer',         hint: 'eine Nachricht für eine andere Rolle (Fisch)', words: ['übersetzer', 'uebersetzer', 'übersetzen', 'uebersetzen', 'übersetzung', 'uebersetzung'], object: {type: 'uebersetzung', id: 'wolke', title: 'Übersetzen'}},
    {id: 'transkript', label: 'Transkripte',          hint: 'importieren, suchen, freigeben, exportieren (Fisch)', words: ['transkript', 'transkripte', 'untertitel', 'srt', 'vtt'], object: {type: 'transkript', id: 'alle', title: 'Transkripte'}},
    {id: 'aufnahme',  label: 'Rekorder',              hint: 'aufnehmen, abspielen, Sprache → Text (Kern)', words: ['rekorder', 'aufnahme', 'aufnahmen', 'aufnehmen', 'mikrofon', 'diktat', 'diktieren', 'sprachaufnahme'], object: {type: 'aufnahme', id: 'rekorder', title: 'Rekorder'}},
    {id: 'planung',   label: 'Planungstisch',         hint: 'mit einem Assistenten Ziele und Aufträge festlegen', words: ['planungstisch', 'planung', 'planen', 'assistent', 'assistenten'], object: {type: 'planung', id: 'tisch', title: 'Planungstisch'}}
  ];

  const ORDER_WORDS = ['erstelle', 'erstell', 'baue', 'bau', 'schreibe', 'schreib', 'implementiere', 'programmiere', 'entwickle', 'ändere', 'aendere',
                       'repariere', 'behebe', 'füge', 'fuege', 'lege', 'teste', 'prüfe', 'pruefe', 'refaktoriere', 'optimiere', 'erweitere', 'generiere', 'migriere', 'dokumentiere'];
  const QUESTION_WORDS = ['was', 'wie', 'warum', 'wieso', 'weshalb', 'welche', 'welcher', 'welches', 'wer', 'wann', 'wo', 'wozu', 'erkläre', 'erklär', 'erklaere',
                          'beschreibe', 'sag', 'sage', 'zeig', 'zeige', 'kannst', 'kann', 'ist', 'sind', 'hat', 'gibt', 'soll', 'hilf', 'hilfe'];

  // Build 19: „kannst du mir ein Fenster für Maschinenraum öffnen“ ist Navigation, auch als Frage und auch lang (PC-Test 15.10.:
  // der Satz ging ans Modell, und das sagte „ich kann keine Fenster öffnen“). Nur die Wörter des Öffnens – „zeig mir …“ bleibt
  // eine Frage, denn „zeig mir die Modelle von gestern“ will eine Antwort, kein Fenster.
  const OPEN_WORDS = ['öffne', 'oeffne', 'öffnen', 'oeffnen', 'öffnest', 'oeffnest', 'aufmachen', 'aufrufen', 'geh', 'gehe', 'wechsle'];

  function wantsOpen(text){
    const words = normalize(text).split(' ');
    return words.some(w=>OPEN_WORDS.includes(w));
  }

  function normalize(text){
    return String(text || '').toLowerCase().replace(/[„“"'.,!?;:()]+/g, ' ').replace(/\s+/g, ' ').trim();
  }

  function wordMatch(hay, needle){
    const i = hay.indexOf(needle);
    if(i < 0) return false;
    return (i === 0 || hay[i - 1] === ' ') && (i + needle.length === hay.length || hay[i + needle.length] === ' ');
  }

  function matchPlaces(text, places){
    const q = normalize(text);
    if(!q) return [];
    const out = [];
    (places || PLACES).forEach(p=>{
      let best = 0;
      p.words.forEach(w=>{
        if(q === w) best = Math.max(best, 100 + w.length);
        else if(wordMatch(q, w)) best = Math.max(best, 50 + w.length);
        else if(q.length >= 3 && w.startsWith(q)) best = Math.max(best, 20 + q.length);
      });
      if(normalize(p.label).startsWith(q)) best = Math.max(best, 30 + q.length);
      if(best) out.push({id: p.id, label: p.label, hint: p.hint, object: p.object, score: best});
    });
    return out.sort((a, b)=>b.score - a.score || a.label.localeCompare(b.label));
  }

  // {kind:'place', id, object} for a short navigation phrase, {kind:'talk', text, order} for everything else.
  function routeText(text, places){
    const raw = String(text || '').trim();
    if(!raw) return null;
    if(raw.startsWith('/')) return {kind: 'talk', text: raw, order: false};
    const q = normalize(raw), words = q.split(' ');
    const order = ORDER_WORDS.includes(words[0]) || (/^(bitte|guppi) /.test(q) && ORDER_WORDS.includes(words[1]));
    const question = QUESTION_WORDS.includes(words[0]) || raw.endsWith('?');
    if(words.length <= 4 && !order && !question){
      const hits = matchPlaces(raw, places);
      if(hits.length && hits[0].score >= 50) return {kind: 'place', id: hits[0].id, object: hits[0].object, text: raw};
    }
    if(words.length <= 14 && !order && wantsOpen(raw)){
      // nur ein ganzes Wort zählt (score ≥ 50) – „öffne mir das bitte“ findet keinen Ort und geht ans Gespräch
      const hits = matchPlaces(raw, places).filter(h=>h.score >= 50);
      if(hits.length) return {kind: 'place', id: hits[0].id, object: hits[0].object, text: raw};
    }
    return {kind: 'talk', text: raw, order};
  }

  // the rows the palette shows for what has been typed so far
  function paletteRows(text, places){
    const route = routeText(text, places) || {kind: 'talk', text: '', order: false};
    const hits = matchPlaces(text, places).slice(0, 6);
    const rows = [];
    const talk = {id: '__talk', label: text.trim() ? 'An SEDRA senden: ' + text.trim().slice(0, 60) : 'An SEDRA senden',
                  hint: route.order ? 'SEDRA antwortet im Gespräch und macht daraus Aufgaben' : 'Frage, Auftrag oder /status'};
    // a place first whenever the text looks like navigation (also half-typed: „entscheid“); an order or a question goes to SEDRA first
    const navigation = route.kind === 'place' || (hits.length && !route.order && !String(text).trim().endsWith('?') && String(text).trim().split(/\s+/).length <= 3);
    if(navigation){ rows.push(...hits); if(text.trim()) rows.push(talk); }
    else { if(text.trim()) rows.push(talk); rows.push(...hits); }
    if(!text.trim()) (places || PLACES).slice(0, 8).forEach(p=>rows.push({id: p.id, label: p.label, hint: p.hint, object: p.object}));
    return rows;
  }

  root.sedraPlaces = {PLACES, routeText, matchPlaces, paletteRows, normalize, wantsOpen, ORDER_WORDS, QUESTION_WORDS, OPEN_WORDS};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraPlaces;
})();
