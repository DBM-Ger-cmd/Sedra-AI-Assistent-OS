// Werkzeug „Rahmen-Probe“ – läuft im abgeschotteten Rahmen (Stufe C, docs/PLAN_STUFE_C_2026-10-19.md). Zeigt, was der Rahmen darf
// und was nicht. Jeder Versuch, der verboten ist, muss mit einer Meldung enden und darf nichts ändern.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'rahmen-probe',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      const box = d().el('div', 's-col');
      const ausgabe = d().el('div', 's-col');
      const zeigen = (text)=>ausgabe.append(d().el('small', null, text));
      const versuch = (name, fn)=>d().button(name, async()=>{
        try{ zeigen(name + ': ' + (await fn())); }
        catch(err){ zeigen(name + ': verweigert – ' + (err && err.message || err)); }
      }, 'p');

      box.append(d().el('h5', 's-head', 'Rahmen-Probe'),
        d().el('small', 's-muted', 'Jeder verbotene Versuch endet mit „verweigert“.'),
        versuch('Status lesen (erlaubt)', async()=>{ const r = await ctx.api('/api/status'); return 'erlaubt, ' + Object.keys(r || {}).length + ' Felder'; }),
        versuch('Fremde Route (nicht im Manifest)', async()=>{ await ctx.api('/api/update/zurueck', {method: 'POST', body: {}}); return 'gelungen (Fehler: sollte nicht gehen)'; }),
        versuch('Freigabe erteilen', async()=>{ await ctx.shell.decide('x', 'ja'); return 'gelungen (Fehler: sollte nicht gehen)'; }),
        versuch('Seite der Shell lesen', ()=>{ const t = window.parent.document.title; return 'gelungen (Fehler: sollte nicht gehen) ' + t; }),
        versuch('Token-Zugang suchen', ()=>{ if(typeof window.sedraApi === 'undefined') return 'nicht vorhanden'; return 'vorhanden (Fehler: sollte nicht sein)'; }),
        versuch('Hinweis an die Shell (erlaubt)', async()=>{ await ctx.shell.notify('Hallo aus dem Rahmen', 'note'); return 'angekommen'; }),
        ausgabe);
      el.replaceChildren(box);
    },

    unmount(){ if(this.el) this.el.replaceChildren(); },

    actions(){ return []; }
  };

  root.sedra.registerTool(tool);
})();
