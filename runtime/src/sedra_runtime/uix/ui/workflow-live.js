// Der Reiter „Live“ der Workflow-Darstellungen (n8n Workflows und Szenario Studio): was gerade läuft, wie der Direktor in seiner Fabrik.
// Ein laufender Prozess meldet seinen Schritt selbst (workflows/live.py, Datei im Projekt); hier wird nur gelesen und gezeigt: eine Karte je
// Prozess mit Zustand, aktuellem Schritt, Text und dem Diagramm, in dem der Schritt leuchtet (fertig, läuft, wartet auf dich, Fehler).
// Nichts wird geraten: ohne Meldung leuchtet nichts, und eine Meldung, die seit drei Minuten nicht mehr kam, steht als „keine Meldung“.
// Abgefragt wird alle 2 Sekunden, solange der Reiter offen ist. `zusammenfassung`, `zustandText`, `dauerText` und `karteKey` sind rein.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const TAKT = 2000;
  const TEXTE = {laeuft: 'läuft', wartet: 'wartet auf dich', fehler: 'Fehler', fertig: 'fertig'};

  const zustandText = (p)=>p && p.veraltet ? 'keine Meldung' : (TEXTE[p && p.zustand] || 'unbekannt');
  // „2 Min.“, „1 Std. 5 Min.“ (rein)
  function dauerText(sek){
    if(sek === null || sek === undefined || !isFinite(sek) || sek < 0) return '–';
    if(sek < 60) return sek + ' Sek.';
    const m = Math.floor(sek / 60); if(m < 60) return m + ' Min.';
    return Math.floor(m / 60) + ' Std. ' + (m % 60) + ' Min.';
  }
  // Die Zeile über den Karten (rein): wie viele laufen, warten auf den Captain, sind gestört oder still
  function zusammenfassung(z){
    const n = z || {}, teile = [];
    if(n.laeuft) teile.push(n.laeuft + ' läuft');
    if(n.wartet) teile.push(n.wartet + (n.wartet === 1 ? ' wartet' : ' warten') + ' auf dich');
    if(n.fehler) teile.push(n.fehler + (n.fehler === 1 ? ' Fehler' : ' Fehler'));
    if(n.veraltet) teile.push(n.veraltet + ' ohne Meldung');
    return teile.length ? teile.join(' · ') : 'Gerade läuft nichts.';
  }
  const karteKey = p=>'k-' + String(p && p.prozess || '');

  const el = (tag, cls, text)=>{ const x = document.createElement(tag); if(cls) x.className = cls; if(text !== undefined) x.textContent = text; return x; };

  function attach(c){
    const panel = c.panels.live;
    const kopf = el('div', 't-wf-live-kopf'), summe = el('p', 't-wf-live-summe', 'Lade …'), liste = el('div', 't-wf-live-karten');
    kopf.append(el('h3', '', 'Live – was gerade geschieht'), summe);
    const leer = el('p', 't-wf-hint t-wf-live-leer', 'Ein Prozess erscheint hier, sobald er meldet, in welchem Schritt er ist. Die Meldung schreibt der laufende Prozess selbst (workflows/live.py); gerechnet oder geraten wird hier nichts.');
    panel.append(kopf, liste, leer);
    const karten = new Map();
    let timer = null, laeuft = false, tot = false;

    async function diagramm(k, p){
      if(k.doc || !p.workflow_id || k.laedt) return;
      k.laedt = true;
      try{
        const o = await c.ctx.api('/api/objects', {method: 'POST', body: {type: 'workflow', id: p.workflow_id}});
        if(tot || !o || !o.workflow) return;
        k.doc = o.workflow; k.state = {doc: k.doc, selected: null, live: p.knoten || {}};
        k.canvas = root.sedraWorkflowCanvas.mount(k.bild, k.state, {style: c.style, readOnly: true, hint: ''});
      }catch(e){ k.bild.textContent = 'Das Diagramm ließ sich nicht laden.'; }
    }

    function karte(p){
      const key = karteKey(p);
      let k = karten.get(key);
      if(!k){
        const box = el('section', 's-card t-wf-live-karte'); box.dataset.prozess = p.prozess;
        const kopfZeile = el('div', 't-wf-live-kartenkopf'), titel = el('b', '', ''), chip = el('span', 't-wf-live-chip', '');
        const schritt = el('p', 't-wf-live-schritt', ''), text = el('p', 't-wf-live-text', '');
        const bild = el('div', 't-wf-live-bild'); const verlauf = el('ol', 't-wf-live-verlauf'); verlauf.setAttribute('aria-label', 'Verlauf der letzten Schritte');
        kopfZeile.append(titel, chip); box.append(kopfZeile, schritt, text, bild, verlauf);
        liste.append(box);
        k = {box, titel, chip, schritt, text, bild, verlauf, doc: null, canvas: null, state: null, laedt: false};
        karten.set(key, k);
      }
      k.box.setAttribute('aria-label', 'Prozess ' + p.titel + ': ' + zustandText(p));
      k.box.dataset.zustand = p.veraltet ? 'veraltet' : p.zustand;
      k.titel.textContent = p.titel;
      k.chip.textContent = zustandText(p); k.chip.dataset.zustand = p.veraltet ? 'veraltet' : p.zustand;
      k.schritt.textContent = p.schritt ? 'Schritt: ' + (p.schritt_name || p.schritt) + (p.workflow_id && !p.schritt_name ? ' (im Diagramm nicht bekannt)' : '') + (p.veraltet ? ' (zuletzt gemeldet vor ' + dauerText(p.alter_s) + ')' : '') : (p.zustand === 'fertig' ? 'Der Lauf ist zu Ende.' : '');
      k.text.textContent = p.text || '';
      k.text.hidden = !p.text;
      k.verlauf.replaceChildren();
      (p.verlauf || []).slice().reverse().forEach(e=>{
        const li = el('li', 't-wf-live-eintrag ' + (e.zustand || ''), (String(e.zeit || '').slice(11, 19)) + ' · ' + (e.schritt_name || e.schritt || 'Ende') + ' · ' + (TEXTE[e.zustand] || e.zustand) + (e.text ? ' – ' + e.text : ''));
        k.verlauf.append(li);
      });
      if(k.state){ k.state.live = p.knoten || {}; if(k.canvas) k.canvas.draw(); }
      else diagramm(k, p);
      return key;
    }

    async function takt(){
      if(laeuft || tot) return;
      laeuft = true;
      try{
        const out = await c.call('workflow', null, 'live');
        if(tot || !out) return;
        const aktuelle = new Set((out.prozesse || []).map(karte));
        karten.forEach((k, key)=>{ if(!aktuelle.has(key)){ if(k.canvas) k.canvas.destroy(); k.box.remove(); karten.delete(key); } });
        summe.textContent = zusammenfassung(out.zaehler);
        leer.hidden = !!(out.prozesse || []).length;
      }catch(e){ summe.textContent = 'Die Live-Ansicht konnte nicht lesen: ' + String(e && e.message || e).slice(0, 120); }
      finally{ laeuft = false; }
    }
    const api = {
      start(){ if(timer) return; takt(); timer = setInterval(takt, TAKT); },
      stop(){ if(timer) clearInterval(timer); timer = null; },
      destroy(){ tot = true; api.stop(); karten.forEach(k=>{ if(k.canvas) k.canvas.destroy(); }); karten.clear(); },
      takt
    };
    return api;
  }

  root.sedraWorkflowLive = {attach, zusammenfassung, zustandText, dauerText, karteKey, TEXTE};
  if(typeof module !== 'undefined' && module.exports) module.exports = {zusammenfassung, zustandText, dauerText, karteKey, TEXTE};
})();
