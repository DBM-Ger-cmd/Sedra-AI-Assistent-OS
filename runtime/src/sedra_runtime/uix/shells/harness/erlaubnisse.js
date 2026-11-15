// Harness-Shell – „Gilt gerade“ (S4.1 UI, SPEC_FREIGABEN_S4_v1 FS-22 bis FS-24): eine Liste aller Erlaubnisse (diese Sitzung · befristet), gelesen aus
// GET /api/harness/erlaubnisse. Spalten: Was (Klartext, Muster dabei) · Wo · Wie lange / noch · Warum · Herkunft · Zurücknehmen. Die Katalogregeln mit
// Stufe „frei“ stehen im Katalog-Editor darüber, nicht doppelt. Zurücknehmen geht über die bestehenden Wege (Sitzung: PATCH, befristet: POST).
// Steht in den Einstellungen unter Agent → Freigabe-Modus. Daten werden nie zu HTML (sedraDom.el mit Text).
// Alle festen Beschriftungen laufen über t() (strings_de.js / strings_de2.js).
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const DE_ERLAUBNISSE = {erst_was:'Was',erst_wo:'Wo',erst_wie_lange:'Wie lange',erst_warum:'Warum',erst_herkunft:'Herkunft',erst_zuruecknehmen:'Zurücknehmen',erst_titel:'Gilt gerade',erst_satz:'Alle Erlaubnisse, die jetzt Karten ersparen: „Diese Sitzung“ und „Befristet“. Feste Vorbehalte, Warnkarten und Verbote gelten trotzdem. „Immer“ steht als Regel im Katalog darüber.',erst_keine:'Keine Erlaubnis offen.',dauer_sitzung:'diese Sitzung (höchstens 24 Stunden)',dauer_befristet:'befristet',dauer_bis:'bis ',dauer_noch:'noch {n} von {max} Aufrufen',wo_sitzung:'Sitzung ',wo_sitzungen:' Sitzungen',wo_ueberall:'überall',hk_captain:'Captain',hk_vorarbeiter:'Vorarbeiter',hk_vorlage:'Vorlage',hk_karte:' · Karte {id}',hk_vorlage_txt:' · Vorlage {id}'}; const T = (k, ...a) => (root.t ? root.t(k, ...a) : (DE_ERLAUBNISSE[k] || k));

  const zeit = iso=>{ const t = String(iso || ''); return t.length >= 16 ? t.slice(0, 10) + ' ' + t.slice(11, 16) : t; };

  function wasText(e){
    return (e.was || []).map(w=>(w.werkzeug || '?') + ' ' + (w.muster || '')).join(' · ');
  }
  function woText(e){
    const sit = (e.wo && e.wo.sitzungen) || [];
    return (e.wo && e.wo.projekt ? e.wo.projekt + ' · ' : '') + (sit.length ? (sit.length === 1 ? T('wo_sitzung') + sit[0] : sit.length + T('wo_sitzungen')) : T('wo_ueberall'));
  }
  function dauerText(e){
    const dd = e.dauer || {};
    if(dd.art === 'sitzung') return T('dauer_sitzung');
    const teile = [T('dauer_befristet')];
    if(dd.bis) teile.push(T('dauer_bis') + zeit(dd.bis));
    if(dd.max_aufrufe != null) teile.push(T('dauer_noch').replace('{n}', String(Math.max(0, dd.max_aufrufe - (e.aufrufe || 0)))).replace('{max}', String(dd.max_aufrufe)));
    return teile.join(' · ');
  }
  function herkunftText(e){
    const h = e.herkunft || {};
    return (T('hk_' + (h.von || '')) || h.von || '?') + (h.karte_id ? T('hk_karte').replace('{id}', h.karte_id) : '') + (h.vorlage ? T('hk_vorlage_txt').replace('{id}', h.vorlage) : '');
  }

  // Die Anfrage zum Zurücknehmen je Art (die bestehenden Wege).
  function zuruecknehmen(S, e){
    if(e.art === 'sitzung') return S.api('/api/harness/sitzungen/' + e.wo.sitzungen[0], {method: 'PATCH', body: {erlaubnis_zuruecknehmen: e.herkunft.karte_id}});
    return S.api('/api/harness/aufgaben/' + e.id + '/zuruecknehmen', {method: 'POST', body: {grund: 'zurückgenommen unter „Gilt gerade“'}});
  }

  function zeileFuer(S, e, neu){
    const z = d().el('div', 'hs-einst-zeile hs-erlaubnis');
    z.dataset.id = e.id; if(e.herkunft && e.herkunft.karte_id) z.dataset.karte = e.herkunft.karte_id;
    const spalten = [[T('erst_was'), wasText(e)], [T('erst_wo'), woText(e)], [T('erst_wie_lange'), dauerText(e)], [T('erst_warum'), e.warum || '–'], [T('erst_herkunft'), herkunftText(e)]];
    spalten.forEach(([name, text])=>{
      const s = d().el('span', 'hs-erlaubnis-spalte'); s.dataset.spalte = name;
      s.append(d().el('small', 'hs-leise', name), d().el(name === 'Was' ? 'code' : 'span', 'hs-einst-wert', text));
      z.append(s);
    });
    const weg = d().el('button', 'hs-knopf', T('erst_zuruecknehmen')); weg.type = 'button';
    weg.onclick = async ()=>{
      weg.disabled = true;
      try{ await zuruecknehmen(S, e); neu(); }
      catch(err){ weg.disabled = false; S.hinweis('Nicht zurückgenommen: ' + err.message, 'bad'); }
    };
    z.append(weg);
    return z;
  }

  function flaeche(S, box){
    const sec = d().el('section', 'hs-einst-gruppe hs-erlaubnisse'); sec.append(d().el('div', 'hs-ueber', T('erst_titel')));
    const satz = d().el('div', 'hs-app-satz', T('erst_satz'));
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
      liste.replaceChildren(...(zeilen.length ? zeilen : [d().el('div', 'hs-leise', T('erst_keine'))]));
    }
    laden();
    return {abbauen(){ tot = true; }, laden};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.erlaubnisse = {flaeche, zeileFuer, wasText, dauerText, herkunftText, woText};
})();
