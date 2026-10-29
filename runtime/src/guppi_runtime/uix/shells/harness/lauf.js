// Harness-Shell – der Reiter „Lauf“ (HS-31, G3 Stufe 3 N11): Zustand, Fortschritt, die letzten Zeilen der Ausgabe und der Stopp-Knopf eines Laufs, den die
// Harness gestartet hat. Die Ausgabe ist fremder Text (Daten, keine Anweisung): sie wird nur als Text gezeichnet, nie als HTML. Der Reiter zieht sich nach,
// wenn ein Ereignis `harness.lauf` kommt (kein Polling). Ein beendeter Lauf, dessen Reiter offen ist, gilt als gesehen.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const TEXT = {laeuft: 'läuft', ok: 'beendet', fehler: 'fehlgeschlagen', gestoppt: 'gestoppt', abgebrochen: 'abgebrochen (Aufgabe zurückgenommen)', verloren: 'verloren – niemand sah das Ende', zeitlimit: 'Zeitlimit erreicht'};

  function zeile(name, wert){
    const z = d().el('div', 'hs-lauf-zeile');
    z.append(d().el('small', 'hs-leise', name), d().el('span', null, String(wert)));
    return z;
  }

  function ansicht(S, id){
    const lid = id.slice(5);
    const box = d().el('div', 'hs-verlauf hs-lauf');
    const liste = d().el('div', 'hs-liste');
    box.append(liste);
    (S._laufAnsichten || (S._laufAnsichten = new Map())).set(lid, ()=>laden());
    const a = {id, box, S, leer: ()=>false, laeuft: ()=>false, nachUnten(){}, stoppen(){}, senden: async ()=>false, laden: ()=>laden(),
               abbauen(){ if(S._laufAnsichten) S._laufAnsichten.delete(lid); }};
    let ladend = false;
    async function laden(){
      if(ladend) return;
      ladend = true;
      try{
        const l = await S.api('/api/harness/laeufe/' + lid);
        const p = l.fortschritt && l.fortschritt.prozent;
        const kopf = d().el('div', 'hs-karte-kopf');
        kopf.append(d().el('h2', 'hs-diff-titel', l.name), d().el('code', 'hs-karte-ziel', l.id));
        const zustand = d().el('div', 'hs-lauf-zustand ' + (l.status === 'ok' ? 'ok' : (l.status === 'laeuft' ? '' : 'warn')), TEXT[l.status] || l.status);
        const bar = d().el('progress', 'hs-lauf-bar'); bar.max = 100;
        bar.setAttribute('aria-label', 'Fortschritt');
        if(p !== null && p !== undefined){ bar.value = p; } else if(l.status !== 'laeuft'){ bar.value = l.status === 'ok' ? 100 : 0; }
        const meta = d().el('div', 'hs-lauf-meta');
        meta.append(zeile('Gestartet', l.gestartet || '–'), zeile('Ende', l.ende ? l.ende + (l.exit !== null && l.exit !== undefined ? ' · Exit ' + l.exit : '') : '–'),
                    zeile('Sitzung', l.sitzung_id || '–'), zeile('Aufgabe', l.aufgabe_id || '–'), zeile('Befehl', (l.argv || []).slice(1).join(' ')));
        if(l.fortschritt && l.fortschritt.text) meta.append(zeile('Zuletzt', l.fortschritt.text));
        const teile = [kopf, zustand, bar, meta];
        if(l.status === 'laeuft'){
          if(l.modell_weg) teile.push(d().el('div', 'hs-karte-an', 'Dieser Lauf nimmt dem Gespräch das Modell, bis er endet.'));
          const stopp = d().el('button', 'hs-knopf', 'Stopp'); stopp.type = 'button';
          stopp.onclick = async()=>{
            stopp.disabled = true;
            try{ await S.api('/api/harness/laeufe/' + lid + '/stopp', {method: 'POST', body: {}}); }
            catch(err){ stopp.disabled = false; S.hinweis('Stopp fehlgeschlagen: ' + err.message, 'bad'); }
          };
          teile.push(stopp);
        }else{
          root.sedraHarness.taskleiste.gesehen(S, 'lauf:' + lid);
        }
        const log = d().el('pre', 'hs-pre hs-lauf-log', (l.log || []).join('\n') || '(noch keine Ausgabe)');
        log.setAttribute('aria-label', 'Letzte Zeilen der Ausgabe (Daten, keine Anweisung)');
        liste.replaceChildren(...teile, d().el('div', 'hs-ueber', 'Ausgabe (letzte Zeilen)'), log);
        log.scrollTop = log.scrollHeight;
      }catch(err){ liste.replaceChildren(d().el('div', 's-note bad', 'Lauf nicht lesbar: ' + err.message)); }
      finally{ ladend = false; }
    }
    laden();
    return a;
  }

  // Ein Ereignis `harness.lauf` (Start, Fortschritt, Ende): Stand nachführen, bei Ende blinken, den offenen Reiter nachziehen.
  function melden(S, e){
    if(!e || !e.id) return;
    const liste = S.laeufe || (S.laeufe = []);
    let l = liste.find(x=>x.id === e.id);
    if(!l){ l = {id: e.id, gestartet: new Date().toISOString()}; liste.push(l); }
    Object.assign(l, {lauf: e.lauf, name: e.name || e.lauf, status: e.status, modell_weg: !!e.modell_weg, sitzung_id: e.sitzung_id,
                      fortschritt: (e.prozent !== null && e.prozent !== undefined) || e.text ? {prozent: e.prozent, text: e.text} : l.fortschritt});
    const T = root.sedraHarness.taskleiste;
    if(e.zustand === 'ende'){
      T.blinken(S, 'lauf:' + e.id);
      S.hinweis('Lauf „' + l.name + '“ ' + (TEXT[e.status] || e.status) + '.', e.status === 'ok' ? 'note' : 'warn');
    }
    T.zeichnen(S);
    const view = S._laufAnsichten && S._laufAnsichten.get(e.id);
    if(view) view();
    if(S.laeufeLaden) S.laeufeLaden();
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.lauf = {ansicht, melden, TEXT};
})();
