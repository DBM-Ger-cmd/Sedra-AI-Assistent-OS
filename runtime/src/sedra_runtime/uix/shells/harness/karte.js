// Harness-Shell – die Freigabe-Karte (SPEC_HARNESS_SHELL_v1 HS-22, G3 Stufe 2 U9): Werkzeug, Ziel, Stufe und Regel, Diff oder Befehlszeile;
// Erlauben · Für diese Sitzung erlauben (P0 M1, 1.11.) · Diff zeigen · Ablehnen. Dieselbe Karte steht im Posteingang; beantwortet wird über POST /api/harness/karten/<id> – dieselbe
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

  function sitzungMoeglich(k){
    if(!k || (k.art && k.art !== 'werkzeug') || k.vorbehalt || k.warnung || k.stufe === 'verboten') return false;
    return !!k.werkzeug && k.werkzeug !== 'modell_laden' && k.werkzeug !== 'modell_entladen';
  }
  // Nur Anzeige (der Server bildet das Muster selbst): Ordner der Datei, Anfang des Befehls, sonst das Ziel.
  function mustervorschau(k){
    if(k.werkzeug === 'befehl'){ const w = String(k.ziel || '').trim().split(/\s+/); return (w[1] === '-m' ? w.slice(0, 3) : w.slice(0, 2)).join(' ') + ' …'; }
    if(/^(lauf_)/.test(k.werkzeug)) return String(k.ziel || '');
    const rel = String(k.ziel || '').replace(/\\/g, '/'); const i = rel.lastIndexOf('/');
    return i > 0 ? rel.slice(0, i) + '/**' : 'Dateien in der Projektwurzel';
  }

  function karteKarte(S, a, k, entscheidung){
    const box = d().el('div', 'hs-karte');
    box.dataset.karte = k.karte_id;
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', 'Freigabe ' + k.karte_id);
    const kopf = d().el('div', 'hs-karte-kopf');
    kopf.append(d().el('span', 'hs-karte-icon', '⛨'), d().el('b', null, 'Freigabe: ' + (k.werkzeug || '')), d().el('code', 'hs-karte-ziel', k.ziel || ''));
    // A21 (1.11.): ein Satz statt „Stufe captain · Regel keine“ – wer entscheidet und warum
    const WER = {captain: 'Entscheidet der Captain', vorarbeiter: 'Entscheidet der Vorarbeiter', frei: 'Frei nach Katalog', verboten: 'Verboten'};
    const warum = k.regel === 'vorbehalt' ? 'fester Vorbehalt' : k.regel ? 'Regel „' + k.regel + '“' : 'keine Regel passt';
    const meta = d().el('div', 'hs-karte-meta hs-leise', (WER[k.stufe] || 'Entscheidet der Captain') + ' · ' + warum + (k.begruendung ? ' · ' + k.begruendung : ''));
    // Warnkasten (Nachtrag 434b108, W-2): die Ersetzung der ganzen Datei ist nicht zu übersehen – oben, vor dem Diff, in Warnfarbe.
    if(k.warnung){
      const kasten = d().el('div', 'hs-karte-warnung', '⚠ ' + (k.warnung.text || 'Ersetzt die ganze Datei.'));
      kasten.setAttribute('role', 'alert');
      box.append(kasten);
      box.classList.add('warnung');
    }
    // Stufe 3: wer entscheidet diese Karte? (HS-26) – beim Vorarbeiter, vorgelegt, Frist abgelaufen
    const an = d().el('div', 'hs-karte-an'); an.hidden = true;
    const anZeigen = x=>{
      const text = x.an === 'vorarbeiter' ? 'Beim Vorarbeiter – er entscheidet diese Karte mit Begründung. Du kannst sie übersteuern.'
                 : (x.vorgelegt ? 'Vom Vorarbeiter vorgelegt' + (x.vorgelegt.notiz ? ': ' + x.vorgelegt.notiz : '.')
                 : (x.frist_abgelaufen ? 'Der Vorarbeiter hat nicht rechtzeitig entschieden – jetzt beim Captain.' : ''));
      an.textContent = text; an.hidden = !text; box.classList.toggle('beim-vorarbeiter', x.an === 'vorarbeiter');
    };
    anZeigen(k);
    box.append(kopf, meta, an, diffZeilen(k.vorschau || ''));
    const fuss = d().el('div', 'hs-karte-fuss');
    box.append(fuss);
    const zeigeEntscheidung = e=>{
      const sitzung = e.entscheidung === 'sitzung';
      const erlaubt = e.entscheidung === 'erlauben' || sitzung;
      const vorarbeiter = String(e.von || '').startsWith('vorarbeiter:');
      fuss.replaceChildren(d().el('span', 'hs-ende ' + (erlaubt ? 'ok' : 'warn'), (sitzung ? 'Erlaubt – gilt für diese Sitzung' : erlaubt ? 'Erlaubt' : 'Abgelehnt') + (vorarbeiter ? ' (Vorarbeiter)' : (e.ueber === 'posteingang' ? ' (Posteingang)' : ''))),
                           ...(sitzung && e.erlaubnis ? [d().el('small', 'hs-leise', 'Ohne Karte bis zum Schließen: ' + e.erlaubnis.werkzeug + ' ' + e.erlaubnis.muster + ' (Einstellungen → Freigabe)')] : []),
                           ...(e.notiz ? [d().el('small', 'hs-leise', (vorarbeiter ? 'Begründung: ' : '') + e.notiz)] : []),
                           ...(e.zurueckgenommen ? [d().el('small', 'hs-karte-an', 'Vom Captain zurückgenommen: ' + (e.zurueckgenommen.grund || ''))] : []));
      box.classList.add('entschieden'); an.hidden = true;            // entschieden: kein „beim Vorarbeiter“ mehr
    };
    (S._karten || (S._karten = new Map())).set(k.karte_id, {aktualisieren: x=>{
      if(x.status !== 'beantwortet') anZeigen(x);
      if(x.status === 'beantwortet') zeigeEntscheidung({entscheidung: x.entscheidung, notiz: x.notiz, ueber: x.ueber, von: x.von, zurueckgenommen: x.zurueckgenommen, erlaubnis: x.erlaubnis});
    }});
    if(entscheidung){ zeigeEntscheidung(entscheidung); return box; }
    setTimeout(()=>aktualisieren(S, k.karte_id), 0);              // eine Karte aus dem Verlauf: Empfänger und Stand vom Server holen
    const notiz = d().el('input', 'hs-karte-notiz'); notiz.placeholder = 'Begründung (optional)'; notiz.setAttribute('aria-label', 'Begründung');
    const antworten = async weg=>{
      fuss.querySelectorAll('button').forEach(b=>{ b.disabled = true; });
      try{
        const out = await S.api('/api/harness/karten/' + k.karte_id, {method: 'POST', body: {weg, notiz: notiz.value.trim() || null}});
        zeigeEntscheidung({entscheidung: weg, notiz: notiz.value.trim(), ueber: 'karte', erlaubnis: out.erlaubnis});
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
    fuss.append(erlauben);
    // P0 M1: „Für diese Sitzung erlauben“ – nicht bei Vorbehalt, Warnkasten, Aufgabenkarte oder Modellen (der Server prüft dasselbe)
    if(sitzungMoeglich(k)){
      const sitzung = d().el('button', 'hs-knopf', 'Für diese Sitzung erlauben'); sitzung.type = 'button'; sitzung.dataset.weg = 'sitzung';
      sitzung.title = 'Gleichartige Aufrufe (' + mustervorschau(k) + ') laufen bis zum Schließen der Sitzung ohne Karte. Zurücknehmen: Einstellungen → Freigabe.';
      sitzung.onclick = ()=>antworten('sitzung');
      fuss.append(sitzung);
    }
    fuss.append(diff, ablehnen, notiz);
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
    return root.sedraHarness.reiter.stub(id, box, S);
  }

  root.sedraHarness = root.sedraHarness || {};
  // Eine Karte wurde anderswo entschieden (Vorarbeiter, Posteingang) oder hat den Empfänger gewechselt: die Anzeige nachziehen.
  async function aktualisieren(S, kartenId){
    const eintrag = S._karten && S._karten.get(kartenId);
    if(!eintrag) return;
    try{ eintrag.aktualisieren(await S.api('/api/harness/karten/' + kartenId)); }catch(_err){}
  }

  root.sedraHarness.karte = {diffZeilen, karteKarte, diffAnsicht, aktualisieren, sitzungMoeglich, mustervorschau};
})();
