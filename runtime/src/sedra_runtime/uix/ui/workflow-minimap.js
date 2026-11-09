// Die Minimap der Workflow-Darstellungen lässt sich verschieben: ein Griff oben links, ziehen mit der Maus oder mit den Pfeiltasten.
// Die Lage merkt sich der Browser je Darstellung als Anteil der Fläche (nur eine Annehmlichkeit, nie Inhalt; fehlt der Speicher, bleibt sie
// unten rechts). `begrenze` und `anteile` sind rein: die Minimap bleibt ganz in der Fläche.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const SCHRITT = 16;

  // Position (links, oben) so begrenzen, dass die Minimap ganz in der Fläche liegt (rein)
  function begrenze(links, oben, flaeche, kiste, rand){
    const r = rand === undefined ? 4 : rand;
    return [Math.max(r, Math.min(links, flaeche[0] - kiste[0] - r)), Math.max(r, Math.min(oben, flaeche[1] - kiste[1] - r))];
  }
  // Lage als Anteil des freien Platzes (0 bis 1), damit sie bei anderer Fensterbreite sinnvoll bleibt (rein)
  function anteile(links, oben, flaeche, kiste){
    const fx = Math.max(1, flaeche[0] - kiste[0]), fy = Math.max(1, flaeche[1] - kiste[1]);
    return [Math.max(0, Math.min(1, links / fx)), Math.max(0, Math.min(1, oben / fy))];
  }
  const aus = (a, flaeche, kiste)=>[a[0] * Math.max(0, flaeche[0] - kiste[0]), a[1] * Math.max(0, flaeche[1] - kiste[1])];

  function lesen(key){ try{ const v = JSON.parse(root.localStorage.getItem(key)); return Array.isArray(v) && v.length === 2 && v.every(x=>typeof x === 'number' && isFinite(x)) ? v : null; }catch(e){ return null; } }
  function schreiben(key, v){ try{ root.localStorage.setItem(key, JSON.stringify(v)); }catch(e){} }

  // Griff an die Minimap setzen. flaeche: das Element, in dem sie liegt (position: relative), key: Speicherschlüssel
  function ziehbar(mini, flaeche, key){
    const griff = document.createElement('button');
    griff.type = 'button'; griff.className = 't-wf-mini-grip'; griff.textContent = '⠿';
    griff.setAttribute('aria-label', 'Minimap verschieben (Pfeiltasten verschieben, Pos1 setzt zurück)'); griff.title = 'Minimap verschieben';
    mini.append(griff);
    const maße = ()=>{ const f = flaeche.getBoundingClientRect(), m = mini.getBoundingClientRect(); return {f: [f.width, f.height], m: [m.width, m.height], l: m.left - f.left, o: m.top - f.top}; };
    const setze = (l, o, merken)=>{
      const g = maße(), p = begrenze(l, o, g.f, g.m);
      mini.style.left = p[0] + 'px'; mini.style.top = p[1] + 'px'; mini.style.right = 'auto'; mini.style.bottom = 'auto';
      if(merken) schreiben(key, anteile(p[0], p[1], g.f, g.m));
    };
    const zurueck = ()=>{ mini.style.left = mini.style.top = ''; mini.style.right = mini.style.bottom = ''; try{ root.localStorage.removeItem(key); }catch(e){} };
    let start = null;
    griff.addEventListener('pointerdown', e=>{
      if(e.button !== undefined && e.button !== 0) return;
      e.preventDefault(); e.stopPropagation();
      const g = maße(); start = {x: e.clientX, y: e.clientY, l: g.l, o: g.o};
      try{ griff.setPointerCapture(e.pointerId); }catch(err){}
    });
    griff.addEventListener('pointermove', e=>{ if(start) setze(start.l + e.clientX - start.x, start.o + e.clientY - start.y, false); });
    const ende = e=>{ if(!start) return; const g = maße(); start = null; setze(g.l, g.o, true); try{ griff.releasePointerCapture(e.pointerId); }catch(err){} };
    griff.addEventListener('pointerup', ende); griff.addEventListener('pointercancel', ende);
    griff.addEventListener('keydown', e=>{
      const d = {ArrowLeft: [-SCHRITT, 0], ArrowRight: [SCHRITT, 0], ArrowUp: [0, -SCHRITT], ArrowDown: [0, SCHRITT]}[e.key];
      if(e.key === 'Home'){ e.preventDefault(); zurueck(); return; }
      if(!d) return;
      e.preventDefault(); const g = maße(); setze(g.l + d[0], g.o + d[1], true);
    });
    // gemerkte Lage wiederherstellen, sobald die Fläche Maße hat
    const gemerkt = lesen(key);
    if(gemerkt){ const spaeter = ()=>{ const g = maße(); if(g.f[0] > 0 && g.m[0] > 0){ const p = aus(gemerkt, g.f, g.m); setze(p[0], p[1], false); } }; if(root.requestAnimationFrame) root.requestAnimationFrame(spaeter); else spaeter(); }
    return {griff, zurueck, setze};
  }

  root.sedraWorkflowMinimap = {ziehbar, begrenze, anteile};
  if(typeof module !== 'undefined' && module.exports) module.exports = {begrenze, anteile};
})();
