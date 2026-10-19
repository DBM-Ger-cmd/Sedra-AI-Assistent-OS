// UI contract – Stufe C: die Brücke zwischen einem abgeschotteten Werkzeug-Rahmen und dem Kern (docs/PLAN_STUFE_C_2026-10-19.md, Abschnitt 3.2).
// Der Rahmen (iframe, sandbox ohne allow-same-origin) hat keinen Token und keinen Zugriff auf die Seite. Er spricht nur über
// postMessage. Der Kern ordnet jede Nachricht über die Quelle (event.source) dem Modul zu, nicht über ein Feld der Nachricht,
// prüft die Routen gegen das Manifest und führt die Shell-Aktion aus. Ereignisse bekommt der Rahmen nach dem Manifest
// (events.listens), nicht auf Anfrage. `decide` (Freigaben) gibt es über die Brücke nie: Freigaben erteilt nur der Kern.
// Die Regeln sind rein und werden mit node getestet. Klassisches Script: defines window.sedraBruecke.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;

  const OPS = ['api', 'shell'];
  const SHELL_AKTIONEN = ['open', 'notify'];

  // '' wenn die Nachricht erlaubt ist, sonst der Grund
  function pruefeNachricht(msg){
    if(!msg || typeof msg !== 'object' || Array.isArray(msg)) return 'nachricht_kein_objekt';
    if(typeof msg.id !== 'string' || msg.id.length < 1 || msg.id.length > 64) return 'id_fehlt';
    if(OPS.indexOf(msg.op) < 0) return 'op_unbekannt:' + String(msg.op).slice(0, 20);
    if(msg.op === 'api'){
      if(typeof msg.path !== 'string' || msg.path.indexOf('/api/') !== 0 || /\s/.test(msg.path)) return 'pfad_ungueltig';
      if(msg.body !== undefined && (msg.body === null || typeof msg.body !== 'object' || Array.isArray(msg.body))) return 'body_kein_objekt';
    }
    if(msg.op === 'shell' && SHELL_AKTIONEN.indexOf(msg.name) < 0) return 'shell_aktion_nicht_erlaubt:' + String(msg.name).slice(0, 20);
    if(msg.op === 'shell' && msg.args !== undefined && !Array.isArray(msg.args)) return 'args_keine_liste';
    return '';
  }

  // Die Routen im Manifest stehen als „GET /api/x“. Methode und Pfad müssen genau passen.
  function routeErlaubt(api, method, path){
    const m = String(method || 'GET').toUpperCase();
    return (api || []).some(e=>{
      const teile = String(e).trim().split(/\s+/);
      return teile.length >= 2 && teile[0].toUpperCase() === m && teile[1] === path;
    });
  }

  // Die Brücke des Kerns. `kern.forModule(modul)` liefert das api(); `shell` ist die Shell, `bus` der Ereignisstrom.
  // `quellen` ist eine Liste je Rahmen: {fenster, manifest}. Antworten gehen nur an das Fenster, aus dem die Nachricht kam.
  function makeBruecke({kern, shell, bus, onProblem}){
    const eintraege = [];
    const weg = [];

    function finde(source){
      return eintraege.find(e=>e.fenster === source) || null;
    }

    function antworte(e, id, ergebnis){
      try{ e.fenster.postMessage(Object.assign({id, antwort: true}, ergebnis), '*'); }catch(_err){}
    }

    async function behandle(e, msg){
      const fehler = pruefeNachricht(msg);
      if(fehler){ antworte(e, msg && msg.id ? String(msg.id) : '', {ok: false, fehler}); return; }
      if(msg.op === 'api'){
        const method = String(msg.method || 'GET').toUpperCase();
        if(!routeErlaubt(e.manifest.api, method, msg.path)){
          antworte(e, msg.id, {ok: false, fehler: 'tool_route_not_allowed', detail: method + ' ' + msg.path});
          onProblem && onProblem(e.manifest.id, 'Route nicht erlaubt: ' + method + ' ' + msg.path);
          return;
        }
        try{
          const daten = await kern.forModule({kind: 'tool', id: e.manifest.id})(msg.path, {method, body: msg.body});
          antworte(e, msg.id, {ok: true, daten});
        }catch(err){ antworte(e, msg.id, {ok: false, fehler: String(err && err.message || err)}); }
        return;
      }
      // shell: die Shell, aus deren Kontext dieser Rahmen gebaut wurde
      try{
        const sh = e.shell || shell;
        if(!sh || typeof sh[msg.name] !== 'function') throw new Error('shell_fehlt:' + msg.name);
        const args = Array.isArray(msg.args) ? msg.args.slice(0, 2) : [];
        const daten = await sh[msg.name](...args);
        antworte(e, msg.id, {ok: true, daten: daten === undefined ? null : daten});
      }catch(err){ antworte(e, msg.id, {ok: false, fehler: String(err && err.message || err)}); }
    }

    return {
      // einen Rahmen anmelden: nur die Ereignisse, die das Manifest listet
      register(fenster, manifest, eigeneShell){
        const e = {fenster, manifest, shell: eigeneShell || null, abos: []};
        eintraege.push(e);
        const hoert = (manifest.events && manifest.events.listens) || [];
        hoert.forEach(name=>{
          const off = bus.on(name, data=>{
            try{ fenster.postMessage({ereignis: name, daten: data || {}}, '*'); }catch(_err){}
          });
          if(typeof off === 'function') e.abos.push(off);
        });
        return e;
      },
      // eine eingehende Nachricht: Quelle prüfen, dann behandeln
      handle(event){
        const e = finde(event.source);
        if(!e){ onProblem && onProblem('Brücke', new Error('Nachricht aus unbekannter Quelle abgelehnt')); return false; }
        behandle(e, event.data);
        return true;
      },
      // den Rahmen abmelden und seine Abos lösen
      abmelden(fenster){
        const i = eintraege.findIndex(e=>e.fenster === fenster);
        if(i < 0) return;
        eintraege[i].abos.forEach(off=>{ try{ off(); }catch(_err){} });
        eintraege.splice(i, 1);
      },
      anzahl(){ return eintraege.length; }
    };
  }

  // Die Verdrahtung im Fenster: eine einzige Lauschstelle für alle Rahmen.
  function einhaengen(bruecke){
    root.addEventListener('message', event=>bruecke.handle(event));
  }

  root.sedraBruecke = {pruefeNachricht, routeErlaubt, makeBruecke, einhaengen, OPS, SHELL_AKTIONEN};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraBruecke;
})();
