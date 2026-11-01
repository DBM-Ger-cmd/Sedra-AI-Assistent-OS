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

  // Die Knöpfe neben der Projektwahl: „Ordner öffnen …“ und „Als Vorgabe merken“. `wahl` ist das <select> der Projekte.
  function knoepfe(S, zeile, wahl){
    const f = formular(S);
    const auf = d().el('button', 'hs-knopf hs-ordner-knopf', 'Ordner öffnen …'); auf.type = 'button'; auf.title = 'Einen Ordner außerhalb des Repos als Projekt öffnen (Antrag mit Freigabe)';
    auf.onclick = ()=>{ if(f.box.hidden) f.oeffnen(); else f.schliessen(); };
    const merken = d().el('button', 'hs-knopf hs-vorgabe-knopf', 'Als Vorgabe merken'); merken.type = 'button'; merken.title = 'Dieses Projekt ist dann der Standard neuer Sitzungen';
    merken.onclick = ()=>setzen(S, {projekt_standard: wahl.value || null}, merken);
    zeile.append(auf, merken);
    zeile.parentNode && zeile.parentNode.insertBefore(f.box, zeile.nextSibling);
    return {formular: f, auf, merken, zeigen(){ merken.hidden = !wahl.value || vorgaben(S).projekt_standard === wahl.value; }};
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
  root.sedraHarness.projekt = {formular, knoepfe, setzen, laden, vorgaben};
})();
