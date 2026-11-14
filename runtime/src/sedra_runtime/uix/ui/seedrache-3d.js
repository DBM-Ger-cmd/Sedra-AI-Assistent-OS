// Seedrache 3D – Progressive Enhancement für den Startbildschirm
// Lazy-loaded Three.js Wrapper, nur bei Einstellung "3D-Startbildschirm" + !reduced-motion

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  
  let threeLoaded = false;
  let scene = null, camera = null, renderer = null, dracheMesh = null;
  let animationId = null;
  let container = null;
  
  // Prüfen ob 3D aktiviert werden soll
  function shouldEnable3D() {
    if (!root.sedraSettings) return false;
    return root.sedraSettings.get('startbildschirm3d') === true;
  }
  
  // Prüfen ob reduced-motion
  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }
  
  // Prüfen WebGL2 Support
  function hasWebGL2() {
    try {
      const canvas = document.createElement('canvas');
      return !!canvas.getContext('webgl2');
    } catch (e) {
      return false;
    }
  }
  
  // Three.js lazy laden
  async function loadThree() {
    if (threeLoaded) return true;
    
    try {
      // Three.js über CDN laden (oder lokal wenn verfügbar)
      await loadScript('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js');
      threeLoaded = true;
      return true;
    } catch (e) {
      console.warn('Three.js konnte nicht geladen werden:', e);
      return false;
    }
  }
  
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) {
        resolve();
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }
  
  // Seedrache 3D initialisieren
  async function initSeedrache3D(targetContainer) {
    if (!shouldEnable3D()) return false;
    if (prefersReducedMotion()) return false;
    if (!hasWebGL2()) return false;
    
    const loaded = await loadThree();
    if (!loaded) return false;
    
    container = targetContainer;
    
    // Scene setup
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 2, 5);
    
    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);
    
    // Lights
    const ambient = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambient);
    
    const dirLight = new THREE.DirectionalLight(0xffffff, 1);
    dirLight.position.set(5, 10, 7);
    dirLight.castShadow = true;
    scene.add(dirLight);
    
    // GLB laden
    try {
      const loader = new THREE.GLTFLoader();
      const glb = await loadGLB('/uix/shells/harness/assets/seedrache-web.glb');
      dracheMesh = glb.scene;
      dracheMesh.scale.set(1, 1, 1);
      dracheMesh.position.set(0, -0.5, 0);
      scene.add(dracheMesh);
      
      // Materialien theme-fähig machen
      updateMaterialsForTheme();
      
      // Animation starten
      animate();
      
      // Resize Handler
      window.addEventListener('resize', onResize);
      
      // Theme-Change Listener
      document.addEventListener('themechange', updateMaterialsForTheme);
      
      return true;
    } catch (e) {
      console.warn('Seedrache GLB konnte nicht geladen werden:', e);
      cleanup();
      return false;
    }
  }
  
  function loadGLB(url) {
    return new Promise((resolve, reject) => {
      const loader = new THREE.GLTFLoader();
      loader.load(url, resolve, undefined, reject);
    });
  }
  
  // Materialien an Theme anpassen
  function updateMaterialsForTheme() {
    if (!dracheMesh) return;
    
    const accentColor = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
    const textColor = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
    
    dracheMesh.traverse((child) => {
      if (child.isMesh && child.material) {
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach(mat => {
          if (mat.name && mat.name.includes('koerper')) {
            mat.color.set(accentColor);
          } else if (mat.name && mat.name.includes('auge')) {
            mat.color.set(textColor);
          }
        });
      }
    });
  }

  function animate() {
    animationId = requestAnimationFrame(animate);
    
    if (dracheMesh) {
      // Subtile Rotation
      dracheMesh.rotation.y += 0.0005;
      // Subtle "Atmen"
      dracheMesh.scale.y = 1 + Math.sin(Date.now() * 0.0005) * 0.01;
    }
    
    renderer.render(scene, camera);
  }
  
  function onResize() {
    if (!container || !camera || !renderer) return;
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
  }
  
  function cleanup() {
    if (animationId) cancelAnimationFrame(animationId);
    if (renderer) renderer.dispose();
    if (container && renderer) container.removeChild(renderer.domElement);
    window.removeEventListener('resize', onResize);
    document.removeEventListener('themechange', updateMaterialsForTheme);
    scene = null;
    camera = null;
    renderer = null;
    dracheMesh = null;
    container = null;
  }
  
  // Public API
  root.sedraSeedrache3D = {
    init: initSeedrache3D,
    cleanup,
    updateTheme: updateMaterialsForTheme
  };
})();