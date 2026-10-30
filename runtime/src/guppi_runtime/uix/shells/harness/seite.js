// Harness-Shell – die Seitenleiste (HS-02): oben „Neue Sitzung“, Projekte mit ihren Sitzungen (aufklappbar), Chats (Sitzungen ohne
// bekanntes Projekt), unten Einstellungen. Strg+B blendet sie ein und aus (shell.js). Löschen fragt im Feld nach (HS-18) und
// verschiebt die Sitzung nur nach geloescht/ – der Server löscht nie.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const ZU_KEY = 'sedra.harness.projekte.zu';
  const ALT_KEY = 'sedra.harness.projekte.alt';            // Projekte, deren Block „Ältere Sitzungen“ offen ist (nur IDs)
  const ALT_TAGE = 7;
  const HILFE = [
    ['Was ist ein Projekt?', 'Ein Arbeitsordner mit eigenen Sitzungen, Freigaben und einem Vorarbeiter. SEDRA arbeitet nur in dessen Ordner.'],
    ['Sitzung anlegen', '„+ Neue Sitzung“ oben oder „Neue Sitzung starten“ unter einem Projekt; die Projektwahl steht unter dem Eingabefeld.'],
    ['Flagge ⚑', 'Der Vorarbeiter des Projekts: Er entscheidet Karten der Stufe „vorarbeiter“ und schlägt Aufgaben vor. Ernennen nur du (⚐ neben der Sitzung).'],
    ['Aufgaben', 'Unten „⛨ Aufgaben“: freigegebene Arbeitspakete mit Zweck, Frist und Zähler; dort nimmst du sie zurück.']];

  function zeit(iso){
    if(!iso) return '';
    const t = new Date(iso);
    if(isNaN(t.getTime())) return '';
    const heute = new Date();
    return t.toDateString() === heute.toDateString() ? t.toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'})
                                                      : t.toLocaleDateString('de-DE', {day: '2-digit', month: '2-digit'});
  }

  function zugeklappt(){
    try{ return new Set(JSON.parse(localStorage.getItem(ZU_KEY) || '[]')); }catch(_e){ return new Set(); }
  }

  function merken(set, key){
    try{ localStorage.setItem(key || ZU_KEY, JSON.stringify([...set])); }catch(_e){}
  }

  function altOffen(){
    try{ return new Set(JSON.parse(localStorage.getItem(ALT_KEY) || '[]')); }catch(_e){ return new Set(); }
  }

  function istAlt(S, s){                      // älter als 7 Tage; die aktive Sitzung und Vorarbeiter-Sitzungen bleiben immer oben
    const t = new Date(s.zuletzt || s.angelegt || 0).getTime();
    const aktiv = S.aktive() && S.aktive().id === s.id;
    return !aktiv && s.vorlage !== 'vorarbeiter' && !s.laeuft && t > 0 && Date.now() - t > ALT_TAGE * 86400000;
  }

  function hilfe(S){
    const box = d().el('div', 'hs-projekte-hilfe'); box.setAttribute('role', 'dialog'); box.setAttribute('aria-label', 'Hilfe zu Projekten');
    HILFE.forEach(([k, v])=>{ const z = d().el('div', 'hs-hilfe-zeile'); z.append(d().el('b', null, k + ' '), d().el('span', 'hs-leise', v)); box.append(z); });
    const zu = d().button('Schließen', ()=>{ S._projekteHilfe = false; zeichnen(S); });
    box.append(zu);
    box.onkeydown = e=>{ if(e.key === 'Escape'){ e.stopPropagation(); S._projekteHilfe = false; zeichnen(S); } };
    setTimeout(()=>zu.focus(), 0);
    return box;
  }

  function projektInfo(S, p, eigene){
    const v = S.vorarbeiter && S.vorarbeiter[p.id];
    const vs = v && eigene.find(s=>s.id === v.sitzung_id);
    const offen = (S.aufgaben || []).filter(a=>a.projekt === p.id && a.status === 'aktiv').length;
    return (p.wurzel ? p.wurzel + ' · ' : '') + eigene.length + ' Sitzungen · Vorarbeiter: ' + (vs ? (vs.titel || 'Ohne Titel') : 'keiner') + ' · ' + offen + ' aktive Aufgaben';
  }

  function zeile(S, s){
    const row = d().el('div', 'hs-sz' + (S.aktive() && S.aktive().id === s.id ? ' on' : '') + (s.laeuft ? ' laeuft' : ''));
    row.dataset.sitzung = s.id;
    const istVorarbeiter = !!(S.vorarbeiter && S.vorarbeiter[s.projekt] && S.vorarbeiter[s.projekt].sitzung_id === s.id);
    const titel = d().el('span', 'hs-sz-titel', (istVorarbeiter ? '⚑ ' : '') + (s.titel || 'Ohne Titel'));
    titel.title = (s.titel || 'Ohne Titel') + (s.nachrichten ? ' · ' + s.nachrichten + ' Nachrichten' : '') + (s.vorlage ? ' · Vorlage ' + s.vorlage : '') + (istVorarbeiter ? ' · Vorarbeiter dieses Projekts' : '');
    const zeitEl = d().el('small', 'hs-sz-zeit', s.laeuft ? 'läuft' : zeit(s.zuletzt));
    const umbenennen = d().el('button', 'hs-sz-knopf', '✎'); umbenennen.type = 'button';
    umbenennen.title = 'Umbenennen'; umbenennen.setAttribute('aria-label', 'Sitzung umbenennen');
    const weg = d().el('button', 'hs-sz-knopf', '×'); weg.type = 'button';
    weg.title = 'Löschen (nach geloescht/ verschieben)'; weg.setAttribute('aria-label', 'Sitzung löschen');
    const haupt = d().clickable(d().el('div', 'hs-sz-haupt'), ()=>root.sedraHarness.reiter.oeffnen(S, s.id));
    haupt.append(titel, zeitEl);
    row.append(haupt);
    if(s.vorlage === 'vorarbeiter'){                    // nur der Captain ernennt (Stufe 3, HS-26)
      const ern = d().el('button', 'hs-sz-knopf' + (istVorarbeiter ? ' an' : ''), istVorarbeiter ? '⚑' : '⚐'); ern.type = 'button';
      ern.title = istVorarbeiter ? 'Vorarbeiter entziehen' : 'Zum Vorarbeiter dieses Projekts ernennen'; ern.setAttribute('aria-label', ern.title);
      ern.onclick = async e=>{
        e.stopPropagation();
        try{
          if(istVorarbeiter) await S.api('/api/harness/vorarbeiter?projekt=' + encodeURIComponent(s.projekt), {method: 'DELETE'});
          else await S.api('/api/harness/vorarbeiter', {method: 'POST', body: {projekt: s.projekt, sitzung_id: s.id}});
          await S.freigabenLaden();
        }catch(err){ S.hinweis('Vorarbeiter: ' + err.message, 'bad'); }
      };
      row.append(ern);
    }
    row.append(umbenennen, weg);
    umbenennen.onclick = e=>{ e.stopPropagation(); umbenennenIm(S, row, s); };
    weg.onclick = e=>{ e.stopPropagation(); loeschenIm(S, row, s); };
    return row;
  }

  function umbenennenIm(S, row, s){
    const feld = d().el('input', 'hs-sz-feld'); feld.value = s.titel || ''; feld.maxLength = 60;
    feld.setAttribute('aria-label', 'Neuer Titel');
    row.replaceChildren(feld); feld.focus(); feld.select();
    let fertig = false;
    const ende = async speichern=>{
      if(fertig) return; fertig = true;
      if(speichern && feld.value.trim() && feld.value.trim() !== s.titel){
        try{ await S.api('/api/harness/sitzungen/' + s.id, {method: 'PATCH', body: {titel: feld.value.trim()}}); }
        catch(err){ S.hinweis('Umbenennen fehlgeschlagen: ' + err.message, 'bad'); }
      }
      await S.sitzungenLaden();
    };
    feld.onkeydown = e=>{ if(e.key === 'Enter'){ e.preventDefault(); ende(true); } else if(e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); ende(false); } };
    feld.onblur = ()=>ende(true);
  }

  function loeschenIm(S, row, s){
    const frage = d().el('div', 'hs-sz-frage');
    frage.append(d().el('span', null, '„' + (s.titel || 'Ohne Titel') + '“ in den Ordner geloescht/ verschieben?'));
    const ja = d().button('Ja', async()=>{
      await S.api('/api/harness/sitzungen/' + s.id, {method: 'DELETE'});
      root.sedraHarness.reiter.schliessen(S, s.id);
      await S.sitzungenLaden();
    }, 'warn');
    const nein = d().button('Nein', ()=>zeichnen(S));
    frage.append(ja, nein);
    row.replaceChildren(frage);
    nein.focus();
  }

  function gruppe(titel, inhalt, offen, umschalten){
    const box = d().el('section', 'hs-gruppe' + (offen ? '' : ' zu'));
    const kopf = d().clickable(d().el('div', 'hs-gruppe-kopf'), umschalten || (()=>{}));
    kopf.setAttribute('aria-expanded', offen ? 'true' : 'false');
    kopf.append(d().el('span', 'hs-pfeil', offen ? '▾' : '▸'), d().el('b', null, titel));
    box.append(kopf);
    if(offen) box.append(inhalt);
    return box;
  }

  function zeichnen(S){
    const el = S.el.seite;
    const zu = zugeklappt();
    const neu = d().button('+ Neue Sitzung', ()=>root.sedraHarness.reiter.neu(S), 'p hs-neu');
    const liste = d().el('div', 'hs-seite-liste');
    const ids = new Set(S.projekte.map(p=>p.id));
    const projekteBox = d().el('div', 'hs-projekte');
    if(S.projektFehler) projekteBox.append(d().el('div', 's-note warn', 'Projekte: ' + S.projektFehler));
    S.projekte.forEach(p=>{
      const eigene = S.sitzungen.filter(s=>s.projekt === p.id);
      const inhalt = d().el('div', 'hs-sz-liste');
      if(!eigene.length){
        inhalt.append(d().el('small', 'hs-leise', 'Noch keine Sitzung. '), d().button('Neue Sitzung starten', ()=>root.sedraHarness.reiter.neu(S)));
      }
      const neuere = eigene.filter(s=>!istAlt(S, s)), aeltere = eigene.filter(s=>istAlt(S, s));
      neuere.forEach(s=>inhalt.append(zeile(S, s)));
      if(aeltere.length){                     // nur einklappen, nie löschen (HS-67)
        const det = d().el('details', 'hs-sz-alt'); det.open = altOffen().has(p.id);
        det.append(d().el('summary', 'hs-leise', 'Ältere Sitzungen (' + aeltere.length + ')'));
        aeltere.forEach(s=>det.append(zeile(S, s)));
        det.ontoggle = ()=>{ const o = altOffen(); det.open ? o.add(p.id) : o.delete(p.id); merken(o, ALT_KEY); };
        inhalt.append(det);
      }
      const offen = !zu.has(p.id);
      const g = gruppe(p.name, inhalt, offen, ()=>{ offen ? zu.add(p.id) : zu.delete(p.id); merken(zu); zeichnen(S); });
      g.title = projektInfo(S, p, eigene);
      projekteBox.append(g);
    });
    const kopf = d().el('div', 'hs-ueber hs-projekte-kopf');
    const fragezeichen = d().el('button', 'hs-sz-knopf', '?'); fragezeichen.type = 'button';
    fragezeichen.title = 'Was ist ein Projekt?'; fragezeichen.setAttribute('aria-label', 'Hilfe zu Projekten'); fragezeichen.setAttribute('aria-expanded', S._projekteHilfe ? 'true' : 'false');
    fragezeichen.onclick = ()=>{ S._projekteHilfe = !S._projekteHilfe; zeichnen(S); };
    kopf.append(d().el('span', null, 'Projekte'), fragezeichen);
    liste.append(kopf, d().el('small', 'hs-leise hs-projekte-satz', 'Ein Projekt ist ein Arbeitsordner mit eigenen Sitzungen, Freigaben und einem Vorarbeiter.'));
    if(S._projekteHilfe) liste.append(hilfe(S));
    liste.append(projekteBox);
    const chats = S.sitzungen.filter(s=>!ids.has(s.projekt));
    const chatBox = d().el('div', 'hs-sz-liste');
    if(!chats.length) chatBox.append(d().el('small', 'hs-leise', 'Keine Sitzung ohne Projekt'));
    chats.forEach(s=>chatBox.append(zeile(S, s)));
    liste.append(d().el('div', 'hs-ueber', 'Chats'), chatBox);
    const aufgaben = d().el('button', 's-btn hs-einstellungen', '⛨ Aufgaben'); aufgaben.type = 'button';
    aufgaben.title = 'Aufgaben-Freigaben und Vorschläge des Vorarbeiters'; aufgaben.onclick = ()=>root.sedraHarness.reiter.oeffnen(S, 'aufgaben:');
    const einst = d().el('button', 's-btn hs-einstellungen', 'Einstellungen');
    einst.type = 'button';
    einst.title = 'Einstellungen (HS-42): Allgemein, Agent, Sprache, Integrationen, Lokale Modelle, System'; einst.dataset.marke = 'hs-einstellungen';
    einst.onclick = ()=>root.sedraHarness.einstellungen.oeffnen(S);           // Stufe 5
    el.replaceChildren(neu, liste, aufgaben, einst);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.seite = {mount: S=>zeichnen(S), zeichnen, zeit};
})();
