// Harness-Shell – das Kontextmenü (Captain 05.11.2026: Rechtsklick auf etwas in Sedra öffnet ein Menü innerhalb von Sedra, mit der Option, es im Chat anzupassen – und damit wird die
// Oberfläche wirklich modular). Jedes Modul der Oberfläche meldet sich mit `kontext.registrieren({id, titel, selektor, dateien, ...})` an: unter welchem Namen es im Menü steht, an
// welchem Selektor man es erkennt und in welchen Dateien es lebt. Ein Rechtsklick sucht von der angeklickten Stelle nach außen die angemeldeten Module; das Menü nennt den Ort
// („Taskleiste › Statuszelle“) und bietet „Im Chat anpassen“ (hängt Ort, Modul, Dateien und den sichtbaren Text als Entwurf an das Eingabefeld – der Captain schreibt dazu, was anders
// sein soll), „Frage dazu stellen“ und „Kopieren“; ein Modul kann eigene Einträge liefern (`eintraege(S, element)`). Umschalt+Rechtsklick und Eingabefelder behalten das Menü des Browsers.
// Alle Texte kommen als textContent in die Oberfläche, nie als HTML. Neue Module melden sich in ihrer eigenen Datei an; die Tabelle der bestehenden steht in kontextmodule.js.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;
  const PFAD = 'runtime/src/sedra_runtime/uix/shells/harness/';
  const INHALT_MAX = 240;
  const REG = [];
  let offen = null;                                               // das geöffnete Menü: {el, weg}

  // ---- die Anmeldung der Module
  function registrieren(m){
    if(!m || typeof m.id !== 'string' || typeof m.selektor !== 'string' || typeof m.titel !== 'string') throw new Error('kontext_modul_ungueltig');
    const eintrag = {id: m.id, titel: m.titel, selektor: m.selektor, dateien: Array.isArray(m.dateien) ? m.dateien.slice() : [], eintraege: typeof m.eintraege === 'function' ? m.eintraege : null};
    const i = REG.findIndex(x=>x.id === m.id);
    if(i >= 0) REG[i] = eintrag; else REG.push(eintrag);
    return eintrag;
  }
  const liste = ()=>REG.map(m=>({id: m.id, titel: m.titel, selektor: m.selektor, dateien: m.dateien.slice()}));

  // Von der angeklickten Stelle nach außen: jedes angemeldete Modul, dessen Selektor passt (das innerste zuerst, jedes Modul einmal).
  function finden(el){
    const out = [], gesehen = new Set();
    for(let n = el; n && n.nodeType === 1; n = n.parentElement){
      for(const m of REG){
        if(gesehen.has(m.id)) continue;
        let passt = false;
        try{ passt = n.matches(m.selektor); }catch(_e){ passt = false; }
        if(passt){ gesehen.add(m.id); out.push({modul: m, element: n}); }
      }
    }
    return out;
  }

  const kurz = (text, n)=>{ const t = String(text || '').replace(/\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n - 1) + '…' : t; };
  function inhaltVon(el){
    const sel = root.getSelection ? String(root.getSelection() || '') : '';
    return kurz(sel && el.contains(root.getSelection().anchorNode) ? sel : el.innerText || el.textContent, INHALT_MAX);
  }

  // Der Text, den „Im Chat anpassen“ und „Frage dazu stellen“ in das Eingabefeld legen. Rein, damit man ihn prüfen kann.
  function entwurf(modus, treffer, inhalt){
    const innen = treffer[0].modul;
    const ort = treffer.map(t=>t.modul.titel).reverse().join(' › ');
    const dateien = innen.dateien.length ? innen.dateien.map(f=>PFAD + f).join(', ') : 'keine Datei angemeldet';
    return [modus === 'anpassen' ? 'Passe diesen Teil der Oberfläche von Sedra an:' : 'Erkläre mir diesen Teil der Oberfläche von Sedra:',
            'Teil: ' + ort, 'Modul: ' + innen.id + ' (' + dateien + ')', inhalt ? 'Sichtbarer Inhalt: „' + inhalt + '“' : null,
            modus === 'anpassen' ? 'Was soll anders sein: ' : 'Meine Frage: '].filter(Boolean).join('\n');
  }

  // ---- in den Chat legen (öffnet bei Bedarf ein neues Gespräch, damit es ein Eingabefeld gibt)
  function insChat(S, text){
    const H = root.sedraHarness;
    if(S.el.eingabe.classList.contains('hs-aus') && H.reiter) H.reiter.neu(S);
    const f = S._eingabe && S._eingabe.feld;
    if(!f){ S.hinweis('Hier gibt es kein Eingabefeld – öffne ein Gespräch.', 'warn'); return false; }
    f.value = f.value.trim() ? f.value.replace(/\s+$/, '') + '\n\n' + text : text;
    f.dispatchEvent(new Event('input'));
    f.focus();
    f.selectionStart = f.selectionEnd = f.value.length;
    return true;
  }
  async function kopieren(S, text){
    try{ await root.navigator.clipboard.writeText(text); S.hinweis('Kopiert.'); }
    catch(_e){ S.hinweis('Nicht kopiert – der Browser hat die Zwischenablage nicht freigegeben.', 'warn'); }
  }

  // ---- das Menü
  function eintraegeFuer(S, treffer){
    const inhalt = inhaltVon(treffer[0].element);
    const eigene = [];
    treffer.forEach(t=>{ if(t.modul.eintraege){ try{ eigene.push(...(t.modul.eintraege(S, t.element) || [])); }catch(_e){ /* ein kaputtes Modul stört das Menü nicht */ } } });
    return eigene.concat(eigene.length ? ['-'] : [], [
      {text: 'Im Chat anpassen …', tun: ()=>insChat(S, entwurf('anpassen', treffer, inhalt))},
      {text: 'Frage dazu stellen', tun: ()=>insChat(S, entwurf('frage', treffer, inhalt))},
      '-',
      {text: 'Kopieren', tun: ()=>kopieren(S, inhalt)},
      {text: 'Aus Zwischenablage einfügen', tun: ()=>einfuegen(S)},
      '-',
      // wie im Rechtsklick-Menü des Desktops (Neuer Chat, Dokument öffnen) und wie bei herdr (neuer Tab aus dem Menü): die Dinge, die man oft braucht, an jeder Stelle
      {text: 'Neues Gespräch', tun: ()=>{ if(root.sedraHarness.reiter) root.sedraHarness.reiter.neu(S); }},
      {text: 'Datei anhängen …', tun: ()=>{ if(root.sedraHarness.reiter && S.el.eingabe.classList.contains('hs-aus')) root.sedraHarness.reiter.neu(S); if(root.sedraHarness.anhang) root.sedraHarness.anhang.oeffnen(S); }}]);
  }
  async function einfuegen(S){
    let text = '';
    try{ text = await root.navigator.clipboard.readText(); }catch(_e){ S.hinweis('Die Zwischenablage ist nicht freigegeben – füge mit Strg+V im Eingabefeld ein.', 'warn'); return; }
    if(text) insChat(S, text);
  }

  function schliessen(){
    if(!offen) return;
    const o = offen; offen = null;
    o.weg();
    o.el.remove();
  }

  function zeigen(S, x, y, treffer){
    schliessen();
    const menue = d().el('div', 'hs-ctxmenu'); menue.setAttribute('role', 'menu');
    const kopf = d().el('div', 'hs-ctxmenu-kopf');
    kopf.append(d().el('b', null, treffer.map(t=>t.modul.titel).reverse().join(' › ')),
                d().el('small', 'hs-leise', treffer[0].modul.dateien.length ? treffer[0].modul.dateien.join(', ') : 'Modul ' + treffer[0].modul.id));
    menue.append(kopf);
    const knoepfe = [];
    eintraegeFuer(S, treffer).forEach(e=>{
      if(e === '-'){ menue.append(d().el('div', 'hs-ctxmenu-strich')); return; }
      const k = d().el('button', 'hs-ctxmenu-punkt', e.text); k.type = 'button'; k.setAttribute('role', 'menuitem');
      k.onclick = ()=>{ schliessen(); try{ e.tun(); }catch(err){ S.hinweis('Das ging nicht: ' + (err && err.message || err), 'warn'); } };
      knoepfe.push(k); menue.append(k);
    });
    menue.append(d().el('small', 'hs-leise hs-ctxmenu-fuss', 'Umschalt+Rechtsklick: Menü des Browsers'));
    document.body.append(menue);
    const b = menue.getBoundingClientRect();
    menue.style.left = Math.max(4, Math.min(x, root.innerWidth - b.width - 4)) + 'px';
    menue.style.top = Math.max(4, Math.min(y, root.innerHeight - b.height - 4)) + 'px';
    const ausserhalb = ev=>{ if(!menue.contains(ev.target)) schliessen(); };
    const taste = ev=>{
      if(ev.key === 'Escape'){ ev.preventDefault(); schliessen(); return; }
      const i = knoepfe.indexOf(document.activeElement);
      if(ev.key === 'ArrowDown'){ ev.preventDefault(); knoepfe[(i + 1) % knoepfe.length].focus(); }
      else if(ev.key === 'ArrowUp'){ ev.preventDefault(); knoepfe[(i - 1 + knoepfe.length) % knoepfe.length].focus(); }
    };
    document.addEventListener('pointerdown', ausserhalb, true);
    document.addEventListener('keydown', taste, true);
    root.addEventListener('resize', schliessen);
    root.addEventListener('blur', schliessen);
    document.addEventListener('scroll', schliessen, true);
    offen = {el: menue, weg(){
      document.removeEventListener('pointerdown', ausserhalb, true); document.removeEventListener('keydown', taste, true);
      root.removeEventListener('resize', schliessen); root.removeEventListener('blur', schliessen); document.removeEventListener('scroll', schliessen, true);
    }};
    if(knoepfe[0]) knoepfe[0].focus();
  }

  // Rechtsklick: Eingabefelder und Umschalt+Rechtsklick behalten das Menü des Browsers; sonst öffnet das Menü von Sedra, wenn ein Modul zur Stelle passt.
  function mount(S){
    document.addEventListener('contextmenu', ev=>{
      if(ev.shiftKey || ev.defaultPrevented) return;
      const t = ev.target;
      if(!t || !t.closest || t.closest('input, textarea, select, [contenteditable="true"], .hs-ctxmenu')) return;
      const treffer = finden(t);
      if(!treffer.length) return;
      ev.preventDefault();
      zeigen(S, ev.clientX, ev.clientY, treffer);
    });
  }

  root.sedraHarness = root.sedraHarness || {};
  // Ein ganzes Modul (ohne angeklickten Teil) als Entwurf in den Chat – für den Desktop Builder
  function modulAnpassen(S, id){
    const m = REG.find(x=>x.id === id);
    if(!m) return false;
    return insChat(S, entwurf('anpassen', [{modul: m, element: null}], ''));
  }

  root.sedraHarness.kontext = {registrieren, liste, finden, entwurf, mount, schliessen, modulAnpassen, PFAD};
})();
