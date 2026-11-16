// Harness-Shell, Workflow Studio: der Startassistent und der Workflow-Katalog. Teil von workflow_studio.js.
// Der Startassistent füllt offene Prozessangaben aus und speichert sie als neue Revision; ein ausführbarer Workflow bekommt keine Angaben.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const G = root.sedraHarness.workflow_studio_geteilt;
  const d = G.d, luecken = G.luecken, angabenVon = G.angabenVon, workflowsZaehlen = G.workflowsZaehlen;

  // Der Workflow-Katalog: alle gespeicherten Workflows, je mit offenen Angaben und einem Sprung in den Startassistenten.
  function baueKatalog(api, zumAssistent){
    const box = d().el('div', 'hs-ws-katalog');
    const stand = d().el('p', 'hs-ws-hinweis', 'Lade die gespeicherten Workflows …');
    const karten = d().el('div', 'hs-ws-luecken');
    box.append(stand, karten);
    workflowsZaehlen(api).then(liste=>{
      stand.textContent = liste.length ? liste.length + ' gespeicherte Workflow(s).' : 'Noch kein Workflow gespeichert. Lege einen im n8n-Editor an oder importiere ihn.';
      liste.forEach(w=>{
        const karte = d().el('div', 'hs-ws-karte');
        karte.append(d().el('h4', 'hs-ws-karten-titel', w.title));
        karte.append(d().el('p', 'hs-ws-hinweis', 'Revision ' + w.revision + (w.geprueft ? ' · ' + (w.offen ? w.offen + ' offene Angabe(n)' : 'vollständig') : ' · nicht geprüft')));
        const knopf = d().el('button', 'hs-ws-knopf', 'Im Startassistenten öffnen'); knopf.type = 'button';
        knopf.onclick = ()=>zumAssistent(w.id);
        karte.append(knopf); karten.append(karte);
      });
    }).catch(err=>{ stand.textContent = 'Workflows nicht geladen: ' + (err.message || err); });
    return {box, abbauen(){ box.replaceChildren(); }};
  }

  // Der Startassistent: wählt einen gespeicherten Workflow, zeigt seine offenen Angaben, nimmt Eingaben an und speichert sie als neue Revision.
  function baueAssistent(api, zumLive){
    const box = d().el('div', 'hs-ws-assist');
    const kopf = d().el('p', 'hs-ws-hinweis', 'Startassistent: füllt die offenen Angaben jedes Schritts aus und speichert sie als neue Revision. Danach geht es in Live & Debugger.');
    const wahl = d().el('select', 'hs-ws-wahl'); wahl.setAttribute('aria-label', 'Workflow wählen');
    const stand = d().el('p', 'hs-ws-hinweis');
    const liste = d().el('div', 'hs-ws-luecken');
    const knoepfe = d().el('div', 'hs-ws-knoepfe');
    let rec = null, eingaben = [];

    async function alleLaden(){
      const data = await api('/api/objects', {method: 'POST', body: {type: 'workflow', id: 'alle'}});
      wahl.replaceChildren(new Option('Workflow wählen', ''));
      (data.items || []).forEach(r=>wahl.append(new Option(r.title + ' · r' + r.revision, r.id)));
      if(rec) wahl.value = rec.id;                                // ein Sprung aus dem Katalog hat schon einen Workflow geöffnet: die Auswahl bleibt
    }
    async function oeffnen(id){
      rec = await api('/api/objects', {method: 'POST', body: {type: 'workflow', id}});
      wahl.value = id;
      zeichnen();
    }
    function zeichnen(){
      liste.replaceChildren(); knoepfe.replaceChildren(); eingaben = [];
      // Ein ausführbarer Workflow bekommt keine Prozessangaben: sobald sie an den Knoten stehen, gilt er als Prozessmodell und ist nicht mehr ausführbar.
      const laufbar = !!(rec && rec.execution && rec.execution.executable);
      const offen = rec && !laufbar ? luecken(rec.workflow) : [];
      if(!rec){ stand.textContent = 'Wähle einen gespeicherten Workflow. Der Startassistent arbeitet an jedem Workflow.'; }
      else if(laufbar){
        stand.textContent = '„' + rec.workflow.name + '“ ist ausführbar. Keine Angaben nötig: Prozessangaben würden den Workflow zum Prozessmodell machen, das nicht läuft. Starte ihn direkt.';
      }
      else if(!offen.length){
        stand.textContent = 'Keine offenen Angaben in „' + rec.workflow.name + '“. Der Workflow ist vollständig beschrieben.';
      }else{
        stand.textContent = rec.workflow.name + ' · Revision ' + rec.revision + ' · ' + offen.length + ' Schritt(e) mit offenen Angaben.';
      }
      offen.forEach(x=>{
        const karte = d().el('div', 'hs-ws-karte'); karte.append(d().el('h4', 'hs-ws-karten-titel', x.name));
        x.fehlt.forEach(([k, label])=>{
          const zeile = d().el('label', 'hs-ws-feld', label);
          const feld = d().el('textarea', 'hs-ws-eingabe'); feld.rows = 2; feld.setAttribute('aria-label', x.name + ': ' + label);
          zeile.append(feld); karte.append(zeile);
          eingaben.push({node: x.node, key: k, feld});
        });
        liste.append(karte);
      });
      const speichern = d().el('button', 'hs-ws-knopf', 'Angaben speichern'); speichern.type = 'button';
      speichern.disabled = !rec || !offen.length;
      speichern.onclick = ()=>sichern().catch(err=>{ stand.textContent = 'Nicht gespeichert: ' + (err.message || err); });
      const start = d().el('button', 'hs-ws-knopf primary', 'Starten: zu Live & Debugger'); start.type = 'button';
      start.onclick = ()=>zumLive(rec);
      knoepfe.append(speichern, start);
    }
    async function sichern(){
      const doc = JSON.parse(JSON.stringify(rec.workflow));
      const P = root.sedraWorkflowProcess;
      const geaendert = eingaben.filter(e=>e.feld.value.trim());
      if(!geaendert.length){ stand.textContent = 'Keine Eingabe. Trage mindestens eine Angabe ein.'; return; }
      // Knoten im Dokument suchen (gleicher Name), Angabe setzen, Rest bleibt unverändert.
      const gruppen = new Map();
      geaendert.forEach(e=>{ if(!gruppen.has(e.node.name)) gruppen.set(e.node.name, {}); gruppen.get(e.node.name)[e.key] = e.feld.value.trim(); });
      (doc.nodes || []).forEach(node=>{
        const werte = gruppen.get(node.name); if(!werte) return;
        P.set(node, Object.assign({}, angabenVon(node), werte));
      });
      const out = await api('/api/actions', {method: 'POST', body: {type: 'workflow', id: rec.id, verb: 'speichern',
        args: {workflow: doc, base_revision: rec.revision, change_note: 'Startassistent: offene Angaben ergänzt'}}});
      const gespeichert = out.result || {};
      await oeffnen(rec.id);
      stand.textContent = 'Revision ' + (gespeichert.revision || '') + ' gespeichert. ' + (luecken(rec.workflow).length ? luecken(rec.workflow).length + ' Schritt(e) noch offen.' : 'Keine offenen Angaben mehr.');
    }
    wahl.onchange = ()=>{ if(wahl.value) oeffnen(wahl.value).catch(err=>{ stand.textContent = 'Nicht geladen: ' + (err.message || err); }); };
    box.append(kopf, wahl, stand, liste, knoepfe);
    zeichnen();                                                  // Starten ist sofort da, auch ohne gewählten Workflow
    alleLaden().catch(err=>{ stand.textContent = 'Workflows nicht geladen: ' + (err.message || err); });
    return {box, oeffne: id=>oeffnen(id).catch(err=>{ stand.textContent = 'Nicht geladen: ' + (err.message || err); }), abbauen(){ box.replaceChildren(); }};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.workflow_studio_assist = {baueKatalog, baueAssistent};
  if(typeof module !== 'undefined' && module.exports) module.exports = root.sedraHarness.workflow_studio_assist;
})();
