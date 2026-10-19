// UI contract – Stufe C, die Seite im Rahmen. Läuft im abgeschotteten iframe eines Nicht-CORE-Werkzeugs (sandbox ohne allow-same-origin).
// Kein Token, kein Zugriff auf die Seite der Shell. Alles geht über postMessage zur Brücke des Kerns (ui/bruecke.js).
// Das Werkzeug bekommt denselben ctx wie in der Seite: api(), bus, shell (open, notify; decide wirft einen Fehler).
// Klassisches Script: definiert window.sedra (nur die Registrierung) und window.sedraRahmen.start(manifest).

(function(){
  const root = window;
  const registriert = [];
  root.sedra = {registerTool(mod){ registriert.push(mod); return mod; }};

  const offen = new Map();
  const hoerer = new Map();
  let nr = 0;

  function senden(op, extra){
    return new Promise((ok, bad)=>{
      const id = 'r' + (++nr);
      offen.set(id, {ok, bad});
      window.parent.postMessage(Object.assign({id, op}, extra), '*');
    });
  }

  window.addEventListener('message', e=>{
    if(e.source !== window.parent) return;          // nur der Kern spricht hier
    const d = e.data || {};
    if(d.antwort){
      const p = offen.get(d.id);
      if(!p) return;
      offen.delete(d.id);
      if(d.ok) p.ok(d.daten); else p.bad(new Error(d.fehler || 'Unbekannter Fehler'));
      return;
    }
    if(d.ereignis){
      (hoerer.get(d.ereignis) || []).slice().forEach(fn=>{ try{ fn(d.daten); }catch(_err){} });
    }
  });

  function kontext(manifest){
    return {
      object: null,
      api: (path, optionen)=>{
        const o = optionen || {};
        return senden('api', {path, method: String(o.method || 'GET').toUpperCase(), body: o.body});
      },
      bus: {
        // ein Rahmen sendet keine Ereignisse; er hört nur die, die sein Manifest listet
        emit(){},
        on(name, fn){
          if(!hoerer.has(name)) hoerer.set(name, []);
          hoerer.get(name).push(fn);
          return ()=>{ const l = hoerer.get(name) || []; const i = l.indexOf(fn); if(i >= 0) l.splice(i, 1); };
        }
      },
      shell: {
        open: obj=>senden('shell', {name: 'open', args: [obj]}),
        notify: (text, ton)=>senden('shell', {name: 'notify', args: [text, ton]}),
        decide: ()=>Promise.reject(new Error('Freigaben erteilt nur der Kern, nicht ein Modul.'))
      },
      tokens: getComputedStyle(document.documentElement),
      manifest,
      _offs: []
    };
  }

  root.sedraRahmen = {
    start(manifest){
      const mod = registriert[registriert.length - 1];
      const el = document.getElementById('werk');
      if(!mod || !el){ document.body.textContent = 'Werkzeug nicht geladen: ' + (manifest && manifest.id); return; }
      try{ mod.mount(el, kontext(manifest)); }
      catch(err){ el.textContent = 'Fehler im Werkzeug: ' + (err && err.message || err); }
    }
  };
})();
