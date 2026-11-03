// Harness-Shell – Hinweis und Bestätigung einer Vorlage mit weitreichenden Freigaben (MasterChat, Captain 03.11.2026): Unter der Vorlagenwahl steht, wofür die Vorlage da ist
// und was sie braucht; beim Anlegen einer Sitzung mit solchen Vorlagen fragt ein Dialog den Captain ausdrücklich, und nur sein Ja schickt `erlaubnisse_bestaetigt` an den Server.
// Ohne Ja gibt es keine Sitzung. Die Erlaubnisse gelten dann nur für diese Sitzung und lassen sich unter Einstellungen → Agent → Freigabe-Modus zurücknehmen. Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const WAS = {datei_schreiben: 'Dateien neu schreiben', datei_aendern: 'Dateien ändern', befehl: 'Befehl ausführen', lauf_starten: 'Lauf starten'};

  function vorlage(S, id){ return (S.vorlagen || []).find(v=>v.id === id) || null; }

  // einklappbar (Captain 03.11.2026): die Wahl wird je Vorlage im Browser gemerkt, ohne Speicher bleibt der Hinweis aufgeklappt
  const KLAPP = 'sedra.harness.hinweis.zu.';
  function zu(id){ try{ return localStorage.getItem(KLAPP + id) === '1'; }catch(_e){ return false; } }
  function merken(id, an){ try{ an ? localStorage.setItem(KLAPP + id, '1') : localStorage.removeItem(KLAPP + id); }catch(_e){ /* ohne Speicher bleibt es bei dieser Ansicht */ } }

  // der Text unter der Vorlagenwahl: eine Kopfzeile zum Ein- und Ausklappen, darunter der Hinweis
  function zeigen(S){
    const e = S._eingabe; if(!e || !e.vorlageHinweis) return;
    const v = vorlage(S, e.vorlage.value);
    const text = v && v.hinweis ? v.hinweis : '';
    const box = e.vorlageHinweis;
    box.replaceChildren();
    box.hidden = !text;
    box.classList.toggle('warn', !!(v && (v.erlaubnisse || []).length));
    if(!text) return;
    const kopf = d().el('button', 'hs-hinweis-kopf'); kopf.type = 'button';
    const inhalt = d().el('div', 'hs-hinweis-text', text);
    const stellen = klappt=>{
      box.classList.toggle('zu', klappt); inhalt.hidden = klappt;
      kopf.textContent = (klappt ? '▸ ' : '▾ ') + v.name + (klappt ? ' – Hinweis anzeigen' : ' – Hinweis');
      kopf.setAttribute('aria-expanded', klappt ? 'false' : 'true');
    };
    kopf.onclick = ()=>{ const klappt = !box.classList.contains('zu'); merken(v.id, klappt); stellen(klappt); };
    box.append(kopf, inhalt);
    stellen(zu(v.id));
  }

  // Der Dialog: Promise<boolean>. Der Fokus liegt auf „Abbrechen“ (Enter gibt nichts frei), Escape bricht ab.
  function bestaetigen(S, v){
    return new Promise(fertig=>{
      const haube = d().el('div', 'hs-dialog-haube');
      const box = d().el('div', 'hs-dialog'); box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true'); box.setAttribute('aria-label', v.name + ' braucht weitreichende Freigaben');
      box.append(d().el('h3', null, '„' + v.name + '“ braucht weitreichende Freigaben'),
                 d().el('p', null, v.hinweis || ''),
                 d().el('div', 'hs-leise', 'Diese Sitzung darf dann ohne Karte:'));
      const liste = d().el('ul', 'hs-dialog-liste');
      (v.erlaubnisse || []).forEach(e=>liste.append(d().el('li', null, (WAS[e.werkzeug] || e.werkzeug) + ': ' + e.muster)));
      box.append(liste,
                 d().el('small', 'hs-leise', 'Feste Vorbehalte gelten trotzdem: Kern, Guard, Freigabe-Code, Vorlagen, local_config, .git, Netz, Installieren, Löschen und Git-Push gehen nie ohne dich.'));
      const knoepfe = d().el('div', 'hs-dialog-knoepfe');
      const schliessen = ja=>{ haube.remove(); document.removeEventListener('keydown', taste, true); fertig(ja); };
      const nein = d().el('button', 'hs-knopf', 'Abbrechen'); nein.type = 'button'; nein.onclick = ()=>schliessen(false);
      const ok = d().el('button', 'hs-senden', 'Ja, diese Sitzung darf das'); ok.type = 'button'; ok.onclick = ()=>schliessen(true);
      knoepfe.append(nein, ok); box.append(knoepfe);
      const taste = e=>{ if(e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); schliessen(false); } };
      document.addEventListener('keydown', taste, true);
      haube.append(box); (S.el.haupt || document.body).append(haube);
      nein.focus();
    });
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.vorlagenhinweis = {vorlage, zeigen, bestaetigen};
})();
