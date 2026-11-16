// Harness-Shell – die Freigabe-Karte (SPEC_HARNESS_SHELL_v1 HS-22, G3 Stufe 2 U9): Werkzeug, Ziel, Stufe und Regel, Diff oder Befehlszeile;
// Erlauben · Für diese Sitzung erlauben (P0 M1, 1.11.) · Diff zeigen · Ablehnen. Dieselbe Karte steht im Posteingang; beantwortet wird über POST /api/harness/karten/<id> – dieselbe
// Tür, dasselbe Audit (harness/freigabe.beantworten). Dazu der Reiter „Diff“ und die Färbung des Diffs. Daten werden nie zu HTML.
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const DE_KARTE = {karte_aria:'Freigabe {id}',karte_freigabe:'Freigabe',karte_wcaptain:'Entscheidet der Captain',karte_wvorarbeiter:'Entscheidet der Vorarbeiter',karte_wfrei:'Frei nach Katalog',karte_wverboten:'Verboten',karte_vorbehalt:'fester Vorbehalt',karte_regel:'Regel "{regel}"',karte_keine_regel:'keine Regel passt',karte_vorarbeiter1:'Beim Vorarbeiter – er entscheidet diese Karte mit Begründung. Du kannst sie übersteuern.',karte_vorarbeiter2:'Vom Vorarbeiter vorgelegt',karte_vorarbeiter3:'Der Vorarbeiter hat nicht rechtzeitig entschieden – jetzt beim Captain.',karte_erlaubt_sitzung:'Erlaubt – gilt für diese Sitzung',karte_erlaubt_befristet:'Erlaubt – befristet',karte_erlaubt_immer:'Erlaubt – Antrag „Immer“ gestellt',karte_erlaubt:'Erlaubt',karte_abgelehnt:'Abgelehnt',karte_vorarbeiter:'(Vorarbeiter)',karte_posteingang:'(Posteingang)',karte_notiz:'Begründung (optional)',karte_erlauben:'Erlauben',karte_erlauben_ersetzt:'Erlauben (ersetzt die Datei)',karte_diff:'Diff zeigen',karte_ablehnen:'Ablehnen',karte_sitzung:'Für diese Sitzung erlauben',karte_sitzung_titel:'Öffnet {muster} bis zum Schließen der Sitzung (höchstens 24 Stunden), ohne Karte. Zurücknehmen: Einstellungen → Freigabe.',karte_befristet:'Befristet erlauben (2 Stunden, 50 Aufrufe)',karte_befristet_titel:'Öffnet {muster} für diese Sitzung, 2 Stunden lang und höchstens 50 Aufrufe. Zurücknehmen: Einstellungen → Freigabe.',karte_immer:'Immer erlauben (Antrag)',karte_immer_titel:'Stellt einen Antrag in den Posteingang: Regel „frei“ für {muster}. Erst deine Freigabe dort macht sie gültig.',karte_befehle:'Befehle, die so anfangen: ',karte_ziel:'genau dieses Ziel: ',karte_ordner:'alle Dateien unter ',karte_datei:'genau diese Datei: ',karte_karte:'Karte ',karte_wartet:'wartet auf Freigabe',karte_nicht_lesbar:'Karte nicht lesbar: '}; const T = (k, ...a) => (root.t ? root.t(k, ...a) : (DE_KARTE[k] || k));

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
  function klartext(k){
    const m = mustervorschau(k);
    if(k.werkzeug === 'befehl') return T('karte_befehle') + m;
    if(/^(lauf_)/.test(k.werkzeug)) return T('karte_ziel') + m;
    return /\*\*$/.test(m) ? T('karte_ordner') + m.slice(0, -2) + ' (' + k.werkzeug + ')' : T('karte_datei') + m + ' (' + k.werkzeug + ')';
  }
  function mustervorschau(k){
    if(k.werkzeug === 'befehl'){ const w = String(k.ziel || '').trim().split(/\s+/); return (w[1] === '-m' ? w.slice(0, 3) : w.slice(0, 2)).join(' ') + ' …'; }
    if(/^(lauf_)/.test(k.werkzeug)) return String(k.ziel || '');
    const rel = String(k.ziel || '').replace(/\\/g, '/'); const i = rel.lastIndexOf('/');
    return i > 0 ? rel.slice(0, i) + '/**' : rel;
  }

  function karteKarte(S, a, k, entscheidung){
    const box = d().el('div', 'hs-karte');
    box.dataset.karte = k.karte_id;
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', T('karte_aria').replace('{id}', k.karte_id));
    const kopf = d().el('div', 'hs-karte-kopf');
    kopf.append(d().el('span', 'hs-karte-icon', '⛨'), d().el('b', null, T('karte_freigabe') + ': ' + (k.werkzeug || '')), d().el('code', 'hs-karte-ziel', k.ziel || ''));
    const WER = {captain: T('karte_wcaptain'), vorarbeiter: T('karte_wvorarbeiter'), frei: T('karte_wfrei'), verboten: T('karte_wverboten')};
    const warum = k.regel === 'vorbehalt' ? T('karte_vorbehalt') : k.regel ? T('karte_regel').replace('{regel}', k.regel) : T('karte_keine_regel');
    const meta = d().el('div', 'hs-karte-meta hs-leise', (WER[k.stufe] || T('karte_wcaptain')) + ' · ' + warum + (k.begruendung ? ' · ' + k.begruendung : ''));
    if(k.warnung){
      const kasten = d().el('div', 'hs-karte-warnung', '⚠ ' + (k.warnung.text || T('karte_erlauben_ersetzt')));
      kasten.setAttribute('role', 'alert');
      box.append(kasten);
      box.classList.add('warnung');
    }
    const an = d().el('div', 'hs-karte-an'); an.hidden = true;
    const anZeigen = x=>{
      const text = x.an === 'vorarbeiter' ? T('karte_vorarbeiter1')
                 : (x.vorgelegt ? T('karte_vorarbeiter2') + (x.vorgelegt.notiz ? ': ' + x.vorgelegt.notiz : '.')
                 : (x.frist_abgelaufen ? T('karte_vorarbeiter3') : ''));
      an.textContent = text; an.hidden = !text; box.classList.toggle('beim-vorarbeiter', x.an === 'vorarbeiter');
    };
    anZeigen(k);
    box.append(kopf, meta, an, diffZeilen(k.vorschau || ''));
    const fuss = d().el('div', 'hs-karte-fuss');
    box.append(fuss);
    const zeigeEntscheidung = e=>{
      const sitzung = e.entscheidung === 'sitzung', befristet = e.entscheidung === 'befristet', immer = e.entscheidung === 'immer';
      const erlaubt = e.entscheidung === 'erlauben' || sitzung || befristet || immer;
      const vorarbeiter = String(e.von || '').startsWith('vorarbeiter:');
      fuss.replaceChildren(d().el('span', 'hs-ende ' + (erlaubt ? 'ok' : 'warn'), (sitzung ? T('karte_erlaubt_sitzung') : befristet ? T('karte_erlaubt_befristet') : immer ? T('karte_erlaubt_immer') : erlaubt ? T('karte_erlaubt') : T('karte_abgelehnt')) + (vorarbeiter ? ' ' + T('karte_vorarbeiter') : (e.ueber === 'posteingang' ? ' ' + T('karte_posteingang') : ''))),     // die Klammern stehen schon in den Texten (strings_de2.js, strings_en2.js)
                           ...(sitzung && e.erlaubnis ? [d().el('small', 'hs-leise', 'Ohne Karte bis zum Schließen: ' + e.erlaubnis.werkzeug + ' ' + e.erlaubnis.muster + ' (' + T('einst_gruppe_agent') + ' → ' + T('esp_freigabe') + ')')] : []),
                           ...((befristet || immer) && e.erlaubnis && e.erlaubnis.hinweis ? [d().el('small', 'hs-leise', e.erlaubnis.hinweis)] : []),
                           ...(e.notiz ? [d().el('small', 'hs-leise', (vorarbeiter ? 'Begründung: ' : '') + e.notiz)] : []),
                           ...(e.zurueckgenommen ? [d().el('small', 'hs-karte-an', 'Vom Captain zurückgenommen: ' + (e.zurueckgenommen.grund || ''))] : []));
      box.classList.add('entschieden'); an.hidden = true;
    };
    (S._karten || (S._karten = new Map())).set(k.karte_id, {aktualisieren: x=>{
      if(x.status !== 'beantwortet') anZeigen(x);
      if(x.status === 'beantwortet') zeigeEntscheidung({entscheidung: x.entscheidung, notiz: x.notiz, ueber: x.ueber, von: x.von, zurueckgenommen: x.zurueckgenommen, erlaubnis: x.erlaubnis});
    }});
    if(entscheidung){ zeigeEntscheidung(entscheidung); return box; }
    setTimeout(()=>aktualisieren(S, k.karte_id), 0);
    const notiz = d().el('input', 'hs-karte-notiz'); notiz.placeholder = T('karte_notiz'); notiz.setAttribute('aria-label', T('karte_notiz'));
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
    const erlauben = d().el('button', 'hs-senden', k.warnung ? T('karte_erlauben_ersetzt') : T('karte_erlauben')); erlauben.type = 'button'; erlauben.onclick = ()=>antworten('erlauben');
    const diff = d().el('button', 'hs-knopf', T('karte_diff')); diff.type = 'button'; diff.onclick = ()=>root.sedraHarness.reiter.oeffnen(S, 'diff:' + k.karte_id);
    const ablehnen = d().el('button', 'hs-knopf', T('karte_ablehnen')); ablehnen.type = 'button'; ablehnen.onclick = ()=>antworten('ablehnen');
    fuss.append(erlauben);
    if(sitzungMoeglich(k)){
      const sitzung = d().el('button', 'hs-knopf', T('karte_sitzung')); sitzung.type = 'button'; sitzung.dataset.weg = 'sitzung';
      sitzung.title = T('karte_sitzung_titel').replace('{muster}', mustervorschau(k));
      sitzung.onclick = ()=>antworten('sitzung');
      fuss.append(sitzung);
      const befristet = d().el('button', 'hs-knopf', T('karte_befristet')); befristet.type = 'button'; befristet.dataset.weg = 'befristet';
      befristet.title = T('karte_befristet_titel').replace('{muster}', mustervorschau(k));
      befristet.onclick = ()=>antworten('befristet');
      const immer = d().el('button', 'hs-knopf', T('karte_immer')); immer.type = 'button'; immer.dataset.weg = 'immer';
      immer.title = T('karte_immer_titel').replace('{muster}', klartext(k));
      immer.onclick = ()=>antworten('immer');
      fuss.append(befristet, immer);
      sitzung.title = T('karte_sitzung_titel').replace('{muster}', mustervorschau(k));
    }
    fuss.append(diff, ablehnen, notiz);
    return box;
  }

  function diffAnsicht(S, id){
    const kid = id.slice(5);
    const box = d().el('div', 'hs-verlauf');
    const liste = d().el('div', 'hs-liste');
    box.append(liste);
    S.api('/api/harness/karten/' + kid).then(k=>{
      liste.replaceChildren(d().el('h2', 'hs-diff-titel', (k.werkzeug || '') + ' · ' + (k.ziel || '')),
                            d().el('div', 'hs-leise', T('karte_karte') + kid + ' · ' + (k.status === 'offen' ? T('karte_wartet') : 'beantwortet: ' + (k.entscheidung || ''))),
                            diffZeilen(k.vorschau || ''));
    }).catch(err=>liste.replaceChildren(d().el('div', 's-note bad', T('karte_nicht_lesbar') + err.message)));
    return root.sedraHarness.reiter.stub(id, box, S);
  }

  root.sedraHarness = root.sedraHarness || {};
  async function aktualisieren(S, kartenId){
    const eintrag = S._karten && S._karten.get(kartenId);
    if(!eintrag) return;
    try{ eintrag.aktualisieren(await S.api('/api/harness/karten/' + kartenId)); }catch(_err){}
  }

  root.sedraHarness.karte = {diffZeilen, karteKarte, diffAnsicht, aktualisieren, sitzungMoeglich, mustervorschau, klartext};
})();
