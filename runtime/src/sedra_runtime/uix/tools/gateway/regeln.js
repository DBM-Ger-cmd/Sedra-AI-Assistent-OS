// Das Regelbuch im GateWay (Menüpunkt „Regeln“, nicht mehr rechte Spalte): das Regelwerk Datenkategorien und Cloudsperre,
// Zeile für Zeile. Gezeichnet aus der Vorgaben-Liste von GET /api/gateway/vorgaenge (Feld `regeln`); schreibt nichts.
// Wird vor tool.js geladen; stellt root.sedraGatewayRegeln bereit.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  // rein: Regeln nach einem Suchwort filtern (node prüft das ohne Browser)
  function filter(regeln, q){
    const s = (q || '').trim().toLowerCase();
    if(!s) return (regeln || []).slice();
    return (regeln || []).filter(r=>[r.id, r.merkmal, r.kategorie, r.bezug, r.satz, r.tun, r.lokal, r.cloud].join(' ').toLowerCase().includes(s));
  }
  // rein: Ton je Cloud-Spalte
  function tone(r){ return r.cloud === 'nie' || r.cloud === '–' ? 'bad' : (r.cloud || '').startsWith('ja') ? 'ok' : 'warn'; }

  // Das Regelbuch als Element: Kopf, Suche, Zeilen. `list` ist die Antwort von /api/gateway/vorgaenge.
  function draw(list){
    const regeln = (list && list.regeln) || [];
    const box = d().el('div', 't-regelbuch-box');
    const head = d().el('div', 't-regelbuch-head');
    const sub = d().el('small', 's-muted', 'Policy ' + ((list && list.policy_version) || '') + ' · Regelwerk v0.1 · ' + regeln.length + ' Regeln');
    sub.title = (list && list.regelwerk) || '';
    head.append(d().el('h3', null, 'Regelbuch'), sub);
    box.append(head);
    const q = d().el('input'); q.placeholder = 'Suchen: IBAN, Art. 9, Kalkulation, R-07 …'; q.setAttribute('aria-label', 'Regel suchen');
    const tbl = d().el('div', 't-regelbuch-rows');
    const rows = (text)=>{
      const treffer = filter(regeln, text);
      tbl.replaceChildren();
      if(!treffer.length){ tbl.append(d().empty('Keine Regel passt zu „' + text + '“.')); return; }
      treffer.forEach(r=>{
        const row = d().el('div', 't-regelbuch-row');
        const top = d().el('div', 't-regelbuch-top');
        top.append(d().el('b', null, r.id), d().el('span', null, r.kategorie), d().el('span', 't-regelbuch-pill ' + tone(r), 'Cloud: ' + r.cloud));
        row.append(top);
        row.append(d().el('div', 's-muted', 'Merkmal ' + r.merkmal + ' · lokal: ' + r.lokal + ' · Prüfung: ' + r.review));
        row.append(d().el('div', null, r.satz));
        row.append(d().el('div', 't-regelbuch-tun', 'Was tun: ' + r.tun));
        row.append(d().el('small', 's-muted', 'Bezug (Annahme): ' + r.bezug));
        tbl.append(row);
      });
    };
    q.addEventListener('input', ()=>rows(q.value));
    box.append(q, tbl);
    box.append(d().el('small', 's-muted t-regelbuch-foot', 'Normbezüge sind Annahmen des Teams, keine Rechtsprüfung; der Datenschutzreview steht aus. Was in einer gesperrten Kategorie liegt, verlässt den Rechner nicht.'));
    rows('');
    return box;
  }

  root.sedraGatewayRegeln = {filter, tone, draw};
  if(typeof module !== 'undefined' && module.exports) module.exports = {filter, tone};
})();
