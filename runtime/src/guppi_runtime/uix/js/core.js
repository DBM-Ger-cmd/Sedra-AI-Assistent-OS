// Basics: API token, api(), small DOM and text helpers.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

const API_TOKEN = decodeURIComponent((location.hash || '').replace(/^#/, ''));

async function api(path, options={}){
  const headers = Object.assign({'X-GUPPI-Token': API_TOKEN}, options.headers || {});
  if(options.body && !headers['Content-Type']) headers['Content-Type']='application/json';
  let res;
  try{ res = await fetch(path, Object.assign({}, options, {headers})); }
  catch(_err){ throw new Error('Keine Verbindung zur Runtime (Server beendet oder Fenster neu starten).'); }   // the browser's "Failed to fetch" says nothing to the Captain
  const data = await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.message || (res.status === 403 ? 'Zugriff verweigert (Token oder Herkunft stimmt nicht; Fenster über START_SEDRA.bat öffnen).' : 'HTTP '+res.status));
  return data;
}

function el(tag, cls, text){
  const e = document.createElement(tag);
  if(cls) e.className = cls;
  if(text !== undefined) e.textContent = text;
  return e;
}

function escapeHtml(str){
  return str.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
}

function formatBytes(bytes){
  if(bytes < 1024) return bytes+' B';
  if(bytes < 1024*1024) return (bytes/1024).toFixed(1)+' KB';
  return (bytes/(1024*1024)).toFixed(1)+' MB';
}
