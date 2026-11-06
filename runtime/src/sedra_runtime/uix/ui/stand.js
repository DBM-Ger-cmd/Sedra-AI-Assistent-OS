// UI contract 1.1 – der Arbeitsstand einer Shell (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §10).
//
// Jede Shell meldet, welche Objekte sie offen hat und welches vorn liegt; die nächste Shell übernimmt sie. Das Melden ist gebündelt
// (höchstens einmal je 500 ms), Schließen wird mitgemeldet, und vor einem Shell-Wechsel geht der letzte Stand sofort hinaus
// (sedraWechsel.beimWechsel). Die Shell entscheidet selbst, wie sie Objekte anordnet – hier steht nur, was offen ist.
//
// Rein bis auf makeMelder: `ordnen` und `uebernahme` prüft node. Classic script: definiert window.sedraStand.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const MAX = 24;
  const FELDER = ['type', 'id', 'title', 'ansicht', 'view', 'collection'];

  function schluessel(o){ return o && o.type && o.id !== undefined && o.id !== null ? String(o.type) + ':' + String(o.id) : ''; }

  // nur die Felder, die der Server annimmt (rein)
  function sauber(o){
    const out = {};
    FELDER.forEach(k=>{ if(o && o[k] !== undefined && o[k] !== null) out[k] = k === 'collection' ? !!o[k] : String(o[k]).slice(0, 200); });
    return out;
  }

  // offene Objekte nach letzter Benutzung, das jüngste vorn, ohne Doppel, höchstens MAX (rein)
  function ordnen(objekte, zuletzt){
    const z = zuletzt || {};
    const seen = new Set();
    return (objekte || []).filter(o=>{ const k = schluessel(o); if(!k || seen.has(k)) return false; seen.add(k); return true; })
      .map((o, i)=>({o, i, t: z[schluessel(o)] || 0}))
      .sort((a, b)=>b.t - a.t || a.i - b.i)
      .slice(0, MAX).map(x=>sauber(x.o));
  }

  // Was eine neue Shell aus dem Stand übernimmt (rein): die Objekte, die sie noch nicht offen hat und zeichnen kann, und was vorn liegt.
  // `kann(objekt)` sagt, ob die Shell ein Werkzeug dafür hat; was sie nicht zeichnen kann, bleibt im Stand stehen (A20).
  function uebernahme(stand, offen, kann){
    const da = new Set((offen || []).map(schluessel));
    const neu = [], ohne = [];
    ((stand && stand.offen) || []).forEach(o=>{
      const k = schluessel(o);
      if(!k || da.has(k)) return;
      (kann && !kann(o) ? ohne : neu).push(o);
      da.add(k);
    });
    const vorn = stand && stand.vorn && !ohne.some(o=>schluessel(o) === stand.vorn) ? stand.vorn : null;
    return {neu, ohne, vorn, von: (stand && stand.shell) || null};
  }

  // Der Melder einer Shell: offen(objekte, vorn) und geschlossen(objekt) merken, gebündelt senden; jetzt() sendet sofort.
  function makeMelder(api, opts){
    const o = opts || {};
    const uhr = o.uhr || {setTimeout: (f, ms)=>setTimeout(f, ms), clearTimeout: id=>clearTimeout(id)};
    let stand = null, zu = [], wartet = null;
    function senden(){
      wartet = null;
      if(!stand && !zu.length) return Promise.resolve();
      const body = {offen: stand ? stand.offen : [], vorn: stand ? stand.vorn : null, geschlossen: zu.splice(0)};
      return Promise.resolve(api('/api/arbeitsstand', {method: 'POST', body})).catch(()=>{});
    }
    const planen = ()=>{ if(wartet === null) wartet = uhr.setTimeout(senden, o.ms === undefined ? 500 : o.ms); };
    const melder = {
      offen(objekte, vorn, zuletzt){ stand = {offen: ordnen(objekte, zuletzt), vorn: vorn || null}; planen(); },
      geschlossen(objekt){ const k = schluessel(objekt); if(k && zu.indexOf(k) < 0) zu.push(k); planen(); },
      jetzt(){ if(wartet !== null) uhr.clearTimeout(wartet); return senden(); },
      holen(){ return Promise.resolve(api('/api/arbeitsstand')).catch(()=>null); }
    };
    // vor einem Shell-Wechsel: der letzte Stand und die Ablage der Werkzeuge gehen sofort hinaus
    if(root.sedraWechsel && root.sedraWechsel.beimWechsel) root.sedraWechsel.beimWechsel(()=>melder.jetzt());
    return melder;
  }

  // Härtung 30.10. (HU-S7): der eine Weg einer Shell, eine Entscheidung zu beantworten – antworten und `decision.answered` senden,
  // damit Werkzeuge und Instrumente nachziehen (vorher hatten drei Shells ein decide ohne Ereignis)
  async function entscheiden(api, bus, id, way){
    const out = await api('/api/decisions/answer', {method: 'POST', body: {id, way}});
    try{ bus && bus.emit('decision.answered', {id: String(id), kind: 'answered'}); }catch(_e){}
    return out;
  }

  root.sedraStand = {schluessel, sauber, ordnen, uebernahme, makeMelder, MAX, entscheiden};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraStand;
})();
