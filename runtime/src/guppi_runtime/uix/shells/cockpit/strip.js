// Cockpit shell – the instrument strip (COCKPIT_MODUL_v1 §1, rule 11: instruments are tools, too).
// The strip gives every tool of kind `instrument` one cell and hands it the reading of /api/strip; it never formats a value itself.
// An instrument implements mount(el, ctx) like any tool and, on top of that, update(reading) – the one thing a cell needs.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  function makeStrip(host, shell){
    const cells = [];
    let leiste = null;

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
      // the last cell belongs to the shell: „?“ opens the shortcuts (SPEC_COCKPIT_BAUM_v1 §3.8) instead of a fixed line of text
      const hilfe = d().el('button', 'ck-hilfe', '?'); hilfe.type = 'button';
      hilfe.title = 'Tastenkürzel (?)'; hilfe.setAttribute('aria-label', 'Tastenkürzel anzeigen');
      hilfe.onclick = ()=>{ if(shell.rahmen) shell.rahmen.kuerzel(); };
      // Stufe 6 (S6-E1): Rekorder und Umschalter stehen rechts in der Leiste, nicht schwebend über dem Werkstück
      const platz = d().el('div', 'ck-sx-platz');
      host.append(platz, hilfe);
      if(root.sedraWechsel && root.sedraWechsel.inLeiste) root.sedraWechsel.inLeiste(platz);
      // Stufe 6 (§2.1): passt nicht alles hinein, wandern ruhige Zellen in „+n ▾“ – nichts wird mehr abgeschnitten
      leiste = root.sedraLeiste ? root.sedraLeiste.makeLeiste(host, ()=>cells.map(c=>({el: c.cell, id: c.manifest.id, order: c.manifest.order})), 'ck-gauge') : null;
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
      if(leiste) leiste.ordnen();                    // die Werte sind neu, die Breiten auch
    }

    return {build, refresh, cells};
  }

  root.sedraStrip = {makeStrip};
})();
