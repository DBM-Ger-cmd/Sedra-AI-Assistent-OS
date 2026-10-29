// Harness-Shell – das Eingabefeld (HS-17, HS-53): mehrzeilig, Enter sendet, Umschalt+Enter neue Zeile; Stopp-Knopf (und Esc, shell.js).
// Daneben: „+“ (Dateien – ab Stufe 2), das Schild (wer in dieser Sitzung freigibt), das Modell (aus /api/models), das Mikrofon
// (der vorhandene Rekorder der Seite). `/` zeigt die Befehle, `@` die Dateien (ab Stufe 2). Ohne geladenes Modell steht
// „Kein Modell geladen – Modell wählen“ da, statt still zu scheitern. In einer leeren Sitzung steht darunter die Projektwahl (HS-04).

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const BEFEHLE = [['/neu', 'neue Sitzung'], ['/stopp', 'laufende Antwort abbrechen'], ['/titel Name', 'Sitzung umbenennen'], ['/seite', 'Seitenleiste ein/aus']];

  function mount(S){
    const box = S.el.eingabe;
    const feld = d().el('textarea', 'hs-feld');
    feld.rows = 1;
    feld.placeholder = 'Nachricht an SEDRA – Enter sendet, Umschalt+Enter neue Zeile, / für Befehle';
    feld.setAttribute('aria-label', 'Nachricht an SEDRA');
    feld.maxLength = 8000;
    const vorschlag = d().el('div', 'hs-vorschlag'); vorschlag.hidden = true;
    const plus = d().el('button', 'hs-rund', '+'); plus.type = 'button';
    plus.title = 'Dateien aus dem Projekt anhängen – kommt mit Stufe 2 (Werkzeuge)'; plus.setAttribute('aria-label', 'Datei anhängen');
    plus.onclick = ()=>S.hinweis('Dateien anhängen kommt mit Stufe 2 (Werkzeuge mit Freigabe).');
    const schild = d().el('span', 'hs-schild', '⛨ Captain gibt frei');
    schild.title = 'Wer in dieser Sitzung freigibt: der Captain (Karte im Verlauf oder Posteingang). Aufgaben-Freigabe kommt mit Stufe 3.';
    S.api('/api/harness/katalog').then(k=>{                    // HS-17/HS-26: das Schild sagt, wer freigibt und nach welchem Katalog
      if(k.fehler){ schild.textContent = '⛨ Katalog ungültig'; schild.classList.add('warn'); schild.title = 'Freigabe-Katalog: ' + k.fehler + ' – nur lesende Werkzeuge.'; return; }
      schild.textContent = '⛨ Captain gibt frei · Katalog ' + k.regeln.length + ' Regeln' + (k.quelle === 'vorlage' ? ' (Vorlage)' : '');
      S._eingabe.schildBasis = schild.textContent; S._eingabe.katalog = k;
      schildZeigen(S);
      schild.title = 'Freigabe-Katalog: ' + k.regeln.map(r=>r.id + ' = ' + r.stufe).join(', ') + '. Ohne Regel entscheidet der Captain; feste Vorbehalte gehen immer an ihn.';
    }).catch(()=>{});
    const modell = d().el('span', 'hs-modell', '…');
    const mikro = d().el('button', 'hs-rund', '🎙'); mikro.type = 'button';
    mikro.title = 'Rekorder (Aufnahme) öffnen'; mikro.setAttribute('aria-label', 'Rekorder öffnen');
    mikro.onclick = ()=>{
      const chip = [...document.querySelectorAll('.sx-hub-leiste .sx-chip')].find(c=>!c.classList.contains('sx-umschalter'));
      if(chip) chip.click(); else S.hinweis('Der Rekorder ist auf dieser Seite nicht da.', 'warn');
    };
    const senden = d().el('button', 'hs-senden p', 'Senden'); senden.type = 'button';
    senden.setAttribute('aria-label', 'Senden');
    const projekt = d().el('select', 'hs-projektwahl'); projekt.setAttribute('aria-label', 'Projekt der neuen Sitzung');
    const projektZeile = d().el('label', 'hs-projektzeile');
    projektZeile.append(d().el('span', 'hs-leise', 'Projekt'), projekt);
    const vorlage = d().el('select', 'hs-projektwahl'); vorlage.setAttribute('aria-label', 'Vorlage der neuen Sitzung');
    projektZeile.append(d().el('span', 'hs-leise', 'Vorlage'), vorlage);
    const kein = d().el('div', 'hs-kein-modell'); kein.hidden = true;
    const zeile = d().el('div', 'hs-eingabe-zeile');
    const werkzeuge = d().el('div', 'hs-eingabe-leiste');
    werkzeuge.append(plus, schild, modell, d().el('span', 'hs-luecke'), mikro, senden);
    zeile.append(feld, werkzeuge);
    box.append(kein, vorschlag, zeile, projektZeile);
    S._eingabe = {feld, senden, modell, projekt, vorlage, projektZeile, kein, vorschlag, schild, schildBasis: schild.textContent};

    const groesse = ()=>{ feld.style.height = 'auto'; feld.style.height = Math.min(feld.scrollHeight, Math.round(root.innerHeight * 0.4)) + 'px'; };
    feld.addEventListener('input', ()=>{ groesse(); hilfe(S); });
    feld.addEventListener('keydown', e=>{
      if(e.key === 'Enter' && !e.shiftKey && !e.isComposing){ e.preventDefault(); absenden(S); }
    });
    senden.onclick = ()=>{ const a = S.aktive(); if(a && a.laeuft()) a.stoppen(); else absenden(S); };
    S._groesse = groesse;
  }

  function hilfe(S){
    const e = S._eingabe, t = e.feld.value;
    e.vorschlag.replaceChildren();
    if(t.startsWith('/') && !t.includes('\n')){
      BEFEHLE.filter(([b])=>b.startsWith(t.split(' ')[0]) || t === '/').forEach(([b, was])=>{
        const r = d().clickable(d().el('div', 'hs-vorschlag-zeile'), ()=>{ e.feld.value = b.split(' ')[0] + (b.includes(' ') ? ' ' : ''); e.feld.focus(); hilfe(S); });
        r.append(d().el('b', null, b), d().el('small', 'hs-leise', was));
        e.vorschlag.append(r);
      });
    }else if(/(^|\s)@\S*$/.test(t)){
      e.vorschlag.append(d().el('div', 'hs-vorschlag-zeile', 'Dateien mit @ anhängen kommt mit Stufe 2 (Werkzeuge mit Freigabe).'));
    }
    e.vorschlag.hidden = !e.vorschlag.childNodes.length;
  }

  async function befehl(S, text){
    const [b, ...rest] = text.trim().split(/\s+/);
    const a = S.aktive();
    if(b === '/neu'){ root.sedraHarness.reiter.neu(S); return true; }
    if(b === '/stopp'){ if(a) a.stoppen(); return true; }
    if(b === '/seite'){ S.seiteUmschalten(); return true; }
    if(b === '/titel'){
      if(!a || !/^S-/.test(a.id)){ S.hinweis('Erst eine Nachricht senden – dann gibt es die Sitzung.'); return true; }
      await S.api('/api/harness/sitzungen/' + a.id, {method: 'PATCH', body: {titel: rest.join(' ')}});
      await S.sitzungenLaden();
      return true;
    }
    return false;
  }

  async function absenden(S){
    const e = S._eingabe, a = S.aktive();
    const text = e.feld.value.trim();
    if(!text || !a || a.laeuft()) return;
    if(text.startsWith('/') && !text.includes('\n')){
      try{ if(await befehl(S, text)){ e.feld.value = ''; hilfe(S); S._groesse(); return; } }
      catch(err){ S.hinweis('Befehl fehlgeschlagen: ' + err.message, 'bad'); return; }
    }
    e.feld.value = ''; hilfe(S); S._groesse();
    const ok = await a.senden(text, e.projekt.value || undefined, e.vorlage.value || undefined);
    if(!ok && !e.feld.value) e.feld.value = text;        // nichts verloren, wenn es nicht ging
    S._groesse();
    zustand(S);
  }

  function zustand(S){
    const e = S._eingabe; if(!e) return;
    const a = S.aktive();
    const laeuft = !!(a && a.laeuft());
    e.senden.textContent = laeuft ? 'Stopp' : 'Senden';
    e.senden.classList.toggle('stopp', laeuft);
    e.senden.title = laeuft ? 'Antwort abbrechen (Esc)' : 'Senden (Enter)';
    e.senden.setAttribute('aria-label', laeuft ? 'Antwort abbrechen' : 'Senden');
    e.projektZeile.hidden = !(a && !/^S-/.test(a.id));
  }

  function fuer(S, a){
    S.el.eingabe.classList.toggle('hs-aus', !!a && /^(aufgaben|lauf|diff):/.test(String(a.id)));      // in Aufgaben-, Lauf- und Diff-Reitern gibt es nichts zu schreiben
    zustand(S); fokus(S); schildZeigen(S);
  }

  // HS-17/HS-26/HS-27: das Schild sagt, wer in dieser Sitzung freigibt – der Captain, der Vorarbeiter für Stufe „vorarbeiter“ – und welche Aufgabe gilt.
  function schildZeigen(S){
    const e = S._eingabe; if(!e) return;
    const a = S.aktive();
    const sid = a && /^S-/.test(a.id) ? a.id : null;
    const s = sid && S.sitzung(sid);
    const vorarbeiter = S.vorarbeiter && s ? S.vorarbeiter[s.projekt] : null;
    let text = e.schildBasis, hinweis = e.schild.title;
    if(vorarbeiter && vorarbeiter.sitzung_id === sid){ text = '⚑ Du bist Vorarbeiter · Stufe captain bleibt beim Captain'; }
    else if(vorarbeiter){ text = text.replace('Captain gibt frei', 'Vorarbeiter gibt frei (Stufe vorarbeiter)'); }
    const aufgabe = (S.aufgaben || []).find(x=>x.status === 'aktiv' && sid && x.sitzungen.indexOf(sid) >= 0);
    if(aufgabe){
      const rest = [aufgabe.rest_aufrufe !== null && aufgabe.rest_aufrufe !== undefined ? 'Rest ' + aufgabe.rest_aufrufe : null, aufgabe.rest_min !== null && aufgabe.rest_min !== undefined ? root.sedraHarness.aufgabe.minuten(aufgabe) : null].filter(Boolean).join(', ');
      text += ' · Aufgabe ' + aufgabe.id + (rest ? ' (' + rest + ')' : '');
      hinweis = 'Aufgabe „' + aufgabe.titel + '“ gilt für diese Sitzung: ' + aufgabe.erlaubt.map(x=>x.werkzeug + ' ' + x.muster).join('; ');
    }
    if(!e.katalog || !e.katalog.fehler){ e.schild.textContent = text; if(aufgabe || vorarbeiter) e.schild.title = hinweis; }
    e.schild.classList.toggle('aufgabe', !!aufgabe);
    e.schild.classList.toggle('vorarbeiter', !!vorarbeiter);
  }

  function vorlagenwahl(S){
    const e = S._eingabe; if(!e) return;
    const vorher = e.vorlage.value;
    const keine = document.createElement('option'); keine.value = ''; keine.textContent = 'ohne Vorlage';
    e.vorlage.replaceChildren(keine, ...(S.vorlagen || []).filter(v=>!v.fehler).map(v=>{ const o = document.createElement('option'); o.value = v.id; o.textContent = v.name; o.title = v.beschreibung || ''; return o; }));
    if(vorher) e.vorlage.value = vorher;
  }

  function fokus(S){ const e = S._eingabe; if(e) setTimeout(()=>e.feld.focus(), 0); }

  function modellZeigen(S){
    const e = S._eingabe; if(!e) return;
    const m = S.modell;
    e.modell.textContent = m ? m.name : 'kein Modell';
    e.modell.title = m ? ('Geladen: ' + m.name + (m.kontext ? ' · Kontext ' + Number(m.kontext).toLocaleString('de-DE') : '') + ' – laden und wechseln in der Werkstatt (Cockpit)')
                       : 'Kein Modell geladen';
    e.modell.classList.toggle('aus', !m);
    e.kein.hidden = !!m;
    e.kein.textContent = 'Kein Modell geladen – Modell wählen (Werkstatt im Cockpit; Wechsel über Start unten links).';
  }

  function projektwahl(S){
    const e = S._eingabe; if(!e) return;
    const vorher = e.projekt.value;
    e.projekt.replaceChildren(...S.projekte.map(p=>{ const o = document.createElement('option'); o.value = p.id; o.textContent = p.name; return o; }));
    if(vorher && S.projekte.some(p=>p.id === vorher)) e.projekt.value = vorher;
    zustand(S);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.eingabe = {mount, zustand, fuer, fokus, modellZeigen, projektwahl, schildZeigen, vorlagenwahl, BEFEHLE};
})();
