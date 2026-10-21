// Werkzeug „Organigramm“ – die reine Logik (Spec 4, D4.2.1): wo jede Karte steht, und welche Budgetstufe sie zeigt.
// Daten rein, Daten raus; node prüft beides ohne Browser (baum.test.js). Kein DOM, kein Zeitgeber.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const CAPTAIN = 'captain';
  const STUFEN = ['ok', 'warnung', 'gestoppt'];

  const name = a=>String(a.title || a.name || a.id);
  const boss = a=>(a.reports_to === null || a.reports_to === undefined || a.reports_to === '') ? null : String(a.reports_to);

  // Das Layout des Baums: die Wurzel ist der Captain, darunter die Agenten ohne Vorgesetzten, darunter ihre Untergebenen.
  // Die Breite eines Teilbaums ist die Summe der Breiten seiner Kinder (mindestens eine Karte); Geschwister nach Name sortiert.
  // Ein Besuchtenspeicher hält Datenfehler (Zyklus, unbekannter Vorgesetzter) auf: was nicht erreichbar ist, steht in
  // `ohneVorgesetzten` und wird unter dem Baum als „Nicht eingeordnet“ gezeigt.
  function layoutTree(agenten, options){
    const o = Object.assign({kartenbreite: 200, kartenhoehe: 84, abstand: 24, tiefeMax: 8}, options || {});
    const list = (agenten || []).filter(a=>a && a.id !== undefined && a.id !== null);
    const byId = new Map(list.map(a=>[String(a.id), a]));
    const kids = new Map();
    list.forEach(a=>{
      const b = boss(a);
      const parent = b === null ? CAPTAIN : b;
      if(!kids.has(parent)) kids.set(parent, []);
      kids.get(parent).push(a);
    });
    kids.forEach(arr=>arr.sort((x, y)=>name(x).localeCompare(name(y), 'de') || String(x.id).localeCompare(String(y.id))));
    const visited = new Set();
    const unit = o.kartenbreite + o.abstand;

    // erst die Teilbäume bauen (mit Besuchtenspeicher), dann die Breiten zählen, dann die Plätze vergeben
    function build(id, ebene){
      const node = {id, ebene, kinder: []};
      if(ebene >= o.tiefeMax) return node;
      (kids.get(id) || []).forEach(a=>{
        const cid = String(a.id);
        if(visited.has(cid)) return;
        visited.add(cid);
        node.kinder.push(build(cid, ebene + 1));
      });
      node.breite = 0;
      return node;
    }
    function width(node){
      node.breite = node.kinder.length ? node.kinder.reduce((s, k)=>s + width(k), 0) : 1;
      return node.breite;
    }
    const knoten = [], linien = [];
    let tiefe = 0;
    function place(node, links){
      const x = Math.round(links * unit + (node.breite * unit - o.abstand - o.kartenbreite) / 2);
      knoten.push({id: node.id, x, y: node.ebene * (o.kartenhoehe + o.abstand), ebene: node.ebene});
      tiefe = Math.max(tiefe, node.ebene);
      let at = links;
      node.kinder.forEach(k=>{ linien.push({von: node.id, nach: k.id}); place(k, at); at += k.breite; });
    }
    const baum = build(CAPTAIN, 0);
    width(baum);
    place(baum, 0);
    const ohneVorgesetzten = list.map(a=>String(a.id)).filter(id=>!visited.has(id))
      .sort((x, y)=>name(byId.get(x)).localeCompare(name(byId.get(y)), 'de') || x.localeCompare(y));
    return {knoten, linien, breite: baum.breite * unit - o.abstand, hoehe: (tiefe + 1) * (o.kartenhoehe + o.abstand) - o.abstand, ohneVorgesetzten};
  }

  // Die Stufe eines Budgets (rein). Maßgeblich ist der Server: `stufe` aus dem Objekt; sonst, wenn er Schwellen mitgibt,
  // Prozent gegen diese Schwellen. Ohne beides `null` – das Werkzeug erfindet keine Schwelle.
  function budgetStufe(budget){
    if(!budget || typeof budget !== 'object') return null;
    if(STUFEN.indexOf(budget.stufe) >= 0) return budget.stufe;
    const s = budget.schwellen, p = budget.prozent;
    if(!s || typeof p !== 'number') return null;
    if(typeof s.gestoppt === 'number' && p >= s.gestoppt) return 'gestoppt';
    if(typeof s.warnung === 'number' && p >= s.warnung) return 'warnung';
    return 'ok';
  }

  // Der Balken (rein): Breite 0–100, Text mit Prozent (nicht nur Farbe), Token; Euro nur, wenn der Server sie liefert
  function budgetBalken(budget){
    if(!budget || typeof budget.prozent !== 'number') return null;
    const p = Math.max(0, Math.round(budget.prozent));
    const teile = [p + ' %'];
    if(typeof budget.verbraucht_token === 'number' && typeof budget.grenze_token === 'number')
      teile.push(budget.verbraucht_token.toLocaleString('de-DE') + ' / ' + budget.grenze_token.toLocaleString('de-DE') + ' Token');
    if(typeof budget.verbraucht_eur_cent === 'number' && typeof budget.grenze_eur_cent === 'number')
      teile.push((budget.verbraucht_eur_cent / 100).toFixed(2).replace('.', ',') + ' / ' + (budget.grenze_eur_cent / 100).toFixed(2).replace('.', ',') + ' €');
    return {breite: Math.min(100, p), text: teile.join(' · '), stufe: budgetStufe(budget) || 'ok'};
  }

  const pure = {layoutTree, budgetStufe, budgetBalken, CAPTAIN};
  root.sedraOrgBaum = pure;
  if(typeof module !== 'undefined' && module.exports) module.exports = pure;
})();
