// Harness-Shell – die Seitenleiste (HS-02): oben „Neue Sitzung“, Projekte mit ihren Sitzungen (aufklappbar), Chats (Sitzungen ohne
// bekanntes Projekt), unten Einstellungen. Strg+B blendet sie ein und aus (shell.js). Löschen fragt im Feld nach (HS-18) und
// verschiebt die Sitzung nur nach geloescht/ – der Server löscht nie.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const ZU_KEY = 'sedra.harness.projekte.zu';

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

  function merken(set){
    try{ localStorage.setItem(ZU_KEY, JSON.stringify([...set])); }catch(_e){}
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
      if(!eigene.length) inhalt.append(d().el('small', 'hs-leise', 'Noch keine Sitzung'));
      eigene.forEach(s=>inhalt.append(zeile(S, s)));
      const offen = !zu.has(p.id);
      const g = gruppe(p.name, inhalt, offen, ()=>{ offen ? zu.add(p.id) : zu.delete(p.id); merken(zu); zeichnen(S); });
      g.title = p.wurzel || '';
      projekteBox.append(g);
    });
    liste.append(d().el('div', 'hs-ueber', 'Projekte'), projekteBox);
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
