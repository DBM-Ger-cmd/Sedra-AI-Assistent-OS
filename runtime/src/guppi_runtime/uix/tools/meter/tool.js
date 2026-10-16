// Werkzeug „Guppy-Meter“ – what the work costs: tokens per day, lines written, and the Münzloch as a picture of the running cost
// (COCKPIT_MODUL_v1 rule 5: Kosten gehören zu den Nachweisen). Reading only; the cost boundary itself comes with Build 9.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // tokens -> coins, the picture the Captain asked for: 1000 Token = 1 Kupfer, 100 Kupfer = 1 Silber, 100 Silber = 1 Gold (pure)
  function coins(tokens){
    const copper = Math.floor((Number(tokens) || 0) / 1000);
    return {gold: Math.floor(copper / 10000), silver: Math.floor(copper / 100) % 100, copper: copper % 100};
  }

  function coinLine(tokens){
    const c = coins(tokens);
    return 'Kupfer ' + c.copper + ' · Silber ' + c.silver + ' · Gold ' + c.gold;
  }

  const tool = {
    id: 'meter',

    mount(el, ctx){
      this.el = el; this.ctx = ctx;
      el.classList.add('t-meter');
      return this.refresh();
    },

    unmount(){ this.el.classList.remove('t-meter'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let v;
      try{ v = await this.ctx.api('/api/meter'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Meter nicht lesbar: ' + err.message)); return; }
      const box = d().el('div', 's-col');
      const today = ((v.tokens || {}).ranges || {}).today || {};
      const all = ((v.tokens || {}).ranges || {}).all || {};

      const hole = d().el('div', 't-meter-hole');
      hole.setAttribute('aria-hidden', 'true');
      const head = d().el('div', 's-row');
      head.append(hole);
      const text = d().el('div');
      text.append(d().el('b', null, d().fmtNumber(today.tokens || 0) + ' Token heute' + (today.runs ? ' · ' + today.runs + ' Läufe' : '')));
      text.append(d().el('div', 's-small s-muted', coinLine(today.tokens || 0) + ' – Münzen fallen, während das Modell arbeitet'));
      head.append(text);
      box.append(head);

      const t = d().el('table', 's-table');
      const rows = [['heute', today], ['7 Tage', ((v.tokens || {}).ranges || {})['7'] || {}], ['30 Tage', ((v.tokens || {}).ranges || {})['30'] || {}], ['insgesamt', all]];
      rows.forEach(([label, r])=>{
        const tr = d().el('tr');
        tr.append(d().el('td', null, label), d().el('td', null, d().fmtNumber(r.tokens || 0) + ' Token'), d().el('td', null, (r.runs || 0) + ' Läufe'));
        t.append(tr);
      });
      box.append(d().el('h5', 's-head', 'Token'), t);

      const lines = (v.ranges || {}).all || {};
      box.append(d().el('h5', 's-head', 'Zeilen'));
      box.append(d().el('div', null, d().fmtNumber(lines.total_lines || 0) + ' Zeilen insgesamt · GUPPI ' + Math.round((lines.guppi_share || 0) * 100) + ' %'));
      if(v.note) box.append(d().el('small', 's-muted', v.note));
      this.el.replaceChildren(box);
    },

    actions(){ return []; }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraMeterPure = {coins, coinLine};
  if(typeof module !== 'undefined' && module.exports) module.exports = {coins, coinLine};
})();
