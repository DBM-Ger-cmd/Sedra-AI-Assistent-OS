// Harness-Shell – die Zeilen einer Antwort (aus verlauf.js ausgelagert, 1.11.2026, A20): Werkzeugzeile (HS-11, HS-29, HS-72), Denkzeile (HS-12),
// Fuß einer Antwort (HS-16). Daten werden nie zu HTML (sedraDom.el mit Text).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const AUSGABE_KURZ = 4000;               // HS-11: gekürzt ab 4000 Zeichen, mit „ganz anzeigen“
  const ENDE = {erledigt: ['Erledigt', 'ok'], nur_plan: ['Nur Plan – nichts ausgeführt', 'warn'], abgebrochen: ['Abgebrochen', 'warn'],
                fehler: ['Fehler', 'bad'], wartet: ['Wartet auf Freigabe', 'warn']};
  const STATUS = {ok: 'ok', fehler: 'Fehler', wiederholt: 'wiederholt', laeuft: 'läuft', wartet: 'wartet auf Freigabe', verboten: 'verboten',
                  abgelehnt: 'abgelehnt', abgebrochen: 'abgebrochen',
                  hinweis: 'Hinweis – nicht geschrieben'};            // Nachtrag 434b108 (B-8): Fehlerfarbe, weil nichts geschah

  // SPEC_WISSEN_KERN_v1 WK-14: unter einer Antwort, die Wissen nutzte, die Fundstellen; fremde Kennungen sind markiert. Rein aus den Daten.
  function wissenZeile(w, oeffnen){
    const ids = (w && w.ids) || [], fremd = (w && w.fremd) || [], belegt = new Set((w && w.belegt) || []);
    if(!ids.length && !fremd.length) return null;
    const det = d().el('details', 'hs-wissen' + (fremd.length ? ' warn' : ''));
    const n = ids.length;
    det.append(d().el('summary', null, '▣ Aus dem Wissen: ' + n + (n === 1 ? ' Fundstelle' : ' Fundstellen') + (fremd.length ? ' · ' + fremd.length + ' Kennung nicht aus dem Wissen' : '')));
    const body = d().el('div', 'hs-wissen-body');
    ids.forEach(id=>{ const c = d().el('span', 'hs-wissen-id' + (belegt.has(id) ? ' belegt' : ''), id); c.title = belegt.has(id) ? 'in der Antwort genannt' : 'gefunden, in der Antwort nicht genannt'; body.append(c); });
    if(fremd.length) body.append(d().el('div', 'hs-wissen-fremd', 'Nicht aus dem Wissen: ' + fremd.join(', ') + ' – diese Angabe prüfen.'));
    if(w.hinweis) body.append(d().el('small', 'hs-leise', w.hinweis));
    if(typeof oeffnen === 'function'){ const k = d().el('button', 'hs-knopf hs-klein', 'Im Wissen öffnen'); k.type = 'button'; k.onclick = ()=>oeffnen(ids); body.append(k); }
    det.append(body);
    return det;
  }

  // SPEC_WISSEN_KERN_v1 WK-14: „Im Wissen öffnen“ – die App Wissen bei der Suche (Ort aus ui/places.js)
  function wissenOeffnen(S){
    return ()=>{ const P = (root.sedraPlaces && root.sedraPlaces.PLACES) || []; const o = P.find(p=>p.id === 'wissen-suche') || P.find(p=>p.id === 'wissen'); if(o) root.sedraHarness.app.oeffnen(S, o); };
  }

  function wissenBlock(text){                                        // WK-15: ohne Modell die Fundstellen selbst
    const b = d().el('div', 'hs-antwort hs-wissen-antwort');
    b.append(d().el('div', 'hs-notiz s-note note', 'Kein Modell geladen – das hat das Wissen dazu:'), d().el('pre', 'hs-pre', text || ''));
    return b;
  }

  function ende(block, daten, wissenOeffnen){
    const art = ENDE[daten.ende];
    const fuss = d().el('div', 'hs-fuss');
    if(art){
      const t = d().el('span', 'hs-ende ' + art[1], art[0] + (daten.ende === 'fehler' && daten.grund ? ': ' + daten.grund : ''));
      fuss.append(t);
    }
    if(daten.abgeschnitten) fuss.append(d().el('span', 'hs-ende warn', 'An der Token-Grenze abgeschnitten'));
    const teile = [];
    if(daten.zuege) teile.push(daten.zuege + (daten.zuege === 1 ? ' Zug' : ' Züge'));
    const tk = daten.token || {};
    if(tk.ein || tk.aus) teile.push((tk.ein || 0).toLocaleString('de-DE') + ' Token ein · ' + (tk.aus || 0).toLocaleString('de-DE') + ' aus');
    if(teile.length) fuss.append(d().el('small', 'hs-leise', teile.join(' · ')));
    if(fuss.childNodes.length) block.append(fuss);
    const wz = daten.wissen ? wissenZeile(daten.wissen, wissenOeffnen) : null;
    if(wz) block.append(wz);
  }

  function werkzeugZeile(name, kurz, args){
    const row = d().el('details', 'hs-wz laeuft');
    const sum = d().el('summary');
    const status = d().el('span', 'hs-wz-status', 'läuft');
    sum.append(d().el('span', 'hs-wz-icon', '⚙'), d().el('b', 'hs-wz-name', name || '?'), d().el('span', 'hs-wz-kurz', kurz || ''),
               d().el('span', 'hs-wz-dauer', ''), status);
    if(args && typeof args.pfad === 'string' && args.pfad && /^datei_/.test(name || '')){          // Stufe 6 (HS-72): die Datei in der Vorschau öffnen und festhalten
      const pf = d().el('button', 'hs-knopf hs-klein hs-wz-pfad', '▸ Vorschau'); pf.type = 'button'; pf.dataset.pfad = args.pfad; pf.title = 'In der Vorschau öffnen und festhalten';
      sum.append(pf);
    }
    const body = d().el('div', 'hs-wz-body');
    body.append(d().el('small', 'hs-leise', 'Eingabe'), d().el('pre', 'hs-pre', args === undefined ? '' : JSON.stringify(args, null, 2)));
    row.append(sum, body);
    row._wz = {name: name || '?', kurz: kurz || '', args, status: 'laeuft'};          // die Daten der Zeile: die Vorschau zeigt sie im unteren Teil (vorschau.js, werkzeug)
    return row;
  }

  function werkzeugEnde(row, status, dauer, ergebnis, stufe, regel){
    if(row._wz){ Object.assign(row._wz, {status, dauer, ergebnis: String(ergebnis || ''), stufe, regel}); if(row._wzHaken) row._wzHaken(); }
    row.classList.remove('laeuft');
    row.classList.add(status === 'ok' ? 'ok' : (status === 'wiederholt' || status === 'wartet' || status === 'abgelehnt' ? 'warn' : 'bad'));
    row.querySelector('.hs-wz-status').textContent = STATUS[status] || status;
    if(typeof dauer === 'number') row.querySelector('.hs-wz-dauer').textContent = dauer < 1 ? Math.round(dauer * 1000) + ' ms' : dauer.toFixed(1) + ' s';
    if(stufe){                                           // HS-29: Stufe und Regel stehen am Werkzeugaufruf
      const marke = d().el('span', 'hs-wz-stufe ' + stufe, stufe + (regel ? ' · ' + regel : ''));
      marke.title = 'Einstufung: Stufe ' + stufe + (regel ? ', Regel ' + regel : ', keine Regel');
      row.querySelector('summary').insertBefore(marke, row.querySelector('.hs-wz-dauer'));
    }
    const body = row.querySelector('.hs-wz-body');
    const text = String(ergebnis || '');
    const pre = d().el('pre', 'hs-pre', text.length > AUSGABE_KURZ ? text.slice(0, AUSGABE_KURZ) + ' …' : text);
    body.append(d().el('small', 'hs-leise', 'Ausgabe' + (text.length > AUSGABE_KURZ ? ' (' + text.length.toLocaleString('de-DE') + ' Zeichen)' : '')), pre);
    if(text.length > AUSGABE_KURZ){
      const ganz = d().el('button', 'hs-knopf hs-klein', 'ganz anzeigen'); ganz.type = 'button';
      ganz.onclick = ()=>{ pre.textContent = text; ganz.remove(); };
      body.append(ganz);
    }
  }

  function denkZeile(text){
    const row = d().el('details', 'hs-denken');
    const sum = d().el('summary', null, text);
    row.append(sum, d().el('pre', 'hs-pre hs-denken-text', ''));
    return row;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.zeilen = {ende, wissenZeile, wissenOeffnen, wissenBlock, werkzeugZeile, werkzeugEnde, denkZeile, STATUS, ENDE, AUSGABE_KURZ};
})();
