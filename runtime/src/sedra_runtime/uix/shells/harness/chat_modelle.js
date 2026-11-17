// Die Zuordnung gehört zum Chat. Lokales Laden/Entladen bleibt eine eigene Serveraktion.
(function(){
  const root=typeof window!=='undefined'?window:globalThis,D=()=>root.sedraDom;
  function auswahl(S){
    const box=D().el('section','hs-chat-modellwahl');box.setAttribute('aria-label','Modell dieses Chats');
    const active=S.aktive();
    box.append(D().el('strong','','Modell für diesen Chat'));
    if(!active || typeof active.senden!=='function'){box.append(D().el('p','hs-leise','Öffne einen Chat, um dessen Modell zu wählen.'));return box;}
    const select=D().el('select','hs-projektwahl');select.setAttribute('aria-label','Chat-Modell');
    const status=D().el('p','hs-leise','Lade die verfügbaren Modelle …');status.setAttribute('role','status');
    const save=D().el('button','hs-knopf p','Für diesen Chat verwenden');save.type='button';save.disabled=true;
    const fetch=D().el('button','hs-knopf','NVIDIA-Modellkatalog laden');fetch.type='button';
    const hardware=D().el('p','hs-leise','Die Auswahl gilt nur für diesen Chat. Lokale Modelle teilen sich den Modellserver; das Laden und Entladen wirkt auf alle lokalen Chats.');
    box.append(select,save,fetch,status,hardware);let choices=[];
    async function laden(remote=false){fetch.disabled=true;try{
      const out=await S.api('/api/actions',{method:'POST',body:{type:'workflow',id:null,verb:'modelle',args:{nvidia_catalog:remote}}});const data=out.result || out;
      choices=remote?choices.filter(m=>m.provider!=='nvidia').concat(data.items || []):(data.items || []);
      const current=active.modellWahl || {provider:'llama-cpp-server',model:null};
      if(!choices.some(m=>m.provider===current.provider&&m.model===current.model))choices.push({...current,label:current.provider+' · '+(current.model || 'geladenes Modell')});
      select.replaceChildren(...choices.map((m,i)=>new Option(m.label,String(i))));select.value=String(choices.findIndex(m=>m.provider===current.provider&&m.model===current.model));save.disabled=false;status.textContent='NVIDIA verwendet die eingerichtete API-Verbindung. Nachrichten dieses Chats gehen dann an diesen Anbieter.';
    }catch(err){status.textContent='Modelle nicht geladen: '+err.message;}finally{fetch.disabled=false;}}
    fetch.onclick=()=>laden(true);
    save.onclick=async()=>{const m=choices[Number(select.value)];if(!m)return;save.disabled=true;try{
      if(/^S-/.test(active.id))await S.api('/api/harness/sitzungen/'+active.id,{method:'PATCH',body:{provider:m.provider,modell:m.model}});
      active.modellWahl={provider:m.provider,model:m.model};status.textContent='Auswahl für diesen Chat gespeichert. Laufende Antworten behalten ihr bisheriges Modell.';
      root.sedraHarness.eingabe.modellZeigen(S);
    }catch(err){status.textContent='Nicht gespeichert: '+err.message;}finally{save.disabled=false;}};
    laden();return box;
  }
  root.sedraHarness=root.sedraHarness||{};root.sedraHarness.chat_modelle={auswahl};
})();
