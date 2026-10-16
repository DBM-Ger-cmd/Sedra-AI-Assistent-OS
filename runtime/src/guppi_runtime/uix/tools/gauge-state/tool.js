// Instrument „Instrument: Zustand“ (kind: instrument) – one cell of the Cockpit strip. It formats one reading of /api/strip and
// nothing else: the strip fetches, every instrument draws. Zustand der Runtime und der Audit-Kette.
// A cell is a tool like any other (COCKPIT_MODUL_v1 rule 11), so another shell can show it in a menu bar instead.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const tool = {
    id: 'gauge-state',
    field: 'state',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      this.body = d().el('div');
      // Der Guppy gehört dem Instrument, nicht einer Shell: bis zum 14.10.2026 trug es die Cockpit-Klassen `ck-guppy`
      // und war in jeder anderen Shell unsichtbar (gefunden beim Bau von Shell E). Jetzt bringt es seinen Stil selbst mit.
      el.classList.add('t-gauge-state');
      el.append(d().el('div', 't-gauge-state-fish'));      // Guppy, klein, im ersten Instrument (Regel 10)
      el.append(this.body);
      // this cell opens nothing: it is a reading, not a place
      this.update(null, null);
    },

    unmount(){ this.el.replaceChildren(); this.el.classList.remove('ok', 'warn', 'bad', 't-gauge-state'); this.el.removeAttribute('role'); },

    // what the strip hands over: the whole reading, or (reading=null, problem) when the runtime did not answer
    update(reading, problem){
      const cell = (reading || {})[this.field] || null;
      this.el.classList.remove('ok', 'warn', 'bad');
      if(cell && cell.tone && cell.tone !== 'off') this.el.classList.add(cell.tone);
      this.body.replaceChildren(
        d().el('small', null, 'SEDRA'),
        d().el('b', null, problem ? '–' : (cell ? String(cell.value) : '…')),
        d().el('i', null, problem ? 'nicht lesbar' : (cell ? cell.hint || '' : ''))
      );
      this.el.title = problem || (cell ? 'SEDRA: ' + cell.value + ' · ' + (cell.hint || '') : 'SEDRA');
    },

    summary(){ return {label: 'SEDRA', value: null, tone: 'off', hint: 'Zustand der Runtime und der Audit-Kette.'}; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
})();
