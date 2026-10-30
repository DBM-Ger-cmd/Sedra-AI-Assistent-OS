// UI contract 1.0 – Sprache (Kern, 19.10.2026): das Mikrofon für jedes Werkzeug in jeder Shell.
// Ein Werkzeug ruft sedraSprache.aufnehmen(ctx.api, {...}) und bekommt einen Griff: pause(), weiter(), stop(), abbrechen().
// Der Browser nimmt auf (MediaRecorder, Stücke alle paar Sekunden), der Helfer schickt jedes Stück über die api() des Werkzeugs
// an den Kern (/api/sprache/aufnahme/stueck) – nacheinander, jedes unter dem Request-Limit. Kein eigenes fetch, kein Speicher.
// Die Routen muss das Werkzeug in seinem Manifest nennen (beginnen · stueck · beenden), sonst sagt der Server Nein (§6).
// Classic script, wie dom.js. Ohne Mikrofon oder ohne MediaRecorder sagt kann() warum – nichts wird vorgetäuscht.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const STUECK_MS = 4000;
  const MIMES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];

  // Warum es (nicht) geht – rein aus dem, was der Browser bietet
  function kann(nav, Rec){
    nav = nav || root.navigator; Rec = Rec || root.MediaRecorder;
    if(!nav || !nav.mediaDevices || !nav.mediaDevices.getUserMedia) return {ok: false, grund: 'Dieser Browser gibt kein Mikrofon frei (kein getUserMedia). Ein neuerer Browser, und die Seite über localhost öffnen.'};
    if(!Rec) return {ok: false, grund: 'Dieser Browser kann nicht aufnehmen (kein MediaRecorder).'};
    const mime = MIMES.find(m=>{ try{ return Rec.isTypeSupported(m); }catch(_e){ return false; } });
    if(!mime) return {ok: false, grund: 'Dieser Browser kennt kein Aufnahmeformat, das SEDRA ablegt (webm, ogg, mp4).'};
    return {ok: true, mime};
  }

  // Bytes → base64, ohne String-Grenzen zu reißen
  function base64(bytes){
    let s = '';
    for(let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }

  // Der Pegel (0..1) aus dem Analyser – rein
  function pegel(daten){
    let sum = 0;
    for(let i = 0; i < daten.length; i++){ const v = (daten[i] - 128) / 128; sum += v * v; }
    return Math.min(1, Math.sqrt(sum / daten.length) * 3);
  }

  // Die Aufnahme: api = ctx.api des Werkzeugs; opts: titel, sprache, onStand(stand), onFehler(text)
  async function aufnehmen(api, opts){
    opts = opts || {};
    const k = kann();
    if(!k.ok) throw new Error(k.grund);
    // Härtung 30.10. (HU-L9): erst der Kern, dann das Mikrofon – lehnt die Route ab, bleibt kein Mikrofon offen
    const record = await api('/api/sprache/aufnahme/beginnen', {method: 'POST', body: {titel: opts.titel || '', mime: k.mime, sprache: opts.sprache || 'de'}});
    const stream = await root.navigator.mediaDevices.getUserMedia({audio: true});
    let rec;
    try{ rec = new root.MediaRecorder(stream, {mimeType: k.mime}); }
    catch(err){ stream.getTracks().forEach(t=>t.stop()); throw err; }
    const stand = {id: record.id, status: 'laeuft', sekunden: 0, pegel: 0, groesse: 0, stuecke: 0, offen: 0};
    let start = Date.now(), pausiert = 0, pauseSeit = 0, kette = Promise.resolve(), fehler = null, timer = null;
    let audio = null, analyser = null, puffer = null;
    try{
      const AC = root.AudioContext || root.webkitAudioContext;
      if(AC){ audio = new AC(); analyser = audio.createAnalyser(); analyser.fftSize = 512; audio.createMediaStreamSource(stream).connect(analyser); puffer = new Uint8Array(analyser.fftSize); }
    }catch(_e){ audio = null; }

    const melden = ()=>{ if(opts.onStand) opts.onStand(Object.assign({}, stand)); };
    const tick = ()=>{
      if(stand.status === 'laeuft') stand.sekunden = (Date.now() - start - pausiert) / 1000;
      if(analyser && stand.status === 'laeuft'){ analyser.getByteTimeDomainData(puffer); stand.pegel = pegel(puffer); } else stand.pegel = 0;
      melden();
    };
    const schicken = blob=>{
      stand.offen += 1;
      kette = kette.then(async()=>{
        if(fehler) return;
        try{
          const bytes = new Uint8Array(await blob.arrayBuffer());
          const r = await api('/api/sprache/aufnahme/stueck', {method: 'POST', body: {id: record.id, data: base64(bytes)}});
          stand.groesse = r.groesse; stand.stuecke = r.stuecke;
        }catch(err){ fehler = err; if(opts.onFehler) opts.onFehler(err.message); }
        finally{ stand.offen -= 1; melden(); }
      });
    };
    rec.ondataavailable = e=>{ if(e.data && e.data.size) schicken(e.data); };
    rec.start(STUECK_MS);
    timer = setInterval(tick, 200);
    tick();

    const aufraeumen = ()=>{ clearInterval(timer); stream.getTracks().forEach(t=>t.stop()); if(audio){ try{ audio.close(); }catch(_e){} } };
    const warten = ()=>new Promise(res=>{ rec.onstop = res; rec.stop(); });

    return {
      stand: ()=>Object.assign({}, stand),
      pause(){ if(rec.state === 'recording'){ rec.pause(); pauseSeit = Date.now(); stand.status = 'pause'; melden(); } },
      weiter(){ if(rec.state === 'paused'){ rec.resume(); pausiert += Date.now() - pauseSeit; stand.status = 'laeuft'; melden(); } },
      async stop(){
        if(rec.state !== 'inactive') await warten();
        aufraeumen(); await kette;
        if(fehler) throw fehler;
        stand.status = 'fertig'; melden();
        return api('/api/sprache/aufnahme/beenden', {method: 'POST', body: {id: record.id, dauer: stand.sekunden}});
      },
      async abbrechen(){
        if(rec.state !== 'inactive'){ rec.ondataavailable = null; await warten(); }
        aufraeumen(); stand.status = 'abgebrochen'; melden();
        try{ await kette; await api('/api/sprache/aufnahme/loeschen', {method: 'POST', body: {id: record.id}}); }catch(_e){}
      }
    };
  }

  root.sedraSprache = {kann, aufnehmen, base64, pegel, MIMES, STUECK_MS};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraSprache;
})();
