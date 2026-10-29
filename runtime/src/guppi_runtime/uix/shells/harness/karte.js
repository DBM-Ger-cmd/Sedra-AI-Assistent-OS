// Harness-Shell – die Freigabe-Karte (SPEC_HARNESS_SHELL_v1 HS-22, G3 Stufe 2 U9): Werkzeug, Ziel, Stufe und Regel, Diff oder Befehlszeile;
// Erlauben · Diff zeigen · Ablehnen. Dieselbe Karte steht im Posteingang; beantwortet wird über POST /api/harness/karten/<id> – dieselbe
// Tür, dasselbe Audit (harness/freigabe.beantworten). Dazu der Reiter „Diff“ und die Färbung des Diffs. Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  function diffZeilen(text){
    const pre = d().el('pre', 'hs-pre hs-diff');
    String(text || '').split('\n').forEach(z=>{
      const cls = z.startsWith('+') && !z.startsWith('+++') ? 'hs-diff-neu' : (z.startsWith('-') && !z.startsWith('---') ? 'hs-diff-alt' : (z.startsWith('@@') ? 'hs-diff-ort' : ''));
      const zeile = d().el('span', cls, z + '\n');
      pre.append(zeile);
    });
    return pre;
  }

  function karteKarte(S, a, k, entscheidung){
    const box = d().el('div', 'hs-karte');
    box.dataset.karte = k.karte_id;
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', 'Freigabe ' + k.karte_id);
    const kopf = d().el('div', 'hs-karte-kopf');
    kopf.append(d().el('span', 'hs-karte-icon', '⛨'), d().el('b', null, 'Freigabe: ' + (k.werkzeug || '')), d().el('code', 'hs-karte-ziel', k.ziel || ''));
    const meta = d().el('div', 'hs-karte-meta hs-leise', 'Stufe ' + (k.stufe || '?') + ' · Regel ' + (k.regel || 'keine') + (k.begruendung ? ' · ' + k.begruendung : ''));
    // Warnkasten (Nachtrag 434b108, W-2): die Ersetzung der ganzen Datei ist nicht zu übersehen – oben, vor dem Diff, in Warnfarbe.
    if(k.warnung){
      const kasten = d().el('div', 'hs-karte-warnung', '⚠ ' + (k.warnung.text || 'Ersetzt die ganze Datei.'));
      kasten.setAttribute('role', 'alert');
      box.append(kasten);
      box.classList.add('warnung');
    }
    box.append(kopf, meta, diffZeilen(k.vorschau || ''));
    const fuss = d().el('div', 'hs-karte-fuss');
    box.append(fuss);
    const zeigeEntscheidung = e=>{
      const erlaubt = e.entscheidung === 'erlauben';
      fuss.replaceChildren(d().el('span', 'hs-ende ' + (erlaubt ? 'ok' : 'warn'), (erlaubt ? 'Erlaubt' : 'Abgelehnt') + (e.ueber === 'posteingang' ? ' (Posteingang)' : '')),
                           ...(e.notiz ? [d().el('small', 'hs-leise', e.notiz)] : []));
      box.classList.add('entschieden');
    };
    if(entscheidung){ zeigeEntscheidung(entscheidung); return box; }
    const notiz = d().el('input', 'hs-karte-notiz'); notiz.placeholder = 'Begründung (optional)'; notiz.setAttribute('aria-label', 'Begründung');
    const antworten = async weg=>{
      fuss.querySelectorAll('button').forEach(b=>{ b.disabled = true; });
      try{
        const out = await S.api('/api/harness/karten/' + k.karte_id, {method: 'POST', body: {weg, notiz: notiz.value.trim() || null}});
        zeigeEntscheidung({entscheidung: weg, notiz: notiz.value.trim(), ueber: 'karte'});
        if(out.antwort_id) a.strom(out.antwort_id, 0);
        else if(out.fortsetzung === 'kein_modell') a.notiz('Entschieden. Kein Modell geladen – die Antwort geht weiter, sobald du wieder schreibst.', 'warn');
      }catch(err){
        fuss.querySelectorAll('button').forEach(b=>{ b.disabled = false; });
        S.hinweis('Freigabe nicht gesendet: ' + err.message, 'bad');
      }
    };
    const erlauben = d().el('button', 'hs-senden', k.warnung ? 'Erlauben (ersetzt die Datei)' : 'Erlauben'); erlauben.type = 'button'; erlauben.onclick = ()=>antworten('erlauben');
    const diff = d().el('button', 'hs-knopf', 'Diff zeigen'); diff.type = 'button'; diff.onclick = ()=>root.sedraHarness.reiter.oeffnen(S, 'diff:' + k.karte_id);
    const ablehnen = d().el('button', 'hs-knopf', 'Ablehnen'); ablehnen.type = 'button'; ablehnen.onclick = ()=>antworten('ablehnen');
    fuss.append(erlauben, diff, ablehnen, notiz);
    return box;
  }

  // ---- ein Reiter mit dem Diff einer Karte (HS-22 „Diff zeigen“)
  function diffAnsicht(S, id){
    const kid = id.slice(5);
    const box = d().el('div', 'hs-verlauf');
    const liste = d().el('div', 'hs-liste');
    box.append(liste);
    S.api('/api/harness/karten/' + kid).then(k=>{
      liste.replaceChildren(d().el('h2', 'hs-diff-titel', (k.werkzeug || '') + ' · ' + (k.ziel || '')),
                            d().el('div', 'hs-leise', 'Karte ' + kid + ' · ' + (k.status === 'offen' ? 'wartet auf Freigabe' : 'beantwortet: ' + (k.entscheidung || ''))),
                            diffZeilen(k.vorschau || ''));
    }).catch(err=>liste.replaceChildren(d().el('div', 's-note bad', 'Karte nicht lesbar: ' + err.message)));
    return {id, box, S, leer: ()=>false, laeuft: ()=>false, nachUnten(){}, abbauen(){}, stoppen(){}, senden: async ()=>false, laden(){}};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.karte = {diffZeilen, karteKarte, diffAnsicht};
})();
