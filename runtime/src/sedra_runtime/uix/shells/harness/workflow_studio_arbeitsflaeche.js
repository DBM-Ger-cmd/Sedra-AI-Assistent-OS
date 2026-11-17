// Ein Workflow, eine Zeichenfläche: Bearbeiten, Startassistent und Laufdiagnose sind Modi.
(function(){
  const root=typeof window!=='undefined'?window:globalThis;
  function landing(c){
    const D=root.sedraDom,p=c.overviewParts,host=c.panels.overview;
    const tabs=D.el('div','hs-ws-start-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Arbeitsfläche öffnen');
    const entry=D.el('section','hs-ws-start-seite'),saved=D.el('section','hs-ws-start-seite hs-ws-gespeichert');
    const suffix=c.id.replace(/[^a-z0-9_-]/gi,'');
    const sections=[['einstieg','Einstieg',entry],['gespeichert','Zuletzt gespeichert',saved]];
    function select(key){sections.forEach(([id,,panel],i)=>{const active=key===id;panel.hidden=!active;tabs.children[i].setAttribute('aria-selected',String(active));tabs.children[i].tabIndex=active?0:-1;});}
    sections.forEach(([id,label,panel],i)=>{const b=D.el('button','hs-ws-start-tab',label);b.type='button';b.id='studio-'+suffix+'-'+id+'-tab';b.setAttribute('role','tab');panel.id='studio-'+suffix+'-'+id;b.setAttribute('aria-controls',panel.id);panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',b.id);b.onclick=()=>select(id);b.onkeydown=e=>{const step=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0;const next=e.key==='Home'?0:e.key==='End'?1:step?(i+step+2)%2:null;if(next!==null){e.preventDefault();tabs.children[next].click();tabs.children[next].focus();}};tabs.append(b);});
    const ai=D.el('details','hs-ws-start-extra');ai.append(D.el('summary','','Mit SEDRA einen Workflow entwerfen'),p.ask);
    const self=D.el('details','hs-ws-start-extra');self.append(D.el('summary','','Abläufe von SEDRA / Selbstabbild'),c.selfBox);
    const imp=D.el('section','hs-ws-start-import');imp.hidden=true;
    const back=D.el('button','hs-ws-knopf','Import schließen');back.type='button';back.onclick=()=>{imp.hidden=true;p.starts.children[1].focus();};imp.append(back,p.importBox);
    p.starts.children[1].onclick=()=>{imp.hidden=false;p.importBox.querySelector('input,textarea,button')?.focus();};
    p.starts.lastElementChild.remove();
    p.hero.querySelector('h2').textContent='Wie möchtest du beginnen?';p.hero.querySelector('p').textContent='Erstelle einen Workflow oder wechsle zu deiner gespeicherten Arbeit.';
    entry.append(p.hero,p.starts,imp,ai);
    const search=D.el('div','hs-ws-start-suche');p.find.placeholder='Gespeicherte Workflows durchsuchen …';search.append(p.find);
    const pager=D.el('nav','hs-ws-start-seiten');pager.setAttribute('aria-label','Gespeicherte Workflows durchblättern');
    const prev=D.el('button','hs-ws-knopf','Zurück'),next=D.el('button','hs-ws-knopf','Weiter'),count=D.el('span','hs-ws-hinweis');prev.type=next.type='button';count.setAttribute('role','status');pager.append(prev,count,next);
    let page=0;function paginate(){const cards=Array.from(c.cards.querySelectorAll('.t-wf-card'));cards.forEach((card,i)=>{card.hidden=i<page*6 || i>=(page+1)*6;});pager.hidden=cards.length<=6;prev.disabled=page===0;next.disabled=(page+1)*6>=cards.length;count.textContent=(page*6+1)+'–'+Math.min((page+1)*6,cards.length)+' von '+cards.length;}
    prev.onclick=()=>{page--;paginate();};next.onclick=()=>{page++;paginate();};
    const render=c.renderCards.bind(c);c.renderCards=filter=>{render(filter);page=0;paginate();};paginate();
    saved.append(D.el('h2','hs-ws-sektion','An einem Workflow weiterarbeiten'),search,c.cards,pager,self);
    host.replaceChildren(tabs,entry,saved);host.classList.add('hs-ws-start');select('einstieg');
    c.tabButtons.overview.querySelector('.t-wf-tab-label').textContent='Einstieg & Gespeichert';c.tabButtons.overview.setAttribute('aria-label','Einstieg & Gespeichert');
  }
  function attach(c){
    const D=root.sedraDom,H=root.sedraHarness,api=(p,o)=>c.ctx.api(p,o);
    landing(c);c.el.classList.add('hs-ws-arbeitsflaeche');
    const originalInspect=c.inspect.bind(c);
    c.inspect=()=>{originalInspect();if(c.editorMode==='live')return;const versions=c.inspector.querySelector('[aria-label="Frühere Revision"]');if(!versions)return;const open=D.el('button','','Revision zum Test öffnen');open.type='button';open.onclick=()=>c.safe(async()=>{if(!c.discard())return;const rec=await c.call('workflow',null,'revision_lesen',{id:c.wid,revision:Number(versions.value)});c.adopt(rec.workflow,rec.id,rec.revision);c.revisions=rec.revisions || [];c.inspectorOpen=false;c.setTab('editor');c.notice('Revision '+rec.revision+' zum Test geöffnet. Neuere Fassungen bleiben erhalten.');});versions.after(open);};
    const dock=D.el('section','hs-ws-live-dock');dock.hidden=true;
    const kontext=D.el('p','hs-ws-banner');kontext.setAttribute('role','status');dock.append(kontext);
    let snapshot=null,inspectLive=null,contextMenu=null,replayTimer=null,lastRun=null;
    const controls=D.el('div','hs-ws-knoepfe'),replay=D.el('button','hs-ws-knopf','Gespeicherten Ablauf nachvollziehen');replay.type='button';replay.disabled=true;controls.append(replay);dock.prepend(controls);
    const laeufe=H.workflow_studio_live.baueLaeufe(api,{workflowId:()=>c.wid,paused:()=>replayTimer!==null,shared:true,state:c.state,inspector:c.inspector,
      async prepare(r,doc){if(c.wid!==r.workflow_id)return false;lastRun=r;replay.disabled=!(r.result && r.result.knoten && r.result.knoten.length);c.state.doc=root.sedraWorkflowModel.clone(doc);c.revision=r.revision;c.saved=JSON.stringify(c.state.doc);c.view='canvas';return true;},
      onInspect(fn){inspectLive=fn;c.inspectorOpen=!!c.state.selected;c.inspector.hidden=!c.inspectorOpen;},draw(){if(c.canvas)c.canvas.draw();},redraw(){c.draw();}});
    dock.append(laeufe.box);c.panels.editor.append(dock);
    c.panels.editor.prepend(kontext);kontext.hidden=true;
    const sourceSummary=D.el('p','hs-ws-quellenstand');c.panels.editor.prepend(sourceSummary);
    const vorpruefung=D.el('p','hs-ws-vorpruefung');vorpruefung.setAttribute('role','status');vorpruefung.hidden=true;sourceSummary.after(vorpruefung);
    let vorStand='',vorSeq=0;
    async function vorpruefen(){let data={};try{data=JSON.parse(c.input.value);}catch(_e){}const ref=Object.values(data).find(v=>v && v.datei),wahl=(c.state.doc.meta || {}).sedra_model || {provider:'llama-cpp-server'},key=ref?ref.datei+'|'+wahl.provider+'|'+(wahl.model || ''):'',seq=++vorSeq;
      if(!ref){vorStand='';vorpruefung.hidden=true;return;}if(key===vorStand)return;vorStand=key;
      try{const out=await api('/api/actions',{method:'POST',body:{type:'workflow',id:null,verb:'vorpruefung',args:{datei:ref.datei,provider:wahl.provider,model:wahl.model || ''}}});if(seq!==vorSeq)return;const r=out.result || out;
        vorpruefung.className='hs-ws-vorpruefung '+(r.stufe || 'hinweis');vorpruefung.hidden=r.stufe==='ok';vorpruefung.textContent='Vorprüfung (beratend, der Start bleibt möglich): '+(r.kurz || '')+(r.empfehlung?' '+r.empfehlung:'');}
      catch(_e){if(seq===vorSeq)vorpruefung.hidden=true;}}

    const actionbar=D.el('section','hs-ws-startaktion'),startHint=D.el('p','hs-ws-hinweis'),pdfButton=D.el('button','hs-ws-knopf','PDF hinzufügen'),setupButton=D.el('button','hs-ws-knopf','Einrichtung öffnen'),saveButton=D.el('button','hs-ws-knopf','Änderungen speichern');
    actionbar.setAttribute('aria-label','Workflow starten und vorbereiten');startHint.id='studio-start-'+c.id;c.startButton.setAttribute('aria-describedby',startHint.id);pdfButton.type=setupButton.type=saveButton.type='button';pdfButton.onclick=()=>c.fileBox.click();setupButton.onclick=()=>c.setTab('runs');saveButton.onclick=()=>{if(c.editorMode==='live')c.setTab('editor');c.safe(()=>c.save());};actionbar.append(startHint,pdfButton,saveButton,setupButton,c.startButton);c.top.parentElement.prepend(actionbar);
    function updateStart(){
      const draft=snapshot || {doc:c.state.doc,wid:c.wid,saved:c.saved},process=root.sedraWorkflowProcess.has(draft.doc),dirty=JSON.stringify(draft.doc)!==draft.saved;let data={};try{data=JSON.parse(c.input.value);}catch(_e){}
      const missing=(c.exec?.dateifelder || []).some(key=>!data[key]?.datei);
      actionbar.hidden=!['editor','runs','live'].includes(c.tab);c.startButton.disabled=process || !draft.wid || dirty || missing;saveButton.hidden=!dirty;pdfButton.hidden=process || !missing;setupButton.hidden=!process && !!draft.wid;
      startHint.textContent=process?'Prozessentwurf: Die Ausführung ist noch nicht eingerichtet.':!draft.wid?'Workflow zuerst speichern.':dirty?'Vor dem Start die Änderungen speichern.':missing?'Für diesen Lauf fehlt noch die Rechnungs-PDF.':'Bereit: '+draft.doc.name+' · Revision '+(snapshot?.revision || c.revision)+' · Start legt einen neuen Lauf zur Freigabe vor.';
    }
    const showCheck=c.showCheck.bind(c);c.showCheck=(...args)=>{showCheck(...args);updateStart();};
    const begin=c.startButton.onclick;c.startButton.onclick=()=>{if(c.editorMode==='live')c.setTab('editor');return begin();};
    function updateContext(){updateStart();const meta=c.state.doc.meta || {},wahl=meta.sedra_model || {provider:'llama-cpp-server'};let source='noch keine PDF';try{source=Object.values(JSON.parse(c.input.value)).find(v=>v && v.datei)?.name || source;}catch(_e){}sourceSummary.textContent='Quelle bereit: '+source+' · KI: '+(wahl.provider==='nvidia'?'NVIDIA':'Lokal')+(wahl.model?' / '+wahl.model:'')+' · Ausgabe: '+(meta.sedra_report_file || 'rechnung-dashboard.html');sourceSummary.hidden=c.editorMode==='live';const h=c.el.querySelector('.t-wf-header h2');if(h)h.textContent=c.state.doc.name;}
    const upload=c.fileBox.onchange;c.fileBox.onchange=async e=>{await upload(e);updateContext();vorpruefen();};updateContext();vorpruefen();
    const assist=H.workflow_studio_assist.baueAssistent(api,()=>c.setTab('live'),{contextual:true});assist.box.hidden=true;c.panels.runs.append(assist.box);
    const empty=D.el('p','hs-ws-banner','Öffne zuerst einen Workflow aus dem Katalog oder speichere deinen Entwurf. Der Startassistent verwendet genau diesen Workflow.');empty.hidden=true;c.panels.runs.prepend(empty);
    const modelBox=D.el('div','hs-ws-modellwahl'),modelLabel=D.el('label','hs-ws-feld','Modell für KI-Schritte dieses Workflows'),modelSelect=D.el('select','hs-ws-wahl');modelSelect.setAttribute('aria-label','Workflow-Modell');modelLabel.append(modelSelect);
    const modelHint=D.el('p','hs-ws-hinweis','Die Auswahl wird mit dem Workflow gespeichert. NVIDIA erhält den Text der KI-Schritte erst nach der Lauf-Freigabe.');
    const loadModels=D.el('button','hs-ws-knopf','NVIDIA-Modellkatalog laden');loadModels.type='button';modelBox.append(modelLabel,loadModels,modelHint);c.panels.runs.prepend(modelBox);
    let models=[];
    async function modelle(remote=false){try{const out=await api('/api/actions',{method:'POST',body:{type:'workflow',id:null,verb:'modelle',args:{nvidia_catalog:remote}}});const items=(out.result || out).items || [];models=remote?models.filter(m=>m.provider!=='nvidia').concat(items):items;const current=(c.state.doc.meta || {}).sedra_model || {provider:'llama-cpp-server',model:null};if(!models.some(m=>m.provider===current.provider&&m.model===current.model))models.push({...current,label:current.provider+' · '+(current.model || 'geladenes Modell')});modelSelect.replaceChildren(...models.map((m,i)=>new Option(m.label,String(i))));modelSelect.value=String(models.findIndex(m=>m.provider===current.provider&&m.model===current.model));}catch(err){modelHint.textContent='Modellkatalog nicht geladen: '+err.message;}finally{loadModels.disabled=false;}}
    loadModels.onclick=()=>{loadModels.disabled=true;modelle(true);};
    modelSelect.onchange=()=>{const m=models[Number(modelSelect.value)];if(!m)return;c.change(()=>{c.state.doc.meta={...(c.state.doc.meta || {}),sedra_model:{provider:m.provider,model:m.model}};});c.notice('Modellwahl geändert. Workflow speichern, bevor du den Lauf vorlegst.');c.updateSteps();vorpruefen();};
    function restore(){if(!snapshot)return;const selected=c.state.selected;Object.assign(c,{wid:snapshot.wid,revision:snapshot.revision,saved:snapshot.saved,history:snapshot.history,future:snapshot.future});c.state.doc=snapshot.doc;c.state.selected=snapshot.doc.nodes.some(n=>n.id===selected)?selected:snapshot.selected;c.state.live={};snapshot=null;inspectLive=null;}
    replay.onclick=()=>{clearTimeout(replayTimer);if(!lastRun || !lastRun.result)return;const steps=lastRun.result.knoten || [];c.state.live={};let at=0;replay.disabled=true;
      const next=()=>{if(document.hidden || c.editorMode!=='live'){replay.disabled=false;return;}const step=steps[at++];if(!step){kontext.textContent='Wiedergabe des gespeicherten Laufs abgeschlossen. Es wurde nichts erneut ausgeführt.';replay.disabled=false;return;}for(const key of Object.keys(c.state.live))if(c.state.live[key]==='laeuft')c.state.live[key]='fertig';const node=c.state.doc.nodes.find(n=>n.name===step.name);if(node){c.state.selected=node.id;c.state.live[node.id]=step.status==='ok'?'laeuft':step.status==='uebersprungen'?'uebersprungen':'fehler';}kontext.textContent='Wiedergabe gespeicherter Laufdaten · '+at+'/'+steps.length+' · '+step.name+' · keine neue Ausführung';if(c.canvas)c.canvas.draw();if(inspectLive)inspectLive(c.state.selected);replayTimer=setTimeout(()=>{replayTimer=null;next();},800);};next();};
    function mode(name){
      const live=name==='live';
      if(!live){clearTimeout(replayTimer);replayTimer=null;replay.disabled=!(lastRun && lastRun.result && lastRun.result.knoten);}
      if(contextMenu){contextMenu.close();contextMenu=null;}
      if(live&&!snapshot)snapshot={doc:root.sedraWorkflowModel.clone(c.state.doc),wid:c.wid,revision:c.revision,saved:c.saved,selected:c.state.selected,history:c.history.slice(),future:c.future.slice()};
      if(!live)restore();
      c.editorMode=live?'live':'edit';c.el.dataset.studioMode=c.editorMode;dock.hidden=!live;
      kontext.hidden=!live;updateContext();
      if(live){c.inspector.removeAttribute('style');kontext.textContent=c.wid?c.state.doc.name+' · Revision '+c.revision+' · Wähle einen Lauf dieses Workflows. Dein Entwurf bleibt erhalten.':'Kein gespeicherter Workflow geöffnet. Wähle einen im Workflow-Katalog; Live und Startassistent bleiben an ihn gebunden.';laeufe.aktualisieren();}
      if(name==='runs'){empty.hidden=!!c.wid;modelBox.hidden=!c.wid;modelle();assist.box.hidden=!c.wid||!root.sedraWorkflowProcess.has(c.state.doc);if(!assist.box.hidden)assist.oeffne(c.wid);}
      c.draw();
      if(name==='overview')c.el.querySelector('.t-wf-header h2').textContent='Arbeitsfläche';
    }
    return {mode,updateContext,context(id,p){if(contextMenu)contextMenu.close();contextMenu=H.workflow_studio_knoten.open(c,id,p);},inspect(id){if(inspectLive)inspectLive(id);else c.inspector.hidden=true;},async openRun(id){c.setTab('live');return laeufe.oeffne(id);},async start(){if(!c.wid || c.dirty()){c.setTab('runs');c.notice('Workflow zuerst speichern, dann Quelle prüfen und vorlegen.');return;}const before=c.runId;await c.submitRun();if(c.runId && c.runId!==before){c.setTab('live');await laeufe.oeffne(c.runId);}},destroy(){clearTimeout(replayTimer);if(contextMenu)contextMenu.close();restore();laeufe.abbauen();assist.abbauen();dock.remove();}};
  }
  async function open(instance,object){
    await instance.ready;
    if(object.id==='alle'){instance.setTab(object.mode || 'editor');return;}
    if(instance.wid===object.id){instance.setTab(object.mode || 'editor');if(object.runId && instance.unifiedWorkspace)await instance.unifiedWorkspace.openRun(object.runId);return;}
    if(instance.editorMode==='live')instance.setTab('editor');
    const untouched=!instance.wid && JSON.stringify(instance.state.doc)===instance.initialSnapshot;
    if(!untouched && !instance.discard())return;
    await instance.safe(async()=>{if(object.id==='neu')instance.adopt(instance.blank(),null,null);else await instance.load(object.id,true);instance.setTab(object.mode || 'editor');});
    if(object.runId && instance.unifiedWorkspace)await instance.unifiedWorkspace.openRun(object.runId);
  }
  root.sedraHarness=root.sedraHarness||{};root.sedraHarness.workflow_studio_arbeitsflaeche={attach,open};
})();
