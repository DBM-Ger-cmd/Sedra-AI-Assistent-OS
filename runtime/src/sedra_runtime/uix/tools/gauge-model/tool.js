// Instrument „Instrument: Modell“ (kind: instrument) – one cell of the Cockpit strip. It formats one reading of /api/strip and
// nothing else: the strip fetches, every instrument draws. Welches Modell geladen ist, mit Kontext.
// A cell is a tool like any other (COCKPIT_MODUL_v1 rule 11), so another shell can show it in a menu bar instead.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'gauge-model',
    field: 'model',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      this.body = d().el('div');
      el.append(this.body);
      d().clickable(el, ()=>ctx.shell.open({type:'model', id:'alle', title:'Werkstatt'}));
      this.update(null, null);
    },

    unmount(){ this.el.replaceChildren(); this.el.classList.remove('ok', 'warn', 'bad'); this.el.removeAttribute('role'); this.el.removeAttribute('tabindex'); this.el.onclick = this.el.onkeydown = null; this.el.title = ''; },   // HU-T18: der Container der Shell bleibt sauber

    // what the strip hands over: the whole reading, or (reading=null, problem) when the runtime did not answer
    update(reading, problem){
      const cell = (reading || {})[this.field] || null;
      this.el.classList.remove('ok', 'warn', 'bad');
      if(cell && cell.tone && cell.tone !== 'off') this.el.classList.add(cell.tone);
      this.body.replaceChildren(
        d().el('small', null, 'Modell'),
        d().el('b', null, problem ? '–' : (cell ? String(cell.value) : '…')),
        d().el('i', null, problem ? 'nicht lesbar' : (cell ? cell.hint || '' : ''))
      );
      this.el.title = problem || (cell ? 'Modell: ' + cell.value + ' · ' + (cell.hint || '') : 'Modell');
    },

    summary(){ return {label: 'Modell', value: null, tone: 'off', hint: 'Welches Modell geladen ist, mit Kontext.'}; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
