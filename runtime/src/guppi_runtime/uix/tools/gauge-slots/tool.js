// Instrument „Slots“ (kind: instrument, Spec 4 D4.2.4) – eine Zelle der Leiste, eine Kachel im Dashboard von Shell D.
// Es formatiert die eine Lesung von GET /api/strip (Feld `slots`, `{value: '2/3', hint: '1 wartet', tone}`) und sonst nichts:
// die Shell holt, jedes Instrument zeichnet. Fehlt das Feld (kein Scheduler, Spec 2), steht „–“ mit „noch keine Daten“.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const MODELLE = {type: 'model', id: 'alle', title: 'Modelle und Slots', collection: true};

  // Was die Zelle zeigt (rein): Wert, Hinweis, Ton
  function zelle(reading, problem){
    if(problem) return {value: '–', hint: 'nicht lesbar', tone: null};
    const cell = (reading || {}).slots;
    if(!reading) return {value: '…', hint: '', tone: null};
    if(!cell) return {value: '–', hint: 'noch keine Daten', tone: null};
    return {value: String(cell.value), hint: cell.hint || '', tone: cell.tone && cell.tone !== 'off' ? cell.tone : null};
  }

  const tool = {
    id: 'gauge-slots',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-gauge-slots');
      this.body = d().el('div');
      el.append(this.body);
      d().clickable(el, ()=>ctx.shell.open(MODELLE));
      this.update(null, null);
    },

    unmount(){ this.el.replaceChildren(); this.el.classList.remove('t-gauge-slots', 'ok', 'warn', 'bad'); this.el.removeAttribute('role'); },

    update(reading, problem){
      const z = zelle(reading, problem);
      this.el.classList.remove('ok', 'warn', 'bad');
      if(z.tone) this.el.classList.add(z.tone);
      this.body.replaceChildren(d().el('small', null, 'Slots'), d().el('b', null, z.value), d().el('i', null, z.hint));
      this.el.title = problem || ('Slots: ' + z.value + (z.hint ? ' · ' + z.hint : ''));
    },

    summary(){ return {label: 'Slots', value: null, tone: 'off', hint: 'Belegte Slots von allen und wie viele Läufe warten.'}; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraGaugeSlotsPure = {zelle};
  if(typeof module !== 'undefined' && module.exports) module.exports = {zelle, tool};
})();
