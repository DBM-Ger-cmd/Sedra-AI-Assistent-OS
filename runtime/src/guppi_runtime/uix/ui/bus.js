// UI contract 1.0 – the event bus (SHELL_WERKZEUG_VERTRAG_v1 §5).
// Named events, flat objects, no functions inside. The shell may send everything; a tool only what its manifest lists under
// events.emits – a tool that sends anything else is refused here, not quietly tolerated, so the contract is visible while building.
// Pure part (checkEvent, EVENTS) is tested with node; the browser part is the subscription list.
// Classic script: defines window.sedraBus.

(function(){
  const EVENTS = {
    'object.open':        ['type', 'id', 'title'],
    'object.close':       ['type', 'id'],
    'task.changed':       ['id'],
    'decision.pending':   ['id'],
    'decision.answered':  ['id'],
    'model.changed':      [],
    'live.line':          ['line'],
    'talk.context':       [],
    'talk.mode':          ['mode'],
    'system.state':       ['state'],
    'desk.error':         ['message'],
    'desk.resync':        [],
    'tools.refresh':      [],
    // Nachtrag N3 (Spec 4, G2-S4-05): Sender ist der Ereignisstrom (desk/events.py); Werkzeuge hören sie, senden sie nicht.
    // N4: `decision.pending` darf zusätzlich `agent_id` tragen (leer, wenn kein Agent betroffen ist) – optional, daher oben nicht Pflicht.
    'agent.changed':      ['id'],
    'issue.changed':      ['id'],
    'budget.warning':     ['agent_id'],
    'slot.changed':       [],
    // Vertrag 1.1 (SPEC_SHELL_WISSEN_v1 §4.1): ein Treffer im Wissen wurde gewählt; Nachweis-Werkzeuge (Fundstelle) hören darauf
    'wissen.auswahl':     ['id'],
    // Vertrag 1.1: ein Werkzeug sagt, dass sich seine Handlungen geändert haben (z. B. eine andere Ansicht) – die Shell zeichnet die Werkbank-Zeile neu
    'object.actions':     ['type', 'id'],
    // Harness-Shell (SPEC_HARNESS_SHELL_v1 G2 §5): Sender ist der Ereignisstrom; der Text einer Antwort läuft über ihren eigenen Strom
    'harness.sitzung':    ['id'],
    'harness.antwort':    ['sitzung_id'],
    // Stufe 3: Aufgaben-Freigabe, Vorarbeiter, Läufe, Karten (Frist) – gesendet vom Ereignisstrom (harness/api.py)
    'harness.aufgabe':    ['id'],
    'harness.vorarbeiter': ['projekt'],
    'harness.lauf':       ['id'],
    'harness.karte':      ['karte_id']
  };
  // Härtung 30.10. (HU-L11, Nachtrag N3): diese Ereignisse sendet nur der Ereignisstrom/die Seite – ein Werkzeug darf sie nicht
  // in `events.emits` eintragen und nicht senden, auch wenn das Manifest es nennt (desk/gateway.py weist das Manifest ab).
  const NUR_STROM = ['task.changed', 'model.changed', 'system.state', 'desk.error', 'desk.resync', 'tools.refresh',
                     'agent.changed', 'issue.changed', 'budget.warning', 'slot.changed'];
  const nurStrom = name=>NUR_STROM.indexOf(name) >= 0 || name.indexOf('harness.') === 0;

  // '' when the event is fine, otherwise the reason – a sender id of null means the shell (it may send everything)
  function checkEvent(name, payload, allowed){
    if(!Object.prototype.hasOwnProperty.call(EVENTS, name)) return 'unbekanntes Ereignis: ' + name;
    if(payload !== undefined && payload !== null && (typeof payload !== 'object' || Array.isArray(payload))) return 'Nutzlast muss ein flaches Objekt sein';
    const flat = payload || {};
    for(const key of Object.keys(flat)){
      const v = flat[key];
      if(typeof v === 'function') return 'Nutzlast enthält eine Funktion: ' + key;
      if(v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).some(k=>typeof v[k] === 'object' && v[k])) return 'Nutzlast ist zu tief verschachtelt: ' + key;
    }
    for(const key of EVENTS[name]) if(flat[key] === undefined) return 'Ereignis ' + name + ' braucht das Feld ' + key;
    if(allowed && allowed.indexOf(name) < 0) return 'dieses Werkzeug darf ' + name + ' nicht senden (events.emits in tool.yaml)';
    if(allowed && nurStrom(name)) return name + ' sendet nur der Ereignisstrom, kein Werkzeug (Vertrag N3)';
    return '';
  }

  function makeBus(onRefused){
    const listeners = new Map();
    function on(name, fn){
      if(!listeners.has(name)) listeners.set(name, new Set());
      listeners.get(name).add(fn);
      return ()=>{ const set = listeners.get(name); if(set) set.delete(fn); };
    }
    function emit(name, payload, allowed){
      const bad = checkEvent(name, payload, allowed);
      if(bad){ if(onRefused) onRefused(name, bad); return false; }
      const flat = payload || {};
      (listeners.get(name) || new Set()).forEach(fn=>{
        try{ fn(flat); }
        catch(err){ if(onRefused) onRefused(name, 'Empfänger hat einen Fehler geworfen: ' + (err && err.message ? err.message : err)); }
      });
      return true;
    }
    // what a tool gets: it may only send what its manifest lists
    function forModule(emits){
      return {on, emit: (name, payload)=>emit(name, payload, emits || [])};
    }
    return {on, emit, forModule, listeners};
  }

  const root = typeof window !== 'undefined' ? window : globalThis;                          // the pure part also runs in node
  root.sedraBus = {EVENTS, NUR_STROM, nurStrom, checkEvent, makeBus};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraBus;
})();
