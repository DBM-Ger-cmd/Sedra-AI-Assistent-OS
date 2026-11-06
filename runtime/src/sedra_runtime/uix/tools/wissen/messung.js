// Werkzeug „Wissen“ – die Ansicht Messung (SPEC_WERKZEUG_WISSEN_v2 §3.7, WZ2): Index und Nachmessung beantworten dieselbe Frage –
// wie gut findet der Speicher? Index als Karte (Modus, Abdeckung als Balken, letzter Lauf, Pause-Grund; „Details“ für den Rest),
// Nachmessung mit Fortschritt und drei Knöpfen je Frage statt einer Auswahlliste. Eine Bewertung zeichnet nur ihre Zeile neu (V7).
// Die Ansichtsnamen index und nachmessung öffnen den jeweiligen Abschnitt (D7.9 bleibt erfüllt). Vor tool.js geladen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const Z = ()=>root.sedraWissenZitate;
  const URTEILE = [['getroffen', 'getroffen'], ['nicht_getroffen', 'nicht getroffen'], ['ohne_antwort', 'ohne Antwort im Speicher']];

  function index(t, stand){
    const card = d().el('section', 's-card s-col t-wissen-index'); card.dataset.abschnitt = 'index';
    card.append(d().el('b', null, 'Index'));
    const p = Math.round((stand.abdeckung || 0) * 100);
    const balken = d().el('div', 't-wissen-balken gross'); const fuell = d().el('i'); fuell.style.width = p + '%'; balken.append(fuell);
    card.append(d().el('div', 's-row', (stand.modus === 'hybrid' ? 'Hybride Suche' : 'Nur Volltext') + ' · ' + p + ' % eingebettet (' +
                       d().fmtNumber(stand.vektoren) + ' von ' + d().fmtNumber(stand.abschnitte) + ')'), balken);
    const l = stand.letzter_lauf || {};
    card.append(d().el('small', 's-muted', 'Letzter Lauf: ' + (l.art ? l.art + ' · ' + l.status + ' · ' + d().fmtTime(l.start) + ' · ' + (l.eingebettet || 0) + ' eingebettet' : 'noch keiner')));
    if(!stand.bereit) card.append(d().el('div', 's-note warn', 'Nicht bereit: ' + (stand.grund || 'kein Embedding-Modell') + '. Die Suche läuft dann nur über den Volltext.'));
    if(stand.pause_grund) card.append(d().el('div', 's-note', 'Pausiert: ' + stand.pause_grund));
    const auf = t.s.indexDetails;
    card.append(d().button(auf ? 'Details zu' : 'Details', ()=>{ t.s.indexDetails = !auf; return t.draw(); }));
    if(auf){
      const tab = d().el('table', 's-table');
      [['Modell-ID', stand.modell_id || '–'], ['Neuaufbau', stand.neuaufbau ? 'läuft' : 'nein'], ['Gerät', (stand.geraet || 'cpu') + ' · Lage ' + (stand.lage || '–')],
       ['Server', stand.server_laeuft ? 'läuft' : 'aus'], ['Zerleger / Fusion', (stand.zerleger || '–') + ' / ' + (stand.fusion || '–')], ['Offene Vorschläge', String(stand.vorschlaege_offen || 0)]]
        .forEach(([k, v])=>{ const tr = d().el('tr'); tr.append(d().el('td', 's-muted', k), d().el('td', null, v)); tab.append(tr); });
      card.append(tab);
    }
    card.append(d().el('small', 's-muted', 'Das Einbetten läuft nur auf der CPU und hält an, solange ein Bau die GPU hat (WIS-12).'));
    return card;
  }

  function frageZeile(t, s){
    const row = d().el('div', 's-row t-wissen-frage-zeile'); row.dataset.frage = s.frage_sha256;
    row.append(d().el('small', null, d().fmtTime(s.zeit)), d().el('small', 's-muted', s.frage_sha256.slice(0, 12) + ' · ' + s.modus));
    row.append(Z().zitatKnoten(d().el('small', 't-wissen-ids'), (s.ids || []).map(i=>'[' + i + ']').join(' '), id=>t.zeigeTreffer(id)));
    const knoepfe = d().el('div', 's-row t-wissen-urteil'); knoepfe.setAttribute('role', 'group'); knoepfe.setAttribute('aria-label', 'Urteil');
    URTEILE.forEach(([v, l])=>{
      const b = d().button(l, async()=>{
        const out = await t.verb('nachmessung_bewerten', {frage_sha256: s.frage_sha256, urteil: v});
        if(out && out.status === 'fehler'){ t.sage(out); return t.draw(); }
        s.urteil = v;
        row.replaceWith ? row.replaceWith(frageZeile(t, s)) : t.draw();          // nur diese Zeile neu (V7)
        const fort = t.el.querySelector('.t-wissen-fortschritt'); if(fort) fort.textContent = fortschritt(t.d.nachmessung);
      }, s.urteil === v ? 'p' : '');
      b.setAttribute('aria-pressed', s.urteil === v ? 'true' : 'false');
      knoepfe.append(b);
    });
    row.append(knoepfe);
    return row;
  }

  function fortschritt(saetze){
    const n = (saetze || []).length, b = (saetze || []).filter(s=>s.urteil).length;
    return b + ' von ' + n + (n === 1 ? ' Frage' : ' Fragen') + ' bewertet';
  }

  function nachmessung(t){
    const card = d().el('section', 's-card s-col t-wissen-nachmessung'); card.dataset.abschnitt = 'nachmessung';
    card.append(d().el('b', null, 'Nachmessung'));
    const saetze = t.d.nachmessung || [];
    if(!saetze.length){ card.append(d().empty('Noch keine Fragen protokolliert. Jede Suche von dir landet hier (nur Hash und Treffer, kein Fragetext).')); return card; }
    card.append(d().el('small', 's-muted t-wissen-fortschritt', fortschritt(saetze)));
    saetze.forEach(s=>card.append(frageZeile(t, s)));
    return card;
  }

  const ansicht = {
    async laden(t){
      if(t.d.nachmessung) return;
      const out = await t.verb('nachmessung');
      if(out && out.status === 'fehler'){ t.hinweis = {text: 'Nachmessung nicht lesbar: ' + root.sedraWissenPure.ergebnisSatz(out), bad: true}; t.d.nachmessung = []; return; }
      t.d.nachmessung = (out && out.saetze) || [];
    },
    zeichnen(t){
      const box = d().el('div', 's-col');
      const stand = (t.d.speicher || {}).stand || {};
      const teile = [index(t, stand), nachmessung(t)];
      if(t.s.abschnitt === 'nachmessung') teile.reverse();                    // der verlangte Abschnitt steht oben
      teile[0].classList.add('t-wissen-markiert');
      box.append(...teile);
      return box;
    },
    aktionen(t){
      const out = [{label: 'Nachführen', run: async()=>{
        const r = await t.verb('nachfuehren');
        t.hinweis = r && r.status === 'erledigt' ? {text: 'Abgleich: ' + r.abgleich.neu + ' neu, ' + r.abgleich.geaendert + ' geändert, ' + r.abgleich.entfernt + ' entfernt · Einbetten: ' + r.einbetten.eingebettet + ' (' + r.einbetten.ende + (r.einbetten.grund ? ': ' + r.einbetten.grund : '') + ')'}
                                                 : {text: root.sedraWissenPure.ergebnisSatz(r), bad: true};
        await t.refresh(false);
      }}];
      // steht immer da: die Werkbank-Zeile fragt nur beim Zeichnen des Reiters, nicht nach jeder Bewertung
      out.push({label: 'Nachmessung abschließen', run: async()=>{
        if(!(t.d.nachmessung || []).some(s=>s.urteil)){ t.hinweis = {text: 'Erst mindestens eine Frage bewerten, dann abschließen.'}; return t.draw(); }
        const r = await t.verb('nachmessung_abschliessen');
        t.hinweis = r && r.status === 'erledigt' ? {text: r.fragen + ' Fragen, ' + r.getroffen + ' getroffen' + (r.anteil !== null && r.anteil !== undefined ? ' (' + Math.round(r.anteil * 100) + ' %)' : '') + ' · ' + r.datei}
                                                 : {text: root.sedraWissenPure.ergebnisSatz(r), bad: true};
        t.d.nachmessung = null;
        await t.refresh(false);
      }});
      return out;
    }
  };

  root.sedraWissenAnsichten = Object.assign(root.sedraWissenAnsichten || {}, {messung: ansicht});
  if(typeof module !== 'undefined' && module.exports) module.exports = {fortschritt};
})();
