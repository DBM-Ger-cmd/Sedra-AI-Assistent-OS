// Stalled rework (plan 2026-10-04): a rework that keeps failing for the same cause waits for the Captain's hint.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.
// It wraps renderRunning (models.js) so the card appears under "Läuft gerade".

async function renderStalled(box){
  let v;
  try{ v = await api('/api/rework'); }
  catch(err){ return; }
  if(!v.stalled.length) return;
  box.append(el('h3',null,'Rework steckt fest'));
  v.stalled.forEach(s=>{
    const c = el('div','mcard'); const info = el('div');
    const what = s.detector === 'ping_pong' ? 'zwei Fehler im Wechsel' : 'derselbe Fehler';
    info.append(el('b',null,'Job '+s.job_id+(s.scenario?' · '+s.scenario:'')));
    info.append(el('small',null,'Gestoppt: '+what+' (Versuch '+s.count+' wäre eine Wiederholung). Fehler-Kennung: '+(s.failure||'?')));
    if(s.hint) info.append(el('small',null,'Letzter Hinweis: '+s.hint));
    const text = el('textarea');
    text.rows = 3; text.style.width = '100%'; text.placeholder = 'Hinweis für den nächsten Versuch: wo liegt die Ursache?';
    info.append(text);
    c.append(info);
    const b = el('button','action','Hinweis geben');
    b.onclick = async()=>{
      if(!text.value.trim()){ alert('Bitte einen Hinweis eingeben.'); return; }
      b.disabled = true;
      try{ await api('/api/rework/hint',{method:'POST',body:JSON.stringify({job_id:s.job_id,text:text.value})}); }
      catch(e){ alert(e.message); }
      refreshModels();
    };
    c.append(b);
    box.append(c);
  });
}

const renderRunningBase = renderRunning;
renderRunning = async function(box){ await renderRunningBase(box); await renderStalled(box); };
