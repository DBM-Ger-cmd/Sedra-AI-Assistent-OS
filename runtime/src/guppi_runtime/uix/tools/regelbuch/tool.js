// Werkzeug „KI GateWay · Regelbuch“ (Ticket B6-G-03): das Regelwerk Datenkategorien und Cloudsperre, Zeile für Zeile.
// Liest nur GET /api/gateway/vorgaenge (Feld `regeln`), schreibt nichts, kein eigener Speicher. Stil nur unter .t-regelbuch, nur Token.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // rein: Regeln nach einem Suchwort filtern (node prüft das ohne Browser)
  function filter(regeln, q){
    const s = (q || '').trim().toLowerCase();
    if(!s) return regeln.slice();
    return regeln.filter(r=>[r.id, r.merkmal, r.kategorie, r.bezug, r.satz, r.tun, r.lokal, r.cloud].join(' ').toLowerCase().includes(s));
  }
  // rein: Ton je Cloud-Spalte
  function tone(r){ return r.cloud === 'nie' || r.cloud === '–' ? 'bad' : (r.cloud || '').startsWith('ja') ? 'ok' : 'warn'; }

  const tool = {
    id: 'regelbuch',

    mount(el, ctx){
      this.el = el; this.ctx = ctx; el.classList.add('t-regelbuch');
      this.off = ctx.bus.on('tools.refresh', ()=>this.refresh());
      return this.refresh();
    },

    unmount(){ if(typeof this.off === 'function') this.off(); this.el.classList.remove('t-regelbuch'); this.el.replaceChildren(); },

    async refresh(){
      if(!this.el) return;
      let list;
      try{ list = await this.ctx.api('/api/gateway/vorgaenge'); }
      catch(err){ this.el.replaceChildren(d().el('div', 's-note bad', 'Das Regelbuch ist nicht lesbar: ' + err.message)); return; }
      this.regeln = list.regeln || [];
      this.aktiv = this.ctx.object && this.ctx.object.id && this.ctx.object.id !== 'alle' ? this.ctx.object.id : null;
      this.draw(list);
    },

    draw(list){
      const box = d().el('div', 't-regelbuch-box');
      const head = d().el('div', 't-regelbuch-head');
      const sub = d().el('small', 's-muted', 'Policy ' + (list.policy_version || '') + ' · Regelwerk v0.1 · 16 Regeln'); sub.title = list.regelwerk || '';
      head.append(d().el('h3', null, 'Regelbuch'), sub);
      box.append(head);
      const q = d().el('input'); q.placeholder = 'Suchen: IBAN, Art. 9, Kalkulation, R-07 …'; q.setAttribute('aria-label', 'Regel suchen');
      q.addEventListener('input', ()=>this.rows(q.value));
      box.append(q);
      this.tbl = d().el('div', 't-regelbuch-rows'); box.append(this.tbl);
      box.append(d().el('small', 's-muted t-regelbuch-foot', 'Normbezüge sind Annahmen des Teams, keine Rechtsprüfung; der Datenschutzreview steht aus. Was in einer gesperrten Kategorie liegt, verlässt den Rechner nicht – auch nicht pseudonymisiert. Neue Regeln sind neue Zeilen mit neuer Version.'));
      this.el.replaceChildren(box);
      this.rows('');
    },

    rows(q){
      const rows = filter(this.regeln, q);
      this.tbl.replaceChildren();
      if(!rows.length){ this.tbl.append(d().empty('Keine Regel passt zu „' + q + '“.')); return; }
      rows.forEach(r=>{
        const row = d().el('div', 't-regelbuch-row');
        const top = d().el('div', 't-regelbuch-top');
        top.append(d().el('b', null, r.id), d().el('span', null, r.kategorie), d().el('span', 't-regelbuch-pill ' + tone(r), 'Cloud: ' + r.cloud));
        row.append(top);
        row.append(d().el('div', 's-muted', 'Merkmal ' + r.merkmal + ' · lokal: ' + r.lokal + ' · Prüfung: ' + r.review));
        row.append(d().el('div', null, r.satz));
        row.append(d().el('div', 't-regelbuch-tun', 'Was tun: ' + r.tun));
        row.append(d().el('small', 's-muted', 'Bezug (Annahme): ' + r.bezug));
        this.tbl.append(row);
      });
    }
  };

  if(root.sedra) root.sedra.registerTool(tool);
  root.sedraRegelbuchPure = {filter, tone};
  if(typeof module !== 'undefined' && module.exports) module.exports = {filter, tone};
})();
