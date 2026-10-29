// Harness-Shell – Aufgaben-Freigaben (SPEC_HARNESS_SHELL_v1 HS-27, HS-29; G3 Stufe 3 N10): ein Reiter „Aufgaben“ mit
//  1. den Vorschlägen des Vorarbeiters (Kartenart `aufgabe`): Einträge abhaken, Frist und Zähler setzen, freigeben oder ablehnen,
//  2. den aktiven Aufgaben mit Rest an Aufrufen und Minuten und dem Knopf „Zurücknehmen“ (Läufe der Aufgabe mit stoppen – Vorgabe an),
//  3. einem Formular „Aufgabe freigeben“ (nur der Captain legt Aufgaben an; weite Muster und Schreiben-dann-Ausführen warnen rot).
// Gesendet wird über /api/harness/aufgaben und /api/harness/karten/<id> – dieselben Türen wie überall; Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  function minuten(a){
    if(a.rest_min === null || a.rest_min === undefined) return '';
    return a.rest_min >= 60 ? Math.floor(a.rest_min / 60) + ' h ' + (a.rest_min % 60) + ' min' : a.rest_min + ' min';
  }

  function eintraege(liste){
    const ul = d().el('ul', 'hs-auf-liste');
    (liste || []).forEach(e=>ul.append(d().el('li', null, e.werkzeug + ' · ' + e.muster)));
    return ul;
  }

  function sitzungsName(S, id){
    const s = S.sitzung && S.sitzung(id);
    return (s && s.titel ? s.titel + ' ' : '') + '(' + id + ')';
  }

  // ---- 1. ein Vorschlag des Vorarbeiters
  function vorschlagKarte(S, k, neuLaden){
    const doc = k.args || {};
    const box = d().el('div', 'hs-karte hs-auf-karte');
    box.dataset.karte = k.karte_id;
    box.append(d().el('div', 'hs-karte-kopf', ''));
    box.firstChild.append(d().el('span', 'hs-karte-icon', '⛨'), d().el('b', null, 'Vorschlag: ' + (doc.titel || k.ziel || '')), d().el('small', 'hs-leise', 'vom Vorarbeiter · Karte ' + k.karte_id));
    box.append(d().el('div', 'hs-leise', 'Sitzungen: ' + (doc.sitzungen || []).map(id=>sitzungsName(S, id)).join(', ')));
    const haken = (doc.erlaubt || []).map((e, i)=>{
      const zeile = d().el('label', 'hs-auf-zeile');
      const cb = d().el('input'); cb.type = 'checkbox'; cb.checked = true; cb.dataset.index = String(i);
      cb.setAttribute('aria-label', e.werkzeug + ' ' + e.muster);
      zeile.append(cb, d().el('span', null, e.werkzeug + ' · ' + e.muster));
      box.append(zeile);
      return cb;
    });
    const ende = doc.ende || {};
    const max = d().el('input', 'hs-auf-feld'); max.type = 'number'; max.min = '1'; max.max = '500'; max.value = ende.max_aufrufe || ''; max.setAttribute('aria-label', 'Höchstens so viele Aufrufe');
    const frist = d().el('input', 'hs-auf-feld'); frist.type = 'number'; frist.min = '1'; frist.max = '1440'; frist.placeholder = 'Minuten ab jetzt'; frist.setAttribute('aria-label', 'Frist in Minuten ab jetzt');
    const ersatz = d().el('div', 'hs-auf-grenzen');
    ersatz.append(d().el('label', 'hs-leise', 'Aufrufe höchstens '), max, d().el('label', 'hs-leise', ' Frist (statt ' + (ende.bis ? new Date(ende.bis).toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'}) + ' Uhr' : 'keine') + ') '), frist);
    box.append(ersatz);
    const notiz = d().el('input', 'hs-karte-notiz'); notiz.placeholder = 'Begründung (optional)'; notiz.setAttribute('aria-label', 'Begründung');
    const fuss = d().el('div', 'hs-karte-fuss');
    const antworten = async weg=>{
      fuss.querySelectorAll('button').forEach(b=>{ b.disabled = true; });
      try{
        const aenderungen = {};
        const auswahl = haken.filter(c=>c.checked).map(c=>Number(c.dataset.index));
        if(weg === 'erlauben'){
          if(!auswahl.length) throw new Error('Mindestens ein Eintrag muss bleiben.');
          if(auswahl.length !== haken.length) aenderungen.auswahl = auswahl;
          if(max.value && Number(max.value) !== ende.max_aufrufe) aenderungen.max_aufrufe = Number(max.value);
          if(frist.value) aenderungen.bis = new Date(Date.now() + Number(frist.value) * 60000).toISOString();
        }
        await S.api('/api/harness/karten/' + k.karte_id, {method: 'POST', body: {weg, notiz: notiz.value.trim() || null, aenderungen: Object.keys(aenderungen).length ? aenderungen : undefined}});
        S.hinweis(weg === 'erlauben' ? 'Aufgabe freigegeben.' : 'Vorschlag abgelehnt.');
        neuLaden();
      }catch(err){
        fuss.querySelectorAll('button').forEach(b=>{ b.disabled = false; });
        S.hinweis('Nicht gesendet: ' + err.message, 'bad');
      }
    };
    const ja = d().el('button', 'hs-senden', 'Freigeben'); ja.type = 'button'; ja.onclick = ()=>antworten('erlauben');
    const nein = d().el('button', 'hs-knopf', 'Ablehnen'); nein.type = 'button'; nein.onclick = ()=>antworten('ablehnen');
    fuss.append(ja, nein, notiz);
    box.append(fuss);
    return box;
  }

  // ---- 2. eine aktive Aufgabe
  function aufgabenZeile(S, a, neuLaden){
    const box = d().el('div', 'hs-karte ' + (a.status === 'aktiv' ? 'hs-auf-aktiv' : 'hs-auf-alt'));
    box.dataset.aufgabe = a.id;
    const kopf = d().el('div', 'hs-karte-kopf');
    kopf.append(d().el('b', null, a.titel), d().el('code', 'hs-karte-ziel', a.id));
    const rest = [a.rest_aufrufe !== null && a.rest_aufrufe !== undefined ? 'Rest ' + a.rest_aufrufe + ' Aufrufe' : null, a.rest_min !== null && a.rest_min !== undefined ? 'noch ' + minuten(a) : null].filter(Boolean).join(' · ');
    box.append(kopf, d().el('div', 'hs-leise', (a.status === 'aktiv' ? rest : a.status + (a.grund ? ' – ' + a.grund : '')) + ' · ' + a.aufrufe + ' Aufrufe bisher' + (a.vorschlag_von ? ' · Vorschlag des Vorarbeiters' : '')),
               d().el('div', 'hs-leise', 'Sitzungen: ' + a.sitzungen.map(id=>sitzungsName(S, id)).join(', ')), eintraege(a.erlaubt));
    if((a.modelle || []).length) box.append(d().el('div', 'hs-leise', 'Modelle: ' + a.modelle.join(', ')));
    (a.warnungen || []).forEach(w=>box.append(d().el('div', 'hs-karte-warnung', '⚠ ' + w)));
    if(a.status !== 'aktiv') return box;
    const laeufe = d().el('input'); laeufe.type = 'checkbox'; laeufe.checked = true; laeufe.setAttribute('aria-label', 'Läufe der Aufgabe mit stoppen');
    const lab = d().el('label', 'hs-auf-zeile'); lab.append(laeufe, d().el('span', 'hs-leise', 'Läufe der Aufgabe mit stoppen'));
    const zurueck = d().el('button', 'hs-knopf', 'Zurücknehmen'); zurueck.type = 'button';
    zurueck.onclick = async()=>{
      zurueck.disabled = true;
      try{
        const out = await S.api('/api/harness/aufgaben/' + a.id + '/zuruecknehmen', {method: 'POST', body: {laeufe_stoppen: laeufe.checked}});
        S.hinweis('Aufgabe zurückgenommen' + ((out.gestoppte_laeufe || []).length ? '; ' + out.gestoppte_laeufe.length + ' Lauf/Läufe gestoppt.' : '.'));
        neuLaden();
      }catch(err){ zurueck.disabled = false; S.hinweis('Rücknahme fehlgeschlagen: ' + err.message, 'bad'); }
    };
    const fuss = d().el('div', 'hs-karte-fuss'); fuss.append(zurueck, lab);
    box.append(fuss);
    return box;
  }

  // ---- 3. das Formular
  function formular(S, neuLaden){
    const f = d().el('form', 'hs-karte hs-auf-form');
    f.setAttribute('aria-label', 'Aufgabe freigeben');
    f.onsubmit = e=>e.preventDefault();
    const titel = d().el('input', 'hs-karte-notiz'); titel.placeholder = 'Titel der Aufgabe'; titel.setAttribute('aria-label', 'Titel');
    const projekt = d().el('select', 'hs-projektwahl'); projekt.setAttribute('aria-label', 'Projekt');
    (S.projekte || []).forEach(p=>{ const o = document.createElement('option'); o.value = p.id; o.textContent = p.name; projekt.append(o); });
    const sitzungen = d().el('div', 'hs-auf-sitzungen');
    const zeichneSitzungen = ()=>{
      sitzungen.replaceChildren(...(S.sitzungen || []).filter(s=>s.projekt === projekt.value).map(s=>{
        const l = d().el('label', 'hs-auf-zeile'); const cb = d().el('input'); cb.type = 'checkbox'; cb.value = s.id;
        l.append(cb, d().el('span', null, (s.titel || 'Ohne Titel') + (s.vorlage ? ' · ' + s.vorlage : '') + ' (' + s.id + ')'));
        return l;
      }));
      if(!sitzungen.childNodes.length) sitzungen.append(d().el('small', 'hs-leise', 'Noch keine Sitzung in diesem Projekt.'));
    };
    projekt.onchange = zeichneSitzungen; zeichneSitzungen();
    const erlaubt = d().el('textarea', 'hs-auf-text'); erlaubt.rows = 4;
    erlaubt.placeholder = 'Eine Zeile je Erlaubnis: Werkzeug Muster\ndatei_aendern docs/spec_entwuerfe/**\nlauf_starten run_tests';
    erlaubt.setAttribute('aria-label', 'Erlaubte Aufrufe');
    const modelle = d().el('input', 'hs-karte-notiz'); modelle.placeholder = 'Modelle (Rezept-IDs, durch Komma) – nur für Läufe mit Modell'; modelle.setAttribute('aria-label', 'Modelle');
    const max = d().el('input', 'hs-auf-feld'); max.type = 'number'; max.min = '1'; max.max = '500'; max.placeholder = 'Aufrufe'; max.setAttribute('aria-label', 'Höchstens so viele Aufrufe');
    const frist = d().el('input', 'hs-auf-feld'); frist.type = 'number'; frist.min = '1'; frist.max = '1440'; frist.placeholder = 'Minuten'; frist.setAttribute('aria-label', 'Frist in Minuten');
    const grenzen = d().el('div', 'hs-auf-grenzen'); grenzen.append(d().el('label', 'hs-leise', 'Aufrufe höchstens '), max, d().el('label', 'hs-leise', ' Frist (höchstens 24 h) '), frist);
    const meldung = d().el('div', 'hs-auf-meldung'); meldung.setAttribute('role', 'status');
    const ok = d().el('button', 'hs-senden', 'Freigeben'); ok.type = 'submit';
    ok.onclick = async()=>{
      meldung.replaceChildren();
      const liste = erlaubt.value.split('\n').map(z=>z.trim()).filter(Boolean).map(z=>{ const i = z.indexOf(' '); return i < 0 ? {werkzeug: z, muster: ''} : {werkzeug: z.slice(0, i), muster: z.slice(i + 1).trim()}; });
      const ende = {}; if(max.value) ende.max_aufrufe = Number(max.value); if(frist.value) ende.bis = new Date(Date.now() + Number(frist.value) * 60000).toISOString();
      ok.disabled = true;
      try{
        const out = await S.api('/api/harness/aufgaben', {method: 'POST', body: {titel: titel.value.trim(), projekt: projekt.value,
          sitzungen: [...sitzungen.querySelectorAll('input:checked')].map(c=>c.value), erlaubt: liste,
          modelle: modelle.value.split(',').map(m=>m.trim()).filter(Boolean), ende}});
        S.hinweis('Aufgabe ' + out.id + ' freigegeben.' + ((out.warnungen || []).length ? ' Achtung: ' + out.warnungen.length + ' Warnung(en).' : ''), (out.warnungen || []).length ? 'warn' : 'note');
        neuLaden();
      }catch(err){
        ok.disabled = false;
        meldung.replaceChildren(d().el('div', 'hs-karte-warnung', 'Nicht freigegeben: ' + err.message));
      }
    };
    f.append(d().el('b', null, 'Aufgabe freigeben'), d().el('small', 'hs-leise', 'Innerhalb davon läuft der Agent ohne Karte. Verboten, feste Vorbehalte und Warnkarten bleiben beim Captain.'),
             titel, projekt, sitzungen, erlaubt, modelle, grenzen, meldung, ok);
    return f;
  }

  // ---- der Reiter
  function ansicht(S, id){
    const box = d().el('div', 'hs-verlauf hs-aufgaben');
    const liste = d().el('div', 'hs-liste');
    box.append(liste);
    const a = {id, box, S, leer: ()=>false, laeuft: ()=>false, nachUnten(){}, abbauen(){}, stoppen(){}, senden: async ()=>false, laden: ()=>laden()};
    async function laden(){
      try{
        const [auf, entsch] = await Promise.all([S.api('/api/harness/aufgaben'), S.api('/api/decisions')]);
        const karten = await Promise.all((entsch.items || []).filter(x=>x.kind === 'harness_aufgabe').map(x=>S.api('/api/harness/karten/' + String(x.id).replace('harness:', ''))));
        const aktiv = (auf.aufgaben || []).filter(x=>x.status === 'aktiv');
        const alt = (auf.aufgaben || []).filter(x=>x.status !== 'aktiv').slice(-5).reverse();
        liste.replaceChildren(d().el('h2', 'hs-diff-titel', 'Aufgaben-Freigaben'),
          d().el('h3', 'hs-ueber', 'Vorschläge des Vorarbeiters (' + karten.length + ')'),
          ...(karten.length ? karten.map(k=>vorschlagKarte(S, k, laden)) : [d().el('small', 'hs-leise', 'Keine offenen Vorschläge.')]),
          d().el('h3', 'hs-ueber', 'Aktiv (' + aktiv.length + ')'),
          ...(aktiv.length ? aktiv.map(x=>aufgabenZeile(S, x, laden)) : [d().el('small', 'hs-leise', 'Keine aktive Aufgabe.')]),
          formular(S, laden),
          ...(alt.length ? [d().el('h3', 'hs-ueber', 'Zuletzt beendet'), ...alt.map(x=>aufgabenZeile(S, x, laden))] : []));
        if(S.freigabenLaden) S.freigabenLaden();
      }catch(err){ liste.replaceChildren(d().el('div', 's-note bad', 'Aufgaben nicht lesbar: ' + err.message)); }
    }
    laden();
    return a;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.aufgabe = {ansicht, vorschlagKarte, aufgabenZeile, formular, minuten};
})();
