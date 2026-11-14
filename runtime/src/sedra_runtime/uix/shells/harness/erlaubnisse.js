// Harness-Shell – „Gilt gerade“ (S4.1 UI, SPEC_FREIGABEN_S4_v1 FS-22 bis FS-24): eine Liste aller Erlaubnisse (diese Sitzung · befristet), gelesen aus
// GET /api/harness/erlaubnisse. Spalten: Was (Klartext, Muster dabei) · Wo · Wie lange / noch · Warum · Herkunft · Zurücknehmen. Die Katalogregeln mit
// Stufe „frei“ stehen im Katalog-Editor darüber, nicht doppelt. Zurücknehmen geht über die bestehenden Wege (Sitzung: PATCH, befristet: POST).
// Steht in den Einstellungen unter Agent → Freigabe-Modus. Daten werden nie zu HTML (sedraDom.el mit Text).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  const HERKUNFT = {captain: 'Captain', vorarbeiter: 'Vorarbeiter', vorlage: 'Vorlage'};
  const zeit = iso=>{ const t = String(iso || ''); return t.length >= 16 ? t.slice(0, 10) + ' ' + t.slice(11, 16) : t; };

  function wasText(e){
    return (e.was || []).map(w=>(w.werkzeug || '?') + ' ' + (w.muster || '')).join(' · ');
  }
  function woText(e){
    const sit = (e.wo && e.wo.sitzungen) || [];
    return (e.wo && e.wo.projekt ? e.wo.projekt + ' · ' : '') + (sit.length ? (sit.length === 1 ? 'Sitzung ' + sit[0] : sit.length + ' Sitzungen') : 'überall');
  }
  function dauerText(e){
    const dd = e.dauer || {};
    if(dd.art === 'sitzung') return 'diese Sitzung (höchstens 24 Stunden)';
    const teile = ['befristet'];
    if(dd.bis) teile.push('bis ' + zeit(dd.bis));
    if(dd.max_aufrufe != null) teile.push('noch ' + Math.max(0, dd.max_aufrufe - (e.aufrufe || 0)) + ' von ' + dd.max_aufrufe + ' Aufrufen');
    return teile.join(' · ');
  }
  function herkunftText(e){
    const h = e.herkunft || {};
    return (HERKUNFT[h.von] || h.von || '?') + (h.karte_id ? ' · Karte ' + h.karte_id : '') + (h.vorlage ? ' · Vorlage ' + h.vorlage : '');
  }

  // Die Anfrage zum Zurücknehmen je Art (die bestehenden Wege).
  function zuruecknehmen(S, e){
    if(e.art === 'sitzung') return S.api('/api/harness/sitzungen/' + e.wo.sitzungen[0], {method: 'PATCH', body: {erlaubnis_zuruecknehmen: e.herkunft.karte_id}});
    return S.api('/api/harness/aufgaben/' + e.id + '/zuruecknehmen', {method: 'POST', body: {grund: 'zurückgenommen unter „Gilt gerade“'}});
  }

  function zeileFuer(S, e, neu){
    const z = d().el('div', 'hs-einst-zeile hs-erlaubnis');
    z.dataset.id = e.id; if(e.herkunft && e.herkunft.karte_id) z.dataset.karte = e.herkunft.karte_id;
    const spalten = [['Was', wasText(e)], ['Wo', woText(e)], ['Wie lange', dauerText(e)], ['Warum', e.warum || '–'], ['Herkunft', herkunftText(e)]];
    spalten.forEach(([name, text])=>{
      const s = d().el('span', 'hs-erlaubnis-spalte'); s.dataset.spalte = name;
      s.append(d().el('small', 'hs-leise', name), d().el(name === 'Was' ? 'code' : 'span', 'hs-einst-wert', text));
      z.append(s);
    });
    const weg = d().el('button', 'hs-knopf', 'Zurücknehmen'); weg.type = 'button';
    weg.onclick = async ()=>{
      weg.disabled = true;
      try{ await zuruecknehmen(S, e); neu(); }
      catch(err){ weg.disabled = false; S.hinweis('Nicht zurückgenommen: ' + err.message, 'bad'); }
    };
    z.append(weg);
    return z;
  }

  function flaeche(S, box){
    const sec = d().el('section', 'hs-einst-gruppe hs-erlaubnisse'); sec.append(d().el('div', 'hs-ueber', 'Gilt gerade'));
    const satz = d().el('div', 'hs-app-satz', 'Alle Erlaubnisse, die jetzt Karten ersparen: „Diese Sitzung“ und „Befristet“. Feste Vorbehalte, Warnkarten und Verbote gelten trotzdem. „Immer“ steht als Regel im Katalog darüber.');
    const liste = d().el('div', 'hs-liste'); liste.setAttribute('aria-live', 'polite');
    sec.append(satz, liste); box.append(sec);
    let tot = false;
    async function laden(){
      if(tot) return;
      let antwort;
      try{ antwort = await S.api('/api/harness/erlaubnisse?status=aktiv'); }
      catch(err){ if(!tot) liste.replaceChildren(d().el('div', 'hs-leise', 'Erlaubnisse nicht lesbar: ' + err.message)); return; }
      if(tot) return;
      const zeilen = ((antwort && antwort.erlaubnisse) || []).filter(e=>e.art !== 'katalog').map(e=>zeileFuer(S, e, laden));
      liste.replaceChildren(...(zeilen.length ? zeilen : [d().el('div', 'hs-leise', 'Keine Erlaubnis offen.')]));
    }
    laden();
    return {abbauen(){ tot = true; }, laden};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.erlaubnisse = {flaeche, zeileFuer, wasText, dauerText, herkunftText, woText};
})();
