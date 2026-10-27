// UI-Vertrag 1.1 – die Leiste ordnet sich (SPEC_UIX_STUFE6_RAHMEN_v1 §2.1, Befund A1).
//
// Eine Leiste mit vielen Instrumenten schneidet sonst jeden Wert ab („Modell kein…“). Hier: Passt nicht alles hinein, wandern die Zellen
// mit dem höchsten `order` in eine letzte Zelle „+n ▾“; ein Klick zeigt sie darunter, lebendig (dieselben Zellen, nicht Kopien).
// Eine Zelle mit Ton warn oder bad wandert nie – was wartet, bleibt sichtbar. Gemessen wird beim Start, nach jedem Auffrischen der
// Leiste und bei Größenänderung (gebündelt). `verteilen` ist rein und wird mit node geprüft. Classic script: window.sedraLeiste.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const LAUT = ['warn', 'bad'];

  // rein: zellen [{id, order, ton, breite}], platz in px, mehrBreite = Breite der Zelle „+n“, luecke = Abstand zwischen Zellen
  // → {sichtbar: [ids in Eingabereihenfolge], mehr: [ids nach order aufsteigend]}
  function verteilen(zellen, platz, mehrBreite, luecke){
    const gap = luecke || 0;
    const summe = liste=>liste.reduce((s, z)=>s + (Number(z.breite) || 0), 0) + gap * Math.max(0, liste.length - 1);
    const alle = (zellen || []).slice();
    if(summe(alle) <= platz) return {sichtbar: alle.map(z=>z.id), mehr: []};
    const raus = new Set();
    // nie hinaus: Ton warn/bad (was wartet, bleibt sichtbar) und feste Zellen (ein abgeschotteter Rahmen lädt beim Umziehen neu)
    const kandidaten = alle.filter(z=>LAUT.indexOf(z.ton) < 0 && !z.fest).sort((a, b)=>(b.order || 0) - (a.order || 0));
    let rest = alle.slice();
    const breite = ()=>summe(rest) + gap + (Number(mehrBreite) || 0);
    for(const z of kandidaten){
      if(breite() <= platz) break;
      raus.add(z.id); rest = rest.filter(x=>x.id !== z.id);
    }
    return {sichtbar: rest.map(z=>z.id), mehr: alle.filter(z=>raus.has(z.id)).sort((a, b)=>(a.order || 0) - (b.order || 0)).map(z=>z.id)};
  }

  // im Browser: host ist die Leiste; zellen() liefert die Zellen [{el, id, order}] in ihrer Reihenfolge; klasse ist die Klasse einer Zelle
  function makeLeiste(host, zellen, klasse){
    if(typeof document === 'undefined' || !host) return {ordnen(){}, zu(){}};
    const mehr = document.createElement('button'); mehr.type = 'button';
    mehr.className = (klasse || '') + ' lst-mehr'; mehr.hidden = true; mehr.dataset.tool = 'weitere';
    // wie eine Zelle gebaut: Beschriftung klein, Wert groß – so liest sie sich wie die anderen Instrumente
    const mehrText = n=>{ const k = document.createElement('small'), w = document.createElement('b'); k.textContent = 'Weitere'; w.textContent = '+' + n + ' ▾'; mehr.replaceChildren(k, w); }; mehr.setAttribute('aria-haspopup', 'true'); mehr.setAttribute('aria-expanded', 'false');
    const panel = document.createElement('div'); panel.className = 'lst-panel'; panel.hidden = true; panel.setAttribute('role', 'group'); panel.setAttribute('aria-label', 'Weitere Instrumente');
    document.body.append(panel);
    let versteckt = [];
    const ton = el=>LAUT.find(t=>el.classList.contains(t)) || '';

    function zu(){
      if(panel.hidden) return;
      versteckt.forEach(z=>{ z.el.classList.add('lst-weg'); z.platz.after(z.el); z.platz.remove(); });
      panel.replaceChildren(); panel.hidden = true; mehr.setAttribute('aria-expanded', 'false');
    }
    function auf(){
      // dieselben Zellen ziehen um (sie bleiben lebendig); an ihrem Platz steht solange ein Merker
      versteckt.forEach(z=>{ z.platz = document.createComment('lst'); z.el.before(z.platz); z.el.classList.remove('lst-weg'); panel.append(z.el); });
      const r = mehr.getBoundingClientRect();
      panel.style.top = Math.round(r.bottom + 4) + 'px';
      panel.style.left = Math.max(8, Math.round(Math.min(r.left, root.innerWidth - 300))) + 'px';
      panel.hidden = false; mehr.setAttribute('aria-expanded', 'true');
    }
    mehr.onclick = e=>{ e.stopPropagation(); panel.hidden ? auf() : zu(); };
    document.addEventListener('mousedown', e=>{ if(!panel.hidden && !panel.contains(e.target) && e.target !== mehr) zu(); });
    document.addEventListener('keydown', e=>{ if(e.key === 'Escape' && !panel.hidden){ zu(); mehr.focus(); } });

    function ordnen(){
      zu();
      const liste = zellen();
      if(!liste.length){ mehr.hidden = true; return; }
      const letzte = liste[liste.length - 1].el;
      if(mehr.previousSibling !== letzte) letzte.after(mehr);
      // natürliche Breite messen: jede Zelle sichtbar und ohne Schrumpfen
      // gemessen wird Beschriftung und Wert; die dritte Zeile (Hinweis) passt sich der Breite an und steht ganz im title
      liste.forEach(z=>{ z.el.classList.remove('lst-weg'); z.el.style.maxWidth = ''; z.el.classList.add('lst-messen'); });
      mehr.hidden = false; mehrText(99); mehr.classList.add('lst-messen');
      const cs = getComputedStyle(host);
      const luecke = parseFloat(cs.columnGap || cs.gap) || 0;
      const fremd = [...host.children].filter(c=>c !== mehr && !liste.some(z=>z.el === c) && !c.hidden && getComputedStyle(c).display !== 'none').reduce((s, c)=>s + c.getBoundingClientRect().width + luecke, 0);
      const RAND = 12;                                    // feste Ränder der Nachbarn (margin) und Rundung: lieber eine Zelle mehr in „+n“
      const platz = host.clientWidth - parseFloat(cs.paddingLeft || 0) - parseFloat(cs.paddingRight || 0) - fremd - RAND;
      const daten = liste.map(z=>({id: z.id, order: z.order, ton: ton(z.el), fest: !!z.el.querySelector('iframe'), breite: z.el.getBoundingClientRect().width}));
      const mehrBreite = mehr.getBoundingClientRect().width;
      liste.forEach(z=>z.el.classList.remove('lst-messen')); mehr.classList.remove('lst-messen');
      const v = verteilen(daten, platz, mehrBreite, luecke);
      versteckt = liste.filter(z=>v.mehr.indexOf(z.id) >= 0);
      versteckt.forEach(z=>{ z.el.classList.add('lst-weg'); });
      liste.forEach((z, i)=>{ if(versteckt.indexOf(z) < 0) z.el.style.maxWidth = Math.ceil(daten[i].breite) + 'px'; });
      mehr.hidden = !versteckt.length;
      mehrText(versteckt.length);
      const namen = versteckt.map(z=>{ const s = z.el.querySelector('small'); return (s && s.textContent) || z.id; });
      mehr.title = versteckt.length ? 'Weitere Instrumente: ' + namen.join(', ') : '';
      mehr.setAttribute('aria-label', mehr.title || 'Weitere Instrumente');
    }

    const buendel = root.sedraLifecycle && root.sedraLifecycle.buendeln ? root.sedraLifecycle.buendeln(ordnen, 200) : ordnen;
    if(typeof ResizeObserver !== 'undefined') new ResizeObserver(()=>buendel()).observe(host);
    root.addEventListener('sedra:leiste', ()=>buendel());           // Rekorder und Umschalter sind dazugekommen (ui/wechsel.js)
    return {ordnen, bald: buendel, zu, mehr, panel};
  }

  root.sedraLeiste = {verteilen, makeLeiste};
  if(typeof module !== 'undefined' && module.exports) module.exports = {verteilen};
})();
