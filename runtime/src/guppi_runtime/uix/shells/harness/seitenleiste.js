// Harness-Shell – Werkzeuge der Seitenleiste (Captain 03.11.2026): Suchen, Sortieren, „Ältere einklappen ab“ und das Aufräumen vieler Sitzungen auf einmal
// (Auswählen, Schnellauswahl, Löschen). Gelöscht wird nie wirklich: der Server verschiebt die Dateien nach geloescht/ (POST /api/harness/aufraeumen, nur der Captain).
// Einstellungen (Sortierung, Älter-ab) stehen nur im Browser (localStorage); Filter und Auswahl nur im Speicher der Seite. Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const KEY = 'sedra.harness.seitenleiste';
  const SORTEN = [['neu', 'Neueste zuerst'], ['alt', 'Älteste zuerst'], ['titel', 'Titel A–Z']];
  const TAGE = [[3, '3 Tage'], [7, '7 Tage'], [14, '14 Tage'], [30, '30 Tage'], [0, 'nie']];
  const SCHNELL = [['dubletten', 'Gleiche Titel (die neueste bleibt)'], ['alt', 'Älter als die Einklapp-Grenze'], ['leer', 'Fast leer (höchstens 2 Nachrichten)'], ['alle', 'Alle sichtbaren']];

  function einst(){
    try{ return Object.assign({sort: 'neu', alt: 7}, JSON.parse(localStorage.getItem(KEY) || '{}')); }catch(_e){ return {sort: 'neu', alt: 7}; }
  }
  function speichern(o){ try{ localStorage.setItem(KEY, JSON.stringify(o)); }catch(_e){} }
  function altTage(){ const t = Number(einst().alt); return Number.isFinite(t) ? t : 7; }                   // 0 = nie einklappen
  function auswahl(S){ return S._auswahl || (S._auswahl = {an: false, ids: new Set()}); }
  function filterText(S){ return String(S._filter || '').trim().toLowerCase(); }
  const titelVon = s=>String(s.titel || 'Ohne Titel');

  // die Sitzungen eines Blocks: gefiltert und sortiert (der Server liefert neueste zuerst)
  function ordnen(S, liste){
    const f = filterText(S);
    let out = f ? liste.filter(s=>titelVon(s).toLowerCase().includes(f)) : liste.slice();
    const art = einst().sort;
    if(art === 'alt') out = out.slice().sort((a, b)=>String(a.zuletzt || '').localeCompare(String(b.zuletzt || '')));
    else if(art === 'titel') out = out.slice().sort((a, b)=>titelVon(a).localeCompare(titelVon(b), 'de'));
    return out;
  }

  function normal(s){ return titelVon(s).toLowerCase().replace(/\s+/g, ' ').trim(); }
  function geschuetzt(S, s){                                         // nie per Schnellauswahl: laufende, aktive und Vorarbeiter-Sitzungen
    const a = S.aktive && S.aktive();
    const v = S.vorarbeiter && S.vorarbeiter[s.projekt];
    return !!s.laeuft || (a && a.id === s.id) || (v && v.sitzung_id === s.id);
  }
  function sichtbare(S){ return ordnen(S, S.sitzungen || []); }

  // Schnellauswahl: liefert die IDs, die sie wählt
  function kandidaten(S, art){
    const alle = sichtbare(S).filter(s=>!geschuetzt(S, s));
    if(art === 'alle') return alle.map(s=>s.id);
    if(art === 'leer') return alle.filter(s=>(s.nachrichten || 0) <= 2).map(s=>s.id);
    if(art === 'alt'){
      const tage = altTage(); if(!tage) return [];
      return alle.filter(s=>{ const t = Date.parse(s.zuletzt || ''); return t > 0 && Date.now() - t > tage * 86400000; }).map(s=>s.id);
    }
    const gruppen = new Map();                                       // dubletten: je Projekt und Titel bleibt die neueste Sitzung
    (S.sitzungen || []).forEach(s=>{ const k = (s.projekt || '') + '|' + normal(s); (gruppen.get(k) || gruppen.set(k, []).get(k)).push(s); });
    const weg = [];
    gruppen.forEach(g=>{ if(g.length > 1){ g.slice().sort((a, b)=>String(b.zuletzt || '').localeCompare(String(a.zuletzt || ''))).slice(1).forEach(s=>weg.push(s)); } });
    return weg.filter(s=>!geschuetzt(S, s)).map(s=>s.id);
  }

  // Auswahl-Haken vor einer Zeile (nur im Auswahl-Modus)
  function haken(S, s, neuZeichnen){
    const a = auswahl(S);
    if(!a.an) return null;
    const cb = d().el('input', 'hs-sz-haken'); cb.type = 'checkbox'; cb.checked = a.ids.has(s.id);
    cb.setAttribute('aria-label', '„' + titelVon(s) + '“ auswählen');
    cb.onclick = e=>e.stopPropagation();
    cb.onchange = ()=>{ cb.checked ? a.ids.add(s.id) : a.ids.delete(s.id); neuZeichnen(); };
    return cb;
  }

  async function loeschen(S, neuZeichnen){
    const a = auswahl(S), ids = [...a.ids];
    if(!ids.length) return;
    try{
      const out = await S.api('/api/harness/aufraeumen', {method: 'POST', body: {ids}});
      (out.verschoben || []).forEach(id=>root.sedraHarness.reiter.schliessen(S, id));
      const ue = (out.uebersprungen || []).length;
      S.hinweis((out.verschoben || []).length + ' Sitzungen nach geloescht/ verschoben' + (ue ? ', ' + ue + ' übersprungen (' + out.uebersprungen.map(x=>/antwort_laeuft/.test(x.grund) ? 'Antwort läuft' : x.grund).filter((v, i, l)=>l.indexOf(v) === i).join(', ') + ')' : '.'), ue ? 'warn' : 'note');
    }catch(err){ S.hinweis('Aufräumen fehlgeschlagen: ' + err.message, 'bad'); }
    a.ids.clear(); a.an = false;
    await S.sitzungenLaden();
    neuZeichnen();
  }

  // die Werkzeugzeile unter „Projekte“: Suchfeld, Auswählen, ⋯ (Sortierung, Einklappen) und im Auswahl-Modus die Leiste mit der Schnellauswahl
  function werkzeugzeile(S, neuZeichnen){
    const box = d().el('div', 'hs-sl-werkzeuge');
    const zeile = d().el('div', 'hs-sl-zeile');
    if(!S._filterFeld){
      const f = d().el('input', 'hs-sz-filter'); f.type = 'search'; f.placeholder = 'Sitzungen suchen …'; f.setAttribute('aria-label', 'Sitzungen suchen');
      f.oninput = ()=>{ S._filter = f.value; neuZeichnen(); f.focus(); try{ f.setSelectionRange(f.value.length, f.value.length); }catch(_e){} };
      f.onblur = ()=>{ if(S._seiteAufgeschoben) neuZeichnen(); };
      S._filterFeld = f;
    }
    S._filterFeld.value = S._filter || '';
    const a = auswahl(S);
    const waehlen = d().el('button', 'hs-sz-knopf' + (a.an ? ' an' : ''), '☑'); waehlen.type = 'button';
    waehlen.title = a.an ? 'Auswählen beenden' : 'Mehrere Sitzungen auswählen (zum Aufräumen)'; waehlen.setAttribute('aria-pressed', a.an ? 'true' : 'false'); waehlen.setAttribute('aria-label', waehlen.title);
    waehlen.onclick = ()=>{ a.an = !a.an; a.ids.clear(); neuZeichnen(); };
    const mehr = d().el('button', 'hs-sz-knopf' + (S._slMenue ? ' an' : ''), '⋯'); mehr.type = 'button';
    mehr.title = 'Sortierung und Einklappen'; mehr.setAttribute('aria-label', 'Optionen der Seitenleiste'); mehr.setAttribute('aria-expanded', S._slMenue ? 'true' : 'false');
    mehr.onclick = ()=>{ S._slMenue = !S._slMenue; neuZeichnen(); };
    zeile.append(S._filterFeld, waehlen, mehr);
    box.append(zeile);
    if(S._slMenue){
      const m = d().el('div', 'hs-sl-menue');
      const wahl = (titel, werte, aktuell, setzen)=>{
        const z = d().el('label', 'hs-sl-opt'); const sel = d().el('select', 'hs-projektwahl'); sel.setAttribute('aria-label', titel);
        werte.forEach(([w, n])=>{ const o = document.createElement('option'); o.value = String(w); o.textContent = n; o.selected = String(w) === String(aktuell); sel.append(o); });
        sel.onchange = ()=>{ setzen(sel.value); neuZeichnen(); };
        z.append(d().el('span', 'hs-leise', titel), sel); return z;
      };
      const e = einst();
      m.append(wahl('Sortierung', SORTEN, e.sort, v=>speichern(Object.assign(einst(), {sort: v}))),
               wahl('Ältere einklappen ab', TAGE, e.alt, v=>speichern(Object.assign(einst(), {alt: Number(v)}))));
      box.append(m);
    }
    if(a.an){
      const leiste = d().el('div', 'hs-sl-auswahl');
      leiste.append(d().el('b', null, a.ids.size + ' gewählt'));
      const schnell = d().el('select', 'hs-projektwahl'); schnell.setAttribute('aria-label', 'Schnellauswahl');
      const o0 = document.createElement('option'); o0.value = ''; o0.textContent = 'Schnellauswahl …'; schnell.append(o0);
      SCHNELL.forEach(([w, n])=>{ const o = document.createElement('option'); o.value = w; o.textContent = n + ' (' + kandidaten(S, w).length + ')'; schnell.append(o); });
      schnell.onchange = ()=>{ if(schnell.value) kandidaten(S, schnell.value).forEach(id=>a.ids.add(id)); neuZeichnen(); };
      const keine = d().el('button', 'hs-knopf hs-klein', 'Keine'); keine.type = 'button'; keine.onclick = ()=>{ a.ids.clear(); neuZeichnen(); };
      const weg = d().el('button', 'hs-knopf hs-klein warn', 'Löschen (' + a.ids.size + ')'); weg.type = 'button'; weg.disabled = !a.ids.size;
      weg.title = 'Verschiebt die gewählten Sitzungen nach geloescht/ – nichts wird wirklich gelöscht';
      weg.onclick = ()=>{
        if(!weg.dataset.sicher){                                     // zweiter Klick statt confirm(): ein Browser-Dialog antwortet in eingebetteten Fenstern still mit Nein
          weg.dataset.sicher = '1'; weg.textContent = 'Sicher? ' + a.ids.size + ' verschieben';
          setTimeout(()=>{ if(weg.isConnected){ delete weg.dataset.sicher; weg.textContent = 'Löschen (' + a.ids.size + ')'; } }, 5000);
          return;
        }
        loeschen(S, ()=>neuZeichnen());
      };
      const fertig = d().el('button', 'hs-knopf hs-klein', 'Fertig'); fertig.type = 'button'; fertig.onclick = ()=>{ a.an = false; a.ids.clear(); neuZeichnen(); };
      leiste.append(schnell, d().el('div', 'hs-sl-knoepfe'));
      leiste.lastChild.append(keine, weg, fertig);
      box.append(leiste);
    }
    if(filterText(S)) box.append(d().el('small', 'hs-leise', sichtbare(S).length + ' von ' + (S.sitzungen || []).length + ' Sitzungen'));
    return box;
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.seitenleiste = {werkzeugzeile, ordnen, haken, altTage, filterText, auswahl, kandidaten};
})();
