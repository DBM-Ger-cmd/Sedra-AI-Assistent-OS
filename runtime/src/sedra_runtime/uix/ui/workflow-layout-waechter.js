// Aufbau-Wächter der Workflow-Darstellung: misst, ob ein Aufbau lesbar ist, und sucht bei Bedarf einen besseren. Rein und ohne DOM.
//
// Das Auge sieht „Liniengewirr", wenn Linien einander kreuzen, übereinanderliegen, durch Kacheln laufen oder große Umwege gehen.
// Der Wächter zählt genau das an den Wegen, die wirklich gezeichnet werden (`routen` führt dieselbe Kantenführung aus wie die
// Zeichenfläche), und gibt einen Befund mit Zahlen und Klartext zurück. `besser` probiert Abstände und Zeilenreihenfolgen durch und
// nimmt den Aufbau mit dem kleinsten Wert; Knoten, Verbindungen und die gespeicherte Revision verändert er nie, nur Positionen einer Kopie.
//
//   pruefe(doc, G)  -> {ok, wert, kreuzungen, ueberlappungen, durchKnoten, umwege, meldungen[]}
//   besser(doc, G)  -> {doc, befund, vorher}      (doc: Kopie mit neuen Positionen)

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const NOTIZ = /\.stickyNote$/;
  const TILE = {w: 96, h: 96, out: (i, n)=>[96, n === 2 ? 32 + i * 32 : 48], inn: [0, 48]};
  // Grenzen: was noch als aufgeräumt gilt. Kreuzungen sind in Verzweigungen manchmal unvermeidbar, Überlappungen und Linien durch
  // Kacheln nie.
  // Jede Schleife (Rücksprung) darf ihre Bahn unter dem Graphen zwei Vorwärtskanten kreuzen lassen.
  const GRENZE = {kreuzungen: 2, je_schleife: 2, ueberlappungen: 0, durchKnoten: 0, umwege: 1, laenge: 3};
  const CIRCLE = {w: 120, h: 120, out: (i, n)=>[118, n === 2 ? 40 + i * 40 : 60], inn: [2, 60]};

  const Lay = ()=>root.sedraWorkflowLayout || (typeof require !== 'undefined' ? require('./workflow-layout.js') : null);

  // Die Wege aller Kanten, wie die Zeichenfläche sie führt (workflow-canvas.js, Kantenführung). Rückgabe: {wege: [{von, nach, art, punkte, rueck}], kisten}
  function routen(doc, G){
    const g = G || TILE, L = Lay(), hoehe = g.h + 34;
    const knoten = doc.nodes.filter(n=>!NOTIZ.test(n.type)), nach = new Map(knoten.map(n=>[n.name, n]));
    const kisten = knoten.map(n=>({n: n.name, r: [n.position[0], n.position[1], g.w, hoehe]}));
    const boden = kisten.length ? Math.max(...kisten.map(k=>k.r[1] + hoehe)) + 28 : 0;
    const zeilenY = [...new Set(kisten.map(k=>k.r[1]))].sort((p, q)=>p - q), quer = [];
    zeilenY.forEach((y, i)=>{ const next = zeilenY[i + 1]; if(next !== undefined && next - (y + hoehe) >= 16) quer.push((y + hoehe + next) / 2); });
    if(zeilenY.length) quer.push(zeilenY[0] - 24);
    let bahnen = 0;
    const gassen = new Map(), wege = [];
    Object.entries(doc.connections || {}).forEach(([quelle, aus])=>Object.entries(aus || {}).forEach(([art, zweige])=>(zweige || []).forEach((zweig, index)=>(zweig || []).forEach(k=>{
      const a = nach.get(quelle), b = nach.get(k.node); if(!a || !b || a === b) return;
      const zahl = a.type.endsWith('.if') ? 2 : 1, o = g.out(Math.min(index, zahl - 1), zahl);
      const x = a.position[0] + o[0], y = a.position[1] + o[1], tx = b.position[0] + g.inn[0], ty = b.position[1] + g.inn[1];
      const rueck = tx - x < L.VORWAERTS, gasse = gassen.get(Math.round(x)) || 0; gassen.set(Math.round(x), gasse + 1);
      let punkte;
      if(art === 'ai_languageModel') punkte = [[a.position[0] + g.w / 2, a.position[1]], [b.position[0] + g.w / 2, b.position[1] + g.h]];
      else punkte = L.fuehren([x, y], [tx, ty], kisten.filter(q=>q.n !== quelle && q.n !== k.node).map(q=>q.r),
        {boden, bahn: rueck ? bahnen++ : 0, querbahnen: quer, stub: (zahl === 2 ? 40 : 20) + gasse * 9, versatz: gasse * 7});
      wege.push({von: quelle, nach: k.node, art, punkte, rueck});
    }))));
    return {wege, kisten};
  }

  // ---- Geometrie der achsparallelen Segmente
  function segmente(punkte){ const s = []; for(let i = 0; i + 1 < punkte.length; i++) s.push([punkte[i], punkte[i + 1]]); return s; }
  const waagerecht = s=>s[0][1] === s[1][1];
  const bereich = (s, i)=>[Math.min(s[0][i], s[1][i]), Math.max(s[0][i], s[1][i])];

  // Zwei Segmente verschiedener Kanten: kreuzen sie sich (senkrecht gegeneinander, Enden zählen nicht), liegen sie übereinander (gleiche Gerade)?
  function paar(s, t){
    if(waagerecht(s) !== waagerecht(t)){
      const [h, v] = waagerecht(s) ? [s, t] : [t, s];
      const [hx0, hx1] = bereich(h, 0), [vy0, vy1] = bereich(v, 1), y = h[0][1], x = v[0][0];
      return x > hx0 + 1 && x < hx1 - 1 && y > vy0 + 1 && y < vy1 - 1 ? 'kreuz' : null;
    }
    const i = waagerecht(s) ? 1 : 0, j = 1 - i;       // i: feste Achse, j: Laufrichtung
    if(Math.abs(s[0][i] - t[0][i]) > 1) return null;
    const [a0, a1] = bereich(s, j), [b0, b1] = bereich(t, j);
    return Math.min(a1, b1) - Math.max(a0, b0) > 4 ? 'ueberlappt' : null;
  }
  const trifft = (s, r, m)=>{
    const [x0, x1] = bereich(s, 0), [y0, y1] = bereich(s, 1);
    return x1 > r[0] - m && x0 < r[0] + r[2] + m && y1 > r[1] - m && y0 < r[1] + r[3] + m;
  };
  const laenge = p=>p.reduce((s, q, i)=>i ? s + Math.abs(q[0] - p[i - 1][0]) + Math.abs(q[1] - p[i - 1][1]) : 0, 0);

  // Befund für fertige Wege. wege: [{von, nach, punkte}], kisten: [{n, r}]
  function pruefeWege(wege, kisten, o){
    const grenze = Object.assign({}, GRENZE, o || {});
    let kreuzungen = 0, ueberlappungen = 0, durchKnoten = 0, umwege = 0;
    const segs = wege.map(w=>segmente(w.punkte));
    for(let a = 0; a < wege.length; a++){
      for(let b = a + 1; b < wege.length; b++){
        const gemeinsam = wege[a].von === wege[b].von || wege[a].nach === wege[b].nach;   // Kanten desselben Ausgangs/Eingangs dürfen sich am Ende berühren
        segs[a].forEach(s=>segs[b].forEach(t=>{ const e = paar(s, t); if(e === 'kreuz') kreuzungen++; else if(e === 'ueberlappt' && !gemeinsam) ueberlappungen++; }));
      }
      segs[a].forEach(s=>kisten.forEach(k=>{ if(k.n !== wege[a].von && k.n !== wege[a].nach && trifft(s, k.r, 2)) durchKnoten++; }));
      const p = wege[a].punkte, luft = Math.abs(p[0][0] - p[p.length - 1][0]) + Math.abs(p[0][1] - p[p.length - 1][1]);
      if(luft > 0 && laenge(p) / luft > grenze.laenge && laenge(p) - luft > 160) umwege++;
    }
    const wert = durchKnoten * 20 + ueberlappungen * 8 + kreuzungen * 3 + umwege * 4;
    const schleifen = wege.filter(w=>w.rueck).length, erlaubt = grenze.kreuzungen + schleifen * grenze.je_schleife, meldungen = [];
    if(durchKnoten) meldungen.push(durchKnoten + ' Linie(n) laufen durch eine Kachel.');
    if(ueberlappungen) meldungen.push(ueberlappungen + ' Linienstück(e) liegen übereinander.');
    if(kreuzungen > erlaubt) meldungen.push(kreuzungen + ' Kreuzungen (erlaubt: ' + erlaubt + ').');
    if(umwege > grenze.umwege) meldungen.push(umwege + ' Linien machen große Umwege.');
    const ok = !durchKnoten && ueberlappungen <= grenze.ueberlappungen && kreuzungen <= erlaubt && umwege <= grenze.umwege;
    return {ok, wert, kreuzungen, ueberlappungen, durchKnoten, umwege, meldungen};
  }

  function pruefe(doc, G, o){ const r = routen(doc, G); return Object.assign(pruefeWege(r.wege, r.kisten, o), {wege: r.wege.length}); }

  // ---- Verbesserung: Abstände und Reihenfolge der Zeilen durchprobieren, den kleinsten Wert nehmen. Nur Positionen einer Kopie.
  function kopie(doc){ return JSON.parse(JSON.stringify(doc)); }
  function mit(doc, pos){ const c = kopie(doc); c.nodes.forEach(n=>{ if(pos[n.name]) n.position = pos[n.name].slice(); }); return c; }

  // Kandidaten: Rastergrößen und je Spalte die Zeilenfolge umgekehrt/verschoben (Knoten einer Spalte tauschen die Zeilen)
  function kandidaten(doc, G){
    const L = Lay(), g = G || TILE, aus = [], start = L.logisch(doc), pos0 = Object.fromEntries(start.nodes.map(n=>[n.name, n.position.slice()]));
    [[1, 1], [1.3, 1], [1, 1.4], [1.3, 1.4], [1.6, 1.2], [1.2, 1.8]].forEach(([fx, fy])=>{
      const pos = {}; Object.keys(pos0).forEach(k=>{ pos[k] = [Math.round(pos0[k][0] * fx), Math.round(pos0[k][1] * fy)]; });
      aus.push(pos);
    });
    // Spalten umsortieren: je Spalte die Knoten in umgekehrter Zeilenfolge
    const spalten = new Map();
    Object.entries(pos0).forEach(([n, p])=>{ (spalten.get(p[0]) || spalten.set(p[0], []).get(p[0])).push(n); });
    spalten.forEach(namen=>{
      if(namen.length < 2) return;
      const ys = namen.map(n=>pos0[n][1]).sort((a, b)=>a - b), umg = namen.slice().sort((a, b)=>pos0[b][1] - pos0[a][1]);
      const pos = Object.fromEntries(Object.entries(pos0).map(([k, v])=>[k, v.slice()]));
      umg.forEach((n, i)=>{ pos[n][1] = ys[i]; });
      aus.push(pos);
    });
    return aus;
  }

  function besser(doc, G, o){
    const g = G || TILE, vorher = pruefe(doc, g, o);
    let beste = {doc, befund: vorher};
    const probiere = d=>{ const b = pruefe(d, g, o); if(b.wert < beste.befund.wert) beste = {doc: d, befund: b}; };
    const L = Lay();
    probiere(L.logisch(doc));                                   // die gewohnte logische Anordnung zuerst
    kandidaten(doc, g).forEach(p=>probiere(mit(L.logisch(doc), p)));
    return {doc: beste.doc, befund: beste.befund, vorher, verbessert: beste.befund.wert < vorher.wert};
  }

  root.sedraWorkflowWaechter = {routen, pruefe, pruefeWege, besser, GRENZE, TILE, CIRCLE};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraWorkflowWaechter;
})();
