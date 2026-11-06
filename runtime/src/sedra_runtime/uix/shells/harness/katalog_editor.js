// Harness-Shell Stufe 5 – der Katalog-Editor (SPEC_HARNESS_SHELL_v1 HS-42 „Änderungen nur durch den Captain“; G2 Stufe 5 §4; G3 N6).
//
// Liest `GET /api/harness/katalog` (Regeln, Quelle, Vorlage), zeigt eine Tabelle, in der jede Regel bearbeitet, hinzugefügt und entfernt
// werden kann (D-U3: alle Felder; Vorlage-Regeln mit `verboten` sind gesperrt). Die Befunde kommen live aus katalog_editor_pruefung.js
// (rein). Der Editor schreibt **nie** selbst: „Antrag stellen“ ruft `POST /api/harness/katalog/antrag` – ein Antrag mit Gate im
// Posteingang; erst „Freigeben und anwenden“ des Captains schreibt die Datei (harness/antraege.py). „Zurück zur Vorlage“ ist ebenso
// ein Antrag (`katalog/entfernen`). Offene Anträge stehen als Satz auf der Seite (§3.2).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const P = ()=>root.sedraKatalogPruefung;
  const HERKUNFT = {vorlage: 'Vorlage', datei: 'Datei', neu: 'neu'};

  function kopie(regeln){ return (regeln || []).map(r=>P().norm(r)); }
  function gleich(a, b){ return JSON.stringify(P().norm(a)) === JSON.stringify(P().norm(b)); }
  function zaehlen(regeln){
    const je = {frei: 0, vorarbeiter: 0, captain: 0, verboten: 0};
    (regeln || []).forEach(r=>{ if(je[r.stufe] !== undefined) je[r.stufe] += 1; });
    return Object.keys(je).map(k=>k + ' ' + je[k]).join(' · ');
  }

  // ---- die Fläche (einstellungen.js: Agent → Freigabe-Modus)
  function flaeche(S, box){
    const st = {stand: [], entwurf: [], vorlage: [], quelle: null, datei: null, fehler: null, offen: []};
    const kopf = d().el('div', 'hs-katalog-kopf');
    const antrag = d().el('div', 'hs-app-satz hs-einst-antrag'); antrag.hidden = true;
    const tabelle = d().el('div', 'hs-katalog'); tabelle.dataset.marke = 'hs-katalog';
    const befunde = d().el('div', 'hs-katalog-befunde'); befunde.setAttribute('aria-live', 'polite');
    const leiste = d().el('div', 'hs-katalog-leiste');
    const vorschau = d().el('details', 'hs-katalog-vorschau'); const vs = d().el('summary', null, 'YAML-Vorschau'); const pre = d().el('pre', 'hs-pre'); vorschau.append(vs, pre);
    box.append(kopf, antrag, tabelle, befunde, leiste, vorschau);

    const laden = async ()=>{
      try{
        const k = await S.api('/api/harness/katalog');
        st.stand = kopie(k.regeln); st.entwurf = kopie(k.regeln); st.vorlage = kopie(k.vorlage); st.quelle = k.quelle; st.datei = k.datei; st.fehler = k.fehler;
      }catch(err){ st.fehler = err.message; }
      try{ st.offen = ((await S.api('/api/decisions')).items || []).filter(x=>x.kind === 'request:harness_katalog'); }catch(_e){ st.offen = []; }
      alles();
    };

    const kopfZeichnen = ()=>{
      kopf.replaceChildren();
      const q = st.quelle === 'local_config' ? 'Datei des Captains' : (st.quelle === 'vorlage' ? 'Vorlage (config/freigabe_katalog.beispiel.yaml)' : 'unbekannt');
      kopf.append(d().el('b', null, 'Freigabe-Katalog · ' + q), d().el('small', 'hs-leise', st.datei ? ' · ' + st.datei : ''), d().el('div', 'hs-leise', st.stand.length + ' Regeln · ' + zaehlen(st.stand)));
      if(st.fehler) kopf.append(d().el('div', 'hs-app-satz warn', 'Der Katalog ist nicht lesbar: ' + st.fehler + ' – ohne gültigen Katalog läuft kein Werkzeug (D-F2).'));
      antrag.hidden = !st.offen.length;
      antrag.textContent = st.offen.length ? st.offen.length + (st.offen.length === 1 ? ' Antrag offen' : ' Anträge offen') + ' – geschrieben wird erst nach „Freigeben und anwenden“ im Posteingang (Freigaben).' : '';
    };

    const herkunft = r=>{
      const v = st.vorlage.find(x=>x.id === r.id);
      if(v && gleich(v, r)) return 'vorlage';
      return st.stand.some(x=>x.id === r.id) ? 'datei' : 'neu';
    };
    const gesperrt = r=>{ const v = st.vorlage.find(x=>x.id === r.id); return !!(v && v.stufe === 'verboten'); };

    const feld = (r, name, wert, setzen, mehrzeilig)=>{
      const f = d().el(mehrzeilig ? 'textarea' : 'input', 'hs-katalog-feld'); f.value = wert; f.setAttribute('aria-label', name + ' ' + (r.id || ''));
      if(mehrzeilig) f.rows = Math.max(1, String(wert).split('\n').length);
      f.disabled = gesperrt(r);
      f.oninput = ()=>{ setzen(f.value); pruefen(); };
      return f;
    };

    const zeileZeichnen = (r, i)=>{
      const z = d().el('div', 'hs-katalog-zeile' + (gesperrt(r) ? ' gesperrt' : '')); z.dataset.regel = r.id || ('neu-' + i); z.dataset.herkunft = herkunft(r);
      const idF = feld(r, 'ID', r.id, v=>{ r.id = v.trim(); });
      const wz = feld(r, 'Werkzeug', r.werkzeug.join(', '), v=>{ r.werkzeug = v.split(',').map(x=>x.trim()).filter(Boolean); });
      const mu = feld(r, 'Muster', r.muster.join('\n'), v=>{ r.muster = v.split('\n').map(x=>x.trim()).filter(Boolean); }, true);
      const stufe = d().el('select', 'hs-katalog-feld'); stufe.setAttribute('aria-label', 'Stufe ' + r.id);
      P().STUFEN.forEach(s=>{ const o = d().el('option', null, s); o.value = s; o.selected = s === r.stufe; stufe.append(o); });
      stufe.disabled = gesperrt(r); stufe.onchange = ()=>{ r.stufe = stufe.value; pruefen(); };
      const bg = feld(r, 'Begründung', r.begruendung, v=>{ r.begruendung = v; });
      const weg = d().el('button', 'hs-sz-knopf', '×'); weg.type = 'button'; weg.title = 'Regel entfernen'; weg.setAttribute('aria-label', 'Regel ' + r.id + ' entfernen'); weg.disabled = gesperrt(r);
      weg.onclick = ()=>{ st.entwurf.splice(st.entwurf.indexOf(r), 1); tabelleZeichnen(); pruefen(); };
      const h = d().el('small', 'hs-katalog-herkunft', HERKUNFT[herkunft(r)] + (gesperrt(r) ? ' · gesperrt' : ''));
      z.append(idF, wz, mu, stufe, bg, h, weg);
      return z;
    };

    const tabelleZeichnen = ()=>{
      tabelle.replaceChildren();
      const k = d().el('div', 'hs-katalog-zeile hs-katalog-titel');
      ['ID', 'Werkzeug', 'Muster (je Zeile eins)', 'Stufe', 'Begründung', 'Herkunft', ''].forEach(t=>k.append(d().el('span', null, t)));
      tabelle.append(k);
      st.entwurf.forEach((r, i)=>tabelle.append(zeileZeichnen(r, i)));
      if(!st.entwurf.length) tabelle.append(d().el('div', 'hs-app-satz', 'Keine Regel – ohne Regeln ist der Katalog ungültig.'));
    };

    const leisteZeichnen = (p)=>{
      leiste.replaceChildren();
      const neu = d().button('+ Regel', ()=>{ st.entwurf.push(P().norm({id: '', werkzeug: ['datei_lesen'], muster: [], stufe: 'captain', begruendung: ''})); tabelleZeichnen(); pruefen(); const f = tabelle.querySelector('.hs-katalog-zeile:last-child .hs-katalog-feld'); if(f) f.focus(); });
      const verwerfen = d().button('Verwerfen', ()=>{ st.entwurf = kopie(st.stand); tabelleZeichnen(); pruefen(); });
      const stellen = d().button('Antrag stellen', async ()=>{
        const out = await S.api('/api/harness/katalog/antrag', {method: 'POST', body: {regeln: st.entwurf.map(r=>P().norm(r))}});
        S.hinweis('Antrag gestellt (' + out.mission_id + ') – Freigabe im Posteingang.');
        await laden();
      }, 'p hs-katalog-antrag');
      stellen.disabled = !p.antragMoeglich;
      stellen.title = p.antragMoeglich ? 'legt einen Antrag mit Gate an – geschrieben wird erst nach deiner Freigabe' : (p.fehler.length ? 'erst die Fehler beheben' : (p.unveraendert ? 'nichts geändert' : 'gesperrte Regel verändert'));
      leiste.append(neu, verwerfen, stellen);
      if(st.quelle === 'local_config'){
        const zurueck = d().button('Zurück zur Vorlage', async ()=>{
          const out = await S.api('/api/harness/katalog/entfernen', {method: 'POST', body: {}});
          S.hinweis('Antrag gestellt (' + out.mission_id + ') – nach der Freigabe gilt die Vorlage; die Datei wird gesichert.');
          await laden();
        }, 'warn');
        zurueck.title = 'Antrag, die Datei des Captains zu entfernen (mit Sicherung) – danach gilt die Vorlage';
        leiste.append(zurueck);
      }
    };

    const pruefen = ()=>{
      const p = P().pruefen(st.stand, st.entwurf, st.vorlage);
      befunde.replaceChildren();
      const dd = p.diff;
      befunde.append(d().el('div', 'hs-leise', 'Änderungen: ' + dd.neu.length + ' neu · ' + dd.geaendert.length + ' geändert · ' + dd.entfernt.length + ' entfernt'));
      p.fehler.forEach(f=>befunde.append(d().el('div', 'hs-katalog-befund bad', f.satz)));
      p.befunde.forEach(b=>befunde.append(d().el('div', 'hs-katalog-befund ' + (b.art === 'gesperrt' ? 'bad' : 'rot'), b.satz)));
      tabelle.querySelectorAll('.hs-katalog-zeile').forEach(z=>z.classList.remove('rot', 'fehler'));
      p.fehler.concat(p.befunde).forEach(x=>{ const z = x.regel ? tabelle.querySelectorAll('.hs-katalog-zeile:not(.hs-katalog-titel)')[x.regel - 1] : null; if(z) z.classList.add(x.satz.indexOf('Lockerung') === 0 || x.satz.indexOf('weites') === 0 ? 'rot' : 'fehler'); });
      pre.textContent = P().alsYamlVorschau(st.entwurf);
      leisteZeichnen(p);
      return p;
    };

    const alles = ()=>{ kopfZeichnen(); tabelleZeichnen(); pruefen(); };
    const auf = e=>{ if(e && (e.kind === 'request:harness_katalog' || String(e.id || '').startsWith('request:'))) laden(); };
    const offs = [S.ctx.bus.on('decision.answered', auf), S.ctx.bus.on('decision.pending', auf), S.ctx.bus.on('harness.katalog', ()=>laden())];
    laden();
    return {abbauen(){ offs.forEach(off=>{ try{ off(); }catch(_e){} }); }, laden, stand: st};
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.katalogEditor = {flaeche, zaehlen};
})();
