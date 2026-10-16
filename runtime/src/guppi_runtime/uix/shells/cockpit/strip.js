// Cockpit shell – the instrument strip (COCKPIT_MODUL_v1 §1, rule 11: instruments are tools, too).
// The strip gives every tool of kind `instrument` one cell and hands it the reading of /api/strip; it never formats a value itself.
// An instrument implements mount(el, ctx) like any tool and, on top of that, update(reading) – the one thing a cell needs.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  function makeStrip(host, shell){
    const cells = [];

    function build(){
      host.replaceChildren();
      cells.length = 0;
      shell.ctx.tools.byKind('instrument').forEach(manifest=>{
        const cell = d().el('div', 'ck-gauge');
        cell.dataset.tool = manifest.id;
        host.append(cell);
        const mod = shell.ctx.tools.mod(manifest.id);
        const ctx = shell.ctx.makeContext(manifest, null, shell.shellApi);
        const state = root.sedraLifecycle.mountTool(mod, cell, ctx, shell.onProblem);
        cells.push({manifest, mod, state, cell});
      });
      // the last cell belongs to the shell: what the keyboard does here (the sketch's right-hand hint)
      const hint = d().el('div', 'ck-gauge ck-hint');
      hint.append(d().el('small', null, 'Strg+K: Ort oder Auftrag · Alt+S: Oberfläche · Enter sendet'));
      host.append(hint);
    }

    async function refresh(){
      if(!cells.length) build();
      let reading;
      try{ reading = await shell.api('/api/strip'); }
      catch(err){
        cells.forEach(c=>{ if(c.mod.update) try{ c.mod.update(null, err.message); }catch(_e){} });
        return;
      }
      cells.forEach(c=>{
        if(!c.mod.update) return;
        try{ c.mod.update(reading, null); }
        catch(err){ shell.onProblem('Instrument ' + c.manifest.id, err); }
      });
    }

    return {build, refresh, cells};
  }

  root.sedraStrip = {makeStrip};
})();
