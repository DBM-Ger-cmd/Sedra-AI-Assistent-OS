// Werkzeug „Wissen“ – die Ansicht Suche (SPEC_WERKZEUG_WISSEN_v2 §3.2, WZ1: die Startansicht).
// Ein Feld, Enter sucht; Treffer als Karten: die Stelle als Titel, Quelle · Datei · Stand darunter, ein Balken für die Relevanz im
// Verhältnis zum besten Treffer, Suchwörter markiert, der Text gekürzt („mehr“), Kennung und Ränge unter „Details“.
// Tastatur: ↑/↓ wechseln den Treffer, Enter zeigt die Fundstelle, Esc zurück ins Feld. Frage und Treffer liegen in der Ablage.
// Vor tool.js geladen; registriert sich unter sedraWissenAnsichten.suche.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const Z = ()=>root.sedraWissenZitate;
  const LANG = 400;                          // ab so vielen Zeichen ist ein Treffer gekürzt (6 Zeilen im Stil)

  function uhrzeit(ms){
    const t = new Date(ms);
    return isNaN(t.getTime()) ? '' : String(t.getHours()).padStart(2, '0') + ':' + String(t.getMinutes()).padStart(2, '0');
  }

  // ein Text mit Verweisen [W…] und markierten Suchwörtern in einen Knoten
  function textKnoten(node, text, woerter, onId){
    Z().zitatTeile(text).forEach(teil=>{
      if(teil.id !== undefined){ Z().zitatKnoten(node, '[' + teil.id + ']', onId); return; }
      Z().hervorheben(teil.text, woerter).forEach(st=>node.append(st.mark ? d().el('mark', 't-wissen-mark', st.text) : st.text));
    });
    return node;
  }

  async function suchen(t, frage, k){
    const s = t.s;
    s.frage = frage; s.k = k; s.aktiv = null; s.aufgeklappt = []; s.details = []; t.hinweis = null;
    t.laedt = true; t.draw();
    const r = await t.verb('suche', {frage, k});
    t.laedt = false;
    if(r && r.status === 'fehler'){ t.sage(r); s.ergebnis = null; }
    else{ s.ergebnis = r; s.ergebnisZeit = Date.now(); t.frisch = true; }
    t.draw();
  }

  const umschalten = (liste, id)=>{ const l = (liste || []).slice(); const i = l.indexOf(id); if(i >= 0) l.splice(i, 1); else l.push(id); return l; };

  function karte(t, tr, bester, woerter, index){
    const s = t.s, offen = (s.aufgeklappt || []).indexOf(tr.id) >= 0;
    const card = d().el('div', 's-card s-col t-wissen-treffer' + (s.aktiv === tr.id ? ' t-wissen-aktiv' : ''));
    card.dataset.id = tr.id; card.tabIndex = 0;
    const head = d().el('div', 't-wissen-kopf');
    head.append(d().el('b', 't-wissen-stelle', tr.stelle || tr.datei || tr.id));
    head.title = 'Quelle ' + tr.quelle + ' in der Ansicht „Quellen“ zeigen';
    d().clickable(head, ()=>t.zeigeQuelle(tr));
    const balken = d().el('div', 't-wissen-balken'); balken.title = 'Relevanz im Verhältnis zum besten Treffer';
    const fuell = d().el('i'); fuell.style.width = Math.round(Z().relevanz(tr.punkte, bester) * 100) + '%'; balken.append(fuell);
    const meta = d().el('div', 's-row t-wissen-meta');
    meta.append(d().el('small', 's-muted', [tr.quelle_titel || tr.quelle, tr.datei, 'Stand ' + String(tr.datum || '').slice(0, 10)].filter(Boolean).join(' · ')));
    if(tr.stufe !== undefined && tr.stufe >= 3) meta.append(d().el('span', 't-wissen-marke', 'ab Stufe ' + tr.stufe));
    if(tr.personenbezug) meta.append(d().el('span', 't-wissen-marke warn', 'Personenbezug'));
    if((tr.befunde || []).length) meta.append(d().el('span', 't-wissen-marke bad', 'Befund'));
    meta.append(balken);
    const text = textKnoten(d().el('pre', 't-wissen-text' + (offen ? '' : ' t-wissen-kurz')), tr.text, woerter, id=>t.zeigeTreffer(id));
    card.append(head, meta, text);
    if((tr.befunde || []).length) card.append(d().el('small', 's-note warn', 'Befund des Inhaltsschutzes: ' + tr.befunde.join(', ') + ' – Agenten sehen diesen Abschnitt nicht.'));
    if((s.details || []).indexOf(tr.id) >= 0) card.append(d().el('small', 's-muted t-wissen-details', root.sedraWissenPure.trefferZeile(tr)));
    const row = d().el('div', 's-row t-wissen-knoepfe');
    // Fundstelle: das Nachweis-Werkzeug daneben hört darauf (wissen.auswahl); hier klappt der Treffer ganz auf
    const fund = ()=>{
      if(!offen) t.ctx.bus.emit('wissen.auswahl', {id: tr.id, quelle: String(tr.quelle || '')});
      s.aufgeklappt = umschalten(s.aufgeklappt, tr.id); s.aktiv = tr.id; t.draw();
    };
    row.append(d().button('Fundstelle', fund), d().button('Quelle', ()=>t.zeigeQuelle(tr)),
               d().button('Ins Gespräch', ()=>{ t.ctx.bus.emit('wissen.auswahl', {id: tr.id, quelle: String(tr.quelle || ''), zweck: 'gespraech', stelle: String(tr.stelle || '')}); t.hinweis = {text: 'Die Fundstelle [' + tr.id + '] steht jetzt im Gespräch.'}; t.draw(); }));
    if(String(tr.text || '').length > LANG) row.append(d().button(offen ? 'weniger' : 'mehr', ()=>{ s.aufgeklappt = umschalten(s.aufgeklappt, tr.id); t.draw(); }));
    row.append(d().button((s.details || []).indexOf(tr.id) >= 0 ? 'Details zu' : 'Details', ()=>{ s.details = umschalten(s.details, tr.id); t.draw(); }));
    card.append(row);
    card.onkeydown = e=>{
      if(e.target !== card) return;
      const alle = t.el.querySelectorAll('.t-wissen-treffer');
      if(e.key === 'ArrowDown' || e.key === 'ArrowUp'){ e.preventDefault(); const n = alle[index + (e.key === 'ArrowDown' ? 1 : -1)]; if(n) n.focus(); }
      else if(e.key === 'Enter'){ e.preventDefault(); fund(); }
      else if(e.key === 'Escape'){ const f = t.el.querySelector('input.t-wissen-frage'); if(f) f.focus(); }
    };
    return card;
  }

  const ansicht = {
    zeichnen(t){
      const s = t.s, box = d().el('div', 's-col');
      const form = d().el('form', 's-row t-wissen-suchform'); form.onsubmit = e=>e.preventDefault();
      const input = d().el('input', 't-wissen-frage'); input.value = s.frage || ''; input.placeholder = 'Frage an das Wissen – Enter sucht';
      input.setAttribute('aria-label', 'Frage an den Wissensspeicher');
      if(!s.ergebnis && !t.laedt) input.classList.add('t-wissen-fokus');
      const kLabel = d().el('label', 's-row s-small t-wissen-k'); kLabel.append(d().el('span', 's-muted', 'Treffer:'));
      const k = d().el('select'); [5, 10, 20].forEach(n=>{ const o = d().el('option', null, String(n)); o.value = String(n); k.append(o); }); k.value = String(s.k || 5);
      k.setAttribute('aria-label', 'Zahl der Treffer'); kLabel.append(k);
      form.append(input, kLabel, d().button('Suchen', ()=>suchen(t, input.value, Number(k.value) || 5), 'p', {absenden: true}));
      box.append(form);
      if(t.laedt){ box.append(d().el('div', 's-note t-wissen-laedt', 'Suche läuft …')); return box; }
      const r = s.ergebnis;
      if(!r){ box.append(d().el('small', 's-muted', 'Noch keine Suche. Jeder Treffer trägt seine Kennung [W…]; die Stelle führt zur Quelle.')); return box; }
      const n = (r.treffer || []).length;
      const kopf = d().el('div', 's-row s-small s-muted t-wissen-ergebnis');
      kopf.append(d().el('span', null, n + (n === 1 ? ' Treffer' : ' Treffer') + ' in ' + (r.ms || 0) + ' ms · ' + (r.modus || '–') + (r.hinweis ? ' · ' + r.hinweis : '')));
      if(!t.frisch && s.ergebnisZeit){
        kopf.append(d().el('span', null, '· Treffer von ' + uhrzeit(s.ergebnisZeit)));
        kopf.append(d().button('neu suchen', ()=>suchen(t, s.frage, s.k || 5)));
      }
      box.append(kopf);
      if(r.modus !== 'hybrid' && !r.hinweis) box.append(d().el('div', 's-note warn', 'Nur Volltextsuche: Treffer mit anderen Worten können fehlen. Warum, steht unter „Messung“.'));
      if(!n){ box.append(d().empty('Dazu habe ich im Wissen nichts gefunden.')); return box; }
      const bester = Math.max.apply(null, r.treffer.map(x=>Number(x.punkte) || 0));
      const liste = d().el('div', 's-col t-wissen-liste'); liste.setAttribute('role', 'list');
      r.treffer.forEach((tr, i)=>liste.append(karte(t, tr, bester, r.woerter || [], i)));
      box.append(liste);
      return box;
    },
    aktionen(t){
      return [{label: 'Neue Suche', run: ()=>{ Object.assign(t.s, {frage: '', ergebnis: null, ergebnisZeit: null, aktiv: null, aufgeklappt: [], details: []}); t.hinweis = null; t.draw(); }}];
    }
  };

  root.sedraWissenAnsichten = Object.assign(root.sedraWissenAnsichten || {}, {suche: ansicht});
  if(typeof module !== 'undefined' && module.exports) module.exports = {textKnoten, suchen};
})();
