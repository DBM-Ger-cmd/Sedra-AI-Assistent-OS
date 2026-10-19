// Die Arbeitsstrecke im GateWay (Spezifikation docs/SPEC_GATEWAY_ARBEITSSTRECKE_2026-10-19.md): Reiter, Dateien, Vorschau mit
// Markierungen, Bearbeiten (je Fundstelle ersetzen, behalten oder entfernen) und Speichern unter in den Ausgang.
// Nur das Original wird gelesen; die Ausgabe trägt einen Vermerk. Wird vor tool.js geladen; stellt root.sedraGatewayArbeit bereit.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const AUSWAHL = ['ersetzen', 'behalten', 'entfernen'];
  const ART_WORT = {ersetzen: 'durch Platzhalter ersetzen', behalten: 'behalten', entfernen: 'entfernen'};

  // Die Reiter oben: Vorgänge, Dateien, Regeln. Klick wechselt die Ansicht des Werkzeugs.
  function reiter(tool, list){
    const bar = d().el('div', 't-gateway-tabs');
    [['vorgaenge', 'Vorgänge'], ['dateien', 'Dateien'], ['regeln', 'Regeln']].forEach(([id, label])=>{
      bar.append(d().button(label, ()=>{ tool.ansicht = id; tool.refresh(); }, (tool.ansicht || 'vorgaenge') === id ? 'p' : undefined));
    });
    return bar;
  }

  // Die hochgeladenen Dateien (der Eingang) mit ihrer Vorschau. Projektdateien sind hier nicht gemeint.
  function dateien(tool, list){
    const box = d().el('div', 't-gateway-dateien');
    box.append(d().el('small', 's-muted', 'Hochgeladene Dateien. Das Original bleibt unverändert; bearbeitet wird eine Fassung im Ausgang.'));
    const liste = (list.dateien || []).filter(f=>f.eingang);
    if(!liste.length) box.append(d().empty('Noch keine Datei. Lade eine .md, .txt oder .docx hoch (Feld „Datei hochladen“ im Vorgang).'));
    liste.forEach(f=>{
      const row = d().el('div', 't-gateway-row');
      row.append(d().el('b', null, f.pfad), d().el('small', 's-muted', d().fmtBytes(f.bytes)));
      row.append(d().button('Vorschau & bearbeiten', ()=>vorschau(tool, f.pfad), 'p'));
      box.append(row);
    });
    return box;
  }

  // Der Text mit allen Fundstellen markiert; jede Markierung nennt die Regel im Hinweis.
  function markierterText(text, fund){
    const pre = d().el('pre', 't-gateway-vorschau');
    let pos = 0;
    fund.slice().sort((a, b)=>a.start - b.start).forEach(f=>{
      if(f.start < pos) return;                              // überlappt: die erste Markierung gilt
      pre.append(document.createTextNode(text.slice(pos, f.start)));
      const mark = d().el('mark', 't-gw-fund', text.slice(f.start, f.end));
      mark.title = f.typ + ' · Regel ' + (f.regel || '–');
      pre.append(mark);
      pos = f.end;
    });
    pre.append(document.createTextNode(text.slice(pos)));
    return pre;
  }

  // Vorschau und Bearbeiten einer Datei: links der Text, rechts je Fundstelle die Vorgabe.
  async function vorschau(tool, name){
    tool.ansicht = 'dateien';
    tool.el.replaceChildren(d().el('small', 's-muted', 'Lese das Original …'));
    let v;
    try{ v = await tool.ctx.api('/api/gateway/vorschau', {method: 'POST', body: {name}}); }
    catch(err){ tool.el.replaceChildren(d().el('div', 's-note bad', 'Die Datei ist nicht lesbar: ' + err.message)); return; }
    const box = d().el('div', 't-gateway-arbeit');
    box.append(d().button('← Dateien', ()=>{ tool.ansicht = 'dateien'; tool.refresh(); }));
    box.append(d().el('h3', null, 'Vorschau: ' + v.name));
    box.append(d().el('small', 's-muted', v.fundstellen.length + ' Fundstelle(n). Original wird nicht verändert.'));
    box.append(markierterText(v.text, v.fundstellen));
    // je gleichem Text eine Zeile; der Server ersetzt alle Vorkommen gleich
    const gruppen = new Map();
    v.fundstellen.forEach(f=>{ const k = f.typ + '|' + f.text.toLowerCase(); if(!gruppen.has(k)) gruppen.set(k, {f, art: (v.vorschlaege && v.vorschlaege[f.id] ? v.vorschlaege[f.id].art : 'ersetzen'), vorschlag: (v.vorschlaege || {})[f.id] || null, merken: false}); });
    const zeilen = d().el('div', 't-gateway-vorgaben');
    zeilen.append(d().el('h4', null, 'Vorgaben je Fundstelle'));
    if(!gruppen.size) zeilen.append(d().empty('Keine Fundstelle. Die Datei kann so in den Ausgang.'));
    gruppen.forEach(g=>{
      const row = d().el('div', 't-gateway-row');
      const sel = d().el('select'); sel.setAttribute('aria-label', 'Vorgabe für ' + g.f.text);
      AUSWAHL.forEach(a=>{ const o = d().el('option', null, ART_WORT[a]); o.value = a; sel.append(o); });
      sel.value = g.art; sel.onchange = ()=>{ g.art = sel.value; };
      const merke = d().el('input'); merke.type = 'checkbox'; merke.onchange = ()=>{ g.merken = merke.checked; };
      const lab = d().el('label', null, merke, ' als Vorgabe merken');
      row.append(d().el('b', null, g.f.text), d().el('small', 's-muted', ' ' + g.f.typ + ' · Regel ' + (g.f.regel || '–')), sel, lab);
      if(g.vorschlag) row.append(d().el('small', 's-muted', ' Vorschlag aus gemerkter Vorgabe (' + (g.vorschlag.datum || '').slice(0, 10) + ')'));
      zeilen.append(row);
    });
    box.append(zeilen);
    const stamm = name.replace(/\.(md|txt|docx)$/i, '');
    const endung = (name.match(/\.(md|txt|docx)$/i) || ['.txt'])[0].toLowerCase();
    const ziel = d().el('input'); ziel.value = stamm + '_anonymisiert' + (endung === '.docx' ? '.txt' : endung); ziel.setAttribute('aria-label', 'Name der Ausgabe');
    const hinweis = d().el('small', 's-muted', 'Gespeichert wird im Ausgang, nie über dem Original.');
    box.append(ziel, hinweis, d().button('Speichern unter', async()=>{ await speichern(tool, name, v, [...gruppen.values()], ziel.value, box); }, 'p'));
    box.append(d().el('small', 's-muted', 'Angekreuzte Vorgaben werden beim Speichern gemerkt und gelten als Vorschlag für neue Dokumente.'));
    tool.el.replaceChildren(box);
  }

  // Speichern unter: die gewählten Vorgaben gehen an den Server; das Ergebnis mit Vermerk wird gezeigt.
  async function speichern(tool, name, v, gruppen, ziel, box){
    const auswahl = gruppen.map(g=>({id: g.f.id, art: g.art}));
    for(const g of gruppen){ if(g.merken){ try{ await tool.ctx.api('/api/gateway/vorgabe/merken', {method: 'POST', body: {text: g.f.text, typ: g.f.typ, art: g.art}}); }catch(_e){} } }
    try{
      const out = await tool.ctx.api('/api/gateway/ausgabe', {method: 'POST', body: {name, auswahl, ziel}});
      box.append(d().el('div', 's-note ok', 'Im Ausgang gespeichert: ' + out.name + ' · Original unverändert (Prüfsumme ' + (out.vermerk.original_sha256 || '').slice(0, 12) + '…)'));
    }catch(err){ box.append(d().el('div', 's-note bad', 'Nicht gespeichert: ' + err.message)); }
  }

  // Der Abschnitt „Gemerkte Vorgaben“ im Reiter Regeln: was gemerkt ist, wirkt als Vorschlag, und man kann es wieder löschen.
  async function vorgabenListe(tool, box){
    const kopf = d().el('h4', null, 'Gemerkte Vorgaben');
    box.append(kopf);
    let liste;
    try{ liste = (await tool.ctx.api('/api/gateway/vorgaben')).vorgaben || []; }
    catch(err){ box.append(d().el('div', 's-note bad', 'Die gemerkten Vorgaben sind nicht lesbar: ' + err.message)); return; }
    if(!liste.length) box.append(d().empty('Noch keine Vorgabe gemerkt. In der Vorschau einer Datei ankreuzen: „als Vorgabe merken“.'));
    liste.forEach(e=>{
      const row = d().el('div', 't-gateway-row');
      row.append(d().el('b', null, e.text), d().el('small', 's-muted', ' ' + e.typ + ' · ' + ART_WORT[e.art] + ' · seit ' + (e.datum || '').slice(0, 10) + ' · global, wirkt als Vorschlag'));
      row.append(d().button('Löschen', async()=>{ try{ await tool.ctx.api('/api/gateway/vorgabe/loeschen', {method: 'POST', body: {id: e.id}}); await tool.refresh(); }catch(err){ alert('Nicht gelöscht: ' + err.message); } }));
      box.append(row);
    });
  }

  root.sedraGatewayArbeit = {reiter, dateien, vorschau, markierterText, vorgabenListe};
  if(typeof module !== 'undefined' && module.exports) module.exports = {markierterText};
})();
