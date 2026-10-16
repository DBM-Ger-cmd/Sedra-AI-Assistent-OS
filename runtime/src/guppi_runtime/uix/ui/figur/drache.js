// Der blaue Seedrache – eine Hintergrundfigur für SEDRA (Three.js 0.160.0, von jsdelivr geladen, nur bei Bedarf).
// Verwendung: sedraDrache.mount(container) – die Figur füllt den Container und ist transparent.
// Bewegung: Körper schlängelt sich, Flossen schlagen, Unterkiefer öffnet sich, Lichtpunkte pulsieren, Bläschen steigen.
// Bei „reduzierter Bewegung“ steht alles still. Farben als Zahlen, weil die Figur Bild ist und kein Oberflächenteil.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const THREE_SRC = 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js';
  const SEG = 28;                 // Segmente des Körpers
  const SCALES_PER_SEG = 10;      // Schuppen je Segment (Instanzen, billig)
  const SPOTS = 14;               // leuchtende Punkte an der Flanke
  const BUBBLES = 60;

  // Die Bibliothek lädt einmal; schlägt der Versuch fehl, wird er einmal wiederholt.
  function loadThree(retry){
    if(root.THREE) return Promise.resolve(root.THREE);
    return new Promise((resolve, reject)=>{
      const s = document.createElement('script');
      s.src = THREE_SRC; s.async = true;
      s.onload = ()=>resolve(root.THREE);
      s.onerror = ()=>{ s.remove(); (retry === false ? reject(new Error('three_not_loaded')) : resolve(loadThree(false))); };
      document.head.append(s);
    });
  }

  // Radius eines Segments: vorn dick, hinten dünn
  const radius = t => 0.95 * Math.pow(1 - t, 1.4) + 0.1;

  // Körper und Anbauten: Kugelkette, Schuppen als Instanzen, Stacheln, Leuchtpunkte
  function buildSkin(T, mats){
    const body = [];
    for(let i = 0; i < SEG; i++) body.push(new T.Mesh(new T.SphereGeometry(1, 28, 20), mats.body));
    const scaleGeo = new T.SphereGeometry(0.16, 8, 6);
    scaleGeo.scale(1, 0.45, 1.3);
    const scales = new T.InstancedMesh(scaleGeo, mats.scale, SEG * SCALES_PER_SEG);
    const spines = new T.InstancedMesh(new T.ConeGeometry(0.16, 0.9, 8), mats.spine, Math.ceil(SEG / 2));
    const spots = new T.InstancedMesh(new T.SphereGeometry(0.13, 10, 8), mats.glow, SPOTS);
    return {body, scales, spines, spots};
  }

  // Kopf mit Unterkiefer (öffnet sich), Zähnen, Augen mit Pupille, Kiemen, Hörnern
  function buildHead(T, mats){
    const g = new T.Group();
    const skull = new T.Mesh(new T.SphereGeometry(1, 36, 26), mats.body);
    skull.scale.set(1.3, 0.92, 1.02);
    const snout = new T.Mesh(new T.ConeGeometry(0.6, 1.7, 28), mats.body);
    snout.rotation.z = Math.PI / 2; snout.position.x = 1.55; snout.scale.set(1, 1, 0.92);
    const jaw = new T.Group();
    jaw.position.set(0.4, -0.45, 0);
    const jawMesh = new T.Mesh(new T.ConeGeometry(0.42, 1.5, 24), mats.body);
    jawMesh.rotation.z = Math.PI / 2; jawMesh.position.x = 0.85; jawMesh.scale.set(1, 0.7, 0.9);
    jaw.add(jawMesh);
    for(let k = 0; k < 6; k++){
      const low = new T.Mesh(new T.ConeGeometry(0.05, 0.22, 6), mats.tooth);
      low.rotation.z = Math.PI; low.position.set(0.7 + k * 0.22, -0.28, 0.42 * Math.sin(k * 0.9));
      jaw.add(low);
      const up = new T.Mesh(new T.ConeGeometry(0.05, 0.22, 6), mats.tooth);
      up.position.set(1.0 + k * 0.2, -0.4, 0.36 * Math.cos(k * 0.8));
      snout.add(up);
    }
    g.add(skull, snout, jaw);
    for(const side of [-1, 1]){
      const eye = new T.Mesh(new T.SphereGeometry(0.18, 18, 14), mats.eye);
      eye.position.set(0.6, 0.34, 0.66 * side);
      const pupil = new T.Mesh(new T.SphereGeometry(0.08, 12, 10), mats.pupil);
      pupil.position.set(0.16, 0, 0.1 * side);
      eye.add(pupil);
      g.add(eye);
      for(let k = 0; k < 3; k++){
        const gill = new T.Mesh(new T.TorusGeometry(0.36 + k * 0.08, 0.035, 8, 20, Math.PI * 0.9), mats.glow);
        gill.position.set(-0.45 - k * 0.12, 0.05, 0.62 * side);
        gill.rotation.set(0, side * Math.PI / 2, Math.PI * 0.5 + k * 0.25);
        g.add(gill);
      }
      const horn = new T.Mesh(new T.ConeGeometry(0.11, 1.05, 14), mats.spine);
      horn.position.set(-0.2, 0.95, 0.38 * side); horn.rotation.z = -0.5;
      g.add(horn);
    }
    return {group: g, jaw};
  }

  // Flosse: Membran und Flossenstrahlen als dünne Linien
  function buildFin(T, mat, rayMat, width, rays){
    const g = new T.Group();
    const shape = new T.Shape();
    shape.moveTo(0, 0);
    shape.quadraticCurveTo(width * 0.55, 1.0, width, 0.15);
    shape.quadraticCurveTo(width * 0.6, -0.15, 0, 0);
    g.add(new T.Mesh(new T.ShapeGeometry(shape, 14), mat));
    for(let k = 0; k < rays; k++){
      const t = k / (rays - 1);
      const pts = [new T.Vector3(0, 0, 0.01), new T.Vector3(width * t, 0.9 * (1 - Math.abs(t - 0.4)) + 0.1, 0.01)];
      g.add(new T.Line(new T.BufferGeometry().setFromPoints(pts), rayMat));
    }
    return g;
  }

  function buildTailFin(T, mat){
    const shape = new T.Shape();
    shape.moveTo(0, 0);
    shape.quadraticCurveTo(0.9, 1.4, 1.9, 0.9);
    shape.quadraticCurveTo(1.2, 0.2, 1.9, -0.9);
    shape.quadraticCurveTo(0.9, -1.4, 0, 0);
    const m = mat.clone(); m.side = T.DoubleSide;
    return new T.Mesh(new T.ShapeGeometry(shape, 18), m);
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
      scene.add(new T.HemisphereLight(0x9fe8ff, 0x0b1a2a, 0.9));
      const key = new T.DirectionalLight(0xe8f8ff, 1.2); key.position.set(4, 7, 9); scene.add(key);
      const rim = new T.DirectionalLight(0x4fd6ff, 1.1); rim.position.set(-8, 2, -4); scene.add(rim);

      const mats = {
        body: new T.MeshStandardMaterial({color: 0x1d74c4, roughness: 0.32, metalness: 0.18, emissive: 0x06243d, emissiveIntensity: 0.55}),
        scale: new T.MeshStandardMaterial({color: 0x2a8fd9, roughness: 0.25, metalness: 0.4, transparent: true, opacity: 0.85}),
        spine: new T.MeshStandardMaterial({color: 0x9fe8ff, roughness: 0.4, emissive: 0x0f4a6e, emissiveIntensity: 0.6}),
        glow: new T.MeshStandardMaterial({color: 0x7ff6ff, emissive: 0x2ad8ff, emissiveIntensity: 1.6}),
        eye: new T.MeshStandardMaterial({color: 0xfff3a0, emissive: 0xffd64d, emissiveIntensity: 1.3}),
        pupil: new T.MeshStandardMaterial({color: 0x05080c, roughness: 0.2}),
        tooth: new T.MeshStandardMaterial({color: 0xeef6ff, roughness: 0.3}),
        fin: new T.MeshStandardMaterial({color: 0x59d3ff, roughness: 0.5, emissive: 0x0b3a57, emissiveIntensity: 0.7, transparent: true, opacity: 0.7}),
        rayLine: new T.LineBasicMaterial({color: 0xbff4ff, transparent: true, opacity: 0.8})
      };

      const dragon = new T.Group();
      const skin = buildSkin(T, mats);
      skin.body.forEach(m=>dragon.add(m));
      dragon.add(skin.scales, skin.spines, skin.spots);
      const headParts = buildHead(T, mats);
      dragon.add(headParts.group);
      const finL = buildFin(T, mats.fin, mats.rayLine, 2.7, 5), finR = buildFin(T, mats.fin, mats.rayLine, 2.7, 5);
      const tail = buildTailFin(T, mats.fin);
      dragon.add(finL, finR, tail);
      dragon.scale.setScalar(1.1);
      scene.add(dragon);

      const bubbleGeo = new T.BufferGeometry();
      const bpos = new Float32Array(BUBBLES * 3);
      for(let i = 0; i < BUBBLES; i++){ bpos[i*3] = (Math.random()-0.5)*30; bpos[i*3+1] = (Math.random()-0.5)*18; bpos[i*3+2] = -4 - Math.random()*8; }
      bubbleGeo.setAttribute('position', new T.BufferAttribute(bpos, 3));
      scene.add(new T.Points(bubbleGeo, new T.PointsMaterial({color: 0xbff4ff, size: 0.12, transparent: true, opacity: 0.55})));

      const m4 = new T.Matrix4(), q = new T.Quaternion(), s = new T.Vector3(), p = new T.Vector3();

      function resize(){
        const w = container.clientWidth || 600, h = container.clientHeight || 400;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.position.set(0, 0, Math.max(13, 18 / camera.aspect));
        camera.updateProjectionMatrix();
      }
      resize();
      const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
      if(ro) ro.observe(container);

      // Pose: Körperkette, Schuppen, Stacheln und Lichtpunkte folgen derselben Welle
      function pose(time){
        const c = [];
        for(let i = 0; i < SEG; i++){
          const t = i / (SEG - 1);
          const x = 1.5 - t * 10.5;
          const y = Math.sin(time * 1.6 - i * 0.42) * (0.3 + 0.9 * t);
          const z = Math.sin(time * 1.1 - i * 0.3) * 0.3 * t;
          const r = radius(t);
          skin.body[i].position.set(x, y, z);
          skin.body[i].scale.setScalar(r);
          c.push({x, y, z, r, t});
        }
        let k = 0;
        for(let i = 0; i < SEG; i++){
          const seg = c[i];
          for(let j = 0; j < SCALES_PER_SEG; j++){
            const a = (j / SCALES_PER_SEG) * Math.PI * 2 + i * 0.5;
            p.set(seg.x, seg.y + Math.sin(a) * seg.r * 0.92, seg.z + Math.cos(a) * seg.r * 0.92);
            s.setScalar(0.9 + 0.25 * seg.t);
            m4.compose(p, q.identity(), s);
            skin.scales.setMatrixAt(k++, m4);
          }
        }
        skin.scales.instanceMatrix.needsUpdate = true;
        for(let i = 0; i < Math.ceil(SEG / 2); i++){
          const seg = c[i * 2];
          p.set(seg.x, seg.y + seg.r * 1.05, seg.z);
          s.setScalar(1 - seg.t * 0.5);
          m4.compose(p, q.identity(), s);
          skin.spines.setMatrixAt(i, m4);
        }
        skin.spines.instanceMatrix.needsUpdate = true;
        for(let i = 0; i < SPOTS; i++){
          const seg = c[Math.min(SEG - 1, 2 + i * 2)];
          p.set(seg.x, seg.y + Math.sin(i) * seg.r * 0.4, seg.z + seg.r * 0.95);
          s.setScalar(0.8 + 0.4 * Math.sin(time * 2.4 + i));
          m4.compose(p, q.identity(), s);
          skin.spots.setMatrixAt(i, m4);
        }
        skin.spots.instanceMatrix.needsUpdate = true;
        const h = c[0];
        headParts.group.position.set(h.x + 0.8, h.y, h.z);
        headParts.group.rotation.z = Math.sin(time * 1.6) * 0.12;
        headParts.jaw.rotation.z = -0.15 - 0.12 * (0.5 + 0.5 * Math.sin(time * 2.2));
        const mid = c[Math.floor(SEG / 3)];
        const beat = Math.sin(time * 3.2) * 0.35;
        finL.position.set(mid.x, mid.y + 0.25, mid.z + 0.5); finL.rotation.set(-0.3, 0, 0.45 + beat);
        finR.position.set(mid.x, mid.y + 0.25, mid.z - 0.5); finR.rotation.set(0.3, Math.PI, 0.45 - beat);
        const end = c[SEG - 1];
        tail.position.set(end.x - 0.2, end.y, end.z);
        tail.rotation.z = Math.sin(time * 2.0) * 0.25;
      }

      let running = true, t0 = performance.now(), frame = 0;
      function tick(now){
        if(!running) return;
        const time = reduce ? 0 : (now - t0) / 1000;
        pose(time);
        const pos = bubbleGeo.attributes.position;
        for(let i = 0; i < BUBBLES; i++){
          const y = pos.getY(i) + (reduce ? 0 : 0.02);
          pos.setY(i, y > 9 ? -9 : y);
        }
        pos.needsUpdate = true;
        camera.position.x = reduce ? 0 : Math.sin(time * 0.15) * 1.2;
        camera.lookAt(-3.4, 0, 0);
        renderer.render(scene, camera);
        frame = requestAnimationFrame(tick);
      }
      if(reduce){ pose(0); camera.lookAt(-3.4, 0, 0); renderer.render(scene, camera); }
      else frame = requestAnimationFrame(tick);

      return {
        stop(){ running = false; cancelAnimationFrame(frame); if(ro) ro.disconnect(); renderer.dispose(); canvas.remove(); }
      };
    });
  }

  root.sedraDrache = {mount};
})();
