// Laufdiagnose: derselbe Canvas wie im Editor, gespeicherte Revision, echte Meldungen.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const text = value=>JSON.stringify(value, null, 2);
  const STATUS = {PAUSED:'Pausiert', COMPLETE:'Abgeschlossen', COMPLETED:'Abgeschlossen', DONE:'Abgeschlossen', FERTIG:'Abgeschlossen', RUNNING:'Läuft', LAEUFT:'Läuft', WAITING:'Wartet', WARTET:'Wartet', ERROR:'Fehler', FEHLER:'Fehler', EXECUTE:'In Ausführung', VERIFY:'Wird geprüft', FAILED:'Fehlgeschlagen', CANCELLED:'Abgebrochen', ABORTED:'Abgebrochen', PENDING:'Ausstehend', READY:'Bereit', CAPTAIN_REVIEW:'Freigabe erforderlich', IN_FLIGHT:'In Bearbeitung', UNKNOWN:'Unbekannt'};
  Object.assign(STATUS,{OK:'Abgeschlossen',UEBERSPRUNGEN:'Übersprungen'});
  const statusText = value=>STATUS[String(value || '').toUpperCase()] || value || 'Keine Meldung';
  function errorText(result){const raw=String(result?.fehler_text || result?.error || '');return raw.includes('SG_PERSONAL_CLOUD')?'Datenschutz: Der Rechnungstext wurde als personenbezogen erkannt. Die Übertragung an NVIDIA wurde blockiert. Wähle für diesen Workflow ein lokales Modell und speichere die neue Revision.':raw;}
  function baue(api, lauf, options={}){
    const box = d().el('section','hs-ws-debugger'); box.setAttribute('aria-label','Grafischer Lauf-Debugger');
    const kopf = d().el('div','hs-ws-debug-kopf');
    kopf.append(d().el('h3','hs-ws-sektion',lauf.title || 'Lauf untersuchen'),d().el('span','hs-ws-chip',statusText(lauf.state)));
    const kontext = d().el('p','hs-ws-hinweis',lauf.id + ' · Revision ' + (lauf.revision || '–'));
    const raster = d().el('div','hs-ws-debug-raster');
    const mitte = d().el('div','hs-ws-debug-mitte');
    const bild = d().el('div','t-workflow hs-ws-debug-canvas');
    const info = d().el('p','hs-ws-hinweis','Lade den Workflow des Laufs …'); info.setAttribute('role','status');
    const inspektor = d().el('aside','hs-ws-debug-inspektor'); inspektor.setAttribute('aria-label','Knoteninspektor');
    mitte.append(info,bild); raster.append(mitte,inspektor); box.append(kopf,kontext);
    if(options.shared){box.append(info);options.inspector.replaceChildren(inspektor);}else box.append(raster);
    let canvas = null, doc = null, prozess = null, ausgewaehlt = null, tot = false;
    const schritte = (lauf.result && lauf.result.knoten) || lauf.steps || [];
    const zustand = options.state || {doc:null,selected:null,live:{}};
    function inspizieren(id){
      if(options.shared)options.inspector.hidden=!id;
      ausgewaehlt = id; zustand.selected = id;
      inspektor.replaceChildren(d().el('h4','hs-ws-karten-titel','Knoteninspektor'));
      const node = doc && doc.nodes.find(n=>n.id === id);
      if(!node){ inspektor.append(d().el('p','hs-ws-hinweis','Wähle einen Knoten im Diagramm, um seine Details zu sehen.')); return; }
      inspektor.append(d().el('h3','hs-ws-sektion',node.name));
      const fakten = d().el('dl','hs-ws-debug-fakten');
      [['Knotentyp',node.type],['Knoten-ID',node.id],['Live-Status',prozess && prozess.veraltet ? 'Keine aktuelle Meldung' : statusText(zustand.live[node.id])]].forEach(([label,wert])=>fakten.append(d().el('dt','',label),d().el('dd','',wert)));
      inspektor.append(fakten);
      if(lauf.result?.fehler_knoten===node.name)inspektor.append(d().el('h4','hs-ws-karten-titel','Fehlerursache'),d().el('p','hs-ws-banner',errorText(lauf.result)));
      const trace=schritte.find(s=>s.name===node.name);
      if(trace && trace.beispiel!==undefined && trace.beispiel!==null)inspektor.append(d().el('h4','hs-ws-karten-titel','Ausgabe · gekürzte Laufvorschau'),d().el('pre','hs-ws-ergebnis',text(trace.beispiel)));
      else inspektor.append(d().el('p','hs-ws-hinweis','Für diesen Knoten liegt keine Ausgabevorschau vor.'));
      if(canvas) canvas.draw();
    }
    const trace = d().el('section','hs-ws-debug-trace');
    trace.append(d().el('h4','hs-ws-karten-titel','Ausführungshistorie'));
    const abgeschlossen = schritte.filter(s=>['COMPLETED','ok'].includes(s.status)).length;
    trace.append(d().el('p','hs-ws-hinweis',schritte.length ? abgeschlossen + ' von ' + schritte.length + ' gemeldeten Schritten abgeschlossen. Wähle einen Schritt zum Prüfen.' : 'Für diesen Lauf wurden noch keine Schritte gemeldet.'));
    const leiste = d().el('ol','hs-ws-debug-schritte'); leiste.setAttribute('aria-label','Gemeldete Ausführungsschritte');
    const schrittDetail = d().el('div','hs-ws-debug-schritt-detail'); schrittDetail.setAttribute('role','status');
    schritte.forEach((s,i)=>{
      const li = d().el('li');
      const b = d().el('button','hs-ws-debug-schritt'); b.type = 'button'; b.dataset.state = s.status;
      b.append(d().el('span','hs-ws-debug-nummer',i+1),d().el('strong','',s.name || s.id || s.step_id),d().el('small','',statusText(s.status)));
      b.onclick = ()=>{
        leiste.querySelectorAll('button').forEach(k=>k.setAttribute('aria-pressed',k === b ? 'true' : 'false'));
        schrittDetail.textContent = (s.name || s.id || s.step_id) + ' · ' + statusText(s.status) + (s.attempts==null?'':' · Versuche: '+s.attempts);
        const node = doc && doc.nodes.find(n=>n.id === s.id || n.name === (s.name || s.id));
        if(node){zustand.selected=node.id;inspizieren(node.id);}
      };
      b.setAttribute('aria-pressed','false');li.append(b);leiste.append(li);
    });
    trace.append(leiste,schrittDetail); box.append(trace);
    if(lauf.result?.fehler_text){const failure=d().el('div','hs-ws-banner');failure.setAttribute('role','alert');failure.append(d().el('strong','','Abbruch bei '+(lauf.result.fehler_knoten || 'der Ausführung')),d().el('p','hs-ws-hinweis',errorText(lauf.result)));box.prepend(failure);}
    if(lauf.wait){ const warten=d().el('div','hs-ws-banner');warten.append(d().el('strong','','Dieser Lauf wartet'),d().el('pre','hs-ws-ergebnis',typeof lauf.wait === 'string' ? lauf.wait : text(lauf.wait)));box.append(warten); }
    if(lauf.result !== null && lauf.result !== undefined){
      const ergebnis = d().el('details','hs-ws-debug-resultat');
      ergebnis.append(d().el('summary','','Laufergebnis ansehen'),d().el('pre','hs-ws-ergebnis',text(lauf.result)));box.append(ergebnis);
    }
    if(lauf.result && lauf.result.dashboard){
      const dashboard=d().el('button','hs-ws-knopf primary','HTML-Auswertung herunterladen');dashboard.type='button';
      dashboard.disabled=lauf.result.dashboard.status!=='created';
      dashboard.onclick=async()=>{dashboard.disabled=true;try{const out=await api('/api/actions',{method:'POST',body:{type:'workflow_run',id:lauf.id,verb:'dashboard_lesen',args:{}}});const r=out.result || out;const url=URL.createObjectURL(new Blob([r.html],{type:'text/html;charset=utf-8'}));const a=d().el('a');a.href=url;a.download=r.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(err){info.textContent='Dashboard nicht geladen: '+err.message;}finally{dashboard.disabled=false;}};
      box.append(dashboard);
    }
    inspizieren(null);
    function savedStates(){const out={};if(doc)for(const node of doc.nodes){const step=schritte.find(s=>s.name===node.name);if(step && ['ok','COMPLETED'].includes(step.status))out[node.id]='fertig';if(lauf.result && lauf.result.fehler_knoten===node.name)out[node.id]='fehler';}return out;}
    function states(){return prozess && !prozess.veraltet?prozess.knoten || {}:savedStates();}
    async function aktualisieren(){
      try{
        const live=await api('/api/actions',{method:'POST',body:{type:'workflow',id:null,verb:'live',args:{}}});
        if(tot) return;
        prozess=((live.result || live).prozesse || []).find(p=>p.lauf===lauf.id);
        zustand.live=states();
        info.textContent=prozess && !prozess.veraltet ? 'Aktuelle Laufmeldung · Knoten anklicken, um Details zu prüfen.' : 'Gespeicherter Lauf · Status aus den übermittelten Knotenergebnissen.';
        inspizieren(ausgewaehlt);if(canvas) canvas.draw();
      }catch(_err){if(!tot){prozess=null;zustand.live=savedStates();info.textContent='Live-Meldung nicht verfügbar. Gespeicherter Workflow und Verlauf bleiben sichtbar.';inspizieren(ausgewaehlt);if(canvas)canvas.draw();}}
    }
    const ready = (async()=>{
      try{
        // Historische Läufe dürfen nicht mit einer neueren Workflow-Fassung gezeigt werden.
        const [version,live] = await Promise.all([
          api('/api/actions',{method:'POST',body:{type:'workflow',id:null,verb:'revision_lesen',args:{id:lauf.workflow_id,revision:lauf.revision}}}),
          api('/api/actions',{method:'POST',body:{type:'workflow',id:null,verb:'live',args:{}}}).catch(()=>null)
        ]);
        if(tot) return;
        doc = (version.result || version).workflow;
        if(!doc || !Array.isArray(doc.nodes)) throw new Error('Workflow-Revision nicht verfügbar');
        if(options.prepare && !(await options.prepare(lauf,doc))){info.textContent='Laufansicht abgebrochen. Der offene Entwurf bleibt erhalten.';return;}
        zustand.doc = doc;
        prozess = ((live && (live.result || live).prozesse) || []).find(p=>p.lauf === lauf.id);
        zustand.live = states();
        info.textContent = prozess && !prozess.veraltet ? 'Aktuelle Laufmeldung · Knoten anklicken, um Details zu prüfen.' : 'Gespeicherter Lauf · Status aus den übermittelten Knotenergebnissen.';
        if(!root.sedraWorkflowCanvas) throw new Error('Diagramm-Komponente nicht verfügbar');
        if(options.shared){options.onInspect(inspizieren);canvas={draw:options.draw,destroy(){}};options.redraw();}
        else canvas = root.sedraWorkflowCanvas.mount(bild,zustand,{style:'diagram',readOnly:true,hint:'Zoomen mit dem Mausrad · Hintergrund ziehen zum Verschieben · Knoten anklicken für Details',select:inspizieren});
        // Eine Leseansicht bietet keine Layoutänderung an.
        const ordnen = bild.querySelector('[aria-label="Aufräumen: Knoten ordnen"]');if(ordnen) ordnen.remove();
        inspizieren(ausgewaehlt);
      }catch(err){ if(!tot) info.textContent = 'Diagramm nicht geladen: ' + (err.message || err) + '. Die Ausführungshistorie bleibt verfügbar.'; }
    })();
    return {box,ready,aktualisieren,abbauen(){tot=true;if(canvas) canvas.destroy();box.replaceChildren();}};
  }
  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.workflow_studio_debugger = {baue,statusText};
})();
