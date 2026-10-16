// Der blaue Seedrache – eine Hintergrundfigur für SEDRA (Three.js, geladen von cdnjs).
// Verwendung: sedraDrache.mount(container) – die Figur füllt den Container und ist transparent, damit der Hintergrund durchscheint.
// Bewegung: sanftes Schlängeln des Körpers und langsame Kamerafahrt. Bei „reduzierter Bewegung“ steht die Figur still.
// Farben als Zahlen hier, weil die Farbtokens für Oberflächen gelten; die Figur ist Bild, kein Oberflächenteil.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const THREE_SRC = 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js';
  const SEGMENTS = 26;

  function loadThree(){
    if(root.THREE) return Promise.resolve(root.THREE);
    return new Promise((resolve, reject)=>{
      const s = document.createElement('script');
      s.src = THREE_SRC; s.async = true;
      s.onload = ()=>resolve(root.THREE);
      s.onerror = ()=>reject(new Error('three_not_loaded'));
      document.head.append(s);
    });
  }

  // Körper: eine Kette von Kugeln, vorn groß, hinten dünn. Jede Kugel liegt auf einer Wellenlinie.
  function buildBody(T, mat){
    const parts = [];
    for(let i = 0; i < SEGMENTS; i++){
      const t = i / (SEGMENTS - 1);
      const r = 0.9 * (1 - t) * (1 - t) + 0.12;               // Kopf dick, Schwanz dünn
      const m = new T.Mesh(new T.SphereGeometry(r, 24, 16), mat);
      parts.push(m);
    }
    return parts;
  }

  function buildHead(T, mat, eyeMat){
    const g = new T.Group();
    const skull = new T.Mesh(new T.SphereGeometry(1, 32, 24), mat);
    skull.scale.set(1.25, 0.9, 1.0);
    const snout = new T.Mesh(new T.ConeGeometry(0.55, 1.6, 24), mat);
    snout.rotation.z = Math.PI / 2; snout.position.x = 1.45; snout.scale.set(1, 1, 0.9);
    g.add(skull, snout);
    for(const side of [-1, 1]){
      const eye = new T.Mesh(new T.SphereGeometry(0.17, 16, 12), eyeMat);
      eye.position.set(0.55, 0.32, 0.62 * side);
      g.add(eye);
      const horn = new T.Mesh(new T.ConeGeometry(0.1, 0.9, 12), mat);
      horn.position.set(-0.2, 0.9, 0.35 * side); horn.rotation.z = -0.5;
      g.add(horn);
    }
    return g;
  }

  // Flossen: flache Dreiecke an den Seiten des Körpers, schlagen im Takt.
  function buildFin(T, mat, width){
    const shape = new T.Shape();
    shape.moveTo(0, 0); shape.quadraticCurveTo(width * 0.6, 0.9, width, 0.1); shape.quadraticCurveTo(width * 0.5, -0.2, 0, 0);
    const fin = new T.Mesh(new T.ShapeGeometry(shape, 12), mat);
    fin.material = mat.clone(); fin.material.side = T.DoubleSide; fin.material.opacity = 0.75; fin.material.transparent = true;
    return fin;
  }

  function mount(container, opts){
    const o = Object.assign({reduceMotion: false}, opts || {});
    const reduce = o.reduceMotion || (root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches);
    container.style.position = container.style.position || 'relative';
    container.dataset.figur = 'drache';
    return loadThree().then((T)=>{
      const renderer = new T.WebGLRenderer({antialias: true, alpha: true});
      renderer.setPixelRatio(Math.min(root.devicePixelRatio || 1, 2));
      renderer.setClearColor(0x000000, 0);
      const canvas = renderer.domElement;
      canvas.style.width = '100%'; canvas.style.height = '100%'; canvas.style.display = 'block';
      container.append(canvas);

      const scene = new T.Scene();
      const camera = new T.PerspectiveCamera(42, 1, 0.1, 100);
      camera.position.set(0, 0, 13);
      scene.add(new T.HemisphereLight(0x9fe8ff, 0x0b1a2a, 0.9));
      const key = new T.DirectionalLight(0xffffff, 1.1); key.position.set(4, 6, 8); scene.add(key);

      const bodyMat = new T.MeshStandardMaterial({color: 0x1f7fd1, roughness: 0.35, metalness: 0.15, emissive: 0x06243d, emissiveIntensity: 0.6});
      const finMat = new T.MeshStandardMaterial({color: 0x59d3ff, roughness: 0.5, emissive: 0x0b3a57, emissiveIntensity: 0.8});
      const eyeMat = new T.MeshStandardMaterial({color: 0xfff3a0, emissive: 0xffd64d, emissiveIntensity: 1.2});

      const dragon = new T.Group();
      const body = buildBody(T, bodyMat);
      body.forEach(m=>dragon.add(m));
      const head = buildHead(T, bodyMat, eyeMat);
      dragon.add(head);
      const finL = buildFin(T, finMat, 2.6), finR = buildFin(T, finMat, 2.6);
      dragon.add(finL, finR);
      dragon.scale.setScalar(1.3); scene.add(dragon);

      // Meeresgrund-Schimmer: ein paar weiche Lichtpunkte im Hintergrund
      const dotsGeo = new T.BufferGeometry();
      const pts = new Float32Array(300 * 3);
      for(let i = 0; i < 300; i++){ pts[i*3] = (Math.random()-0.5)*40; pts[i*3+1] = (Math.random()-0.5)*24; pts[i*3+2] = -6 - Math.random()*12; }
      dotsGeo.setAttribute('position', new T.BufferAttribute(pts, 3));
      scene.add(new T.Points(dotsGeo, new T.PointsMaterial({color: 0x7fd8ff, size: 0.08, transparent: true, opacity: 0.6})));

      function resize(){
        const w = container.clientWidth || 600, h = container.clientHeight || 400;
        renderer.setSize(w, h, false); camera.aspect = w / h; camera.position.z = Math.max(13, 18 / camera.aspect); camera.updateProjectionMatrix();
      }
      resize();
      const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
      if(ro) ro.observe(container);

      // Der Körper: jede Kugel folgt einer Welle, die von vorn nach hinten läuft.
      function pose(time){
        body.forEach((m, i)=>{
          const t = i / (SEGMENTS - 1);
          const x = 1.5 - t * 9.5;
          const wave = Math.sin(time * 1.6 - i * 0.45) * (0.35 + 0.9 * t);
          m.position.set(x, wave, Math.sin(time * 1.1 - i * 0.3) * 0.25 * t);
        });
        head.position.set(body[0].position.x + 0.9, body[0].position.y, body[0].position.z);
        head.rotation.z = Math.sin(time * 1.6) * 0.12;
        const beat = Math.sin(time * 3.2) * 0.35;
        const mid = body[Math.floor(SEGMENTS / 3)].position;
        finL.position.set(mid.x, mid.y + 0.2, mid.z + 0.5); finL.rotation.set(-0.3, 0, 0.4 + beat);
        finR.position.set(mid.x, mid.y + 0.2, mid.z - 0.5); finR.rotation.set(0.3, Math.PI, 0.4 - beat);
      }

      let running = true, t0 = performance.now(), frame = 0;
      function tick(now){
        if(!running) return;
        const time = reduce ? 0 : (now - t0) / 1000;
        pose(time);
        camera.position.x = Math.sin(time * 0.15) * 1.2;
        camera.lookAt(-2.6, 0, 0);
        renderer.render(scene, camera);
        frame = requestAnimationFrame(tick);
      }
      if(reduce){ pose(0); camera.lookAt(-2.6, 0, 0); renderer.render(scene, camera); }
      else frame = requestAnimationFrame(tick);

      return {
        stop(){ running = false; cancelAnimationFrame(frame); if(ro) ro.disconnect(); renderer.dispose(); canvas.remove(); }
      };
    });
  }

  root.sedraDrache = {mount};
})();
