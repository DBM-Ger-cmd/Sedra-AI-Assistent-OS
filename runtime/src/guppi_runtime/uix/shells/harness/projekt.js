// Harness-Shell – „Ordner öffnen“ und Vorgaben (Bau 1.11.2026, P0 M3 – aus dem Harness-Vergleich 31.10.): statt Konfig-Datei plus Neustart
// stellt der Captain hier einen Antrag (POST /api/harness/projekte → Posteingang „Ordner als Projekt öffnen“); nach der Freigabe kommt
// `harness.projekt` und die Projektwahl kennt den Ordner. „Als Vorgabe merken“ (POST /api/harness/vorgaben) macht Projekt bzw. Rezept zum
// Standard neuer Sitzungen. Der Browser kennt keine Ordnerpfade – der Pfad wird getippt oder eingefügt. Daten werden nie zu HTML.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const d = ()=>root.sedraDom;

  function vorgaben(S){ return S.vorgaben || (S.vorgaben = {rezept_standard: null, projekt_standard: null, auto_laden: null}); }

  // Das Formular unter der Projektzeile: Pfad, Name, Schreibbereich → Antrag. Gibt {box, oeffnen, schliessen}.
  function formular(S){
    const box = d().el('form', 'hs-ordner'); box.hidden = true; box.setAttribute('aria-label', 'Ordner als Projekt öffnen');
    const pfad = d().el('input', 'hs-ordner-feld'); pfad.placeholder = 'Vollständiger Pfad, z. B. D:\\Arbeit\\mein-projekt oder /home/ich/projekt'; pfad.setAttribute('aria-label', 'Ordner');
    const name = d().el('input', 'hs-ordner-feld kurz'); name.placeholder = 'Name (sonst der Ordnername)'; name.setAttribute('aria-label', 'Name');
    const bereich = d().el('input', 'hs-ordner-feld kurz'); bereich.value = '**'; bereich.setAttribute('aria-label', 'Schreibbereich'); bereich.title = 'Muster relativ zum Ordner, mit Komma getrennt; ** = überall darin';
    const senden = d().el('button', 'hs-senden p', 'Antrag stellen'); senden.type = 'submit';
    const zu = d().el('button', 'hs-knopf', 'Abbrechen'); zu.type = 'button';
    const satz = d().el('div', 'hs-leise', 'Der Ordner wird nach deiner Freigabe im Posteingang zum Projekt – ohne Neustart. Das Modell darf darin nach Katalog schreiben; außerhalb nie.');
    const stand = d().el('div', 'hs-leise hs-ordner-stand'); stand.setAttribute('role', 'status');
    const zeile = d().el('div', 'hs-ordner-zeile'); zeile.append(name, bereich, senden, zu);
    box.append(pfad, zeile, satz, stand);
    const schliessen = ()=>{ box.hidden = true; stand.textContent = ''; };
    zu.onclick = schliessen;
    box.onsubmit = async e=>{
      e.preventDefault();
      if(!pfad.value.trim()){ stand.textContent = 'Ein Pfad fehlt.'; pfad.focus(); return; }
      senden.disabled = true; stand.textContent = 'Antrag wird gestellt …';
      try{
        const muster = bereich.value.split(',').map(x=>x.trim()).filter(Boolean);
        const out = await S.api('/api/harness/projekte', {method: 'POST', body: {wurzel: pfad.value.trim(), name: name.value.trim() || undefined, schreibbereich: muster.length ? muster : undefined}});
        stand.textContent = 'Antrag gestellt: „' + (out.projekt && out.projekt.name) + '“ – Entscheidung im Posteingang (Freigaben). Danach steht der Ordner in der Projektwahl.';
        S.hinweis('Ordner öffnen: Antrag im Posteingang.', 'note');
        if(S.freigabenLaden) S.freigabenLaden();
      }catch(err){ stand.textContent = 'Nicht gestellt: ' + err.message; }
      finally{ senden.disabled = false; }
    };
    return {box, oeffnen(){ box.hidden = false; pfad.focus(); }, schliessen};
  }

  // „Neues Projekt …“ (Captain 04.11.2026): Name und übergeordneter Ordner → Antrag; der Ordner wird erst nach der Freigabe im Posteingang angelegt und ist dann ein Projekt.
  // Der übergeordnete Ordner ist vorbelegt mit dem Ordner über der Wurzel des ersten Projekts (dort liegen auch die anderen), sonst wird er getippt.
  function elternVorschlag(S){
    const w = String(((S.projekte || [])[0] || {}).wurzel || '').replace(/[\\/]+$/, '');
    const i = Math.max(w.lastIndexOf('/'), w.lastIndexOf(String.fromCharCode(92)));
    return i > 0 ? w.slice(0, i) : '';
  }
  function formularNeu(S){
    const box = d().el('form', 'hs-ordner'); box.hidden = true; box.setAttribute('aria-label', 'Neues Projekt anlegen');
    const name = d().el('input', 'hs-ordner-feld'); name.placeholder = 'Name des neuen Projekts (wird auch der Ordnername)'; name.setAttribute('aria-label', 'Name');
    const eltern = d().el('input', 'hs-ordner-feld'); eltern.placeholder = 'Ordner, in dem es angelegt wird (vollständiger Pfad)'; eltern.setAttribute('aria-label', 'Übergeordneter Ordner');
    const bereich = d().el('input', 'hs-ordner-feld kurz'); bereich.value = '**'; bereich.setAttribute('aria-label', 'Schreibbereich'); bereich.title = 'Muster relativ zum Ordner, mit Komma getrennt; ** = überall darin';
    const senden = d().el('button', 'hs-senden p', 'Antrag stellen'); senden.type = 'submit';
    const zu = d().el('button', 'hs-knopf', 'Abbrechen'); zu.type = 'button';
    const satz = d().el('div', 'hs-leise', 'Der Ordner wird erst nach deiner Freigabe im Posteingang angelegt und ist dann ein Projekt – ohne Neustart. Das Modell darf darin nach Katalog schreiben; außerhalb nie.');
    const stand = d().el('div', 'hs-leise hs-ordner-stand'); stand.setAttribute('role', 'status');
    const zeile = d().el('div', 'hs-ordner-zeile'); zeile.append(bereich, senden, zu);
    box.append(name, eltern, zeile, satz, stand);
    const schliessen = ()=>{ box.hidden = true; stand.textContent = ''; };
    zu.onclick = schliessen;
    box.onsubmit = async e=>{
      e.preventDefault();
      if(!name.value.trim()){ stand.textContent = 'Ein Name fehlt.'; name.focus(); return; }
      if(!eltern.value.trim()){ stand.textContent = 'Der übergeordnete Ordner fehlt.'; eltern.focus(); return; }
      senden.disabled = true; stand.textContent = 'Antrag wird gestellt …';
      try{
        const muster = bereich.value.split(',').map(x=>x.trim()).filter(Boolean);
        const out = await S.api('/api/harness/projekte', {method: 'POST', body: {anlegen: true, name: name.value.trim(), eltern: eltern.value.trim(), schreibbereich: muster.length ? muster : undefined}});
        stand.textContent = 'Antrag gestellt: „' + (out.projekt && out.projekt.name) + '“ in ' + (out.projekt && out.projekt.wurzel) + ' – Entscheidung im Posteingang (Freigaben). Danach steht es in der Projektwahl.';
        S.hinweis('Neues Projekt: Antrag im Posteingang.', 'note');
        if(S.freigabenLaden) S.freigabenLaden();
      }catch(err){ stand.textContent = 'Nicht gestellt: ' + err.message; }
      finally{ senden.disabled = false; }
    };
    return {box, oeffnen(){ box.hidden = false; if(!eltern.value) eltern.value = elternVorschlag(S); name.focus(); }, schliessen};
  }

  // Die Knöpfe neben der Projektwahl: „Ordner öffnen …“, „Neues Projekt …“ und „Als Vorgabe merken“. `wahl` ist das <select> der Projekte.
  function knoepfe(S, zeile, wahl){
    const f = formular(S);
    const fn = formularNeu(S);
    const neu = d().el('button', 'hs-knopf hs-ordner-knopf', 'Neues Projekt …'); neu.type = 'button'; neu.title = 'Einen neuen Ordner anlegen und als Projekt öffnen (Antrag mit Freigabe)';
    neu.onclick = ()=>{ f.schliessen(); if(fn.box.hidden) fn.oeffnen(); else fn.schliessen(); };
    const auf = d().el('button', 'hs-knopf hs-ordner-knopf', 'Ordner öffnen …'); auf.type = 'button'; auf.title = 'Einen Ordner außerhalb des Repos als Projekt öffnen (Antrag mit Freigabe)';
    auf.onclick = ()=>{ fn.schliessen(); if(f.box.hidden) f.oeffnen(); else f.schliessen(); };
    const merken = d().el('button', 'hs-knopf hs-vorgabe-knopf', 'Als Vorgabe merken'); merken.type = 'button'; merken.title = 'Dieses Projekt ist dann der Standard neuer Sitzungen';
    merken.onclick = ()=>setzen(S, {projekt_standard: wahl.value || null}, merken);
    zeile.append(auf, neu, merken);
    if(zeile.parentNode){ zeile.parentNode.insertBefore(f.box, zeile.nextSibling); zeile.parentNode.insertBefore(fn.box, f.box.nextSibling); }
    return {formular: f, formularNeu: fn, auf, neu, merken, zeigen(){ merken.hidden = !wahl.value || vorgaben(S).projekt_standard === wahl.value; }};
  }

  async function setzen(S, teil, knopf){
    if(knopf) knopf.disabled = true;
    try{
      const v = await S.api('/api/harness/vorgaben', {method: 'POST', body: teil});
      Object.assign(vorgaben(S), v);
      S.hinweis('Vorgabe gemerkt.', 'note');
    }catch(err){ S.hinweis('Vorgabe nicht gemerkt: ' + err.message, 'bad'); }
    finally{ if(knopf) knopf.disabled = false; }
  }

  async function laden(S){
    try{ Object.assign(vorgaben(S), await S.api('/api/harness/vorgaben')); }catch(_e){}
    return vorgaben(S);
  }

  root.sedraHarness = root.sedraHarness || {};
  root.sedraHarness.projekt = {formular, formularNeu, elternVorschlag, knoepfe, setzen, laden, vorgaben};
})();
