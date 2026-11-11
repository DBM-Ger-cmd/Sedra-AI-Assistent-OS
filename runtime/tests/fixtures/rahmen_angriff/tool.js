// Werkzeug „Rahmen-Angriff“ – Prüf-Modul, läuft im abgeschotteten Rahmen. Jeder Versuch endet mit „blockiert“ (und nennt, wenn es ihn gibt, die verletzte CSP-Richtlinie) oder,
// wenn er gelingt, mit „GELUNGEN (Fehler: sollte nicht gehen)“. Die Gegenprobe „Status lesen“ und „Bild aus data:“ muss gelingen – sonst wäre der Rahmen nur kaputt.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const GELUNGEN = 'GELUNGEN (Fehler: sollte nicht gehen)';
  const verletzt = [];
  document.addEventListener('securitypolicyviolation', e=>verletzt.push(e.violatedDirective));
  const warte = ms=>new Promise(r=>setTimeout(r, ms));
  const richtlinien = async()=>{ await warte(150); const v = verletzt.splice(0); return v.length ? ' (' + [...new Set(v)].join(', ') + ')' : ''; };

  const tool = {
    id: 'rahmen-angriff',

    mount(el, ctx){
      this.el = el;
      const box = d().el('div', 's-col');
      const ausgabe = d().el('div', 's-col');
      const zeigen = text=>ausgabe.append(d().el('div', null, text));
      const versuch = (name, fn)=>d().button(name, async()=>{
        let r;
        try{ r = await fn(); }
        catch(err){ r = 'blockiert – ' + ((err && err.name) || 'Fehler'); }
        zeigen(name + ': ' + r + await richtlinien());
      }, 'p');
      const bild = url=>new Promise(res=>{
        const i = new Image();
        i.onload = ()=>res('geladen');
        i.onerror = ()=>res('nicht geladen');
        i.src = url;
        setTimeout(()=>res('keine Antwort'), 4000);
      });
      const socket = url=>new Promise(res=>{
        let s;
        try{ s = new WebSocket(url); }catch(err){ res('blockiert – ' + err.name); return; }
        s.onopen = ()=>res(GELUNGEN);
        s.onerror = ()=>res('blockiert – Verbindung verweigert');
        setTimeout(()=>res('blockiert – keine Antwort'), 4000);
      });

      box.append(d().el('h5', 's-head', 'Rahmen-Angriff'),
        versuch('Gegenprobe Status lesen', async()=>{ const r = await ctx.api('/api/status'); return 'erlaubt, ' + Object.keys(r || {}).length + ' Felder'; }),
        versuch('Gegenprobe Bild aus data', async()=>{ const r = await bild('data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'); return r === 'geladen' ? 'erlaubt, Bild geladen' : 'Fehler: ' + r; }),
        versuch('fetch eigene Adresse', async()=>{ await fetch('/api/strip'); return GELUNGEN; }),
        versuch('fetch Manifest', async()=>{ await fetch('/uix/manifest'); return GELUNGEN; }),
        versuch('fetch fremde Adresse', async()=>{ await fetch('https://example.org/'); return GELUNGEN; }),
        versuch('Bild von fremder Adresse', async()=>{ const r = await bild('https://example.org/x.png'); return r === 'geladen' ? GELUNGEN : 'blockiert – ' + r; }),
        versuch('WebSocket zur eigenen Adresse', ()=>socket('ws://' + location.host + '/')),
        versuch('Fenster öffnen', ()=>{ const w = window.open('https://example.org/'); return w ? GELUNGEN : 'blockiert – kein Fenster'; }),
        versuch('Seite der Shell wechseln', ()=>{ window.top.location.href = 'https://example.org/'; return GELUNGEN; }),
        versuch('Seite der Shell lesen', ()=>{ const t = window.parent.document.title; return GELUNGEN + ' ' + t; }),
        versuch('Speicher der Seite lesen', ()=>{ const v = window.localStorage.getItem('sedra'); return GELUNGEN + ' ' + v; }),
        versuch('Formular absenden', async()=>{
          window.__vor = 1;
          const f = document.createElement('form'); f.method = 'post'; f.action = '/api/objects';
          document.body.append(f); f.submit();
          await warte(500);
          return window.__vor === 1 ? 'blockiert – Seite blieb stehen' : GELUNGEN;
        }),
        ausgabe);
      el.replaceChildren(box);
    },

    unmount(){ if(this.el) this.el.replaceChildren(); },

    actions(){ return []; }
  };

  root.sedra.registerTool(tool);
})();
