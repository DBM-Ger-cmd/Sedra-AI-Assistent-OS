// Cockpit shell – der Rahmen um die Zonen (SPEC_COCKPIT_BAUM_v1 §3.6, §3.8; T3, Logbucheintrag zu COCKPIT_MODUL_v1 §1):
// - das Gespräch ist aufziehbar (§1 „aufziehbar“ nachgeholt): ein Griff an der Oberkante, 2 Zeilen bis 50 % des Fensters, Doppelklick
//   setzt zurück; gemerkt in localStorage `sedra.cockpit.gespraech` (nur die Höhe);
// - der Baum blendet sich mit Strg+B oder dem Knopf am Rand aus und ein; ausgeblendet bleibt ein schmaler Rand, die Zonen bleiben;
// - „?“ öffnet die Übersicht der Kürzel (Knopf in der Leiste oder die Taste, wenn kein Eingabefeld den Fokus hat).
// `hoeheBegrenzen` und `tippt` sind rein.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const GESPRAECH = 'sedra.cockpit.gespraech';
  const MIN_HOEHE = 64;                                  // zwei Zeilen
  const KUERZEL = [
    ['Strg+K', 'Palette: einen Ort, eine Aufgabe, „?“ für das Wissen, oder ein Auftrag'],
    ['Strg+B', 'den Baum aus- und einblenden'],
    ['Alt+S', 'Oberfläche wechseln, Darstellung, Schrift'],
    ['Enter', 'im Gespräch: senden · im Baum: öffnen'],
    ['↑ ↓ ← →', 'im Baum: Zeile wechseln, Gruppe zu und auf'],
    ['Pos1 · Ende', 'im Baum: erste und letzte Zeile'],
    ['Esc', 'Palette, Menü oder diese Übersicht schließen'],
    ['mittlere Maustaste', 'am Reiter: schließen'],
    ['?', 'diese Übersicht']
  ];

  // die Höhe des Gesprächs (rein): mindestens zwei Zeilen, höchstens die Hälfte des Fensters
  function hoeheBegrenzen(px, fenster){
    const max = Math.max(MIN_HOEHE, Math.floor((fenster || 800) / 2));
    const n = Math.round(Number(px) || 0);
    return Math.max(MIN_HOEHE, Math.min(max, n));
  }
  // tippt der Captain gerade (dann gehört „?“ dem Feld)?
  function tippt(ziel){
    if(!ziel || !ziel.tagName) return false;
    return ['INPUT', 'TEXTAREA', 'SELECT'].indexOf(ziel.tagName) >= 0 || ziel.isContentEditable === true;
  }

  function lesen(){ try{ return localStorage.getItem(GESPRAECH); }catch(_e){ return null; } }
  function schreiben(v){ try{ if(v === null) localStorage.removeItem(GESPRAECH); else localStorage.setItem(GESPRAECH, String(v)); }catch(_e){} }

  function einrichten(shell){
    const host = shell.host;
    const setze = px=>{ if(px === null){ host.style.removeProperty('--talk-h'); return; } host.style.setProperty('--talk-h', hoeheBegrenzen(px, root.innerHeight) + 'px'); };
    const gemerkt = Number(lesen());
    if(gemerkt) setze(gemerkt);

    // ---- der Griff an der Oberkante des Gesprächs
    const griff = d().el('div', 'ck-griff');
    griff.setAttribute('role', 'separator'); griff.setAttribute('aria-orientation', 'horizontal');
    griff.setAttribute('aria-label', 'Höhe des Gesprächs – ziehen, Pfeiltasten, Doppelklick setzt zurück'); griff.tabIndex = 0;
    griff.title = 'Gespräch aufziehen · Doppelklick: zurück';
    const jetzt = ()=>shell.el.talk.getBoundingClientRect().height;
    griff.onpointerdown = e=>{
      e.preventDefault();
      const y0 = e.clientY, h0 = jetzt();
      const zieh = ev=>setze(h0 + (y0 - ev.clientY));
      const los = ()=>{ document.removeEventListener('pointermove', zieh); document.removeEventListener('pointerup', los); schreiben(Math.round(jetzt())); };
      document.addEventListener('pointermove', zieh); document.addEventListener('pointerup', los);
    };
    griff.ondblclick = ()=>{ setze(null); schreiben(null); };
    griff.onkeydown = e=>{
      if(e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
      e.preventDefault(); setze(jetzt() + (e.key === 'ArrowUp' ? 24 : -24)); schreiben(Math.round(jetzt()));
    };
    host.append(griff);                                 // absolut über der Oberkante: keine Zelle im Raster

    // ---- Baum aus und ein
    const knopf = d().el('button', 'ck-baum-knopf', '‹'); knopf.type = 'button';
    const zeigeBaum = aus=>{
      host.classList.toggle('ck-ohne-baum', !!aus);
      knopf.textContent = aus ? '›' : '‹';
      knopf.title = (aus ? 'Baum einblenden' : 'Baum ausblenden') + ' (Strg+B)';
      knopf.setAttribute('aria-label', knopf.title); knopf.setAttribute('aria-expanded', aus ? 'false' : 'true');
    };
    knopf.onclick = ()=>baumUmschalten();
    host.append(knopf);
    function baumUmschalten(){
      const aus = shell.tree.ausblenden();
      zeigeBaum(aus);
      if(!aus){ const z = shell.el.tree.querySelector('[role=treeitem][tabindex="0"]'); if(z) z.focus(); }
      return aus;
    }
    zeigeBaum(shell.tree.ausgeblendet());

    // ---- Übersicht der Kürzel
    let ueber = null;
    function kuerzel(){
      if(ueber){ ueber.remove(); ueber = null; return; }
      ueber = d().el('div', 'pal ck-kuerzel'); ueber.setAttribute('role', 'dialog'); ueber.setAttribute('aria-label', 'Tastenkürzel');
      const box = d().el('div', 'pal-box');
      box.append(d().el('b', null, 'Tastenkürzel'));
      const tab = d().el('table', 's-table');
      KUERZEL.forEach(([k, was])=>{ const tr = d().el('tr'); tr.append(d().el('td', null, k), d().el('td', 's-muted', was)); tab.append(tr); });
      const zu = d().button('Schließen', ()=>kuerzel());
      box.append(tab, zu);
      ueber.append(box);
      ueber.onmousedown = e=>{ if(e.target === ueber) kuerzel(); };
      ueber.onkeydown = e=>{ if(e.key === 'Escape'){ e.preventDefault(); kuerzel(); } };
      document.body.append(ueber);
      zu.focus();
    }

    shell.rahmen = {baumUmschalten, kuerzel, setze};
    return shell.rahmen;
  }

  root.sedraCockpitRahmen = {einrichten, hoeheBegrenzen, tippt, KUERZEL};
  if(typeof module !== 'undefined' && module.exports) module.exports = {hoeheBegrenzen, tippt, KUERZEL};
})();
