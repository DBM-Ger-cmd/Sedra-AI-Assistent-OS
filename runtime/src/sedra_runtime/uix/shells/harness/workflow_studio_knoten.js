// Kontextbezogene Einrichtung direkt am Knoten, ohne Kopie der Arbeitsfläche.
(function(){
  const root=typeof window!=='undefined'?window:globalThis;
  function open(c,id,point){
    const D=root.sedraDom,node=c.state.doc.nodes.find(n=>n.id===id),readonly=c.editorMode==='live';
    const box=D.el('section','hs-ws-knotenmenue');box.setAttribute('role','dialog');box.setAttribute('aria-label','Workflow-Knoten einrichten');
    const abort=new AbortController(),close=()=>{abort.abort();box.remove();};
    const head=D.el('div','hs-ws-knoepfe'),title=D.el('strong','',node?node.name:'Workflow einrichten'),x=D.el('button','hs-ws-knopf','Schließen');x.type='button';x.onclick=close;head.append(title,x);box.append(head);
    const status=D.el('p','hs-ws-hinweis');status.setAttribute('role','status');
    const action=(label,fn)=>{const b=D.el('button','hs-ws-knopf',label);b.type='button';b.onclick=fn;box.append(b);return b;};
    action('Mit SEDRA über diesen Knoten sprechen',()=>{c.state.selected=id;if(c.chat)c.chat.open('Hilf mir beim Einrichten von '+(node?node.name:'diesem Workflow')+'. Erkläre passende Quellen, Modellwahl und Ausgabe anhand des aktuellen Workflows.');close();});
    if(!readonly){
      if(!node || node.type.endsWith('.formTrigger'))action('Rechnung / PDF als Quelle hinzufügen …',()=>{c.fileBox.click();status.textContent='Wähle eine PDF. Sie wird dem Eingabefeld des geöffneten Workflows zugeordnet.';});
      if(node && node.type.endsWith('.informationExtractor')){
        const source=D.el('select','hs-ws-wahl');source.setAttribute('aria-label','Quellknoten der Extraktion');
        const ancestors=new Set(),visit=name=>{for(const [from,types] of Object.entries(c.state.doc.connections))if((types.main || []).some(branch=>branch.some(e=>e.node===name))&&!ancestors.has(from)){ancestors.add(from);visit(from);}};visit(node.name);
        c.state.doc.nodes.filter(n=>ancestors.has(n.name)).forEach(n=>source.append(new Option(n.name,n.name)));
        const field=D.el('input','hs-ws-eingabe');field.setAttribute('aria-label','Quellfeld der Extraktion');field.value='Rechnungstext';field.placeholder='Feld, z. B. Rechnungstext oder text';
        if(ancestors.has('Rechnungstext vorbereiten'))source.value='Rechnungstext vorbereiten';
        box.append(D.el('label','hs-ws-feld','Informationen aus diesem vorgelagerten Knoten und Feld lesen'),source,field);
        action('Informationsquelle übernehmen',()=>{if(!source.value || !field.value.trim()){status.textContent='Wähle Quellknoten und Feld.';return;}c.change(()=>{node.parameters.text='={{ $('+JSON.stringify(source.value)+').first().json['+JSON.stringify(field.value.trim())+'] }}';});status.textContent='Informationsquelle zugeordnet. Workflow speichern.';});
      }
      if(node && node.type.includes('.lmChat')){
        const select=D.el('select','hs-ws-wahl');select.setAttribute('aria-label','Modell am Workflow-Knoten');box.append(select);let choices=[];
        const load=async(remote=false)=>{try{const out=await c.ctx.api('/api/actions',{method:'POST',body:{type:'workflow',id:null,verb:'modelle',args:{nvidia_catalog:remote}}});const items=(out.result || out).items || [];choices=remote?choices.filter(m=>m.provider!=='nvidia').concat(items):items;select.replaceChildren(...choices.map((m,i)=>new Option(m.label,String(i))));}catch(err){status.textContent=err.message;}};
        action('NVIDIA-Modelle anzeigen',()=>load(true));
        action('Dieses Modell verwenden',()=>{const m=choices[Number(select.value)];if(!m)return;c.change(()=>{c.state.doc.meta={...(c.state.doc.meta || {}),sedra_model:{provider:m.provider,model:m.model}};node.type='@n8n/n8n-nodes-langchain.lmChatOpenAi';node.parameters={model:{__rl:true,mode:'list',value:m.model || 'loaded-local-model',cachedResultName:m.model || 'Aktuell geladenes lokales Modell'},options:{}};delete node.credentials;});title.textContent=m.label;status.textContent='Modell zugeordnet. Workflow speichern. Interne Knotennamen und Verbindungen bleiben erhalten.';});load();
      }
      if(node && node.type.endsWith('.dataTable')){
        const select=D.el('select','hs-ws-wahl');select.setAttribute('aria-label','Datenquelle Tabelle');box.append(select);
        c.call('workflow',null,'tabellen',{}).then(r=>{for(const t of r.tabellen || [])select.append(new Option(t.name,t.name));}).catch(err=>{status.textContent=err.message;});
        action('Tabelle als Quelle verwenden',()=>{if(!select.value)return;c.change(()=>{node.parameters.dataTableId={__rl:true,mode:'list',value:select.value,cachedResultName:select.value};});status.textContent='Tabelle zugeordnet. Bestehende Filter bleiben erhalten. Workflow speichern.';});
      }
      const dir=D.el('input','hs-ws-eingabe');dir.setAttribute('aria-label','Ausgabeordner innerhalb der Laufablage');dir.placeholder='z. B. Auswertung';dir.value=(c.state.doc.meta || {}).sedra_report_dir || '';
      box.append(D.el('label','hs-ws-feld','HTML-Ausgabeordner innerhalb der Laufablage'),dir);
      action('HTML-Ausgabeordner übernehmen',()=>{const value=dir.value.trim().replaceAll('\\','/');if(value.startsWith('/')||value.includes(':')||value.split('/').some(p=>p==='..'||p==='.' || /[<>"|?*]/.test(p))){status.textContent='Verwende einen relativen Unterordner ohne „..“.';return;}c.change(()=>{c.state.doc.meta={...(c.state.doc.meta || {}),sedra_report:'invoice-dashboard-v1',sedra_report_dir:value};});status.textContent='HTML-Ausgabe eingestellt. Workflow speichern.';});
      if(node)action('Weitere Knoteneinstellungen',()=>{c.nodeAction('open',id);close();});
    }else status.textContent='Laufansicht: Daten und Ergebnis prüfen. Zum Ändern in „Bearbeiten“ wechseln.';
    box.append(status);document.body.append(box);
    const r=box.getBoundingClientRect();box.style.left=Math.max(12,Math.min(point.x,innerWidth-r.width-12))+'px';box.style.top=Math.max(12,Math.min(point.y,innerHeight-r.height-12))+'px';
    document.addEventListener('pointerdown',e=>{if(!box.contains(e.target))close();},{capture:true,signal:abort.signal});
    document.addEventListener('keydown',e=>{if(e.key==='Escape')close();},{signal:abort.signal});x.focus();return {close};
  }
  root.sedraHarness=root.sedraHarness||{};root.sedraHarness.workflow_studio_knoten={open};
})();
