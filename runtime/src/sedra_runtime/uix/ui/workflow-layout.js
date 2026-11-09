// Layout und Kantenführung der Workflow-Darstellungen (n8n Workflows und Szenario Studio), rein und ohne DOM: `node workflow-layout.test.js`.
// Anordnung in Ebenen von links nach rechts: Rücksprünge (Kanten zu einem Vorfahren) werden vorher herausgenommen, sonst zerreißen
// Schleifen die Ebenen; die Spalte ist der längste Weg vom Auslöser, die Zeile folgt dem Vorgänger (Ausgang „Ja“ bleibt auf seiner Zeile,
// „Nein“ eine Zeile darunter). Kanten laufen rechtwinklig mit abgerundeten Ecken: vorwärts durch die freie Gasse neben dem Knoten oder
// durch eine freie Querbahn zwischen zwei Zeilen, Rücksprünge in einer eigenen Bahn unterhalb des Graphen. `ebenen`, `anordnen`,
// `fuehren` und `pfad` sind rein; weder Knoten noch Verbindungen werden verändert.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const NOTIZ = /\.stickyNote$/;
  const VORWAERTS = 40;                  // kleinster waagerechter Abstand zwischen Ausgang und Eingang einer Vorwärtskante

  // Kanten als flache Liste [{von, nach, ast, art}] in der Reihenfolge der Ausgänge (rein)
  function kanten(doc){
    const namen = new Set(doc.nodes.map(n=>n.name)), out = [];
    doc.nodes.forEach(n=>{
      const verb = (doc.connections || {})[n.name] || {};
      Object.keys(verb).forEach(art=>(verb[art] || []).forEach((zweig, ast)=>(zweig || []).forEach(e=>{
        if(namen.has(e.node) && e.node !== n.name) out.push({von: n.name, nach: e.node, ast, art});
      })));
    });
    return out;
  }

  // Ebenen: {spalte: Map(name → Spalte), zurueck: Set('von|nach|ast'), wurzeln: [name]} (rein)
  function ebenen(doc){
    const knoten = doc.nodes.filter(n=>!NOTIZ.test(n.type)), liste = kanten(doc).filter(k=>knoten.some(n=>n.name === k.von) && knoten.some(n=>n.name === k.nach));
    const aus = new Map(knoten.map(n=>[n.name, []])), ein = new Map(knoten.map(n=>[n.name, 0]));
    liste.forEach(k=>{ aus.get(k.von).push(k); ein.set(k.nach, ein.get(k.nach) + 1); });
    aus.forEach(l=>l.sort((a, b)=>a.ast - b.ast));
    const start = knoten.find(n=>/\.manualTrigger$/.test(n.type)) || knoten.find(n=>ein.get(n.name) === 0) || knoten[0];
    const wurzeln = [];
    if(start) wurzeln.push(start.name);
    knoten.forEach(n=>{ if(ein.get(n.name) === 0 && !wurzeln.includes(n.name)) wurzeln.push(n.name); });
    // Tiefensuche: eine Kante zu einem Knoten auf dem aktuellen Weg ist ein Rücksprung
    const zurueck = new Set(), farbe = new Map(), reihenfolge = [];
    const gehe = name=>{
      farbe.set(name, 1); reihenfolge.push(name);
      aus.get(name).forEach(k=>{
        const f = farbe.get(k.nach);
        if(f === 1) zurueck.add(k.von + '|' + k.nach + '|' + k.ast);
        else if(!f) gehe(k.nach);
      });
      farbe.set(name, 2);
    };
    wurzeln.forEach(w=>{ if(!farbe.get(w)) gehe(w); });
    knoten.forEach(n=>{ if(!farbe.get(n.name)){ wurzeln.push(n.name); gehe(n.name); } });
    // Spalte = längster Weg über die Vorwärtskanten, in der Reihenfolge der Tiefensuche (Vorgänger zuerst nach Topologie)
    const vor = liste.filter(k=>!zurueck.has(k.von + '|' + k.nach + '|' + k.ast)), spalte = new Map(knoten.map(n=>[n.name, 0]));
    for(let runde = 0; runde < knoten.length + 1; runde++){
      let geaendert = false;
      vor.forEach(k=>{ if(spalte.get(k.nach) < spalte.get(k.von) + 1){ spalte.set(k.nach, spalte.get(k.von) + 1); geaendert = true; } });
      if(!geaendert) break;
    }
    return {spalte, zurueck, wurzeln, reihenfolge, kanten: liste, vor};
  }

  // Zeile je Knoten (ganze Zahlen ab 0) und Position {name → [x, y]} (rein). o: {dx, dy}
  function anordnen(doc, o){
    const opt = Object.assign({dx: 224, dy: 170}, o || {});
    const e = ebenen(doc), maxSp = Math.max(0, ...e.spalte.values());
    const spalten = [];
    for(let s = 0; s <= maxSp; s++) spalten.push(e.reihenfolge.filter(n=>e.spalte.get(n) === s));
    const eingehend = new Map();
    e.vor.forEach(k=>{ (eingehend.get(k.nach) || eingehend.set(k.nach, []).get(k.nach)).push(k); });
    const zeile = new Map();
    spalten.forEach(namen=>{
      const frei = new Set(), wunsch = new Map();
      namen.forEach(n=>{
        const vorgaenger = (eingehend.get(n) || []).filter(k=>zeile.has(k.von));
        if(!vorgaenger.length){ wunsch.set(n, null); return; }
        const erste = vorgaenger.slice().sort((a, b)=>a.ast - b.ast || zeile.get(a.von) - zeile.get(b.von))[0];
        wunsch.set(n, zeile.get(erste.von) + (erste.ast > 0 ? 1 : 0));
      });
      // Knoten mit Wunsch zuerst (der Hauptweg behält seine Zeile), dann die ohne
      const mit = namen.filter(n=>wunsch.get(n) !== null).sort((a, b)=>wunsch.get(a) - wunsch.get(b) || namen.indexOf(a) - namen.indexOf(b));
      const ohne = namen.filter(n=>wunsch.get(n) === null);
      const setze = (n, z)=>{ let r = z, d = 0; while(frei.has(r)){ d += 1; r = z + (d % 2 ? (d + 1) / 2 : -d / 2); } frei.add(r); zeile.set(n, r); };
      mit.forEach(n=>setze(n, wunsch.get(n)));
      ohne.forEach(n=>setze(n, ohne.length && !mit.length ? ohne.indexOf(n) : (Math.max(-1, ...frei) + 1)));
    });
    const kleinste = Math.min(0, ...zeile.values());
    const pos = {};
    doc.nodes.forEach(n=>{
      if(!zeile.has(n.name)) return;
      pos[n.name] = [e.spalte.get(n.name) * opt.dx, (zeile.get(n.name) - kleinste) * opt.dy];
    });
    return {pos, zeile, spalte: e.spalte, zurueck: e.zurueck, kanten: e.kanten};
  }

  const schneidet = (a, b, r, m)=>{                  // achsparalleles Segment a–b gegen Rechteck r = [x, y, w, h] mit Rand m
    const x0 = Math.min(a[0], b[0]), x1 = Math.max(a[0], b[0]), y0 = Math.min(a[1], b[1]), y1 = Math.max(a[1], b[1]);
    return x1 > r[0] - m && x0 < r[0] + r[2] + m && y1 > r[1] - m && y0 < r[1] + r[3] + m;
  };
  const frei = (punkte, kisten, m)=>{ for(let i = 0; i + 1 < punkte.length; i++) for(const k of kisten) if(schneidet(punkte[i], punkte[i + 1], k, m)) return false; return true; };
  const laenge = p=>p.reduce((s, q, i)=>i ? s + Math.abs(q[0] - p[i - 1][0]) + Math.abs(q[1] - p[i - 1][1]) : 0, 0);
  const vereinfache = p=>{                          // doppelte und gerade durchlaufene Punkte entfernen
    const q = [];
    p.forEach(pt=>{ if(!q.length || q[q.length - 1][0] !== pt[0] || q[q.length - 1][1] !== pt[1]) q.push(pt); });
    return q.filter((pt, i)=>!(i && i < q.length - 1 && ((q[i - 1][0] === pt[0] && pt[0] === q[i + 1][0]) || (q[i - 1][1] === pt[1] && pt[1] === q[i + 1][1]))));
  };

  // Der Weg einer Kante als Punktliste (rein). a: Ausgang [x, y], b: Eingang [x, y], kisten: Rechtecke der übrigen Knoten,
  // o: {stub, boden (y der ersten Rücksprungbahn), bahnen: Anzahl der schon belegten Bahnen, querbahnen: [y …]}
  function fuehren(a, b, kisten, o){
    const opt = Object.assign({stub: 24, boden: 0, bahn: 0, querbahnen: [], rand: 6}, o || {});
    const s = Math.min(opt.stub, Math.max(6, (b[0] - a[0]) / 2)), x1 = a[0] + s, x2 = b[0] - s;
    if(b[0] - a[0] >= VORWAERTS){                     // genug Platz nach rechts: Vorwärtskante, sonst Rücksprung unter dem Graphen
      const kandidaten = [[a, [x1, a[1]], [x1, b[1]], b], [a, [x2 > x1 ? x2 : x1, a[1]], [x2 > x1 ? x2 : x1, b[1]], b]];
      // der Knick in der Mitte der Lücke (mit kleinem Versatz je Kante, damit sich Kanten derselben Spalte nicht decken): dann liegt die
      // Mitte der Kante auf dem Knick, und ein Klick auf die Kante trifft sie
      const xm = Math.max(x1, Math.min(x2 > x1 ? x2 : x1, (a[0] + b[0]) / 2 + (opt.versatz || 0)));
      kandidaten.unshift([a, [xm, a[1]], [xm, b[1]], b]);
      opt.querbahnen.forEach(y=>kandidaten.push([a, [x1, a[1]], [x1, y], [x2, y], [x2, b[1]], b]));
      const gut = kandidaten.map(vereinfache).filter(p=>frei(p, kisten, opt.rand));
      if(gut.length) return gut.sort((p, q)=>p.length - q.length || laenge(p) - laenge(q))[0];
      return vereinfache(kandidaten[0]);
    }
    // Rücksprung: weit genug vom Knoten, damit die Bahn seine Beschriftung (breiter als die Kachel) nicht streift; jede Bahn eigene Spur
    const y = opt.boden + opt.bahn * 18, xa = a[0] + Math.max(s, 44) + opt.bahn * 8, xb = b[0] - 46 - opt.bahn * 8;
    return vereinfache([a, [xa, a[1]], [xa, y], [xb, y], [xb, b[1]], b]);
  }

  // Punktliste → SVG-Pfad mit abgerundeten Ecken (rein)
  function pfad(punkte, radius){
    const r = radius === undefined ? 8 : radius;
    if(punkte.length < 3) return 'M ' + punkte.map(p=>p.join(' ')).join(' L ');
    let d = 'M ' + punkte[0].join(' ');
    for(let i = 1; i < punkte.length - 1; i++){
      const p = punkte[i - 1], c = punkte[i], n = punkte[i + 1];
      const l1 = Math.hypot(c[0] - p[0], c[1] - p[1]), l2 = Math.hypot(n[0] - c[0], n[1] - c[1]), rr = Math.min(r, l1 / 2, l2 / 2);
      const von = [c[0] - (c[0] - p[0]) / l1 * rr, c[1] - (c[1] - p[1]) / l1 * rr], nach = [c[0] + (n[0] - c[0]) / l2 * rr, c[1] + (n[1] - c[1]) / l2 * rr];
      d += ' L ' + von.join(' ') + ' Q ' + c.join(' ') + ' ' + nach.join(' ');
    }
    return d + ' L ' + punkte[punkte.length - 1].join(' ');
  }
  // Mitte der Punktliste entlang ihrer Länge, für den Punkt zum Wählen der Kante (rein)
  function mitte(punkte){
    const gesamt = laenge(punkte); let rest = gesamt / 2;
    for(let i = 1; i < punkte.length; i++){
      const l = Math.abs(punkte[i][0] - punkte[i - 1][0]) + Math.abs(punkte[i][1] - punkte[i - 1][1]);
      if(rest <= l) return l ? [punkte[i - 1][0] + (punkte[i][0] - punkte[i - 1][0]) * rest / l, punkte[i - 1][1] + (punkte[i][1] - punkte[i - 1][1]) * rest / l] : punkte[i];
      rest -= l;
    }
    return punkte[punkte.length - 1];
  }

  root.sedraWorkflowLayout = {kanten, ebenen, anordnen, fuehren, pfad, mitte, VORWAERTS};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraWorkflowLayout;
})();
