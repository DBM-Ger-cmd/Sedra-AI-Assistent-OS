// Harness-Shell – die Seitenleiste (HS-02): oben „Neue Sitzung“, Projekte mit ihren Sitzungen (aufklappbar), Chats (Sitzungen ohne
// bekanntes Projekt), unten Einstellungen. Strg+B blendet sie ein und aus (shell.js). Löschen fragt im Feld nach (HS-18) und
// verschiebt die Sitzung nur nach geloescht/ – der Server löscht nie.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const ZU_KEY = 'sedra.harness.projekte.zu';
  const ALT_KEY = 'sedra.harness.projekte.alt';            // Projekte, deren Block „Ältere Sitzungen“ offen ist (nur IDs)
  const HILFE = [
    ['Was ist ein Projekt?', 'Ein Arbeitsordner mit eigenen Sitzungen, Freigaben und einem Vorarbeiter. SEDRA arbeitet nur in dessen Ordner.'],
    ['Sitzung anlegen', '„+ Neue Sitzung“ oben oder „Neue Sitzung starten“ unter einem Projekt; die Projektwahl steht unter dem Eingabefeld.'],
    ['Flagge ⚑', 'Der Vorarbeiter des Projekts: Er entscheidet Karten der Stufe „vorarbeiter“ und schlägt Aufgaben vor. Ernennen nur du (⚐ neben der Sitzung).'],
    ['Aufgaben', 'Unten „⛨ Freigaben“: was wartet, was gerade gilt (Aufgaben mit Zweck, Frist und Zähler, Erlaubnisse) und die Regeln des Katalogs; dort nimmst du auch zurück.']];

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
    const sl = root.sedraHarness.seitenleiste, tage = sl.altTage();                           // wählbar (⋯): 3, 7, 14, 30 Tage oder nie; mit einem Suchtext bleibt alles sichtbar
    return !aktiv && s.vorlage !== 'vorarbeiter' && !s.laeuft && t > 0 && tage > 0 && !sl.filterText(S) && Date.now() - t > tage * 86400000;
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
    const exp = d().el('button', 'hs-sz-knopf', '↓'); exp.type = 'button';                  // V6 (1.11.): als Markdown speichern
    exp.title = 'Als Markdown speichern (/export)'; exp.setAttribute('aria-label', 'Sitzung als Markdown speichern');
    exp.onclick = e=>{ e.stopPropagation(); exportieren(S, s.id); };
    const haupt = d().clickable(d().el('div', 'hs-sz-haupt'), ()=>root.sedraHarness.reiter.oeffnen(S, s.id));
    haupt.append(titel, zeitEl);
    const hk = root.sedraHarness.seitenleiste.haken(S, s, ()=>zeichnen(S, true));            // Auswahl-Modus: ein Haken vor der Zeile
    if(hk) row.append(hk);
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
    row.append(exp, umbenennen, weg);
    umbenennen.onclick = e=>{ e.stopPropagation(); umbenennenIm(S, row, s); };
    weg.onclick = e=>{ e.stopPropagation(); loeschenIm(S, row, s); };
    return row;
  }

  // V6: GET …/export → Datei im Browser speichern (Blob, kein Server-Schreiben)
  async function exportieren(S, sid){
    try{
      const out = await S.api('/api/harness/sitzungen/' + sid + '/export');
      const blob = new Blob([out.markdown || ''], {type: 'text/markdown;charset=utf-8'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = out.dateiname || (sid + '.md'); document.body.append(a); a.click(); a.remove();
      setTimeout(()=>URL.revokeObjectURL(url), 1000);
      S.hinweis('Gespeichert: ' + (out.dateiname || sid + '.md'), 'note');
    }catch(err){ S.hinweis('Export fehlgeschlagen: ' + err.message, 'bad'); }
  }

  function umbenennenIm(S, row, s){
    const feld = d().el('input', 'hs-sz-feld'); feld.value = s.titel || ''; feld.maxLength = 60;
    feld.setAttribute('aria-label', 'Neuer Titel');
    row.replaceChildren(feld); feld.focus(); feld.select();
    let fertig = false;
    const ende = async speichern=>{
      if(fertig) return; fertig = true;
      feld.dataset.fertig = '1';                                   // A9: ab jetzt darf die Leiste wieder neu gezeichnet werden
      if(speichern && feld.value.trim() && feld.value.trim() !== s.titel){
        try{ await S.api('/api/harness/sitzungen/' + s.id, {method: 'PATCH', body: {titel: feld.value.trim()}}); }
        catch(err){ S.hinweis('Umbenennen fehlgeschlagen: ' + err.message, 'bad'); }
      }
      await S.sitzungenLaden();
      if(S._seiteAufgeschoben) zeichnen(S);
    };
    feld.onkeydown = e=>{ if(e.key === 'Enter'){ e.preventDefault(); ende(true); } else if(e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); ende(false); } };
    feld.onblur = ()=>ende(true);
  }

  function loeschenIm(S, row, s){
    const frage = d().el('div', 'hs-sz-frage');
    frage.append(d().el('span', null, '„' + (s.titel || 'Ohne Titel') + '“ in den Ordner geloescht/ verschieben?'));
    const ja = d().button('Ja', async()=>{
      frage.dataset.fertig = '1';
      try{
        await S.api('/api/harness/sitzungen/' + s.id, {method: 'DELETE'});
        root.sedraHarness.reiter.schliessen(S, s.id);
      }catch(err){                                                 // A5: eine Antwort läuft oder die Sitzung ist weg – sagen, nicht hängen
        S.hinweis(/antwort_laeuft/.test(err.message) ? 'Nicht verschoben: in dieser Sitzung läuft noch eine Antwort – erst stoppen.' : 'Nicht verschoben: ' + err.message, 'warn');
      }
      await S.sitzungenLaden();
      zeichnen(S);
    }, 'warn');
    const nein = d().button('Nein', ()=>{ frage.dataset.fertig = '1'; zeichnen(S); });
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

  // Direkt in der Seitenleiste freigeben, was nur Daten der Harness anlegt und keine Regel lockert: ein Projekt, eine neue Vorlage (ohne Rechte), der gesehene Code-Stand.
  // Regeln (Katalog) und alles andere erst im Posteingang mit allen Angaben. Gleiche Leiter wie dort: Freigeben (zweiter Klick bestätigt) · Ablehnen · Ansehen.
  const FREIGABE_DIREKT = ['request:harness_projekt', 'request:harness_vorlage', 'request:harness_code_stand'];
  const SICHER_MS = 10000;                  // so lange gilt der zweite Klick (5 s waren zu knapp: die Rückfrage fiel zurück, bevor man sie las)

  function zeichnen(S, erzwingen){
    const el = S.el.seite;
    // A9 (1.11.): ein offenes Umbenennen-Feld oder eine Lösch-Rückfrage überlebt Ereignisse – der Neuaufbau wartet, bis sie fertig sind; ebenso das Suchfeld, solange man darin tippt
    if(!erzwingen && el.querySelector('.hs-sz-feld:not([data-fertig]), .hs-sz-frage:not([data-fertig]), .hs-sz-filter:focus')){ S._seiteAufgeschoben = true; return; }
    S._seiteAufgeschoben = false;
    const zu = zugeklappt();
    const neu = d().button('+ Neue Sitzung', ()=>root.sedraHarness.reiter.neu(S), 'p hs-neu');
    const liste = d().el('div', 'hs-seite-liste');
    const ids = new Set(S.projekte.map(p=>p.id));
    const projekteBox = d().el('div', 'hs-projekte');
    if(S.projektFehler) projekteBox.append(d().el('div', 's-note warn', 'Projekte: ' + S.projektFehler));
    S.projekte.forEach(p=>{
      const alle = S.sitzungen.filter(s=>s.projekt === p.id);
      const eigene = root.sedraHarness.seitenleiste.ordnen(S, alle);                        // gefiltert und sortiert (⋯)
      const inhalt = d().el('div', 'hs-sz-liste');
      if(!alle.length){
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
      g.title = projektInfo(S, p, alle);
      projekteBox.append(g);
    });
    const kopf = d().el('div', 'hs-ueber hs-projekte-kopf');
    const fragezeichen = d().el('button', 'hs-sz-knopf', '?'); fragezeichen.type = 'button';
    fragezeichen.title = 'Was ist ein Projekt?'; fragezeichen.setAttribute('aria-label', 'Hilfe zu Projekten'); fragezeichen.setAttribute('aria-expanded', S._projekteHilfe ? 'true' : 'false');
    fragezeichen.onclick = ()=>{ S._projekteHilfe = !S._projekteHilfe; zeichnen(S); };
    kopf.append(d().el('span', null, 'Projekte'), fragezeichen);
    liste.append(kopf, d().el('small', 'hs-leise hs-projekte-satz', 'Ein Projekt ist ein Arbeitsordner mit eigenen Sitzungen, Freigaben und einem Vorarbeiter.'));
    if(S._projekteHilfe) liste.append(hilfe(S));
    liste.append(root.sedraHarness.seitenleiste.werkzeugzeile(S, ()=>zeichnen(S, true)), projekteBox);
    const chats = root.sedraHarness.seitenleiste.ordnen(S, S.sitzungen.filter(s=>!ids.has(s.projekt)));
    const chatBox = d().el('div', 'hs-sz-liste');
    if(!chats.length) chatBox.append(d().el('small', 'hs-leise', 'Keine Sitzung ohne Projekt'));
    chats.forEach(s=>chatBox.append(zeile(S, s)));
    liste.append(d().el('div', 'hs-ueber', 'Chats'), chatBox);
    // Verknüpfungen: eigene Knöpfe, die der Captain im Chat verlangt hat (Werkzeug verknuepfung_anlegen); das Kreuz nimmt sie weg
    const verkn = d().el('div', 'hs-verkn');
    (S.verknuepfungen || []).forEach(v=>{
      const zeile = d().el('div', 'hs-verkn-zeile');
      const knopf = d().el('button', 's-btn hs-einstellungen', v.name); knopf.type = 'button';
      knopf.title = 'Öffnet ' + v.name;
      knopf.onclick = ()=>{
        const ort = (root.sedraPlaces && root.sedraPlaces.PLACES || []).find(p=>p.id === v.ort);
        if(ort) root.sedraHarness.app.oeffnen(S, ort); else S.hinweis('Das Fenster „' + v.name + '“ gibt es in dieser Oberfläche nicht.', 'note');
      };
      const weg = d().el('button', 'hs-sz-knopf', '×'); weg.type = 'button'; weg.title = 'Verknüpfung entfernen'; weg.setAttribute('aria-label', 'Verknüpfung ' + v.name + ' entfernen');
      weg.onclick = async()=>{
        try{ await S.api('/api/harness/verknuepfungen?id=' + encodeURIComponent(v.id), {method: 'DELETE'}); }catch(err){ S.hinweis('Die Verknüpfung blieb: ' + (err && err.message || err), 'warn'); }
        S.freigabenLaden();
      };
      zeile.append(knopf, weg); verkn.append(zeile);
    });
    // Posteingang: alle Anträge, die auf den Captain warten (Ordner als Projekt, Katalog, Schalter …). Ein Klick klappt die Liste auf; Freigeben und
    // Ablehnen gehen hier direkt (dieselbe Antwort wie in den Entscheidungen, mit „Sicher?“ vor dem Freigeben).
    const antraege = S.antraege || [];
    const offene = antraege.length + (S.entscheidungen || []).length;
    const blinkt = S._blinken && S._blinken.has('posteingang');
    const post = d().el('button', 's-btn hs-einstellungen' + (offene ? ' neu' : '') + (blinkt ? ' blinkt' : ''), '✉ Posteingang' + (offene ? ' (' + offene + ')' : '')); post.type = 'button'; post.dataset.grundfunktion = 'entscheidungen';      // AM2-16: der Posteingang
    post.title = offene ? offene + ' warten auf deine Freigabe – Klick klappt sie auf' : 'Keine Anträge offen – hier erscheinen Anträge, die auf deine Freigabe warten';
    post.dataset.marke = 'hs-posteingang';
    post.setAttribute('aria-expanded', S._postOffen ? 'true' : 'false');
    post.onclick = ()=>{ S._postOffen = !S._postOffen; zeichnen(S); };
    const postBox = d().el('div', 'hs-post');
    if(S._postOffen){
      const alle = d().el('button', 'hs-knopf hs-klein', 'Alles im Posteingang ansehen'); alle.type = 'button'; alle.onclick = ()=>S.shellApi.decide();
      alle.title = 'Öffnet den Posteingang als App: Freigaben der Sitzungen, Anträge und Vorschläge in einer Liste';
      postBox.append(alle);
      if(!antraege.length) postBox.append(d().el('small', 'hs-leise', (S.entscheidungen || []).length ? 'Nur Freigaben der Sitzungen – sie stehen im Gespräch auf ihrer Karte.' : 'Nichts offen.'));
      antraege.forEach(x=>{
        const karte = d().el('div', 'hs-post-antrag');
        karte.append(d().el('div', 'hs-post-titel', x.title || x.id));
        if(x.note) karte.append(d().el('small', 'hs-leise', String(x.note).slice(0, 160)));
        (x.risks || []).slice(0, 3).forEach(rk=>karte.append(d().el('small', 'hs-leise', '⚠ ' + String(rk).slice(0, 200))));          // was die Freigabe bedeutet, steht vor dem Knopf
        const reihe = d().el('div', 'hs-post-reihe');
        const ways = x.ways || [];
        // Direkt freigeben nur, was wenig ändert: ein Ordner als Projekt. Alles andere (Katalog, Schalter, Cloud …) erst in den Entscheidungen, mit allen Angaben.
        const ja = FREIGABE_DIREKT.indexOf(x.kind) >= 0 ? ['freigeben_und_anwenden', 'einmal'].find(w=>ways.indexOf(w) >= 0) : null;
        const entscheide = async(way)=>{
          try{ await S.shellApi.decide(x.id, way); }catch(err){ S.hinweis('Nicht entschieden: ' + (err && err.message || err), 'warn'); }
          S.freigabenLaden();
        };
        if(ja){
          const k = d().el('button', 'hs-knopf hs-klein p', 'Freigeben'); k.type = 'button';
          k.onclick = ()=>{
            if(!k.dataset.sicher){                                    // zweiter Klick statt confirm(): ein Browser-Dialog antwortet in eingebetteten Fenstern still mit Nein
              k.dataset.sicher = '1'; k.textContent = 'Sicher? Freigeben';
              setTimeout(()=>{ if(k.isConnected){ delete k.dataset.sicher; k.textContent = 'Freigeben'; } }, SICHER_MS);
              return;
            }
            entscheide(ja);
          };
          reihe.append(k);
        }
        if(ways.indexOf('ablehnen') >= 0){
          const n = d().el('button', 'hs-knopf hs-klein', 'Ablehnen'); n.type = 'button'; n.onclick = ()=>entscheide('ablehnen'); reihe.append(n);
        }
        const mehr = d().el('button', 'hs-knopf hs-klein', 'Ansehen'); mehr.type = 'button';
        mehr.title = 'Öffnet den Posteingang mit allen Angaben zu diesem Antrag';
        mehr.onclick = ()=>S.shellApi.decide();
        reihe.append(mehr);
        karte.append(reihe); postBox.append(karte);
      });
    }
    const aufgaben = d().el('button', 's-btn hs-einstellungen', '⛨ Freigaben'); aufgaben.type = 'button';
    aufgaben.dataset.grundfunktion = 'aufgaben';                            // AM2-16: der Kernweg „Aufgaben“ (Reiter aufgaben:)
    aufgaben.title = 'Ein Ort für alles rund um Freigaben: was wartet, was gerade gilt (Aufgaben, Erlaubnisse) und die Regeln des Katalogs'; aufgaben.onclick = ()=>root.sedraHarness.reiter.oeffnen(S, 'aufgaben:');
    const einst = d().el('button', 's-btn hs-einstellungen', 'Einstellungen');
    einst.dataset.grundfunktion = 'einstellungen_zustand';                  // AM2-16
    einst.type = 'button';
    einst.title = 'Einstellungen (HS-42): Allgemein, Agent, Sprache, Integrationen, Lokale Modelle, System'; einst.dataset.marke = 'hs-einstellungen';
    einst.onclick = ()=>root.sedraHarness.einstellungen.oeffnen(S);           // Stufe 5
    el.replaceChildren(neu, liste, verkn, post, postBox, aufgaben, einst);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.seite = {exportieren, mount: S=>zeichnen(S), zeichnen, zeit};
})();
