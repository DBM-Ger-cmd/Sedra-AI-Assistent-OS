// Harness-Shell – die 3D-Bühne (UIX nächste Stufe, 15.11.2026): der Seedrache des Startbilds als echtes 3D-Modell.
// Ohne Bibliothek und ohne Netz: ein kleiner GLB-Leser und ein WebGL2-Zeichner für Modelle ohne Textur (seedrache-web.glb,
// glTF 2.0 mit KHR_mesh_quantization – die ganzzahligen Attribute liest die Grafikkarte direkt). Die Zeichnung aus Tokens
// (verlauf.js `drache`) bleibt im DOM und ist der Rückfall: kein WebGL2, Modell fehlt, Kontext verloren, Bühne abgeschaltet.
// Ruhe-Regeln: zeichnet nur, wenn die Bühne sichtbar und der Reiter vorn ist; bei „weniger Bewegung“ genau ein Standbild;
// Auflösung gedeckelt (Pixelverhältnis höchstens 1,5), damit die Anzeige neben einem laufenden Modell nichts kostet.
// Die Bühne liest nur, sie entscheidet nichts. Wahl in localStorage `sedra.harness.buehne3d`: `hintergrund` (Vorgabe: der Drache
// läuft leise hinter der Arbeitsfläche), `buehne` (nur im Startbild über dem Titel), `aus`.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  root.sedraHarness = root.sedraHarness || {};
  const MODELL_URL = '/uix/shells/harness/seedrache-web.glb';
  const KEY = 'sedra.harness.buehne3d';
  const GLB_MAGIC = 0x46546C67, FOV = 30 * Math.PI / 180, DPR_MAX = 1.5;
  const ANZAHL = {SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4};
  let geladen = null;                      // Promise auf das gelesene Modell – einmal je Seite

  // ---- Matrizen (4x4, spaltenweise wie WebGL)
  const m4 = {
    eins: ()=>new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]),
    mal(a, b){
      const o = new Float32Array(16);
      for(let c = 0; c < 4; c++) for(let r = 0; r < 4; r++)
        o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
      return o;
    },
    trs(t, q, s){
      const [x, y, z, w] = q, [sx, sy, sz] = s;
      return new Float32Array([
        (1 - 2 * (y * y + z * z)) * sx, 2 * (x * y + z * w) * sx, 2 * (x * z - y * w) * sx, 0,
        2 * (x * y - z * w) * sy, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z + x * w) * sy, 0,
        2 * (x * z + y * w) * sz, 2 * (y * z - x * w) * sz, (1 - 2 * (x * x + y * y)) * sz, 0,
        t[0], t[1], t[2], 1]);
    },
    drehY(a){ const c = Math.cos(a), s = Math.sin(a); return new Float32Array([c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]); },
    drehX(a){ const c = Math.cos(a), s = Math.sin(a); return new Float32Array([1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1]); },
    schieben(x, y, z){ const o = m4.eins(); o[12] = x; o[13] = y; o[14] = z; return o; },
    sicht(fov, seite, nah, fern){
      const f = 1 / Math.tan(fov / 2);
      return new Float32Array([f / seite, 0, 0, 0, 0, f, 0, 0, 0, 0, (fern + nah) / (nah - fern), -1, 0, 0, 2 * fern * nah / (nah - fern), 0]);
    },
    punkt(m, x, y, z){ return [m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13], m[2] * x + m[6] * y + m[10] * z + m[14]]; }
  };

  // ---- GLB lesen (rein: läuft auch unter node, test_uix_buehne3d)
  function glbLesen(buf){
    const dv = new DataView(buf);
    if(buf.byteLength < 28 || dv.getUint32(0, true) !== GLB_MAGIC) throw new Error('kein_glb');
    const jl = dv.getUint32(12, true);
    const json = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 20, jl)));
    const bl = dv.getUint32(20 + jl, true);
    const bin = new Uint8Array(buf, 28 + jl, bl);
    const erlaubt = ['KHR_mesh_quantization'];
    (json.extensionsRequired || []).forEach(e=>{ if(!erlaubt.includes(e)) throw new Error('erweiterung_fehlt:' + e); });
    return {json, bin};
  }

  // Die Teile des Modells: je Primitive die Weltmatrix seines Knotens, das Material und die Zugriffe; dazu Mitte und Radius.
  function teileVon(glb){
    const j = glb.json, teile = [];
    const lauf = (nr, eltern)=>{
      const k = j.nodes[nr];
      const eigen = k.matrix ? new Float32Array(k.matrix) : m4.trs(k.translation || [0, 0, 0], k.rotation || [0, 0, 0, 1], k.scale || [1, 1, 1]);
      const welt = m4.mal(eltern, eigen);
      if(k.mesh !== undefined) j.meshes[k.mesh].primitives.forEach(p=>{
        if((p.mode === undefined || p.mode === 4) && p.attributes.POSITION !== undefined && p.attributes.NORMAL !== undefined && p.indices !== undefined)
          teile.push({welt, p, material: (j.materials || [])[p.material] || {}});
      });
      (k.children || []).forEach(c=>lauf(c, welt));
    };
    (j.scenes[j.scene || 0].nodes || []).forEach(n=>lauf(n, m4.eins()));
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    const dv = new DataView(glb.bin.buffer, glb.bin.byteOffset, glb.bin.byteLength);
    teile.forEach(t=>{
      const a = j.accessors[t.p.attributes.POSITION], bv = j.bufferViews[a.bufferView];
      const start = (bv.byteOffset || 0) + (a.byteOffset || 0), schritt = bv.byteStride || (a.componentType === 5126 ? 12 : 6);
      const lies = a.componentType === 5126 ? o=>dv.getFloat32(o, true) : (a.normalized ? o=>Math.max(dv.getInt16(o, true) / 32767, -1) : o=>dv.getInt16(o, true));
      const breite = a.componentType === 5126 ? 4 : 2;
      for(let i = 0; i < a.count; i += 4){                     // jede vierte Ecke reicht für den Rahmen
        const o = start + i * schritt, w = m4.punkt(t.welt, lies(o), lies(o + breite), lies(o + 2 * breite));
        for(let k = 0; k < 3; k++){ if(w[k] < min[k]) min[k] = w[k]; if(w[k] > max[k]) max[k] = w[k]; }
      }
    });
    const mitte = [0, 1, 2].map(k=>(min[k] + max[k]) / 2);
    const radius = Math.hypot(max[0] - min[0], max[1] - min[1], max[2] - min[2]) / 2 || 1;
    const halb = [0, 1, 2].map(k=>(max[k] - min[k]) / 2);
    return {teile, mitte, radius, halb};
  }

  function laden(){
    if(!geladen) geladen = fetch(MODELL_URL).then(r=>{ if(!r.ok) throw new Error('HTTP ' + r.status); return r.arrayBuffer(); })
      .then(buf=>{ const glb = glbLesen(buf); return Object.assign(teileVon(glb), {glb}); });
    return geladen;
  }

  const VS = `#version 300 es
in vec3 aOrt; in vec3 aNormale;
uniform mat4 uBild, uWelt;
out vec3 vN, vOrt;
void main(){ vec4 w = uWelt * vec4(aOrt, 1.0); vOrt = w.xyz; vN = mat3(uWelt) * aNormale; gl_Position = uBild * w; }`;
  const FS = `#version 300 es
precision highp float;
in vec3 vN, vOrt;
uniform vec3 uFarbe, uAkzent, uAuge;
uniform float uMetall, uRau;
out vec4 farbe;
void main(){
  vec3 n = normalize(vN), v = normalize(uAuge - vOrt);
  vec3 l1 = normalize(vec3(0.55, 0.8, 0.6)), l2 = normalize(vec3(-0.7, 0.25, 0.35));
  float d1 = max(dot(n, l1), 0.0), d2 = max(dot(n, l2), 0.0);
  float himmel = 0.5 + 0.5 * n.y;
  vec3 streu = uFarbe * (1.0 - 0.6 * uMetall) * (0.18 + 0.32 * himmel + 1.05 * d1 + 0.35 * d2);
  float glanz = mix(120.0, 10.0, uRau);
  vec3 h = normalize(l1 + v);
  vec3 spiegel = mix(vec3(0.04), uFarbe, uMetall) * pow(max(dot(n, h), 0.0), glanz) * (2.2 - 1.6 * uRau) * 2.0;
  float rand = pow(1.0 - max(dot(n, v), 0.0), 3.0);
  vec3 c = streu + spiegel + uAkzent * rand * 0.55;
  farbe = vec4(pow(c, vec3(1.0 / 2.2)), 1.0);
}`;

  function programm(gl){
    const teil = (art, text)=>{ const s = gl.createShader(art); gl.shaderSource(s, text); gl.compileShader(s);
      if(!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error('shader:' + gl.getShaderInfoLog(s)); return s; };
    const p = gl.createProgram();
    gl.attachShader(p, teil(gl.VERTEX_SHADER, VS)); gl.attachShader(p, teil(gl.FRAGMENT_SHADER, FS));
    gl.bindAttribLocation(p, 0, 'aOrt'); gl.bindAttribLocation(p, 1, 'aNormale');
    gl.linkProgram(p);
    if(!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error('programm:' + gl.getProgramInfoLog(p));
    const u = {}; ['uBild', 'uWelt', 'uFarbe', 'uAkzent', 'uAuge', 'uMetall', 'uRau'].forEach(n=>{ u[n] = gl.getUniformLocation(p, n); });
    return {p, u};
  }

  // Die Teile auf die Grafikkarte: je Pufferbereich ein Puffer, je Primitive ein Vertex-Array.
  function hochladen(gl, modell){
    const j = modell.glb.json, bin = modell.glb.bin, puffer = new Map();
    const pufferVon = (nr, ziel)=>{
      const schluessel = nr + ':' + ziel;
      if(!puffer.has(schluessel)){
        const bv = j.bufferViews[nr], b = gl.createBuffer();
        gl.bindBuffer(ziel, b); gl.bufferData(ziel, bin.subarray(bv.byteOffset || 0, (bv.byteOffset || 0) + bv.byteLength), gl.STATIC_DRAW);
        puffer.set(schluessel, b);
      }
      return puffer.get(schluessel);
    };
    return modell.teile.map(t=>{
      const vao = gl.createVertexArray(); gl.bindVertexArray(vao);
      [['POSITION', 0], ['NORMAL', 1]].forEach(([name, ort])=>{
        const a = j.accessors[t.p.attributes[name]], bv = j.bufferViews[a.bufferView];
        gl.bindBuffer(gl.ARRAY_BUFFER, pufferVon(a.bufferView, gl.ARRAY_BUFFER));
        gl.enableVertexAttribArray(ort);
        gl.vertexAttribPointer(ort, ANZAHL[a.type], a.componentType, !!a.normalized, bv.byteStride || 0, a.byteOffset || 0);
      });
      const ix = j.accessors[t.p.indices];
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, pufferVon(ix.bufferView, gl.ELEMENT_ARRAY_BUFFER));
      gl.bindVertexArray(null);
      const pbr = t.material.pbrMetallicRoughness || {};
      return {vao, welt: t.welt, anzahl: ix.count, art: ix.componentType, ab: ix.byteOffset || 0,
              farbe: (pbr.baseColorFactor || [0.8, 0.8, 0.8, 1]).slice(0, 3), metall: pbr.metallicFactor === undefined ? 1 : pbr.metallicFactor, rau: pbr.roughnessFactor === undefined ? 1 : pbr.roughnessFactor};
    });
  }

  // Die Akzentfarbe der Shell als lineare RGB-Werte (der Browser rechnet jeden CSS-Wert in #rrggbb um).
  function akzent(){
    try{
      const c = document.createElement('canvas').getContext('2d');
      c.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || 'teal';
      const m = /^#([0-9a-f]{6})$/i.exec(c.fillStyle);
      if(m) return [0, 2, 4].map(i=>Math.pow(parseInt(m[1].slice(i, i + 2), 16) / 255, 2.2));
    }catch(_e){ /* ohne Akzent bleibt der Rand neutral */ }
    return [0, 0.6, 0.4];
  }

  const MODI = ['hintergrund', 'buehne', 'aus'];
  let flug = null;                         // die Steuerung des fliegenden Drachen (landen, abheben), solange er fliegt – für den Avatar (avatar.js)
  const RUHE_MS = 25000, FLUG_FERNE = 2.6, LANDE_FERNE = 6, FLUG_BREITE = 1400, REGUNG = ['pointermove', 'pointerdown', 'keydown', 'wheel'];
  const modus = ()=>{ try{ const v = localStorage.getItem(KEY); return MODI.includes(v) ? v : MODI[0]; }catch(_e){ return MODI[0]; } };
  const ruhig = ()=>!!(root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches);

  // Die Bühne starten: zeichnet in `leinwand`, meldet `bereit` an `rahmenEl`, räumt auf, sobald der Rahmen das Dokument verlässt.
  function starten(rahmenEl, leinwand, modell, weit){
    const gl = leinwand.getContext('webgl2', {alpha: true, antialias: true, premultipliedAlpha: true, powerPreference: 'low-power'});
    if(!gl) return false;
    const {p, u} = programm(gl), teile = hochladen(gl, modell), rand = akzent();
    const quer = Math.hypot(modell.halb[0], modell.halb[2]), hoch = modell.halb[1] * 1.25;      // das Modell dreht sich um die Hochachse: quer zählt die Diagonale
    const st = {zeiger: [0, 0], ziel: [0, 0], lauf: 0, sichtbar: true, ende: false, t0: 0, winkel: -0.3, zeit: 0, kurs: 0, letzte: 0, ruhe: false, ferne: FLUG_FERNE, ort: [0, 0], platz: null};
    gl.enable(gl.DEPTH_TEST); gl.enable(gl.CULL_FACE); gl.clearColor(0, 0, 0, 0);

    const bild = ()=>{
      const dpr = Math.min(root.devicePixelRatio || 1, weit ? Math.min(1, FLUG_BREITE / Math.max(1, leinwand.clientWidth)) : DPR_MAX);    // der Flug über das ganze Fenster zeichnet nie breiter als FLUG_BREITE
      const b = Math.max(1, Math.round(leinwand.clientWidth * dpr)), h = Math.max(1, Math.round(leinwand.clientHeight * dpr));
      if(leinwand.width !== b || leinwand.height !== h){ leinwand.width = b; leinwand.height = h; }
      gl.viewport(0, 0, b, h); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      if(weit) st.ferne += ((st.platz ? LANDE_FERNE : FLUG_FERNE) - st.ferne) * 0.03;      // gelandet ist der Drache kleiner: er sitzt neben einem Hinweis
      const abstand = (Math.max(hoch, quer / (b / h)) / Math.tan(FOV / 2) + quer) * (weit ? st.ferne : 1), auge = [0, 0, abstand];
      st.zeiger[0] += (st.ziel[0] - st.zeiger[0]) * 0.08; st.zeiger[1] += (st.ziel[1] - st.zeiger[1]) * 0.08;
      let dreh = m4.mal(m4.drehX(0.12 + st.zeiger[1] * 0.25), m4.drehY(st.winkel + st.zeiger[0] * 0.6)), ort = [0, 0, 0];
      if(weit){                                                // der Flug: eine ruhige Schleife über das Fenster, der Kopf zeigt in Flugrichtung, die Nase folgt dem Steigen
        const hh = Math.tan(FOV / 2) * abstand, hw = hh * b / h, t = st.zeit, cw = Math.max(1, leinwand.clientWidth), ch = Math.max(1, leinwand.clientHeight);
        let ziel = [Math.sin(t * 0.13) * hw * 0.62, Math.sin(t * 0.19 + 1) * hh * 0.5], vx = Math.cos(t * 0.13), vy = Math.cos(t * 0.19 + 1);
        if(st.platz){                                          // Landeplatz in Fensterpunkten (Avatar): hinfliegen, dort leicht schweben, zum Hinweis schauen
          ziel = [(st.platz[0] / cw * 2 - 1) * hw, (1 - st.platz[1] / ch * 2) * hh + Math.sin(t * 1.6) * hh * 0.008];
          const dx = ziel[0] - st.ort[0];
          vx = Math.abs(dx) > hw * 0.08 ? dx : 1; vy = 0;
        }
        const zug = st.platz ? 0.05 : 0.02;
        st.ort[0] += (ziel[0] - st.ort[0]) * zug; st.ort[1] += (ziel[1] - st.ort[1]) * zug;
        ort = [st.ort[0], st.ort[1], 0];
        st.kurs += ((vx < 0 ? 0 : Math.PI) - st.kurs) * 0.025;
        dreh = m4.mal(m4.drehX(0.1 - vy * 0.16), m4.drehY(st.kurs - 0.25 + Math.sin(t * 0.9) * 0.1));
      }
      const lage = m4.mal(m4.schieben(ort[0], ort[1], ort[2]), m4.mal(dreh, m4.schieben(-modell.mitte[0], -modell.mitte[1], -modell.mitte[2])));
      const kamera = m4.mal(m4.sicht(FOV, b / h, abstand * 0.05, abstand * 4), m4.schieben(0, 0, -abstand));
      gl.useProgram(p);
      gl.uniformMatrix4fv(u.uBild, false, kamera); gl.uniform3fv(u.uAuge, auge); gl.uniform3fv(u.uAkzent, rand);
      teile.forEach(t=>{
        gl.uniformMatrix4fv(u.uWelt, false, m4.mal(lage, t.welt));
        gl.uniform3fv(u.uFarbe, t.farbe); gl.uniform1f(u.uMetall, t.metall); gl.uniform1f(u.uRau, t.rau);
        gl.bindVertexArray(t.vao); gl.drawElements(gl.TRIANGLES, t.anzahl, t.art, t.ab);
      });
      gl.bindVertexArray(null);
    };
    const aufraeumen = ()=>{
      if(st.ende) return;
      st.ende = true; cancelAnimationFrame(st.lauf); if(st.blick) st.blick.disconnect(); if(weit) flug = null;
      document.removeEventListener('visibilitychange', wecken); REGUNG.forEach(n=>root.removeEventListener(n, regung));
      const weg = gl.getExtension('WEBGL_lose_context'); if(weg) weg.loseContext();
    };
    const schritt = zeit=>{
      st.lauf = 0;
      if(st.ende) return;
      if(!rahmenEl.isConnected){ aufraeumen(); return; }
      if(st.t0){ st.zeit += Math.min(zeit - st.t0, 100) / 1000; st.winkel = -0.3 + Math.sin(st.zeit * 0.4) * 0.5; }     // ruhiges Wiegen statt Kreiseln: die Seite bleibt zu sehen
      st.t0 = zeit;
      if(weit && !st.ruhe && zeit - st.letzte > RUHE_MS){ st.ruhe = true; rahmenEl.classList.add('ruhe'); }       // niemand rührt etwas an: der Drache tritt hervor
      bild();
      if(st.sichtbar && document.visibilityState === 'visible') st.lauf = requestAnimationFrame(schritt); else st.t0 = 0;
    };
    function wecken(){ if(!st.ende && !st.lauf && !ruhig() && st.sichtbar && document.visibilityState === 'visible') st.lauf = requestAnimationFrame(schritt); }

    leinwand.addEventListener('webglcontextlost', e=>{ e.preventDefault(); rahmenEl.classList.remove('bereit'); aufraeumen(); });
    function zeigen(e){
      const r = rahmenEl.getBoundingClientRect();
      st.ziel = [((e.clientX - r.left) / r.width - 0.5) * 2, ((e.clientY - r.top) / r.height - 0.5) * 2];
    }
    function regung(){                                         // der Captain arbeitet: der Drache tritt zurück
      st.letzte = root.performance ? root.performance.now() : 0;
      if(st.ruhe){ st.ruhe = false; rahmenEl.classList.remove('ruhe'); }
    }
    if(weit){
      regung(); REGUNG.forEach(n=>root.addEventListener(n, regung, {passive: true}));
      flug = {landen(x, y){ st.platz = [x, y]; rahmenEl.classList.add('gelandet'); }, abheben(){ st.platz = null; rahmenEl.classList.remove('gelandet'); }};
    }
    else { rahmenEl.addEventListener('pointermove', zeigen); rahmenEl.addEventListener('pointerleave', ()=>{ st.ziel = [0, 0]; }); }
    if(root.IntersectionObserver){ st.blick = new IntersectionObserver(e=>{ st.sichtbar = e[0].isIntersecting; wecken(); }); st.blick.observe(rahmenEl); }
    document.addEventListener('visibilitychange', wecken);
    bild();                                                    // das erste Bild sofort – bei „weniger Bewegung“ bleibt es dabei
    rahmenEl.classList.add('bereit');
    wecken();
    return true;
  }

  // Der Rahmen um die Zeichnung: gibt immer ein Element zurück, in dem die Zeichnung steht; das Modell kommt nach, wenn es geht.
  function rahmen(zeichnung){
    const el = document.createElement('div'); el.className = 'hs-buehne';
    el.append(zeichnung);
    const m = modus();
    if(m !== 'buehne') el.classList.add('klein');
    if(m === 'aus' || typeof fetch !== 'function') return el;
    if(m === 'hintergrund'){ hintergrund(); return el; }       // im Startbild bleibt die Zeichnung, der Drache selbst fliegt über das Fenster
    const leinwand = document.createElement('canvas'); leinwand.className = 'hs-buehne-leinwand'; leinwand.setAttribute('aria-hidden', 'true');
    el.append(leinwand);
    laden().then(modell=>{ if(!starten(el, leinwand, modell)) leinwand.remove(); })
      .catch(()=>{ el.classList.remove('bereit'); leinwand.remove(); });          // Rückfall: die Zeichnung bleibt
    return el;
  }

  // Der Drache als Bildschirmschoner (Captain 15.11.): eine Ebene über dem ganzen Fenster, er fliegt auch durch die Menüs. Sie nimmt
  // keine Klicks und keine Tasten; solange der Captain arbeitet, ist der Drache blass, nach RUHE_MS ohne Regung tritt er hervor.
  function hintergrund(){
    const shell = document.querySelector('.hs');
    if(!shell || ruhig()) return Promise.resolve(false);
    if(shell.querySelector('.hs-grund')) return Promise.resolve(true);
    const el = document.createElement('div'); el.className = 'hs-grund'; el.setAttribute('aria-hidden', 'true');
    const leinwand = document.createElement('canvas'); leinwand.className = 'hs-buehne-leinwand';
    el.append(leinwand); shell.append(el);
    return laden().then(modell=>{ const ok = starten(el, leinwand, modell, true); if(!ok) el.remove(); return ok; }).catch(()=>{ el.remove(); return false; });
  }

  root.sedraHarness.buehne3d = {rahmen, hintergrund, modus, MODI, landen: (x, y)=>!!flug && (flug.landen(x, y), true), abheben: ()=>{ if(flug) flug.abheben(); }, glbLesen, teileVon, m4, KEY, MODELL_URL};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.buehne3d;
})();
