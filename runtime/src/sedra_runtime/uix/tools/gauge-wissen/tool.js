// Instrument „Wissen“ (kind: instrument, SPEC_SHELL_WISSEN_v1 §4.3) – eine Zelle der Leiste. Es formatiert den Messwert `wissen`
// aus /api/strip und sonst nichts: „hybrid · 85 %“ und darunter, wie viele Vorschläge warten. Ohne Schalter „wissen“ fehlt das Feld,
// die Zelle sagt „aus“. Ton warn bei offenen Vorschlägen oder Volltext-Rückfall, bad, wenn die Runtime nicht antwortet.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // was die Zelle zeigt (rein): {wert, hinweis, ton}
  function anzeige(cell, problem){
    if(problem) return {wert: '–', hinweis: 'nicht lesbar', ton: 'bad'};
    if(cell === undefined) return {wert: '…', hinweis: '', ton: 'off'};
    if(cell === null) return {wert: 'aus', hinweis: 'Schalter „wissen“', ton: 'off'};
    return {wert: String(cell.value), hinweis: cell.hint || '', ton: cell.tone || 'off'};
  }

  const tool = {
    id: 'gauge-wissen',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      this.body = d().el('div');
      el.append(this.body);
      d().clickable(el, ()=>ctx.shell.open({type: 'wissen', id: 'speicher', title: 'Wissen'}));
      this.update(undefined, null);
    },

    unmount(){ this.el.replaceChildren(); this.el.classList.remove('ok', 'warn', 'bad'); this.el.removeAttribute('role'); this.el.removeAttribute('tabindex'); this.el.onclick = this.el.onkeydown = null; this.el.title = ''; },   // HU-T18: der Container der Shell bleibt sauber

    update(reading, problem){
      const a = anzeige(reading === undefined ? undefined : ((reading || {}).wissen || null), problem);
      this.el.classList.remove('ok', 'warn', 'bad');
      if(a.ton !== 'off') this.el.classList.add(a.ton);
      this.body.replaceChildren(d().el('small', null, 'Wissen'), d().el('b', null, a.wert), d().el('i', null, a.hinweis));
      this.el.title = problem || ('Wissen: ' + a.wert + (a.hinweis ? ' · ' + a.hinweis : '') + ' – Klick öffnet Wissen');
    },

    summary(){ return {label: 'Wissen', value: null, tone: 'off', hint: 'Modus, Abdeckung und offene Vorschläge des Wissensspeichers.'}; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  if(typeof module !== 'undefined' && module.exports) module.exports = {anzeige, tool};
})();
