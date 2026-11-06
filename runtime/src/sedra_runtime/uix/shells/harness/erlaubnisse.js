// Harness-Shell – Sitzungs-Erlaubnisse (Bau 1.11.2026, P0 M1): was der Captain auf Karten mit „Für diese Sitzung erlauben“ geöffnet hat,
// je Sitzung als Liste mit „Zurücknehmen“ (PATCH /api/harness/sitzungen/<id> {erlaubnis_zuruecknehmen}). Steht in den Einstellungen unter
// Agent → Freigabe-Modus unter dem Katalog-Editor. Daten werden nie zu HTML (sedraDom.el mit Text).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  function zeileFuer(S, sid, e, neu){
    const z = d().el('div', 'hs-einst-zeile hs-erlaubnis');
    z.dataset.karte = e.karte_id;
    z.append(d().el('span', 'hs-einst-label', e.werkzeug), d().el('code', 'hs-einst-wert', e.muster));
    if(e.regel) z.append(d().el('small', 'hs-leise', 'statt Regel „' + e.regel + '“ · Karte ' + e.karte_id));
    const weg = d().el('button', 'hs-knopf', 'Zurücknehmen'); weg.type = 'button';
    weg.onclick = async ()=>{
      weg.disabled = true;
      try{ await S.api('/api/harness/sitzungen/' + sid, {method: 'PATCH', body: {erlaubnis_zuruecknehmen: e.karte_id}}); neu(); }
      catch(err){ weg.disabled = false; S.hinweis('Nicht zurückgenommen: ' + err.message, 'bad'); }
    };
    z.append(weg);
    return z;
  }

  // Die Fläche: alle Sitzungen mit Erlaubnissen (die Liste kennt sie nicht – je Sitzung nachladen, nur die offenen Reiter und die 20 neuesten).
  function flaeche(S, box){
    const sec = d().el('section', 'hs-einst-gruppe hs-erlaubnisse'); sec.append(d().el('div', 'hs-ueber', 'Erlaubnisse dieser Sitzungen'));
    const satz = d().el('div', 'hs-app-satz', 'Was du auf einer Karte mit „Für diese Sitzung erlauben“ geöffnet hast – gilt, bis du es zurücknimmst oder die Sitzung schließt. Feste Vorbehalte und der Schreibbereich bleiben davon unberührt.');
    const liste = d().el('div', 'hs-liste'); liste.setAttribute('aria-live', 'polite');
    sec.append(satz, liste); box.append(sec);
    let tot = false;
    async function laden(){
      if(tot) return;
      const ids = (S.sitzungen || []).slice(0, 20).map(s=>s.id);
      const zeilen = [];
      for(const sid of ids){
        let s; try{ s = await S.api('/api/harness/sitzungen/' + sid); }catch(_e){ continue; }
        const liste_e = s.erlaubnisse || [];
        if(!liste_e.length) continue;
        const kopf = d().el('div', 'hs-ueber hs-erlaubnis-sitzung', (s.titel || 'Ohne Titel') + ' · ' + sid);
        zeilen.push(kopf, ...liste_e.map(e=>zeileFuer(S, sid, e, laden)));
      }
      if(tot) return;
      liste.replaceChildren(...(zeilen.length ? zeilen : [d().el('div', 'hs-leise', 'Keine Erlaubnis offen.')]));
    }
    laden();
    return {abbauen(){ tot = true; }, laden};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.erlaubnisse = {flaeche, zeileFuer};
})();
